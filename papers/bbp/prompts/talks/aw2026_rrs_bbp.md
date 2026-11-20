# Create the rrs figure for AWOC 2026

## Goals

Create one or more figures for my talk at AWOC 2026.
Possibly a slide or two too.

## Context

- The majority of Python scripts to make the figures for this paper are in `pab/matchup`
- There is a master script to make the figures for the paper in `PAB/papers/bbp/make_paper_figures.py`

See the prompt doc `rt_fit_pb24.md` in `Oceanography/python/retrieve-or-bust/claude_prompts/RT`
for pointers to code that ingests the PB24 Hydrolight outputs.

## Prompts

### RT+bbp/bb

1.  Read the Context section above.  
I wish to create a figure showing how Rrs depends on the molecular to particle
scattering ratio (bbw/bbp).  We will use the Hydrolight outputs from PB24 to create the figure.
The axes of the figure should be Rrs vs. b_b/(a+b_b), and we will show the outputs for data
with the upper 10% of bbp/bb values and the lower 10% of bbp/bb values.
We will begin at a single wavelength of 650 nm.
Before creating this figure, confirm you can read the Hydrolight outputs from PB24
and that you have the data you need to create the figure.
Discuss this with me in the "Q&A/RT+bbp/bb" section below.
Use Opus 5.5.  Log your work.

2. Read my answers in the "Q&A/RT+bbp/bb" section below.
Then create a first draft of the figure (2 panels).
Use Matplotlib and/or Seaborn.
I may then make a few edits by hand.
If you have any additional questions, put them in the "Q&A/RT+bbp/bb" section below.
Use Opus 5.5.  Log your work.

3. Read my next round of answers in the "Q&A/RT+bbp/bb" section below.
Then create a new draft of the figure.
If you have any additional questions, put them in the "Q&A/RT+bbp/bb" section below.
Use Opus 5.5.  Log your work.

4. Read my last round of answers in the "Q&A/RT+bbp/bb" section below.
Then create a new draft of the figure.
If you have any additional questions, put them in the "Q&A/RT+bbp/bb" section below.
Use Opus 5.5.  Log your work.

5. Read my last round of answers in the "Q&A/RT+bbp/bb" section below.
I think it may make more sense to use rrs instead of Rrs.  This is because the
Gordon approximation is stricly a polynomial in rrs.
Please provide an option to show rrs instead of Rrs.
No need to have the filenames change, just the axes labels and data used.
If you have any additional questions, put them in the "Q&A/RT+bbp/bb" section below.
Use Opus 5.5.  Log your work.

5. Read my last round of answers in the "Q&A/RT+bbp/bb" section below.
I have renamed and moved this doc and the script to generate the figure.
Things appear to be fine and I think we are done (I'll make any
additional edits as needed).  Use Opus 5.5.  Log your work.

## Q&A

### RT+bbp/bb

*Response to RT+bbp/bb prompt 1 (Claude Opus 5.5, 2026-11-20).*

**Short answer: yes, I can read the PB24 Hydrolight outputs, and they have
every quantity the figure needs. But at 650 nm the two 10 % groups do not
overlap in b_b/(a+b_b) at all, so the figure as specified would show two
disjoint clouds rather than a dependence on b_bw/b_bp. Some design choices
are needed first (questions below).**

#### The data

- **Source.** The consolidated PB24 cache at
  `$OS_COLOR/SD/derived/pb24_v1/` (36 GB). It holds all 5,000 realisations of
  `SD_hyp_no_R_NNNN.nc`, read with `robust.rt.data.pb24_cache.open_cache()`
  in `retrieve-or-bust`, through the `ocpy.hydrolight.pb24` reader. The build
  record is `retrieve-or-bust/design/ztt_pb24/cache_build.md`, and the
  pointers are in `claude_prompts/RT/rt_fit_pb24.md`. Note that file is under
  `claude_prompts/RT/`, not `design/ztt_pb24/`.
- **Fields used.** All are per realisation on a 451-band grid (350–800 nm,
  1 nm), so 650 nm is an exact node:
  - `aw`, `aph`, `ag`, `aNAP` → a;
  - `bbw` and `bbph` + `bbNAP` → b_bw, b_bp, b_b;
  - `Rrs` on (θs, θ_v, φ, λ), above water, sr⁻¹. "no_R" means **no Raman**,
    so this is elastic Rrs only.
- **Read check.** All 5,000 values are finite at 650 nm, and the read takes
  under a second (memmap).

