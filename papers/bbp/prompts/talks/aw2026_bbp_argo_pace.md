# Create figures comparing bbp from Argo and PACE

## Goals

Create figures comparing the bbp values from PACE and Argo for my talk at AWOC 2026

## Context

- The majority of Python scripts to make the figures for this paper are in `pab/matchup`
- There is a master script to make the figures for the paper in `PAB/papers/bbp/make_paper_figures.py`
- There is a script that generates global level figures in `PAB/papers/bbp/plot_global_maps.py`
- See code in `pab/viz` and `pab/plotting` for existing code

See the prompt doc `rt_fit_pb24.md` in `Oceanography/python/retrieve-or-bust/claude_prompts/RT`
for pointers to code that ingests the PB24 Hydrolight outputs.

We will define a matchup as having separation dx < 10km and dt < 3 hours.

All of the figures will be placed in Google Slides, so be mindful to keep the font sizes
sufficiently large to be visible.

## Code

- Use Python
- Use matplotlib and/or seaborn
- Have a main() function in the script that calls the other functions.
- Put imports at the top of the script.
- Document the code using docstrings and inline comments.
- Reuse existing code where possible.
- Follow the approach in `talks/AWOC2026/fig_argo.py` for how to call the function from main.

## Prompts

### Head-to-head

1. We will begin with a scatter-plot like figure that shows the bbp values from PACE and Argo for 
all of the matchups.  Let's start with a 2D histogram colored by the number of matchups at each point.
We will not plot cells with fewer than 10 matchups, but a second version will show these as individual
points on the figure.
This will be a single figure on a Google slide, with a title that I will create.
Before creating the figure, discuss it with me in the `Q&A/Head-to-head` section below.
Use Opus 5.5.  Log your work.

2. I have answered the first round of questions in the `Q&A/Head-to-head` section.  Please review my answers
and continue the discussion.  Do not generate the code yet.
Use Opus 5.5.  Log your work.

3. I have answered the next round of questions in the `Q&A/Head-to-head` section.  Please review my answers
and proceed to write the code as `PAB/papers/bbp/talks/AWOC2026/fig_bbp_h2h.py`.
Have this first figure be named `fig_bbp_h2h_raw.png`.
If any issues come up, discuss them with me in the `Q&A/Head-to-head` section below.
Use Opus 5.5.  Log your work.

4. I have answered the next round of questions in the `Q&A/Head-to-head` section.  
Please review my answers.  Then let's make the following edits:
    - With only ~3,000 matchups, we can show all of them as individual points on the figure.
    Let's make a new version named `fig_bbp_h2h_dots.png` that does so.
    - Let us color them by the Chl value from the PACE fit
    - Let's move the Legend into the plot and make a narrower figure.

    If any issues come up, discuss them with me in the `Q&A/Head-to-head` section below.
    Use Opus 5.5.  Log your work.

5. Let's make a few additional changes to the `fig_bbp_h2h_dots.png` figure:
    - Do add a 2:1 line to the figure.  Make it dark gray and dotted
    - Also add the equivalent below the 1:1 line.  Also dark gray and dotted.

    Use Opus 5.5.  Log your work.

### Differential

1. Let us now generate a scatter plot like `fig_bbp_h2h_dots.png` but with the Argo bbp values on 
the x-axis and $\delta$ = (PACE - Argo)/Argo on the y-axis.
This time, let us color by the PACE A_dg value, although we may revert to PACE Chl later.
Name the new figure `fig_bbp_differential_adg.png`.
Have it be a new method in the `fig_bbp_h2h.py` module.
If any issues come up, discuss them with me in the `Q&A/Differential` section below.
Use Opus 5.5.  Log your work.

## Examples to hold on to

- PACE/Argo = 2x
    - 5906209/224



## Q&A

### Differential

*Response to Differential prompt 1 (Claude Opus 5.5, 2026-11-23).*

**New figure:** `fig_bbp_differential_adg.png`, from
`python fig_bbp_h2h.py 4`, via a new function `fig_bbp_differential_adg()`
in `fig_bbp_h2h.py`.
- **Axes:** x is Argo b_bp(700), log, 1e-4 to 1e-2 m⁻¹ as before. y is
  δ = (PACE − Argo)/PACE, from −1.5 to 1.
  - This is the paper's Fig 7 definition and y range
    (`pab/matchup/plot_delta_vs_bbp.py`).
  - δ = 0.5 means PACE is 2× Argo; δ = −1 means PACE is ½ Argo.
  - There is a solid line at δ = 0.
