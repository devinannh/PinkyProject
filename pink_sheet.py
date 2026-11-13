"""
Pink Sheet mode: the Production department's job checklist, read into plain
columns.

DevinAnn marked the values she needs on a filled-in sheet (2026-11-13): the
Job Number, Original +, Notes, every witness listed with its R&S and "R&S Sent
To", Initial QC and Production (completed, and by whom), the five YES/NO flags,
the Originals and Copies choices with their lines, quantities and media, and
the USB / CD box; and from page 2, only "Final QC Completed By" ("let's just
start with 1 value"). Not wanted: the checklist ticks and "Verify order
details". Billing is out of scope for now (DevinAnn, 2026-11-13). Page 2's
Job Number is not output; it is only checked against page 1.

Output is ONE ROW PER JOB (one per sheet), with each witness listed at the
top in its own set of columns: Witness A, Witness A R&S, Witness A R&S Sent
To, then B ... F, in the order the rows appear on the form (DevinAnn,
2026-11-13: "one row per job, with columns like Witness A, Witness A R&S,
Witness A R&S Sent To"; "If multiple witnesses are listed at the top, all
must be included").

The field names come from the three revisions of the form (docs/pink-sheet-
field-map.md). They are the same in all three for everything read here,
except "Dropdown9", which is Depo Summary on the 2023 and May 2025 sheets and
Picture-in-Picture on the October 2025 sheet. So the sheet's revision is read
from the "Revised ..." date printed on page 1, and an unknown revision is
reported rather than guessed.
"""

from __future__ import annotations

import re

# The revisions, by the date printed at the bottom of page 1.
VERSIONS = {
    "December 8, 2023": "Dec 2023",
    "May 2, 2025": "May 2025",
    "October 13, 2025": "Oct 2025",
}

_REVISED = re.compile(r"Revised\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})")

# The witness rows at the top of page 1, top to bottom.
WITNESS_NAME = ["Text12", "Text11", "Text10", "Text9", "Text8", "Text7"]
WITNESS_RS = ["R&S.0", "R&S.1", "R&S.2", "R&S.3", "R&S.4", "R&S.5"]
WITNESS_RS_SENT_TO = ["E-Mail", "Text15.0", "Text15.1", "Text15.2", "Text15.3", "Text15.4"]

# (column, field). Checkboxes come out as Yes / No.
SHEET_COLUMNS = [
    ("Original +", "Text3"),
    ("Notes", ("Text4", "Text6")),
    ("Initial QC completed", "Check Box18.0.0"),
    ("Initial QC by", "Dropdown17.0"),
    ("30(b)(6)", "Dropdown7"),
    ("Videotaped", "Dropdown8"),
    ("Interpreter", "Dropdown1.1"),
    ("Cross-Depo", "Dropdown1.2"),
    ("Picture-in-Picture", None),        # Dropdown9 on the Oct 2025 sheet
    ("Depo Summary (Dec 2023 / May 2025 sheets)", None),  # Dropdown9 on the older sheets
    ("Production completed", "Check Box19.0"),
    ("Printed by", "Dropdown4"),          # "Production completed by" on the form (DevinAnn, 2026-11-13)
    ("Original: Printed w/ Full-Mini-Word Printed Copy (Standard Package)", "Check Box19.1.0"),
    ("  line", "Text21.0"),
    ("Original: Printed w/ Electronic Copy", "Check Box19.1.1.0"),
    ("  line", "Text21.1.0"),
    ("  media", "Dropdown20.0"),
    ("Original: Printed w/ Printed Full-Size Copy", "Check Box19.1.1.1.0"),
    ("  line", "Text21.1.1.0"),
    ("Original: Printed w/ Printed Mini-Size Copy", "Check Box19.1.1.1.1.0"),
    ("  line", "Text21.1.1.1"),
    ("Original: No Printed Original w/ Electronic Copy", "Check Box19.1.1.1.1.1.0"),
    ("  line", "Text21.1.1.2"),
    ("  media", "Dropdown20.1"),
    ("Copies: Full-Mini-Word Printed", "Check Box19.1.1.1.1.1.1"),
    ("  quantity", "Text22.0"),
    ("Copies: Printed Full-Size Only", "Check Box19.1.1.1.1.1.2"),
    ("  quantity", "Text22.1"),
    ("Copies: Printed Mini-Size Only", "Check Box19.1.1.1.1.1.3"),
    ("  quantity", "Text22.2.0"),
    ("Copies: Electronic Only", "Check Box19.1.1.1.1.1.4"),
    ("  quantity", "Text22.2.1"),
    ("  media", "Dropdown11"),           # not on the 2023 sheet
    ("Copies: E-Mail Only", "Check Box19.1.1.1.1.1.5.0"),
    ("  quantity", "Text22.2.2"),
    ("USB", "Check Box25"),         # "Disc/CD" / "CD/USB" on the older sheets
    ("USB Qty", "Text26"),
    # Page 2: one value only, for now (DevinAnn, 2026-11-13).
    ("Final QC by", "Dropdown6"),
]


