# Pink Sheet: field map (DRAFT for DevinAnn's review)

What each fillable field on the Pink Sheet means, how the versions differ, and
where each one could go in the portal. **Nothing here is decided.** Every
"Proposed" destination waits for DevinAnn's approval; nothing is imported until
then.

**Billing is out of scope for now** (DevinAnn, 2026-11-13: *"Ignore the
Billing section for now. If I confirm it is needed later, we can circle
back."*). The page 2 Billing fields are listed below for completeness only;
Pinky will not map or import them unless that changes.

Read from four blank copies DevinAnn supplied on 2026-11-13. No client data was
used, and no PDF is stored in this repository.

## 1. The versions

The Pink Sheet is the Production department's two-page job checklist (Initial QC,
Production, Final QC, Billing). One layout, three revisions. Pinky can tell
them apart by the **"Revised …" date printed at the bottom of page 1**, which
it will need to do (see section 2).

| Version | Printed date | Fields | Differences from the one before |
| --- | --- | --- | --- |
| **Dec 2023** | Revised December 8, 2023 | 106 | (the oldest) Media is "Disc/CD"; "Depo Summary" YES/NO sits under the flags |
| **May 2025** | Revised May 2, 2025 | 112 | Adds "Verified order details" (5 ticks); media becomes "CD/USB"; adds a media choice for electronic copies |
| **Oct 2025** | Revised October 13, 2025 | 113 | Adds "Picture-in-Picture"; renames order details; adds "End of ASCII" and "Ensure all pages are numbered"; "Deposition Analysis (summary) generation started"; media becomes "USB" |

The file names do not say which version a form is ("Pink Sheet", "UPDATED",
"Updated June 2026" were all one of these three), so Pinky must read the date.

## 2. Problems in the form itself

These are true of every version and limit what can be imported.

1. *(Billing, out of scope for now.)* **The ten billing numbers on page 2 are ONE field** ("Text13"): Page Count,
   Bill Rate, Pay Rate, Appearance Fee and Exhibits – Page Count (original), and
   Billing Rate, Pay Rate, Exhibits – Page Count, Shipping and Check Message
   (copy). Typing in any one of them puts the same text in all ten. **Pinky gets
   one value for all ten and cannot tell which box it was meant for.**
2. **One tick box sits on two or three rows** ("Check Box18.11"): "Read and Sign
   parenthetical is present and correct", "Deposition summary is completed and
   uploaded" (2023 and May 2025 only), and "Deposition summary is included in the
   transcript bundle". Ticking one ticks all of them.
3. **The same field name means different things in different versions.**
   "Dropdown9" is *Depo Summary* (YES/NO) on 2023 and May 2025, and
   *Picture-in-Picture* on Oct 2025. The "Verify order details" ticks and the
   last rows of the Initial QC checklist also move. Reading by field name alone
   would put answers in the wrong place.
4. **"Completed by" holds a first name only**, chosen from a staff list that
   changes with each version. The portal keys people by user number, never by
   name (AGENTS.md: "Identity is a NUMBER"), so names need a lookup table that a
   person approves.

## 3. Field by field

Status key: **Key** = used to find the job or witness, never written;
**Proposed** = a suggested portal home, needs approval; **Decide** = needs
DevinAnn's decision before it can be placed; **Skip (proposed)** = a process tick
recommended not to import; **Unusable** = cannot be read reliably (section 2).

