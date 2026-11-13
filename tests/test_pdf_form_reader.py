"""
Tests for pdf_form_reader.py, run against MADE-UP forms built here.

No real job files are used or stored. To run:

    python -m pip install -r requirements-dev.txt
    python -m unittest discover -s tests -v
"""

import csv
import io
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
        fields, files = self.run_reader()
        names = sorted(f["File"] for f in files)
        self.assertEqual(
            names,
            sorted([
                "March/Job 140205/worksheet.pdf",
                "March/Job 140205/Exhibits/Deeper/scan.pdf",
                "March/Job 140205/bundle.zip > a/worksheet copy.PDF",
                "March/Job 140205/bundle.zip > inner.zip > nested/form.pdf",
            ]),
        )
        self.assertTrue(all(f["Month"] == "March" and f["Job folder"] == "Job 140205" for f in files))
        self.assertTrue(any(f["Field name"] == "rush" and f["Value"] == "Checked" for f in fields))

    def test_formulas_are_not_live_in_excel(self):
        fields, _ = self.run_reader()
        notes = [f["Value"] for f in fields if f["Field name"] == "notes" and f["Value"]]
        self.assertTrue(notes and all(v.startswith("'=") for v in notes))
        counts = [f["Value"] for f in fields if f["Field name"] == "page_count" and f["Value"]]
        self.assertIn("-12", counts)  # a negative number is left alone

    def test_source_folder_is_untouched(self):
        self.run_reader()
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


class NoInternet(unittest.TestCase):
    def test_imports_nothing_that_reaches_the_network(self):
        source = (Path(__file__).resolve().parent.parent / "pdf_form_reader.py").read_text()
        for banned in ("socket", "urllib", "http.client", "requests", "smtplib", "ftplib", "subprocess"):
            self.assertNotIn(f"import {banned}", source)
            self.assertNotIn(f"from {banned}", source)


if __name__ == "__main__":
    unittest.main()
