# PDF form reader

Lists every fillable field in the PDFs you choose (by file name and by
where they sit in the job folders): text boxes, checkboxes, toggles, radio
buttons, dropdowns and lists. You get one
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

## Choosing what to read: `reader-settings.txt`

Open **reader-settings.txt** (in this folder) in Notepad (Windows) or
TextEdit (Mac), change the text after each colon, and save. Each setting has
a short explanation beside it.

| Setting | What to put |
| --- | --- |
| Folder to read | The year folder, e.g. `D:\Jobs\2026` |
| Folder is | `year`, `month` or `job`: what that folder is. Use `month` or `job` to try a small batch first. |
| Look in | `main job folder`: only files sitting directly in each job folder; subfolders are not opened. `all subfolders`: the job folder and every folder inside it. |
| Include zip files | `no` or `yes`. With `yes`, PDFs inside zip files in those places are read too. |
| File names | The names to look for, one per line, each starting with a dash. No dashes = every PDF. |
| Match | `partial`: the PDF's name **contains** one of the names. `complete`: the PDF's name **is** one of the names. |
| Results folder | Where results go. Blank = a new dated folder in Documents. |

Matching ignores capital letters, extra spaces and the `.pdf` ending. With
the name `worksheet`:

| PDF name | partial | complete |
| --- | --- | --- |
| `Worksheet.pdf` | found | found |
| `Smith Worksheet FINAL.pdf` | found | not found |
| `Notice of Deposition.pdf` | not found | not found |

A typo in the settings stops the reader before it reads anything, and it says
which line to fix.

## Running it

Open a command window in this folder (see setup, step 3) and type:

- Windows: `py pdf_form_reader.py`
- Mac: `python3 pdf_form_reader.py`

On Windows you can also **double-click `pdf_form_reader.py`**. The window
stays open at the end until you press Enter.

The screen shows the settings it used and a count of what it did: PDFs read,
PDFs passed over because the name did not match, and zip files not opened.
If the count looks wrong, check the settings and run it again into a new
results folder (it never overwrites earlier results).

For a one-off run without editing the file, settings can be typed after the
command and override the file, e.g.
`py pdf_form_reader.py "D:\Jobs\2026\March" --start month --name worksheet --match complete`.
Type `py pdf_form_reader.py --help` to list them.

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

**files.csv**: one row per PDF read, with which of your file names it
matched, and whether its form was read and, if not, why: no fillable fields (a scan or a flattened form), password-protected,
damaged, or skipped.

**settings-used.txt**: the settings that produced these results.

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
