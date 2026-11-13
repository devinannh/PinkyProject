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

What to read is set in reader-settings.txt, next to this file: the folder,
where to look inside each job folder, whether to open zip files, and which
file names to look for (partial or complete match). See README.md.

  python pdf_form_reader.py                       uses reader-settings.txt
  python pdf_form_reader.py --settings other.txt  uses another settings file
  python pdf_form_reader.py "D:\\Jobs\\2026" --name worksheet --match partial

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
    print(
        "The PDF library is not installed yet.\n"
        "Run this once, then try again:\n"
        "  Windows:  py -m pip install -r requirements.txt\n"
        "  Mac:      python3 -m pip install -r requirements.txt"
    )
    if len(sys.argv) == 1:  # double-clicked: keep the window open to read this
        input("\nPress Enter to close this window.")
    sys.exit(1)

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
    "Matched name",
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
        self.counts = {
            "pdfs": 0, "with_fields": 0, "fields": 0, "problems": 0,
            "name_skipped": 0, "place_skipped": 0, "zips_not_opened": 0,
        }

    def where(self, parts: list[str]) -> tuple[str, str]:
        """Month and job folder from a path relative to the starting folder."""
        folders = parts[:-1]
        if self.start == "year":
            return (folders[0] if folders else "", folders[1] if len(folders) > 1 else "")
        if self.start == "month":
            return (self.root_name, folders[0] if folders else "")
        return ("", self.root_name)

    def add(self, parts: list[str], shown_path: str, result: PdfResult, matched: str = ""):
        month, job = self.where(parts)
        filled = sum(1 for r in result.fields if r.filled)
        self.counts["pdfs"] += 1
        if result.result == RESULT_READ:
            self.counts["with_fields"] += 1
            self.counts["fields"] += len(result.fields)
        elif result.result != RESULT_NO_FORM:
            self.counts["problems"] += 1
        self.files.writerow(
            [_safe_cell(v) for v in (month, job, shown_path, matched, result.result,
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
        self.files.writerow([_safe_cell(v) for v in (month, job, shown_path, "", RESULT_SKIPPED, 0, 0, reason)])

    def close(self):
        self._fields_fh.close()
        self._files_fh.close()


# --------------------------------------------------------------------------
# What to read: settings
# --------------------------------------------------------------------------

DEFAULT_SETTINGS_FILE = Path(__file__).resolve().parent / "reader-settings.txt"

# How deep the job folder sits below the folder being read.
JOB_DEPTH = {"year": 2, "month": 1, "job": 0}


class SettingsError(Exception):
    """A problem in the settings, worded for the person who wrote them."""


@dataclass
class Settings:
    folder: str = ""
    start: str = "year"          # year | month | job
    look_in: str = "main"        # main = the job folder itself; all = and its subfolders
    zips: bool = False
    names: list[str] = field(default_factory=list)
    match: str = "partial"       # partial | complete
    out: str = ""

    def describe(self) -> str:
        names = "\n".join(f"  - {n}" for n in self.names) or "  (every PDF)"
        return (
            f"Folder to read: {self.folder}\n"
            f"Folder is: {self.start}\n"
            f"Look in: {'main job folder' if self.look_in == 'main' else 'all subfolders'}\n"
            f"Include zip files: {'yes' if self.zips else 'no'}\n"
            f"File names:\n{names}\n"
            f"Match: {self.match}\n"
        )


_CHOICES = {
    "folder is": ("start", {"year": "year", "month": "month", "job": "job"}),
    "look in": ("look_in", {
        "main job folder": "main", "main job folder only": "main", "main": "main",
        "job folder": "main", "job folder only": "main",
        "all subfolders": "all", "subfolders": "all", "all": "all",
        "job folder and subfolders": "all",
    }),
    "include zip files": ("zips", {"yes": True, "y": True, "no": False, "n": False}),
    "match": ("match", {"partial": "partial", "complete": "complete", "exact": "complete", "full": "complete"}),
}


def _choice(key: str, value: str, where: str):
    attr, allowed = _CHOICES[key]
    picked = allowed.get(" ".join(value.lower().split()))
    if picked is None:
        options = sorted({k for k, v in allowed.items() if k in _PRIMARY_WORDS})
        raise SettingsError(f'{where}: "{value}" is not one of: {", ".join(options)}.')
    return attr, picked


_PRIMARY_WORDS = {"year", "month", "job", "main job folder", "all subfolders", "yes", "no", "partial", "complete"}


def load_settings(path: Path) -> Settings:
    """Read a settings file like reader-settings.txt."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        raise SettingsError(f"The settings file was not found: {path}")
    settings = Settings()
    in_names = False
    for number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        where = f"Settings line {number}"
        if text.startswith("-"):
            if not in_names:
                raise SettingsError(f'{where}: a list item ("- ...") must sit under "File names:".')
            name = text[1:].strip().strip('"').strip()
            if name:
                settings.names.append(name)
            continue
        if ":" not in text:
            raise SettingsError(f'{where}: expected "Setting: value", found "{text}".')
        key, value = text.split(":", 1)
        key = " ".join(key.lower().split())
        value = value.strip().strip('"').strip()
        in_names = key == "file names"
        if key == "folder to read":
            settings.folder = value
        elif key == "results folder":
            settings.out = value
        elif key == "file names":
            if value:  # names written on the same line, separated by semicolons
                settings.names.extend(n.strip() for n in value.split(";") if n.strip())
        elif key in _CHOICES:
            attr, picked = _choice(key, value, where)
            setattr(settings, attr, picked)
        else:
            raise SettingsError(f'{where}: "{key}" is not a setting this reader knows.')
    return settings


def _normal(name: str) -> str:
    """A file name for comparing: no .pdf ending, capitals and extra spaces ignored."""
    name = " ".join(name.split()).casefold()
    return name[:-4].rstrip() if name.endswith(".pdf") else name


def name_matches(filename: str, settings: Settings) -> str | None:
    """Which wanted name this PDF's file name matches ('' when every PDF is wanted)."""
    if not settings.names:
        return ""
    stem = _normal(filename)
    for wanted in settings.names:
        target = _normal(wanted)
        if not target:
            continue
        if (settings.match == "complete" and stem == target) or (
            settings.match == "partial" and target in stem
        ):
            return wanted
    return None


# --------------------------------------------------------------------------
# Walking the folders
# --------------------------------------------------------------------------

def _read_zip(data: bytes, parts: list[str], shown: str, report: Report, settings: Settings, depth: int):
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
            is_zip = lower.endswith(".zip")
            if not (lower.endswith(".pdf") or is_zip):
                continue
            matched = None if is_zip else name_matches(inner_name.rsplit("/", 1)[-1], settings)
            if not is_zip and matched is None:
                report.counts["name_skipped"] += 1
                continue
            if info.flag_bits & 0x1:
                report.skip(parts, inner_shown, "Password-protected zip - not read")
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                report.skip(parts, inner_shown, "Too large to read safely inside a zip")
                continue
            if is_zip and depth >= MAX_ZIP_DEPTH:
                report.skip(parts, inner_shown, "Zip nested too deeply - open it by hand")
                continue
            try:
                inner = archive.read(info)
            except Exception as exc:
                report.skip(parts, inner_shown, f"Could not be read from the zip ({type(exc).__name__})")
                continue
            if is_zip:
                _read_zip(inner, parts, inner_shown, report, settings, depth + 1)
            else:
                report.add(parts, inner_shown, read_pdf(inner), matched or "")


def scan(root: Path, report: Report, settings: Settings, quiet: bool = False):
    """Read the PDFs the settings ask for. Folders below a job folder are not
    even opened when only the main job folder is wanted."""
    job_depth = JOB_DEPTH[settings.start]
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        depth = len(here.relative_to(root).parts)
        dirnames.sort()
        if settings.look_in == "main" and depth >= job_depth:
            dirnames[:] = []  # do not go below the job folder
        for name in sorted(filenames):
            lower = name.lower()
            is_zip = lower.endswith(".zip")
            if not (lower.endswith(".pdf") or is_zip):
                continue
            path = here / name
            parts = list(path.relative_to(root).parts)
            shown = "/".join(parts)
            in_place = depth == job_depth if settings.look_in == "main" else depth >= job_depth
            if not in_place:
                if not is_zip:
                    report.counts["place_skipped"] += 1
                continue
            if is_zip:
                if not settings.zips:
                    report.counts["zips_not_opened"] += 1
                    continue
                matched = None
            else:
                matched = name_matches(name, settings)
                if matched is None:
                    report.counts["name_skipped"] += 1
                    continue
            try:
                with open(_long_path(path), "rb") as fh:
                    data = fh.read()
            except Exception as exc:
                report.skip(parts, shown, f"Could not be opened ({type(exc).__name__})")
                continue
            if is_zip:
                _read_zip(data, parts, shown, report, settings, depth=1)
            else:
                report.add(parts, shown, read_pdf(data), matched)
            seen += 1
            if not quiet and seen % 50 == 0:
                print(f"  ...{seen} files read")


def build_settings(args) -> Settings:
    """Settings file first (if any), then anything typed on the command line."""
    if args.settings:
        settings = load_settings(Path(args.settings).expanduser())
    elif not args.folder:
        settings = load_settings(DEFAULT_SETTINGS_FILE)
    else:
        settings = Settings()
    if args.folder:
        settings.folder = args.folder
    if args.start:
        settings.start = args.start
    if args.look_in:
        settings.look_in = args.look_in
    if args.zips:
        settings.zips = args.zips == "yes"
    if args.name:
        settings.names = list(args.name)
    if args.match:
        settings.match = args.match
    if args.out:
        settings.out = args.out
    if not settings.folder:
        raise SettingsError('No folder to read. Fill in "Folder to read:" in the settings file.')
    return settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="List every fillable field in the chosen PDFs. Nothing leaves this computer."
    )
    parser.add_argument("folder", nargs="?", help='The folder to read, e.g. "D:\\Jobs\\2026"')
    parser.add_argument("--settings", help="A settings file to use instead of reader-settings.txt.")
    parser.add_argument("--start", choices=["year", "month", "job"],
                        help="What the folder is: the year folder, one month, or one job.")
    parser.add_argument("--look-in", choices=["main", "all"],
                        help="main = only files directly in each job folder; all = and its subfolders.")
    parser.add_argument("--zips", choices=["yes", "no"], help="Read PDFs inside zip files.")
    parser.add_argument("--name", action="append",
                        help="A file name to look for. Repeat for several.")
    parser.add_argument("--match", choices=["partial", "complete"],
                        help="partial = the file name contains it; complete = the file name is exactly it.")
    parser.add_argument("--out", help="Where to put the results (a new folder).")
    parser.add_argument("--quiet", action="store_true", help="Do not print progress.")
    args = parser.parse_args(argv)

    try:
        settings = build_settings(args)
    except SettingsError as exc:
        print(exc)
        return 2

    root = Path(settings.folder).expanduser().resolve()
    if not root.is_dir():
        print(f"That folder was not found: {root}")
        return 2

    if settings.out:
        out_dir = Path(settings.out).expanduser().resolve()
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
            'Set "Results folder:" to a local folder that is not synced, e.g. C:\\Local\\form-results.'
        )
        return 2

    report = Report(out_dir, settings.start, root.name)
    # A record of what produced these results, kept beside them.
    (out_dir / "settings-used.txt").write_text(settings.describe(), encoding="utf-8")
    if not args.quiet:
        print(f"Reading PDFs under {root}")
        print(settings.describe())
    try:
        scan(root, report, settings, quiet=args.quiet)
    finally:
        report.close()

    c = report.counts
    if not args.quiet:
        print()
        print(f"PDFs read:                       {c['pdfs']}")
        print(f"  with form fields:              {c['with_fields']}")
        print(f"  form fields listed:            {c['fields']}")
        print(f"  needing a look:                {c['problems']}  (see files.csv)")
        print(f"PDFs passed over, name did not match:      {c['name_skipped']}")
        print(f"PDFs passed over, outside any job folder:  {c['place_skipped']}")
        if settings.look_in == "main":
            print("Subfolders inside job folders were not opened (Look in: main job folder).")
        if c["zips_not_opened"]:
            print(f"Zip files not opened (zips are set to no): {c['zips_not_opened']}")
        print()
        print(f"Results: {out_dir}")
        print("They contain real client data. Keep them on this computer and delete them when done.")
    return 0


if __name__ == "__main__":
    double_clicked = len(sys.argv) == 1
    try:
        code = main()
    except Exception as exc:  # keep the window open long enough to read what went wrong
        print(f"Something went wrong: {type(exc).__name__}: {exc}")
        code = 1
    if double_clicked:
        input("\nPress Enter to close this window.")
    sys.exit(code)