def _column_names() -> list[str]:
    """Sub-columns ("  line", "  media", "  quantity") take the name of the
    choice above them, so every column can be read on its own."""
    names, parent = [], ""
    for col, _ in SHEET_COLUMNS:
        if col.startswith("  "):
            names.append(f"{parent} - {col.strip()}")
        else:
            parent = col
            names.append(col)
    return names


WITNESS_LETTERS = "ABCDEF"

WITNESS_COLUMNS = [
    col
    for letter in WITNESS_LETTERS
    for col in (f"Witness {letter}", f"Witness {letter} R&S", f"Witness {letter} R&S Sent To")
]

COLUMNS = [
    "Year", "Month", "Job folder", "File", "Form version",
    "Job Number",
    *WITNESS_COLUMNS,
    *_column_names(),
    "Needs a look",
]

# What makes a PDF a Pink Sheet: these fields, which every revision has.
_SIGNATURE = {"Job Number", "Text12", "R&S.0", "Dropdown17.0", "Check Box19.1.0"}


def version_of(page_one_text: str) -> tuple[str, str]:
    """(version, the printed date) from page 1's text; version '' when unknown."""
    m = _REVISED.search(page_one_text or "")
    if not m:
        return "", ""
    printed = " ".join(m.group(1).split())
    return VERSIONS.get(printed, ""), printed


def is_pink_sheet(fields: dict) -> bool:
    return _SIGNATURE <= set(fields)


def _value(fields: dict, name) -> str:
    if isinstance(name, tuple):
        return " ".join(v for v in (_value(fields, n) for n in name) if v)
    f = fields.get(name)
    if f is None:
        return ""
    if f.kind == "Checkbox":
        return "Yes" if f.filled else "No"
    return f.value.strip() if f.filled else ""


def row(fields: dict, page_one_text: str, page_two_job_number: str | None = None) -> dict:
    """The sheet's one row, keyed by COLUMNS minus the place columns.
    `fields` maps field name -> FieldRow."""
    version, printed = version_of(page_one_text)
    problems = []
    if not version:
        problems.append(
            f'Unrecognised form revision ("Revised {printed}")' if printed
            else "No \"Revised ...\" date found on page 1"
        )

    job = _value(fields, "Job Number")
    if not job:
        problems.append("No Job Number")
    # A blank page 2 Job Number is not a mismatch (DevinAnn, 2026-11-13):
    # only two filled-in numbers that differ are flagged.
    p2 = _value(fields, "Text28") if page_two_job_number is None else page_two_job_number
    if p2 and job and "".join(p2.split()) != "".join(job.split()):
        problems.append(f"Page 2 Job Number differs ({p2})")

    sheet = {}
    names = _column_names()
    for (col, field), name in zip(SHEET_COLUMNS, names):
        sheet[name] = _value(fields, field) if field else ""
    dd9 = _value(fields, "Dropdown9")
    if version == "Oct 2025":
        sheet["Picture-in-Picture"] = dd9
    elif version in ("Dec 2023", "May 2025"):
        sheet["Depo Summary (Dec 2023 / May 2025 sheets)"] = dd9
    elif dd9:
        problems.append(f"Dropdown9 is {dd9}, but its meaning depends on the revision")

    row = {
        "Form version": version or (f"Unknown (Revised {printed})" if printed else "Unknown"),
        "Job Number": job,
    }
    listed = 0
    for i, letter in enumerate(WITNESS_LETTERS):
        name = _value(fields, WITNESS_NAME[i])
        rs = _value(fields, WITNESS_RS[i])
        sent = _value(fields, WITNESS_RS_SENT_TO[i])
        if name:
            listed += 1
        elif rs or sent:
            problems.append(f"Witness row {letter} has R&S details but no witness name")
        row[f"Witness {letter}"] = name
        row[f"Witness {letter} R&S"] = rs
        row[f"Witness {letter} R&S Sent To"] = sent
    if not listed:
        problems.append("No witness listed")
    row.update(sheet)
    row["Needs a look"] = "; ".join(problems)
    row["_witnesses"] = listed      # for the count; not a column
    return row


_NOT_COUNTED = {"Year", "Month", "Job folder", "File", "Form version", "Needs a look"}


def filled_count(row: dict) -> int:
    """How filled in a sheet is: the values that hold an answer. A box left
    unticked ("No") and a dropdown left on the form's own default ("N/A") do
    not count."""
    return sum(
        1 for col, value in row.items()
        if col not in _NOT_COUNTED and not col.startswith("_")
        and str(value).strip() not in ("", "No", "N/A")
    )
