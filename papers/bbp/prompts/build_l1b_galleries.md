# Build PACE L1B Galleries

## Goals

This prompt doc will be used to build image galleries of PACE L1B data.
We will make ones for various regions in the PACE/Argo bbp(700)
matchup space.

## Context

- `Oceanography/python/bing` holds the Bayesian fitting code for IOP retrievals
- `Oceanography/python/retrieve-or-bust` holds the radiative transfer model code

We have fitted the PACE observations with BING using the ZTT RT model in retrieve-or-bust.

Outputs for the analysis are in `$PAB_DATA_DIR/v2`

Here is a tutorial for processing PACE L1B to L2 data with `l2gen`:
`https://nasa.github.io/oceandata-notebooks/notebooks/oci/oci_ocssw_l2gen.html`

On my Mac laptop, the folder `$OS_COLOR/ocssw` contains the OSSSW code.
On my workstation, it is `~Oceanography/ocssw/`.

Code in these modules in `py/` should be modified and reused as needed:
    - `py/find_examples.py` :: Queries the PAB database for matchups with select criteria
    - `py/plot_L1B.py` :: Generate a single L1B plot.  Downloads the data first as needed.

Matchups are defined to be within 10km of one another and within Dt<=3 hours of one another.

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

### Test gallery

1. Let's start by building a test gallery of PACE L1B data.  We will use the code
in `find_examples.py` to find matchups with the following criteria:
    - The Argo bbp(700) is approximately 1.0e-3 m-1
    - The PACE/Argo bbp(700) ratio is approximately 2
    - The time difference between the PACE and Argo measurements is Dt <=3 hours

    We should capture these criteria in a JSON file that will be input to the `find_examples.py` code.
We will create a new module named `py/l1b_gallery.py` which will contain the main() function and the functions
to build the gallery.   It will input the JSON file into the `find_examples.py` code and then 
use code in `plot_L1B.py` to generate a gallery of the L1B data.  
The test gallery should be named `figs/l1b_gallery_test.png`.
It will show 12 matchups in a 4x3 grid, easy to view on a Google Slide
(if you think a different sampling is better, let me know).
Each L1B plot should be at 650nm and show the TOA reflectance (no flags).
It should indicate the `wmo` and `cycle_ID` of the matchup. And `lat/lon`.
And the PACE and Argo bbp(700) values.  A scene of 400km on a side is preferred.
It should also indicate the Argo and PACE location.

    We are mainly generating these galleries to search for clouds in the L1B data.
    Before writing any code, discuss this with me in the `Q&A/Test Gallery` section below.
    Use Opus 5.5.  Log your work.

2. I have answered the first round of questions in the `Q&A/Test Gallery` section below.
Please review those and ask any additional questions you may have.  In addition, note:
    -  I want the JSON files to appear in the `bbp/galleries/` folder.
    -  Use dpi=300
    -  Let's reduce to 300km on a side from 400km

    Use Opus 5.5.  Log your work.

3. I have answered the next round of questions in the `Q&A/Test Gallery` section below.
Please review those, then 
write the code to build the test gallery.  Use Opus 5.5.  Log your work.
If any additional issues come up, discuss them with me in the `Q&A/Test Gallery` section below.

4. That is an excellent draft.  Let's make these changes:
    - Reduce the scene size to 200km on a side from 300km
    - Remove the cyan + marker on the Argo position 
    - Remove the orange circle on the PACE pixel.  Replace it with a single, small orange dot at its center location
    - Add a cyan, dotted circle centered on the Argo position with a radius of 20km
    - Reduce the size of the PACE circle from 50km to 30km.  Make it dotted too

    Use Opus 5.5.  Log your work.

### High 1e-3 gallery

1. The test gallery looks good.  We are ready to generate the gallery for the first 36 matchups
following the same criteria as the test gallery.  Create a new JSON file named 
`papers/bbp/galleries/high_1e-3.json` to guide the process.  And have the filenames for the figures be `figs/l1b_gallery_high_1e-3_#.png`.
If any issues arise,  discuss them with me in the `Q&A/High 1e-3` section below.
Use Opus 5.5.  Log your work.

### Matched 1e-3 gallery

1. Now, we wish to show the 36 matchups where the PACE/Argo bbp(700) ratio is approximately 1.
Before creating the figure, generate the JSON file and name it `papers/bbp/galleries/matched_1e-3.json`.
If you have any questions,  discuss them with me in the `Q&A/Matched 1e-3` section below.
Use Opus 5.5.  Log your work.

### Low 1e-3 gallery

1. Now, we wish to show the 36 matchups where the PACE/Argo bbp(700) ratio is approximately 0.5.
Before creating the figure, generate the JSON file and name it `papers/bbp/galleries/low_1e-3.json`.
Do not download or run the code yet.
If you have any questions,  discuss them with me in the `Q&A/Low 1e-3` section below.
Use Opus 5.5.  Log your work.

