# Scrutinize PACE

## Goals

This prompt doc will be used to scrutinize one or more of the 
PACE analyses.  In particular our retrieval of bbp(700). 

The effort will include an examination of the RT model and PACE
atmospheric corrections.

## Context

- `Oceanography/python/bing` holds the Bayesian fitting code for IOP retrievals
- `Oceanography/python/retrieve-or-bust` holds the radiative transfer model code

We have fitted the PACE observations with BING using the ZTT RT model in retrieve-or-bust.

Outputs for the analysis are in `$PAB_DATA_DIR/v2`

Here is a tutorial for processing PACE L1B to L2 data with `l2gen`:
`https://nasa.github.io/oceandata-notebooks/notebooks/oci/oci_ocssw_l2gen.html`

The folder `$OS_COLOR/ocssw` contains the OSSSW code.

## Code

- Use Python
- Use matplotlib and/or seaborn
- Have a main() function in the script that calls the other functions.
- Put imports at the top of the script.
- Document the code using docstrings and inline comments.
- Reuse existing code where possible.
- Follow the approach in `talks/AWOC2026/fig_argo.py` for how to call the function from main.
- Have any figures generted be placed in the `figs/` folder.

If you need to run python, use the `ocean14` conda environment.

## Prompts

### CDOM

1.  I wish to examine whether CDOM fluorescence could affect our retrieval of bbp(700).
We are going to start by examining the BING model for the matchup with
`wmo = 5906209` and `cycle_ID = 224`.
Before performing any analysis, read the Context above.
And assess whether we had performed the BING analysis with CDOM fluorescence included.
Discuss this examination with me in the `Q&A/CDOM` section below.
Use Fable.  Log your work.

2. Ok, let's explore further.  Before refitting, let's plot the best model as is
and then also turning on the CDOM fluorescence term.
Create a module named `py/explore_cdom.py` that plots (i) the Rrs spectrum from PACE,
(ii) the best fit model as is, and (iii) the best fit model with CDOM fluorescence turned on.
Include an inset that shows the data and models at wavelengths 610-700 nm
(see the left panel in PAB/papers/bbp/talks/AWOC2026/fig_bing.py for an example). 
If you have any questions or concerns, discuss them with me in the `Q&A/CDOM` section below.
Use Fable.  Log your work.

### Atmospheric Corrections

1. We now wish to explore how the atmospheric corrections by the PACE team using `l2gen`
affect our retrieval of bbp(700).  I have added additional information to the Context
section regarding the atmospheric corrections.  You should review the webpage which
descibes the standard commands for processing the L1B data.
We are going to want to download the 
L1B data for the matchup with `wmo = 5906209` and `cycle_ID = 224` and then process it with `l2gen`
being sure to first grab the ancillary data for that file (using `getanc`).
Before doing any real work, discuss this with me in the `Q&A/Atmospheric Corrections` section below.
We should decide on where the new products go, and whether you need to install additional
`l2gen` related software.
Use Fable.  Log your work.

2. I have answered the first round of questions in the `Q&A/Atmospheric Corrections` section below.
Please review those and react accordingly.  Hopefully you can successfully install `l2gen`
and we will take it from there.
If you have additional questions or concerns, discuss them with me in the `Q&A/Atmospheric Corrections` section below.
Use Fable.  Log your work.

3. Ok, please download the L1B data for the matchup with `wmo = 5906209` and `cycle_ID = 224`.
We are then going to construct a figure with a method in a module 
named `py/plot_L1B.py`.  The left panel 
should show the TOA radiance at 650 nm for the matchup.  The right panel should show 
indicate what flags are set in the L1B file.
Before creating the code, discuss this with me in the `Q&A/Plot L1B` section below.
Use Fable.  Log your work.

4. I have answered the first round of questions in the `Q&A/Plot L1B` section below.
Read those and then create the code and figure as we have discussed.
If you have any additional questions or concerns, discuss them with me in the `Q&A/Plot L1B` section below.
Use Fable.  Log your work.

### Find examples

1. My first matchup scrutinized (`wmo=5906209` and `cycle_ID=224`) was likely 
an issue related to cloud coverage.  Let us look for other examples.
Create a module named `py/find_examples.py` that finds other matchups with
these approximate conditions:
    - The Argo bbp(700) is approximately 1.0e-3 m-1
    - The PACE/Argo bbp(700) ratio is approximately 2
    - The cloud coverage in the granule is <50%
    - The time difference between the PACE and Argo measurements is <=3 hours

    Have the script print a list of the top 20 matchups given these criteria with the following information:
    - The matchup location (lat/lon)
    - The cloud coverage in the granule
    - The Argo bbp(700)
    - The PACE bbp(700)

    If you have any additional questions or concerns, discuss them with me in the `Q&A/Find Examples` section below.
    Use Fable.  Log your work.

2. Ok, thanks for the iteration.  I have answered your questions and concerns
and ask that you update the script accordingly.  I will then run it, examine
several of the options and return to L1B inspection.
If you have any additional questions or concerns, discuss them with me in the `Q&A/Find Examples` section below.
Use Fable.  Log your work.

#### Examples

- 5907088_41 is the first, very clear granule outside the Mediterranean
   - It's BING fit, however, is not optimal, e.g. high chi^2

### Plot L1B

1. Modify the `py/plot_L1B.py` module to download the L1B data for the input
`wmo` and `cycle` if the file is not already present in the `SCRUTINIZE_DIR`.
I will then run it on a new matchup. 
If you have any questions or concerns, discuss them with me in the `Q&A/Plot L1B` section below.
Use Fable.  Log your work.

## Q&A

### Find examples

#### 1. Matchups like 5906209 / 224 under clearer skies (2026-11-24)

Module: `papers/bbp/py/find_examples.py`. Run it with
`python papers/bbp/py/find_examples.py [n]`; it prints the top `n` (default 20).

**How I made "approximately" concrete.** Cloud cover < 50 % is a hard cut. The
other two criteria are ranked by one score, the distance from the targets in
log space: `score = sqrt(ln(argo/1e-3)² + ln(ratio/2)²)`. A given fractional
miss in Argo bbp or in the ratio costs the same. PACE bbp(700) is the v2.1
BING posterior median; Argo is the mixed-layer mean; only successful fits are
used.

**The top 20** (3066 of 15,189 usable v2.1 matchups pass the cloud cut):

