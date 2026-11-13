"""
PDF form reader: lists every fillable field in every PDF under a folder.

Runs entirely on this computer. It makes no internet connection, sends nothing
anywhere, and never changes, moves or copies the source files. Zip files are
read in memory; nothing inside them is unpacked to disk.

It writes two spreadsheets (CSV files that open in Excel) to a results folder:

  fields.csv  one row per form field: where it came from, its type
              (text box, checkbox, radio buttons, dropdown, list, signature),
              its value, and the choices a dropdown or radio group offered.
  files.csv   one row per PDF: whether its form could be read, and if not, why.

Usage (see README.md for step-by-step instructions):

  python pdf_form_reader.py "D:\\Jobs\\2026"
  python pdf_form_reader.py "D:\\Jobs\\2026" --out "C:\\Users\\me\\Desktop\\form-results"
  python pdf_form_reader.py "D:\\Jobs\\2026\\March" --start month

The results contain real client data. Keep them on this computer, and delete
them once the values have been checked and imported.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import os
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject, IndirectObject, NameObject
except ImportError:  # pragma: no cover - friendly message for a first run
    sys.exit(
        "The PDF library is not installed yet.\n"
        "Run this once, then try again:\n"
        "  Windows:  py -m pip install -r requirements.txt\n"
        "  Mac:      python3 -m pip install -r requirements.txt"
    )

# pypdf prints a warning for every small flaw in a PDF; the files.csv note is enough.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# Zip safety limits: a zip inside a zip inside a zip is read, deeper is not,
# and a single file inside a zip larger than this is skipped rather than read
# into memory.
MAX_ZIP_DEPTH = 3
MAX_MEMBER_BYTES = 300 * 1024 * 1024

# PDF field flag bits (PDF 1.7 specification, section 12.7).
FF_READ_ONLY = 1 << 0
FF_REQUIRED = 1 << 1
FF_RADIO = 1 << 15
FF_PUSHBUTTON = 1 << 16
FF_COMBO = 1 << 17
FF_MULTISELECT = 1 << 21

FIELD_COLUMNS = [
    "Month",
    "Job folder",
    "File",
    "Page",
    "Field name",
    "Field label",
    "Field type",
    "Value",
    "Filled in",
    "Choices offered",
    "Raw value",
    "Read-only",
    "Required",
]
FILE_COLUMNS = [
    "Month",
    "Job folder",
    "File",
    "Result",
    "Fields",
    "Fields filled in",
    "Note",
]

# Folder names that mean "this syncs to the cloud" (results would leave the computer).
CLOUD_SYNC_MARKERS = ("OneDrive", "iCloud", "Mobile Documents", "Dropbox", "Google Drive", "Box Sync")

# Result wording used in files.csv.
RESULT_READ = "Form fields read"
RESULT_NO_FORM = "No fillable fields"
RESULT_PASSWORD = "Password-protected - not read"
RESULT_UNREADABLE = "Could not be read"
RESULT_SKIPPED = "Skipped"


@dataclass
class FieldRow:
    name: str
    label: str
    kind: str
    value: str
    filled: bool
    choices: str
    raw: str
    pages: str
    read_only: bool
    required: bool


@dataclass
class PdfResult:
    result: str
    note: str = ""
    fields: list[FieldRow] = field(default_factory=list)


# --------------------------------------------------------------------------
# Reading one PDF
# --------------------------------------------------------------------------

def _text(obj) -> str:
    """A PDF value as plain text. Names lose their leading slash."""
    if obj is None:
        return ""
    obj = obj.get_object() if isinstance(obj, IndirectObject) else obj
    if isinstance(obj, NameObject):
        return str(obj)[1:]
    if isinstance(obj, (list, ArrayObject)):
        return "; ".join(_text(o) for o in obj)
    if isinstance(obj, bytes):
        return obj.decode("latin-1", errors="replace")
    return str(obj)


def _ref_id(obj):
    return (obj.idnum, obj.generation) if isinstance(obj, IndirectObject) else None


def _options(opt) -> list[tuple[str, str]]:
    """Dropdown/list options as (export value, text shown) pairs."""
    pairs = []
    for item in (opt.get_object() if opt is not None else []) or []:
        item = item.get_object() if isinstance(item, IndirectObject) else item
        if isinstance(item, (list, ArrayObject)) and len(item) >= 2:
            pairs.append((_text(item[0]), _text(item[1])))
        else:
            pairs.append((_text(item), _text(item)))
    return pairs


def _widget_states(widgets) -> list[str]:
    """The 'on' states a checkbox or radio group's buttons can take."""
    states = []
    for w in widgets:
        ap = w.get("/AP")
        ap = ap.get_object() if ap is not None else None
        normal = ap.get("/N") if ap is not None else None
        normal = normal.get_object() if normal is not None else None
        if hasattr(normal, "keys"):
            for key in normal.keys():
                name = _text(NameObject(key)) if not isinstance(key, NameObject) else _text(key)
                if name != "Off" and name not in states:
                    states.append(name)
    return states