2. I have checked the JSON file and it looks good.  Now, run the code to build the gallery
after reading my answer in the `Q&A/Low 1e-3` section below.
Use Opus 5.5.  Log your work.

## Q&A

### Low 1e-3 gallery

#### 1. JSON created; not run (2026-11-24)

**JSON:** `galleries/low_1e-3.json` is `high_1e-3.json` with `ratio_target`
2.0 → **0.5**. Name, description and `out`
(`figs/l1b_gallery_low_1e-3.png` → `_1`, `_2`, `_3`) change; nothing else
does. It is registered as figure 4 in `py/l1b_gallery.py`, so
`python papers/bbp/py/l1b_gallery.py 4` will build it. **Nothing has been
downloaded or plotted.** The only thing I ran was the read-only database
selection (`find_examples`), to size the sample.

**The sample is thinner than the other two galleries.** Matchups within a
given score of the targets (Argo 1e-3; no cloud cut, |Δt| ≤ 3 h, one per
float):

| ratio target | score < 0.15 (~±15 %) | score < 0.3 (~±30 %) | score of rank 36 |
|---|---|---|---|
| 2 (high) | 48 | 134 | 0.130 |
| 1 (matched) | 47 | 155 | 0.120 |
| **0.5 (low)** | **16** | **57** | **0.228** |

For the low gallery's top 36, PACE/Argo runs **0.41–0.63** and Argo
bbp(700) runs 8.6e-4 to 1.2e-3. Ranks 1–12 are within ~13 % of both targets.
Rank 36 (1902605/311) has a ratio of 0.63, about a quarter of the way in log
space from 0.5 towards 1. The panels are still clearly "low", but the tail is
looser than in the other two galleries. 11 of its floats also appear in the
high gallery and 13 in the matched gallery, with different cycles. The run
will need up to 36 L1B downloads (~25 min, ~68 GB) unless some granules are
already cached.

**Question**

1. **Keep 36, or tighten?**
   - (a) Run as is: 36 panels, the looser tail labelled by rank only.
   - (b) Cut to 24 panels (2 pages). Rank 24 has score 0.17 and ratio 0.59.
   - (c) Keep 36 but add a cap such as `"score_max": 0.2` to the JSON. That
     would need a small change to `find_examples`, and would leave ~30
     panels.

   I lean towards **(a)**, so that the three galleries have the same size and
   can be compared like for like. The ratio is printed in every panel anyway
   (Argo and PACE values).

>A. Keep it at 36

#### 2. Gallery built (2026-11-24)

**Output:** `figs/l1b_gallery_low_1e-3_1.png`, `_2.png` and `_3.png`, from
`galleries/low_1e-3.json` unchanged (36 panels, per A1). Build them with
`python papers/bbp/py/l1b_gallery.py 4`.

- **Downloads:** 35 new L1B granules; one was already cached from an earlier
  gallery. The cache now holds 107 granules, 190 GB.
- **Edges:** 2 panels are padded at a granule edge (1902347/213 and
  7901086/8, both on page 3).

**One code change: retries on NASA CMR errors.** The run failed twice
part-way through, at different granules, because the CMR granule search
behind the download returned **HTTP 500 "An Internal Error has occurred"**.
That is a server-side problem, not ours. I added `fetch_l1b()` to
`l1b_gallery.py`: up to 4 attempts with a wait of 30 s, then 60 s, then
120 s. The third run hit the error once more, and the retry recovered it
within 30 s. Because cached granules are reused, the failed runs cost only
time.

### Matched 1e-3

#### 1. JSON and gallery built; one issue: OCI tilt change (2026-11-24)

**JSON:** `galleries/matched_1e-3.json` is `high_1e-3.json` with
`ratio_target` 2.0 → **1.0**: name, description and `out` change, nothing
else. Argo bbp(700) ≈ 1e-3, |Δt| ≤ 3 h, no cloud cut, one per float, top 36,
12 per page.

**Figures:** `figs/l1b_gallery_matched_1e-3_{1,2,3}.png`. Build them with
`python papers/bbp/py/l1b_gallery.py 3`. Ranks 1–36 have score ≤ 0.120:
ratios 0.91–1.12, Argo bbp(700) 8.9e-4 to 1.1e-3. 8 of the 36 floats also
appear in the high gallery, with different cycles. All 36 granules were new
downloads (~25 min); the L1B cache is now 72 granules, 128 GB.