| # | wmo | cycle | date | lat | lon | cloud % | Argo bbp | PACE bbp | ratio | Δx km | Δt h | χ²_ν |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2903797 | 160 | 2026-02-27 | 36.80 | 17.13 | 42.4 | 1.01e-3 | 1.99e-3 | 1.98 | 0.4 | 1.1 | 0.80 |
| 2 | 5907088 | 106 | 2025-04-27 | 38.00 | 17.09 | 42.9 | 9.78e-4 | 1.96e-3 | 2.00 | 0.4 | 7.1 | 0.74 |
| 3 | 6990588 | 15 | 2024-08-04 | −36.97 | 120.40 | 26.4 | 9.73e-4 | 1.99e-3 | 2.04 | 2.2 | 23.1 | 0.41 |
| 4 | 5906473 | 89 | 2024-05-31 | −0.63 | −147.41 | 41.1 | 9.70e-4 | 1.90e-3 | 1.96 | 1.7 | 1.0 | 0.47 |
| 5 | 5906574 | 74 | 2025-01-16 | −13.06 | −103.38 | 47.7 | 1.02e-3 | 2.12e-3 | 2.08 | 0.5 | 8.3 | 1.14 |
| 6 | 5906238 | 172 | 2024-12-13 | −0.90 | 169.44 | 48.6 | 1.01e-3 | 1.93e-3 | 1.91 | 4.1 | 9.9 | 0.44 |
| 7 | 5906486 | 147 | 2026-03-04 | 12.50 | −91.77 | 44.8 | 9.92e-4 | 1.89e-3 | 1.90 | 0.3 | 1.7 | 0.40 |
| 8 | 2903969 | 5 | 2026-01-09 | −38.81 | 160.43 | 41.7 | 1.05e-3 | 2.15e-3 | 2.04 | 2.8 | 0.5 | 0.51 |
| 9 | 5907088 | 113 | 2025-06-01 | 37.98 | 17.00 | 30.6 | 1.02e-3 | 2.19e-3 | 2.14 | 0.4 | 18.5 | 1.17 |
| 10 | 6990528 | 183 | 2026-05-29 | 42.38 | 6.74 | 35.2 | 9.31e-4 | 1.83e-3 | 1.96 | 0.6 | 5.6 | 0.71 |
| 11 | 6990686 | 118 | 2026-07-06 | 40.67 | 3.12 | 25.2 | 9.35e-4 | 1.80e-3 | 1.93 | 0.6 | 1.7 | 0.61 |
| 12 | 1902347 | 382 | 2025-08-05 | −0.26 | −179.51 | 48.3 | 9.44e-4 | 1.99e-3 | 2.11 | 0.9 | 10.1 | 2.04 |
| 13 | 1902347 | 73 | 2025-03-02 | −0.17 | −177.53 | 35.6 | 9.24e-4 | 1.78e-3 | 1.92 | 0.2 | 21.8 | 0.62 |
| 14 | 7901109 | 34 | 2026-02-15 | 12.60 | −91.29 | 28.1 | 9.45e-4 | 1.76e-3 | 1.86 | 0.8 | 4.1 | 0.46 |
| 15 | 5906473 | 145 | 2025-12-30 | 0.13 | −136.79 | 42.5 | 9.46e-4 | 1.76e-3 | 1.86 | 2.9 | 14.7 | 1.43 |
| 16 | 7902124 | 42 | 2026-01-08 | −35.87 | 25.02 | 48.0 | 1.06e-3 | 1.96e-3 | 1.86 | 0.3 | 5.0 | 0.16 |
| 17 | 2903797 | 159 | 2026-02-22 | 36.76 | 17.20 | 43.4 | 1.04e-3 | 1.91e-3 | 1.84 | 1.0 | 1.5 | 0.55 |
| 18 | 2903854 | 38 | 2024-08-06 | −30.99 | 113.80 | 33.3 | 1.04e-3 | 1.90e-3 | 1.83 | 3.2 | 9.0 | 0.94 |
| 19 | 5907146 | 74 | 2026-07-02 | 42.38 | 3.75 | 36.8 | 9.35e-4 | 2.00e-3 | 2.14 | 0.4 | 1.0 | 0.90 |
| 20 | 2904029 | 14 | 2026-03-30 | 9.91 | −89.96 | 46.6 | 1.10e-3 | 2.12e-3 | 1.94 | 0.5 | 23.4 | 0.35 |

bbp in m⁻¹; lat/lon are the fitted PACE pixel. The script also prints the
score and marks flagged pixels (none of these 20 is flagged).

**What stands out:**

- **Close matches are easy to find.** All 20 are within 10 % of both targets.
  The condition is not rare under clearer skies.
- **The cloud cut does not change the bias.** The median PACE/Argo ratio is
  1.33 for granules under 50 % cloud and 1.34 for all matchups. Among
  low-cloud matchups with Argo bbp(700) between 0.8e-3 and 1.25e-3 m⁻¹, 124 of
  559 (22 %) have a ratio between 1.6 and 2.5.
- That weighs against granule-level cloud cover as the explanation of a
  factor-of-two excess. It does not rule out cloud near the pixel, which the
  granule number does not measure.
- **The list clusters by region.** Seven of the 20 are in the Mediterranean
  (Ionian Sea and the north-west basin), five are in the equatorial Pacific,
  one is in the tropical South Pacific, three are off Central America, and
  four are at 31–39° S. Several floats
  appear twice (2903797, 5907088, 5906473, 1902347).
- **Few granules are really clear.** The lowest cloud cover in the list is
  25 %, and half the list is above 42 %. Only 5 % of all matchup granules are
  below 38 % cloud.

**Concerns and questions:**

- C1. Granule cloud cover is a blunt measure. A granule that is 30 % cloud can
  still have cloud beside the pixel, and one that is 80 % cloud can have a
  wide clear region. For the question you are asking, a local measure (from
  the L1B reflectance around the pixel, as in `plot_L1B.py`, or from the L2
  flags) would be more telling, at the cost of downloading each granule.
>A. Agreed, but we will start with the granule cloud cover for now.
- C2. Repeat floats and regional clusters may point to a float-side cause
  (a sensor offset on one float) or a regional water type, not the
  atmosphere. I have not separated these.
>A. Also agreed, but this should be a small issue overall
- Q1. Do you want the ranking to prefer matchups that are close in space and
  time (e.g. Δt < 3 h), or to drop poor fits (χ²_ν > 1)? Neither is applied
  now; rows 3, 13 and 20 are about a day apart.
>A. Yes, I have added a close in time criterion, Dt <= 3 hours
- Q2. Should the list be limited to one matchup per float, to spread the
  examples?
>A. Yes, limit to one matchup per float
- Q3. Which of these should I take forward to the L1B plot? My suggestion is
  three with small Δt from different regions: #1 (2903797 / 160, Ionian Sea),
  #4 (5906473 / 89, equatorial Pacific) and #8 (2903969 / 5, Tasman Sea).
  Each needs a 1.9 GB L1B download.
>A. I am still exploring and will soon decide.

#### 2. Script updated: Δt ≤ 3 h and one matchup per float (2026-11-24)

`papers/bbp/py/find_examples.py` now applies your two answers:

- **Time cut:** `|Δt| ≤ 3 h` is a hard cut, like the cloud cut. It is a
  module constant (`DTIME_MAX`) and an argument of `find_examples()`.
- **One per float:** each float contributes only its best-scoring matchup
  (`one_per_float=True`, the default).

The score is unchanged. Run it as before:
`python papers/bbp/py/find_examples.py [n]`.

**Counts:** 15,189 usable v2.1 matchups → 3066 under 50 % cloud → 894 within
3 h, from 238 floats.

**The new top 20:**

| # | wmo | cycle | date | lat | lon | cloud % | Argo bbp | PACE bbp | ratio | Δx km | Δt h | χ²_ν |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2903797 | 160 | 2026-02-27 | 36.80 | 17.13 | 42.4 | 1.01e-3 | 1.99e-3 | 1.98 | 0.4 | 1.1 | 0.80 |
| 2 | 5906473 | 89 | 2024-05-31 | −0.63 | −147.41 | 41.1 | 9.70e-4 | 1.90e-3 | 1.96 | 1.7 | 1.0 | 0.47 |
| 3 | 5906486 | 147 | 2026-03-04 | 12.50 | −91.77 | 44.8 | 9.92e-4 | 1.89e-3 | 1.90 | 0.3 | 1.7 | 0.40 |
| 4 | 2903969 | 5 | 2026-01-09 | −38.81 | 160.43 | 41.7 | 1.05e-3 | 2.15e-3 | 2.04 | 2.8 | 0.5 | 0.51 |
| 5 | 6990686 | 118 | 2026-07-06 | 40.67 | 3.12 | 25.2 | 9.35e-4 | 1.80e-3 | 1.93 | 0.6 | 1.7 | 0.61 |
| 6 | 5907146 | 74 | 2026-07-02 | 42.38 | 3.75 | 36.8 | 9.35e-4 | 2.00e-3 | 2.14 | 0.4 | 1.0 | 0.90 |
| 7 | 3901578 | 116 | 2025-02-02 | 10.44 | −19.62 | 46.9 | 9.41e-4 | 2.08e-3 | 2.21 | 0.7 | 1.8 | 1.91 |
| 8 | 5907088 | 41 | 2024-06-06 | 37.51 | 16.78 | 36.0 | 9.68e-4 | 2.18e-3 | 2.25 | 0.2 | 0.2 | 1.87 |
| 9 | 4903660 | 89 | 2025-03-15 | 15.43 | 59.54 | 47.3 | 1.12e-3 | 2.15e-3 | 1.92 | 0.5 | 1.8 | 0.64 |
| 10 | 5906990 | 106 | 2025-05-24 | 38.17 | 2.06 | 47.6 | 8.98e-4 | 1.67e-3 | 1.86 | 0.6 | 1.7 | 0.47 |
| 11 | 2902936 | 35 | 2026-02-16 | 16.05 | 64.24 | 46.1 | 9.37e-4 | 1.66e-3 | 1.77 | 0.4 | 0.2 | 0.27 |
| 12 | 2902273 | 212 | 2025-02-12 | 17.43 | 68.37 | 48.6 | 9.31e-4 | 2.12e-3 | 2.28 | 0.6 | 0.1 | 1.49 |
| 13 | 5906303 | 162 | 2025-02-16 | 2.36 | −173.61 | 43.9 | 8.54e-4 | 1.71e-3 | 2.01 | 4.8 | 0.8 | 0.50 |
| 14 | 4903848 | 51 | 2026-02-22 | 36.32 | 16.97 | 43.4 | 1.09e-3 | 1.90e-3 | 1.74 | 1.4 | 1.2 | 0.64 |
| 15 | 1902605 | 231 | 2025-03-06 | 43.01 | 7.18 | 38.0 | 8.45e-4 | 1.60e-3 | 1.90 | 0.1 | 0.4 | 0.45 |
| 16 | 6990528 | 114 | 2024-07-08 | 42.74 | 8.33 | 47.4 | 1.13e-3 | 1.99e-3 | 1.76 | 0.7 | 1.5 | 0.54 |
| 17 | 6903825 | 167 | 2025-03-08 | 42.15 | 17.39 | 36.8 | 1.01e-3 | 2.45e-3 | 2.43 | 1.0 | 0.3 | 1.01 |
| 18 | 5907147 | 29 | 2025-08-15 | 41.15 | 7.72 | 34.0 | 8.25e-4 | 1.57e-3 | 1.91 | 0.4 | 1.0 | 0.88 |
| 19 | 4903564 | 26 | 2025-10-22 | 24.28 | −28.16 | 49.1 | 8.11e-4 | 1.72e-3 | 2.12 | 0.4 | 0.5 | 0.35 |
| 20 | 4903487 | 66 | 2025-01-05 | 26.68 | −23.71 | 39.1 | 8.05e-4 | 1.64e-3 | 2.04 | 0.3 | 3.0 | 1.43 |