def _current_state(value: str, widgets) -> str:
    """A button's selected state: the field value, else the widgets' own state."""
    if value and value != "Off":
        return value
    for w in widgets:
        state = _text(w.get("/AS"))
        if state and state != "Off":
            return state
    return ""


def _walk_fields(nodes, parent_name: str, inherited: dict, seen: set):
    """Yield (qualified name, inherited attributes, field dict, widgets) per terminal field."""
    for ref in nodes or []:
        key = _ref_id(ref)
        if key is not None:
            if key in seen:  # a malformed PDF can loop
                continue
            seen.add(key)
        node = ref.get_object()
        if not hasattr(node, "get"):
            continue
        part = _text(node.get("/T"))
        name = f"{parent_name}.{part}" if parent_name and part else (part or parent_name)
        attrs = dict(inherited)
        for k in ("/FT", "/Ff", "/V", "/Opt", "/TU"):
            if k in node:
                attrs[k] = node[k]
        kids = node.get("/Kids")
        kids = kids.get_object() if kids is not None else []
        field_kids = [k for k in kids if "/T" in k.get_object()]
        if field_kids:
            yield from _walk_fields(field_kids, name, attrs, seen)
        else:
            widgets = [k.get_object() for k in kids] if kids else [node]
            widget_refs = list(kids) if kids else [ref]
            yield name, attrs, node, widgets, widget_refs


def _describe(attrs: dict, widgets) -> tuple[str, str, bool, str, str] | None:
    """(type, value shown, filled in, choices offered, raw value). None = not a data field."""
    ftype = _text(attrs.get("/FT"))
    flags = int(attrs.get("/Ff", 0) or 0)
    raw_obj = attrs.get("/V")
    raw = _text(raw_obj)

    if ftype == "Tx":
        return "Text box", raw, bool(raw.strip()), "", raw

    if ftype == "Btn":
        if flags & FF_PUSHBUTTON:
            return None  # a plain button carries no answer
        states = _widget_states(widgets)
        current = _current_state(raw, widgets)
        opt = _options(attrs.get("/Opt"))
        if flags & FF_RADIO:
            shown = current
            # Some radio groups store an index ("0", "1") and keep the wording in /Opt.
            if opt and current.isdigit() and int(current) < len(opt):
                shown = opt[int(current)][1]
            choices = [o[1] for o in opt] if opt else states
            return (
                "Radio buttons (choose one)",
                shown if current else "Nothing selected",
                bool(current),
                "; ".join(choices),
                current,
            )
        checked = bool(current)
        return (
            "Checkbox",
            "Checked" if checked else "Not checked",
            checked,
            "",
            current or "Off",
        )

    if ftype == "Ch":
        opt = _options(attrs.get("/Opt"))
        shown_for = {export: shown for export, shown in opt}
        if isinstance(raw_obj, (list, ArrayObject)):
            picked = [_text(v) for v in raw_obj]
        else:
            picked = [raw] if raw else []
        shown = "; ".join(shown_for.get(p, p) for p in picked)
        if flags & FF_COMBO:
            kind = "Dropdown"
        elif flags & FF_MULTISELECT:
            kind = "List (choose several)"
        else:
            kind = "List (choose one)"
        return kind, shown, bool(picked), "; ".join(o[1] for o in opt), "; ".join(picked)

    if ftype == "Sig":
        signed = raw_obj is not None
        # The signature's contents are never copied out; only whether it is there.
        return "Signature", "Signed" if signed else "Not signed", signed, "", ""

    return "Other (" + (ftype or "unknown") + ")", raw, bool(raw.strip()), "", raw