- **Colour:** the BING posterior-median **A_dg** (`BING_ExpBPow_Adg`).
  This is the a_dg amplitude at the ExpBricaud pivot, so
  A_dg = a_dg(400 nm), in m⁻¹.
  - Scale: log, 0.005–0.3 m⁻¹ (the 1–99 % range is about 0.004–0.7),
    clipped, with arrows on the colour bar.
  - Colormap: cmocean `turbid`, browns to match the a_dg colour of the
    BING-fit slides.
- **Same as the head-to-head figures:** 6.2 × 4.6 in, same layout, float
  5907147 masked, off-scale points not drawn, seeded random drawing
  order, legend inside at the upper right.
- **Stats** (lower left), on all 3,180 matchups: N, median δ = 0.24, and
  IQR [−0.13, 0.49].
- `load_matchups()` now also returns `adg_pace`.

**What it shows.** δ falls with Argo b_bp: PACE is high where Argo b_bp is
low. The colour sorts the points, with pale (low A_dg) at the top left and
dark (high A_dg) near or below δ = 0 at higher Argo b_bp.

**Caveat (Q1 below).** Argo b_bp is on the x axis *and* inside δ, so some
of the falling trend is built in. PACE b_bp spans a narrower range than
Argo, so δ = 1 − Argo/PACE must fall as Argo rises.

**The A_dg signal is not just that.** At fixed Argo b_bp, A_dg still
separates δ (median δ; matchup counts in parentheses):

| Argo b_bp (m⁻¹) | A_dg < 0.01 | 0.01–0.03 | 0.03–0.1 | > 0.1 |
|---|---:|---:|---:|---:|
| 1–4e-4 | 0.54 (151) | 0.57 (83) | 0.63 (10) | 0.62 (5) |
| 4–6e-4 | **0.50** (343) | 0.37 (495) | **−0.08** (57) | −0.22 (6) |
| 0.6–1e-3 | **0.57** (65) | 0.29 (676) | **−0.04** (307) | −0.50 (31) |
| 1–2e-3 | 0.41 (22) | 0.21 (214) | 0.00 (289) | −0.13 (47) |
| 2–10e-3 | 0.26 (22) | −0.02 (51) | −0.06 (122) | 0.03 (128) |

- In the clear-water bins (Argo 4e-4–1e-3), PACE runs about 1.6–2.3× Argo
  when A_dg < 0.01, but matches Argo when A_dg > 0.03.
- A_dg tracks Argo b_bp (ρ = 0.64) far better than it tracks PACE b_bp
  (ρ = 0.14).
- So PACE b_bp is too high where BING puts little CDOM/detritus. That
  fits the "bad" fit, which has a low a_dg and a red excess.

#### Questions for JXP (Differential)