**Notes on the new list:**

- The first four rows are close to both targets (within 5 %). The match
  loosens down the list: by row 20 the Argo bbp is 20 % below target and the
  ratios run from 1.74 to 2.43.
- Half the list (10 of 20) is in the Mediterranean, even with one matchup per
  float. The rest: three in the Arabian Sea, three in the north-east Atlantic
  off West Africa, two in the equatorial Pacific, one off Central America and
  one in the Tasman Sea.
- Five rows have χ²_ν above 1 (7, 8, 12, 17, 20); no pixel is flagged.
- The three I suggested earlier are rows 1, 2 and 4 here.

No new questions. One reminder for when you return to the L1B inspection:
`plot_L1B.py` looks for the granule under
`$PAB_DATA_DIR/scrutinize/<wmo>_<cycle>/l1b/`, and each new example needs its
own 1.9 GB download first.

### Plot L1B

#### 1. The L1B file and a proposal for `py/plot_L1B.py` (2026-11-24)

**The L1B is downloaded** (1.93 GB):
`$PAB_DATA_DIR/scrutinize/5906209_224/l1b/PACE_OCI.20260417T015116.L1B.V3.nc`
(processing version 3.0.2). No plotting code has been written.

**What is in the file that matters for the figure:**

- **It stores reflectance, not radiance.** The variables are `rhot_blue`,
  `rhot_red` and `rhot_SWIR` (TOA reflectance, band × scan × pixel). To show
  radiance I would convert the way `l2gen` does when it reads the file
  (`ocssw_src/oel_hdf4/libl1/l1_oci.c`):
  `Lt = rhot · F0 · cos(θ_s) / (π · d²)`, with `F0` the band's solar
  irradiance and `d²` the Earth–Sun distance correction (1.0074), both read
  from the file.
- **650 nm is on the red detector:** band index 24, centre 649.65 nm. The blue
  detector stops at 605.7 nm.
- **Grid:** 1710 scans × 1272 pixels. Our pixel is at (scan 1401, pixel 1068);
  its latitude and longitude match the stored matchup pixel.
- **At our pixel:** `rhot(650)` = 0.0543, θ_s = 62.0°, which gives
  Lt ≈ 12.8 W m⁻² µm⁻¹ sr⁻¹.

**What the scene looks like at 650 nm:**

- The granule is mostly cloud: the median `rhot(650)` is 0.31, and clear water
  is about 0.04.
- Our pixel is in a clear patch (0.054), but cloud is close. Within ±5 pixels
  the reflectance reaches 0.28, and 35 % of the ±50-pixel box is brighter
  than 0.1.

**The L1B flags are sparse.** The file has no cloud, glint or stray-light
flags; those are made by `l2gen` and live in the L2 `l2_flags`. What the L1B
does have:

| flag | where | set in this granule? |
|---|---|---|
| saturation, per band | `qual_blue` | never |
| saturation, per band | `qual_red` | yes, only in bands 656–717 nm; 1.9 % of pixels have at least one saturated red band |
| HAM-B striping, per band | `qual_red` | never |
| saturation, per band | `qual_SWIR` | yes, in 1.2 % of pixels |
| off-Earth, solar eclipse, bad terrain | `geolocation_data/quality_flag` | never |
| tilt change, missing time, missing encoder | `scan_quality_flags` | never |
| land/water | `watermask` | 2.3 % land |

- The 650 nm band itself is never saturated. Saturation starts at 655.8 nm.
- Our pixel has no flag set in any band. The nearest saturated pixel is about
  30 pixels away.
- The saturated bands (656–717 nm) overlap the red end of our fit window.
  Saturated cloud nearby is the classic source of stray light, which would
  add signal in exactly those bands. That makes the flag map more interesting
  than its sparseness suggests.

**Proposal for the figure:**

- *Left:* TOA radiance at 649.65 nm, with the matchup pixel marked and the
  Argo profile position shown. Logarithmic colour scale, because clear water
  and cloud differ by more than a factor of ten.
- *Right:* a categorical map on the same area: no flag, red saturation
  (any band 656–717 nm), SWIR saturation, both, and land.
- A single function, e.g. `plot_l1b(wmo, cycle, half_width=..., out=...)`, in
  `papers/bbp/py/plot_L1B.py`, saving the PNG beside it. The granule and pixel
  come from `pab.db`, so it works for other matchups once their L1B is
  downloaded.

**Questions:**

- Q1. Radiance or reflectance on the left? You asked for radiance, and I can
  convert as above. Note that θ_s runs from 56° to 78° across the granule, so
  a radiance map carries that illumination gradient and a reflectance map
  does not. I suggest radiance as asked, in W m⁻² µm⁻¹ sr⁻¹. `l2gen` uses
  mW cm⁻² µm⁻¹ sr⁻¹, which is ten times smaller; say if you prefer those.
>A. Show reflectance, not radiance.
- Q2. Area: the full granule, or a zoom on the matchup? I suggest a zoom of
  ±100 pixels (about 200 km across) so the cloud edges near the pixel are
  visible, with the box size as an argument. A full-granule view could be a
  second call.
>A. Let's do a zoom, but 2x larger, i.e. 400km across.  We may then Zoom further
- Q3. Axes: pixel and scan indices, or latitude and longitude? The granule
  crosses the date line (178° W), which complicates a map projection. I
  suggest pixel/scan axes for the zoom, with the pixel's lat/lon in a label.
>A. Pixels and a lat/lon label is fine
- Q4. The right panel as proposed shows only saturation and land. Is that
  what you want, or should it also show the L2 `l2_flags` (cloud, stray
  light, etc.) for this granule? That needs the NASA L2 file (0.3 GB), which
  is not yet downloaded, and they are not L1B flags.
>A. Ok, keep to saturation and land for now
- Q5. Should the right panel count the number of saturated bands per pixel
  instead of a yes/no category? It would show how deep the saturation goes.
>A. Yes/no is fine.

#### 2. The L1B figure (2026-11-24)

Module: `papers/bbp/py/plot_L1B.py`. Figure:
`papers/bbp/py/fig_L1B_5906209_224.png`.

**As built, following your answers:** reflectance (not radiance) at 649.6 nm
on a log grey scale on the left; saturation (yes/no over all bands) and land
on the right; pixel/scan axes with the pixel's latitude and longitude in the
title; the fitted PACE pixel and the Argo position marked on both panels.