**Issue: OCI tilt change.** The last panel, **1902347 / 131** (page 3), is
distorted: the circles are flattened ellipses and the pixel sits near the
bottom of the frame.
- **Cause:** its PACE pixel (scan 1132, 0.13° S) lies inside scans
  1114–1309, which the L1B `scan_quality_flags` marks **`tilt_change`**.
  OCI flips its tilt near the sub-solar latitude. During the flip,
  successive scans are stretched on the ground: along this pixel's column,
  the step grows from ~1.2 km per scan to ~4 km per scan within ~20 scans.
  The panel's single mean scale cannot represent that, so it is drawn
  wrong.
- **The same problem elsewhere:** I checked all 72 gallery matchups against
  the flag.
  - **5906574 / 66** (high gallery, rank 20) is also inside the tilt-change
    scans (scan 1212; flagged 1116–1310). My earlier "swath edge"
    explanation for its blockiness was wrong, and I have corrected it in
    High 1e-3 1.
  - **1902601 / 80** (matched, rank 35) is 77 scans from the flagged block.
    Its pixel is fine, but the lower edge of its box comes close to the
    flagged scans.
- **Why it matters beyond the figure:** the rhot of a tilt-change pixel
  averages over a stretched footprint, and its geometry is changing during
  the scan. Both the L2 Rrs we fitted and the 10 km matchup distance are
  suspect there. As far as I know, PAB does not currently test this flag:
  it is in the L1B, not the L2 AOP files we use.

**Questions**

1. **Galleries:** should I (a) leave the tilt-change matchups in and label
   the panel "tilt change", or (b) drop them and promote the next-ranked
   matchup? I lean towards **(a)** for these galleries, so that they stay a
   faithful view of the top-36 matchups, plus (c) below.
>A. Leave them in; I can still see the clouds.  
2. **Analysis:** do you want a check of how many v2.1 matchups fall in
   tilt-change scans? It needs only the L1B `scan_quality_flags` (a small
   read per granule) or the scan time of the flip, not the full 1.9 GB
   files. If the fraction is non-trivial, it is a candidate quality cut for
   the matchup database.
>A. No, I do not want to do this.  

**First read of the images** (not a measurement): the matched gallery has
more panels clear within 30 km of the pixel than the high gallery does. The
median granule cloud cover of its 36 is also lower (64 % against 74 %). That
fits the idea that the PACE > Argo excess is partly cloud-related, but both
numbers are coarse. A per-panel tally (clear / cloud within 30 km / cloud at
the pixel) for both galleries would test it properly. Should I set that up,
for example as a CSV you fill in by eye?

>A. No, do not set that up.  We don't have a way to reliably identify clouds.

### High 1e-3

#### 1. Gallery built (2026-11-24)

**Output:** `figs/l1b_gallery_high_1e-3_1.png`, `_2.png` and `_3.png` (ranks
1–12, 13–24, 25–36). Settings are in `galleries/high_1e-3.json`: the same
criteria and plot settings as `test.json`, with `n = 36` and
`n_per_page = 12`. Build it with `python papers/bbp/py/l1b_gallery.py 2`.

- **Downloads:** 24 new L1B granules, which took ~20 min. The cache
  `$PAB_DATA_DIR/L1B/` now holds 36 granules.
- **Page 1 is identical to `l1b_gallery_test.png`.** It has the same 12
  matchups and settings.
- **Score range:** the 36 run to score 0.130, i.e. both targets are matched
  to within ~13 %.

**Things worth a look** (my reading of the images; none needed a code
change):

1. **5906209 / 224 is rank 15** (page 2). That is the scrutinize reference
   matchup, the one `find_examples` was first written to find look-alikes
   of. The gallery shows the cloud we already knew about, so it is a good
   sanity check.
2. **4903660 / 89** (Arabian Sea, page 3) has bright, striped bands across
   the bottom of the panel, ~25 km south of the pixel. They look like **sun
   glint** with along-scan striping, not cloud. L1B carries no glint flag,
   so this gallery cannot tell glint from cloud. A `l2_flags` overlay
   (HIGLINT / CLDICE) would settle it. Want that as an option?
3. **3901578 / 116** (off West Africa, 10° N, page 3) is a uniform grey haze
   with faint streaks, most likely **Saharan dust** rather than cloud.
   Dust matters for the atmospheric correction just as cloud does, so it is
   worth tagging separately when you classify the panels.
4. **Edge padding** appears in 4 of the 36: 6902906/262, 5906469/152,
   2903464/51 and 5905505/217. 1902647/49 is clipped by only a sliver.
   5906574/66 and 1902647/49 are also near the swath edge, so their pixels
   are coarse and blocky.
   **Correction (Matched 1e-3 1):** 5906574/66 is blocky because its
   pixel is inside the OCI **tilt-change** scans, not because of the swath
   edge.

### Test gallery

#### 1. Plan for `py/l1b_gallery.py` and questions (2026-11-24)

