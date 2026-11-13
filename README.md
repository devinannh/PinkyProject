# PDF form reader

Lists every fillable field in every PDF under a folder: text boxes,
checkboxes, toggles, radio buttons, dropdowns and lists. You get one
spreadsheet with what each field holds.

**It runs only on your computer.** It makes no internet connection, sends
nothing anywhere, and never changes, moves or copies your job files. Zip files
are read in memory; nothing is unpacked onto the drive.

It does **not** use AI and does **not** put anything into the portal. It
shows you what is in the forms so we can decide which form fields belong in
which portal fields.

## One-time setup

1. Install Python from https://www.python.org/downloads/ .
   On Windows, tick **"Add python.exe to PATH"** on the first screen.
2. Download this folder (GitHub: **Code**, then **Download ZIP**) and unzip it
   somewhere like your Documents.
3. Open a command window in that folder:
   - **Windows:** open the folder in File Explorer, click the address bar,
     type `cmd` and press Enter.
   - **Mac:** right-click the folder in Finder, then **New Terminal at Folder**.
4. Install the PDF library (once):
   - Windows: `py -m pip install -r requirements.txt`
   - Mac: `python3 -m pip install -r requirements.txt`

## Running it

Point it at the year folder. Put the folder in quotes:

- Windows: `py pdf_form_reader.py "D:\Jobs\2026"`
- Mac: `python3 pdf_form_reader.py "/Volumes/Jobs/2026"`

To try one month or one job first, add `--start month` or `--start job`:

- `py pdf_form_reader.py "D:\Jobs\2026\March" --start month`
- `py pdf_form_reader.py "D:\Jobs\2026\March\Job 140205" --start job`

Results go into a new dated folder in your **Documents**, for example
`Documents\pdf-form-results-2026-11-13_101500`. To choose another place, add
`--out "C:\somewhere\new-folder"`. It refuses to write inside the folder it
is reading, and never overwrites earlier results.

## What you get

**fields.csv**: one row per form field.

| Column | What it means |
| --- | --- |
| Month, Job folder | The folders the PDF sits in |
| File | The PDF's path. Inside a zip: `bundle.zip > form.pdf` |
| Page | Which page the field is on |
| Field name | The form's own name for the field (what we will match on) |
| Field label | The hover-text label, when the form has one |
| Field type | Text box, Checkbox, Radio buttons (choose one), Dropdown, List, Signature |
| Value | The answer: the text; Checked / Not checked; the option chosen |
| Filled in | Yes / No |
| Choices offered | For dropdowns, lists and radio buttons: every option |
| Raw value | Exactly what the PDF stores, for checking |

**files.csv**: one row per PDF, saying whether its form was read and, if
not, why: no fillable fields (a scan or a flattened form), password-protected,
damaged, or skipped.

## Things to know

- **Toggles** are stored in a PDF as checkboxes, so they show as Checkbox.
- **Radio buttons** show the form's internal name for the option picked. It
  is usually the printed wording, but some forms use names like `Choice2`.
  "Choices offered" lists them all.
- **Signatures** show only Signed / Not signed. The signature is not copied.
- **Scans and flattened forms** have no fields to read. They are listed in
  files.csv for the text and OCR reader, which is the next step.
- **Adobe LiveCycle (XFA) forms** may be only partly readable; files.csv flags them.
- A typed answer that starts with `=` is shown with a leading `'` so Excel
  does not run it as a formula.

## Keep the results private

**Check that the results folder is not synced to the cloud.** On many work
computers, Documents is synced to OneDrive (or iCloud on a Mac), which would
copy the results there. The reader stops without reading anything when the
results folder looks synced (OneDrive, iCloud, Dropbox, Google Drive, Box).
Run it again with `--out` pointing at a local folder that is not synced, such
as `--out "C:\Local\form-results"`.

The spreadsheets contain real client data. Keep them on your computer, do
not email or upload them, and delete the results folder once the values have
been checked and imported.

## For developers

Tests use made-up forms built in memory; no real file is ever stored here.

    python -m pip install -r requirements-dev.txt
    python -m unittest discover -s tests -v
