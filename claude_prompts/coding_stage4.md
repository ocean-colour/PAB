# Coding up PAB — Stage 4 (Matchup engine)

## Goals

Implement **Stage 4** of the coding plan: the **matchup engine** that joins the
two data sides built in Stages 2–3 (BGC-Argo mixed-layer summaries ↔ PACE
granules) into **matchup records**. This is the first stage where the Argo and
PACE halves meet, so it depends on `pab.argo`, `pab.pace`, and `pab.db`.

We continue to be guided by the design document `docs/design/PAB_design.md` and
the coding plan `docs/design/PAB_coding_plan.md`, and we record what we build in
`docs/design/PAB_implementation.md`.

## Claude

### Skills

Consider using the skills in `.claude/skills/` (e.g. `critical-partner`,
`code-review`) as helpful.

### Working agreements (unchanged from Stages 0–3)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written; do **not** copy
  the one-off `bing/papers/biomass/Analysis` scripts.

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md`, especially *Data → Matchup, use, and
  analysis* and *Cloud access* (the 5×5-pixel box and tight time window per
  Bisson et al.).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 4* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current
  state; update it at the close of this stage).
- **Distilled references** — `docs/context.md` §3 (Bisson matchup recipe: 5×5
  unflagged box, neighbours within ~3 h, a `dtime` window) and §5 (PACE
  nearest-pixel extraction).
- **Existing PAB seams this stage builds on:**
  - `pab.db` — the `matchups` and `matchup_pixels` tables already exist in the
    schema (`matchup_id` PK; `profile_id`/`granule_id` FKs; `distance_km`,
    `dtime_hours`, `n_spectra`; pixel rows with `ix/iy/lat/lon/distance/rank/
    flagged`). Write through `Store.upsert*` (idempotent).
  - `pab.pace.cloud.open_granule` (canonical granule dataset; mockable via the
    `opener=` seam) and `pab.pace.extract.{nearest_valid_pixels,
    extract_matchup_spectra, haversine_km}`.
  - `pab.pace.discover` — the `granules` table is the candidate set.
  - `pab.argo` — `profiles` / `mld_summary` rows are the qualifying floats.

## Prompts

1. Read this doc.  Execute the 1st task in the Pre Stage 4 section below.

2. Read this doc.  Execute the 2nd task in the "Stage 4" section below.
3. Read this doc.  Execute the 3rd task in the "Stage 4" section below.
4. Read this doc.  Execute the 4th task in the "Stage 4" section below.

5. Read this doc.  Execute the 1st task in the "Pull Request" section below.
6. Read this doc.  Execute the 2nd task in the "Pull Request" section below.
7. Read this doc.  Execute the 3rd task in the "Pull Request" section below.

8. Read this doc.  Execute the 1st task in the "Stage 5" section below.

## Pre Stage 4

1. Read this doc.  For development for here on out, let us work with a set of 10 Argo profiles, a subset of which will have match-ups with PACE.  Here are 3 profiles I know that will match-up, named by Argo WMO number and profile number (my numbering, so there is room for error here):

    - 7902226,4
    - 7902136,7

If you have any questions, write them in the Q&A section below.  If you have any requests, write them in the Requests section below.

2.  Great!  I have answered the questions and requests.  Please continue working on this step.  If you have any questions, write them in the Q&A section below.  If you have any requests, write them in the Requests section below.


### Q&A

**Q (Claude, 2026-06-20):** You wrote "3 profiles" but listed only **two**
(`7902226,4` and `7902136,7`). Is there a missing third seed matchup? I built
the dev set with the two given. — *JXP:*

Only two. :)

**Q (Claude, 2026-06-20):** Cycle-number confirmation. Treating the second value
as the **GDAC cycle number**, your seeds resolve to:
- `7902226` cycle 4 → 2025-02-08 18:16 UTC, **27.22 °N, 46.02 °W** (N. Atlantic
  subtropical gyre).
- `7902136` cycle 7 → 2025-01-15 06:08 UTC, **3.68 °N, 137.24 °W** (equatorial
  Pacific).

Both are in the PACE era. Do these positions/times look like the matchups you
had in mind? (You flagged the numbering as approximate.) — *JXP:*

The one I meant for `7902226` cycle 4 has a timestamp of 2025-02-18T20:26:59.  
The other one has 2025-01-25T13:05:59. Let's continue to work on this until we converge.  

**Converged (Claude, 2026-06-20):** Your timestamps pin to index **cycles 5 and
8** (your numbering ran one low):
- `2025-02-18T20:26:59` → `7902226` **cycle 5** (index 2025-02-18 20:27:49,
  27.48 °N, 46.22 °W).
- `2025-01-25T13:05:59` → `7902136` **cycle 8** (index 2025-01-25 13:01:02,
  3.95 °N, 136.72 °W).

Dates match to the day; the ~1–5 min offsets are just different time fields
(index `date` vs. the profile `JULD` your source quotes). Manifest updated to
these two seeds.

**Q (Claude, 2026-06-20):** For the other 8 profiles I chose a spread of ~7
cycles apart across each float's 2025 track (so the engine sees both hits and
misses). Cycles: `7902226` = 11, 18, 25, 32; `7902136` = 14, 21, 28, 35. Happy
with this, or would you prefer specific cycles / a different float for variety?
— *JXP:*

I would prefer you choose 8 additional ones at random, but within the PACE era.

**Done (Claude, 2026-06-20):** Drew 8 at random (4 per float) from each float's
PACE-era cycles (on/after 2024-03-05). Reproducible: NumPy `default_rng(20260620)`.
`7902226` → 21, 27, 42, 51; `7902136` → 30, 42, 46, 47. Manifest updated.

### Requests

- Built the development profile set as a committed manifest:
  [`data/dev_profiles.csv`](../data/dev_profiles.csv) (10 rows) with
  [`data/README.md`](../data/README.md). Both seed floats (`7902226`,
  `7902136`) verified present in the GDAC synthetic-profile index (53 and 57
  profiles, all PACE-era). Note: the Ifremer BGC **ERDDAP** measurement fetch
  was intermittently timing out / 404-ing today, so positions/times here come
  from the synthetic-profile **index** (offline-of-ERDDAP); actual measurement
  arrays will be pulled (and cached under `PAB_DATA_DIR`) when Stage 4 runs.

## Stage 4

### Tasks

1. Read this doc and the context files. Implement Stage 4 (below). If you have
   questions, write them in the Q&A section.  If you have any requests, write them in the Requests section.  Log your work in the Logs section.

2. I wish to dig in further on one of the profiles: (7902226, 4).  Please generate a Jupyter Notebook named `docs/nb/05_matchup_7902226_4.ipynb` that will allow me to dig in further.  It should:

    - Fetch the profile from the GDAC index using argopy.
    - Fetch the granule from the PACE index using earthaccess.
    - Match the profile to the granule using the matchup engine.
    - Plot the profile and the granule.
    - Plot Rrs spectrum from the closest pixel.

3. When running the Notebook, the 3rd cell fails with an error:

```
Error: 408, message='', url='https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats-synthetic-BGC.nc?bbp700,bbp700_adjusted,bbp700_adjusted_error,bbp700_adjusted_qc,bbp700_qc,chla,chla_adjusted,chla_adjusted_error,chla_adjusted_qc,chla_qc,config_mission_number,cycle_number,direction,latitude,longitude,platform_number,position_qc,pres,pres_adjusted,pres_adjusted_error,pres_adjusted_qc,pres_qc,psal,psal_adjusted,psal_adjusted_error,psal_adjusted_qc,psal_qc,temp,temp_adjusted,temp_adjusted_error,temp_adjusted_qc,temp_qc,time,time_qc&platform_number=~%227902226%22&cycle_number=~%225%22&latitude!=NaN&longitude!=NaN&distinct()&orderBy(%22time,pres%22)'

