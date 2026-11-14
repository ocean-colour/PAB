# Build v2.1: re-fit with the nadir/zenith-normalized geometry

## Goals

Re-fit every v2 BING matchup with the forward model evaluated at the geometry
that the PACE L2 AOP `Rrs` is **actually normalized to**:
**(θ_s, θ_v, Δφ) = (0, 0, 0)**, with the inelastic (Raman and Chl
fluorescence) `Ed` taken at θ_s = 0. The result is stamped
**`pab_version = "2.1"`**.

Why. NASA's l2gen runs with `brdf_opt = 7` (Morel f/Q plus Fresnel on the
sensor and solar paths), so the distributed `Rrs` is an exact-normalized
reflectance for a zenith sun and a nadir view. v2.0 and v2.0.1 instead passed
each pixel's *observed* L1B angles to `robust_hybrid`. Measured on 300 real v2
pixel geometries, the forward model then predicts a median of about 5–10 %
more `Rrs` for the same IOPs. The 5–95 % range is roughly 0.93–1.29, and the
error is correlated with geometry. The expected result of the fix is
`b_bp(700)` higher by about 5–10 % on median, plus the removal of a ±15 %
geometry-driven scatter. A side benefit: (0, 0, 0) lies **inside** the
emulator's trained domain (`cos_theta_s ∈ [0.5, 1]`,
`cos_theta_v = cos_dphi = 1`), so the "hybrid applied off-nadir, never
validated" caveat goes away.

Source of the decision: `papers/bbp/prompts/analysis.md`, under Q&A /
Viewing angle (findings 1–5; JXP's answers Q1 = fit at (0, 0, 0), Q2 =
θ_s = 0 for the inelastic terms) and Q&A / Raman correction. The second
established that the AOP `Rrs` is **not** Raman-corrected, so keeping BING's
Raman term on is correct.

## Claude

### Skills

- **`batch-fit-argo`**: the parallel-fit and checkpointing pattern.
- **`run-bing-fit`**, **`inelastic-rrs`**: the per-spectrum fit and the
  `rt_dict` inelastic flags.
- **`diagnose-mcmc`**, **`debug-priors`**: if anything changes in chain
  behaviour at the new geometry.

### Working agreements

- **Git is handled by JXP.** Run no state-changing git commands. JXP creates
  the working branch before Task 1. Read-only `git status` / `git diff` /
  `git log` are fine.
- **Python only.** Use the `ocean14` env, and call
  **`/home/xavier/miniconda3/envs/ocean14/bin/python`** directly, because
  `conda activate ocean14` in Claude's shell still resolves `python` to
  `os_313`.
- **Explicit `--db` every time**: `$PAB_DATA_DIR/v2/pab.db`. Set
  **`PAB_DATA_DIR=$PAB_DATA_DIR/v2`** for any command that writes chains, or
  they land in the root `fit_chains/` (lesson from Prompt 1).
- **`v1/pab.db` is frozen.** It is `chmod a-w`, sha `09de0a6d…f978273`.
  Open it only read-only (`create=False` or a read-only URI `ATTACH`).
- **Never modify the 2.0 or 2.0.1 rows.** 2.1 adds new rows (`fit_id …_v2.1`)
  under the design's provenance rule. Before any write to the live v2 DB,
  make a dated, sha-verified copy (the O6 discipline:
  `v2/pab_pre_v21_<date>.db`), and record row counts and checksums of the
  2.0 and 2.0.1 `fits` / `fit_results` before and after.
- **Safety run first, on a scratch DB copy.** Do a `--dry-run`, then a
  2-matchup real fit, before touching the live DB (the O6 pattern).
- **Confirm outward-facing steps with JXP** before running them: S3 uploads,
  `AIOcean` backups, Nautilus jobs, and anything published.