1. **Q1: The built-in trend.** Plotting δ against Argo makes a falling
   trend partly built in (see the caveat above). Do you want to:
   - keep Argo on x, as asked; or
   - switch to PACE b_bp on x (the left panel of the paper's Fig 7), which
     has the opposite built-in trend; or
   - use the mean of the two?

   *(My recommendation: keep Argo on x, since it is the independent
   measurement, and say a word about it in the talk.)*

   **A:**

2. **Q2: Statistics.** I show N, median δ and the δ interquartile range.
   Do you prefer the four head-to-head statistics (N, median PACE/Argo,
   ρ, log RMS)? Or nothing?

   **A:**

3. **Q3: Off-scale.** 2,984 of the 3,180 matchups are drawn:
   - 140 have δ < −1.5 (PACE < Argo/2.5) within the x range;
   - 56 are off the x range.

   Following Q12, they are neither drawn nor noted. OK?

   **A:**

4. **Q4: The stats text** sits at the lower left without a box. It
   overlaps a handful of sparse points near Argo 5e-4–1e-3, δ ≈ −1.2.
   Acceptable? Or should it move outside the axes, e.g. above the colour
   bar?

   **A:**

### Head-to-head

*Response to Head-to-head prompt 1 (Claude Opus 5.5, 2026-11-23). No code yet.*

#### The data

Applying the matchup cut (dx < 10 km, dt < 3 h) to the live v2.1 DB, with
v2.1 BING (ExpBPow) on the rank-1 pixel and the Argo mixed-layer
de-spiked b_bp(700) from `mld_summary`:

- **Totals:** 3,471 matchups. Of these, 3,336 have both b_bp > 0 and a
  successful fit, from 614 floats.
- **Dropped:**
  - 114 have no Argo b_bp;
  - 21 BING fits failed;
  - a few Argo values are ≤ 0.

| quantity (m⁻¹) | 1 % | 5 % | median | 95 % | 99 % |
|---|---:|---:|---:|---:|---:|
| Argo b_bp(700) | 2.6e-4 | 3.7e-4 | 7.3e-4 | 1.0e-2 | 4.8e-2 |
| PACE (BING) b_bp(700) | 7e-6 | 3.1e-4 | 1.08e-3 | 3.4e-3 | 6.1e-3 |

- **Agreement statistics** (log10, from `pab.metrics.compare.log_comparison`):
  - median PACE/Argo = 1.28 (IQR 0.84–1.94);
  - Spearman ρ = 0.40;
  - log bias = +0.01;
  - log RMS = 0.54;
  - log MAD = 0.18.
- **The two tails look different.**
  - The Argo high tail reaches 5e-2, while BING tops out near 6e-3
    (99th percentile). I have not checked where those profiles are.
  - The BING low tail (below about 1e-4) is a handful of fits where b_bp
    has collapsed toward 0.

#### Existing code to reuse

`pab.plotting.population.density_scatter` (used for the paper figures)
already does what you describe:
- it draws a log–log `histogram2d`, with cells of ≥ `min_count` matchups
  filled and coloured by a log count;
- it draws the matchups in sparser cells as individual dots;
- it adds the 1:1 line and a median-ratio line;
- it clips the axes to the central 99 % and reports `[N off-scale]`.

It is styled for the paper (5.6 × 5 in, 8–9 pt text, stats in the title).
I would call its core logic and restyle for the slide. The new script would
be `talks/AWOC2026/fig_bbp_h2h.py`, run as `main(flg)` / `python
fig_bbp_h2h.py 1` like `fig_argo.py`:
- flag 1: cells only, with sparse cells left blank;
- flag 2: the same plus the dots.

With 3,138 matchups inside 1e-4 to 1e-2 m⁻¹:

| cell width (dex) | cells ≥ 10 | matchups in them | max per cell |
|---:|---:|---:|---:|
| 0.05 | 115 | 1,864 (59 %) | 34 |
| 0.10 | 80 | 2,787 (89 %) | 97 |
| 0.15 | 51 | 2,960 (94 %) | 201 |

At 0.05 dex, 41 % of the data vanish from version 1, which would undersell
the matchups. At 0.1 dex, version 1 already shows 89 % of them.

#### Questions for JXP

1. **Q1: PACE b_bp source.** BING v2.1 (ExpBPow) on the rank-1 pixel,
   as in the BING-fit slides? Or also NASA GIOP (b_bp(442) moved to 700 nm)
   as a second panel or a later slide?

   *(My recommendation: BING only.)*

   **A:**  BING only

2. **Q2: Which matchups?** All 3,336 with b_bp > 0 on both sides? Or also
   drop failed or low-quality fits, e.g. χ²_ν > some cut, or BING b_bp
   < 1e-4 (the collapsed fits)?

   *(My recommendation: all 3,336, no extra cuts. The slide is "here is
   everything".)*

   **A:**  All 3,336, no extra cuts. The slide is "here is everything".

3. **Q3: Axes.**
   - Which axis gets which? *(Recommendation: Argo on x, PACE on y.)*
   - Log–log, with equal fixed limits? I suggest 1e-4 to 1e-2 m⁻¹, which
     drops 198 matchups (6 %) off-scale and states that number in a small
     note. The alternative is the auto 99 % clip, which is similar but
     less round.

   **A:** Agreed, Argo on x, PACE on y.

4. **Q4: Cell size.** 0.1 dex (30 × 30 cells over 1e-4 to 1e-2). This
   keeps 89 % in the ≥ 10 cells. Is that OK?

   **A:** Let's start with 0.1 dex

5. **Q5: Colour.** The count colour scale: log, from 10 to about 100.
   Which colormap?
   - (a) the paper's `Blues`;
   - (b) purple, to match the b_bp colour used in the BING-fit slides
     (`Purples`);
   - (c) a perceptual map such as `viridis` or cmocean `dense`.

   The dots in version 2 would be a dark shade of the same hue, or grey.

   *(My recommendation: (b), with grey dots.)*

   **A:** (b), with grey dots.

6. **Q6: Overlays.**
   - Keep the 1:1 line?
   - Add the median-ratio line (×1.28) or ±factor-of-2 lines?
   - Put stats on the figure (N, median ratio, ρ, log RMS)? Since you write
     the title, I would put a small box in a corner, or nothing.

   *(My recommendation: 1:1 solid, ×2 and ×½ dashed, and a 2-line box:
   "N = 3,336 / median PACE/Argo = 1.28".)*

   **A:** Show the 1:1 line as solid.  Put stats on the figure;
   the ones you suggest

7. **Q7: Size.** A single figure on a 16:9 slide under your title. A
   square plot plus colorbar at about 6.2 × 5 in (300 dpi), with 14 pt
   labels and 12 pt ticks. Or wider, to leave room for text on the slide?

   **A:**  It will be a single figure

#### Round 2

*Response to Head-to-head prompt 2 (Claude Opus 5.5, 2026-11-23). No code yet.*

**Settled from your answers:**
- **Data:** BING v2.1 only, and all 3,336 matchups with no extra cuts.
- **Axes:** Argo b_bp(700) on x, PACE b_bp(700) on y, log–log with equal
  limits.
- **Cells:** 0.1 dex, filled where they hold ≥ 10 matchups, using
  `Purples` with a log count scale. Version 2 adds the sparse matchups as
  grey dots.
- **Overlays:** a solid 1:1 line and a stats box with N and the median
  PACE/Argo ratio.
- **Size:** one figure on the slide.

**Correction to round 1:** with the successful fits only, 1e-4 to 1e-2 m⁻¹
leaves **228** matchups (6.8 %) off-scale, not 198. Here is where they go:

| limits (m⁻¹) | off-scale | Argo > max | PACE > max | PACE < min |
|---|---:|---:|---:|---:|
| 1e-4 – 1e-2 | 228 | 169 | 8 | 64 |
| 1e-4 – 3e-2 | 135 | 75 | 0 | 64 |
| 1e-4 – 1e-1 | 67 | 2 | 0 | 64 |

(Argo < 1e-4: 1 matchup.)

**A new finding: one float dominates the high Argo tail.**

169 matchups have Argo b_bp(700) > 1e-2. They come from 11 floats, but
114 of them come from one: **5907147 (Ligurian Sea, 43°N, 9°E)**.

| float | matchups | where | median Argo b_bp | median PACE b_bp | Chl |
|---|---:|---|---:|---:|---:|
| 5907147 | 114 | Ligurian Sea | 2.9e-2 | 6.1e-4 | 0.10 |
| 4903784 | 21 | Baltic | 4.8e-2 | 3.0e-3 | 0.97 |
| 4903847 | 15 | Tyrrhenian Sea | 2.9e-2 | 8.0e-4 | 0.36 |
| 4903660 | 6 | Arabian Sea | 2.0e-2 | 1.6e-3 | 0.32 |
| 7 others | 13 | | | | |

The 4903660 row includes your "Ugly" example.

Over all 359 of 5907147's profiles in `mld_summary`, its mixed-layer
b_bp averages 2.9e-2 m⁻¹. Its maximum is 0.04999, which looks like a cap.
Its Chl averages 0.1 mg m⁻³. The data mode is A (adjusted).

That b_bp is about 50× what oligotrophic water at that Chl should have,
and its ML std is small (median 1 % vs 5 % overall). This looks like a
sensor offset, fouling, or a calibration problem, not ocean signal.

With the 1e-4 to 1e-2 limits it all falls off-scale. With wider limits it
forms a tight off-diagonal blob at x ≈ 3e-2, y ≈ 6e-4, which by itself
could fill several ≥ 10 cells.

It also shifts the statistics:

| | N | median PACE/Argo | ρ | log RMS |
|---|---:|---:|---:|---:|
| all 3,336 | 3,336 | 1.28 | 0.40 | 0.54 |
| only those inside 1e-4 to 1e-2 | 3,108 | 1.34 | 0.49 | 0.29 |

#### Questions for JXP (round 2)

8. **Q8: Axis limits.**
   - (a) 1e-4 to 1e-2. This is the cleanest view of the bulk; 228 matchups
     are off-scale and counted in a note.
   - (b) 1e-4 to 1e-1. Shows the Argo high tail (mostly 5907147) as a
     separate blob off the 1:1 line; 67 off-scale.
   - (c) 1e-4 to 3e-2, a compromise.

   *(My recommendation: (a), with a short note, "228 matchups off-scale",
   in a corner.)*

   **A:**  Use (a), but do not include the note.

9. **Q9: Float 5907147.** You said no cuts (Q2). Should I keep it as it
   is? Or would you rather:
   - mark it, e.g. its matchups as hollow symbols with a legend entry
     "float 5907147 (suspect b_bp)"; or
   - flag it only in this doc and in your talk notes?

   This matters most if you choose (b) in Q8.

   *(My recommendation: keep it with no special marker, use limits (a),
   and keep it in mind for the "Ugly" slide. Its 114 matchups are an
   example of Argo being wrong, which is a different message from PACE
   being wrong.)*

   **A:** Let's mask it altogether

10. **Q10: Which statistics?** For the box I suggested "N = 3,336" and
    "median PACE/Argo = 1.28".
    - Confirm that is the set, rather than also ρ and log RMS.
    - Both should be computed on all 3,336 matchups, including the
      off-scale ones, as the paper's `density_scatter` does. A failed
      match is reported, not hidden. Agreed?

    **A:** Also include ρ and log RMS.  Do not include the masked matchups.

11. **Q11: The ×2 and ×½ lines.** You asked for a solid 1:1 line and
    did not mention the factor-of-2 lines. Should I leave them out?

    *(My recommendation: leave them out; the 1:1 line alone is cleaner.)*

    **A:** Leave them out; the 1:1 line alone is cleaner.

12. **Q12: Off-scale matchups in version 2.** Should the dots version
    draw the off-scale matchups pinned to the axis edge (small open
    triangles pointing outward)? Or leave them to the off-scale note?

    *(My recommendation: the note only.)*

    **A:** We won't show the off-scale matchups in the dots version. Nor inclucde a note

13. **Q13: Size.** Unless you say otherwise, a square axis plus colorbar,
    **6.2 × 5 in** at 300 dpi, with 14 pt labels and 12 pt ticks. On a
    10 × 5.6 in slide this leaves room at the right for a few bullets. Do
    you prefer it full-height and centred instead?

    **A:**  Do not save room for bullets.  Fill the slide, modulo a title I will include.

#### Round 3: the code

*Response to Head-to-head prompt 3 (Claude Opus 5.5, 2026-11-23).*

**Module:** `papers/bbp/talks/AWOC2026/fig_bbp_h2h.py`, run as `main(flg)`
like `fig_argo.py`:
- `python fig_bbp_h2h.py 1` writes `fig_bbp_h2h_cells.png`, the cells
  only;
- `python fig_bbp_h2h.py 2` writes `fig_bbp_h2h_cells_dots.png`, the
  cells plus grey dots for the matchups in cells with < 10.
- Both are 10 × 4.6 in at 300 dpi.

**Pieces:**
- `load_matchups()` reads the DB directly: v2.1 BING, success,
  rank-1 pixel, dx < 10 km, dt < 3 h, b_bp > 0 on both sides, with
  `MASK_WMO = (5907147,)` removed.
- `fig_bbp_h2h()` mirrors the cell/dot logic of
  `pab.plotting.population.density_scatter`. That function builds its own
  5.6 × 5 in figure with a 9 pt title, so I mirrored it rather than
  calling it.
- The statistics come from `pab.metrics.compare.log_comparison`.

**Answers applied:**
- (Q8a) The limits are 1e-4 to 1e-2. Off-scale matchups are neither drawn
  nor noted (Q12).
- (Q9, Q10) 5907147 is masked from the figure and the statistics. The
  statistics still include the other off-scale matchups.
- (Q6, Q10, Q11) The figure has a solid 1:1 line only, and the box shows
  N, the median ratio, ρ and log RMS.

**Issues to flag:**

1. **N is 3,180, not 3,222.** Float 5907147 has 156 matchups, not 114.
   114 is the number above 1e-2; its other 42 are spread between 3e-4 and
   1e-2. All are masked, as you asked. With the mask, the statistics are:

   | | N | median PACE/Argo | ρ | log RMS |
   |---|---:|---:|---:|---:|
   | all (round 1) | 3,336 | 1.28 | 0.40 | 0.54 |
   | **5907147 masked (on the slide)** | **3,180** | **1.32** | **0.48** | **0.42** |

2. **Filling the slide (Q13).** The slide's height limits the plot. Under
   your title there are about 4.6 in, so a square log–log axis is about
   3.75 in on a side. Stretching it to the width would tilt the 1:1 line
   off 45°. I made the figure the full width (10 × 4.6 in) and used the
   right side for the statistics in 17 pt and the legend in 14 pt. Moving
   the legend there also keeps it off the dots in version 2.
   - If you would rather have the legend inside the plot and a narrower
     figure (about 6 × 4.6 in) to centre, it is a two-line change.

3. **What the slide shows.**
   - The densest cells, at Argo 4–8e-4 m⁻¹, sit above the 1:1 line, at
     PACE about 0.6–1.5e-3. That is where the median ratio of 1.32 comes
     from.
   - Above about 1.5e-3 the cells follow the 1:1 line.
   - Version 2 shows a broad, roughly symmetric spray of sparse points
     around that core.

#### Round 4: all-dots version, narrower figures

*Response to Head-to-head prompt 4 (Claude Opus 5.5, 2026-11-23).*

I found no new **A:** entries under Round 3, so there was nothing further
to apply from the Q&A. Prompt 3 now names the first figure
`fig_bbp_h2h_raw.png`, so I renamed flag 1's output.

**`fig_bbp_h2h.py` now makes three figures, all in the same narrower
layout:**

| flag | file | content |
|---:|---|---|
| 1 | `fig_bbp_h2h_raw.png` | cells (≥ 10) only |
| 2 | `fig_bbp_h2h_cells_dots.png` | cells, plus grey dots for the sparse cells |
| 3 | `fig_bbp_h2h_dots.png` | **new:** all 3,067 on-scale matchups as dots, coloured by the BING (PACE) Chl |

- **Size:** 6.2 × 4.6 in, down from 10 × 4.6. That is the square axis plus
  the colour bar.
- **Legend:** inside the axes at the upper left, which is empty above the
  1:1 line at low Argo b_bp.
- **Statistics:** inside at the lower right, below the 1:1 line at high
  Argo b_bp. The text has no filled box, because a white box hid the
  low-PACE tail. The statistics are unchanged (N = 3,180, 1.32, 0.48,
  0.42).
- **Chl colour (flag 3):** the BING posterior-median Chl
  (`BING_ExpBPow_chl`). It uses a log scale from 0.01 to 3 mg m⁻³ and
  cmocean `algae`, the same scale as the global-matchup map, so the two
  slides read alike. The dots are drawn in a random (seeded) order, so
  neither high nor low Chl hides the other.
- The old `fig_bbp_h2h_cells.png` is superseded by `_raw.png` and can be
  deleted.

**What the Chl colouring shows.** High-Chl matchups follow the 1:1 line.
The excess sits in the low-to-moderate Chl water:

| PACE Chl (mg m⁻³) | N | median PACE/Argo | ρ | log RMS |
|---|---:|---:|---:|---:|
| < 0.03 | 324 | 1.10 | 0.33 | 0.83 |
| 0.03–0.1 | 728 | **1.53** | 0.16 | 0.41 |
| 0.1–0.3 | 1,241 | **1.45** | 0.18 | 0.35 |
| 0.3–1 | 800 | 1.19 | **0.65** | 0.28 |
| > 1 | 87 | 1.24 | **0.74** | 0.26 |

- Above 0.3 mg m⁻³, PACE tracks Argo (ρ ≈ 0.7, log RMS < 0.3).
- From 0.03 to 0.3 mg m⁻³, PACE is about 1.5× high and nearly
  uncorrelated with Argo. That fits the "bad" BING-fit slide: high b_bp in
  clear water, driven by excess red Rrs.
- Below 0.03 mg m⁻³, the median ratio is near 1, but the scatter is
  large. This bin includes the fits where b_bp collapsed toward 0.

#### Questions for JXP (round 4)

14. **Q14: Chl source for the colour.** You said "the Chl value from the
    PACE fit", so I used the BING posterior Chl. Would the Argo ML Chl
    (raw CHLA, as on the global map) be better? It is independent of the
    fit being judged.

    **A:** Stick with PACE

15. **Q15: The Chl-bin table.** Is it worth a figure or a callout? For
    example, a small second panel with the median PACE/Argo vs Chl.

    **A:** No, it is not worth a figure or a callout.

## Logs

### 2026-11-23 (Head-to-head prompt 1: design discussion for the PACE vs Argo b_bp 2D histogram)

Pulled the dx < 10 km, dt < 3 h matchups from the live v2.1 DB, joining
v2.1 BING b_bp(700) from `fit_results` with the Argo mixed-layer
b_bp(700) from `mld_summary`. 3,471 matchups remain; 3,336 have positive
values on both sides and a successful fit, from 614 floats.

Computed:
- the percentiles of each b_bp;
- the `log_comparison` stats (median ratio 1.28, ρ = 0.40, log RMS 0.54);
- cell occupancy for 0.05, 0.10 and 0.15 dex bins over 1e-4 to 1e-2 m⁻¹,
  where 0.1 dex puts 89 % of matchups in cells with ≥ 10.

Found that `pab.plotting.population.density_scatter` already implements
dense cells plus sparse dots, so I proposed reusing it and restyling it
for the slide in `talks/AWOC2026/fig_bbp_h2h.py`.

Wrote Q1–Q7 in Q&A/Head-to-head:
- the PACE source;
- the matchup cuts;
- the axes and limits;
- the cell size;
- the colormap;
- the overlays and stats;
- the figure size.

No code was written.

### 2026-11-23 (Head-to-head prompt 2: answers reviewed; axis limits and a suspect float)

Reviewed JXP's answers to Q1–Q7:
- BING only, with all 3,336 matchups;
- Argo on x and PACE on y;
- 0.1 dex cells;
- `Purples` with grey dots;
- a solid 1:1 line and a stats box;
- one figure.

Recounted the off-scale matchups for several limits: 228, not 198, for
1e-4 to 1e-2. The difference: the round-1 count included the 21 failed
fits.

Found that 114 of the 169 matchups with Argo b_bp > 1e-2 come from float
5907147 in the Ligurian Sea. Its ML b_bp is 2.9e-2 at Chl 0.1, and it caps
at 0.04999 (data mode A). That is a suspect Argo sensor, not ocean
signal.

Compared the stats on all data vs the in-range subset:
- median ratio: 1.28 vs 1.34;
- ρ: 0.40 vs 0.49;
- log RMS: 0.54 vs 0.29.

Asked Q8–Q13: the limits, how to treat 5907147, the stats set and sample,
the ×2 lines, off-scale markers in version 2, and the size.

No code was written.

### 2026-11-23 (Head-to-head prompt 3: fig_bbp_h2h.py written; cells and cells+dots figures)

Created `papers/bbp/talks/AWOC2026/fig_bbp_h2h.py`, following `fig_argo.py`:
`main(flg)`, a `FIGURES` table, no argparse, and the constants at the top
(`MASK_WMO`, `LIM`, `DEX`, `MIN_COUNT`, `CMAP`).
- `load_matchups()` is a single SQL join for the successful v2.1 BING
  rank-1 fits, the Argo ML b_bp(700) and the dx/dt cut, then masks float
  5907147.
- `fig_bbp_h2h()` mirrors the paper's `density_scatter` and restyles it
  for a slide:
  - a 10 × 4.6 in figure with a square log–log axis from 1e-4 to 1e-2;
  - 0.1 dex cells shown where they hold ≥ 10, in `Purples` (starting at
    20 % so the faintest cells stay visible) on a log count scale;
  - a solid 1:1 line;
  - grey dots for the sparse cells (flag 2);
  - the `log_comparison` stats and the legend in the free right-hand area.

Rendered and inspected both figures. Moved the legend out of the axes
after it covered sparse dots in version 2.

N is 3,180 from 613 floats. Masking removed 156 matchups, not 114, because
the float also has 42 matchups below 1e-2.

With the mask the stats are: median ratio 1.32, ρ = 0.48, log RMS = 0.42.

Raised the width/height trade-off of "fill the slide" in Q&A round 3.

### 2026-11-23 (Head-to-head prompt 4: all-dots figure coloured by PACE Chl; narrower layout)

Reworked `talks/AWOC2026/fig_bbp_h2h.py`:
- `load_matchups()` also returns `chl_pace` (`BING_ExpBPow_chl`, from the
  same fit).
- Shared layout helpers: `_axes()` (a 3.75 in square axis plus a colour
  bar, figure 6.2 × 4.6 in) and `_finish()` (log axes, 1:1 line, stats,
  legend).
- New `fig_bbp_h2h_chl()` (flag 3, `fig_bbp_h2h_dots.png`): every
  on-scale matchup as a dot, coloured by PACE Chl on the `fig_global.py`
  scale (log, 0.01–3, `algae`), in a seeded random drawing order.
- Flag 1 now writes `fig_bbp_h2h_raw.png`, per the edited prompt 3.

Rendered and inspected all three figures. On the first pass a white stats
box at the upper left cut a rectangle out of the points. Moved the stats to
the lower right without a fill, and the legend to the upper left.

Found that PACE/Argo depends on Chl:
- about 1.5× high, with ρ ≈ 0.2, for Chl 0.03–0.3 mg m⁻³;
- about 1.2×, with ρ ≈ 0.7, above 0.3 mg m⁻³.

Asked Q14 (BING vs Argo Chl for the colour) and Q15 (whether the Chl-bin
result deserves a panel).

### 2026-11-23 (Differential prompt 1: delta vs Argo b_bp, coloured by PACE A_dg)

Added `fig_bbp_differential_adg()` and the helper `delta()` to
`talks/AWOC2026/fig_bbp_h2h.py`.
- Flag 4 writes `fig_bbp_differential_adg.png`.
- `load_matchups()` also returns `adg_pace` (`BING_ExpBPow_Adg`, which is
  a_dg(400)).
- The y axis is δ = (PACE − Argo)/PACE from −1.5 to 1, as the paper's
  Fig 7. The x axis is log Argo b_bp from 1e-4 to 1e-2.
- The colour is A_dg on a log 0.005–0.3 m⁻¹ scale, using cmocean `turbid`.
- It uses the same 6.2 × 4.6 in layout and mask as the head-to-head
  figures, with a δ = 0 line.
- Stats (N, median δ = 0.24, IQR [−0.13, 0.49]) at the lower left, legend
  at the upper right.

Rendered and inspected it. Moved the stats from the lower right, where
they overlapped dots, to the lower left. Added intermediate colour-bar
ticks.

Checked that the A_dg colouring is more than the built-in δ-vs-Argo trend.
At fixed Argo b_bp of 4e-4–1e-3, median δ is about 0.5 for A_dg < 0.01 and
about 0 for A_dg of 0.03–0.1. A_dg correlates with Argo b_bp (ρ = 0.64),
not with PACE b_bp (0.14).

Asked Q1–Q4 in Q&A/Differential: the built-in trend, the stats set,
off-scale points, and the stats placement.

### 2026-11-23 (Head-to-head prompt 5: 2:1 and 1:2 lines on fig_bbp_h2h_dots.png)

Added dotted, dark-grey (`FAC2_COLOR = "#404040"`) lines for PACE = 2 × Argo
and PACE = Argo/2 to `fig_bbp_h2h_chl()` (flag 3, `fig_bbp_h2h_dots.png`)
only. They have one legend entry, "2:1, 1:2", between "matchup" and "1:1".
The other figures are unchanged.

Kept JXP's own edits in the file (the stats label now reads "PACE/Argo").
Re-rendered and inspected the figure: the lines clear the legend and the
stats text.

For reference, of the 3,180 matchups (off-scale ones included):
- 68 % have PACE within a factor of 2 of Argo;
- 24 % have PACE more than 2× Argo;
- 8 % have PACE less than half of Argo.