**One change from what we discussed: the box is set in kilometres, not
pixels.** My first version used ±200 pixels and came out 1078 × 483 km. Near
this pixel OCI samples about 2.1 km per pixel across-track and 1.2 km per scan
along-track, because the view angle is 49°. The function now takes a
half-width in km (default 200) and selects scans 1236–1566 and pixels
960–1147, which is 399 × 399 km. The panels are stretched so the box is square
on the ground; a pixel is therefore drawn wider than it is tall.

**What the figure shows:**

- The pixel sits in a dark, clear lane inside a field of broken cellular
  cloud. `ρt(650)` is 0.054 at the pixel against a box median of 0.078.
- Bright cloud edges lie a few pixels away in several directions.
- Flags are rare in the box: 0.33 % of pixels have a saturated red band,
  0.03 % have red and SWIR saturated, and 0.37 % are land (the Chatham
  Islands, I believe, at the right edge). The pixel has no flag.
- The nearest saturated pixel is 46 km from the matchup pixel.
- Saturation in the box is confined to the 49 red bands from 655.8 to
  716.8 nm. HAM-B striping, geolocation-quality and scan-quality flags are not
  set anywhere in the box.

**What it does and does not tell us about bbp(700):**

- The L1B saturation flag does not implicate this pixel directly: nothing is
  flagged within 46 km.
- It does not clear it either. Saturation marks only the brightest cloud
  cores; unsaturated cloud at `ρt` ≈ 0.3 is within a few pixels, five to six
  times brighter than the water. Stray light and adjacency scale with that
  contrast, and neither is recorded in an L1B flag. The L2 `l2_flags`
  (stray light, cloud) are the place to look next.

**Concerns and questions:**

- C1. The Argo cross sits on the PACE circle: the profile is 2 km from the
  pixel, less than one across-track pixel. That is correct, not a plotting
  slip.
- Q1. You mentioned zooming further. The function takes the half-width in km
  as its third argument (e.g. `plot_L1B.py 5906209 224 50` for 100 km). Shall
  I make that figure, and at what size?
- Q2. Would a third panel help, showing the brightest reflectance within some
  radius of each pixel, as a simple proxy for cloud-adjacency risk?

#### 3. `plot_L1B.py` now downloads a missing L1B (2026-11-24)

`python papers/bbp/py/plot_L1B.py <wmo> <cycle> [half_width_km]` now fetches
the L1B granule itself when it is not on disk, then makes the figure.

**How it works:**

- It looks for the file in `$PAB_DATA_DIR/scrutinize/<wmo>_<cycle>/l1b/`.
- If it is absent, it resolves the L1B address from the matchup's granule
  through NASA's catalogue and downloads it with your Earthdata login
  (`~/.netrc`). Expect about 1.9 GB and a few minutes; a line is printed when
  a download starts.
- A file already on disk is reused. `plot_l1b(..., download=False)` forbids
  the download and raises if the file is missing.

**What I tested, and what I did not:**

- Tested: the existing granule (5906209 / 224) is found and plotted without a
  download; for a new matchup (2903797 / 160) the pixel, the L1B name
  (`PACE_OCI.20260227T113237.L1B.V3.nc`) and its download address all resolve;
  `download=False` raises as intended.
- Not tested: an actual download through the new code path. I did not want to
  pull 1.9 GB for a matchup you have not chosen. It calls the same helper
  that downloaded the first granule, so I expect it to work; your first run
  on a new matchup is the real test.

**Concerns and questions:**

- C1. **Where the data goes.** You wrote "if the file is not already present
  in the `DEFAULT_OUT_DIR`". In the script that name is the *figure* folder
  (`papers/bbp/py/`, inside the git repository). I kept the L1B files in
  `$PAB_DATA_DIR/scrutinize/<wmo>_<cycle>/l1b/`, the location you chose
  earlier, so that 1.9 GB files stay out of the repository. Say if you meant
  something else.
- C2. **Disk use.** Each matchup adds 1.9 GB. The 20 examples would be about
  39 GB; there is 1.2 TB free.
- Q1. I see the two figures now live in `papers/bbp/figs/`. The scripts still
  write new figures to `papers/bbp/py/`. Shall I point `DEFAULT_OUT_DIR` in
  `plot_L1B.py` and `explore_cdom.py` at `papers/bbp/figs/`? I recommend yes.

### Atmospheric Corrections

#### 1. Plan for running `l2gen` on the L1B of 5906209 / 224 (2026-11-24)

Nothing has been downloaded, installed or run. This is the proposal and the
decisions I need from you.

**The granule.** The matchup used `PACE_OCI.20260417T015116.L2.OC_AOP.V3_2.nc`.
The co-temporal L1B is `PACE_OCI.20260417T015116.L1B.V3.nc` (collection
`PACE_OCI_L1B_SCI`, about 1.8 GB). PAB has only ever read its geolocation by
byte range; no L1B file is on disk. The fitted pixel is PAB `(ix, iy)` =
(1401, 1068), i.e. scan line 1401 and pixel 1068 (0-based), at 45.08° S,
178.31° W. The scene is 81 % cloud, θ_s = 62°, θ_v = 48.7°.

**What the tutorial does** (I read the main page; the install steps are on a
separate prerequisite page I have not read):

1. Source `$OCSSWROOT/OCSSW_bash.env` in every subprocess.
2. Get the L1B with `earthaccess` (the tutorial reads it from S3; we would
   download the file).
3. `getanc --use_filename <L1B name> --ofile l2gen.anc --noprint`. This fetches
   the MERRA-2 met, profile and aerosol files, ozone, SST and sea ice for the
   granule time and writes them as a par file. Without it `l2gen` falls back
   to climatology and will not reproduce the NASA product.
4. `l2gen par=l2gen.par par=l2gen.anc`, where `l2gen.par` holds `ifile`,
   `ofile`, a lat/lon box (`north/south/east/west`) and `l2prod`. The suite
   default is `OC`, read from `share/oci/msl12_defaults.par`.
5. Compare with the NASA L2 file. The tutorial reports identical Rrs apart
   from a few stray points.

The tutorial's subset (382 lines × 136 pixels) ran at 0.6–1.4 scans/s, so
several minutes. A small box around our pixel should take about a minute.

**State of the local OCSSW install (`$OS_COLOR/ocssw`).** It is not runnable:

| piece | present? |
|---|---|
| installer (`install_ocssw`, tag **V2026.4**, installed 2026-08-01) | yes |
| source code (`ocssw_src`, `opt/src`) | yes |
| `share/common` (9.8 GB) | yes, but the first attempt timed out; a rerun reported Done |
| `bin/` (compiled `l2gen`, `getanc`, …) | **no** |
| `lib/` and compiled `opt/` libraries | **no** |
| `share/oci` (OCI aerosol and Rayleigh tables, gains, gas transmittance) | **no** |
| `var/anc` (ancillary cache) | no (created by `getanc`) |

`OCSSWROOT` is not set in the shell, and Docker is not installed.

**What I would need to install.** The installer offers pre-built binaries for
`macosx_arm64`, which is this machine, so no compiling and no Docker:

```
cd $OS_COLOR/ocssw
./install_ocssw --install_dir $OS_COLOR/ocssw --tag V2026.4 --seadas --oci
```

`--seadas` should add the `bin`, `lib` and `opt` bundles for this
architecture; I will confirm that from the installer before running it. I do
not know the download size; I expect a few GB, mostly the OCI aerosol tables.
There is 1.2 TB free. No Python packages need installing: `earthaccess` is
already in `ocean14`, and `~/.netrc` exists for the Earthdata login that
`getanc` needs. I would not edit your shell profile; the scripts would set
`OCSSWROOT` and source the env file themselves.

**Where the products would go (proposal).** Outside `v2/`, so the release tree
stays untouched:

```
$PAB_DATA_DIR/scrutinize/l2gen/5906209_224/
    l1b/    PACE_OCI.20260417T015116.L1B.V3.nc        (1.8 GB)
    nasa/   PACE_OCI.20260417T015116.L2.OC_AOP.V3_2.nc (~0.3 GB, the reference)
    anc/    l2gen.anc + the ancillary files
    runs/<run_name>/  l2gen.par, the L2 output, the log
```

Each run gets a name (`baseline`, `brdf0`, …) and keeps its par file beside
its output, so every result is reproducible. Code would go in
`papers/bbp/py/` next to `explore_cdom.py`.