- `PYTHONWARNINGS=ignore` for fit runs (robust's `DomainWarning` spam). At
  (0, 0, 0) the view-geometry breach disappears, but the `B_p` breach remains
  on most fits.
- **Questions go in the Q&A section of this file**, never chat-only.

## Context

Read before Task 1:

- `papers/bbp/prompts/analysis.md`: Q&A / Viewing angle and Q&A / Raman
  correction, the physics and the evidence.
- `HOWTO.md`: §3 (the fit stage, `--matchups-csv`, `--replay-chains`) and
  §5b (how the 2.0.1 re-fit was run and published).
- `claude_prompts/v2/run_full_inelastic.md`: the v2 plan (two-DB layout,
  provenance rules, gate pattern).
- `claude_prompts/v2/report_improvements.md`: Outliers O5–O9, covering the
  2.0.1 configuration, the replay seam, the patch overlay, and the site
  rebuild and publish. 2.1 reuses most of that machinery.
- `versions/v2/high_bbp_outliers.md`, Appendix C: the replay re-fit as
  actually executed (commands, timings, checks).
- `versions/v2/ztt_slice.md`: the emulator domain and why the hybrid was
  never valid off-nadir.

### Code seams (verified 2026-11-14)

| What | Where | Note |
|---|---|---|
| Fit-time geometry | `pab/fit/run.py:212` `obs_geometry(theta_s, theta_v, dphi)` | builds `ObsGeometry` from the stored L1B angles |
| Gathered angles | `pab/fit/run.py:~782` (`_gather_fit_input`), `:~797` `_geometry_or_none` | reads `matchup_pixels.theta_s/theta_v/dphi` |
| Strict no-geometry skip (R3) | `pab/fit/run.py:~1011` | `requires_geometry(config)` is true for every robust backend |
| Inelastic `Ed` | `pab/fit/run.py:234` `set_inelastic_Ed(models, geom, rt_dict)` → `robust.rt.ed.Ed(geom.theta_s, …)` | L23 anchors 0/30/60°, so **θ_s = 0 is an anchor and needs no interpolation** |
| Diagnostics | `pab/fit/run.py:700` `_fit_diagnostics(…, geom=)` | χ²/AIC/BIC with the robust forward model |
| Figure reconstruction | `pab/plotting/fit_fig.py:62` `_geometry_from_row` → `obs_geometry` | **reads the pixel angles back**, so it must learn the fit's geometry mode or 2.1 figures will be drawn at the wrong geometry |
| Config | `pab/fit/models.py` `FitConfig` (+ `.v1()`, `.v2_0()`) | 2.0.1 ceilings are the current defaults |
| Replay | `pab/fit/replay.py` `spectrum_from_chains(root, version="2.0")` | bit-identical 2.0 input spectrum, no granule opened |
| Patch overlay | `pab/metrics/compare.py` `version_family` / `overlay_patch` | `"2.1"` is a **base** version, not a patch: the newest family becomes `("2.1", [])` |
| Version stamp | `pab/config.py` `pab_version = "2.0.1"`; `setup.py` `2.0.1` | |

### Measured facts this prompt starts from

- **v2 DB** (`$PAB_DATA_DIR/v2/pab.db`, schema v5): 15,976 matchups;
  **15,971 BING 2.0** fits (15,827 LM `success`), **51 BING 2.0.1**
  re-fits, 15,976 NASA_GIOP 1.1. All AOP granules are **V3_2**, which is
  after NASA's fix of the cross-scan BRDF azimuth bug (V3 release notes).
  Five matchups have no 2.0 fit, and 50 pixels have no geometry.
- **Chains**: `$PAB_DATA_DIR/v2/fit_chains/` holds all **15,971 `_v2.0.npz`**
  and **51 `_v2.0.1.npz`** files (19 GB). Every 2.0 fit is replayable on the
  workstation.
- **2.0 fit config**: 400–700 nm, 10k steps / 1k burn / 16 walkers, free
  `B_p` [0.004, 0.05], `phi_C = 0.02`, Raman + Chl-fl on, CDOM-fl off.
- **Cost**: the 2.0.1 replay ran at a **median 198 s CPU/fit** on the
  workstation (`--jobs 8`, O6). The workstation has **24 cores and 755 GB
  RAM**. 15,971 × ~200–250 s ÷ 20 workers ≈ **45–55 h** wall time.
- **Expected direction** (analysis.md, Viewing-angle finding 3; ZTT and
  hybrid, synthetic IOPs): `Rrs(obs)/Rrs(0,0,0)` has a median of 1.06–1.12
  at 440 nm and 1.03–1.10 at 700 nm, so **expect `bbp700(2.1)/bbp700(2.0)`
  ≈ 1.05–1.10 on median**, rising with θ_v and θ_s. A ratio *below* 1 on
  median would mean something other than geometry is acting. Stop and look.
- Test baseline at 2.0.1: **494 passed, 1 skipped**; `ruff check pab` clean.

## Prompts

1. Read this file. JXP has answered the questions in Q&A / Round 1. Fold the
   answers into the Plan, then execute **Task 1**. Use Opus 5.5. Log your
   work.
2. Execute **Task 2** (the slice and the gate). Stop for JXP's review. Use
   Opus 5.5. Log your work.
3. JXP has reviewed the slice. Execute **Task 3** (the full re-fit). Use
   Opus 5.5. Log your work.
4. Execute **Task 4** (figures, report, write-up). Use Opus 5.5. Log your
   work.
5. Execute **Task 5** (publish, backup, close-out). Use Opus 5.5. Log your
   work.

## Plan

*Drafted 2026-11-14. It assumes the recommendation on every question in
Q&A / Round 1. Revise after the answers.*

### 1. What changes, and what does not

| | 2.0.1 (current) | **2.1** |
|---|---|---|
| Forward-model geometry | observed L1B (θ_s, θ_v, Δφ) per pixel | **(0, 0, 0)** for every pixel |
| Inelastic `Ed` | L23 `Ed(θ_s observed)` | **L23 `Ed(0°)`** |
| Spectrum | 2.0 granule read (2.0.1: replayed) | **replayed from the 2.0 chain NPZ** (V2) |
| Priors | ceilings 0.1 / 10 / 10 m⁻¹ | same (the 2.0.1 default) |
| Backend / inelastic / window / MCMC | `robust_hybrid`, Raman + Chl-fl, 400–700, 10k/1k/16, free `B_p` | **unchanged** |
| `on_out_of_domain` | `"warn"` | `"warn"` (V11) |
| L1B angles on `matchup_pixels` | used by the fit | **kept as metadata and QA** (glint, θ_v cuts), not used by the fit |

So 2.0.1 → 2.1 differs by the geometry and its `Ed`, and by nothing else.
The 15,920 non-runaway fits also pick up the ceilings, but O6 showed that
the ceilings never bind a physical posterior.

### 2. Code (Task 1)

| # | Change | Where |
|---|---|---|
| a | `FitConfig.geometry_mode: str = "normalized"`, with values `"observed"` / `"normalized"`. `FitConfig.v2_0()` and `FitConfig.v1()` pin `"observed"` (v1 is moot under Gordon). Add **`FitConfig.v2_0_1()`** (ceilings + `"observed"`) so every published release has a frozen constructor. | `pab/fit/models.py` |
| b | A single resolver, `fit_geometry(config, theta_s, theta_v, dphi)`. It returns `ObsGeometry(0, 0, 0)` under `"normalized"` and `obs_geometry(...)` under `"observed"`. Use it in `_geometry_or_none`, the fit path, `_fit_diagnostics`, and `set_inelastic_Ed` (automatic, since that reads `geom.theta_s`). | `pab/fit/run.py` |
| c | **Provenance, schema v6**: `fits.geom_mode TEXT`. `'observed'` / `'normalized'`; NULL on legacy rows means observed for robust fits (the forward migration pattern of v2–v5). `_config_from_row` reads it back. (V4) | `pab/db/schema.py`, `pab/fit/run.py` |
| d | **Reconstruction**: `fit_fig._geometry_from_row` and `reconstruct_fit` dispatch on the row's `geom_mode`, so a 2.1 figure is drawn at (0, 0, 0) and a 2.0 figure is still drawn at its observed angles. | `pab/plotting/fit_fig.py` |
| e | **R3 under `"normalized"`** (V5): the geometry is fixed by the product definition, so a pixel without L1B angles is **not** refused. `requires_geometry` splits into "the backend needs an `ObsGeometry`" (still true) and "the pixel needs L1B angles" (only under `"observed"`). | `pab/fit/run.py` |
| f | `pab_version = "2.1"` with a docstring entry; `setup.py` → `2.1.0`. `make_fit_id` already appends `_v2.1`. | `pab/config.py`, `setup.py` |
| g | **Report**: confirm that `version_family` makes 2.1 the headline on the v2 DB, `("2.1", [])`, and that `--compare-db v1` now yields a 1.0-vs-2.1 section. Fix any hard-coded "2.0" wording the rebuild exposes. Optional per V8: a 2.0-vs-2.1 comparison. | `pab/metrics/compare.py`, `pab/report/rst.py` |
| h | **Tests**: the resolver (normalized → (0,0,0); observed → passthrough); `Ed` called at 0°; the v6 migration on a v5 copy; `geom_mode` round-trip into `reconstruct_fit`; the frozen constructors; the normalized-mode fit of a pixel with NULL angles is not refused; a toy robust fit under `importorskip("robust")`. `ruff` clean. | `pab/tests/` |
| i | Docs: `HOWTO.md` (§3 fit defaults; a new §5c on the 2.1 re-fit), `docs/` schema page (v6 column), and a note in BING's `robust_hybrid` docstring that PAB now evaluates it at nadir (the old off-nadir caveat is moot for PAB). | docs |

**End-of-task check** (no DB writes): re-fit ~5 cached matchups
under `FitConfig()` (2.1) and `FitConfig.v2_0_1()` on a scratch DB, and
confirm three things: the 2.1 forward model is called with (0, 0, 0); the
2.0.1 config reproduces the stored 2.0.1/2.0 posteriors to MCMC noise; and
the `bbp700` ratio has the expected sign.

### 3. The gate (Task 2): a geometry-stratified slice

- **Selection** (V7): **200 matchups**, stratified 50 per θ_v band (<25°,
  25–35°, 35–45°, >45°) and spread across basins and seasons. Include the
  50 of `ztt_slice` (re-used for comparability) and ~10 of the 51 2.0.1
  re-fits. Write the selection to `versions/v2.1/slice_200.csv`.
- **Run** on a scratch copy of the v2 DB, `--replay-chains`, `--jobs 20`.
  Measure s/fit from a few dozen fits in, never from the first ten.
- **Report** in `versions/v2.1/geometry_rerun.md` (new):
  - The `bbp700(2.1)/bbp700(2.0 or 2.0.1)` distribution, overall and per
    θ_v band, against θ_s, and against the analysis.md prediction.
  - The same for `a_ph(440)`, Chl, `A_dg` and `B_p`.
  - χ²_red and acceptance against 2.0.
  - The `DomainWarning` breach mix (the view features should be gone).
  - LM `success` rate and failures.
  - Against the float, a quick look at whether δ = (PACE − Argo)/PACE moves
    as predicted.
- **Pause triggers** (V7): median `bbp700` ratio outside **[0.98, 1.20]**;
  failure rate > 2 %; median s/fit > 300 s; or any χ² or acceptance change
  JXP finds implausible. **Stop for JXP's review in every case.**

### 4. The full re-fit (Task 3)

- Where (V6): the **workstation**. Replay needs no granule, the DB and
  chains are already local, no image rebuild is needed, and there is a
  single custodian. About 2 days at `--jobs 20`, run in the background with
  a tee'd log in `$PAB_DATA_DIR/v2/logs/` and progress checked at intervals.
  Nautilus is the fallback (Plan §6).
- Selection: the **15,971 matchups with a 2.0 NPZ** (V3), via
  `--matchups-csv versions/v2.1/refit_all.csv`. This guards against a
  silent all-matchup run.
- Idempotent and resumable (keyed on the `_v2.1` `fit_id`). A crash
  resumes where it left off.
- Before: a dated DB copy, counts and checksums. After: 2.0 and 2.0.1 rows
  byte-identical; `integrity_check`; 15,971 rows at 2.1 (minus failures,
  listed).

### 5. Figures, report, write-up (Task 4)

- `--stage figure --figure-version 2.1` for every 2.1 fit (V9). Scenes are
  untouched; the v1 scene paths still apply.
- Rebuild `report_site/` with 2.1 as the headline and
  `--compare-db $PAB_DATA_DIR/v1/pab.db`.
- Finish `versions/v2.1/geometry_rerun.md` with the full-population numbers.
  Flag for the paper that the bias numbers in
  `papers/bbp/bias_discussion_draft.md` were computed on 2.0 or 2.0.1 and
  must be refreshed from 2.1 (that refresh is a separate paper prompt, not
  this doc).

### 6. Publish and close-out (Task 5); each step confirmed with JXP

- `s3://pab/v2/pab.db` and `v2/matchup_summary.*` updated in place (V10).
  The DB is the same file with more rows.
- Dated backup to `AIOcean:PAB/pab_v2_<date>.db`.
- Verify that the v1 sha is unchanged.
- JXP pushes `report_site/` (RTD).
- Close-out log entries here and in HOWTO §5c.

*Nautilus fallback (only if V6 = B):* image `pab:2.1.0` with the baked
`PAB` SHA checked against the commit; stage the v2 DB and the 2.0 chains
(they are already at `/data/v2/fit_chains/`); the DB-local wrapper from
`nautilus/v2_fit_job.yaml` with `--replay-chains /data/v2/fit_chains`;
`PYTHONWARNINGS=ignore`; tee to the PVC; return the DB and the new chains to
the workstation afterwards.

## Tasks

### Task 1: code, tests, local check

Implement Plan §2 a–i in the order f → a → b → e → c → d → g → h → i. Run
`pytest pab/tests -q` and `ruff check pab`, and report the new baseline. Then
do the §2 end-of-task check on a **scratch** DB copy with
`PAB_DATA_DIR` set to scratch. Report the measured `bbp700` ratios for those
matchups. No writes to the live v2 DB.

### Task 2: the slice and the gate (STOP for review)

Build `versions/v2.1/slice_200.csv` per Plan §3 and run it on a scratch copy
of the v2 DB with `--replay-chains $PAB_DATA_DIR/v2/fit_chains`. Write the
§3 report into `versions/v2.1/geometry_rerun.md`, with figures in
`versions/v2.1/`. Put the go/no-go recommendation, and any new questions, in
Q&A / Round 2. **Do not start Task 3.**

### Task 3: the full re-fit

After JXP's go: run the pre-flight, the dated copy and the checksums, then
the safety run (dry-run plus 2 matchups on scratch), then the full 15,971
on the live v2 DB per Plan §4. Monitor it. When it finishes, verify and
list any failures with their reasons. Re-try failures once, and leave the
rest listed for JXP.

### Task 4: figures, report, write-up

Plan §5. Rebuild the site locally and check it renders (summary headline
reads 2.1; the comparison section is 1.0 vs 2.1; the 2.1 fit figures link
correctly). Complete `versions/v2.1/geometry_rerun.md`.

### Task 5: publish, backup, close-out

Plan §6, each outward step confirmed with JXP first. Update `HOWTO.md` §5c
and `docs/`, and log.

## Q&A

### Round 1

*Answer inline under each **Your answer:**. Each question carries my
recommendation, and the Plan assumes it.*

**V1: Which database holds the 2.1 fits?**
- **A (recommended).** The live **v2 DB**, as new rows (`fit_id …_v2.1`),
  exactly as 2.0.1 was added. It has the same matchups, pixels and NASA-GIOP
  rows, and the report's `version_family` then picks 2.1 as the headline
  with no new plumbing. 2.0 and 2.0.1 stay untouched beside it.
- **B.** A new `v2.1/pab.db` split from v2 (a third DB, a new S3 prefix,
  and `--compare-db` plumbing for 2.0-vs-2.1).

**Your answer:**

**V2: Spectrum source.** Replay each pixel's spectrum from its **2.0 chain
NPZ** (`--replay-chains`, the 2.0.1 seam), so 2.0 → 2.1 differs only by
geometry. The alternative is to re-read the granules, which picks up any
NASA reprocessing since the 2.0 run, costs ~25 GB+ of downloads, and
confounds the comparison. *(My recommendation: replay.)*

**Your answer:**

**V3: Scope.** Re-fit the **15,971 matchups that have a 2.0 fit**. The 51
runaways are included: they replay their 2.0 spectrum under the 2.1 config,
which keeps the ceilings, so they do not run away again. The **5 matchups
with no 2.0 fit** have no NPZ to replay. Under `"normalized"` geometry they
*could* be fitted from the granule, since L1B angles are no longer needed,
but that means a granule download and a mixed `rrs_source`. Leave them out
of 2.1? *(My recommendation: leave them out and list them in the write-up.)*

**Your answer:**

**V4: Provenance of the geometry.** Add **`fits.geom_mode`** (schema v6;
`'observed'` / `'normalized'`; NULL on legacy rows means observed). Without
it, the only record that a fit used (0, 0, 0) is the version number, and
`reconstruct_fit` / `fit_fig` would have to infer physics from a version
string. The alternative is to imply it from `pab_version >= 2.1`, with no
migration. *(My recommendation: the explicit column.)*

**Your answer:**

**V5: R3 (strict "no geometry → no fit") under the normalized mode.** R3
existed so that θ_s was never *assumed*. Under `"normalized"`, the geometry
is fixed by NASA's product definition, not assumed. Proposal: in
`"normalized"` mode a pixel without L1B angles is **not** refused. The
`geometry` stage keeps running for new matchups, as QA metadata. In
`"observed"` mode, R3 stays exactly as it is. *(My recommendation: yes. It
doesn't affect this run, where every replayed pixel has angles, but it
matters for future granule fits.)*

**Your answer:**

**V6: Where does the full re-fit run?**
- **A (recommended).** The **workstation**: 24 cores, `--jobs 20`, ~45–55 h,
  in the background with a tee'd log. No image rebuild, no PVC staging, no
  DB round-trip; the chains and DB are already local.
- **B.** **Nautilus**: ~50 workers, ~20 h of fitting, plus a `pab:2.1.0`
  image build, DB staging, the DB-local wrapper, and bringing the DB and
  ~18 GB of new chains back.

**Your answer:**

**V7: The gate.**
- (a) A **200-matchup** slice stratified by θ_v band (50 each), including the
  `ztt_slice` 50 and ~10 of the 2.0.1 re-fits.
- (b) Pause triggers: median `bbp700(2.1)/bbp700(2.0)` outside
  **[0.98, 1.20]**; failures > 2 %; median s/fit > 300 s; or any χ² or
  acceptance change you find implausible.
- (c) You review before Task 3 in every case.

*(My recommendation: (a)–(c) as written.)*

**Your answer:**

**V8: Report presentation.** On the v2 DB, 2.1 becomes the site's headline
automatically, and the existing comparison section becomes **1.0 vs 2.1**
via `--compare-db`.
- **A (recommended).** The 2.0-vs-2.1 change is documented in
  `versions/v2.1/geometry_rerun.md`, with one sentence and a link on the
  report's summary page. No new report code.
- **B.** A second comparison section in the report (2.0 vs 2.1, same DB),
  which needs a version-pair gatherer inside one store.
- **C.** Swap the comparison section to 2.0 vs 2.1 and drop 1.0 vs 2.x.

**Your answer:**

**V9: Figures.** Re-render the **fit figures for all ~15,971 2.1 fits**.
They encode the fitted physics, and the gallery and tap-through would
otherwise show 2.0 fits. The earlier estimate was ~9 h at 16 workers. Scenes
stay as they are, still the v1 ones per R7. *(My recommendation: yes.)*

**Your answer:**

**V10: Publishing.** Update `s3://pab/v2/pab.db` and `v2/matchup_summary.*`
**in place** (the same DB, with 2.1 rows added), plus a dated `AIOcean`
backup and the RTD site rebuild. The alternative is a new `s3://pab/v2.1/`
prefix. *(My recommendation: in place under `v2/`, consistent with V1 = A
and with how 2.0.1 was published.)*

**Your answer:**

**V11: `on_out_of_domain`.** At (0, 0, 0) the view-geometry breach that
made `"ztt"` mean "pure ZTT everywhere" (O8) disappears. The `B_p` breach
remains: 86 % of 2.0 posterior medians lie outside the emulator's trained
`B_p` range [0.0103, 0.018]. Keep **`"warn"`**, i.e. the hybrid everywhere,
as in 2.0 (Q&A/Outliers 12 = A), so 2.0 → 2.1 isolates the geometry. The
alternative is to revisit the policy now. *(My recommendation: keep
`"warn"`. Retraining the emulator over the `B_p` prior range is the real fix
and belongs to the RoB repo.)*

**Your answer:**

**V12: Version naming.** Use `pab_version = "2.1"` (fit ids `…_v2.1`),
package `2.1.0`, and add `FitConfig.v2_0_1()` as a frozen constructor
alongside `.v1()` / `.v2_0()`. It is a minor bump, not a patch, because the
physics changes for every fit, so it is a new **base** version and not an
overlay on 2.0. *(My recommendation: as stated.)*

**Your answer:**

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-11-14 (Prompt doc written: the v2.1 normalized-geometry re-fit planned; twelve questions posed)

Written from `papers/bbp/prompts/analysis.md` RT prompt 3, with Claude Opus
5.5. Read JXP's answers in Q&A / Raman correction and Q&A / Viewing angle:
fit at (0, 0, 0) under the name v2.1; θ_s = 0 for the inelastic terms; the
Raman term stays on, because the AOP `Rrs` is not Raman-corrected; no 2×2
test. Checked the current state read-only. The v2 DB is schema v5 with
15,971 BING 2.0 fits, 51 BING 2.0.1 fits, 15,976 NASA_GIOP 1.1 fits, and
all-V3_2 granules. All 15,971 + 51 chain NPZs are local (19 GB), so the
whole re-fit can replay on the workstation without a granule. The
production window is 400–700 nm (not 720). Five matchups have no 2.0 fit.
The workstation has 24 cores and 755 GB. The L23 `Ed` table anchors at
0/30/60°, so θ_s = 0 needs no interpolation. Traced the code seams where
geometry enters: `obs_geometry` in the fit, `_fit_diagnostics`,
`set_inelastic_Ed`, `fit_fig._geometry_from_row` / `reconstruct_fit`, and
the R3 skip. The figure reconstruction is the easy one to miss: it reads the
pixel's angles back, so it needs the fit's geometry mode. Checked that `2.1`
is a base version under `compare.version_family`, so it becomes the report
headline on the v2 DB without new code. Wrote Goals, Context (code seams,
measured facts, the expected 1.05–1.10 `bbp700` ratio), a Plan (code a–i,
gate, full run, report, publish), five Tasks with a hard stop after the
slice, and questions V1–V12. No code or DB changes.