| 650 nm | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| a (m⁻¹) | 0.342 | 0.342 | 0.345 | 0.426 | 14.8 |
| b_bw (m⁻¹) | 4.25e-4 | (constant) | | | |
| b_bp (m⁻¹) | 9.2e-6 | 1.7e-4 | 2.1e-3 | 0.106 | 63 |
| x = b_b/(a+b_b) | 5.0e-4 | 1.7e-3 | 7.2e-3 | 0.173 | 0.91 |
| b_bp/b_b | 0.021 | 0.281 | 0.83 | 0.996 | 1.000 |
| Rrs(θs=0, nadir) (sr⁻¹) | 2.3e-5 | 9.4e-5 | 3.2e-4 | 0.011 | 0.17 |

Rrs at nadir hardly depends on the sun at 650 nm: θs = 30° vs 0° differs
by about 1 %.

#### The problem at 650 nm

At 650 nm, a is almost pure water (a_w = 0.34) and b_bw is a single constant
(PB24 uses one seawater b_bw). So b_bp/b_b and x are nearly the same
variable: both increase with b_bp.
- **Bottom 10 %** (b_bp/b_b ≤ 0.28, n = 500): x = 0.0013–0.0017, Rrs about
  9e-5. These are the clearest waters, with median C = 0.01 mg m⁻³. The group
  sits at almost a single point on the x axis.
- **Top 10 %** (b_bp/b_b ≥ 0.996, n = 500): x = 0.066–0.91, Rrs
  0.003–0.17. These are turbid and very high-Chl waters, with median
  C ≈ 11 mg m⁻³.
- **Zero overlap in x.** The figure would show what x does, not what
  b_bw/b_bp does.

**What happens when x is held fixed.** I split x into 12 log bins and took
the 10 % / 90 % of b_bp/b_b *within each bin*. The ratio Rrs/x is
effectively the "G" factor in Rrs ≈ G·x:

| x bin | b_bp/b_b p10 / p90 | Rrs/x, low b_bp/b_b | Rrs/x, high b_bp/b_b |
|---|---|---:|---:|
| 0.0009–0.0017 | 0.10 / 0.27 | 0.0584 | 0.0545 |
| 0.0017–0.0033 | 0.33 / 0.59 | 0.0540 | 0.0482 |
| 0.0033–0.0061 | 0.64 / 0.78 | 0.0478 | 0.0448 |
| 0.0061–0.0114 | 0.81 / 0.89 | 0.0446 | 0.0430 |
| 0.011–0.021 | 0.90 / 0.94 | 0.0431 | 0.0429 |
| 0.075–0.14 | 0.987 / 0.995 | 0.0487 | 0.0545 |
| 0.26–0.49 | 0.997 / 1.000 | 0.0736 | 0.0884 |

- **[CORRECTED 2026-11-20, prompt 2: this 7–12 % is mostly an artefact of
  the binning. See "Prompt 2: the draft figure" below.]** **The physics shows up at small x.** In clear water, at the same x, the
  more molecular-dominated half has Rrs/x about **7–12 % higher**. That is
  what you'd expect: water's phase function sends more of its backscatter
  toward nadir than a particle phase function does.
- **At x ≳ 0.05 the comparison is not useful.** b_bp/b_b spans only
  0.99–1.00 in those bins, so the high-x differences come from the particle
  phase function (b_bp/b_p) and multiple scattering, not from b_bw.
- **G itself depends on x.** Rrs/x falls from about 0.058 to 0.043 and then
  rises toward 0.13 as x → 0.9. So any comparison has to be made at matched
  x, or plotted against a G(x) curve.

**What pooling wavelengths does.** Pooling 400–700 nm (every 25 nm) gives
the groups overlapping x ranges:
- low group (b_bp/b_b ≤ 0.17): x = 0.0006–0.37;
- high group (≥ 0.993): x = 0.04–0.84.

The cost is that the low group is then mostly blue bands (400 nm alone has
1,111 points, 650 nm only 185). That trades the b_bw signal against
wavelength-dependent a_w and phase-function structure.

#### Questions for JXP

1. **Q1: The selection.** How should the two groups be chosen, given that
   the global 10 % groups don't overlap at 650 nm?
   - (a) Plot the global 10 % groups as asked, accepting two disjoint
     clouds. The message is then "molecular-dominated water sits at low x".
   - (b) **Choose the 10 % groups within bins of x**, as in the table above.
     Plot Rrs vs x for both, or Rrs/x vs x, and add the theoretical G(x)
     (e.g. Gordon 1988) as a reference.
   - (c) Pool several wavelengths so the groups overlap in x.
   - (d) Show the whole population colour-coded by b_bp/b_b (a continuous
     colourbar), with no 10 % cut.

   *(My recommendation: (d) as the main panel, since it shows the whole
   structure at once. Add (b) as a Rrs/x inset or second panel, since that
   isolates the b_bw/b_bp effect at fixed x.)*

   **A:**  Let us show 2 panels, (d) and (b).
