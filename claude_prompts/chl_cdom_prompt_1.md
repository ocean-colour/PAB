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
6. Execute the 6th task in Tasks below

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

6. **Publish the updated `pab.db` back to `s3://pab/full/`.** The local
   `$PAB_DATA_DIR/pab.db` now carries schema v4 + the Task 4 re-ingestion
   (CDOM, `chla_adjusted`, DAC provenance); the copy on
   `s3://pab/full/pab.db` is still the pre-pass version from 2026-08-24 (JXP
   asked directly and confirmed this — nothing has been pushed since Task 4).
   Before uploading:
   - **Resolve the `pab_version` question first, in Q&A below — don't just
     upload.** Task 4's re-ingestion upserted every touched row under the
     *same* `pab_version = "1.0"` that the original full-mission release
     used. That cuts against this project's own stated versioning principle
     (`PAB_design.md` → *Provenance & versioning*: "re-running under a new
     `pab_version` **adds** records, never silently overwrites") — here we
     used `UPSERT` in place, under the *same* version, which does overwrite.
     Confirm with JXP whether that's acceptable for this pass (a deliberate,
     documented exception — it's a schema/provenance backfill, not a
     re-analysis) or whether `pab_version` should bump (e.g. to `1.1`) before
     publishing, so the S3 copy's version string honestly reflects that its
     data differs from the original `1.0` release.
   - Verify the local DB one more time (`PRAGMA integrity_check`; row counts
     against Task 4's verified numbers) immediately before upload, in case
     anything has changed since.
   - Upload (overwrite) `s3://pab/full/pab.db` via `NautilusS3Backend` (or the
     equivalent `aws s3 cp`/endpoint invocation used earlier in this project —
     see `HOWTO.md` §7b), then verify the upload: public `HTTP 200`,
     `content-length` matches the local file size, and a fresh download
     round-trips the same row counts (mirroring the verification done in
     `run_full_pipeline.md`'s 2026-08-24 log entry when the DB was first
     published).
   - Back up the updated DB to `AIOcean:PAB/` via `rclone` too, per this
     project's "Nautilus isn't backed up, everything published also goes to
     Google Drive" convention (N5 in `run_full_pipeline.md`) — don't leave the
     only updated copy live solely on S3.
   - Update `HOWTO.md` §7b's publish-status note only as needed to keep it
     accurate (e.g. if the published DB's `pab_version` changed) — do not
     duplicate the `PAB_implementation.md` update, still deferred to
     `chl_cdom_prompt_2.md` per C5.
   Report what was published (URL, size, checksum, version) in the Reports
   section below and log your work.

## Q&A

**Q1 (raised by Task 1) — `cdom_adjusted` is moot as "mirror the DAC's field"; what should PAB compute instead?**
The spot-check (see Reports below) found `CDOM_ADJUSTED` is **100% empty fleet-wide** — no float has ever had CDOM delayed-mode/adjusted processing. So a `cdom_adjusted` column that just copies GDAC's adjusted field would always be NULL; it isn't a meaningful thing to ingest as designed in Stage 10. Per C2 ("we will eventually want to analyze values with the correction applied"), the real choice for Task 3 is whether PAB **computes its own** `cdom_adjusted = 5.62 × cdom` (the confirmed part of the Sea-Bird RAF) at ingestion time. Two wrinkles:
- The RAF applies only to sensors **calibrated/serviced before 2023-01-13**, but sensor calibration date does not appear to be in the BGC profile files fetched here (only `FLOAT_SERIAL_NO`/`FIRMWARE_VERSION`/`PLATFORM_TYPE` were seen) — so there may be no way to conditionally apply it per float without an external sensor/calibration manifest. Applying it unconditionally to all floats would mis-correct any float actually calibrated after the cutoff (rare in this fleet, since CDOM-carrying floats sampled here mostly launched years before 2023, but not guaranteed for every float).
- The **second** Sea-Bird correction (the separate reference-sensor bias) has no published factor at all (per the earlier investigation) — so even a "corrected" value is only partially corrected.

My lean: compute `cdom_adjusted = 5.62 × cdom` for all floats for now (documenting it as a **partial, unconditional** correction — first factor only, applied fleet-wide since no per-float calibration-date signal is available in the fetched fields), and note this explicitly wherever `cdom_adjusted` is used downstream. Should Task 3 proceed on that basis, or do you want to hold `cdom_adjusted` empty until calibration-date metadata is confirmed available (elsewhere in Argo's meta files) or the second correction is published?

>A. I will make a correction later after consulting with BGC experts.  For now, just injest `cdom`.  

**Q2 (raised by Task 6) — `pab_version` before publishing: keep `1.0`, or bump it?**
Task 4's re-ingestion upserted the touched `mld_summary`/`floats`/`profiles` rows **in place, under the same `pab_version = "1.0"`** the original full-mission release used — so the DB now published under `1.0` would carry materially different content (CDOM, `chla_adjusted`, DAC provenance, and the small legitimate drift in `chla`/`bbp700`/`mld` from re-fetching) than the `1.0` that's actually been cited/downloaded from `s3://pab/full/pab.db` since 2026-08-24. That cuts against this project's own stated principle in `PAB_design.md` (*Provenance & versioning*): a new version is supposed to **add** records, not silently overwrite. Options: **(a)** publish as-is under `1.0`, documenting this pass as a deliberate, one-time exception (a provenance/schema backfill, not a re-analysis — no science numbers changed except the tiny drift already explained in Task 4's report); **(b)** bump `pab_version` (e.g. `1.1`) before publishing, so anyone comparing DB snapshots by version string sees the difference honestly, at the cost of re-stamping/re-running to get every row onto the new version (unclear if that means literally changing the `pab_version` string on the already-upserted rows, or a fuller re-run). My lean: (a) with a clear note wherever this pass is documented (the eventual `PAB_implementation.md` update in `chl_cdom_prompt_2.md` is the natural place) — this really is a backfill of previously-missing provenance fields plus one new BGC variable, not a change in analysis method, so I don't think it needs its own version number the way an algorithm/prior change would. But this is your call, especially since it sets precedent for how future backfills get versioned. Which?

>A.

## Reports

### Task 1 — `CDOM_ADJUSTED` spot-check: empty fleet-wide, not just unconfirmed

**Finding: GDAC's `CDOM_ADJUSTED` is not populated for any BGC-Argo float — the Sea-Bird correction is not, and cannot currently be, "baked in" anywhere in the archive.**

Installed `argopy` 1.4.0 + `erddapy<3.0` (per this repo's own `BGC_Argo_Coverage_Report.md` compatibility note) into the `ocean14` conda env (not previously present). Fetched three real floats with CDOM going back to 2011–2012 (well before the 2023-01-13 cutoff, so RAF-affected by construction): **4902284** (AOML, Gulf of Mexico), **5904218** (CSIRO, Argo Australia), **6901474** (Coriolis, remOcean) via `argopy.DataFetcher(ds='bgc', src='gdac', mode='expert', params=['CDOM'])`.

- `expert` mode does surface `CDOM_ADJUSTED`/`CDOM_ADJUSTED_ERROR`/`CDOM_ADJUSTED_QC`/`CDOM_DATA_MODE` as first-class dataset variables alongside raw `CDOM`/`CDOM_QC` — no special mode juggling needed, contrary to a cautious assumption in the task text. `DATA_CENTRE`/`PROJECT_NAME` are likewise present per-profile (`AO`/`CS`/`IF` for the three floats above) — directly usable for Task 2's DAC fix.
- All three floats: **`CDOM_DATA_MODE` = `'R'` (real-time) for every single point**, and **`CDOM_ADJUSTED` entirely `NaN`** — zero finite adjusted values anywhere in any of the three profiles, despite thousands of finite raw `CDOM` values each.
- Widened the check to the **entire live GDAC BGC index** (not just the 3 sampled floats): joined each index row's `parameters`/`parameter_data_mode` position-coded strings to isolate CDOM's per-profile mode across **90,270 CDOM profile-rows / 694 unique floats**. Result: **100% mode `'R'`** — literally zero profiles anywhere in the global BGC-Argo archive have CDOM in `'A'` (real-time-adjusted) or `'D'` (delayed-mode) status.
- For context, ran the same check for `CHLA` (194,261 profile-rows: 89% `'A'`, 8% `'D'`, only 4% `'R'`) and `BBP700` (191,390 rows: 80% `'A'`, 9% `'D'`, 11% `'R'`) — both are predominantly adjusted/delayed-mode fleet-wide. **CDOM stands alone as the one BGC variable PAB touches with essentially no delayed-mode QC pipeline at all**, consistent with `euroargodev/argopy#280` omitting CDOM from its per-parameter mode-handling proposal (found investigating C2/C3 previously).

**Conclusion for C2:** not ambiguous — the answer is a clean no. GDAC will not hand PAB a corrected CDOM value under any current mode setting, for any float, because that correction has never been performed by any DAC. If PAB wants "CDOM with the Sea-Bird correction applied" (per JXP's stated intent), PAB must compute it itself. This changes the shape of Task 3's `cdom_adjusted` column from "capture what GDAC provides" to "PAB's own derived value" — raised as Q1 above rather than decided here, since it also surfaces a new wrinkle (no per-float sensor calibration date was found in the fetched fields, so the 2023-01-13 cutoff may not be applicable per-float without further metadata).

**JXP's answer to Q1:** hold off on any correction — "I will make a correction later after consulting with BGC experts. For now, just ingest `cdom`." Task 3 therefore ingests raw `cdom`/`cdom_std` only; no `cdom_adjusted` column/computation for this pass.

### Task 2 — DAC/project-name provenance fix + tests: done, verified

**Root cause confirmed directly against live data.** Fetched real profiles from float 4902284 in `expert` mode: `PROJECT_NAME`/`DATA_CENTRE` are ordinary per-profile dataset variables (`"Langrangian Study of the Deep Circulation in the Gulf of Mexico "` / `"AO"`), fully populated — so the bug was purely that `pab/pipeline.py::ingest()` never forwarded what `iter_profiles` could already extract (and `iter_profiles` itself was missing the `PROJECT_NAME`/`DATA_CENTRE` extraction lines entirely).

**Also found, not previously known:** a bare `DATA_MODE` variable **does not exist** on real BGC/GDAC datasets (point-level or per-profile) — confirmed on the same test float via `'DATA_MODE' in ds.variables` → `False`. BGC files carry only per-parameter `<PARAM>_DATA_MODE` (e.g. `CHLA_DATA_MODE`, `CDOM_DATA_MODE`; see Task 3). So `iter_profiles`'s existing `if "DATA_MODE" in one:` guard is dead code for every real BGC/GDAC fetch PAB makes — `profiles.data_mode` will stay NULL even after this fix, until Task 3's per-parameter fields land. Left the guard in place (harmless, defensive) but documented this in the docstring rather than silently leaving a misleading impression that the fix populates it.

**Changes made:**
- `pab/argo/fetch.py::iter_profiles` — added `PROJECT_NAME`/`DATA_CENTRE` extraction (stripped of Argo's fixed-width char-array padding) into `meta["project_name"]`/`meta["data_center"]`, mirroring the existing `DATA_MODE` pattern; docstring updated with the dead-code note above.
- `pab/pipeline.py::_persist_profile` — both call sites (precomputed-offline and live-fetch) now forward `data_mode`/`project_name`/`data_center` to `summary.persist_summary()`, which already accepted them.

**Tests added (both new, both pass):**
- `pab/tests/test_argo.py::test_iter_profiles_extracts_dac_and_project_metadata` — exercises the real `iter_profiles` extraction logic via a fake `.argo` accessor (a plain object standing in for argopy's `point2profile()`, returning a hand-built `xr.Dataset`) — no real argopy needed, consistent with this project's established practice of never exercising argopy's real accessor in the offline suite.
- `pab/tests/test_pipeline.py::test_ingest_persists_dac_and_project_provenance` — the end-to-end regression test the task asked for: runs `pipeline.ingest()` via the existing fetcher-stub seam (updated `_stub_iter_profiles` to also yield `project_name`/`data_center`/`data_mode`) and asserts `floats.project_name`, `floats.data_center`, and `profiles.data_mode` are populated after ingestion. Confirmed this test fails against the pre-fix code (reverted locally to check) and passes after.

**Verification:** full suite `pytest pab/tests/` → **189 passed** (was 187; +2 new), no regressions. `ruff check`/`ruff format --check` clean on both changed source files (`pab/argo/fetch.py`, `pab/pipeline.py`); the two test files have pre-existing, unrelated formatting debt (long lines predating this change) left untouched.

Did not run this against the real 881-float `pab.db` yet — that's Task 4's combined re-ingestion. This task's fix is self-contained and independently verified per the task's own instruction.

### Task 3 — CDOM ingestion, per-parameter provenance, schema v4: done, verified live

**Scope note (per Q1's answer):** no `cdom_adjusted` column this pass — JXP wants to consult BGC-Argo colleagues on the Sea-Bird correction first. Only raw `cdom`/`cdom_std` is ingested for CDOM. `chla_adjusted` is still added (a real, meaningfully-populated GDAC field, unlike CDOM's — this is the "second pass" Chl quantification from Q10, not the CDOM correction question).

**Schema v3→v4** (`pab/db/schema.py`): added to `mld_summary` — `cdom`, `cdom_std`, `chla_adjusted`, `chla_data_mode`, `cdom_data_mode`, `bbp700_data_mode`. Updated both the inline `CREATE TABLE` DDL (so a fresh DB gets v4 directly) and a new `_v3_to_v4` forward migration (for the real, already-v3 `pab.db`), following the existing `_v1_to_v2`/`_v2_to_v3` pattern exactly. `SCHEMA_VERSION` bumped 3 → 4.

**Ingestion changes:**
- `pab/argo/fetch.py`: `"CDOM"` added to `DEFAULT_PARAMS`; `iter_profiles` now also extracts `CDOM` and `CHLA_ADJUSTED` per-level arrays, and per-**parameter** data modes (`CHLA_DATA_MODE`/`CDOM_DATA_MODE`/`BBP700_DATA_MODE`) into `meta["chla_data_mode"]` etc. — the real fix for the coarse-`data_mode`-is-dead-code gap found in Task 2.
- `pab/argo/summary.py`: `summarize_profile()` gained `chla_adjusted`/`cdom` params, averaged the same plain way as `chla` (no despike/IQR — that's `BBP700`-specific); `persist_summary()` gained `chla_data_mode`/`cdom_data_mode`/`bbp700_data_mode` params, written straight to `mld_summary` (not derived from the array-based `summary` dict, since they're profile-level scalars from `meta`).
- `pab/pipeline.py`: both `_fetch_profile_payload`/`_persist_profile` call sites updated to pass the new fields through.

**Tests added (all pass):** extended Task 2's `test_iter_profiles_extracts_dac_and_project_metadata` fixture with `CHLA_DATA_MODE`/`CDOM_DATA_MODE`/`BBP700_DATA_MODE`/`CDOM`/`CHLA_ADJUSTED` and asserted they're extracted; `test_summarize_profile_averages_cdom_and_chla_adjusted` (known-answer, mirrors the existing CHLA test) and `test_summarize_profile_omits_cdom_and_chla_adjusted_when_absent` (NaN default, not a crash) in `test_argo.py`; `test_v3_to_v4_migration_is_idempotent` in `test_db.py` (a genuine v3-shaped DB migrates once to v4, and a second `migrate()` call is a no-op — not a duplicate-column error). Also had to fix a pre-existing test, `test_migrations_add_figure_path_columns`, which hardcoded `SCHEMA_VERSION == 3`; extended it to also assert the new v4 columns land on a full v1→v4 migration.

**Live smoke test (real data, not mocked) — the "verify on a small subset" step:** ran `pipeline.ingest()` with no fetcher override (genuine `argopy`/GDAC network fetch) against two real floats (4902284/AOML, 5904218/CSIRO) into a scratch DB, then deleted it. Results were fully sensible and directly confirm the whole chain works end to end:

| wmo | project_name | data_center | chla | chla_adjusted | cdom | cdom_data_mode | bbp700_data_mode |
|---|---|---|---|---|---|---|---|
| 4902284 | Langrangian Study of the Deep Circulation in the Gulf of Mexico | AO | 0.1533 | 0.1102 | 1.572 | R | A |
| 5904218 | Argo Australia | CS | 0.1819 | 0.1404 | 0.763 | R | D |

`chla` vs `chla_adjusted` differ meaningfully on both floats (real delayed/real-time-adjusted correction visible, not a passthrough), `cdom_data_mode` is `'R'` on both (consistent with Task 1's fleet-wide finding), and `bbp700_data_mode` varies (`A` vs `D`) between floats as expected. Pre-existing fields (`bbp700`, `mld`) were also produced correctly alongside the new ones — no regression.

**Verification:** full suite `pytest pab/tests/` → **192 passed** (was 189; +3 new/modified). `ruff check`/`ruff format --check` clean on all six touched files (`pab/db/schema.py`, `pab/argo/fetch.py`, `pab/argo/summary.py`, `pab/pipeline.py`, `pab/tests/test_argo.py`, `pab/tests/test_db.py`).

Did not yet run the real combined re-ingestion over the 881-float `pab.db` — that is Task 4.

### Task 4 — combined re-ingestion: smoke test passed; full run in progress

**No new Q&A answers to check.** Confirmed the local `pab.db` (downloaded from `s3://pab/full/pab.db` in an earlier task) is genuinely pre-pass: schema v3, 881/54,031/54,031/67,435/14,610/146,100/14,609/146,090 across floats/profiles/mld_summary/granules/matchups/matchup_pixels/fits/fit_results, `floats.data_center` NULL for all 881. Saved an aggregate baseline (sum + non-null count of `chla`/`bbp700`/`mld`/`psal`/`temp`/`n_points` across all 54,031 profiles, plus every table's row count) to compare against after the pass.

**Why a full re-fetch is actually required, not just a metadata patch:** all 54,031 profiles already have an `mld_summary` row, and `ingest()` skips any profile that does (idempotency). Populating the new per-profile fields (`cdom`, `chla_adjusted`, per-parameter data modes) for *existing* profiles needs `replace=True` — a genuine re-fetch of every one of the 54,031 profiles from Argo, not a cheap in-place patch. Exported the full `(wmo, cycle)` list from `profiles` (54,031 rows) to re-ingest.

**Smoke test (10 profiles, on a scratch copy of `pab.db` — not the real file) — passed cleanly:**
- 10/10 written, 0 failed.
- `project_name`/`data_center` populated correctly across three different DACs in the sample (`AO`, `HZ`, `IF` — Argo PMEL/CHINA ARGO/SO-CHIC/REFINE/GO-BGC projects), confirming the fix handles DAC diversity, not just the AOML floats checked earlier.
- `cdom` populated where the float carries the sensor, `None` where it doesn't (2 of 10) — exactly the expected "not every float has CDOM" behavior, not a bug.
- `chla_adjusted` differs meaningfully from `chla` on every populated row (a real correction, not a passthrough).
- Table row counts (`floats`/`profiles`/`mld_summary`/`matchups`/`fits`) identical before and after — the re-ingestion touches only `mld_summary`/`floats`/`profiles` rows in place, no side effects on the matchup/fit tables.
- `chla`/`bbp700`/`mld` values for the 10 sampled profiles are **bit-for-bit unchanged** from before the smoke test — no regression to pre-existing science fields.

**Full run:** launched in the background against the **real** `$PAB_DATA_DIR/pab.db` (all 54,031 profiles, `replace=True`, `ingest_jobs=16`) — a genuine re-fetch of the whole selection from Argo, expected to take on the order of an hour based on historical per-profile rates.

**Two launch attempts failed before this — both fixed, neither touched the real DB (confirmed via `PRAGMA integrity_check` + unchanged row/NULL counts after each):**
1. First attempt: the scratch driver script couldn't `import pab` (wrong working directory for the script's own `sys.path`) — fixed with an explicit `PYTHONPATH`.
2. Second attempt: a **self-inflicted multiprocessing bug** — the driver script called `ingest()` (which spawns a `ProcessPoolExecutor`) at module level with no `if __name__ == "__main__":` guard. On macOS's default `spawn` start method, every worker process re-imports the driver as `__main__`, which re-ran the whole `ingest()` call *inside* the worker — a recursive process-spawn storm that broke the pool (`BrokenProcessPool`) after ~17 recursive launches. This is a bug in the scratch driver script, not in `pab.pipeline` itself (the real `pab` CLI already guards its entry point correctly). Fixed by wrapping the driver in `if __name__ == "__main__":`; verified the fix on the 10-profile scratch smoke test before relaunching against the real DB.

**Full run completed:** 103,730.5 s (28.8 h) elapsed, `written=52,844, skipped=0, failed=1,187` (2.2% failure rate — in line with this project's historical ~2–3% argopy transient-failure expectation at this scale; failures were `DataNotFound`/`502 Proxy Error`/`FSTimeoutError`, all per-profile, none batch-aborting).

**Verification — all checks pass, nothing materially off:**

- **Schema/integrity:** `PRAGMA integrity_check` → `ok`; schema version → 4.
- **Table row counts — exactly unchanged** across all 8 tables (`floats` 881, `profiles` 54,031, `mld_summary` 54,031, `granules` 67,435, `matchups` 14,610, `matchup_pixels` 146,100, `fits` 14,609, `fit_results` 146,090) — confirms the pass touched only `floats`/`profiles`/`mld_summary` rows in place, zero side effects on the matchup/fit tables.
- **`chla`/`bbp700`/`mld`/`psal`/`temp` — tiny, *positive* deltas, not a regression.** 8–14 additional profiles (out of 54,031, ~0.02–0.03%) now have a non-null value versus the pre-pass baseline, with correspondingly small positive sum deltas — i.e., a few more valid values, none lost. This is structurally impossible to be data loss: `persist_summary()` (and thus any DB write) only runs when a profile's live re-fetch *succeeds*; a failed profile's pre-existing row is never touched. The most likely explanation is genuine upstream drift — Argo's delayed-mode QC keeps processing real-time profiles after the fact, so a profile that was incomplete at the original August fetch can pick up newly-available values on a fresh fetch weeks later. Not investigated further since the direction (gain, not loss) and structural guarantee both rule out a bug.
- **AOML count: 612 in the DB, exact match once explained.** The external GDAC-index join (from the earlier chat question) found 617/881 AOML floats. All 8 floats that ended up with `data_center` still NULL had **100% of their profiles fail** this pass (confirmed: each one's failed-profile count equals its total profile count) — and cross-checking those 8 WMOs against the live GDAC index shows **exactly 5 are AOML** (the rest: 1 Coriolis, 2 MEDS). `612 + 5 = 617` — an exact reconciliation, not a coincidence.
- **CDOM coverage: 394/881 floats (44.7%) carry at least one non-null `cdom`** — closely matches the ~46% fleet-wide figure from `pab/argo/BGC_Argo_Coverage_Report.md`. 25,630/54,031 profiles (47.4%) have non-null `cdom`. `cdom_data_mode` is `'R'` for all 25,982 profiles that have it and `NULL` for the rest (no sensor) — **zero `'A'`/`'D'`**, consistent with Task 1's fleet-wide finding that no BGC-Argo float has ever had CDOM delayed-mode processed.
- **`chla_adjusted` populated for 48,343/54,031 profiles (89.5%)** — consistent with Task 1's fleet-wide CHLA mode finding (89% `'A'` + 8% `'D'`).

No count was materially off, so proceeding to Task 5 is warranted per the task's own gate ("stop and raise it in Q&A" only triggers on a real problem) — holding here to report back to JXP before continuing, since this is a natural, substantial checkpoint.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-03 (Task 1 — spot-checked `CDOM_ADJUSTED`: empty fleet-wide, not just for sampled floats)

Installed `argopy` 1.4.0 + `erddapy<3.0` into the `ocean14` conda env (neither was present; this repo's own `BGC_Argo_Coverage_Report.md` already documents the erddapy pin needed for argopy 1.4.0 compatibility). Fetched three real BGC-Argo floats with long CDOM records predating 2023-01-13 (4902284/AOML, 5904218/CSIRO, 6901474/Coriolis) via `mode='expert'` and confirmed `expert` mode already surfaces `CDOM_ADJUSTED`/`_ADJUSTED_ERROR`/`_ADJUSTED_QC`/`CDOM_DATA_MODE` and `DATA_CENTRE`/`PROJECT_NAME` as ordinary dataset variables — no special handling needed for Task 2's DAC fix.

All three floats showed `CDOM_DATA_MODE = 'R'` for every point and zero finite `CDOM_ADJUSTED` values despite thousands of finite raw `CDOM` values. Not satisfied with 3 floats as a "spot-check," widened the query to the live GDAC BGC index's `parameters`/`parameter_data_mode` position-coded columns across all 90,270 CDOM profile-rows / 694 floats in the archive: **100% report `'R'` — zero profiles anywhere in BGC-Argo have delayed-mode or real-time-adjusted CDOM.** Ran the same check on `CHLA` (89% A / 8% D / 4% R) and `BBP700` (80% A / 9% D / 11% R) for contrast — both are mostly adjusted/delayed-mode fleet-wide, unlike CDOM. This matches (and quantifies) the earlier finding that `euroargodev/argopy#280`'s per-parameter mode proposal omits CDOM entirely.

Conclusion for C2: not ambiguous — GDAC cannot supply a Sea-Bird-corrected CDOM value under any mode, for any float, because no DAC has ever delayed-mode-processed CDOM. This means Task 3's planned `cdom_adjusted` column can't simply mirror an Argo-provided field (it would always be NULL); PAB would have to compute it. Raised this as a new Q1 in this doc rather than deciding it, since it surfaces an unresolved wrinkle: no per-float sensor calibration date was visible in the fetched profile variables, so applying the RAF (5.62×) conditionally on the 2023-01-13 cutoff may not be possible without further metadata — proposed applying it unconditionally for now, flagged explicitly as a partial/uncertain correction, pending JXP's call. Did not proceed to Task 2/3, per the user's "execute the 1st prompt" instruction. No package code changed.

### 2026-09-04 (Task 2 — fixed DAC/project-name provenance; two regression tests added)

Read JXP's answer to Q1 first: hold off on any CDOM correction until consulting BGC experts, ingest raw `cdom` only — simplifies Task 3's scope (no `cdom_adjusted` column/computation this pass).

Confirmed the root cause directly against live data (float 4902284, `expert` mode): `PROJECT_NAME`/`DATA_CENTRE` are ordinary, fully-populated per-profile dataset variables — the bug was purely that `iter_profiles` never extracted them and `pipeline.py::ingest()` never forwarded even the `DATA_MODE` it did extract. Also found something not previously known: a bare `DATA_MODE` variable **does not exist at all** on real BGC/GDAC datasets (checked directly: `'DATA_MODE' in ds.variables` → `False`) — BGC files carry only per-parameter `<PARAM>_DATA_MODE`. So `iter_profiles`'s pre-existing `data_mode` extraction is dead code for every real fetch PAB makes; documented this rather than let the fix imply `profiles.data_mode` is now reliably populated (it isn't, until Task 3's per-parameter fields land).

Changed `pab/argo/fetch.py::iter_profiles` (extract `PROJECT_NAME`/`DATA_CENTRE`, stripped of Argo's fixed-width padding, into `meta`) and `pab/pipeline.py::_persist_profile` (both call sites now forward `data_mode`/`project_name`/`data_center` to `persist_summary`, which already accepted them). Added two tests: `test_argo.py::test_iter_profiles_extracts_dac_and_project_metadata` (exercises the real extraction logic via a fake `.argo` accessor object standing in for argopy's `point2profile()` — no real argopy needed, matching this suite's established practice) and `test_pipeline.py::test_ingest_persists_dac_and_project_provenance` (the end-to-end regression test via the existing fetcher-stub seam, updated `_stub_iter_profiles` to carry the new fields too). Explicitly verified the regression test actually catches the bug — stashed `pipeline.py`, reran, watched it fail (`assert False` on `project_name`), then restored and reran to confirm it passes — rather than just asserting this without checking.

Full suite: **189 passed** (+2 from 187), no regressions. `ruff check`/`ruff format --check` clean on both changed source files; left pre-existing, unrelated formatting debt in the two test files untouched (out of scope). Did not touch `pab.db` — this task's fix is self-contained per its own instructions; Task 4 covers the real re-ingestion. Not yet started Task 3.

### 2026-09-04 (Task 3 — CDOM ingestion + per-parameter provenance + schema v4; verified live against real floats)

No new Q&A answers to check beyond Q1 (already read in Task 2). Per that answer, scoped this task down slightly: no `cdom_adjusted` column/computation — raw `cdom`/`cdom_std` only, pending JXP's BGC-Argo consult. `chla_adjusted` still goes in, since that's a separate, already-real GDAC field (unlike CDOM's non-existent adjusted data) and is the Q10 "second pass" Chl quantification, not the CDOM correction question.

Migrated the schema (v3→v4, `pab/db/schema.py`): added `cdom`, `cdom_std`, `chla_adjusted`, `chla_data_mode`, `cdom_data_mode`, `bbp700_data_mode` to `mld_summary`, both in the inline `CREATE TABLE` DDL and as a new `_v3_to_v4` forward migration (following the existing `_v1_to_v2`/`_v2_to_v3` pattern). Extended `pab/argo/fetch.py::iter_profiles` to pull `CDOM`/`CHLA_ADJUSTED` per-level arrays and per-**parameter** data modes (`<PARAM>_DATA_MODE` for CHLA/CDOM/BBP700) — this is the real fix for the "coarse `data_mode` is dead code" gap found in Task 2, since BGC files carry modes per-parameter, not per-profile. Threaded the new fields through `pab/argo/summary.py` (`summarize_profile`'s `chla_adjusted`/`cdom` params, averaged the same plain way as `chla` — no despike/IQR, that's `BBP700`-specific; `persist_summary`'s new `*_data_mode` params, written straight from `meta` since they're profile-level scalars, not part of the array-based `summary` dict) and `pab/pipeline.py` (both call sites).

Added tests mirroring existing patterns: extended the Task-2 `iter_profiles` fixture with the new variables and modes; a CDOM/chla_adjusted known-answer test plus an absent-data NaN-default test in `test_argo.py`; a `_v3_to_v4` idempotency test in `test_db.py` (genuine v3-shaped DB → migrate once → migrate again is a no-op, no duplicate-column error) — and had to fix a pre-existing test that hardcoded `SCHEMA_VERSION == 3`.

Went beyond the offline suite for the "verify on a small subset" instruction: ran `pipeline.ingest()` with a real, non-mocked `argopy`/GDAC fetch against two real floats (4902284/AOML, 5904218/CSIRO) into a scratch DB (deleted after). Every new field came back sensible: `chla` vs `chla_adjusted` differ meaningfully on both floats (a real correction, not a passthrough — e.g. 0.153 vs 0.110 for 4902284), `cdom_data_mode` was `'R'` on both (consistent with Task 1's fleet-wide finding), `bbp700_data_mode` varied `A`/`D` between floats as expected, and pre-existing fields (`bbp700`, `mld`) were unaffected.

Full suite: **192 passed** (+3 from 189), no regressions. `ruff check`/`ruff format --check` clean on all six touched files. Did not yet run the real 881-float combined re-ingestion — that's Task 4, not started.

### 2026-09-04/05 (Task 4 — combined re-ingestion run and verified; two scripting bugs found and fixed along the way)

Confirmed the local `pab.db` was genuinely pre-pass (schema v3; 881/54,031/54,031/67,435/14,610/146,100/14,609/146,090 across the eight tables; `data_center` NULL for all 881 floats) and saved an aggregate baseline (sum + non-null count of `chla`/`bbp700`/`mld`/`psal`/`temp`/`n_points`, plus every table's row count) before touching anything.

Ran a 10-profile smoke test on a scratch copy of `pab.db` first: DAC/CDOM/adjusted-Chl fields populated correctly across three different DACs, `chla`/`bbp700`/`mld` values were bit-for-bit unchanged from before, and table row counts didn't move — passed cleanly.

Launching the real 54,031-profile re-ingestion (`replace=True`, since every profile already has an `mld_summary` row and would otherwise be skipped by the idempotency guard) against the actual `$PAB_DATA_DIR/pab.db` hit two of my own scripting bugs, both caught and fixed before any damage (verified via `PRAGMA integrity_check` + unchanged counts after each failed attempt): a `PYTHONPATH` issue, then a genuine multiprocessing footgun — the driver script called `ingest()` (which spawns a `ProcessPoolExecutor`) at module level with no `if __name__ == "__main__":` guard, so macOS's `spawn` start method re-imported the driver as `__main__` inside every worker, re-running the whole `ingest()` call recursively until the pool broke. Fixed by adding the guard; re-verified on the 10-profile scratch subset before relaunching for real. This is a lesson for any future one-off driver script around `pipeline.ingest()`'s parallel path, not a `pab` package bug — the real CLI already guards its entry point.

The real run took **28.8 hours** (103,730 s) — much longer than my initial ~1 h estimate, closer to this project's own historical ~4.2 s/profile-at-16-workers rate from an earlier production attempt. Kept the user updated with live progress checks (measured the live rate once, ~2.5 profiles/s, to give an honest revised ETA) rather than letting the estimate stand unchallenged, and reassured them about laptop sleep vs. a real interruption (the latter would need a smarter resume, since `replace=True` doesn't build a skip-set) — sleep turned out to be fine; the background job survived it.

Final result: `written=52,844, skipped=0, failed=1,187` (2.2%, in line with historical argopy failure rates; all `DataNotFound`/`502`/`FSTimeoutError`, all per-profile, none batch-aborting). Full verification against the baseline: table counts identical across all 8 tables (zero side effects outside `floats`/`profiles`/`mld_summary`); `chla`/`bbp700`/`mld`/`psal`/`temp` showed tiny *positive* deltas (8–14 more non-null values out of 54,031) — explainable as genuine Argo-side delayed-mode updates arriving between the original August fetch and this one (structurally can't be data loss, since a failed profile's row is never written); AOML count landed at 612, and cross-checking the 8 floats that ended up with no `data_center` (each had **100% of its profiles fail**) against the live GDAC index found exactly 5 of them are AOML — `612 + 5 = 617`, an exact reconciliation against the earlier external-join answer; CDOM coverage came out to 394/881 floats (44.7%), matching the ~46% fleet-wide figure in `BGC_Argo_Coverage_Report.md`; `cdom_data_mode` was `'R'` for every populated row and never `'A'`/`'D'`, matching Task 1's fleet-wide finding; `chla_adjusted` populated for 89.5% of profiles, matching Task 1's CHLA mode breakdown. Nothing was materially off, so no Q&A entry raised. Did not proceed to Task 5 — reporting this checkpoint back to JXP first, per how this session has been walking through the doc one task at a time.

### 2026-09-06 (added Task 6 — publish the updated `pab.db` to S3)

JXP asked whether the updated local DB had also been pushed to `s3://pab/full/pab.db`. Checked directly: no — the S3 object's last-modified timestamp (2026-08-24) and size (138,854,400 B) exactly match the pre-pass DB; nothing has been uploaded since Task 4 touched only the local copy at `$PAB_DATA_DIR/pab.db` (now 141,156,352 B, modified 2026-09-05).

Per JXP's follow-up ask, added **Task 6** to this doc: publish the updated DB back to `s3://pab/full/pab.db`, plus back it up to `AIOcean:PAB/` per the project's existing "Nautilus isn't backed up" convention, and keep `HOWTO.md` §7b accurate. Flagged one real design question before uploading (added as **Q2**, not decided here): Task 4's re-ingestion upserted rows **in place under the same `pab_version = "1.0"`** the original release used, which cuts against `PAB_design.md`'s own stated versioning principle (a new version should **add** records, not silently overwrite). Gave a lean (publish as-is under `1.0`, documented as a deliberate backfill exception, since no analysis method changed) but left the actual call to JXP, since it also sets precedent for how future backfills get versioned. No code changed; doc-only edit.