**Proposed sequence of work:**

1. Install the missing bundles and check `l2gen --help` runs.
2. Download the L1B and the NASA L2 for this granule.
3. Run `getanc`.
4. **Baseline:** run `l2gen` with defaults on a box around the pixel and check
   it reproduces the NASA `Rrs` at pixel (1401, 1068). Until this matches, no
   perturbation result means anything.
5. Output diagnostics as well as `Rrs`, so we can see the size of each
   correction at 600–700 nm: aerosol optical depth and Ångström exponent,
   the aerosol, Rayleigh and glint radiances, the transmittances, the BRDF
   factor and `l2_flags`. I will take the exact product names from
   `get_product_info`.
6. Then perturb one setting at a time and refit with BING.

**Points that bear on bbp(700):**

- **Version match.** The NASA file was made with whatever `l2gen` build and
  tables defined V3.2. The local tag is V2026.4 and the tutorial page shows
  V2026.5. The NASA L2 file records its software version and input
  parameters, so I would read those first and diff them against our defaults.
- **BRDF.** The tutorial confirms the default is `brdf_opt=7` (Morel f/Q plus
  Fresnel), which is what the v2.1 "normalized geometry" fits assume.
  `brdf_opt=0` is the obvious first perturbation: on this pixel, switching our
  assumed geometry moved bbp(700) by 43 %.
- **Aerosol.** The default is `aer_opt=-18` with the 751 and 870 nm bands.
  Any error in the aerosol extrapolation is largest in relative terms where
  Rrs is small, which is the red. The 1 σ red deficit in the BING fit is the
  kind of offset an aerosol error would produce.
- **Gas correction.** The data dip at ~688–690 nm in the CDOM figure sits on
  the O₂ B band. `gas_opt` and `oxaband_opt` are worth a look.
- **Scene.** 81 % cloud and a 62° sun: stray light and cloud adjacency are
  plausible, and `l2gen` cannot remove them. The flags will tell us whether
  the pixel was marked.
- **Uncertainty.** The tutorial runs with `proc_uncertainty=0` and its output
  has no `Rrs_unc`. BING needs σ, so I would either turn it on or reuse the
  NASA `Rrs_unc` for perturbed runs. I would test which works.

**Questions:**

- Q1. Is `$PAB_DATA_DIR/scrutinize/l2gen/5906209_224/` acceptable for the
  products, or do you want them elsewhere (e.g. under `$OS_COLOR/PACE`)?
>A. Let's use `$PAB_DATA_DIR/scrutinize/5906209_224/`

- Q2. May I run the installer in `$OS_COLOR/ocssw` to add the binaries and the
  OCI tables? And which tag: stay on **V2026.4** (already installed, my
  recommendation unless the NASA file says otherwise) or move to the latest?
>A. Let's stay on **V2026.4**

- Q3. The fit records show the v2.1 fits were written from a Linux machine
  (`/home/xavier/...`). If the macOS binaries fail on this OS version, is that
  machine available as a fallback, and does it have OCSSW?
>A. It is available, but hopefully we can run on my Mac
- Q4. Subset size: I propose a box of about ±0.25° around the pixel, enough to
  see spatial context and all 10 matchup pixels. Is that right, or do you want
  the full granule?
>A. Let's do the full granule
- Q5. For the first perturbations I propose, in order: `brdf_opt=0`, then the
  aerosol option, then the gas/O₂ options. Do you have a different priority?
>A. I will decide on the priority and specify them with prompts

#### 2. Installing `l2gen` on the Mac (2026-11-24)

**Result: `l2gen` is installed and runs on this Mac** (`msl12 10.3.0-V2026.4`,
built 2026-07-27). `getanc` and `get_product_info` also start. No L1B has been
downloaded and no processing has been run.

**Your answers, as I have applied them:**

- Products go in `$PAB_DATA_DIR/scrutinize/5906209_224/` (created, empty).
- Tag stays at V2026.4.
- Run on the Mac; the Linux machine was not needed.
- Full granule, not a subset, when we run `l2gen`.
- You will specify the perturbations by prompt; I will not start any.

**What I installed:**

1. In `$OS_COLOR/ocssw`:
   `./install_ocssw --install_dir $PWD --tag V2026.4 --seadas --oci`.
   This added the `macosx_arm64` binaries (`bin/`, 196 programs), `lib/`,
   compiled `opt/` (2.1 GB), `share/oci` (4.6 GB) and `share/ocrvc`. The tree
   is now 17 GB. Log: `$OS_COLOR/ocssw/install_20261124.log`.
2. A small conda prefix, `$OS_COLOR/ocssw_x11` (7.9 MB), holding four X11
   libraries. See the first problem below.
3. `papers/bbp/py/ocssw_env.sh`: source it to get `OCSSWROOT`, the OCSSW
   environment and the library path in the current shell. It changes nothing
   permanently. Tested in zsh and bash.

**Two problems met, both worked around:**

- **Missing X11 libraries.** The NASA binaries are linked against XQuartz
  (`/opt/X11/lib/libSM`, `libICE`, `libX11`, `libXext`), which is not on this
  Mac, so `l2gen` would not start. Rather than install XQuartz (a system
  installer needing your password) or add packages to `ocean14` or Homebrew, I
  put the four libraries in their own conda prefix and pointed
  `DYLD_FALLBACK_LIBRARY_PATH` at it. Deleting `$OS_COLOR/ocssw_x11` undoes it.
- **LUT update failed inside the installer.** Its last step (`update_luts oci`)
  ran under a login shell whose Python had no `requests`, so the installer
  exited with status 1 after all eight bundles were in place. I reran
  `update_luts oci` under `ocean14` and it returned 0.

**Not yet tested:**

- An actual `l2gen` run. Starting and printing the version proves the binary
  and its libraries load; it does not prove the OCI tables are complete or
  that a full granule processes correctly on this OS.
- `getanc` downloading ancillary files with your Earthdata login.
- Whether V2026.4 reproduces the NASA V3.2 Rrs. The defaults file names the
  gain table `oci_gains_v3.2_20260501.nc`, which is encouraging, but only the
  baseline comparison settles it.

**Concerns and questions:**

- C1. Are you content with the `ocssw_x11` workaround, or would you rather
  install XQuartz yourself (`brew install --cask xquartz`) so the binaries
  resolve their libraries the way NASA intends? Both work; XQuartz is the
  supported route.
>A. The workaround is fine for now.  I have also installed XQuartz on my Mac, but it 
won't take effect until I log out and back in. 
- C2. A full granule is 1709 scans. The tutorial reports 0.6–1.4 scans/s for
  `Rrs` only, so expect roughly 20–50 minutes per run on comparable hardware,
  and longer with diagnostic products. That is per perturbation. A subset
  around the pixel would take about a minute; say if you want that option
  kept for the perturbation runs after a full-granule baseline.
>A. Ok, let's allow for a subset around the pixel.
- Q1. Next step, when you are ready: download the L1B (1.8 GB) and the NASA L2
  (0.3 GB) into `$PAB_DATA_DIR/scrutinize/5906209_224/`, run `getanc`, and run
  the default baseline on the full granule. Shall I go ahead with all three in
  one prompt?
>A. Yes, I am constructing this prompt and will ask you to execute it.
- Q2. For the baseline, which outputs do you want beyond `Rrs` and
  `l2_flags`? I suggest adding the aerosol optical depth and Ångström
  exponent and the uncertainty (`proc_uncertainty` on), so the file can be
  compared with NASA's `Rrs_unc` and fed to BING unchanged.
>A. Agreed, let us add the aerosol optical depth and Ångström exponent and the uncertainty (`proc_uncertainty` on).

### CDOM

#### 1. Was CDOM fluorescence included in the BING fit of 5906209 / 224? (2026-11-24)

**Answer: No.** Neither BING fit of this matchup included CDOM fluorescence, and
no BING fit in `pab.db` does.

**Evidence (read from `$PAB_DATA_DIR/v2/pab.db`, table `fits`, read-only):**

