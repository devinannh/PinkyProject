"""
Tests for pdf_form_reader.py, run against MADE-UP forms built here.

No real job files are used or stored. To run:

    python -m pip install -r requirements-dev.txt
    python -m unittest discover -s tests -v
"""

import csv
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pdf_form_reader as reader  # noqa: E402


def place(row) -> str:
    """Where a result row's file is: month / job folder / file name. The File
    column holds the file's name only (DevinAnn, 2026-11-13)."""
    return f'{row["Month"]}/{row["Job folder"]}/{row["File"]}'


def fillable_form(filled: bool) -> bytes:
    """A two-page form with every field type the job forms use."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    form = c.acroForm
    c.drawString(50, 800, "Sample job worksheet (made up)")
    form.textfield(name="witness_name", tooltip="Witness name", x=50, y=740, width=250, height=20,
                   value="Jane Q. Sample" if filled else "")
    form.textfield(name="notes", x=50, y=700, width=250, height=20,
                   value="=HYPERLINK(\"x\")" if filled else "")
    form.checkbox(name="rush", x=50, y=660, size=14, checked=filled, buttonStyle="check")
    form.checkbox(name="video", x=80, y=660, size=14, checked=False)
    for i, opt in enumerate(["In person", "Remote", "Hybrid"]):
        form.radio(name="attendance", value=opt.replace(" ", "_"), x=50 + 60 * i, y=620, size=14,
                   selected=(filled and opt == "Remote"), buttonStyle="circle")
    # reportlab cannot draw an EMPTY dropdown or list, so both are drawn with
    # an answer and the answer is removed afterwards for the empty form.
    form.choice(name="turnaround", x=50, y=580, width=150, height=20,
                options=["Standard", "Expedited", "Daily"], value="Expedited",
                fieldFlags="combo")
    form.listbox(name="copies", x=50, y=500, width=150, height=60,
                 options=["Original", "Certified copy", "Rough"], value="Rough")
    c.showPage()
    c.drawString(50, 800, "Page two")
    form.textfield(name="page_count", x=50, y=740, width=100, height=20, value="-12" if filled else "")
    c.showPage()
    c.save()
    return buf.getvalue() if filled else clear_answers(buf.getvalue(), {"turnaround", "copies"})


def clear_answers(data: bytes, names: set) -> bytes:
    w = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    for ref in w._root_object["/AcroForm"]["/Fields"]:
        f = ref.get_object()
        if f.get("/T") in names:
            for key in ("/V", "/I"):
                if key in f:
                    del f[key]
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def plain_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(50, 800, "A scanned-looking page with no fields")
    c.showPage()
    c.save()
    return buf.getvalue()


def locked(data: bytes) -> bytes:
    w = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    w.encrypt(user_password="secret", owner_password="owner")
    out = io.BytesIO()
    w.write(out)
    return out.getvalue()


def zipped(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


class ReadOnePdf(unittest.TestCase):
    def fields(self, data):
        result = reader.read_pdf(data)
        self.assertEqual(result.result, reader.RESULT_READ, result.note)
        return {f.name: f for f in result.fields}

    def test_every_field_type_when_filled(self):
        f = self.fields(fillable_form(filled=True))
        self.assertEqual(f["witness_name"].kind, "Text box")
        self.assertEqual(f["witness_name"].value, "Jane Q. Sample")
        self.assertEqual(f["witness_name"].label, "Witness name")
        self.assertTrue(f["witness_name"].filled)

        self.assertEqual(f["rush"].kind, "Checkbox")
        self.assertEqual(f["rush"].value, "Checked")
        self.assertEqual(f["video"].value, "Not checked")
        self.assertFalse(f["video"].filled)

        self.assertEqual(f["attendance"].kind, "Radio buttons (choose one)")
        self.assertEqual(f["attendance"].value, "Remote")
        self.assertEqual(f["attendance"].choices, "In_person; Remote; Hybrid")

        self.assertEqual(f["turnaround"].kind, "Dropdown")
        self.assertEqual(f["turnaround"].value, "Expedited")
        self.assertEqual(f["turnaround"].choices, "Standard; Expedited; Daily")

        self.assertTrue(f["copies"].kind.startswith("List"))
        self.assertEqual(f["copies"].value, "Rough")

    def test_empty_form_reads_as_not_filled(self):
        f = self.fields(fillable_form(filled=False))
        self.assertEqual(f["attendance"].value, "Nothing selected")
        self.assertEqual(f["turnaround"].value, "")
        self.assertFalse(any(x.filled for x in f.values()))

    def test_page_numbers(self):
        f = self.fields(fillable_form(filled=True))
        self.assertEqual(f["witness_name"].pages, "1")
        self.assertEqual(f["page_count"].pages, "2")
        self.assertEqual(f["attendance"].pages, "1")

    def test_pdf_without_fields(self):
        self.assertEqual(reader.read_pdf(plain_pdf()).result, reader.RESULT_NO_FORM)

    def test_password_protected(self):
        self.assertEqual(reader.read_pdf(locked(fillable_form(True))).result, reader.RESULT_PASSWORD)

    def test_not_a_pdf(self):
        self.assertEqual(reader.read_pdf(b"this is a text file").result, reader.RESULT_UNREADABLE)


class WholeFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "2026"
        job = self.root / "March" / "Job 140205"
        (job / "Exhibits" / "Deeper").mkdir(parents=True)
        (job / "worksheet.pdf").write_bytes(fillable_form(True))
        (job / "Exhibits" / "Deeper" / "scan.pdf").write_bytes(plain_pdf())
        (job / "transcript.txt").write_text("not a pdf, ignored")
        inner = zipped({"nested/form.pdf": fillable_form(False)})
        (job / "bundle.zip").write_bytes(
            zipped({"a/worksheet copy.PDF": fillable_form(True), "inner.zip": inner, "readme.txt": b"x"})
        )
        self.before = sorted((p.relative_to(base), p.stat().st_mtime) for p in base.rglob("*"))
        self.out = base / "results"

    def tearDown(self):
        self.tmp.cleanup()

    def run_reader(self, *extra):
        code = reader.main([str(self.root), "--out", str(self.out), "--quiet", *extra])
        self.assertEqual(code, 0)
        with open(self.out / "fields.csv", encoding="utf-8-sig") as fh:
            fields = list(csv.DictReader(fh))
        with open(self.out / "files.csv", encoding="utf-8-sig") as fh:
            files = list(csv.DictReader(fh))
        return fields, files

    def test_finds_pdfs_in_subfolders_and_zips(self):
        fields, files = self.run_reader("--look-in", "all", "--zips", "yes")
        names = sorted(place(f) for f in files)
        self.assertEqual(
            names,
            sorted([
                "March/Job 140205/worksheet.pdf",
                "March/Job 140205/scan.pdf",
                "March/Job 140205/worksheet copy.PDF (in bundle.zip)",
                "March/Job 140205/form.pdf (in inner.zip)",
            ]),
        )
        self.assertTrue(all(f["Month"] == "March" and f["Job folder"] == "Job 140205" for f in files))
        self.assertTrue(all(f["Year"] == "2026" for f in files))
        self.assertTrue(any(f["Field name"] == "rush" and f["Value"] == "Checked" for f in fields))

    def test_formulas_are_not_live_in_excel(self):
        fields, _ = self.run_reader()
        from openpyxl import load_workbook
        ws = load_workbook(self.out / "pinky-results.xlsx")["Fields"]
        cells = [c for row in ws.iter_rows(min_row=2) for c in row if str(c.value).startswith("=HYPERLINK")]
        self.assertTrue(cells)
        self.assertTrue(all(c.data_type == "s" for c in cells))  # text, not a live formula
        notes = [f["Value"] for f in fields if f["Field name"] == "notes" and f["Value"]]
        self.assertTrue(notes and all(v.startswith("'=") for v in notes))
        counts = [f["Value"] for f in fields if f["Field name"] == "page_count" and f["Value"]]
        self.assertIn("-12", counts)  # a negative number is left alone

    def test_source_folder_is_untouched(self):
        self.run_reader("--look-in", "all", "--zips", "yes")
        base = Path(self.tmp.name)
        after = sorted(
            (p.relative_to(base), p.stat().st_mtime) for p in base.rglob("*") if "results" not in p.parts
        )
        self.assertEqual(after, self.before)

    def test_refuses_to_write_inside_the_source(self):
        code = reader.main([str(self.root), "--out", str(self.root / "results"), "--quiet"])
        self.assertEqual(code, 2)
        self.assertFalse((self.root / "results").exists())

    def test_refuses_to_overwrite_earlier_results(self):
        self.run_reader()
        self.assertEqual(reader.main([str(self.root), "--out", str(self.out), "--quiet"]), 2)

    def test_refuses_a_cloud_synced_results_folder(self):
        target = Path(self.tmp.name) / "OneDrive - Gallo" / "results"
        self.assertEqual(reader.main([str(self.root), "--out", str(target), "--quiet"]), 2)
        self.assertFalse(target.exists())

    def test_starting_at_a_month_folder(self):
        code = reader.main([str(self.root / "March"), "--out", str(self.out), "--quiet", "--start", "month"])
        self.assertEqual(code, 0)
        with open(self.out / "files.csv", encoding="utf-8-sig") as fh:
            files = list(csv.DictReader(fh))
        self.assertTrue(all(f["Month"] == "March" and f["Job folder"] == "Job 140205" for f in files))
        self.assertTrue(all(f["Year"] == "2026" for f in files))


class ChoosingWhatToRead(unittest.TestCase):
    """File-name matching (partial / complete) and where to look."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "2026"
        job1 = self.root / "March" / "Job 140205"
        job2 = self.root / "April" / "Job 140300"
        (job1 / "Sub").mkdir(parents=True)
        job2.mkdir(parents=True)
        form = fillable_form(True)
        (job1 / "Smith Worksheet FINAL.pdf").write_bytes(form)
        (job1 / "worksheet.pdf").write_bytes(form)
        (job1 / "Notice.pdf").write_bytes(form)
        (job1 / "Sub" / "worksheet.pdf").write_bytes(form)
        (job1 / "bundle.zip").write_bytes(zipped({"docs/worksheet.pdf": form, "docs/other.pdf": form}))
        (job2 / "WORKSHEET.PDF").write_bytes(form)
        (self.root / "March" / "loose worksheet.pdf").write_bytes(form)
        self.out = self.base / "results"

    def tearDown(self):
        self.tmp.cleanup()

    def files_read(self, *args):
        code = reader.main([*args, "--out", str(self.out), "--quiet"])
        self.assertEqual(code, 0)
        with open(self.out / "files.csv", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.rows = rows
        return {place(r): r for r in rows}

    def test_default_is_main_job_folder_partial_no_zips(self):
        got = self.files_read(str(self.root), "--name", "worksheet")
        self.assertEqual(sorted(got), [
            "April/Job 140300/WORKSHEET.PDF",
            "March/Job 140205/Smith Worksheet FINAL.pdf",
            "March/Job 140205/worksheet.pdf",
        ])
        self.assertEqual({r["Matched name"] for r in got.values()}, {"worksheet"})

    def test_complete_match(self):
        got = self.files_read(str(self.root), "--name", "Worksheet.pdf", "--match", "complete")
        self.assertEqual(sorted(got), ["April/Job 140300/WORKSHEET.PDF", "March/Job 140205/worksheet.pdf"])

    def test_several_names(self):
        got = self.files_read(str(self.root), "--name", "notice", "--name", "worksheet", "--match", "complete")
        self.assertEqual(got["March/Job 140205/Notice.pdf"]["Matched name"], "notice")
        self.assertEqual(len(got), 3)

    def test_all_subfolders(self):
        got = self.files_read(str(self.root), "--name", "worksheet", "--match", "complete", "--look-in", "all")
        # the main folder's worksheet.pdf AND Sub/worksheet.pdf: the File
        # column names both "worksheet.pdf"
        self.assertEqual(sorted(place(r) for r in self.rows).count("March/Job 140205/worksheet.pdf"), 2)
        self.assertNotIn("March/loose worksheet.pdf", got)  # not inside a job folder

    def test_zips_yes_reads_only_matching_pdfs_inside(self):
        got = self.files_read(str(self.root), "--name", "worksheet", "--match", "complete", "--zips", "yes")
        self.assertIn("March/Job 140205/worksheet.pdf (in bundle.zip)", got)
        self.assertNotIn("March/Job 140205/other.pdf (in bundle.zip)", got)

    def test_no_names_reads_every_pdf_in_the_main_folders(self):
        got = self.files_read(str(self.root))
        self.assertEqual(len(got), 4)
        self.assertIn("March/Job 140205/Notice.pdf", got)

    def test_only_what_was_read_is_counted(self):
        settings = reader.Settings(folder=str(self.root), names=["worksheet"], match="complete")
        self.out.mkdir()
        rep = reader.Report(self.out / "r", "year", "2026")
        reader.scan(self.root, rep, settings, quiet=True)
        rep.close()
        self.assertEqual(rep.counts["pdfs"], 2)
        # Files passed over are not counted (owner's choice, to keep runs lean).
        self.assertFalse({"name_skipped", "place_skipped", "zips_not_opened"} & set(rep.counts))

    def write_settings(self, text):
        path = self.base / "my-settings.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_settings_file(self):
        path = self.write_settings(
            f"# a note\nFolder to read: {self.root}\nFolder is: year\nLook in: all subfolders\n"
            f"Include zip files: yes\nFile names:\n  - worksheet\n  - notice\nMatch: Complete\n"
            f"Results folder: {self.out}\n"
        )
        code = reader.main(["--settings", str(path), "--quiet"])
        self.assertEqual(code, 0)
        with open(self.out / "files.csv", encoding="utf-8-sig") as fh:
            got = sorted(place(r) for r in csv.DictReader(fh))
        self.assertEqual(got, sorted([
            "April/Job 140300/WORKSHEET.PDF",
            "March/Job 140205/worksheet.pdf",
            "March/Job 140205/Notice.pdf",
            "March/Job 140205/worksheet.pdf",          # Sub/worksheet.pdf
            "March/Job 140205/worksheet.pdf (in bundle.zip)",
        ]))
        used = (self.out / "settings-used.txt").read_text()
        self.assertIn("Match: complete", used)
        self.assertIn("  - notice", used)

    def test_names_on_one_line(self):
        path = self.write_settings(f"Folder to read: {self.root}\nFile names: notice; worksheet\nMatch: complete\n")
        self.assertEqual(reader.load_settings(path).names, ["notice", "worksheet"])

    def test_settings_mistakes_are_explained_and_nothing_runs(self):
        for text in (
            f"Folder to read: {self.root}\nMatch: sort of\n",
            f"Folder to read: {self.root}\nColour: blue\n",
            f"Folder to read: {self.root}\n  - worksheet\n",
            "Match: partial\n",
        ):
            path = self.write_settings(text)
            self.assertEqual(reader.main(["--settings", str(path), "--quiet", "--out", str(self.out)]), 2, text)
            self.assertFalse(self.out.exists())

    def test_the_shipped_settings_file_is_valid(self):
        s = reader.load_settings(Path(__file__).resolve().parent.parent / "reader-settings.txt")
        self.assertEqual((s.look_in, s.zips, s.match, s.start), ("main", False, "partial", "year"))
        self.assertEqual(s.names, ["worksheet"])


class OtherFileTypes(unittest.TestCase):
    """Optional extra file types: found and listed, never opened."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "2026"
        job = self.root / "March" / "Job 140205"
        job.mkdir(parents=True)
        (job / "Worksheet.pdf").write_bytes(fillable_form(True))
        (job / "Worksheet.docx").write_bytes(b"not really word")
        (job / "Worksheet.wpd").write_bytes(b"not really wordperfect")
        (job / "Notes.txt").write_text("x")
        (job / "bundle.zip").write_bytes(zipped({"Worksheet.DOCX": b"x", "other.pdf": fillable_form(True)}))
        self.out = base / "results"

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, *args):
        self.assertEqual(reader.main([str(self.root), "--out", str(self.out), "--quiet", *args]), 0)
        with open(self.out / "files.csv", encoding="utf-8-sig") as fh:
            return {place(r): r for r in csv.DictReader(fh)}

    def test_pdf_only_by_default(self):
        self.assertEqual(sorted(self.files("--name", "worksheet")), ["March/Job 140205/Worksheet.pdf"])

    def test_extra_types_are_listed_not_read(self):
        got = self.files("--name", "worksheet", "--type", "docx", "--type", ".WPD", "--zips", "yes")
        self.assertEqual(sorted(got), sorted([
            "March/Job 140205/Worksheet.docx",
            "March/Job 140205/Worksheet.pdf",
            "March/Job 140205/Worksheet.wpd",
            "March/Job 140205/Worksheet.DOCX (in bundle.zip)",
        ]))
        docx = got["March/Job 140205/Worksheet.docx"]
        self.assertEqual((docx["File type"], docx["Result"], docx["Fields"]), ("DOCX", reader.RESULT_FOUND, "0"))
        self.assertEqual(got["March/Job 140205/Worksheet.pdf"]["Result"], reader.RESULT_READ)

    def test_extra_types_are_never_opened(self):
        import builtins
        from unittest import mock
        opened = []
        real_open = builtins.open

        def spy(path, *a, **k):
            opened.append(str(path))
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", spy):
            self.files("--type", "docx", "--type", "wpd", "--type", "txt")
        self.assertFalse([p for p in opened if p.lower().endswith((".docx", ".wpd", ".txt"))], opened)

    def test_a_name_with_an_ending_matches_only_that_type(self):
        got = self.files("--name", "worksheet.docx", "--match", "complete", "--type", "docx", "--type", "wpd")
        self.assertEqual(sorted(got), ["March/Job 140205/Worksheet.docx"])

    def test_type_spellings_and_refusals(self):
        self.assertEqual(reader.clean_types(["*.DOCX", ".docx", "pdf", " wpd ", ""]), ["docx", "wpd"])
        for bad in ("zip", "word doc", "x" * 11, "."):
            with self.assertRaises(ValueError):
                reader.clean_types([bad])
        self.assertEqual(reader.main([str(self.root), "--out", str(self.out), "--quiet", "--type", "zip"]), 2)

    def test_settings_file_round_trip(self):
        path = Path(self.tmp.name) / "s.txt"
        path.write_text(f"Folder to read: {self.root}\nOther file types: docx; .wpd, txt\n")
        settings = reader.load_settings(path)
        self.assertEqual(settings.types, ["docx", "wpd", "txt"])
        reader.save_settings(settings, path)
        self.assertEqual(reader.load_settings(path).types, ["docx", "wpd", "txt"])
        path.write_text("Other file types: zip\n")
        with self.assertRaises(reader.SettingsError):
            reader.load_settings(path)


def blank_pink_sheet_pdf() -> bytes:
    """A made-up Pink Sheet with nothing filled in, as the form starts."""
    data = pink_sheet_pdf(witnesses=(), job="", page_two_job="", blank=True)
    dropdowns = {f"R&S.{i}" for i in range(6)} | {
        "Dropdown17.0", "Dropdown7", "Dropdown8", "Dropdown1.1", "Dropdown1.2", "Dropdown9",
        "Dropdown4", "Dropdown20.1", "Dropdown5", "Dropdown6"}
    return clear_answers(data, dropdowns)


def pink_sheet_pdf(revised="October 13, 2025", witnesses=(("Pat Example", "Waived", "Sam Counsel"),),
                   job="999001", page_two_job=None, dd9="YES", extra_rs_row=False, blank=False) -> bytes:
    """A MADE-UP Pink Sheet: the real form's field names, invented values.
    Also fills a checklist tick and Billing fields with sentinel values that
    must never appear in Pinky's output."""
    rs_choices = ["Reserved - Print Witness Copy", "Reserved - Via E-Mail Only",
                  "Reserved - Letter Only", "Waived"]
    yes_no = ["YES", "NO"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    form = c.acroForm
    y = [800]

    def nxt():
        y[0] -= 22
        if y[0] < 60:
            c.showPage()
            y[0] = 780
        return y[0]

    def text(name, value=""):
        form.textfield(name=name, value="" if blank else value, x=60, y=nxt(), width=200, height=16)

    def drop(name, options, value):
        form.choice(name=name, options=options, value=value, x=60, y=nxt(), width=200, height=16,
                    fieldFlags="combo")

    def tick(name, on):
        form.checkbox(name=name, checked=on and not blank, x=60, y=nxt(), size=12)

    c.drawString(300, 30, f"Revised {revised}")
    text("Job Number", job)
    text("Text3", "2")
    text("Text4", "First note")
    text("Text6", "second line")
    names = ["Text12", "Text11", "Text10", "Text9", "Text8", "Text7"]
    sent = ["E-Mail", "Text15.0", "Text15.1", "Text15.2", "Text15.3", "Text15.4"]
    for i in range(6):
        w = witnesses[i] if i < len(witnesses) else ("", "", "")
        text(names[i], w[0])
        drop(f"R&S.{i}", rs_choices, w[1] or rs_choices[0])
        text(sent[i], w[2] if i < len(witnesses) or not extra_rs_row else "Orphan Person")
    tick("Check Box18.0.0", True)
    drop("Dropdown17.0", ["Becca", "Rochelle"], "Becca")
    for n in ("Dropdown7", "Dropdown8", "Dropdown1.1", "Dropdown1.2"):
        drop(n, yes_no, "NO")
    drop("Dropdown9", yes_no, dd9)
    tick("Check Box19.0", True)
    drop("Dropdown4", ["DevinAnn", "Becca"], "DevinAnn")
    tick("Check Box19.1.1.1.1.1.0", True)
    text("Text21.1.1.2", "made-up line")
    drop("Dropdown20.1", ["E-Mail", "USB", "N/A"], "E-Mail")
    tick("Check Box19.1.0", False)
    tick("Check Box19.1.1.1.1.1.5.0", True)
    text("Text22.2.2", "1")
    tick("Check Box25", False)
    text("Text26", "")
    # sentinels that must never be output: a checklist tick and Billing
    tick("Check Box18.5", True)
    drop("Dropdown5", ["Yes", "No"], "Yes")
    text("Text13", "SENTINEL-BILLING-4242")
    c.showPage()
    c.drawString(60, 800, "page two")
    form.textfield(name="Text28", value=page_two_job if page_two_job is not None else job,
                   x=60, y=760, width=200, height=16)
    form.choice(name="Dropdown6", options=["Rochelle", "Becca"], value="Rochelle",
                x=60, y=730, width=200, height=16, fieldFlags="combo")
    c.showPage()
    c.save()
    # reportlab cannot draw an empty dropdown, so unused witness rows' R&S are
    # drawn with an answer and cleared here, as they are on the real blank form
    unused = {f"R&S.{i}" for i in range(len(witnesses), 6)}
    return clear_answers(buf.getvalue(), unused) if unused else buf.getvalue()


class PinkSheetMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "2026"
        self.out = self.base / "results"

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, job_folder, data, name="Pink Sheet.pdf"):
        folder = self.root / "November" / job_folder
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)

    def run_pink(self):
        self.assertEqual(reader.main([str(self.root), "--form", "pink", "--out", str(self.out), "--quiet"]), 0)
        with open(self.out / "pink-sheets.csv", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        with open(self.out / "files.csv", encoding="utf-8-sig") as fh:
            files = {place(r): r for r in csv.DictReader(fh)}
        return rows, files

    def test_one_row_per_job_with_each_witness_in_its_own_columns(self):
        self.put("Job 1", pink_sheet_pdf(witnesses=(
            ("Pat Example", "Reserved - Print Witness Copy", "Sam Counsel"),
            ("Lee Sample", "Waived", ""),
        )))
        rows, files = self.run_pink()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        expected = {
            "Form version": "Oct 2025", "Job Number": "999001",
            "Witness A": "Pat Example", "Witness A R&S": "Reserved - Print Witness Copy",
            "Witness A R&S Sent To": "Sam Counsel",
            "Witness B": "Lee Sample", "Witness B R&S": "Waived", "Witness B R&S Sent To": "",
            "Witness C": "", "Witness F R&S Sent To": "",
            "Original +": "2", "Notes": "First note second line",
            "Initial QC completed": "Yes", "Initial QC by": "Becca",
            "30(b)(6)": "NO", "Videotaped": "NO", "Interpreter": "NO", "Cross-Depo": "NO",
            "Picture-in-Picture": "YES", "Depo Summary (Dec 2023 / May 2025 sheets)": "",
            "Production completed": "Yes", "Printed by": "DevinAnn",
            "Year": "2026", "File": "Pink Sheet.pdf",
            "Original: No Printed Original w/ Electronic Copy": "Yes",
            "Original: No Printed Original w/ Electronic Copy - line": "made-up line",
            "Original: No Printed Original w/ Electronic Copy - media": "E-Mail",
            "Original: Printed w/ Full-Mini-Word Printed Copy (Standard Package)": "No",
            "Copies: E-Mail Only": "Yes", "Copies: E-Mail Only - quantity": "1",
            "USB": "No", "USB Qty": "",
            "Final QC by": "Rochelle", "Needs a look": "",
        }
        for col, value in expected.items():
            self.assertEqual(row[col], value, col)
        self.assertEqual(files["November/Job 1/Pink Sheet.pdf"]["Result"], "Pink Sheet read")

    def test_columns_in_order(self):
        cols = reader.pink_sheet.COLUMNS
        self.assertEqual(cols[:5], ["Year", "Month", "Job folder", "File", "Form version"])
        self.assertEqual(cols[5:9], ["Job Number", "Witness A", "Witness A R&S", "Witness A R&S Sent To"])
        self.assertEqual(cols[21:24], ["Witness F", "Witness F R&S", "Witness F R&S Sent To"])
        self.assertIn("Printed by", cols)
        self.assertNotIn("Production by", cols)
        for flag in ("30(b)(6)", "Videotaped", "Interpreter", "Cross-Depo", "Picture-in-Picture", "USB", "USB Qty"):
            self.assertIn(flag, cols)
        self.assertEqual(len(cols), len(set(cols)))

    def test_blank_page_two_job_number_is_not_a_mismatch(self):
        self.put("Job 1", pink_sheet_pdf(job="999001", page_two_job=""))
        rows, _ = self.run_pink()
        self.assertEqual(rows[0]["Needs a look"], "")

    def test_excel_workbook_matches_the_csv(self):
        from openpyxl import load_workbook
        self.put("Job 1", pink_sheet_pdf())
        self.put("Job 2", pink_sheet_pdf(job="999002", witnesses=(("Kim Witness", "Waived", ""),)))
        rows, _ = self.run_pink()
        wb = load_workbook(self.out / "pinky-results.xlsx")
        self.assertEqual(wb.sheetnames, ["Pink Sheets", "Files"])
        ws = wb["Pink Sheets"]
        header = [c.value for c in ws[1]]
        self.assertEqual(header, reader.pink_sheet.COLUMNS)
        self.assertEqual(ws.max_row, 3)
        by_col = {h: i for i, h in enumerate(header)}
        jobs = sorted(r[by_col["Job Number"]].value for r in ws.iter_rows(min_row=2))
        self.assertEqual(jobs, [999001, 999002])  # whole numbers are numbers in Excel
        self.assertEqual(ws.freeze_panes, "A2")
        self.assertEqual(wb["Files"].max_row, 3)

    def test_billing_and_checklist_ticks_never_leave_the_pdf(self):
        self.put("Job 1", pink_sheet_pdf())
        self.run_pink()
        written = (self.out / "pink-sheets.csv").read_text(encoding="utf-8-sig")
        self.assertNotIn("SENTINEL-BILLING-4242", written)
        self.assertFalse((self.out / "fields.csv").exists())
        header = written.splitlines()[0]
        for word in ("Billing", "Rush", "COD", "Check Case", "Text13"):
            self.assertNotIn(word, header)

    def test_older_sheets_put_dropdown9_under_depo_summary(self):
        self.put("Job 1", pink_sheet_pdf(revised="December 8, 2023", dd9="YES"))
        self.put("Job 2", pink_sheet_pdf(revised="May 2, 2025", dd9="NO"))
        rows, _ = self.run_pink()
        got = {r["Job folder"]: (r["Form version"], r["Depo Summary (Dec 2023 / May 2025 sheets)"], r["Picture-in-Picture"])
               for r in rows}
        self.assertEqual(got, {"Job 1": ("Dec 2023", "YES", ""), "Job 2": ("May 2025", "NO", "")})

    def test_unknown_revision_is_reported_not_guessed(self):
        self.put("Job 1", pink_sheet_pdf(revised="January 1, 2027", dd9="YES"))
        rows, files = self.run_pink()
        self.assertEqual(rows[0]["Form version"], "Unknown (Revised January 1, 2027)")
        self.assertEqual((rows[0]["Picture-in-Picture"], rows[0]["Depo Summary (Dec 2023 / May 2025 sheets)"]), ("", ""))
        self.assertIn("Unrecognised form revision", rows[0]["Needs a look"])
        self.assertIn("Dropdown9 is YES", rows[0]["Needs a look"])
        self.assertIn("Unrecognised", files["November/Job 1/Pink Sheet.pdf"]["Note"])

    def test_page_two_job_number_is_checked(self):
        self.put("Job 1", pink_sheet_pdf(job="999001", page_two_job="999002"))
        rows, _ = self.run_pink()
        self.assertIn("Page 2 Job Number differs (999002)", rows[0]["Needs a look"])
        self.assertNotIn("Text28", rows[0])

    def test_sheet_with_no_witness_still_gives_a_row(self):
        self.put("Job 1", pink_sheet_pdf(witnesses=()))
        rows, _ = self.run_pink()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Witness A"], "")
        self.assertIn("No witness listed", rows[0]["Needs a look"])

    def test_r_and_s_details_without_a_name_are_flagged(self):
        self.put("Job 1", pink_sheet_pdf(extra_rs_row=True))
        rows, _ = self.run_pink()
        self.assertIn("Witness row B has R&S details but no witness name", rows[0]["Needs a look"])

    def test_a_pdf_that_is_not_a_pink_sheet(self):
        self.put("Job 1", fillable_form(True), name="Other form.pdf")
        rows, files = self.run_pink()
        self.assertEqual(rows, [])
        self.assertIn("Not a Pink Sheet", files["November/Job 1/Other form.pdf"]["Note"])

    def test_a_filled_in_sheet_beside_a_blank_one_is_used(self):
        self.put("Job 1", blank_pink_sheet_pdf(), name="Pink Sheet.pdf")
        self.put("Job 1", pink_sheet_pdf(), name="Pink Sheet UPDATED.pdf")
        rows, files = self.run_pink()
        self.assertEqual([r["File"] for r in rows], ["Pink Sheet UPDATED.pdf"])
        self.assertIn("2 Pink Sheets in this job folder: used this one, the only one filled in "
                      "(blank, not used: Pink Sheet.pdf)", rows[0]["Needs a look"])
        set_aside = files["November/Job 1/Pink Sheet.pdf"]
        self.assertEqual(set_aside["Result"], reader.RESULT_NOT_USED)
        self.assertIn("Blank; the filled-in Pink Sheet in this job folder was used: Pink Sheet UPDATED.pdf",
                      set_aside["Note"])
        self.assertEqual([r["File"] for r in self._workbook_rows()], ["Pink Sheet UPDATED.pdf"])

    def test_two_filled_in_sheets_are_never_guessed_between(self):
        # one has more answers than the other: still no guess
        fuller = pink_sheet_pdf(witnesses=(("Pat Example", "Waived", "Sam Counsel"), ("Lee Sample", "Waived", "")))
        thinner = pink_sheet_pdf(witnesses=(("Pat Example", "Waived", ""),))
        self.put("Job 1", thinner, name="Pink Sheet.pdf")
        self.put("Job 1", fuller, name="Pink Sheet UPDATED.pdf")
        self.put("Job 1", blank_pink_sheet_pdf(), name="Pink Sheet blank.pdf")
        rows, files = self.run_pink()
        self.assertEqual(sorted(r["File"] for r in rows), ["Pink Sheet UPDATED.pdf", "Pink Sheet.pdf"])
        for r in rows:
            self.assertIn("2 filled-in Pink Sheets in this job folder: all kept, choose by hand", r["Needs a look"])
        self.assertEqual(files["November/Job 1/Pink Sheet blank.pdf"]["Result"], reader.RESULT_NOT_USED)

    def test_all_blank_sheets_are_kept_and_flagged(self):
        self.put("Job 1", blank_pink_sheet_pdf(), name="Pink Sheet A.pdf")
        self.put("Job 1", blank_pink_sheet_pdf(), name="Pink Sheet B.pdf")
        rows, _ = self.run_pink()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("2 Pink Sheets in this job folder, all blank" in r["Needs a look"] for r in rows))

    def test_a_blank_sheet_counts_as_blank(self):
        rows_ = []
        self.put("Job 1", blank_pink_sheet_pdf())
        rows_, _ = self.run_pink()
        row = {k: v for k, v in rows_[0].items()}
        self.assertEqual(reader.pink_sheet.filled_count(row), 0, {k: v for k, v in row.items() if v not in ("", "No")})

    def test_same_job_number_in_two_job_folders_is_flagged_not_dropped(self):
        self.put("Job 1", pink_sheet_pdf(job="999001"))
        self.put("Job 2", pink_sheet_pdf(job="999001"))
        self.put("Job 3", pink_sheet_pdf(job="999003"))
        rows, _ = self.run_pink()
        self.assertEqual(len(rows), 3)
        notes = {r["Job folder"]: r["Needs a look"] for r in rows}
        self.assertIn("Job Number also on a Pink Sheet in: November/Job 2", notes["Job 1"])
        self.assertIn("Job Number also on a Pink Sheet in: November/Job 1", notes["Job 2"])
        self.assertEqual(notes["Job 3"], "")

    def test_a_non_pink_pdf_beside_a_pink_sheet_is_not_a_duplicate(self):
        self.put("Job 1", pink_sheet_pdf())
        self.put("Job 1", fillable_form(True), name="Pink Sheet notes.pdf")
        rows, _ = self.run_pink()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Needs a look"], "")

    def test_how_filled_in_is_counted(self):
        count = reader.pink_sheet.filled_count
        self.assertEqual(count({"Witness A": "Pat", "USB": "No", "Copies: Electronic Only - media": "N/A",
                                "Year": 2026, "File": "x.pdf", "Needs a look": "something"}), 1)

    def _workbook_rows(self):
        from openpyxl import load_workbook
        ws = load_workbook(self.out / "pinky-results.xlsx")["Pink Sheets"]
        head = [c.value for c in ws[1]]
        return [dict(zip(head, r)) for r in ws.iter_rows(min_row=2, values_only=True)]

    def test_settings_file_and_app_carry_the_choice(self):
        path = self.base / "s.txt"
        path.write_text("Form: Pink Sheet\n")
        settings = reader.load_settings(path)
        self.assertEqual(settings.form, "pink")
        reader.save_settings(settings, path)
        self.assertEqual(reader.load_settings(path).form, "pink")
        import pdf_form_reader_app as app_module
        self.assertEqual(app_module._settings_from({"form": "pink"}).form, "pink")
        self.assertEqual(app_module._settings_from({"form": "elsewhere"}).form, "any")