```

Please advise in the Reporting section below.

4. Ok, the Notebook works now and looks great.  I wish to add a cell that over-plots the Rrs spectrum kindly provided by Rorbert Frouin.  For that, you will need to use the `bing/papers/biomass/Analysis/py/jr_utils.py` module and the `load_jr_data` function to load the JR data.  Please generate the code for that cell and put in the Extra cell section below.  The figure should show the PACE Rrs spectrum and the JR Rrs spectrum on the same plot, both with error regions.  The JR Rrs spectrum should be in red.

### Extra cell

**Done (Claude, 2026-06-21).** Added as **section 9** of
`docs/nb/05_matchup_7902226_4.ipynb` (appended after the closest-pixel spectrum).
It *imports* (does not copy) `jr_utils.load_jr_data`/`extract_rrs` from
`bing/papers/biomass/Analysis/py`, selects the JR row nearest the float (its
row 6 — `PACE_OCI.20250219T155847…`, PACE pixel 0.4 km from the float, time
2025-02-18T20:26:59, an exact match for this seed), and over-plots the PACE L2
AOP closest-pixel spectrum (blue, ±`Rrs_unc`) against the JR/Frouin spectrum
(red, ±`Rrs_std`):

```python
import os, sys
import numpy as np
import matplotlib.pyplot as plt

# Robert Frouin ("JR") provided Rrs spectra derived from PACE *L1B* with his
# atmospheric correction. We *import* the biomass-paper helper (we do not copy
# it); point BING_ANALYSIS_PY at it if it lives elsewhere.
BING_ANALYSIS_PY = os.environ.get(
    "BING_ANALYSIS_PY",
    os.path.expanduser("~/Oceanography/python/bing/papers/biomass/Analysis/py"),
)
if BING_ANALYSIS_PY not in sys.path:
    sys.path.insert(0, BING_ANALYSIS_PY)