| fit | rt_backend | Raman | Chl fl | **CDOM fl** | phi_C | fit_Bp | geometry | bbp700 (m⁻¹) [5–95 %] |
|---|---|---|---|---|---|---|---|---|
| `…_1401_1068_ExpBPow_v2.0` | robust_hybrid | 1 | 1 | **0** | 0.02 | 1 | observed (θ_s = 62°, θ_v = 48.7°) | 1.40e-3 [1.26, 1.52] |
| `…_1401_1068_ExpBPow_v2.1` | robust_hybrid | 1 | 1 | **0** | 0.02 | 1 | normalized (0, 0, 0) | 2.01e-3 [1.83, 2.18] |

- Matchup: `5906209_224_PACE_OCI.20260417T015116.L2.OC_AOP.V3_2.nc`, pixel
  (1401, 1068), 2.0 km and 3.0 h from the profile (45.1° S, 178.3° W).
- Argo MLD-mean bbp700 = 1.05e-3 m⁻¹ (adjusted mode, MLD = 50 m). So PACE/Argo
  ≈ 1.9 for the 2.1 fit and ≈ 1.3 for the 2.0 fit.
- Across the whole database, `include_cdom_fl = 0` on all 15,971 v2.0, 51 v2.0.1
  and 15,971 v2.1 BING fits. There is no fit with it on.
- The fit-chain NPZ files carry no RT flags (only `chains`, `wave`, `Rrs`,
  `varRrs`, `param_names`, `Chl`); the `fits` table is the record.

**Why it was off.** It is a deliberate default, not an oversight:
`FitConfig.include_CDOM_fl = False` in `pab/fit/models.py`, with the stated
reason that the Hawes kernel needs a pure-CDOM source term that BING can only
approximate as `cdom_fraction * a_dg`.

**What the machinery can do if we switch it on.** The path exists end to end:

- *retrieve-or-bust* has `robust.rt.cdom_fl.cdom_kernel` — the Hawes (1992) FA7
  kernel, added to the hybrid forward model as
  `Rrs_total = (Rrs_ZTT + ΔRrs)·f_R + Rrs_chlfl + scale·K_cdom`.
- *BING* exposes it as `rt_dict['include_CDOM_fl']` (robust_hybrid only), with
  `scale` fixed at 1.0 and `a_cdom = cdom_fraction × a_dg`, `cdom_fraction` = 0.8
  by default. ExpBricaud has a separable `a_dg`, so our model pair qualifies.
- *PAB* passes the flag through and stamps it in `fits.include_cdom_fl`.

**Caveats that bear on whether the term can answer the question:**

1. **It is unvalidated.** retrieve-or-bust's `limitations.md` says the term is
   "present and unmeasured": implementation-checked only, no HydroLight truth
   (M6 blocked), and the learned correction δ_C is untrained and unwired.
2. **Excitation is clamped to 350–490 nm**, so UV-excited emission is dropped.
   That mostly costs the blue (57 % of nominal emission at 400 nm); I expect it
   to matter less at 700 nm, but that is not quantified.
3. **The amplitude is not fitted.** With `scale` = 1 and `cdom_fraction` = 0.8
   fixed, the fluorescence is tied rigidly to the retrieved `a_dg`. The Hawes
   constants are from one Gulf of Mexico fulvic-acid station (FA7); this pixel
   is the Southern Ocean subantarctic zone.
4. **No in-situ CDOM here.** `mld_summary.cdom` is NULL for this profile, so the
   float gives no independent check on `a_cdom` for this matchup.

**First impressions on the physics (back-of-envelope, not a model run):**

- From the FA7 constants, the Hawes emission at 700 nm is roughly 7–10 % of its
  peak for excitation across 400–490 nm. The red tail is small but not zero,
  and Rrs(700) is itself very small, so the fractional effect could be
  non-trivial.
- The sign is right for the bias we see: an unmodelled additive source in the
  red would be absorbed by a higher bbp, pushing PACE above Argo.
- But bbp700 here is not set by Rrs(700) alone. It is a power law (`Bnw`,
  `beta`) constrained by 136 bands over 400–700 nm, and CDOM fluorescence is
  strongest in the blue-green, where it would trade against `Adg`/`Sdg` and
  `Aph`. The net effect on bbp700 could go either way and needs a refit.
- The larger lever on this pixel so far is geometry: bbp700 rose 43 % from 2.0
  to 2.1 (observed → normalized angles), and θ_s = 62° is a high sun angle.

**Questions for you before I run anything:**

- Q1. For the first test, should I refit this pixel at the 2.1 configuration
  with only `include_CDOM_fl=True` added (`cdom_fraction` = 0.8), and compare
  bbp700 and the Rrs residuals against the stored 2.1 fit? I recommend this,
  preceded by a forward-only evaluation of `scale·K_cdom(λ)` at the stored 2.1
  posterior median so we see the size of the term relative to Rrs before
  refitting.
>A. Let's make a plot or two before refitting
- Q2. Should I also bracket the unknown amplitude, e.g. `cdom_fraction` in
  {0.4, 0.8, 1.0}, since `scale` is not fitted?
>A. We will keep `scale=0.8` for now
- Q3. The NPZ `Chl` (the a_ph shape seed) is 0.663 mg m⁻³, the raw float chla;
  the adjusted value is 0.183. Is the raw value the intended seed? It is
  outside the CDOM question but affects the Chl-fluorescence term in the same
  red bands.
>A. Do not worry about the Chl seed for now.

#### 2. The stored model with CDOM fluorescence switched on (2026-11-24)

**Result: the CDOM-fluorescence term is negligible in the red for this pixel.**
At 700 nm it adds 5e-7 sr⁻¹, which is 0.2 % of the model Rrs and 0.005 σ.

Module: `papers/bbp/py/explore_cdom.py`. Figure:
`papers/bbp/py/fig_explore_cdom_5906209_224.png`.

**What the script does.** It takes the stored v2.1 posterior (no refit) and runs
it through the forward model twice: once as fitted, and once with only
`include_CDOM_fl=True` changed. Geometry, Raman, Chl fluorescence, `B_p` and
the posterior samples are identical. Each curve is the per-band median over
the posterior samples; the band is the 5–95 % range of the as-is model.

**Size of the term (CDOM on − as is, posterior median):**

| λ (nm) | Rrs obs | model as is | Δ from CDOM fl. | Δ / model | Δ / σ |
|---|---|---|---|---|---|
| 400 | 6.36e-3 | 6.87e-3 | 7.8e-6 | 0.1 % | 0.01 |
| 440 | 4.75e-3 | 4.57e-3 | 2.2e-5 | 0.5 % | 0.04 |
| 490 | 4.25e-3 | 4.25e-3 | 4.7e-5 | 1.1 % | 0.15 |
| 550 | 2.28e-3 | 2.29e-3 | 3.9e-5 | 1.7 % | 0.22 |
| 613 | 5.14e-4 | 4.56e-4 | 5.9e-6 | 1.3 % | 0.04 |
| 650 | 4.66e-4 | 3.30e-4 | 2.5e-6 | 0.7 % | 0.02 |
| 679 | 4.56e-4 | 3.75e-4 | 9.7e-7 | 0.3 % | 0.01 |
| 699 | 3.30e-4 | 2.42e-4 | 5.3e-7 | 0.2 % | 0.00 |

- The term peaks in the blue-green (490–550 nm) at 1–2 % of Rrs, about 0.2 σ.
- χ²_ν goes from 0.36 to 0.39 with CDOM on. That is expected without a refit:
  the model was already slightly above the data at 530–580 nm and the term
  pushes it further.
- The term falls off faster toward the red than my earlier estimate from the
  Hawes emission shape alone, because water absorption at 700 nm strongly
  attenuates the emitted light.

**What this means for bbp(700):**

- The figure shows a coherent red deficit: the model sits about 1 σ below the
  data from ~640 to 685 nm (1.4e-4 sr⁻¹ at 650 nm). The CDOM term at 650 nm is
  about 55 times too small to fill it, and about 165 times too small at 699 nm.
- So CDOM fluorescence, with this kernel at `scale` = 1, cannot directly
  explain the red residual or pull bbp(700) down through the red bands.
- An indirect effect is still possible: a 1–2 % addition at 490–550 nm lets the
  fit trade a little `Adg`/`Aph` against `Bnw`/`beta`. At 0.2 σ I expect that
  shift in bbp(700) to be well inside the current 5–95 % interval, but only a
  refit would measure it.

**Concerns and questions:**

