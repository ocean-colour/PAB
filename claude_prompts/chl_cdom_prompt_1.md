# Chl-a/CDOM Provenance Pass — Implementation

## Goals

Implement Stage 10 of the coding plan: one combined re-ingestion pass over the
existing 881 matched floats that (a) fixes the never-populated
`floats.project_name`/`data_center` and per-profile `data_mode` provenance
columns, (b) adds CDOM ingestion with per-parameter data mode and `_ADJUSTED`
values for CHLA and CDOM (and BBP700 if cheap), and (c) migrates the schema
v3→v4 to hold the new fields. The analysis and reports built on this pass live
in `claude_prompts/chl_cdom_prompt_2.md`, which must not start until this doc's
tasks are complete and verified.

## Claude

### Skills

None specific — this is ingestion/schema work on the existing `pab` modules.
Do not use the BING-fit skills (`run-bing-fit`, `batch-fit-argo`); no fitting
is redone in this pass.

### Working agreements

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Extend the existing seams — `pab/argo/fetch.py`,
  `pab/argo/summary.py`, `pab/pipeline.py`, and the forward-migration pattern
  already in `pab/db/schema.py` (`_v2_to_v3`). Do not re-implement the fetch or
  summary paths.
- **This pass migrates the schema and re-ingests data.** Test everything —
  migration, extraction, threading, re-ingestion — against a small subset
  (a handful of floats) and confirm it before running over all 881 floats.
  Re-running must add/update records without silently clobbering
  previously-populated fields.
- **`pab.db` is already local.** It was downloaded from `s3://pab/full/pab.db`
  to `$PAB_DATA_DIR/pab.db` this session — do not re-download it.
- **Decisions are already made.** C1–C5 in
  `claude_prompts/chl_cdom_matchups.md` are answered; Stage 10 in the coding
  plan pins the scope. Do not reopen them — raise anything genuinely blocking
  in Q&A below instead of guessing.

## Context

Read these before running:

- `docs/design/PAB_design.md` (v0.5) — the BGC-Argo provenance and CDOM
  sections: what the pass must produce and why.
- `docs/design/PAB_coding_plan.md` (v0.2) — **Stage 10 — BGC-Argo provenance &
  CDOM ingestion**: the authoritative scope for this doc's tasks.
- `claude_prompts/chl_cdom_matchups.md` — the full planning/Q&A record
  (C1–C5, Q1–Q11), including the Sea-Bird CDOM calibration-bias investigation
  (RAF 5.62×, pre-2023-01-13 sensors) and the AOML/DAC finding (617 of 881
  floats AOML-processed, externally verified against the GDAC index but not
  stored in `pab.db`).
- `pab/db/schema.py` — the schema and the `_v2_to_v3` forward-migration
  pattern to follow for v3→v4.
- `pab/argo/fetch.py` — `DEFAULT_PARAMS` and `iter_profiles` (where
  `PROJECT_NAME`/`DATA_CENTRE` extraction is missing).
- `pab/argo/summary.py` — `persist_summary()` already accepts
  `project_name`/`data_center` parameters that nothing supplies.
- `pab/pipeline.py` — `ingest()` and its two `persist_summary()` call sites,
  which today drop even the `DATA_MODE` they extract.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below

## Tasks

1. **Spot-check `CDOM_ADJUSTED`.** Before writing any ingestion code, fetch two
   or three real BGC-Argo profiles carrying CDOM via argopy, in a mode that
   surfaces `CDOM_ADJUSTED` alongside raw `CDOM`, from floats whose sensors
   were calibrated/serviced before 2023-01-13. Determine whether the GDAC's
   `CDOM_ADJUSTED` already has the Sea-Bird RAF-5.62 correction baked in
   (i.e., whether `CDOM_ADJUSTED / CDOM ≈ 5.62`, some other factor, or is
   absent/unpopulated). Per C2, this answer drives whether we later apply the
   correction ourselves or read it from the adjusted field — do not decide
   that here; just establish the fact. Report findings in the Reports section
   below and log your work. If the spot-check is ambiguous (e.g., no adjusted
   values found on any sampled float), report exactly what you saw and raise
   the ambiguity in Q&A rather than guessing.

2. **Fix DAC/project-name provenance + tests.** In
   `pab/argo/fetch.py::iter_profiles`, extract `PROJECT_NAME` and
   `DATA_CENTRE` per float from the argopy dataset. In
   `pab/pipeline.py::ingest()`, thread `project_name`/`data_center` — and the
   `DATA_MODE` it already extracts but drops — through both
   `persist_summary()` call sites. No schema change is needed:
   `floats.project_name`/`data_center` and `profiles.data_mode` have existed
   since Stage 1; they are simply never populated. Add tests: a fixture
   asserting `floats.data_center` round-trips through ingestion (this is the
   exact regression test for the bug that was found). Verify against a small
   subset of floats before moving on. This fix is self-contained — land and
   verify it independently of Task 3. Log your work.

3. **CDOM ingestion, per-parameter provenance, and schema v3→v4 + tests.**
   Following Stage 10 of the coding plan:
   - Add `"CDOM"` to `pab/argo/fetch.py::DEFAULT_PARAMS`. Compute its
     mixed-layer mean like `CHLA` (plain mean, no de-spike/IQR — Bisson's
     despike recipe is `BBP700`-specific).
   - Extract, per profile, the parameter-level data mode and `_ADJUSTED`
     value for `CHLA` and `CDOM` (and `BBP700` for consistency if cheap).
   - Migrate the schema v3→v4 in `pab/db/schema.py`, following the existing
     `_v2_to_v3` forward-migration pattern: add to `mld_summary` — `cdom`,
     `cdom_std`, `cdom_adjusted`, `chla_adjusted`, `chla_data_mode`,
     `cdom_data_mode` (names provisional per Stage 10 — finalize during
     implementation, staying consistent with existing column conventions).
   - Tests: CDOM mixed-layer mean (known-answer, mirroring the existing CHLA
     test); v3→v4 migration idempotency.

   Verify on a small subset before Task 4. Log your work; raise blocking
   questions in Q&A rather than guessing.

4. **Run the combined re-ingestion and verify.** Per C1 and C4, run ONE
   combined pass (Chl-adjusted + CDOM + DAC/provenance) over the existing 881
   matched floats only — do not broaden the float selection. First run a small
   subset end-to-end as a smoke test confirming no previously-populated field
   regresses; then run the full set. Verify against known facts, from
   `pab.db` directly:
   - The AOML count matches the externally-verified 617 of 881 (remainder
     across Coriolis/INCOIS/MEDS/CSIRO/BODC/CSIO/JMA).
   - The CDOM-populated float count is sensible given the ~46% fleet-coverage
     figure in `pab/argo/BGC_Argo_Coverage_Report.md` (687 of 2,924 GDAC BGC
     floats carry CDOM, vs 1,490 CHLA / 1,473 BBP700).
   - Pre-existing fields (e.g., `chla`, `bbp700` mixed-layer means, matchup
     counts) are unchanged from before the pass.
   Report the verification numbers in the Reports section below and log your
   work. If any count is materially off, stop and raise it in Q&A — do not
   proceed to Task 5.

5. **Update the user docs.** Update `docs/db_schema.rst` and
   `docs/argo_ingestion.rst` for the new fields and the v4 schema. Do NOT
   update `docs/design/PAB_implementation.md` here — per C5, the
   implementation record is updated at the end of the analysis pass
   (`claude_prompts/chl_cdom_prompt_2.md`), after the ingested data has proved
   usable. Log your work.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
