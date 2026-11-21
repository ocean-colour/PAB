# Create global figures for AWOC 2026

## Goals

Create one or more figures for my talk at AWOC 2026.
Possibly a slide or two too.

## Context

- The majority of Python scripts to make the figures for this paper are in `pab/matchup`
- There is a master script to make the figures for the paper in `PAB/papers/bbp/make_paper_figures.py`
- There is a script that generates global level figures in `PAB/papers/bbp/plot_global_maps.py`

See the prompt doc `rt_fit_pb24.md` in `Oceanography/python/retrieve-or-bust/claude_prompts/RT`
for pointers to code that ingests the PB24 Hydrolight outputs.

We will define a matchup as having separation dx < 10km and dt < 2 hours.

## Code

- Use Python
- Use matplotlib and/or seaborn
- Have a main() function in the script that calls the other functions.
- Put imports at the top of the script.
- Document the code using docstrings and inline comments.
- Reuse existing code where possible.

## Prompts

### Matchups

1.  Read the Context section above.   We are going to create a global figure
showing where we have matchups between Argo and PACE, using the definition in Context.
We wish to indicate land.  Have the color of the points be the
adjusted Chl value from Argo and show a color bar.
This will be one method in `talks/AWOC2026/fig_global.py`, called by main.
Before creating the figure, confirm you can read the matchup data and that you have the data you need to create the figure.
Discuss this with me in the "Q&A/Matchups" section below before writing code.
Use Opus 5.5.  Log your work.


## Q&A

### Matchups

*Response to Matchups prompt 1 (Claude Opus 5.5, 2026-11-21). No code yet.*

#### Can I read the data? Yes.

Everything comes from the live v2.1 database, `$PAB_DATA_DIR/v2/pab.db`,
with three joins on `profile_id`:
- **Separation and time:** `matchups.distance_km` and `matchups.dtime_hours`.
  `dtime_hours` is stored as |Δt|.
- **Position:** `profiles.latitude` and `profiles.longitude`. These are the
  float positions.
- **Chl:** `mld_summary.chla_adjusted`, the mixed-layer mean of Argo
  `CHLA_ADJUSTED` (mg m⁻³). It is NULL where Argo has not adjusted the
  profile. `mld_summary.chla_data_mode` gives the R/A/D mode.

I can't use `matchup_summary.parquet` here, for two reasons:
- It is not in `v2/` yet; that is Q2 in `analysis.md`. The copy in
  `v2/s3_stage_v21_20261119/` exists.
- Its `chla_argo` column is the *raw* mixed-layer CHLA, not the adjusted
  value. It matches `mld_summary.chla` exactly.

The land mask is available: cartopy 0.25 is in ocean14.
`papers/bbp/plot_global_maps.py` already has a `_base_map()` with land,
ocean and coastlines on a Mollweide projection.

#### What the definition selects

| Cut | Matchups | Floats |
|---|---:|---:|
| All matchups in the DB | 15,976 | — |
| dx < 10 km and dt < 2 h | **2,710** | **555** |
| … with `chla_adjusted` not NULL | 2,529 | |
| … with `chla_adjusted` > 0 (plottable on a log scale) | 2,464 | |

- **The dx < 10 km cut does nothing.** The pipeline only built matchups
  within 5 km (the maximum distance in the DB is 5.00 km), so dt < 2 h is
  the only cut that bites. For the slide, "dx < 5 km, dt < 2 h" is the
  honest description.
- There is one profile per matchup, so each point is one float profile.
  They run from 2024-03-06 to 2026-08-01, at latitudes 76°S to 77°N.
- 2,709 of the 2,710 have a BING 2.1 fit.
- **The 246 matchups without a positive adjusted Chl:**
  - 93 are real-time (R) profiles, which have no adjusted Chl at all.
  - 74 have no CHLA data mode.
  - 14 are A/D-mode profiles where the mixed-layer mean is missing.
  - 65 have `chla_adjusted` ≤ 0. These are oligotrophic profiles, where
    dark-offset noise pushes the mean below zero.
- **Adjusted Chl range:** median 0.059 mg m⁻³, 1–99 % range ≈ 0.004 to
  2.0, maximum 6.9. 241 profiles are below 0.01.
- Adjusted vs raw: adjusted is a median 0.62× raw, with a 5–95 % range of
  0.20–1.64. So the colours will differ noticeably from a map of the
  parquet's `chla_argo`.

#### Questions for JXP

1. **Q1: The 246 matchups with no usable adjusted Chl.**
   - (a) Draw them as small grey markers beneath the coloured ones, so the
     map still shows every matchup, with a legend entry such as "no
     adjusted Chl".
   - (b) Drop them, so the map shows 2,464 points.
   - (c) Fall back to raw CHLA for them. I don't recommend this, because it
     mixes two calibrations on one colour bar.

   *(My recommendation: (a).)*

   **A:**

2. **Q2: The colour scale.** I suggest log10 Chl, clipped to 0.01–3 mg m⁻³
   with extension arrows on the colour bar, using `viridis`. Is there
   another colour map you prefer, such as cmocean `algae` (if installed)?

   **A:**

3. **Q3: The projection and the reuse of `_base_map()`.**
   - Mollweide, as in the paper's maps, by importing `_base_map` from
     `papers/bbp/plot_global_maps.py`. That file is not inside a package,
     so the import needs a `sys.path` insert.
   - Or a short copy of it in `fig_global.py`, so the talk script stands
     alone.

   *(My recommendation: copy it, about 8 lines. Then the talk figure won't
   change if the paper's map style changes.)*

   **A:**

4. **Q4: The details.**
   - File: `talks/AWOC2026/fig_global_matchups.png`.
   - Size: 12 × 6 in, 200 dpi.
   - Title: "PACE–BGC-Argo matchups (dx < 5 km, dt < 2 h), N = …, … floats".
   - Marker size: about 10 pt², drawn in order of Chl so that the high
     values sit on top.

   Any changes, e.g. no title on a slide, or a dark background?

   **A:**


## Logs

### 2026-11-21 (Matchups prompt 1: matchup and adjusted-Chl data confirmed for the global map; questions raised before coding)

I confirmed that the live v2.1 DB (`$PAB_DATA_DIR/v2/pab.db`) has
everything the map needs, with three joins on `profile_id`:
- `matchups`: `distance_km`, and `dtime_hours` stored as |Δt|;
- `profiles`: latitude and longitude;
- `mld_summary.chla_adjusted`: the mixed-layer mean of `CHLA_ADJUSTED`,
  plus `chla_data_mode`.

Cartopy 0.25 is in ocean14, so the land mask is available, and
`plot_global_maps._base_map()` can be reused.

Findings:
- `matchup_summary.parquet` is not in `v2/` yet; only the copy in
  `s3_stage_v21_20261119/` exists. Its `chla_argo` column is the raw
  mixed-layer CHLA, not the adjusted value.
- dx < 10 km and dt < 2 h selects 2,710 matchups from 555 floats. The dx
  cut is non-binding, because the pipeline caps matchups at 5 km.
- 2,529 of those have adjusted Chl, and 2,464 have adjusted Chl > 0. The
  missing ones are mostly R-mode profiles (93) and profiles with no data
  mode (74).
- Adjusted Chl has a median of 0.059 mg m⁻³ and a 1–99 % range of
  0.004–2.0. It is a median 0.62× the raw value.

Wrote Q1–Q4 in "Q&A/Matchups": how to handle matchups without adjusted
Chl, the colour scale, reusing vs copying `_base_map`, and the file name,
size and title. No code was written yet, as the prompt asked.