import jr_utils as jr

# Pick the JR row nearest the float (the table's trailing rows are comments,
# dropped by requiring finite PACE_lat/lon).
jr_df = jr.load_jr_data()
valid = jr_df.dropna(subset=["PACE_lat", "PACE_lon"])
cos = np.cos(np.radians(lat))
d_km = np.sqrt((valid["PACE_lat"] - lat) ** 2
               + ((valid["PACE_lon"] - lon) * cos) ** 2) * 111.0
jr_idx = int(d_km.idxmin())
jr_rrs = jr.extract_rrs(jr_idx)
wl_jr, m_jr, s_jr = jr_rrs["wavelengths"], jr_rrs["Rrs_mean"], jr_rrs["Rrs_std"]
print(f"JR row {jr_idx}: {jr_df.loc[jr_idx, 'AOP_file']} "
      f"({d_km.loc[jr_idx]:.2f} km from float)")

# PACE L2 AOP closest pixel (from section 8)
wl_p, rrs_p, unc_p = closest["wavelength"], closest["Rrs"], closest["Rrs_unc"]

fig, ax = plt.subplots(figsize=(8, 4.5))
# PACE L2 AOP (blue) with its Rrs_unc band
ax.plot(wl_p, rrs_p, "-", color="C0", lw=1.5, label="PACE L2 AOP (closest pixel)")
ax.fill_between(wl_p, rrs_p - unc_p, rrs_p + unc_p, color="C0", alpha=0.25)
# JR / Frouin (red) with its Rrs_std band
ax.plot(wl_jr, m_jr, "-", color="red", lw=1.5, label="JR / Frouin (L1B AC)")
ax.fill_between(wl_jr, m_jr - s_jr, m_jr + s_jr, color="red", alpha=0.25)