No code has been written. I read `py/find_examples.py`, `py/plot_L1B.py` and
`talks/AWOC2026/fig_argo.py`, and ran `find_examples()` read-only against
`$PAB_DATA_DIR/v2/pab.db` to size the sample.

**What the criteria give** (v2.1 BING, rank-1 pixel, |Δt| ≤ 3 h, score =
log-space distance to Argo bbp = 1e-3 and PACE/Argo = 2):

| granule cloud cut | one per float | matchups | score < 0.3 | score < 0.5 |
|---|---|---|---|---|
| < 50 % (current default) | yes | 238 | 31 | 60 |
| < 50 % | no | 894 | 50 | 133 |
| none | yes | 614 | 134 | 268 |
| none | no | 3336 | 209 | 583 |

With no cloud cut and one per float, the top 12 are all within ~6 % of both
targets (score ≤ 0.057). They span the Med, the Pacific, the NE Atlantic, the
Indian Ocean and the Tasman Sea. Granule cloud cover ranges from 41 % to 89 %.

**Proposed design**

- **JSON** (`py/galleries/test.json`), passed straight to
  `find_examples.find_examples(**criteria)` plus gallery settings:
  ```json
  {
    "name": "test",
    "criteria": {"argo_target": 1.0e-3, "ratio_target": 2.0,
                 "dtime_max": 3.0, "cloud_max": null, "one_per_float": true},
    "selection": {"n": 12, "order": "score"},
    "plot": {"wave": 650.0, "half_width_km": 200.0, "ncols": 4, "nrows": 3},
    "out": "figs/l1b_gallery_test.png"
  }
  ```
  `cloud_max: null` needs a one-line change in `find_examples` so that `None`
  means no cut. That is the only change I would make there.
- **Reuse from `plot_L1B.py`:** `find_matchup`, `l1b_path` (download if
  missing), `load_l1b_box`, `_great_circle_km`. The panel drawing in
  `plot_l1b` is tied to its two-panel figure, so I would write a compact
  `draw_panel(ax, m, box, row)` in `l1b_gallery.py` rather than refactor
  `plot_L1B.py`.
- **Layout:** 4 columns × 3 rows, 16 × 9 in (16:9 for a Google Slide), 200 dpi.
  Each panel is the 400 km box on its scan/pixel grid, with the aspect set so
  it is square on the ground (as in `plot_L1B.py`). There are no tick labels;
  a 100 km scale bar is drawn instead. There is one shared colourbar.
- **Per-panel annotations:**
  - Title: `wmo / cycle`.
  - Corner text: lat/lon, `Argo 1.01e-3 · PACE 1.99e-3 (×1.98)`, and the date.
  - Markers: an orange open circle on the PACE pixel and a cyan + on the Argo
    position, as in `plot_L1B.py`.
- **`main(flg)`** as in `fig_argo.py`: `1` = test gallery. A JSON path can
  also be given on the command line.

**Questions**

1. **Granule cloud cut.** `find_examples` drops granules with ≥ 50 % cloud by
   default. Your criteria don't list a cloud cut, and the gallery is for
   *finding* clouds, so I propose **no cut** (`cloud_max: null`). Agree?
>A. Agreed, no cut.  Have the JSON file use `null`
2. **Radiance vs reflectance.** You asked for TOA *radiance*. The L1B stores
   reflectance `rhot` (see scrutinize.md Q&A/Plot L1B 1), and `plot_L1B.py`
   plots `rhot`. I recommend **`rhot(650)`** on one shared log scale
   (0.03–1, grey). Reflectance removes the sun-angle dependence, so a cloud
   looks equally bright in a high-latitude winter scene and in a tropical
   one, and one colour scale works across all 12 panels. Radiance
   (`Lt = rhot·F0·cosθs/(π d²)`) is an easy switch if you prefer it.
>A. My mistake.  Use reflectance.
3. **Which 12.** These are the top 12 by score, one per float. An alternative
   is a random 12 from within a tolerance (e.g. score < 0.3, about ±30 %),
   which would make the test more representative of the population we will
   use. The top 12 already span several regions. Preference?
>A. I am eventually going to ask for 36.  So let's use the top 12.
4. **Downloads.** No L1B granules are on this workstation
   (`$PAB_DATA_DIR/scrutinize/` does not exist here). 12 × ~1.9 GB ≈ 23 GB,
   probably 30–60 min; disk is fine (7.7 TB free). I propose a **shared cache
   `$PAB_DATA_DIR/L1B/<granule name>`** instead of the per-profile
   `scrutinize/<wmo>_<cycle>/l1b/`, because later galleries will reuse
   granules. That would mean adding an `l1b_dir` argument to
   `plot_L1B.l1b_path`. Streaming only the box with `earthaccess.open` is
   possible in principle, but outside us-west-2 it is untested and may be
   slow. I would not try it now. OK to download, and OK with the new
   location?
