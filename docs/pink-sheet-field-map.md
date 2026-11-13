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
| **2023** | Revised December 8, 2023 | 106 | (the oldest) Media is "Disc/CD"; "Depo Summary" YES/NO sits under the flags |
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
| Original + | Text3 | Text | all | Unclear: who receives the original plus a copy? Possibly `witnesses.send_original_to` | Decide |
| Notes (2 lines) | Text4, Text6 | Text | all | `production_state.remarks`, or the job's notes | Decide |
| Witness 1–6 | Text12, Text11, Text10, Text9, Text8, Text7 (top to bottom) | Text | all | Match to the job's existing `witnesses` rows by name. Never creates a witness. | Key |
| R&S for witness 1–6 | R&S.0 – R&S.5 | Dropdown: Reserved - Print Witness Copy / Reserved - Via E-Mail Only / Reserved - Letter Only / Waived | all | `witnesses.read_sign` (reserved or waived) and `witnesses.sig_instructions` (how) | Proposed |
| E-mail beside each witness's R&S | E-Mail, Text15.0 – Text15.4 | Text | all | Where the R&S goes. Possibly `witnesses.email`, but that is the witness's own address | Decide |

### Page 1: Initial QC

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| INITIAL QC COMPLETED BY | Dropdown17.0 (+ tick Check Box18.0.0) | Staff first name | all | Initial QC assignee (`initial_qc_assignee_user_id` + name), through an approved name→user table | Proposed |
| 30(b)(6) | Dropdown7 | YES/NO | all | `witnesses.thirty_b6` | Proposed |
| Videotaped | Dropdown8 | YES/NO | all | Job or witness flag: portal home to confirm | Decide |
| Interpreter | Dropdown1.1 | YES/NO | all | Job or witness flag: portal home to confirm | Decide |
| Cross-Depo | Dropdown1.2 | YES/NO | all | The portal's Cross-depo toggle (Production state) | Proposed |
| Depo Summary (2023, May 2025) / Picture-in-Picture (Oct 2025) | Dropdown9 | YES/NO | all, **meaning changes** | Read by version (section 2, item 3) | Decide |
| 13 checklist rows (Check Case Style … Deposition summary) | Check Box18.0.1, 18.1 – 18.11, Check Box7 | Ticks | rows differ by version | Initial QC checklist in Production state | Skip (proposed) |
| Verify order details (RB Invoices, Production/Billing Notes, Firm/Contact warnings, Billing Sheet, End of ASCII) | Check Box1, 2, 4, 5, plus Check Box3 (May 2025) or Check Box6 (Oct 2025) | Ticks | May 2025, Oct 2025 only; the same box name sits on a different row in each | — | Skip (proposed) |

### Page 1: Production

| Printed label | Field | Type | Versions | Proposed portal home | Status |
| --- | --- | --- | --- | --- | --- |
| PRODUCTION COMPLETED BY | Dropdown4 (+ tick Check Box19.0) | Staff first name | all | The portal has no Production-stage person column (Initial QC, Final QC and Billing only) | Decide |
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