2. **Q2: The geometry.** Use Rrs at θs = 0°, nadir view? That matches the
   normalized PACE L2 `Rrs` the v2.1 fits now use. At 650 nm θs barely
   matters (about 1 %).

   *(Recommended: yes.)*

   **A:** yes
3. **Q3: The range.** PB24 reaches b_bp = 63 m⁻¹ and x = 0.91, far outside
   the Argo/PACE open-ocean matchups (b_bp(700) ~ 10⁻⁴–10⁻²). Should I clip to
   an oceanic range (for example x ≤ 0.05, or b_bp(650) ≤ 0.05 m⁻¹), or show
   it all on log axes with the matchup range shaded?

   **A:** Let's clip to an oceanic range of x ≤ 0.05 for now, but I may expand it
4. **Q4: Axes.** Should both axes be log? x spans 3 decades and Rrs spans
   4, so linear axes would squash the open-ocean points into the corner.

   *(Recommended: log–log.)*

   **A:** Yes, let's use log–log axes.
5. **Q5: Where the code lives.** Should I write it as
   `papers/bbp/talks/fig_rrs_vs_x_pb24.py`? It would read the cache through
   `robust.rt.data.pb24_cache`, so it depends on `retrieve-or-bust`, which is
   already in ocean14. Or would you prefer a new module under `pab/` with a
   group in `make_paper_figures.py`?

   *(Recommended: `papers/bbp/talks/`, since it's a talk figure, not a paper
   figure.)*

   **A:** Make it a method in a module named `papers/bbp/talks/figs_awoc2026.py`.
   It is find that this has a dependency on the `retrieve-or-bust` package.

#### Prompt 2: the draft figure

*Response to RT+bbp/bb prompt 2 (Claude Opus 5.5, 2026-11-20).*

**The draft.** `papers/bbp/talks/pb24_rrs_vs_x_650.png`, made by
`fig_rrs_vs_x()` in `papers/bbp/talks/figs_awoc2026.py`. Regenerate it with
`python papers/bbp/talks/figs_awoc2026.py` (ocean14; flags `--wave`,
`--x-max`, `--out-dir`). Everything follows your answers: θs = 0 and nadir
view, x ≤ 0.05 (3,922 of 5,000 realisations), log–log axes, Matplotlib.
- **(a)** Rrs vs b_b/(a+b_b) for every realisation, coloured by b_bp/b_b
  on a single-hue blue scale. The dashed line is Gordon (1988) for rrs,
  carried above water with Lee et al. (2002): Rrs = 0.52 rrs/(1 − 1.7 rrs).
- **(b)** The lowest and highest 10 % of b_bp/b_b within each of 10 log-x
  bins, plotted as Rrs/x vs x. Points are faint; each line connects that
  group's per-bin median (x, Rrs/x). The same Gordon curve is shown.
- **Hand edits.** The module-level `RC`, the colour constants and the
  `figsize` in `fig_rrs_vs_x` are where to make them. `load_pb24_band()`,
  `binned_extremes()` and `gordon_Rrs()` are separate helpers.

**A correction to my prompt 1 finding.** Panel (b) at 650 nm shows almost
**no** difference between the two groups: the orange and blue medians lie on
top of each other. The "7–12 % higher Rrs/x" I reported came from plotting
both groups at the bin centre. Within a bin, the low-b_bp/b_b points sit at
lower x, and Rrs/x falls steeply with x there, so the gap was really an x
gap. Once each median is placed at its own group's x, the gap disappears.

The reason is that **at a single band, x and b_bp/b_b are the same variable.**
At 650 nm with x ≤ 0.05, Spearman ρ(x, b_bp/b_b) = **0.999**. a ≈ a_w and
b_bw are both fixed, so x is set by b_bp alone, and so is b_bp/b_b. So the
within-bin comparison is empty by construction. The fall in Rrs/x from 0.058
to 0.043 across panel (b) is the molecular-fraction effect itself: b_bp/b_b
rises from 0.1 to 0.95 along that axis, and Gordon's curve is flat there.
But one band cannot show that it is b_bw/b_bp rather than x.

**What separates them: pooling wavelengths.** a_w and b_bw change with λ in
different ways, so across bands x and b_bp/b_b decouple. I pooled
400–700 nm every 20 nm with x ≤ 0.05 (35,825 points); there ρ(x, b_bp/b_b)
= 0.32.
- **Within x bins, molecular-rich runs have Rrs/x 15–31 % higher**
  (0.057 vs 0.043 at matched x). The residual of log(Rrs/x) after a smooth
  fit in x correlates with b_bp/b_b at ρ = −0.91.