>A. Yes, that is a better location.  And it is OK to download.
5. **Scale.** On a slide, a 400 km panel has ~300 px across, so the PACE
   pixel and the Argo position sit almost on top of each other. Cloud within a
   few km of the matchup will be hard to judge. Should I add a dashed
   **50 km square** around the matchup to guide the eye? (A second, zoomed
   gallery is another option.)
>A. Let's use 2 circles with radius of ~50km around each.  This will allo us to 
see the clouds at the analysis location
6. **Granule edges.** Some matchups lie near the edge of a granule, where the
   box is clipped. I propose padding with blank so every panel is the full
   400 km, centred on the PACE pixel, and noting "edge" in the panel. The
   scene could also continue into the next granule, but stitching granules
   is out of scope for a test. OK?
>A. Yes, padding is fine
7. **Extra info per panel.** Should I also show the granule cloud % and Δt?
   They are cheap to add, but they crowd a small panel.
>A. No, do not include those

#### 2. Updated plan and follow-up questions (2026-11-24)

No gallery code has been written yet. Since you approved the downloads (A4),
I fetched the L1B granules of the top 12 into the new shared cache
`$PAB_DATA_DIR/L1B/`. It took ~35 s and 1.9 GB per granule. I used a
throwaway script in my scratch area; no repo code changed.

**Updated plan** (with your answers and the prompt-2 notes folded in):

- **JSON:** `papers/bbp/galleries/test.json` (not `py/galleries/`), with
  `"cloud_max": null`, `"n": 12`, `"half_width_km": 150.0` (300 km box) and
  `"wave": 650.0`. `out` is resolved relative to `papers/bbp/`, so the figure is
  `papers/bbp/figs/l1b_gallery_test.png`.
- **Figure:** 4 × 3 panels, 16 × 9 in, **dpi = 300** (4800 × 2700 px). The
  panels show `rhot(650)` on one shared grey log scale (0.03–1).
- **Panels:** each box is padded to the full 300 km and centred on the PACE
  pixel, with "edge" noted where the granule ends. The panels are in score
  order (best first).
- **Annotations:** `wmo / cycle`, lat/lon, and Argo and PACE bbp(700) values.
  There is no cloud % and no Δt.
- **Code changes outside `l1b_gallery.py`:**
  - `find_examples.find_examples`: `cloud_max=None` means no cut.
  - `plot_L1B.l1b_path`: a new `l1b_dir` argument. The gallery passes
    `$PAB_DATA_DIR/L1B`; the `plot_L1B.py` default stays
    `scrutinize/<wmo>_<cycle>/l1b/`.
- **Circles:** drawn in km on the ground, as the 50 km contour of the
  great-circle distance on the L1B lat/lon grid. On the scan/pixel axes they
  come out as slightly squashed ellipses, which is correct: it reflects OCI's
  rectangular pixels.

**Follow-up questions**

1. **The two 50 km circles will overlap almost exactly.** In the top 12, the
   PACE pixel and the Argo profile are 0.3–3.4 km apart (median 0.7 km). In
   the top 36 they are at most 4.8 km apart. Two 50 km circles, one on each,
   will therefore look like one thick ring. Options:
   - (a) One 50 km circle on the PACE pixel, plus a cyan + on Argo and an
     orange marker on the pixel. This is the cleanest option.
   - (b) Two concentric circles on the PACE pixel at **10 km** (the matchup
     radius) and **50 km**. This shows cloud right at the matchup as well as
     in the wider surroundings.
   - (c) Exactly what you wrote: a 50 km circle on each, in their two colours.

   I recommend **(b)**. Which do you want?
>A. Ok, let's try (b)

2. **Date in the panel?** In round 1 I proposed adding the date to each
   panel. You declined cloud % and Δt but did not mention the date. I'll
   leave it out unless you want it.
>A. Leave it out

3. **For the 36-panel gallery later:** a 6 × 6 grid on a 16:9 slide gives
   square panels only ~1.5 in tall. Would you rather have three 4 × 3 slides
   (ranks 1–12, 13–24, 25–36)? The code would make that a single `n_per_page`
   setting.
>A. Yes, I wish to have 3 slides.  Let's append `_#` to the figure name (before .png)

4. **Granule edges matter more than I expected.** All 12 granules are
   downloaded, and their matchup scan indices (out of 0–1709) show that 4 of
   the 12 sit near the along-track end of the 5-minute granule. A 150 km
   half-width is about 125 scans.
   - **6902906 / 262** is at scan **1709**, the very last scan, so half of its
     panel would be blank.
   - **2903464 / 51** (scan 42), **5906469 / 152** (scan 61) and
     **2903969 / 5** (scan 164) lose 20–65 % of one side.
   - 5906469 / 152 is also near the swath edge (pixel 1176 of 1272). That
     side is the true edge of the image, since nothing lies beyond the swath.

   Along-track, the scene simply continues in the previous or next granule.
   Stitching that granule on is easy: same pixel grid, scans appended, one
   more 1.9 GB download per affected matchup. Options:
   - (a) Pad with blank, as agreed in A6.
   - (b) Stitch in the adjacent granule when the box crosses the along-track
     edge.

   Because clouds right next to the matchup are the point of the gallery, I
   recommend **(b)**. Shall I?