ax.set_xlabel("wavelength (nm)")
ax.set_ylabel("Rrs (sr$^{-1}$)")
ax.set_xlim(340, 720)
ax.set_title(f"PACE L2 AOP vs JR/Frouin Rrs  —  WMO {WMO} / cycle {CYCLE}")
ax.legend()
ax.grid(alpha=0.3)
plt.show()
```

Notes: it reuses `lat`/`lon`/`closest`/`WMO`/`CYCLE` from earlier cells, so run
the notebook top-to-bottom first. I used JR `Rrs_std` (the 3×3-window spread) as
the error band — the table also carries `Rrs_uncertainty_<λ>` columns if you
prefer the formal AC uncertainty instead.

### Reporting

**Diagnosis & fix (Claude, 2026-06-21).** The `408` is a **server-side timeout
from the Ifremer BGC ERDDAP** — the same flakiness flagged in the Pre-Stage-4
log (we have seen `FSTimeoutError`, `404`, and now `408` from that host on
different days). It is not a bug in our code: the request URL is well-formed and
the float/cycle exist. ERDDAP is simply slow/overloaded and drops the request.

I diagnosed it live and **switched the notebook to read the GDAC NetCDF
directly** (`argopy` `src="gdac"`), which fetched this profile reliably in ~9 s
in repeated tests. Along the way I found two further gotchas, now handled in the
notebook:

1. **Source.** `src="gdac"` avoids the flaky ERDDAP entirely (and matches your
   "fetch from the GDAC index" phrasing). An `api_timeout=600` is still set for
   safety.
2. **Mode.** With `gdac`, `mode="standard"`/`"research"` return **0 points**
   (`"No data left after QC filtering"`) for this profile: those modes prefer
   delayed-mode/**adjusted** fields, which do not exist yet for a *recent*
   (2025-02) real-time cycle. `mode="expert"` returns the 509 measured levels
   (`PRES`/`BBP700`/`CHLA`/`PSAL`/`TEMP` all QC=1).
3. **QC filtering.** I **dropped the blanket `fetch.filter_quality`** call in the
   notebook. In `expert` mode the dataset carries *all* BGC parameters incl.
   `NITRATE_QC` (0/3) and `PH_IN_SITU_TOTAL_QC` (3); `filter_qc(QC=[1,2])` drops
   a level if **any** parameter fails, so it emptied the dataset. The core
   variables we use are QC=1, and the summary already de-spikes / IQR-screens
   `BBP700`. (A cleaner future option: restrict `filter_qc` to the fields we
   actually use.)

With this recipe the profile loads and summarizes sensibly: **MLD = 30 m,
bbp700(ML) = 4.3×10⁻⁴ m⁻¹, chla(ML) = 0.091 mg m⁻³** (N. Atlantic gyre values).

**Caveat:** `expert` mode returns *raw* (non-adjusted) `BBP700`/`CHLA`; for a
recent real-time cycle that is the only data available, but CHLA in particular
carries the usual real-time uncertainty (no delayed-mode factor-2 / NPQ
correction yet).

**Recommendation / question for JXP:** given the recurring ERDDAP outages, shall
I switch PAB's default Argo source from `erddap` to `gdac` in
`pab/argo/fetch.py` (with `expert` mode for recent profiles)? It would make the
whole pipeline more robust, but changes the project default, so I left it as-is
pending your call. — *JXP:*

### Q&A

**Note (Claude, 2026-06-21):** You named the dig-in profile `(7902226, 4)`; per
our Pre-Stage-4 convergence that is **GDAC cycle 5** (timestamp 2025-02-18T20:27,
the seed recorded in `data/dev_profiles.csv`). I kept your requested filename
(`05_matchup_7902226_4.ipynb`) but set `CYCLE = 5` inside, with a note at the
top. Change `CYCLE` if you actually meant index cycle 4 (2025-02-08).

### Requests

- The new notebook `docs/nb/05_matchup_7902226_4.ipynb` is **live end-to-end**
  (argopy + earthaccess) and I could not execute it here — this workstation has
  no `~/.netrc` / Earthdata Login, so `earthaccess.login()` and the granule read
  fail. It is committed **without** cell outputs; please run it where Earthdata
  credentials exist (ideally in-region `us-west-2` for the fast S3 read). It is
  excluded from the Sphinx build for the same reason (cannot build offline-safe).

## Stage 4 — Matchup engine

Here is some additional context

### Scope

For each qualifying BGC-Argo profile (one with a mixed-layer summary), find the
PACE granule(s) whose footprint covers the float position **and** whose
acquisition time is within a configurable window of the profile time; for the
selected granule, extract the ~10 nearest **unflagged** `Rrs` spectra around the
float and write the matchup record linking **float ↔ granule ↔ pixels**.

Concretely:

- **Spatial match** — the float `(lat, lon)` falls within (or near) a granule's
  footprint; at the pixel level, restrict to a small box (e.g. 5×5 pixels per
  Bisson) and select the nearest unflagged pixels via the existing
  `pab.pace.extract` functions.
- **Temporal match** — `|profile_time − granule_time|` within a configurable
  `dtime` (design/Bisson suggest a tight window, e.g. ≤ 1 day → tighten toward
  ~3 h as data allow). Record `dtime_hours`.
- **Selection rule** — when several granules qualify, pick the closest in
  space/time with valid `Rrs` (document the tie-break). Record `distance_km`
  (float → nearest pixel) and `n_spectra`.
- **Deterministic `matchup_id`** — encode profile + granule (e.g.
  `"{wmo}_{cycle}_{granule_id}"`) so re-runs upsert idempotently.
- **Idempotent + resumable** — skip/replace already-written matchups by
  `matchup_id`; write through `pab.db.store.Store`.

Keep the engine **source-agnostic and testable**: accept granule datasets via
the `pab.pace.cloud.open_granule` seam (so tests inject synthetic granules and
no network/S3 is touched), and keep the geometry/time logic in pure functions
that operate on arrays/values.

### Deliverables

- `pab.matchup.engine` — the matching + record-writing logic (and any small
  helper module if warranted). Update `pab/matchup/__init__.py` to export the
  public API.
- New rows in `matchups` and `matchup_pixels` via the DB layer (no schema change
  expected; if one is needed, bump `pab.db.schema.SCHEMA_VERSION` and add a
  migration).

### Tests (offline; `pytest`)

- **Spatial/temporal matching on synthetic geometry/time** — a profile vs. one
  or more synthetic granules: correct granule selected; distance computed;
  **time-window edge** behaviour (just inside vs. just outside the window).
- **Flagged-pixel exclusion** — the nearest pixel is flagged → it is not
  selected (reuse the `pab.pace` flag machinery / synthetic granule fixture).
- **Record links persisted** — `matchups` + `matchup_pixels` rows written with
  correct FKs, `n_spectra`, `distance_km`, `dtime_hours`; **idempotent re-run**
  produces no duplicates.
- Continue the project convention: pure functions checked with known values; the
  cloud layer mocked (inject synthetic granules via `opener=`).

### Docs

- A **matchup-criteria page** (`docs/matchup.rst`): box size, `dtime` window,
  the selection/tie-break rule, the `matchup_id` scheme, and how records link
  float ↔ granule ↔ pixels. Add it to the `index.rst` *Package* toctree and
  autodoc `pab.matchup.engine`.

### Notebook

- `docs/nb/04_matchup.ipynb` — a worked example that builds a matchup on
  **synthetic** profile + granule data (offline), shows the selected pixels and
  the written records, and ends with an **optional `RUN_LIVE`** section that
  matches a real float profile (argopy) to a discovered PACE granule
  (earthaccess). Build it executed (offline-safe), render it via `myst-nb`, and
  add it to the *Notebooks* toctree.

### Definition of done (the Stage 0–3 standard)

- `pytest` green (new Stage 4 tests included); `ruff check pab` and
  `ruff format --check pab` clean; `sphinx-build -W` succeeds.
- Google-style docstrings on every public function; provenance stamped
  (`pab_version`, `created`) on written records where applicable.
- `docs/design/PAB_implementation.md` updated: flip Stage 4 to ✅ in the status
  table, add a Stage 4 section (modules/API, key decisions, tests, docs,
  notebook), update the module index and the verification line; bump its
  version/date.
- Work logged (see below).

### Q&A

(Write any questions for JXP here; he answers inline. Do not block on interactive
prompts.)

## Pull Request

1. I have executed a Pull Request on GitHub for Stage 4.  Please review the Pull Request and post it to GitHub.

2. Make edits to the Repo to address the review comments.  If you have any questions, write them in the Q&A section below.  If you have any requests, write them in the Requests section below.

3. I have answered your question in the Q&A section.  Please make the necessary edits.

### Requests

**Addressed the PR #2 review (Claude, 2026-06-21).** Working-tree edits (not
committed — git is yours to push):

- **Fixed — missing-position guard.** `find_matchup` now raises a clear
  `ValueError` if a profile lacks `latitude`/`longitude` (was an opaque
  `TypeError` from `float(None)`), and `build_matchups` skips such profiles into
  `unmatched` rather than crashing mid-run. Added two tests
  (`test_find_matchup_requires_position`,
  `test_build_matchups_skips_profile_without_position`). Suite now **72 passed**;
  `ruff`/`sphinx -W` still clean.
- **Deferred (with rationale), not changed:**
  - *Open-every-candidate + O(profiles×granules) scan* — negligible at the
    10-profile dev scale; the real optimization is the footprint bbox pre-filter
    already documented as future work in `docs/matchup.rst`. Holding it for a
    later stage to avoid premature complexity / a WKT-parse dependency.
  - *`matchup_pixels.flagged` always 0* — correct by construction (only unflagged
    pixels are selected); already documented. No change.
- **Awaiting your call (Q&A):** switching PAB's default Argo source from
  `erddap` to `gdac` in `pab/argo/fetch.py`. Not touched pending your decision
  below.

### Q&A

**Q (Claude, 2026-06-21):** Re the recurring ERDDAP flakiness — shall I switch
the PAB default Argo source to `gdac` (with `expert` mode for recent real-time
profiles) in `pab/argo/fetch.py`, or keep `erddap` as the default and leave
`gdac` opt-in? — *JXP:*

yes, please switch to gdac.

**Done (Claude, 2026-06-21):** `pab/argo/fetch.py` `build_fetcher` default is now
`src="gdac"` (was `"erddap"`); updated the module + function docstrings (gdac
default, erddap still selectable, and the `mode="expert"` note for recent
real-time profiles). `mode` default left at `"standard"` (the science-correct
choice when delayed-mode/adjusted data exist). Verified: offline construction
test passes, and a live `fetch_profile(7902226, 5, mode="expert")` returns 509
levels via gdac. Heads-up: argopy emits `UserWarning: BGC data support with the
'gdac' data source is still in Work In Progress` — it works reliably in our
tests, just noting the upstream caveat. Suite **72 passed**, `ruff` + `sphinx -W`
clean.

## Stage 5

1. Generate a prompt doc for Stage 5.  Name it `claude_prompts/coding_stage5.md`.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-06-21 (Stage 5 — generated the Stage 5 prompt doc)

Created `claude_prompts/coding_stage5.md` (the BING fitting wrapper), mirroring
the Stage 4 doc's structure (Goals / Claude[Skills, Working agreements] /
Context / Prompts / Stage 5 [Scope, Deliverables, Tests, Docs, Notebook,
Definition of done, Q&A] / Logging / Logs).

- Grounded it in coding-plan §5 (model pair `ExpBricaud`+`Pow`, LM→MCMC,
  `nsteps≈10000`/`nburn≈1000`/16 walkers, namespaced IOP columns, NPZ chains,
  batch + idempotent) and `docs/context.md` §2 (the `bb/a` degeneracy, why
  `b_bp` is the matchup observable).
- Named the seams Stage 5 builds on: the existing `fits`/`fit_results` schema
  (long → `fit_results_wide()`), the `matchups`/`matchup_pixels` inputs, re-read
  of pixel `Rrs` via `pace.extract`/`cloud` (spectra aren't stored), and
  `package_versions()` for provenance.
- Pointed at the relevant installed skills (`run-bing-fit`, `satellite-band-prep`,
  `debug-priors`, `diagnose-mcmc`, `plot-bing-fit`, `fit-l23-spectrum`,
  `batch-fit-argo`) and reiterated "reuse `bing`, don't copy the biomass
  Analysis scripts."
- Proposed deliverables `pab.fit.{models,run,artifacts}`, a known-answer
  recovery test (synthetic `Rrs` via `calc_Rrs`, short MCMC, `importorskip`),
  `docs/fitting.rst`, and `docs/nb/06_fit.ipynb` — all to the Stage 0–4 DoD.

### 2026-06-21 (Stage 4 — switched default Argo source to GDAC)

Per JXP's Q&A answer ("yes, please switch to gdac"), changed `build_fetcher`'s
default `src` from `"erddap"` to `"gdac"` in `pab/argo/fetch.py`, with docstring
updates (module + function): gdac is the reliable default (avoids the recurring
ERDDAP 408/timeout/404), erddap stays selectable, and recent real-time profiles
need `mode="expert"` (the module's data-mode note).

- Kept `mode="standard"` as the default — the science-correct choice where
  delayed-mode/adjusted data exist; expert is opt-in per the note. The dig-in
  notebook (`05`) already sets `ARGO_MODE="expert"` explicitly, so it is
  consistent.
- Verified: `test_build_fetcher_is_bgc` still passes (gdac fetcher constructs
  offline), and a live `fetch_profile(7902226, 5, mode="expert")` returns 509
  levels. Full suite **72 passed**; `ruff` + `sphinx -W` clean.
- Noted the upstream `UserWarning` that argopy still marks BGC-over-gdac as
  "Work In Progress"; it nonetheless returns correct data quickly in our tests.

### 2026-06-21 (Stage 4 — addressed PR #2 review comments)

Made working-tree edits to address the review I posted on PR #2.

- **Concrete fix:** missing-position guard. `find_matchup` raises a clear
  `ValueError` for a profile without `latitude`/`longitude` (previously an opaque
  `TypeError` from `float(None)` at `engine.py:165`), and `build_matchups` skips
  such profiles into `unmatched` instead of crashing. Updated the docstrings
  (`Raises:` + the `unmatched` description) and added two tests. **72 passed**,
  `ruff` + `sphinx -W` clean. Bumped the implementation-record verification line
  (70→72) and the Stage 4 test description (10→12).
- **Deferred with rationale (no change):** the open-every-candidate /
  O(profiles×granules) cost is negligible at dev scale — the footprint bbox
  pre-filter is the real fix and is already logged as future work in
  `matchup.rst`; and `matchup_pixels.flagged` is correctly always 0 by
  construction.
- **Left for JXP:** the ERDDAP→GDAC default-source switch — re-asked as a Q&A
  question; `pab/argo/fetch.py` untouched.
- Did **not** post to GitHub or commit (this task was repo edits; git/push is
  JXP's). The review-response diff will be visible once he pushes.

### 2026-06-21 (Stage 4 — reviewed PR #2 and posted the review to GitHub)

JXP opened PR **#2 "Stage 4"** (`stage4` → `main`). Reviewed it and posted the
review to GitHub.

- **Scope.** The PR diff is the 14 Stage-4 files (matchup engine + tests, the
  `matchup.rst` page, the `04`/`05` notebooks, the dev manifest, `conf.py`,
  implementation record, prompt docs). My local `main` is stale, so a local
  `git diff main...stage4` over-reports (65 files); the real PR base on origin
  already carries Stages 0–3.
- **Due diligence.** Re-ran `pytest` (70 passed), `ruff check`/`format` (clean),
  `sphinx-build -W` (succeeds) on the branch before reviewing.
- **Verdict:** good to merge; no blockers. Flagged minor, non-blocking notes:
  NULL-position guard at `engine.py:165-166`; the open-every-candidate network
  cost and O(profiles×granules) candidate scan (both fine at dev scale, footprint
  pre-filter already noted as future work); and that `matchup_pixels.flagged` is
  always 0 by construction. Also reiterated the open ERDDAP→GDAC default question.
- **Posted** as a COMMENT-type review via `gh pr review 2 --comment`
  (https://github.com/ocean-colour/PAB/pull/2). Per the working agreement I did
  not merge or change branch state — only posted the requested review.

### 2026-06-20 (Pre Stage 4 — established the 10-profile development set)

Executed the first Pre Stage 4 task: pin a fixed set of 10 BGC-Argo profiles for
Stage 4+ development, seeded with JXP's two known PACE matchups.

What I did:

- **Verified the seeds.** Both WMOs are real BGC floats present in the GDAC
  `argo_synthetic-profile_index.txt` (via `argopy.ArgoIndex`): `7902226` has 53
  profiles (2025-01 → 2026-06, N. Atlantic gyre ~27 °N 46 °W) and `7902136` has
  57 (2024-11 → 2026-06, equatorial Pacific ~4 °N 137 °W) — all in the PACE era.
  Seed cycles resolve to `7902226`/4 = 2025-02-08 (27.22 °N, 46.02 °W) and
  `7902136`/7 = 2025-01-15 (3.68 °N, 137.24 °W).
- **Assembled the dev set.** 10 profiles = the 2 seeds + 8 candidates chosen as a
  ~7-cycle spread across each float's 2025 track (two distinct biomes, so the
  matchup engine will see both hits and misses). Written as the committed
  manifest `data/dev_profiles.csv` with `data/README.md`.
- **Raised 3 questions** in the Pre Stage 4 Q&A section (the "3 vs 2" seed
  discrepancy; cycle-number confirmation; the choice of the other 8).

What I learned / watch-outs:

- The Ifremer **BGC ERDDAP** (the only `pab.argo.fetch` source) was flaky today —
  one `FSTimeoutError` and one `FileNotFoundError` (404, empty result) for a
  float that the GDAC index clearly contains. The index path is a reliable
  offline-of-ERDDAP fallback for metadata; Stage 4 should fetch measurement
  arrays defensively (retry/timeout) and cache to `PAB_DATA_DIR` to avoid
  re-hitting ERDDAP.
- JXP's seed numbering is profile-relative ("room for error"); the canonical key
  recorded in the manifest is the **GDAC cycle number** — pending his Q&A
  confirmation.

### 2026-06-20 (Pre Stage 4 — converged seeds, finalized the dev set)

Executed the second Pre Stage 4 task after JXP answered the Q&A:

- **Only two seeds** (he confirmed "3" was a typo).
- **Corrected the seed cycles.** His timestamps `2025-02-18T20:26:59` and
  `2025-01-25T13:05:59` pin to index **cycles 5 and 8** (his numbering ran one
  low), not 4 and 7. Dates match to the day; the ~1–5 min offsets are just
  `date` (index) vs. `JULD` (his source). Seeds are now `7902226`/5 and
  `7902136`/8.
- **Chose the other 8 at random** per his request — 4 per float, drawn from each
  float's PACE-era cycles (on/after the 2024-03-05 PACE science-data start, per
  `docs/context.md`). Reproducible via NumPy `default_rng(20260620)`:
  `7902226` → 21, 27, 42, 51; `7902136` → 30, 42, 46, 47.
- Rebuilt `data/dev_profiles.csv` and updated `data/README.md` (selection method,
  seed cycles, RNG seed, PACE-era cutoff).

### 2026-06-20 (Stage 4 — matchup engine)

Implemented the matchup engine that joins the BGC-Argo and PACE halves.

What I built:

- **`pab/matchup/engine.py`** — the matching + record-writing logic. Pure
  geometry/time helpers (`parse_time`, `time_offset_hours`, `make_matchup_id`)
  plus `find_matchup` (temporal pre-filter → open each candidate via the
  `open_granule` `opener=` seam → nearest-unflagged-pixel extraction → distance
  gate → best-by-(distance, dtime, −n_spectra, granule_id)), `write_matchup`
  (idempotent upsert + delete-then-insert of pixels), `qualifying_profiles`,
  `candidate_granules`, and the `build_matchups` driver
  (`{written, skipped, unmatched}`, resumable by `matchup_id`). `MatchupConfig`
  holds the knobs: `dtime_max_hours=24`, `n_spectra=10`, `max_distance_km=5`,
  `mask_flags`. Exported the public API from `pab/matchup/__init__.py`.
- **Tests** — `pab/tests/test_matchup.py` (10, all offline): id format, time
  parsing, closest-granule selection, time-window edge (in/out), distance-gate
  rejection, flagged-nearest-pixel exclusion, all-flagged→None, persisted links
  + idempotent re-run, unmatched-out-of-window, `write_matchup` profile_id
  guard. Suite: **70 passed**.
- **Docs** — `docs/matchup.rst` (criteria, selection/tie-break, `matchup_id`,
  float↔granule↔pixels linkage, autodoc) wired into `index.rst` (Package +
  Notebooks toctrees).
- **Notebook** — `docs/nb/04_matchup.ipynb`, executed offline-safe, with an
  optional `RUN_LIVE` section that reads a seed from `data/dev_profiles.csv`,
  fetches the float (argopy), discovers a granule (earthaccess), and matches.
- **Implementation record** — Stage 4 → ✅, new §5b, module index + verification
  line updated, version 0.2.3 → 0.3.0.

Key decisions / what I learned:

- **Spatial test = nearest-pixel distance gate**, not polygon-in-footprint —
  reuses Stage 3 extraction unchanged, no WKT/shapely; footprint bbox
  pre-filtering is a documented future optimization. No schema change
  (`SCHEMA_VERSION` stays 1). `matchup_pixels.flagged` is always 0 (only
  unflagged pixels are selected). Spectra are *not* stored — re-read at fit time.
- The synthetic test granule has ~26 km pixel spacing (5×5 over ~1°), so the
  realistic 5 km default gate rejects post-flag neighbours; the flagged-pixel
  test loosens the gate to exercise neighbour selection. Real PACE OCI pixels
  are ~1 km, where the 5 km default is appropriate.

### 2026-06-21 (Stage 4 — live dig-in notebook for 7902226)

Built `docs/nb/05_matchup_7902226_4.ipynb`, the requested live exploration of the
seed profile JXP calls "(7902226, 4)" (= GDAC cycle 5). End-to-end against real
services, reusing the PAB seams:

1. `earthaccess.login()`;
2. fetch the profile via `pab.argo.fetch` (BGC ERDDAP, QC 1/2, `iter_profiles`);
3. mixed-layer summary via `pab.argo.summary`;
4. discover `PACE_OCI_L2_AOP` granules in a ±`DTIME_HOURS`, ±`BBOX_PAD`° box via
   `pab.pace.discover`;
5. match with `pab.matchup.engine.find_matchup`;
6. plot the profile (`pab.argo.qa.plot_profile`), the granule (`Rrs`≈442 nm map
   with the float + selected pixels overlaid), and the closest-pixel `Rrs`
   spectrum with its `Rrs_unc` band.

What I learned / decisions:

- **Could not execute it here** — no `~/.netrc`/Earthdata Login on this
  workstation, so `earthaccess.login()` and the S3 granule read fail. Committed
  without outputs; JXP runs it where credentials exist (ideally `us-west-2`).
  Validated the notebook JSON with `nbformat`.
- **Excluded from the Sphinx build** (added to `conf.py` `exclude_patterns`,
  alongside `nb/README.md`) because it is live-only and cannot build
  offline-safe; `sphinx-build -W` still succeeds. Listed it in `docs/nb/README.md`
  and added a Q&A note on the cycle-4↔5 naming.

### 2026-06-21 (Stage 4 — diagnosed the notebook's ERDDAP 408, switched to GDAC)

JXP reported the notebook's fetch cell failing with HTTP `408` from the Ifremer
BGC ERDDAP. Diagnosed live and fixed `docs/nb/05_matchup_7902226_4.ipynb`.

Findings (full write-up in the Reporting section):

- The `408` is **server-side ERDDAP flakiness** (we've now seen FSTimeout / 404 /
  408 from that host across days), not a code bug.
- **Fixed by reading GDAC directly** (`argopy src="gdac"`, ~9 s, reliable).
- Two follow-on gotchas, now handled: (a) `mode="expert"` is required — `standard`
  /`research` return 0 points for a *recent real-time* cycle (they prefer
  adjusted fields that don't exist yet); (b) the blanket `fetch.filter_quality`
  empties the dataset in expert mode because unrelated params (`NITRATE`,
  `PH_IN_SITU_TOTAL`) have QC 0/3 and `filter_qc` rejects a level if *any* param
  fails — so I removed that call. Core params are QC=1; the summary de-spikes
  `BBP700` itself.
- Verified the recipe end-to-end through the PAB seams: MLD=30 m, bbp700=4.3e-4,
  chla=0.091 — sensible N. Atlantic gyre values.
- Raised a Q&A/Reporting question: whether to switch PAB's **default** Argo
  source to `gdac` given the recurring ERDDAP outages (left `fetch.py` unchanged
  pending JXP's call).

No package code changed; `pytest` still 70 passed, `ruff` clean, `sphinx-build
-W` succeeds (the notebook remains excluded from the build).

### 2026-06-21 (Stage 4 — JR/Frouin Rrs overlay cell)

Added section 9 to `docs/nb/05_matchup_7902226_4.ipynb`: over-plots Robert
Frouin's ("JR") PACE-L1B atmospheric-correction `Rrs` spectrum on the standard
PACE L2 AOP closest-pixel spectrum, both with error bands (PACE ±`Rrs_unc` blue;
JR ±`Rrs_std` red). Code also mirrored into the prompt doc's *Extra cell*
section.

- **Reused, didn't reinvent.** *Imports* `jr_utils.load_jr_data`/`extract_rrs`
  from `bing/papers/biomass/Analysis/py` (via a `BING_ANALYSIS_PY` env override),
  honoring the "don't copy the one-off Analysis scripts" agreement — using the
  helper is what JXP asked for.
- **Row selection.** The JR CSV (`Frouin/jr_test_matchup_L1B.csv`, 9 data rows +
  comment rows) is matched to the float by nearest `PACE_lat`/`PACE_lon`
  (`dropna` drops the comment rows). For this seed it resolves to JR **row 6**
  (`PACE_OCI.20250219T155847…`, 0.4 km, time 2025-02-18T20:26:59) — an exact hit.
- **Sanity.** JR spectrum: 268 bands (339–895 nm), blue ~1.0×10⁻² → red
  ~1.7×10⁻⁴ sr⁻¹ — a textbook oligotrophic-gyre shape. Used `Rrs_std` for the
  band (noted `Rrs_uncertainty_<λ>` as an alternative).
- Could not execute end-to-end here (the PACE half still needs Earthdata creds),
  but verified the JR-loading path live; notebook validates with `nbformat`.