- **Rrs/x collapses onto b_bp/b_b.** A smooth function of b_bp/b_b
  predicts log(Rrs/x) to **1.4 % rms**. x alone manages only 9 %.

| b_bp/b_b | 0–0.2 | 0.2–0.4 | 0.4–0.6 | 0.6–0.8 | 0.8–0.9 | 0.9–0.97 | 0.97–1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| median Rrs/x (sr⁻¹) | 0.0571 | 0.0540 | 0.0504 | 0.0468 | 0.0440 | 0.0430 | 0.0436 |

So over the oceanic range, the "G" in Rrs ≈ G·x is set by the molecular
fraction: a **25 %** drop from water-dominated to particle-dominated
backscatter, at the same x. That is a clean talk message. It also bears on
the paper's bias discussion: a forward model with the wrong G(b_bp/b_b) maps
straight into b_bp(700).

#### Questions for JXP (prompt 2)

6. **Q6: Rework panel (b)?** At 650 nm, panel (b) as specified can only show
   two coincident curves. Options:
   - (a) Keep it as is. The message becomes "at one band you cannot separate
     them", which is a weak slide.
   - (b) Replace it with **Rrs/x vs b_bp/b_b** (linear x axis), pooled over
     400–700 nm and coloured by λ, with the 650 nm points highlighted and a
     flat Gordon line. This shows the 25 % drop and the collapse directly.
   - (c) Keep the within-x-bin 10 % extremes, but pool the wavelengths. The
     two groups then separate by 15–31 % at every x, but each group mixes
     bands (the molecular-rich group is mostly blue and green, the
     particle-rich group mostly red).

   *(My recommendation: b, with panel (a) unchanged at 650 nm.)*

   **A:** Let us try option (b).
7. **Q7: Panel (a)'s colour scale.** At 650 nm b_bp/b_b > 0.6 for most of
   panel (a), so the upper half is uniformly dark. Shall I put the colour bar
   on a logit or "1 − b_bp/b_b" (molecular fraction, log) scale to spread it?

   **A:** Let's try the logit scale.
8. **Q8: Output location.** The PNG is written next to the module, in
   `papers/bbp/talks/`. Do you want it elsewhere, e.g. `$PAB_DATA_DIR/talks/`,
   to keep images out of git?

   **A:** That location is good.

#### Prompt 3: second draft

*Response to RT+bbp/bb prompt 3 (Claude Opus 5.5, 2026-11-20).*

**The draft.** Same file and command as before:
`papers/bbp/talks/pb24_rrs_vs_x_650.png` from `fig_rrs_vs_x()` in
`papers/bbp/talks/figs_awoc2026.py` (`python papers/bbp/talks/figs_awoc2026.py`).
- **(a) Unchanged except the colour bar (Q7).** b_bp/b_b is now on a logit
  scale, limits 0.02–0.995, ticks 0.05 … 0.99. The 0.5–0.99 range, where
  most 650 nm points sit, takes about half the bar either way.
  The real gain is at the top: 0.9–0.99 gets 26 % of the bar instead of 9 %.
- **(b) Rebuilt as Rrs/x vs b_bp/b_b (Q6 = b).**
  - 400–700 nm every 20 nm, plus 650 nm, with x ≤ 0.05: 39,747 points,
    coloured by λ (viridis), drawn in random order so no band hides another.
  - Black line with markers: the median in 0.05-wide b_bp/b_b bins, all
    bands.
  - Orange line: the same median from **650 nm alone**.
  - Grey band: Gordon (1988) + Lee (2002) Rrs/x over x ≤ 0.05
    (0.049–0.052). That model has no b_bp/b_b dependence, so it is a flat
    band.
  - The y axis is linear, since it spans only 0.040–0.060.

**What it shows.**
- **G falls from about 0.059 to 0.043 sr⁻¹ (about 27 %)** as b_bp/b_b goes
  from 0 to 0.93, almost linearly. The spread at fixed b_bp/b_b is a few %.
- **The 650 nm-only median lies on top of the all-band median.** At one band
  you can't tell x and b_bp/b_b apart (prompt 2). Across bands you can, and
  G follows b_bp/b_b. So the trend along x at 650 nm is the molecular
  fraction at work.
- **Gordon's G crosses the PB24 curve at b_bp/b_b ≈ 0.45–0.55.** It is
  about 15 % low for water-dominated backscatter and about 15 % high for
  particle-dominated backscatter.
- **Two details you might be asked about.**
  - Above b_bp/b_b ≈ 0.95 the median turns up again. Those are the most
    turbid points, near the x = 0.05 clip, where G rises with x (prompt 1
    table), plus spread in the particle phase function.
  - The blue bands (400–450 nm) sit a little *below* the curve at low
    b_bp/b_b. Smaller per-band effects such as the shape of a_w or Fresnel
    dispersion could cause that. I have not checked which.

