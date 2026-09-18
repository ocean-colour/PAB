# AQUA MODIS – Argo first 10 matchups

## Goals

Mirror what was done in the PACE–Argo matchup pipeline for the first 10
AQUA MODIS collocations. For each of the first 10 profiles in `pab.db`
(ordered by time), search for AQUA MODIS L2 OC granules, open the nearest
granule, extract the nearest unflagged Rrs pixel using the same logic as
`pab/pace/extract.py`, and write the results (position, distance, Δt,
8-band Rrs spectrum) to a CSV.

## Claude

### Working agreements (unchanged from PACE stages)

- **Git is handled by the user.** No state-changing git commands.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Drive existing `pab` functions wherever possible:
  - `pab.db.store.Store` — database access
  - `pab.pace.discover.search_granules` — CMR search (change `short_name` only)
  - `pab.pace.extract.haversine_km` and `nearest_valid_pixels` — pixel finding
  - `pab.pace.flags.L2_FLAG_BITS` — flag-bit lookup (same bit-field format for MODIS)
  - `pab.pace.cloud.read_datatree` — **not reusable** (PACE-specific variable layout);
    MODIS needs its own open function (see `pab/modis/run_modis_matchup.py` as template)

## Context

Read these before running:

- **Operator guide / design** — `HOWTO.md`, `docs/design/PAB_design.md`
- **PAB database** — `/Users/alliejames/Documents/summer 2026/data/PAB/pab.db`
  (run1k: 986 profiles, 652 floats, global, 2024-03-05 onward)
- **Python environment** — `ocean14` conda environment
- **Earthdata credentials** — stored in `~/.netrc`; `earthaccess.login(strategy="netrc")`

### What the PACE pipeline does (mirror this)

**Granule discovery** (`pab/pace/discover.py` → `search_granules`):
```python
from pab.pace.discover import search_granules
results = search_granules(
    short_name="PACE_OCI_L2_AOP",        # ← change to MODIS short name
    temporal=(t_start, t_end),            # profile time ± 12 h
    bounding_box=(lon-2, lat-2, lon+2, lat+2),
    cloud_cover=(0, 100),
)
```

**Granule open** (`pab/pace/run_pace_matchup.py`):
```python
import earthaccess
from pab.pace.cloud import read_datatree   # ← MODIS needs its own open function
fileset = earthaccess.open([granule_url])
ds = read_datatree(fileset[0])             # returns ds with Rrs, lat, lon, l2_flags, wavelength
```

**Pixel extraction** (`pab/pace/extract.py` — reuse directly):
```python
from pab.pace.extract import nearest_valid_pixels, extract_spectrum
pixels = nearest_valid_pixels(ds, float_lat, float_lon, n=10)
wave, rrs, unc = extract_spectrum(ds, pixels[0]["ix"], pixels[0]["iy"])
```

### MODIS-specific differences

| Item | PACE | AQUA MODIS |
|---|---|---|
| `short_name` | `PACE_OCI_L2_AOP` | `MODISA_L2_OC` (DOI 10.5067/AQUA/MODIS/L2/OC/2022.0) |
| Bands | ~184 (400–700 nm) | 8 (412, 443, 469, 488, 531, 547, 667, 678 nm) |
| Rrs variable | `Rrs` (3-D array) | `Rrs_{wl}` per band (e.g. `Rrs_412`) |
| Uncertainty | `Rrs_unc` | not available per band |
| Granule open | `pab.pace.cloud.read_datatree` | custom (see `run_modis_matchup.py`) |
| Flag mask | Same set used in both: `ATMFAIL`, `LAND`, `HIGLINT`, `HILT`, `STRAYLIGHT`, `CLDICE`, `COCCOLITH`, `HISATZEN`, `HISOLZEN`, `LOWLW`, `CHLFAIL`, `NAVFAIL`, `MAXAERITER` | ← identical |

**Existing MODIS open function** (`pab/modis/run_modis_matchup.py`):
- Opens with `xr.open_datatree(fileset[0], engine="h5netcdf")`
- Reads `Rrs_{wl}` from `geophysical_data` group
- Reads `latitude`/`longitude` from `navigation_data` group
- Reads `l2_flags` from `geophysical_data` group
- **No distance cutoff** in the existing code — takes 10 nearest unflagged pixels
  regardless of distance. The batch script should add a 5 km cutoff as a new design choice.

