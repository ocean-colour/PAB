# Getting started 

## Goals

This repository will be used to perform matchup analyses between PACE and BGC-Argo data and share the results with the community.

## Prompts

1. Read this file.  Execute the 1st task under "Claude/CLAUDE.md file"
2. Read this file.  Execute the 1st task under "Basic start up"
3. Read this file.  Execute the 1st task under "Dependencies"

## Claude

### CLAUDE.md file

1. Please generate a basic CLAUDE.md file for this project.  Have it indicate:

    - I will perform git commands

### Skills

### Settings

## Basic start up

1. Generate the basic files that one needs for a Python GitHub repository, e.g. a file for dependencies.  Examine the other Repositories in Oceanography/python to see how I tend to organize things.

## Dependencies

1. We have generated a requirements.txt file in the PAB directory.  There appears to be a problem with the version of xarray.  One of my packages requires xarray>=2025.10.1, and I think argopy requires  xarray==2025.9.0 for its latest least.  Please explore and write a Report below.  Do no editing yet.

### Report

## Logging

The "Logs" section will record Claude's work.  Please use the following format:

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

...

## Logs

### 2026-07-28 (First matchup map: PACE–Argo bbp700 relative difference)

**Task:** Produce a regional scatter-map of all PACE–Argo bbp700 matchups in pab.db,
coloured by the relative backscattering difference (PACE − Argo) / PACE, on a
diverging red–blue scale (red = PACE > Argo, blue = Argo > PACE, white = agreement).

**What was done:**

- Queried `pab.db` via `pab.metrics.compare.gather_matchups()` to retrieve the
  4 current matchups (WMO 7902226, cycles 5/21/27/42, subtropical North Atlantic
  ~24–27 °N, 46–54 °W).
- Computed relative difference as `(bbp_bing − bbp_argo) / bbp_bing` where
  `bbp_bing` is the BING-fit posterior median (`BING_ExpBPow_bbp700`) and
  `bbp_argo` is the de-spiked MLD mean from `mld_summary`.
- Wrote a new one-off script `pab/pace/plot_bbp_matchup_map.py` (plain
  matplotlib, no cartopy dependency). The script: auto-pads the map extent
  around the data, uses a symmetric diverging colormap (`RdBu_r`) scaled to
  the maximum observed |rel_diff| rounded up to the nearest 0.1, annotates
  each dot with its cycle number (above) and the ±rel_diff value (below), and
  adds a dashed zero-line on the colorbar. `--db` and `--out` are CLI arguments
  so the script is re-runnable as the database grows.
- **Results for the current 4 matchups:** all four are strongly red (rel_diff
  +0.45 to +0.67), meaning PACE bbp700 consistently exceeds the Argo MLD
  estimate by 45–67 %. This systematic positive bias is the main scientific
  signal to investigate in subsequent analyses.
- **Cartopy note:** cartopy is installed in ocean14 but its Natural Earth
  shapefiles are not pre-cached, and the sandbox cannot write to
  `~/.local/share/cartopy`. The plain matplotlib path was used instead.
  When cartopy shapefiles are available (run `python -c "import cartopy; cartopy.feature.LAND.geometries()"` once to trigger download), the script can
  be extended to add coastlines.

**Output:** `pace_argo_bbp700_relDiff_map.png` (saved to PAB repo root and
as a project artifact).