**Code notes.**
- New helper `load_pb24_bands(waves, x_max=…)`.
- New constant `POOL_WAVES` (400–700 by 20).
- The band shown in panel (a) is always added to the pool.
- `fig_rrs_vs_x(..., pool_waves=, frac_lim=, pooled=)` lets you pass
  pre-loaded data when iterating by hand.
- `binned_extremes()` is no longer used by the figure. I left it in case
  you want the within-x-bin version back. Tell me if it should go.
- The pooled load takes about 3 s.

#### Questions for JXP (prompt 3)

9. **Q9: The λ colour map.** Viridis is perceptually uniform, but it does
   not look like the spectrum (yellow = 700 nm). An ocean-colour audience
   might read a spectral map ("Spectral_r" or "turbo", violet → red) more
   naturally. Keep viridis or switch?

   **A:** Use a spectral map, e.g. 'jet'
10. **Q10: The Gordon reference.** In (b) it is a flat band because Gordon's
    G depends only on x. Keep it as a band, draw a single line at the
    small-x value (0.049), or drop it?

    **A:** Draw a single line at 0.049.  Use dark grey
11. **Q11: Panel (a) is still visually flat.** Even on the logit scale, the
    650 nm points form a thin ribbon, because Rrs is almost a function of x
    there, and the colour mostly encodes x again. Would panel (a) work better
    as Rrs vs x at **several** bands (e.g. 450, 550, 650 nm in three
    categorical colours), or is the single 650 nm ribbon what you want to
    open with?

    **A:**  Ok, let's add 2 more bands, but include it as an option so that I can
    revert to only 650 nm as I wish.

#### Prompt 4: third draft

*Response to RT+bbp/bb prompt 4 (Claude Opus 5.5, 2026-11-20).*

**The drafts.** There are now two files, one per panel-(a) option. Both come
from `fig_rrs_vs_x()` in `papers/bbp/talks/figs_awoc2026.py`:
- **`pb24_rrs_vs_x_450_550_650.png`** (the new default):
  `python papers/bbp/talks/figs_awoc2026.py`.
- **`pb24_rrs_vs_x_650.png`** (650 nm only, Q11 option):
  `python papers/bbp/talks/figs_awoc2026.py --extra-bands`, i.e. the flag
  with no values. In Python, use `fig_rrs_vs_x(extra_bands=())`.

**Changes.**
- **Q9.** λ is coloured with `jet`. The colour map is a constant,
  `CMAP_WAVE`, so it is one edit to change.
- **Q10.** Gordon is now a single dark-grey dashed line at
  `GORDON_G0` = 0.52 × 0.0949 = **0.0493** sr⁻¹ (the x → 0 limit).
- **Q11.** Panel (a) draws `wave` plus `EXTRA_BANDS` = (450, 550) nm, each
  in its `jet` colour (the same mapping as panel (b)). The legend gives each
  band's N, and the points are drawn in one random order so no band hides
  another. With `extra_bands=()` panel (a) goes back to the single band
  coloured by logit(b_bp/b_b), as in draft 2. Panel (a)'s bands are always
  included in the panel-(b) pool.
- **The 650 nm-only median in (b)** is now a white line with a dark outline.
  An orange line would have vanished in `jet`.
- The output file name now encodes the panel-(a) bands, so both versions can
  coexist.

**A caveat the 3-band panel exposed: x ≤ 0.05 is "oceanic" only in the
red.** Pure seawater already has x ≈ 0.17 at 450 nm (a_w is small, b_bw is
large), so the clip removes almost all clear water in the blue. It keeps
only the strongly absorbing realisations:

| λ (nm) | 400 | 450 | 500 | 550 | 600 | 650 | 700 |
|---|---:|---:|---:|---:|---:|---:|---:|
| kept by x ≤ 0.05 (of 5,000) | 409 | 321 | 288 | 2,581 | 3,680 | 3,922 | 4,136 |
| median C kept (mg m⁻³) | 1.03 | 1.76 | 0.28 | 0.04 | 0.08 | 0.09 | 0.11 |

So in panel (a) the 450 nm points (N = 321) are high-Chl/CDOM waters only,
and the blue bands in panel (b) come from the same subset.
- **What happens with a per-realisation clip.** I kept the realisations with
  x(650) ≤ 0.05 at every band: 3,922 runs × 16 bands. The median trend in (b)
  survives, with G going from 0.058 to 0.044 across b_bp/b_b. But the blue
  bands then reach x ≈ 0.3, where G also *rises with x*. The collapse
  loosens: log G has 8.5 % rms about a curve in b_bp/b_b alone, and 4.8 %
  with x and b_bp/b_b together.