- C1. Your answer to Q2 said `scale=0.8`. I took that to mean
  `cdom_fraction` = 0.8 (BING's default), with the kernel `scale` left at 1.0.
  If you meant kernel `scale` = 0.8, the term is 20 % smaller still.
- C2. This is one low-CDOM pixel (`a_dg(400)` ≈ 0.019 m⁻¹). The term scales with
  `a_dg`, so the conclusion may not carry to high-CDOM matchups. The script
  takes any `<wmo> <cycle>`.
- C3. The kernel is unvalidated and the excitation is clamped at 350 nm, so the
  absolute amplitude is uncertain. A factor-of-two error would not change the
  conclusion at 700 nm; a factor of ~100 would be needed.
- Q4. Given this, do you still want the refit with CDOM fluorescence on for
  this pixel? My recommendation is to skip it here and instead run the script
  on one or two high-`a_dg` matchups to see whether the term ever matters.
- Q5. The red deficit at 640–685 nm resembles the "bad" fit in the AWOC talk
  (2902882 / 96). Is that the next thing to scrutinize, e.g. atmospheric
  correction in the red, or the Chl-fluorescence amplitude (`phi_C` fixed at
  0.02)?

## Logs

### 2026-11-24 (CDOM prompt 1: was CDOM fluorescence in the BING fit of 5906209/224?)

Read the Context repos and the v2 outputs; no fits were run and nothing in
`$PAB_DATA_DIR` was modified (pab.db opened read-only).

- **Finding:** CDOM fluorescence was **not** included. Both BING fits of the
  matchup (`…_1401_1068_ExpBPow_v2.0` and `_v2.1`) have `include_cdom_fl = 0`,
  with `rt_backend = robust_hybrid`, Raman on, Chl fluorescence on
  (`phi_C` = 0.02), `fit_Bp` on. The same holds for every BING fit in pab.db
  (15,971 + 51 + 15,971).
- **Where the truth lives:** the RT flags are in the `fits` table of pab.db,
  not in the chain NPZ files. The default comes from
  `FitConfig.include_CDOM_fl = False` in `pab/fit/models.py`.
- **Capability:** `robust.rt.cdom_fl` (Hawes 1992 FA7 kernel) is wired through
  BING (`rt_dict['include_CDOM_fl']`, `a_cdom = cdom_fraction × a_dg`, default
  0.8, `scale` fixed at 1) and PAB. ExpBricaud qualifies. The term is
  unvalidated per retrieve-or-bust `docs/using/limitations.md`, and excitation
  is clamped to 350–490 nm.
- **Matchup numbers:** BING bbp700 = 1.40e-3 (2.0) and 2.01e-3 m⁻¹ (2.1); Argo
  MLD mean = 1.05e-3 m⁻¹; float CDOM is NULL for this profile; L1B geometry
  θ_s = 62°, θ_v = 48.7°.
- **Noticed in passing:** the NPZ `Chl` seed is the raw chla (0.663), not the
  adjusted value (0.183). Raised as Q3 in Q&A/CDOM.
- Wrote the assessment and three questions in Q&A/CDOM. Logged here rather
  than in `claude_prompts/start_up.md` because this doc has its own Logs
  section.


### 2026-11-24 (CDOM prompt 2: stored model with CDOM fluorescence switched on)

Wrote `papers/bbp/py/explore_cdom.py` and produced
`papers/bbp/py/fig_explore_cdom_5906209_224.png`. No refit; pab.db and the
chains were only read.

- **Method:** the stored v2.1 posterior of 5906209/224 is pushed through the
  forward model twice, as fitted and with only `include_CDOM_fl=True` changed
  (`cdom_fraction` = 0.8, kernel `scale` = 1). The models are built the same
  way as `pab.plotting.fit_fig.reconstruct_posterior`, with the config changed
  through `dataclasses.replace`. Figure: data, as-is median and 5–95 % band,
  CDOM-on median, a 610–700 nm inset, and residuals/σ for both.
- **Finding:** the CDOM term peaks at 490–550 nm at 1–2 % of Rrs (about
  0.2 σ) and is 0.2 % of Rrs (0.005 σ) at 700 nm. χ²_ν 0.36 → 0.39 without a
  refit.
- **Learned:** the model sits about 1 σ below the data over 640–685 nm; the
  CDOM term is 55–165 times too small to fill that deficit. Water absorption
  suppresses the red tail of the emission more than the Hawes emission shape
  alone suggests.
- **Open:** interpreted the user's "scale=0.8" as `cdom_fraction` = 0.8 (C1 in
  Q&A/CDOM 2). Recommended skipping the refit on this pixel and testing a
  high-`a_dg` matchup instead (Q4), and asked whether the red deficit is the
  next target (Q5).
- **Practical:** each forward pass over the thinned posterior takes well under
  a minute; the script accepts `<wmo> <cycle>` on the command line.

### 2026-11-24 (Atmospheric Corrections prompt 1: plan for `l2gen` on 5906209/224)

Discussion only: nothing downloaded, installed or run. Wrote the plan and five
questions in Q&A/Atmospheric Corrections 1.

- **Tutorial:** read the NASA `l2gen` page through a fetch agent. The page is
  long and parts came back as summaries rather than verbatim text, and the
  last ~13k characters were not read. The workflow is: source
  `OCSSW_bash.env`, get the L1B, `getanc --use_filename <L1B> --ofile
  l2gen.anc`, then `l2gen par=l2gen.par par=l2gen.anc`. Defaults for OCI are
  suite `OC`, `aer_opt=-18` (751/870 nm), `brdf_opt=7`, `gas_opt=495`,
  `glint_opt=3`. The install steps are on a separate page, not read.
- **Local OCSSW (`$OS_COLOR/ocssw`):** tag V2026.4, installed 2026-08-01, but
  only the installer, the source trees and `share/common` (9.8 GB). There is
  no `bin/`, no `lib/`, no compiled `opt/` and no `share/oci`, so `l2gen` and
  `getanc` cannot run yet. The installer lists pre-built `macosx_arm64`
  bundles. `OCSSWROOT` is unset; Docker is absent; `~/.netrc` exists.
- **Granule:** L1B is `PACE_OCI.20260417T015116.L1B.V3.nc` (~1.8 GB), not on
  disk. PAB `(ix, iy)` = (scan line, pixel) = (1401, 1068), 0-based.
- **Proposed:** products under `$PAB_DATA_DIR/scrutinize/l2gen/5906209_224/`;
  first reproduce the NASA Rrs at the pixel, then perturb `brdf_opt`, the
  aerosol option and the gas/O₂ options one at a time.
- **Unverified:** that `--seadas --oci` pulls the right bundles, the download
  size, the exact diagnostic product names, and whether the macOS binaries
  run on this OS version.

### 2026-11-24 (Atmospheric Corrections prompt 2: installed `l2gen` on the Mac)

`l2gen` now runs locally: `msl12 10.3.0-V2026.4`. No L1B downloaded, no
processing run.

- **Install:** `./install_ocssw --install_dir $PWD --tag V2026.4 --seadas
  --oci` in `$OS_COLOR/ocssw`. `--seadas` turns on `root`, `bin`, `opt`,
  `luts`, `common` and `ocrvc` (read from the installer source). Added
  `bin/` (196 programs), `lib/`, compiled `opt/` (2.1 GB), `share/oci`
  (4.6 GB). Tree is 17 GB. Log in `$OS_COLOR/ocssw/install_20261124.log`.
- **Learned 1:** the macOS binaries link to XQuartz paths
  (`/opt/X11/lib/libSM.6`, `libICE.6`, `libX11.6`, `libXext.6`) and to
  Homebrew's gfortran runtime. XQuartz is absent; Homebrew has `libX11` and
  `libXext` but not `libSM` or `libICE`. dyld falls back to
  `DYLD_FALLBACK_LIBRARY_PATH` by leaf name, so a conda prefix with
  `xorg-libsm xorg-libice xorg-libx11 xorg-libxext`
  (`$OS_COLOR/ocssw_x11`, 7.9 MB) fixes it without touching `ocean14`,
  Homebrew or the system.
- **Learned 2:** the installer's final `update_luts oci` step runs through
  `ocssw_runner`, a `bash -l` script, whose `python3` lacked `requests`; the
  installer exits 1 even though every bundle installed. Rerunning
  `update_luts oci` with `ocean14` first on the path returns 0.
