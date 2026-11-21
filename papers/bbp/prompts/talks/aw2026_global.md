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

We will define a matchup as having separation dx < 10km and dt < 3 hours.

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

2. Read the answers to the questions in the "Q&A/Matchups" section below. Also
note the new matchup definition.  Create the script
If you have any additional questions, put them in the "Q&A/Matchups" section below.
Use Opus 5.5.  Log your work.

3. Read the new answers to the questions in the "Q&A/Matchups" section below.
Modify the figure accordingly.
If you have any additional questions, put them in the "Q&A/Matchups" section below.
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

   **A:** To keep it simple, let's show raw CHLA for all of them

2. **Q2: The colour scale.** I suggest log10 Chl, clipped to 0.01–3 mg m⁻³
   with extension arrows on the colour bar, using `viridis`. Is there
   another colour map you prefer, such as cmocean `algae` (if installed)?

   **A:** I agree with log10.  Let's try `algae`.  You can install it with `pip install cmocean`
   and add to the Repo's requirements.txt file.

3. **Q3: The projection and the reuse of `_base_map()`.**
   - Mollweide, as in the paper's maps, by importing `_base_map` from
     `papers/bbp/plot_global_maps.py`. That file is not inside a package,
     so the import needs a `sys.path` insert.
   - Or a short copy of it in `fig_global.py`, so the talk script stands
     alone.

   *(My recommendation: copy it, about 8 lines. Then the talk figure won't
   change if the paper's map style changes.)*

   **A:** Agreed, copy it.

4. **Q4: The details.**
   - File: `talks/AWOC2026/fig_global_matchups.png`.
   - Size: 12 × 6 in, 200 dpi.
   - Title: "PACE–BGC-Argo matchups (dx < 5 km, dt < 2 h), N = …, … floats".
   - Marker size: about 10 pt², drawn in order of Chl so that the high
     values sit on top.

   Any changes, e.g. no title on a slide, or a dark background?

   **A:** Let's try that, and I will tinker.  Note that I changed the definition of a matchup to
   dx < 10 km and dt < 3 hours.


#### Prompt 2: the script and first draft

*Response to Matchups prompt 2 (Claude Opus 5.5, 2026-11-21).*

**Script:** `papers/bbp/talks/AWOC2026/fig_global.py`.
- Run it with `python papers/bbp/talks/AWOC2026/fig_global.py`. Options:
  `--db`, `--out-dir`, `--dx-max`, `--dt-max`.
- It writes `talks/AWOC2026/fig_global_matchups.png`.
- `main()` calls two functions:
  - `load_matchups(db, dx_max, dt_max)` does a SQL join of `matchups`,
    `profiles` and `mld_summary` on the live v2.1 DB;
  - `fig_global_matchups(df, out, ...)` draws the map.
- The matchup definition (`DX_MAX_KM` = 10, `DT_MAX_H` = 3), the Chl range
  (`CHL_LIM`) and the colour map (`CMAP_CHL`) are constants at the top, so
  they are easy to change.

**Answers applied.**
- **Q1.** The points are coloured by *raw* mixed-layer CHLA
  (`mld_summary.chla`), as in the parquet's `chla_argo`.
- **Q2.** The scale is log10, clipped to 0.01–3 mg m⁻³, with arrows at both
  ends, using cmocean `algae`. cmocean 3.0.3 was already installed in
  ocean14.
- **Q3.** `_base_map()` is copied into the script (Mollweide, grey land,
  coastlines).
- **Q4.** 12 × 6 in, 200 dpi. The title gives the definition and N.
  Points are drawn in order of Chl.

**The new definition (dx < 10 km, dt < 3 h)** selects **3,473 matchups
from 628 floats**, up from 2,710 at dt < 2 h. The dx cut still removes
nothing, because the pipeline only builds matchups within 5 km.

On the colour scale:
- **81 profiles have no CHLA at all.** They are drawn as small grey dots
  underneath, with a legend entry, so every matchup appears.
- **150 sit at the bottom of the scale.** 80 have CHLA ≤ 0 and 70 have
  0 < CHLA < 0.01. The lower arrow covers them all.
- **24 have CHLA > 3** and take the top colour.
- Median CHLA is 0.10 mg m⁻³, and the 99th percentile is 2.5.

**Note:** cartopy downloaded Natural Earth's 110 m ocean shapefile on the
first run (one-time, cached).

#### Questions for JXP (prompt 2)

5. **Q5: Pale low-Chl points.** The lowest end of `algae` is a very pale
   green. Points below about 0.03 mg m⁻³ blend into the pale-blue ocean,
   even with their thin dark edge (subtropical gyres, e.g. the South
   Pacific). Options:
   - (a) A white ocean fill.
   - (b) Start the colour map about 15 % in, so the palest colour is a
     light green, not near-white.
   - (c) Leave it.

   *(My recommendation: (b). It keeps the land/ocean contrast.)*

   **A:** It is fine

6. **Q6: The centre longitude.** The map is centred on 0°. The Pacific is
   split at the edges, and many matchups sit near the dateline (central
   and western Pacific). Would a Pacific-centred map
   (`central_longitude=-160` or 180) suit the talk better?

   **A:** Yes, make it Pacific-centred.

#### Prompt 3: Pacific-centred map

*Response to Matchups prompt 3 (Claude Opus 5.5, 2026-11-21).*

- **Q5:** the colour scale is unchanged (`algae` over its full range).
- **Q6:** the map is now Pacific-centred. It uses
  `Mollweide(central_longitude=CENTRAL_LON)`, with `CENTRAL_LON = -155`
  as a constant and a `central_lon` argument.
  - **Why −155:** I counted the matchups near each candidate seam. A seam
    at 25°E (through the Aegean, Libya and South Africa) has only 4
    matchups within 2° and 11 within 5°.
  - Centring on 180° would put the seam at 0°, through the North Atlantic
    and the western Mediterranean: 36 matchups within 2°, 150 within 5°.
    Centring on −160 puts it at 20°E: 73 within 2°.
  - The western and central Mediterranean now sits at the right edge, and
    the far eastern Mediterranean and the Black Sea at the left.

No new questions.

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

### 2026-11-21 (Matchups prompt 2: fig_global.py written; first draft of the global matchup map coloured by raw Argo Chl)

Created `papers/bbp/talks/AWOC2026/fig_global.py`.
- Imports sit at the top, and `main()` calls two functions:
  - `load_matchups()` joins `matchups`, `profiles` and `mld_summary` on the
    live v2.1 DB;
  - `fig_global_matchups()` draws the map.
- Applied the answers:
  - Q1: raw mixed-layer CHLA;
  - Q2: log10 from 0.01 to 3 mg m⁻³, cmocean `algae` (already installed in
    ocean14);
  - Q3: a local copy of `_base_map`;
  - Q4: 12 × 6 in at 200 dpi, a title, points drawn in order of Chl.
- Used the new definition, dx < 10 km and dt < 3 h. It gives 3,473
  matchups from 628 floats. The dx cut is non-binding, because the
  pipeline caps matchups at 5 km.
- Of those, 81 have no CHLA and are drawn as grey dots. 80 have CHLA ≤ 0
  and are clipped to the lower end of the scale.

Rendered `talks/AWOC2026/fig_global_matchups.png` and inspected it.

Added Q5 (pale low-Chl points against the ocean fill) and Q6 (a
Pacific-centred projection).

### 2026-11-21 (Matchups prompt 3: global matchup map made Pacific-centred)

Applied Q5 (keep the colour scale) and Q6 (Pacific-centred) in
`talks/AWOC2026/fig_global.py`. Added a `CENTRAL_LON = -155` constant and a
`central_lon` argument to `fig_global_matchups()`.

I chose the seam by counting matchups within ±2° and ±5° of each candidate
seam longitude. 25°E is the cleanest, with 4 and 11 matchups. The seam at
0° that a 180° centre gives has 36 and 150.

Re-rendered `fig_global_matchups.png` and inspected it. No new questions.
