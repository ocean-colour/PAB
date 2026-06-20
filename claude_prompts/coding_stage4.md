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

1. Read this doc and the context files. Implement Stage 4 (below). If you have
   questions, write them in the Q&A section. Log your work in the Logs section.

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

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

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