class SavedSettings(unittest.TestCase):
    def test_save_and_load_give_back_the_same_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app" / "settings.txt"
            for original in (
                reader.Settings(folder=r"D:\Jobs\2026", start="month", look_in="all", zips=True,
                                names=["worksheet", "Job Info Sheet.pdf"], match="complete",
                                out=r"C:\Local\results"),
                reader.Settings(folder="/Volumes/Jobs/2026"),
            ):
                reader.save_settings(original, path)
                self.assertEqual(reader.load_settings(path), original)


class NameMatching(unittest.TestCase):
    def match(self, filename, names, how):
        return reader.name_matches(filename, reader.Settings(names=names, match=how))

    def test_partial_and_complete(self):
        self.assertEqual(self.match("Smith  WORKSHEET final.pdf", ["worksheet"], "partial"), "worksheet")
        self.assertIsNone(self.match("Smith Worksheet final.pdf", ["worksheet"], "complete"))
        self.assertEqual(self.match("Worksheet.PDF", ["worksheet"], "complete"), "worksheet")
        self.assertEqual(self.match("Job  Info Sheet.pdf", ["job info sheet.pdf"], "complete"), "job info sheet.pdf")
        self.assertIsNone(self.match("notice.pdf", ["worksheet"], "partial"))

    def test_no_names_means_every_pdf(self):
        self.assertEqual(self.match("anything.pdf", [], "partial"), "")


