# Pink Sheet upload to the portal — design (DRAFT for DevinAnn's review)

Status: **design only.** Nothing here is built in the portal yet; the portal
repository was read-only in the session that wrote this (2026-11-21). Where a
point is DevinAnn's decision it is quoted; where it is my proposal it says
**Proposed**.

## The decision this implements

DevinAnn, 2026-11-21: *"Pinky should export the spreadsheet for staff to upload
in the portal. The portal should preview proposed changes and flag duplicates,
unmatched records, and conflicts before staff confirm. Save the approved values
to the portal database. Uploading the same approved file again should produce
no duplicate changes."*

## 1. The flow, start to finish

1. **Pinky reads the Pink Sheets** on the staff member's computer and writes
   `pinky-results.xlsx` (and the same tables as CSV). Nothing leaves the
   computer.
2. **Staff review the spreadsheet** in Excel if they want (they may rearrange,
   add or hide columns, and delete rows they do not want imported).
3. **Staff upload the workbook** on a portal page. **Proposed location:**
   Production › Job Tracking Log › *Import Pink Sheets*.
4. **The portal shows a preview**: every proposed change, and everything it
   will NOT do and why. Nothing is saved yet.
5. **The reviewer makes the choices the preview asks for** (which witnesses a
   YES applies to; whether to replace a value the portal already holds).
6. **Confirm.** The portal checks everything again and saves the approved
   values to its database, with an audit trail entry for each job.
7. **Uploading the same file again changes nothing** (section 6).

## 2. What the portal reads

- The **Pink Sheets** sheet of `pinky-results.xlsx` (or `pink-sheets.csv`).
  The portal can already read Excel files (it has the `xlsx` library).
- **Columns are found by their heading, never by position**, so staff can
  rearrange or add columns. A file missing a required heading is refused with
  the heading named. Required: Job Number, Form version, the Witness A–F
  columns, and the columns of whatever is being imported.
- **The file is not kept.** No Netlify Blobs, no stored upload. The preview is
  worked out when the file is uploaded; on Confirm the browser sends the same
  file again with the reviewer's choices, and the portal works everything out
  again before saving anything. So there is no half-saved import to clean up.
- Rows Pinky flagged in "Needs a look" are shown with Pinky's note.

## 3. Matching, and what is flagged