- **Wrote:** `papers/bbp/py/ocssw_env.sh` (source it to set `OCSSWROOT`, the
  OCSSW env and the library path). Created the empty product folder
  `$PAB_DATA_DIR/scrutinize/5906209_224/`, per the user's answer.
- **Not tested:** a real `l2gen` run, `getanc` downloads, agreement with the
  NASA V3.2 Rrs.
- **Open:** whether to keep the `ocssw_x11` workaround or install XQuartz;
  full-granule runtime (about 20–50 min per run by the tutorial's rate);
  go-ahead for download + `getanc` + baseline.

### 2026-11-24 (Atmospheric Corrections prompt 3: L1B downloaded, plot proposal)

Downloaded the L1B; wrote the plotting proposal in Q&A/Plot L1B 1. No plotting
code yet, as instructed.

- **Download:** `PACE_OCI.20260417T015116.L1B.V3.nc` (1.93 GB, processing
  version 3.0.2) into `$PAB_DATA_DIR/scrutinize/5906209_224/l1b/`, using
  `pab.pace.l1b.l1b_source_for_aop` for the URL and
  `pab.pace.cloud.download_granule`.
- **Learned (file):** the L1B holds TOA **reflectance** (`rhot_blue/red/SWIR`),
  not radiance. `l2gen` converts with
  `Lt = rhot · F0 · cos(θ_s) / d² / π / 10` (mW cm⁻² µm⁻¹ sr⁻¹), in
  `ocssw_src/oel_hdf4/libl1/l1_oci.c`. 650 nm is red band index 24
  (649.65 nm). Grid is 1710 × 1272; pixel (1401, 1068) matches the stored
  lat/lon. HAM side 0 at that scan; tilt −19.8°.
- **Learned (flags):** the only L1B flags set are per-band saturation in the
  red bands 656–717 nm (1.9 % of pixels) and in the SWIR (1.2 %), plus the
  land mask. HAM-B striping, geolocation quality and scan quality are never
  set. No flag at our pixel; nearest saturated pixel ~30 pixels away.
- **Learned (scene):** `rhot(650)` = 0.054 at the pixel, median 0.31 over the
  granule. Cloud is within 5 pixels (up to 0.28) and covers 35 % of the
  ±50-pixel box. Stray light from saturated cloud in 656–717 nm is a live
  candidate for the red excess.
- **Open:** five questions on radiance vs reflectance, zoom, axes, whether to
  add L2 flags, and counting saturated bands.

### 2026-11-24 (Atmospheric Corrections prompt 4: L1B figure)

Wrote `papers/bbp/py/plot_L1B.py` and produced
`papers/bbp/py/fig_L1B_5906209_224.png`; discussion in Q&A/Plot L1B 2.

- **Built:** `plot_l1b(wmo, cycle, half_width, out)`. Left panel: TOA
  reflectance at the red band nearest 650 nm (649.6 nm), log grey scale.
  Right panel: categories for red saturation, SWIR saturation, both, and
  land. The matchup, pixel and Argo position come from `pab.db`; only the box
  is read from the 1.9 GB file.
- **Learned:** a box in pixels is misleading here. ±200 pixels was
  1078 × 483 km, because at θ_v ≈ 49° the sampling is ~2.1 km/pixel
  across-track and ~1.2 km/scan. Changed the argument to a half-width in km
  (default 200 → scans 1236–1566, pixels 960–1147, 399 × 399 km) and set the
  image aspect so the box is square on the ground.
- **Finding:** the pixel is in a clear lane within broken cloud
  (`ρt(650)` = 0.054; box median 0.078). In the box 0.33 % of pixels have a
  saturated red band (655.8–716.8 nm only), 0.37 % are land, and the nearest
  saturated pixel is 46 km away. No flag at the pixel. Unsaturated cloud at
  `ρt` ≈ 0.3 is within a few pixels, which the L1B flags do not capture.
- **Open:** whether to make a tighter zoom, and whether to add a
  cloud-adjacency proxy panel.

### 2026-11-24 (Find examples prompt 1: matchups like 5906209/224 with less cloud)

Wrote `papers/bbp/py/find_examples.py`; table and discussion in
Q&A/Find examples 1. Read-only on pab.db.

- **Method:** joins `fits` (BING, v2.1, success), `fit_results`
  (`BING_ExpBPow_bbp700`), `matchups`, `matchup_pixels`, `profiles`,
  `mld_summary` and `granules`. Hard cut `cloud_cover < 50`; rank by
  `sqrt(ln(argo/1e-3)² + ln(ratio/2)²)`. Prints wmo, cycle, date, pixel
  lat/lon, cloud %, Argo and PACE bbp(700), ratio, Δx, Δt, χ²_ν, score.
- **Numbers:** 15,189 v2.1 matchups have finite positive Argo and PACE
  bbp(700); 3066 pass the cloud cut. The top 20 are all within 10 % of both
  targets.
- **Learned:** granule cloud cover does not separate the bias. Median
  PACE/Argo is 1.33 below 50 % cloud and 1.34 overall; 22 % of low-cloud
  matchups with Argo bbp near 1e-3 have a ratio of 1.6–2.5. Truly clear
  granules are scarce (5th percentile of cloud cover is 38 %).
- **Noticed:** the top 20 cluster in the Mediterranean, the equatorial
  Pacific and off Central America, with several floats repeated.
- **Open:** whether to add Δt / χ² / one-per-float filters, and which
  examples to carry to the L1B plot.

### 2026-11-24 (Find examples prompt 2: Δt ≤ 3 h and one matchup per float)

Updated `papers/bbp/py/find_examples.py` per the user's answers; new table in
Q&A/Find examples 2.

- **Changes:** hard cut `|dtime_hours| <= 3` (`DTIME_MAX`, argument
  `dtime_max`); after sorting by score, `drop_duplicates("wmo")` keeps each
  float's best matchup (`one_per_float=True`). The header line now prints the
  count after each cut.
- **Numbers:** 15,189 → 3066 (cloud < 50 %) → 894 (|Δt| ≤ 3 h), 238 floats.
  `dtime_hours` is stored as a non-negative value (0.001–24 h), so the
  absolute value in the cut is a safeguard only.
- **Learned:** with one per float the list still leans on the Mediterranean
  (10 of 20); the rest are the Arabian Sea (3), the north-east Atlantic off
  West Africa (3), the equatorial Pacific (2), Central America (1) and the
  Tasman Sea (1). The top four are within 5 % of both targets; by row 20 the
  match is within ~20 %.

### 2026-11-24 (Plot L1B prompt 1: download a missing L1B)

Modified `papers/bbp/py/plot_L1B.py`; discussion in Q&A/Plot L1B 3.

- **Change:** `l1b_path(wmo, cycle, m, download=True)` now returns the local
  file if present and otherwise resolves the URL with
  `pab.pace.l1b.l1b_source_for_aop(granule_id)` and fetches it with
  `pab.pace.cloud.download_granule` into
  `$PAB_DATA_DIR/scrutinize/<wmo>_<cycle>/l1b/`. `plot_l1b` gained a
  `download` argument.
- **Tested:** existing granule reused; URL and pixel resolve for
  2903797 / 160 (scan 334, pixel 831); `download=False` raises. **Not
  tested:** a real download through the new path (avoided an unrequested
  1.9 GB fetch).
- **Decision to confirm:** the prompt said "`DEFAULT_OUT_DIR`", which in the
  script is the figure folder inside the repo. Kept the data under
  `$PAB_DATA_DIR/scrutinize/` and flagged it (C1).
- **Noticed:** the user moved the figures to `papers/bbp/figs/`; the scripts
  still write to `papers/bbp/py/`. Asked whether to repoint them (Q1).

### 2026-11-24 (Figures now written to `papers/bbp/figs/`)

At the user's request, `DEFAULT_OUT_DIR` in `papers/bbp/py/plot_L1B.py` and
`papers/bbp/py/explore_cdom.py` now points to `papers/bbp/figs/` (created if
absent) instead of the script folder. Both scripts were rerun and rewrote
`fig_L1B_5906209_224.png` and `fig_explore_cdom_5906209_224.png` there. The
L1B data location (`$PAB_DATA_DIR/scrutinize/<wmo>_<cycle>/l1b/`) is unchanged.
