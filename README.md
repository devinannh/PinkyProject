# Pinky - Form Reader

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

## The app (Windows)

### Getting it

1. On GitHub, open this project, then the **Actions** tab.
2. Click the newest **Build Windows app** run with a green tick.
3. Under **Artifacts** at the bottom, click **Pinky-for-Windows**.
   A zip downloads.
4. Open the zip and drag **Pinky.exe** to your Desktop (or any
   folder on your computer). There is nothing to install.

**The first time you open it, Windows may warn you.** The app is not signed
with a paid company certificate, so Windows shows "Windows protected your
PC". Click **More info**, then **Run anyway**. You will not be asked again
for that copy. If your antivirus or IT policy blocks it, IT can allow it, or
we can look at signing it.

### Using it

The app looks and behaves like GalloScript: steps down the left, a card for
each step, and the results on the right. It follows Windows' light or dark
setting.

1. **Folder to read**: click **Browse…** and pick the year folder (or one
   month or one job to try a small batch first), and say which it is.
2. **Where to look in each job folder**: *Main job folder only* reads files
   sitting directly in each job folder and does not open subfolders. *Job
   folder and all subfolders* reads everything inside it. Tick *Also read
   PDFs inside zip files* to include zips.
3. **File names to look for**: type a name and press Enter (or **Add**). Each
   name shows as a tag; click its **×** to remove it. Choose **Partial** (the
   file name contains it) or **Complete** (the file name is exactly it); the
   grey box under it shows an example of what your choice finds.
   **File types** (optional): Pinky always reads PDF forms. To also *find*
   other kinds of files (Word, WordPerfect, text, ...), type the ending, such
   as `docx`, and press Enter. Those files are listed in files.csv by name
   and folder, with their type; they are never opened or read. A file name
   written with an ending, like `worksheet.docx`, finds only that type.
   **Form**: *Any fillable PDF* lists every field of every PDF (fields.csv).
   *Pink Sheet* reads the Production department's Pink Sheet into
   **pink-sheets.csv**, one row per job: Job Number, Witness A to F each
   with R&S and R&S Sent To, Original +, Notes, Initial QC, the YES/NO flags,
   Production (Printed by), Originals, Copies, USB and USB Qty, and Final QC By. Checklist ticks
   and Billing are left out, and fields.csv is not written. Pinky reads the
   sheet's revision from its "Revised …" date, and anything odd (no Job
   Number, page 2 Job Number different, an unknown revision, no witness) is
   flagged in the "Needs a look" column and in files.csv. If a job folder
   holds more than one Pink Sheet, Pinky uses the filled-in one only when the
   others are blank (those are listed in files.csv as not used); when more
   than one is filled in, it keeps them all and flags them to choose by hand.
   The same Job Number in two job folders is flagged on both. Add `pink sheet` as
   a file name so only the Pink Sheets are opened. See
   `docs/pink-sheet-field-map.md`.
4. **Save results in**: pick a folder on this computer. A new dated folder is
   made inside it each time, so earlier results are never overwritten.
5. Press **Read PDFs** at the bottom. **Stop** halts after the current file.
   The Results panel shows the counts as it finishes; **Open results folder**
   shows the spreadsheets.

The app remembers your choices for next time. It keeps them in
`%LOCALAPPDATA%\Pinky\settings.txt`, which holds folder paths and
file names only, never anything read from a PDF.

The window is drawn by Microsoft Edge WebView2, which comes with Windows 10
and 11. If the app opens to a blank window on an older or locked-down PC,
IT can install the WebView2 Runtime from Microsoft.

With the name `worksheet`:

| PDF name | Partial | Complete |
| --- | --- | --- |
| `Worksheet.pdf` | found | found |
| `Smith Worksheet FINAL.pdf` | found | not found |
| `Notice of Deposition.pdf` | not found | not found |

Capital letters, extra spaces and the file's ending (`.pdf`, `.docx`) never matter.

## What you get

**fields.csv**: one row per form field.

| Column | What it means |
| --- | --- |
| Year, Month, Job folder | The folders the PDF sits in |
| File | The file's name only. Inside a zip: `form.pdf (in bundle.zip)` |
| Page | Which page the field is on |
| Field name | The form's own name for the field (what we will match on) |
| Field label | The hover-text label, when the form has one |
| Field type | Text box, Checkbox, Radio buttons (choose one), Dropdown, List, Signature |
| Value | The answer: the text; Checked / Not checked; the option chosen |
| Filled in | Yes / No |
| Choices offered | For dropdowns, lists and radio buttons: every option |
| Raw value | Exactly what the PDF stores, for checking |

**pinky-results.xlsx**: the same tables as sheets in one Excel workbook
(header row frozen, filters on, whole numbers stored as numbers, and typed
answers that start with `=` kept as plain text).

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
Choose a local folder that is not synced instead, such as `C:\Local\form-results`
(in the app: **Save results in**; on the command line: `--out`).

The spreadsheets contain real client data. Keep them on your computer, do
not email or upload them, and delete the results folder once the values have
been checked and imported.

## Advanced: running it without the app

The same reader can run from a command window, for anyone who prefers
that. It is not needed with the app.

### One-time setup

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

### Choosing what to read: `reader-settings.txt`

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

### Running it

Open a command window in this folder (see setup, step 3) and type:

- Windows: `py pdf_form_reader.py`
- Mac: `python3 pdf_form_reader.py`

On Windows you can also **double-click `pdf_form_reader.py`**. The window
stays open at the end until you press Enter.

The screen shows the settings it used and a count of what it read: PDFs
read, form fields listed, and files needing a look. Files passed over are
not counted. If the results look wrong, check the settings and run it again into a new
results folder (it never overwrites earlier results).

For a one-off run without editing the file, settings can be typed after the
command and override the file, e.g.
`py pdf_form_reader.py "D:\Jobs\2026\March" --start month --name worksheet --match complete`.
Type `py pdf_form_reader.py --help` to list them.

## For developers

Tests use made-up forms built in memory; no real file is ever stored here.

    python -m pip install -r requirements-dev.txt
    python -m unittest discover -s tests -v

The app is `pdf_form_reader_app.py` (the `Api` the page calls, and the window)
plus the page in `ui/`, styled after GalloScript (egallo8/YesLaw). The tests
drive `Api` the way the page does. The .exe is built by `.github/workflows/build-windows-exe.yml` on a GitHub
Windows machine, which runs every test, builds with PyInstaller, and starts
the finished .exe with `--selftest` before offering it for download.