## Tasks

### Task 1 — Search for MODIS granules near the first 10 profiles

1. Open `pab.db`, query the first 10 profiles ordered by `time`.
2. For each profile, call `pab.pace.discover.search_granules` with
   `short_name="MODISA_L2_OC"` and a ±12 h temporal window.
3. From the candidates, keep the granule with the smallest |Δt| that
   is ≤ 8 hours. Skip the profile if none qualifies.
4. Print a table:
   `profile_id | wmo | cycle | lat | lon | time | granule_url | Δt_hours`

**Before writing code, ask clarifying questions in Q&A below.**

### Task 2 — Open granules, extract pixels, write CSV

For each profile–granule pair from Task 1:

1. Adapt the `open_modis()` function from `pab/modis/run_modis_matchup.py`
   to return a dataset with the same keys as a PACE `ds`
   (`Rrs` as a 3-D array, `latitude`, `longitude`, `l2_flags`, `wavelength`).
2. Call `pab.pace.extract.nearest_valid_pixels` on that dataset — reuse
   without modification.
3. Take the rank-1 pixel if it is within 5 km. Skip otherwise.
4. Write one row per matchup to `pab/modis/modis_argo_matchups.csv`:

```
profile_id, wmo, cycle, lat_float, lon_float, time_float,
granule_url, lat_pixel, lon_pixel, dist_km, dtime_hours,
Rrs_412, Rrs_443, Rrs_469, Rrs_488, Rrs_531, Rrs_547, Rrs_667, Rrs_678
```

5. Print a summary: profiles searched / granules found / valid pixels extracted.

Code goes in `pab/modis/run_modis_matchup_batch.py` as a one-off script
(same pattern as `pab/pace/run_pace_matchup.py`).

## Q&A

**Q1. What is the correct CMR `short_name` for AQUA MODIS L2 OC?**  
A. `MODISA_L2_OC`, version 2022.0, DOI 10.5067/AQUA/MODIS/L2/OC/2022.0.
Confirmed via CMR collection lookup on the granule DOI landing page.

**Q2. Are the flag names the same as PACE?**  
A. Yes — both pipelines use the identical 13-flag mask:
`ATMFAIL, LAND, HIGLINT, HILT, STRAYLIGHT, CLDICE, COCCOLITH, HISATZEN,
HISOLZEN, LOWLW, CHLFAIL, NAVFAIL, MAXAERITER`.
`pab.pace.flags.L2_FLAG_BITS` covers all of them; no new flag logic needed.

**Q3. Can `pab.pace.extract.nearest_valid_pixels` be reused unchanged?**  
A. Yes, provided the MODIS granule is opened into a dataset with the same
variable names (`Rrs`, `latitude`, `longitude`, `l2_flags`, `wavelength`).
`open_modis_as_ds()` in the batch script constructs exactly this layout by
stacking the per-band `Rrs_{wl}` variables into a single 3-D array.

## Logging

Append an entry to the **Logs** section using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-08-06 (MODIS batch matchup script written — first 10 profiles)

Confirmed the correct CMR short name for AQUA MODIS L2 OC is `MODISA_L2_OC`
(version 2022.0) via a CMR DOI lookup. Confirmed the 13-flag mask is identical
to PACE — no new flag logic required. Wrote `pab/modis/run_modis_matchup_batch.py`
which: (1) queries the first N profiles from pab.db; (2) calls
`pab.pace.discover.search_granules` with `short_name="MODISA_L2_OC"` and ±12 h
window; (3) opens the best-Δt granule (≤8 h) via a custom `open_modis_as_ds()`
that normalises the per-band `Rrs_{wl}` variables into the same 3-D layout as
the PACE ds; (4) calls `pab.pace.extract.nearest_valid_pixels` unchanged; (5)
writes results to `pab/modis/modis_argo_matchups.csv`. Also updated the prompt's
MODIS differences table to correct the flag row (all 13 flags are shared with
PACE, not MODIS-specific) and filled in the Q&A section.