def read_pdf(data: bytes) -> PdfResult:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except Exception as exc:  # damaged or not really a PDF
        return PdfResult(RESULT_UNREADABLE, f"Not a readable PDF ({type(exc).__name__})")

    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                return PdfResult(RESULT_PASSWORD)
        except Exception:
            return PdfResult(RESULT_PASSWORD)

    try:
        root = reader.trailer["/Root"].get_object()
        acroform = root.get("/AcroForm")
        acroform = acroform.get_object() if acroform is not None else None
        notes = []
        if acroform is not None and "/XFA" in acroform:
            notes.append(
                "XFA (Adobe LiveCycle) form: only the parts stored as ordinary "
                "fields could be read. Check this file by hand."
            )
        top = acroform.get("/Fields") if acroform is not None else None
        top = top.get_object() if top is not None else []
        if not top:
            return PdfResult(
                RESULT_NO_FORM,
                "No fillable fields. It may be a scan, a printed-and-saved form, "
                "or a form that was flattened. Needs the text or OCR reader instead.",
            )

        # Which page each field's box sits on.
        page_of: dict = {}
        for number, page in enumerate(reader.pages, start=1):
            annots = page.get("/Annots")
            annots = annots.get_object() if annots is not None else []
            for a in annots or []:
                key = _ref_id(a)
                if key is not None:
                    page_of.setdefault(key, number)

        rows = []
        for name, attrs, node, widgets, widget_refs in _walk_fields(top, "", {}, set()):
            described = _describe(attrs, widgets)
            if described is None:
                continue
            kind, shown, filled, choices, raw = described
            pages = sorted({page_of[k] for k in map(_ref_id, widget_refs) if k in page_of})
            flags = int(attrs.get("/Ff", 0) or 0)
            rows.append(
                FieldRow(
                    name=name or "(unnamed field)",
                    label=_text(attrs.get("/TU")),
                    kind=kind,
                    value=shown,
                    filled=filled,
                    choices=choices,
                    raw=raw,
                    pages=", ".join(str(p) for p in pages),
                    read_only=bool(flags & FF_READ_ONLY),
                    required=bool(flags & FF_REQUIRED),
                )
            )
        if not rows:
            return PdfResult(RESULT_NO_FORM, "The form has only buttons, no answer fields.")
        return PdfResult(RESULT_READ, " ".join(notes), rows)
    except Exception as exc:
        return PdfResult(RESULT_UNREADABLE, f"Form could not be read ({type(exc).__name__})")


# --------------------------------------------------------------------------
# Walking the folders
# --------------------------------------------------------------------------

def _safe_cell(value) -> str:
    """Stop Excel treating a typed answer like '=SUM(...)' as a formula."""
    text = "" if value is None else str(value)
    if text and (text[0] in "=+@\t\r" or (text[0] == "-" and not _is_number(text))):
        return "'" + text
    return text


def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", ""))
        return True
    except ValueError:
        return False


def _long_path(path: Path) -> str:
    """Windows refuses paths over 260 characters unless they are marked as long."""
    text = str(path)
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        text = "\\\\?\\" + os.path.abspath(text)
    return text


class Report:
    def __init__(self, out_dir: Path, start: str, root_name: str = ""):
        self.out_dir = out_dir
        self.start = start
        self.root_name = root_name
        out_dir.mkdir(parents=True, exist_ok=False)
        self._fields_fh = open(out_dir / "fields.csv", "w", newline="", encoding="utf-8-sig")
        self._files_fh = open(out_dir / "files.csv", "w", newline="", encoding="utf-8-sig")
        self.fields = csv.writer(self._fields_fh)
        self.files = csv.writer(self._files_fh)
        self.fields.writerow(FIELD_COLUMNS)
        self.files.writerow(FILE_COLUMNS)
        self.counts = {"pdfs": 0, "with_fields": 0, "fields": 0, "problems": 0}

    def where(self, parts: list[str]) -> tuple[str, str]:
        """Month and job folder from a path relative to the starting folder."""
        folders = parts[:-1]
        if self.start == "year":
            return (folders[0] if folders else "", folders[1] if len(folders) > 1 else "")
        if self.start == "month":
            return (self.root_name, folders[0] if folders else "")
        return ("", self.root_name)

    def add(self, parts: list[str], shown_path: str, result: PdfResult):
        month, job = self.where(parts)
        filled = sum(1 for r in result.fields if r.filled)
        self.counts["pdfs"] += 1
        if result.result == RESULT_READ:
            self.counts["with_fields"] += 1
            self.counts["fields"] += len(result.fields)
        elif result.result != RESULT_NO_FORM:
            self.counts["problems"] += 1
        self.files.writerow(
            [_safe_cell(v) for v in (month, job, shown_path, result.result,
                                     len(result.fields), filled, result.note)]
        )
        for r in result.fields:
            self.fields.writerow(
                [
                    _safe_cell(v)
                    for v in (
                        month, job, shown_path, r.pages, r.name, r.label, r.kind,
                        r.value, "Yes" if r.filled else "No", r.choices, r.raw,
                        "Yes" if r.read_only else "", "Yes" if r.required else "",
                    )
                ]
            )

    def skip(self, parts: list[str], shown_path: str, reason: str):
        month, job = self.where(parts)
        self.counts["problems"] += 1
        self.files.writerow([_safe_cell(v) for v in (month, job, shown_path, RESULT_SKIPPED, 0, 0, reason)])

    def close(self):
        self._fields_fh.close()
        self._files_fh.close()