| Check | How | If it fails |
| --- | --- | --- |
| **The job** | By Job Number (the portal's own Job Number reader), to an existing job. Never creates a job. | **Unmatched job:** the row is listed and nothing on it is imported. |
| **Duplicates in the file** | The same Job Number on more than one row. | **Duplicate:** none of those rows is imported until the reviewer chooses one in the preview (or removes the others and uploads again). |
| **Each witness** | Witness A–F, by name, to the job's existing witnesses: same name, ignoring capital letters and extra spaces. Never creates a witness. | **Unmatched witness:** that witness's values (R&S, toggles) are not imported; the rest of the job is. **Two portal witnesses with that name:** flagged the same way. |
| **Staff names** | Initial QC by, Printed by, Final QC by, through the approved staff-name lookup. Each user number in the lookup is checked against the portal's user list at preview time. | **No verified match:** the name is kept exactly as written, with no user number. **Ambiguous in the lookup:** flagged; nothing is saved for that name until the lookup is settled. |
| **Conflicts** | A value the portal already holds that differs from the sheet. | **Conflict:** shown side by side. **Proposed default: keep the portal's value**; the reviewer ticks "Replace" to use the sheet's. |

Every proposed change is one of:

- **New**: the portal has nothing; the sheet's value will be saved.
- **Same**: the portal already holds this value; nothing will be saved.
- **Conflict**: see above.
- **Not imported**: with the reason (unmatched, duplicate, needs review,
  not mapped).

## 4. What is saved, and where

| From the Pink Sheet | Saved to | Notes |
| --- | --- | --- |
| Original + (as Transcript Order(s), O+N) | The job's production record (`production_state`), Order Overview → Transcript Order(s) | Before the first import, the portal's choices get whatever O+6 and up the first run found. |
| R&S (per witness): Reserved / Waived | The witness's `reserved` (Yes / No) | Saved through the portal's own witness edit, so the R&S verification rule applies (a changed answer withdraws the verification and records it on the audit trail). Blank = no change. The three "Reserved - …" methods are not mapped yet. |
| 30(b)(6), Videotaped, Interpreter (and Cross-Depo, proposed) | The matched witness's Witness Toggle | One witness: a YES switches the toggle on. Several witnesses: the reviewer ticks one, several or all; none ticked = toggle left as it is. **Proposed:** a NO never switches a toggle off. |
| Initial QC by / Printed by | `production_state`: Intake's Initial QC and Printing completion details (section 5) | RB jobs: dates left blank. |
| Final QC by | **Proposed:** `production_state`, Final QC completion details, the same way (section 5) | Final QC today records only when it was completed, not by whom. |
| R&S Sent To, Picture-in-Picture, Notes, Originals, Copies, USB, the three R&S methods | Not saved | Stay in the spreadsheet. Notes, Originals, Copies and USB have no decided home yet. |

## 5. Initial QC and Printing completion details

DevinAnn, 2026-11-21: *"Use the existing `production_state` database table,
where Intake and Final QC completion are already recorded. Store separate
completion details for Initial QC and Printing, including the person's name,
verified portal user number when available, and completion time when known.
Keep those details separate from the lane assignee and the job's current
stage."*

**Proposed columns** on `production_state`, following the table's existing
pattern (a person is a user number plus a name snapshot, as the lane assignees
are):

| Column | Holds |
| --- | --- |
| `intake_initial_qc_by_user_id` | the verified portal user number, or empty |
| `intake_initial_qc_by_snapshot` | the name, exactly as recorded |
| `intake_initial_qc_at` | when, or empty when not known |
| `intake_printing_by_user_id` | as above, for Printing |
| `intake_printing_by_snapshot` | |
| `intake_printing_at` | |
| `final_qc_completed_by_user_id` *(proposed, for Final QC by)* | |
| `final_qc_completed_by_snapshot` *(proposed)* | |

- They sit beside `initial_qc_completed_at` (Intake complete) and
  `final_qc_completed_at`, and never replace or move the lane assignees or the
  job's stage.
- **This is a database change (a migration).** It follows the portal's
  migration rules: announced first, and stopped for DevinAnn before anything is
  pushed. `production_state` is part of the Job Number consolidation, so the
  columns belong in the post-switch shape; the timing is DevinAnn's.
- **Live work:** completing Intake records the same person (the one
  completing it, by user number) for both, with the time. *Proposed:* if
  either half already holds a different person, completing Intake does not
  overwrite it.
- **Display:** both halves naming the same person → "User A completed
  Intake". Different people → "User A completed Initial QC" and "User B
  completed Printing". A blank date shows as no date, never a guessed one.
- **RB jobs (the import):** Initial QC ← "Initial QC by", Printing ←
  "Printed by", dates blank.

## 6. Uploading the same file twice

- Every value is compared with what the portal holds before anything is
  written. Equal is **Same**, and Same writes nothing and adds no audit entry.
- So uploading the same approved file again shows every line as Same, saves
  nothing and adds nothing to any audit trail.
- The completion details follow the same rule: a name already recorded is not
  recorded again.
- Toggles: switching on a toggle that is already on is Same.

## 7. Audit trail and permissions

- Each job that changes gets one audit entry on its Job Number, in the
  uploader's name: "Pink Sheet import: updated …", with before and after for
  each field. Witness changes go through the witness edit, which writes its
  own entries (including any R&S verification withdrawal).
- **Proposed gate:** the same staff gate as editing a witness in the
  Production console. The uploader is taken from the session, never from the
  file.
- Because the writes go through the portal's own checks and are audited, the
  import is ordinary application work, not a data repair.

## 8. Before the first real import

1. Approve the staff-name lookup (draft sent 2026-11-21).
2. Run Pinky on a real month; read `summary.csv` for the Transcript Order(s)
   values, the number of toggle reviews, and any staff names not yet in the
   lookup.
3. Add the Transcript Order(s) options the run found.
4. Decide the three R&S methods, and homes for Notes, Originals, Copies and
   USB (or leave them in the spreadsheet).
5. Approve the `production_state` columns (section 5).
6. Settle where the portal's database will live (the earlier question about
   moving it off Netlify before real data goes in).

## 9. Proposed build order (portal work, small pull requests)

1. The `production_state` columns, the live default when Intake is completed,
   and the one-line / two-line display.
2. The upload page: read the workbook and show the preview. Saves nothing.
3. Confirm: save, with the audit trail, the witness-edit path and the
   repeat-upload rule.
4. The Witness Toggle picker in the preview.