- **Revised statement of the prompt 2 result.** For x ≤ 0.05, G is set by
  b_bp/b_b (1.4 % rms). Over a wider x range, G depends on both b_bp/b_b and
  x. The 25 % molecular-fraction effect holds in both cases.

#### Questions for JXP (prompt 4)

12. **Q12: How to clip.**
    - (a) Keep the per-point x ≤ 0.05 clip (as now). It is clean, but the
      blue bands then represent only absorbing water.
    - (b) Clip per realisation, on x(650) ≤ 0.05 or b_bp(650) ≤ some value,
      and keep those realisations at every band. That is closer to "oceanic
      waters", but panel (b) gets more scatter, and panel (a)'s 450 nm
      ribbon extends to x ≈ 0.3.
    - (c) Keep (a) for panel (b) but use (b) for panel (a).

    *(My recommendation: (a) for the talk. Its message is cleanest, and the
    caption can say "x ≤ 0.05". I would mention (b) only if asked.)*

    **A:** Agreed, stick with (a)
13. **Q13: Is the 3-band panel (a) worth it?** Under the current clip the
    three ribbons mostly overlap. Only 550 nm stands out a little, above the
    others near x ≈ 0.015–0.05. Under clip (b) they would separate more.
    Keep it as the default, or make 650-only the default again?

    **A:** No, I am not going to show the 3-band figure, only the 1-band.


#### Prompt 5: rrs option, 1-band default

*Response to RT+bbp/bb prompt 5 (Claude Opus 5.5, 2026-11-20).*

**Q12/Q13 applied.** The per-point x ≤ 0.05 clip stays. Panel (a) is again
650 nm only by default (`EXTRA_BANDS = ()`). The 3-band version is still
available with `--extra-bands 450 550`, or `fig_rrs_vs_x(extra_bands=(450, 550))`.

**The rrs option.** Use `python papers/bbp/talks/figs_awoc2026.py --rrs`, or
`fig_rrs_vs_x(refl="rrs")`. The file name is the same
(`pb24_rrs_vs_x_650.png`), so the two versions overwrite each other. Use
`--out-dir` to keep both. In the rrs version:
- **The data are Hydrolight's own sub-surface rrs.** PB24 stores it next to
  Rrs (`rrs.npy`, same 4-D geometry grid), so I read it at the same
  θs = 0°, nadir geometry. It is not a Lee et al. (2002) inversion of Rrs.
- **The reference is the plain Gordon (1988) polynomial.** Panel (a) uses
  rrs = 0.0949x + 0.0794x², and panel (b) has a dashed line at its x → 0
  limit, G = **0.0949** sr⁻¹. Both are labelled "Gordon (1988)". In the Rrs
  version those two references are now labelled
  "Gordon (1988) + Lee (2002)", which is what they are.
- **The axis labels** become r_rs and r_rs/[b_b/(a+b_b)].

**What changes physically: almost nothing.** The molecular-fraction effect
is a sub-surface effect, so it carries over unchanged:

| | G at b_bp/b_b < 0.2 | G at b_bp/b_b > 0.9 | fall | rms of log G about the b_bp/b_b median |
|---|---:|---:|---:|---:|
| Rrs/x | 0.0571 | 0.0431 | 24.4 % | 1.41 % |
| rrs/x | 0.1085 | 0.0814 | 25.0 % | 1.35 % |

(x ≤ 0.05, 400–700 nm every 20 nm.)

**One small difference: Hydrolight's Rrs/rrs is not a constant 0.52.** At
x ≤ 0.05 the median Rrs/rrs rises with λ:

| λ (nm) | 400 | 450 | 500 | 550 | 600 | 650 | 700 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hydrolight Rrs/rrs | 0.518 | 0.522 | 0.525 | 0.525 | 0.527 | 0.528 | 0.529 |
| Hydrolight / Lee (2002) | 0.990 | 0.998 | 1.003 | 1.006 | 1.012 | 1.014 | 1.018 |

That is a 2–3 % spread across the visible. It is probably the wavelength
dependence of water's refractive index (the n² factor in the radiance
transfer), but I have not checked Hydrolight's settings. You can see it in
panel (b):
- In the **Rrs** version the blue bands sit slightly *below* the median.
- In the **rrs** version they sit on or above it.

This supports your point. In rrs, the cross-band scatter in (b) comes only
from the in-water physics, with no surface-transfer term mixed in.

#### Questions for JXP (prompt 5)