def _read_zip(data: bytes, parts: list[str], shown: str, report: Report, depth: int):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        report.skip(parts, shown, "Zip file could not be opened")
        return
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            inner_name = info.filename.replace("\\", "/")
            inner_shown = f"{shown} > {inner_name}"
            lower = inner_name.lower()
            if not (lower.endswith(".pdf") or lower.endswith(".zip")):
                continue
            if info.flag_bits & 0x1:
                report.skip(parts, inner_shown, "Password-protected zip - not read")
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                report.skip(parts, inner_shown, "Too large to read safely inside a zip")
                continue
            if lower.endswith(".zip") and depth >= MAX_ZIP_DEPTH:
                report.skip(parts, inner_shown, "Zip nested too deeply - open it by hand")
                continue
            try:
                inner = archive.read(info)
            except Exception as exc:
                report.skip(parts, inner_shown, f"Could not be read from the zip ({type(exc).__name__})")
                continue
            if lower.endswith(".zip"):
                _read_zip(inner, parts, inner_shown, report, depth + 1)
            else:
                report.add(parts, inner_shown, read_pdf(inner))


def scan(root: Path, report: Report, quiet: bool = False):
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            lower = name.lower()
            if not (lower.endswith(".pdf") or lower.endswith(".zip")):
                continue
            path = Path(dirpath) / name
            parts = list(path.relative_to(root).parts)
            shown = "/".join(parts)
            try:
                with open(_long_path(path), "rb") as fh:
                    data = fh.read()
            except Exception as exc:
                report.skip(parts, shown, f"Could not be opened ({type(exc).__name__})")
                continue
            if lower.endswith(".zip"):
                _read_zip(data, parts, shown, report, depth=1)
            else:
                report.add(parts, shown, read_pdf(data))
            seen += 1
            if not quiet and seen % 50 == 0:
                print(f"  ...{seen} files checked")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="List every fillable field in every PDF under a folder. Nothing leaves this computer."
    )
    parser.add_argument("folder", help='The folder to read, e.g. "D:\\Jobs\\2026"')
    parser.add_argument(
        "--out",
        help="Where to put the results (a new folder). Default: a dated folder in your Documents.",
    )
    parser.add_argument(
        "--start",
        choices=["year", "month", "job"],
        default="year",
        help="What the folder you give is: the year folder (default), one month, or one job.",
    )
    parser.add_argument("--quiet", action="store_true", help="Do not print progress.")
    args = parser.parse_args(argv)

    root = Path(args.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"That folder was not found: {root}")
        return 2

    if args.out:
        out_dir = Path(args.out).expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        out_dir = Path.home() / "Documents" / f"pdf-form-results-{stamp}"

    # Never write results into the folder being read: that is the shared job data.
    if out_dir == root or root in out_dir.parents:
        print("Please choose a results folder OUTSIDE the folder being read.")
        return 2
    if out_dir.exists():
        print(f"That results folder already exists, so nothing was overwritten: {out_dir}")
        return 2

    synced = [m for m in CLOUD_SYNC_MARKERS if m.lower() in str(out_dir).lower()]
    if synced:
        print(
            f"Stopped: the results folder looks like it syncs to the cloud ({synced[0]}),\n"
            "so the results would be copied there. Nothing was read or written.\n"
            'Run again with a local folder that is not synced, e.g. --out "C:\\Local\\form-results".'
        )
        return 2

    report = Report(out_dir, args.start, root.name)
    if not args.quiet:
        print(f"Reading PDFs under {root}")
    try:
        scan(root, report, quiet=args.quiet)
    finally:
        report.close()

    c = report.counts
    if not args.quiet:
        print()
        print(f"PDFs checked:              {c['pdfs']}")
        print(f"PDFs with form fields:     {c['with_fields']}")
        print(f"Form fields listed:        {c['fields']}")
        print(f"Files needing a look:      {c['problems']}  (see files.csv)")
        print()
        print(f"Results: {out_dir}")
        print("They contain real client data. Keep them on this computer and delete them when done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