class AppBehindThePage(unittest.TestCase):
    """The desktop app's Api: what the page calls, driven as the page drives it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self._old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = str(base / "appdata")
        job = base / "2026" / "March" / "Job 140205"
        job.mkdir(parents=True)
        (job / "Smith Worksheet.pdf").write_bytes(fillable_form(True))
        (job / "Notice.pdf").write_bytes(fillable_form(True))
        (base / "results").mkdir()
        self.base = base
        import pdf_form_reader_app as app_module
        self.m = app_module
        self.api = app_module.Api()
        self.page = {"folder": str(base / "2026"), "start": "year", "look_in": "main", "zips": False,
                     "names": ["worksheet"], "match": "partial", "out": str(base / "results")}

    def tearDown(self):
        self.api.stop()
        self.api.wait(10)
        if self._old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self._old_local
        self.tmp.cleanup()

    def test_a_run_reads_the_chosen_pdfs_and_remembers_the_settings(self):
        self.assertEqual(self.api.start(self.page), {"ok": True})
        st = self.api.wait(30)
        self.assertEqual(st["state"], "done")
        self.assertEqual(st["counts"]["pdfs"], 1)
        with open(Path(st["results"]) / "files.csv", encoding="utf-8-sig") as fh:
            files = [place(r) for r in csv.DictReader(fh)]
        self.assertEqual(files, ["March/Job 140205/Smith Worksheet.pdf"])
        self.assertEqual(self.api.load()["names"], ["worksheet"])

    def test_first_load_offers_documents_for_results(self):
        self.assertTrue(self.api.load()["out"])

    def test_what_the_page_sends_is_checked_not_trusted(self):
        s = self.m._settings_from({"folder": ' "D:\\Jobs" ', "start": "decade", "look_in": "x",
                                   "names": ["worksheet", " Worksheet ", "", "a  b"], "match": "??"})
        self.assertEqual((s.folder, s.start, s.look_in, s.match), ("D:\\Jobs", "year", "main", "partial"))
        self.assertEqual(s.names, ["worksheet", "a b"])

    def test_refusals_are_explained(self):
        cases = [
            ({**self.page, "folder": ""}, "Choose the folder"),
            ({**self.page, "folder": str(self.base / "nope")}, "was not found"),
            ({**self.page, "out": str(self.base / "nope")}, "save results in was not found"),
            ({**self.page, "out": str(self.base / "2026")}, "OUTSIDE"),
        ]
        (self.base / "OneDrive - Gallo").mkdir()
        cases.append(({**self.page, "out": str(self.base / "OneDrive - Gallo")}, "cloud"))
        for page, words in cases:
            answer = self.api.start(page)
            self.assertFalse(answer["ok"], page)
            self.assertIn(words, answer["error"])
        self.assertEqual(self.api.status()["state"], "idle")

    def test_stop(self):
        self.api._stop.set()  # as if Stop were pressed before the first file
        settings = self.m._settings_from(self.page)
        out = self.base / "results" / "stopped"
        self.api._work(settings, Path(settings.folder).resolve(), out)
        st = self.api.status()
        self.assertEqual(st["state"], "stopped")
        self.assertEqual(st["counts"]["pdfs"], 0)

    def test_file_types_from_the_page(self):
        self.assertEqual(self.api.check_type("*.DOCX"), {"ok": True, "type": "docx"})
        self.assertFalse(self.api.check_type("pdf")["ok"])
        self.assertIn("zip", self.api.check_type("zip")["error"])
        answer = self.api.start({**self.page, "types": ["docx", "not a type"]})
        self.assertFalse(answer["ok"])
        (self.base / "2026" / "March" / "Job 140205" / "Smith Worksheet.docx").write_bytes(b"x")
        self.assertEqual(self.api.start({**self.page, "types": ["docx"]}), {"ok": True})
        st = self.api.wait(30)
        self.assertEqual((st["counts"]["pdfs"], st["counts"]["other_found"], st["types"]), (1, 1, ["DOCX"]))
        self.assertEqual(self.api.load()["types"], ["docx"])

    def test_the_built_app_self_check(self):
        try:
            import webview  # noqa: F401
        except ImportError:
            self.skipTest("pywebview not installed")
        self.assertEqual(self.m.selftest(), 0)


class NoInternet(unittest.TestCase):
    def test_imports_nothing_that_reaches_the_network(self):
        for source_file in ("pdf_form_reader.py", "pdf_form_reader_app.py"):
            self._check(source_file)

    def _check(self, source_file):
        source = (Path(__file__).resolve().parent.parent / source_file).read_text(encoding="utf-8")
        for banned in ("socket", "urllib", "http.client", "requests", "smtplib", "ftplib", "subprocess"):
            self.assertNotIn(f"import {banned}", source)
            self.assertNotIn(f"from {banned}", source)


if __name__ == "__main__":
    unittest.main()


class FileColumn(unittest.TestCase):
    def test_file_name_only(self):
        self.assertEqual(reader.display_name("March/Job 1/Pink Sheet.pdf"), "Pink Sheet.pdf")
        self.assertEqual(reader.display_name("March/Job 1/Sub/x.pdf"), "x.pdf")
        self.assertEqual(reader.display_name("March/Job 1/b.zip > docs/Pink Sheet.pdf"), "Pink Sheet.pdf (in b.zip)")
        self.assertEqual(reader.display_name("March/Job 1/b.zip > in.zip > y.pdf"), "y.pdf (in in.zip)")

    def test_year_and_month_when_starting_at_one_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "2026" / "March" / "Job 1"
            job.mkdir(parents=True)
            (job / "worksheet.pdf").write_bytes(fillable_form(True))
            out = Path(tmp) / "out"
            self.assertEqual(reader.main([str(job), "--start", "job", "--out", str(out), "--quiet"]), 0)
            with open(out / "files.csv", encoding="utf-8-sig") as fh:
                row = next(csv.DictReader(fh))
            self.assertEqual((row["Year"], row["Month"], row["Job folder"], row["File"]),
                             ("2026", "March", "Job 1", "worksheet.pdf"))