### Page 1, top: the job and its witnesses

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| Job Number | Job Number | Text | all | Find the existing job by `jobs.job_no`. Never creates a job. | Key |
| Original + | Text3 | Text | all | Transcript Order(s), as O+N (section 6, decided 2026-11-18/21) | Wanted |
| Notes (2 lines) | Text4, Text6 | Text | all | `production_state.remarks`, or the job's notes | Decide |
| Witness 1–6 | Text12, Text11, Text10, Text9, Text8, Text7 (top to bottom) | Text | all | Match to the job's existing `witnesses` rows by name. Never creates a witness. | Key |
| R&S for witness 1–6 | R&S.0 – R&S.5 | Dropdown: Reserved - Print Witness Copy / Reserved - Via E-Mail Only / Reserved - Letter Only / Waived | all | `witnesses.read_sign` (reserved or waived) and `witnesses.sig_instructions` (how) | Proposed |
| **R&S Sent To** (the box beside each witness's R&S) | E-Mail, Text15.0 – Text15.4 | Text: a person's name | all | Who the R&S was sent to (DevinAnn, 2026-11-13). Report only, not mapped (DevinAnn, 2026-11-18) | Report only |

### Page 1: Initial QC

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| INITIAL QC COMPLETED BY | Dropdown17.0 (+ tick Check Box18.0.0) | Staff first name | all | Intake's "Initial QC completed by" (section 6, decided 2026-11-21), through the approved name table | Wanted |
| 30(b)(6) | Dropdown7 | YES/NO | all | Witness Toggle "30(b)(6)" (`thirtyB6`); per-witness question open | Wanted |
| Videotaped | Dropdown8 | YES/NO | all | Witness Toggle "Videotaped" (DevinAnn, 2026-11-21); per-witness question open | Wanted |
| Interpreter | Dropdown1.1 | YES/NO | all | Witness Toggle "Interpreter" (DevinAnn, 2026-11-21); per-witness question open | Wanted |
| Cross-Depo | Dropdown1.2 | YES/NO | all | Witness Toggle "Cross-depo" (surcharge "Cross Depo"); per-witness question open | Proposed |
| Depo Summary (2023, May 2025) / Picture-in-Picture (Oct 2025) | Dropdown9 | YES/NO | all, **meaning changes** | Read by version (section 2, item 3) | Decide |
| 13 checklist rows (Check Case Style … Deposition summary) | Check Box18.0.1, 18.1 – 18.11, Check Box7 | Ticks | rows differ by version | Initial QC checklist in Production state | Skip (proposed) |
| Verify order details (RB Invoices, Production/Billing Notes, Firm/Contact warnings, Billing Sheet, End of ASCII) | Check Box1, 2, 4, 5, plus Check Box3 (May 2025) or Check Box6 (Oct 2025) | Ticks | May 2025, Oct 2025 only; the same box name sits on a different row in each | — | Skip (proposed) |

### Page 1: Production

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| PRODUCTION COMPLETED BY ("Printed by") | Dropdown4 (+ tick Check Box19.0) | Staff first name | all | Intake's "Printing completed by" (section 6, decided 2026-11-21) | Wanted |
| Originals: Printed Original w/ Full-Mini-Word Printed Copy (Standard Package) · w/ Electronic Copy · w/ Printed Full-Size Copy · w/ Printed Mini-Size Copy · No Printed Original w/ Electronic Copy | Check Box19.1.0, 19.1.1.0, 19.1.1.1.0, 19.1.1.1.1.0, 19.1.1.1.1.1.0 | Ticks | all | What the original's order was: Production's fulfillment record | Decide |
| Line under each Originals choice | Text21.0, 21.1.0, 21.1.1.0, 21.1.1.1, 21.1.1.2 | Text | all | Unclear: for whom, or how many? | Decide |
| Media for "w/ Electronic Copy" and "No Printed Original" | Dropdown20.0, Dropdown20.1 | E-Mail / USB / N/A (CD on older versions) | all | Fulfillment record | Decide |
| Copies: Full-Mini-Word Printed · Printed Full-Size Only · Printed Mini-Size Only · Electronic Only · E-Mail Only, each with Quantity | Check Box19.1.1.1.1.1.1 – .5.0, Text22.0, 22.1, 22.2.0, 22.2.1, 22.2.2 | Ticks + quantities | all | Fulfillment record | Decide |
| Media for electronic copies | Dropdown11 | USB / N/A (CD on May 2025) | May 2025, Oct 2025 | Fulfillment record | Decide |
| Exhibits – # of pages | Check Box19.1.1.1.1.1.5.2.2, Text24.0 | Tick + number | all | `witnesses.has_exhibits`, exhibit page count | Proposed |
| No Exhibits | Check Box19.1.1.1.1.1.5.2.0, Text24.1 | Tick + text | all | `witnesses.has_exhibits = false` | Proposed |
| Retained | Check Box19.1.1.1.1.1.5.3, Text24.2 | Tick + text | all | `witnesses.exhibit_instructions` | Decide |
| Depo Summary (exhibits row) | Dropdown10 | YES/NO | all | Depo summary ordered | Decide |
| Deposition summary included in bundle | Check Box18.11 (shared) | Tick | all | — | Unusable |
| USB / CD – # | Check Box25, Text26 | Tick + text | all | Fulfillment record | Decide |

### Page 2: Final QC

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| Job Number | Text28 | Text | all | Checked against page 1; a mismatch is reported, not guessed | Key |
| FINAL QC COMPLETED BY | Dropdown6 (+ tick Check Box29) | Staff first name | all | Final QC assignee (by user number, through the name table) | Proposed |
| 10 checklist rows (Ensure Headers … Ensure Exhibit Page Count) | Check Box31.0 – 31.8, Check Box14 | Ticks | all | Final QC checklist | Skip (proposed) |
| (1) O-Email, O-Email Invoice, (2)–(5) C-Email, C-Email Invoice | Text34.0 – Text34.9 | Text (e-mail addresses) | all | Who the original and copies (and their invoices) went to: client contacts. Delivery record, if wanted | Decide |

### Page 2: Billing (out of scope for now)

Not mapped or imported (DevinAnn, 2026-11-13). Kept here so the work is not
lost if Billing is brought back in.

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| BILLING COMPLETED BY | Dropdown2 (+ tick Check Box35) | Staff first name (billing staff) | all | — | Out of scope |
| Original: Rush / COD / Shipping | Dropdown5, Dropdown15, Dropdown3 | Yes/No, Yes/No, FedEx 2-Day … E-mail Only | all | — | Out of scope |
| Copy: Rush / COD / Shipping | Dropdown16, Dropdown18, Dropdown19 | same | all | — | Out of scope |
| Page Count, Bill/Pay/Billing Rate, Appearance Fee, Exhibit Page Counts, Shipping, Check Message | Text13 (one field, ten boxes) | Text | all | — | Out of scope (and unusable as it stands) |

## 4. Decisions for DevinAnn

1. **What the import is for.** Recommended: bring in the job facts (witnesses,
   R&S, flags, what was ordered, exhibits) and who completed each stage. Leave
   out the checklist ticks: they record a finished step, they differ by version,
   and two of them are unreliable (section 2).
2. ~~Billing rows go to Leanne.~~ **Resolved 2026-11-13: Billing is out of
   scope for now** (DevinAnn). Revisit only if she confirms it is needed.
3. **Meanings to confirm:** "Original +", the line under each Originals choice,
   and whose address the R&S e-mail is.
4. **The staff name → user table:** a short list, one row per first name that
   appears in the dropdowns, approved by a person before any import.
5. **The form going forward:** if the Pink Sheet is still being filled in,
   giving "Check Box18.11" a separate box on each row would make future sheets
   fully readable (and "Text13" too, if Billing comes back).

## 5. Decided 2026-11-13 (DevinAnn)

DevinAnn marked the values she needs on a filled-in sheet. Pinky's **Pink Sheet
mode** (`pink_sheet.py`) now reads exactly these into `pink-sheets.csv`, one
row per witness:

- **Page 1, wanted:** Job Number; every witness listed ("If multiple witnesses
  are listed at the top, all must be included"), each with its **R&S** (the
  dropdown beside the name) and **R&S Sent To** (the box to the right of that
  dropdown, a person's name); Original +; Notes; Initial QC completed and by
  whom; 30(b)(6), Videotaped, Interpreter, Cross-Depo and Picture-in-Picture
  (Depo Summary on the older sheets); Production completed and by whom; the
  five Originals choices with their lines and media; the five Copies choices
  with their quantities and media; the USB / CD box and number.
- **Page 1, not wanted:** the Initial QC checklist ticks and "Verify order
  details".
- **Page 2:** one value only for now, **Final QC Completed By**
  ("From the 2nd page, let's just start with 1 value"). Page 2's Job Number is
  not output; Pinky only checks it matches page 1.
- **Billing:** out of scope for now.
- **Job Number:** taken from the form (top left of page 1), not the folder name.

Where these go in the portal is still to be decided, field by field (the
"Proposed portal home" column above). Nothing is imported yet.

### Later the same day (DevinAnn, 2026-11-13)

- **One row per job**, not per witness: Witness A, Witness A R&S, Witness A
  R&S Sent To, then B to F, in the order the rows appear on the form.
- **30(b)(6), Videotaped, Interpreter, Cross-Depo, Picture-in-Picture, USB and
  USB Qty are columns.** (USB and USB Qty are the "Disc/CD" / "CD/USB" box on
  the older sheets.)
- **A blank page 2 Job Number is not a mismatch.** Only two filled-in numbers
  that differ are flagged.
- **Results come as CSV and Excel**: pink-sheets.csv and files.csv, and the
  same two tables as sheets in pinky-results.xlsx.
- The versions are named Dec 2023, May 2025 and Oct 2025.

### Later again (DevinAnn, 2026-11-13)

- "Production by" is renamed **"Printed by"** (the form's "Production
  completed by"). "Production completed" keeps its name.
- The **File** column shows the file's name only, in every table (a file
  inside a zip reads "Pink Sheet.pdf (in bundle.zip)").
- A **Year** column comes before Month, in every table.
- DevinAnn rearranges the columns herself as needed, so their order is not
  a requirement.

### More than one Pink Sheet in a job folder (DevinAnn, 2026-11-13)

*"by 'most filled out', I'm assuming a situation where one version has every
value we need filled out, and another that is blank ... If there is a
situation where multiple are truly filled out, I don't want it to guess."*

- **One filled in, the rest blank:** the filled-in one is used and flagged in
  "Needs a look"; the blank ones are listed in files.csv as "Pink Sheet read -
  not used", naming the one used.
- **More than one filled in** (even if one has more answers): all of them are
  kept and flagged "choose by hand". Pinky never picks between them. Any blank
  ones beside them are still listed as not used.
- **All blank:** all kept and flagged.
- **Blank** means none of the Pink Sheet values above holds an answer; an
  unticked box and the form's own "N/A" default do not count. Checked against
  the four blank templates: all count as blank.
- **The same Job Number in two different job folders:** flagged on both rows,
  nothing dropped.

## 6. Decided 2026-11-18 (DevinAnn)

- **Original + is the portal's Transcript Order(s)** (Job Tracking Log ›
  Turn In › Order Overview; choices None, O+1 – O+5; saved in the job's
  production record as `orderOverview.transcript`). Pinky now adds a
  **Transcript Order(s)** column beside Original +: "2" becomes "O+2", "0"
  becomes "None". Anything that is not a number of copies is left blank and
  flagged in "Needs a look", never guessed.
  - *Corrected 2026-11-21:* O+6 and above are **not** a limit (*"If there is
    an O+6 or more, we can add those as options"*). Pinky passes any number
    through as O+N. Portal follow-up: before an import, add O+6 and up to the
    Transcript Order(s) choices for any number the sheets actually contain.
- **R&S Sent To is NOT mapped to the portal**, but stays in pink-sheets.csv /
  the Excel workbook.
  - *Corrected 2026-11-21:* **Videotaped and Interpreter ARE mapped, to the
    Witness Toggles of the same name, just like 30(b)(6)** (*"Videotaped and
    Interpreter should trigger the Witness Toggles of the same name, just like
    30(b)(6)"*). In the portal: 30(b)(6) is the witness's `thirtyB6`;
    Videotaped and Interpreter are the witness's `surcharges` "Videotaped" and
    "Interpreter"; Cross-Depo is "Cross Depo" beside them. They stay in the
    report too.
  - Open: the Pink Sheet holds ONE value per sheet, while each Witness Toggle
    belongs to ONE witness. See "Open questions" below.
- **The "Deposition summary is included in the transcript bundle" tick box is
  ignored.** It was never output; no change to the form is needed.
- **Pink Sheets only.** Word forms are not read; rows stay in folder order.

### Intake: who did Initial QC and who did Printing

*Rewritten 2026-11-21. The first draft called the halves "Checking" and
Printing; DevinAnn: "It's Initial QC and Printing that make up Intake."*

The portal's **Intake** is the old Initial QC and Printing sections combined.
Today it holds ONE assignee and ONE completion time
(`production_state.initial_qc_assignee` / `_user_id` /
`initial_qc_completed_at`), and its checklist ticks do not record who ticked
them, so it cannot say that one person did Initial QC and another did
Printing. DevinAnn: the portal must keep both names, never drop or merge one.

Decided (DevinAnn, 2026-11-21: *"we will need a value for each Initial QC and
Printing. When the values indicate the same user, the portal can simplify
from User A completed Initial QC and User A completed Printing, to User A
completed Intake ... The values will be separated for most RB-derived jobs,
while they will be combined by default once the portal is live."*):

- **Two values on every job: Initial QC completed by, and Printing completed
  by**, each the person's user number where they have one, their name, and
  when.
- **When both name the same person, the portal shows one line:** "User A
  completed Intake". When they differ, it shows both: "User A completed
  Initial QC", "User B completed Printing". Both values are always stored.
- **Defaults:** for RB-derived jobs (the Pink Sheet import), the two values
  are filled separately: Pink Sheet "Initial QC by" fills Initial QC, and
  "Printed by" fills Printing. Once the portal is live, completing Intake
  sets both to the same person by default.
- "Final QC by" fills Final QC.

Still open: where the two values are stored. Recommended: inside the job's
production record, the way R&S verification already keeps `{by, at}` (no
database change). The alternative is two new database columns beside the
Initial QC ones, easier to sort and filter on the Job Tracking Log but a
migration needing approval.

### Proposed: the staff name table

Some "completed by" names have no portal user number, and may have no RB user
number either. Proposal: one row per first name that appears on the sheets —
*name on the sheet → full name → portal user (if any)*. Where there is no
portal user, the import keeps **the name as written with no number**, never a
guessed number. This matches how the portal already keeps lane assignees:
the number first, the name beside it as a fallback. An RB user number is not
needed for the portal. DevinAnn approves the table before any import.

### Proposed: getting approved rows into the portal

- **Where it saves:** the portal's own database (the job's production record
  and its witnesses), never Netlify Blobs. Any holding step before "apply" is
  a database table too.
- **Reviewing in Pinky** (approve, edit, remove rows) keeps real data on the
  reviewer's computer until it is approved.
- **Two ways to hand over:** (a) Pinky sends the approved rows straight to the
  portal, which means signing in to the portal from Pinky; (b) Pinky saves an
  approved file, and a small portal Import page takes it, checks every row
  again, shows what will change, and applies it on confirm. Both need the same
  portal-side checks; (b) avoids building sign-in into Pinky while the
  portal's hosting (and its sign-in) is due to change.
- Either way the portal re-checks every row (the job exists by Job Number,
  witnesses match, names are in the approved table) and writes Audit Trail
  entries in the uploader's name. Going through the portal is also what keeps
  it from being a data repair (AGENTS.md: writes from outside the application
  are Elizabeth's).

### Open questions (2026-11-21)

1. **One flag per sheet, toggles per witness.** The Pink Sheet's 30(b)(6),
   Videotaped, Interpreter and Cross-Depo are one value for the whole sheet;
   the portal's Witness Toggles are set witness by witness. With one witness
   listed this is exact. With several, should the sheet's YES switch the
   toggle on for every witness on the sheet, or should those sheets be
   flagged for a person to choose the witness?
2. **Where Intake's two values are stored** (above).