>A. No, let's use (a) -- pad with blank

#### 3. Test gallery built (2026-11-24)

**Output:** `papers/bbp/figs/l1b_gallery_test.png` (4800 × 2700 px, 300 dpi).
Build it with `python papers/bbp/py/l1b_gallery.py`, which takes ~6 s once
the L1B files are cached.

**Files:**
- `papers/bbp/galleries/test.json` is new and holds the criteria
  (`cloud_max: null`), `n = 12`, `n_per_page = 12`, a 150 km half-width, the
  10 and 50 km circles, the 4 × 3 grid, 16 × 9 in, and dpi 300.
- `papers/bbp/py/l1b_gallery.py` is new:
  - `main(flg)` follows `fig_argo.py`: `1` = the test gallery, or pass any
    gallery `.json` path.
  - `build_gallery(json)` → `select_matchups` → `load_panel` →
    `plot_page`. With more than one page it writes `<name>_1.png`,
    `<name>_2.png`, … (A3); with one page it writes the name as given.
- `find_examples.py`: `cloud_max=None` now means no cloud cut.
- `plot_L1B.py`: `l1b_path` gained `l1b_dir`. The gallery passes
  `$PAB_DATA_DIR/L1B/`; the default is unchanged.

**One design change from the plan.** My first version framed each panel as
the PACE pixel ± 150 km / (mean km per pixel). OCI pixels grow away from
nadir, so the mean scale put the frame a few pixels outside the data on one
side, and most panels showed false "outside granule" strips. Each side of the
frame is now the box edge itself: the last pixel within 150 km on the ground.
The frame is extrapolated only where the granule really ends. As a result,
the PACE pixel is centred **on the ground** but can sit slightly off-centre
in pixel units.

**What the gallery shows** (my first read; please check):
- **No cloud within 50 km:** 5906885/55, 5906486/147, 6990685/54 and
  6990686/44 (the land in that panel is the Provence coast).
- **Clear at the pixel, cloud inside the 50 km circle:** 2903797/160,
  5906551/74, 3902688/69 and 2903464/51.
- **Cloud at or right next to the pixel (within 10 km):**
  - 5906473/89: broken cumulus streets.
  - 5906469/152: broken cloud at the swath edge, so the pixels are coarse
    and blocky.
  - 2903969/5: the pixel sits in a narrow gap in a cloud field.
  - 6902906/262: cloud ~30 km north. Its matchup is on the last scan, so
    half the panel is padding.

**Possible issues / questions**

1. **Panel size.** The panels are square and limited by the height of a 16:9
   page, so there is white space between columns. Fine for a slide; if you
   want bigger panels, I can drop the suptitle and/or move the colourbar
   into the legend row.
2. **Colour scale.** One log scale (ρt 0.03–1) for every panel. Clear water
   is ~0.04 and sits near black. That makes cloud stand out but hides any
   faint structure in the water, such as thin cirrus or haze. A lower `vmax`
   (e.g. 0.3) would bring out thin cloud at the cost of saturating bright
   cloud. Want that as a JSON option?
3. **Coarse pixels at the swath edge** (5906469/152, pixel 1176 of 1272).
   Pixels there are ~4–5 km across, so fine cloud structure blurs together
   into blocks. This is a property of the sensor, not a bug.

#### 4. Prompt 4 changes made (2026-11-24)

`figs/l1b_gallery_test.png` has been rebuilt with a 200 km scene, a small
orange dot on the PACE pixel, a dotted orange 30 km circle around the PACE
pixel and a dotted cyan 20 km circle around the Argo profile. The Argo +
marker is gone.

- **How I read "remove the orange circle on the PACE pixel":** I removed
  both orange rings at the pixel, the open-circle marker *and* the 10 km
  circle, and kept one dot. With that, "the PACE circle" (singular) is the
  50 → 30 km one. If you wanted the 10 km circle kept, add `10.0` to
  `pace_circle_km` in `galleries/test.json`.
- **JSON:** `circle_radii_km` is replaced by `pace_circle_km: [30.0]` and
  `argo_circle_km: [20.0]`. Both are lists, so more radii can be added. A new
  `scale_km: 50.0` sets the scale bar, which is now 50 km so that it is not
  half the panel.