14. **Q14: Which reflectance is the talk default?** The code still defaults
    to Rrs, so nothing changed unless you pass `--rrs`.
    - rrs is cleaner for the argument, because Gordon is a polynomial in rrs.
    - Rrs is what PACE delivers and what the audience knows.

    *(My recommendation: show rrs, and say in one line that Rrs ≈ 0.52 rrs
    up to a 2–3 % λ-dependent factor. If you agree, I will flip the default
    to rrs.)*

    **A:** Yes, we will make rrs the talk default.

## Logs

### 2026-11-20 (RT+bbp/bb prompt 1: PB24 Hydrolight data confirmed readable; 650 nm group-selection problem raised)

Located the PB24 reader pointers. The prompt doc is
`retrieve-or-bust/claude_prompts/RT/rt_fit_pb24.md`, not under
`design/ztt_pb24/`. Opened the consolidated cache
(`$OS_COLOR/SD/derived/pb24_v1/`, 5,000 realisations, through
`robust.rt.data.pb24_cache.open_cache()` in ocean14) and extracted
everything the figure needs at 650 nm:
- a from `aw`, `aph`, `ag` and `aNAP`;
- b_bw and b_bp from `bbw`, `bbph` and `bbNAP`;
- above-water `Rrs` at θs = 0 and 30°, nadir view.

All 5,000 values are finite. The files are Raman-free ("no_R"). Found that
at 650 nm a ≈ a_w and b_bw is constant, so b_bp/b_b tracks x = b_b/(a+b_b).
The global bottom and top 10 % groups occupy disjoint x ranges
(0.0013–0.0017 vs 0.066–0.91). Within log-x bins, the low-b_bp/b_b decile
has Rrs/x 7–12 % higher at small x. Above x ≈ 0.05, b_bp/b_b is
0.99–1.00 and the difference is not driven by b_bw. Pooling 400–700 nm
makes the groups overlap, but the low group is then dominated by blue
bands. Wrote five design questions in Q&A / RT+bbp/bb. No figure yet. The
working arrays are in the session scratchpad (`pb24_650.npz`).

Lessons: PB24 uses a single seawater b_bw (4.25e-4 m⁻¹ at 650 nm), so b_bw
varies only with λ. Any "molecular vs particle" split at one band reduces to
a b_bp split.

### 2026-11-20 (RT+bbp/bb prompt 2: first draft of the 2-panel PB24 Rrs vs b_b/(a+b_b) figure; prompt 1 finding corrected)

Wrote `papers/bbp/talks/figs_awoc2026.py` with `load_pb24_band`,
`gordon_Rrs`, `binned_extremes` and `fig_rrs_vs_x`, plus a small CLI.
Rendered `papers/bbp/talks/pb24_rrs_vs_x_650.png`:
- (a) Rrs vs x, all 3,922 realisations with x ≤ 0.05, coloured by b_bp/b_b;
- (b) Rrs/x vs x for the lowest and highest 10 % of b_bp/b_b within 10
  log-x bins;
- geometry θs = 0 and nadir view, log–log axes, Gordon (1988) + Lee (2002)
  reference curve.

Placing each group's median at its own x, rather than the bin centre,
removed the 7–12 % gap I reported in prompt 1. At one band, x and b_bp/b_b
are the same variable (ρ = 0.999 at 650 nm), because a ≈ a_w and b_bw is
fixed. Pooling 400–700 nm decouples them (ρ = 0.32). Rrs/x then collapses
onto b_bp/b_b: 1.4 % rms, against 9 % for x alone. It falls about 25 %, from
0.057 to 0.043, going from water-dominated to particle-dominated
backscatter. Marked the prompt 1 claim as corrected. Added Q6–Q8: rework
panel (b) as Rrs/x vs b_bp/b_b pooled over λ (recommended), the colour scale
of panel (a), and the output location.

Lessons: when choosing deciles inside bins of a steep function, plot each
group at its own median x, not the bin centre. Otherwise a within-bin x
offset reads as a group effect.

### 2026-11-20 (RT+bbp/bb prompt 3: second draft, panel (b) as G vs b_bp/b_b pooled over λ, logit colour bar)

Applied Q6 = b, Q7 = logit and Q8 = keep. Panel (a) colour bar is now
logit(b_bp/b_b) via a `FuncNorm` (limits 0.02–0.995; the logit is clipped
because the colour bar probes 0 and 1). Panel (b) is now Rrs/x vs b_bp/b_b
over 400–700 nm every 20 nm plus 650 nm, x ≤ 0.05, 39,747 points coloured by
λ. It shows the all-band median, the 650 nm-only median and the Gordon (1988)
band. Added `load_pb24_bands` and `POOL_WAVES`. Result: G falls about 27 %,
from 0.059 to 0.043, as b_bp/b_b goes 0 → 0.93. The 650 nm-only median
overlays the all-band median, and Gordon crosses it near b_bp/b_b ≈ 0.5.
Rendered and inspected three iterations:
- the 650 nm band was missing from the 20 nm pool, so it is now always added;
- hollow 650 nm markers hid the median, so they became a thin median line.