- **Note:** where the PACE pixel and the Argo profile are a few km apart
  (5906469/152: 3.4 km; 2903969/5: 2.8 km), the cyan circle is visibly
  off-centre from the orange dot. That is expected. In 6902906/262 both
  circles stop at the granule edge, because the contours exist only where
  there is data.

## Logs

### 2026-11-24 (Test gallery prompt 1: plan and questions, no code)

Read `py/find_examples.py`, `py/plot_L1B.py` and `talks/AWOC2026/fig_argo.py`.
Ran `find_examples()` read-only on `$PAB_DATA_DIR/v2/pab.db` to size the
sample. The plan and 7 questions are in Q&A/Test gallery 1. I renamed the
Q&A heading "Test" to "Test gallery" to match the prompt.

- **Numbers:** with |Δt| ≤ 3 h and one matchup per float, there are 614
  matchups with no cloud cut and 238 with granule cloud < 50 %. The top 12
  with no cloud cut are all within ~6 % of both targets.
- **Learned:**
  - `find_examples` applies a granule cloud cut of < 50 % by default. That
    works against a cloud-search gallery, so I proposed turning it off.
  - The L1B stores reflectance, not radiance.
  - No L1B granules are on this workstation: the `scrutinize/` data is on the
    Mac. A 12-panel gallery therefore needs ~23 GB of downloads.

### 2026-11-24 (Test gallery prompt 2: answers reviewed, L1B downloaded, follow-up questions)

Reviewed the round-1 answers and folded them, plus the prompt-2 notes, into an
updated plan in Q&A/Test gallery 2. The prompt-2 notes were: JSON in
`papers/bbp/galleries/`, dpi = 300, and a 300 km box. Asked 4 follow-up
questions. No gallery code has been written yet.

- **Downloads (approved in A4):** I fetched the 12 L1B granules of the top-12
  matchups (no cloud cut, one per float) into the new shared cache
  `$PAB_DATA_DIR/L1B/`. Each took 27–67 s and was 1.86–1.92 GB, ~23 GB in all.
  I used a throwaway scratch script that calls
  `pab.pace.l1b.l1b_source_for_aop` and `pab.pace.cloud.download_granule`. No
  repo code changed.
- **Learned:**
  - The PACE pixel and the Argo position are only 0.3–3.4 km apart in the
    top 12 (≤ 4.8 km in the top 36). Two 50 km circles, one on each, would
    overlap, so I asked about concentric 10 and 50 km circles instead.
  - Several matchups sit at the along-track ends of their granules. The worst
    is 6902906 / 262, at the last scan (1709). I proposed stitching in the
    adjacent granule rather than padding.

### 2026-11-24 (Test gallery prompt 3: built `py/l1b_gallery.py` and the test gallery)

Wrote `papers/bbp/py/l1b_gallery.py` and `papers/bbp/galleries/test.json`.
Produced `papers/bbp/figs/l1b_gallery_test.png`. Made two small changes to
existing code: `find_examples(cloud_max=None)` means no cloud cut, and
`plot_L1B.l1b_path` gained an `l1b_dir` argument. Details and a first read of
the gallery are in Q&A/Test gallery 3.

- **Round-2 answers applied:**
  - Concentric 10 and 50 km circles on the PACE pixel, drawn as contours of
    great-circle distance on the L1B lat/lon grid.
  - No date in the panels.
  - Multi-page galleries get `_<page>` appended to the file name.
  - Blank (beige "outside granule") padding at granule edges.
- **Learned:**
  - The L1B scan dimension is named `scans` (1709 here), not
    `number_of_scans`. I read the granule size from the `latitude` shape
    instead.
  - OCI's across-track pixel size changes enough over 150 km that a single
    mean km-per-pixel misplaces the frame, which produced false padded
    strips. The fix frames each side at the box edge, i.e. 150 km on the
    ground, and extrapolates only where the granule ends.
  - In the top 12, 4 matchups have cloud within ~10 km of the PACE pixel,
    4 have cloud only within 50 km, and 4 are clear within 50 km.
- **Run time:** ~6 s for 12 panels once the L1B files are cached.

### 2026-11-24 (Test gallery prompt 4: 200 km scene, new markers and circles)

Updated `papers/bbp/py/l1b_gallery.py` and `papers/bbp/galleries/test.json`,
then rebuilt `papers/bbp/figs/l1b_gallery_test.png`. Notes are in
Q&A/Test gallery 4.

- **Changes:**
  - `half_width_km` 150 → 100, i.e. a 200 km scene.
  - The Argo + marker is removed.
  - The PACE open-circle marker and the 10 km circle are replaced by a
    single small orange dot.
  - Dotted orange 30 km circle around the PACE pixel (`pace_circle_km`).
  - Dotted cyan 20 km circle around the Argo profile (`argo_circle_km`). It
    is a contour of the great-circle distance from the Argo lat/lon, so it is
    drawn even when the profile is not on a box pixel; the old `argo_sp`
    lookup is dropped.
  - The scale bar is configurable through `scale_km`, now 50 km.
- **Learned:** with circles centred on each point, the 0.3–3.4 km offset
  between the PACE pixel and the Argo profile becomes visible as a
  non-concentric pair.

### 2026-11-24 (High 1e-3 gallery prompt 1: the top-36 gallery on 3 pages)

Created `papers/bbp/galleries/high_1e-3.json`: the test gallery's criteria
with `n = 36` and `n_per_page = 12`. Added it as figure 2 in
`py/l1b_gallery.py` `main()`. Produced
`figs/l1b_gallery_high_1e-3_{1,2,3}.png`. Notes are in Q&A/High 1e-3 1.

- **Run:** ~20 min, almost all of it downloading 24 more L1B granules into
  `$PAB_DATA_DIR/L1B/`. The plotting takes seconds.
- **Learned:**
  - The `_<page>` naming works as intended.
  - Page 1 reproduces the test gallery exactly (same bytes).
  - The reference matchup 5906209/224 comes back at rank 15.
  - L1B reflectance alone cannot separate sun glint (4903660/89) or dust
    (3901578/116) from cloud. An L2 `l2_flags` overlay is the natural next
    step if that matters.

### 2026-11-24 (Matched 1e-3 gallery prompt 1: PACE/Argo ~ 1, 36 matchups; tilt-change issue)

Created `papers/bbp/galleries/matched_1e-3.json` (`ratio_target` = 1.0,
otherwise as `high_1e-3.json`). Added it as figure 3 in `py/l1b_gallery.py`
`main()`. Produced `figs/l1b_gallery_matched_1e-3_{1,2,3}.png`. Notes and
questions are in Q&A/Matched 1e-3 1.

- **Run:** ~25 min, for 36 new L1B downloads. The cache now holds 72
  granules, 128 GB.
- **Found:** panel 1902347/131 was distorted because its PACE pixel falls in
  OCI **tilt-change** scans (L1B `scan_quality_flags` bit 1). Checking all
  72 gallery matchups found one more inside the flagged scans (5906574/66,
  high gallery) and one ~77 scans away (1902601/80). I corrected my earlier
  "swath edge" note for 5906574/66 in Q&A/High 1e-3 1.
- **Learned:**
  - The tilt flip happens near the sub-solar latitude and spans ~195 scans
    per granule.
  - During the flip, the along-track ground step grows from ~1.2 to ~4 km
    per scan.
  - PAB's L2-based matchups do not see this flag. It may deserve a quality
    cut, and I raised that as a question.
  - First impression only: the matched (ratio ≈ 1) gallery looks clearer
    near the pixels than the high (ratio ≈ 2) gallery, and its median
    granule cloud cover is lower (64 % against 74 %).

### 2026-11-24 (Low 1e-3 gallery prompt 1: JSON only; not run)

Created `papers/bbp/galleries/low_1e-3.json` (`ratio_target` = 0.5,
otherwise as `high_1e-3.json`). Registered it as figure 4 in
`py/l1b_gallery.py` `main()`. As instructed, nothing was downloaded and no
figure was made. Read your answers to Q&A/Matched 1e-3 1: the tilt-change
panels stay in, and there will be no tilt-change survey and no cloud tally.
Notes and one question are in Q&A/Low 1e-3 gallery 1.

- **Sizing (read-only DB query):** PACE/Argo ≈ 0.5 is about 3× rarer than
  ≈ 1 or ≈ 2 at Argo 1e-3: 16 matchups within score 0.15, against 47–48 for
  the other targets. The top 36 reach score 0.228 (ratios 0.41–0.63),
  against ≤ 0.13 for the high and matched galleries.
- **Learned:** at Argo bbp(700) ≈ 1e-3, PACE is much more often high than
  low relative to Argo, so the low gallery's tail is looser.

### 2026-11-24 (Low 1e-3 gallery prompt 2: built the 36-panel low gallery)

Built `figs/l1b_gallery_low_1e-3_{1,2,3}.png` from the unchanged
`galleries/low_1e-3.json`, keeping 36 panels per the user's answer. Notes are
in Q&A/Low 1e-3 gallery 2.

- **Run:**
  - 35 new L1B downloads (cache: 107 granules, 190 GB).
  - The first two attempts stopped part-way, at different granules, on
    **HTTP 500 from NASA CMR** (the L1B granule search).
  - Added `fetch_l1b()` to `py/l1b_gallery.py`: 4 attempts with a doubling
    wait starting at 30 s.
  - The third run hit one more 500 error, recovered on the first retry, and
    finished.
- **Learned:** CMR's granule search fails intermittently under a long series
  of lookups, so any multi-granule download loop needs retries.