Added Q9–Q11: the λ colour map, the Gordon reference style, and a possible
multi-band panel (a).

### 2026-11-20 (RT+bbp/bb prompt 4: third draft with jet λ colours, a Gordon line and an optional 3-band panel (a); the x-clip caveat)

Applied the answers:
- Q9: `CMAP_WAVE = "jet"`.
- Q10: `GORDON_G0` = 0.0493, a dark-grey dashed line.
- Q11: `EXTRA_BANDS = (450, 550)` with a revert path, `extra_bands=()` or a
  bare `--extra-bands`. Panel (a) colours each band by λ, with a legend; the
  single-band path keeps the logit(b_bp/b_b) colour bar.

The 650 nm median in (b) is now a white line with a dark outline (path
effects). Output names now encode the bands. Rendered and inspected both
versions. The first 3-band render had colliding direct labels and 650 nm
drawn on top, so I switched to a legend and a random draw order. Found that
x ≤ 0.05 keeps only 6–8 % of realisations at 400–500 nm, the absorbing
high-C ones, because pure-water x(450) ≈ 0.17. With a per-realisation
x(650) ≤ 0.05 clip the median G trend holds, but its collapse onto b_bp/b_b
loosens from 1.4 % to 8.5 % rms (4.8 % with x and b_bp/b_b together).
Restated the prompt 2 result as holding for x ≤ 0.05. Added Q12 (clip
definition) and Q13 (3-band default).

Lessons: a clip in x defined at one band is not a water-type clip at other
bands. To select water types across bands, clip per realisation.

### 2026-11-20 (RT+bbp/bb prompt 5: an rrs option for the PB24 figure; 650 nm-only panel (a) is the default again)

Applied the Q12/Q13 answers. The per-point x ≤ 0.05 clip stays, and
`EXTRA_BANDS` now defaults to `()`, so panel (a) is 650 nm only. Use
`--extra-bands 450 550` to get the 3-band version back.

Added a reflectance option, `fig_rrs_vs_x(refl="rrs")` or CLI `--rrs`. File
names are unchanged.
- `load_pb24_band` now also returns Hydrolight's own sub-surface rrs. PB24
  stores it next to Rrs in `rrs.npy`, on the same 4-D geometry grid.
- New `gordon_rrs` function and `GORDON_G1`/`GORDON_G2` constants.
- New `REFLECTANCE` table, keyed by `"Rrs"`/`"rrs"`. Each entry gives the
  panel-(a) curve, the panel-(b) x → 0 G (0.0493 for Rrs, 0.0949 for rrs),
  the axis symbol and the legend label.
- In the Rrs version the Gordon label is now "Gordon (1988) + Lee (2002)".

Results:
- The molecular-fraction effect is unchanged in rrs. G falls by 25.0 %
  across b_bp/b_b, with 1.35 % rms about the b_bp/b_b median. For Rrs the
  figures are 24.4 % and 1.41 %.
- Hydrolight's Rrs/rrs is not Lee's constant 0.52. It rises from 0.518 at
  400 nm to 0.529 at 700 nm, i.e. 0.990 to 1.018 × Lee. This is probably
  n(λ). It explains why the blue bands sit low in the Rrs version of panel
  (b) but not in the rrs version.

Rendered `papers/bbp/talks/pb24_rrs_vs_x_650.png` (Rrs, default) and an rrs
copy in the session scratchpad, and inspected both. Added Q14 (make rrs the
default?).

### 2026-11-20 (RT+bbp/bb prompt 5b: rrs is now the default; wrap-up after the move to talks/AWOC2026/)

The doc moved from `prompts/talk_awoc2026.md` to
`prompts/talks/aw2026_rrs_bbp.md`. The script moved from
`talks/figs_awoc2026.py` to `talks/AWOC2026/fig_rrs_bbp.py`.

Changes to `fig_rrs_bbp.py`, applying the Q14 answer ("make rrs the talk
default"):
- `fig_rrs_vs_x(refl=...)` now defaults to `"rrs"`. Its docstring describes
  both options.
- The CLI flag is now `--Rrs`, which selects the above-water version. It
  replaces `--rrs`.
- The module docstring now points at the new doc and script paths.

Re-rendered `talks/AWOC2026/pb24_rrs_vs_x_650.png` (rrs, 650 nm-only panel
(a)) and inspected it. JXP considers the figure done.

The untracked `talks/AWOC2026/pb24_rrs_vs_x_450_550_650.png` is a leftover
from draft 3. It is no longer the default output and can be deleted.
