# PAB Websites

## Goals

This prompt doc will be used to update the websites for the PAB GitHub Repository.  This includes both the GitHub facing site -- https://github.com/ocean-colour/PAB -- and the Read the Docs site -- https://pab.readthedocs.io/en/develop/ but not the Reports -- https://pab-report.readthedocs.io/en/develop/


## Prompts

1. Read this file.  Execute the 1st task under "GitHub Website"
2. Read this file.  Execute the 2nd task under "GitHub Website"
4. Read this file.  Execute the 4th task under "GitHub Website"
5. Read this file.  Execute the 5th task under "GitHub Website"
6. Read this file.  Execute the 6th task under "GitHub Website"
7. Read this file.  Execute the 7th task under "GitHub Website"
8. Read this file.  Execute the 8th task under "GitHub Website"

## GitHub Website

### Tasks

1. Let's improve the GitHub website via our README.md file. Please:

    - Add the SeaMeetstheStars logo which you can find here: `https://github.com/Sea-Meets-the-Stars`
    - Add a long description of the project.  Pull from the RTD website
    - Add the developer names: J. Xavier Prochaska and Allie James

In addition, create a new graphic which summarizes the project.  Use your imagination, and feel free to ask questions first in the Q&A section.  I will also use this grahpic in talks and presentations.  If you can, use `matplotlib` to create the graphic and save the Python script as `pab_graphic.py` in the `docs/scripts` directory.
    
2. Let's iterate on the graphic.  The current one is very boring.  We want one that grabs the attention of oceanographers.  Assume they have some knowledge of PACE and BGC-Argo.  Let's start a conversation on this topic.  You are allowed to grab images from the internet to use in the graphic.  Ask me questions in Q&A below first before making the next iteration.  Log your work.

3. Ok, I have answered your questions.  Please create a new graphic based on the answers.  Save the Python script as `pab_graphic.py` in the `docs/scripts` directory.  Log your work.

4. This is great!  Please make the following edits:

    - use larger fonts everywhere
    - Do not show a strong absorption dip in the Rrs spectrum in the red
    - Where possible, avoid putting text on any lines, etc.
    - Make the PACE image larger
    - Make the BING retrieval image larger
    - Make the Rrs panel larger
    - In general, there is too much open (i.e. wasted) space in the graphic.  
    - Log your work.

5. Better.  Here are more edits to make:

    - The PACE/OCI text is right on the ocean surface and impossible to read.  Move it 
    - The BGC-Argo float should have a longer aspect ratio.
    - The "matched water column" text is too hard to read
    - Most of the text needs to be larger still
    - Log your work.

6. Almost there.  Now:

    - The a_nw in the BING retrieval panel is on the curve and hard to read.  Move it to the right
    - Move the BGC-Argo float text up and off the BING retrieval panel
    - Make the bbp, Chl, and T-S text darker
    - Move the Rrs curve down a little so it is off the "hyperspectral" text
    - Move the water surface down a bit so you can make the images up top larger. do so
    - Log your work.

7. Hopefully the last edits for now:

    - You moved the BGC-Argo float text up too high.  Move it down a bit
    - Move the "water-leaving Rrs(λ)" text a little to the left
    - Move the "bbp / Chl / T-S" text closer to the profile curve
    - Log your work.

8. Last one for now

    - Spell out PAB (PACE and BGC-Argo)
    - Log your work.

### Q&A

#### 2026-07-10 — Graphic iteration (task 2): questions before redesign

The current graphic is a plain box-and-arrow flow chart — functional but boring.
Before building an attention-grabbing version for oceanographers, a few
decisions. Please answer inline under each question (or edit freely).

**Q1. Central visual concept** — the biggest lever on the look. Which one?

- **(a) "Light's journey" scene** — a cross-section: sun → sea surface, PACE
  viewing from above, a BGC-Argo float profiling below, converging on one
  matched water column. Iconic and instantly readable to oceanographers.
- **(b) "Real-data hero"** — a striking composite of *actual* results: a PACE
  hyperspectral Rrs(λ) spectrum, the BING-retrieved IOP spectra with
  uncertainty bands, and an Argo bbp(z) profile. The science, shown beautifully.
- **(c) "Global map matchup"** — a world ocean-color basemap with a PACE swath
  and BGC-Argo float positions, plus a zoom-in callout to a single matchup.
- **(d) "Hybrid"** — the "light's journey" scene as a backdrop with a real-data
  inset (spectrum + retrieved IOPs). Richest, but busier / more design risk.

  *Answer:* (a)

**Q2. Real data or illustrative curves?**

- **(a) Real repo data** — pull actual fits from `data/fit_chains/` and the
  biomass analysis CSVs (real PACE Rrs, BING IOPs, Argo bbp profiles). More
  authentic; I'll pick clean, representative examples.
- **(b) Illustrative curves** — synthetic but realistic-looking. Guaranteed
  clean, fully reproducible, no dependence on data-file paths.

  *Answer:* (b)

**Q3. May I embed external (NASA / public-domain) imagery?**

- **(a) Yes** — PACE satellite render, a real ocean-color granule, a BGC-Argo
  float photo. Visually richer, but adds downloaded image assets to the repo.
- **(b) No, pure matplotlib** — 100% vector/drawing, self-contained and fully
  reproducible, but more schematic.

  *Answer:* (a)

**Q4. Aesthetic tone for how you'll use it?**

- **(a) Dark hero** — deep ocean/space background, luminous accents. Dramatic on
  a projector.
- **(b) Clean light** — works in README and slides, prints well; safer.
- **(c) Both** — I generate a dark and light variant from one script (a flag).

  *Answer:* (c)

**Q5. Anything specific to feature or avoid?** — e.g. a particular study region,
the "Sea Meets the Stars" identity, hyperspectral resolution as a selling point,
a color scheme to match your slide template.

  *Answer:* No, nothing to avoid for now.

## Logging

The "Logs" section will record Claude's work.  Please use the following format:

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

...

## Logs

### 2026-07-10 (GitHub README overhaul + project summary graphic)

Executed the 1st task under "GitHub Website". Rewrote `README.md`:

- Added the **Sea Meets the Stars** logo (the org avatar,
  `https://avatars.githubusercontent.com/u/77852500?v=4`, linked to the org
  page) in a centered header alongside the title, tagline, and CI/RTD badges.
- Added a long **Overview** section describing the project and the end-to-end
  pipeline (float mixed-layer summary → space/time matchup → ~10 nearest PACE
  Rrs spectra → BING retrieval → reports), pulled from the RTD design doc
  (`docs/design/PAB_design.md`) and `docs/index.rst`.
- Added a **Developers** section: J. Xavier Prochaska and Allie James.

Created `docs/scripts/pab_graphic.py` — a self-contained matplotlib figure (no
data files needed) summarizing the pipeline as a left-to-right flow: PACE and
BGC-Argo converge into Matchup → BING fit → IOPs + reports. Uses a
colorblind-safe Okabe-Ito palette (one hue per entity). Writes
`docs/figures/pab_summary.png` plus a transparent-background copy for dark
slides. The README embeds the PNG at the top.

Note: the graphic script is a design draft — the "~10 nearest Rrs spectra" and
"LM → MCMC" details mirror the design doc; worth a glance to confirm they match
current pipeline behavior before using in talks.

### 2026-07-10 (Graphic iteration — questions posed)

Started task 2 ("iterate on the graphic"). The current `pab_summary.png` is a
plain box-and-arrow flow chart — accurate but boring. Per the task instructions,
I did not build a new version yet; instead I posed five design questions in the
Q&A section above (central concept, real vs illustrative data, external imagery,
aesthetic tone, and anything to feature/avoid). Confirmed that real matchup data
is available for a data-driven design: fit chains in `data/fit_chains/*.npz` and
a large set of biomass-analysis CSVs (real PACE Rrs, BING IOPs, Argo bbp
profiles). Waiting on answers before the next iteration.

### 2026-07-11 (New "light's journey" hero graphic — task 3)

Executed task 3 using the Q&A answers: (a) light's-journey cross-section,
(b) illustrative curves, (a) NASA imagery allowed, (c) both dark + light.

Rewrote `docs/scripts/pab_graphic.py` into a hero figure. Composition (a vertical
cross-section of the ocean): sun in the upper sky casts a warm downwelling shaft
into a highlighted "matched water column"; the PACE satellite sits above-right
with a viewing cone to the surface footprint and upwelling `water-leaving
Rrs(λ)` arrows back to the sensor; a stylized BGC-Argo float profiles inside the
same column, with an illustrative `bbp/Chl/T-S` depth profile beside it; a small
`Rrs(λ)` spectrum panel (top-left) advertises the hyperspectral input, and a
`BING retrieval` callout (lower-right) shows retrieved `a_nw`/`b_b,nw` with
uncertainty bands. Title/branding in the corners.

Data are illustrative (synthetic-but-realistic) curves so the script is fully
reproducible with no data-file dependencies. One real, **public-domain** PACE/OCI
ocean-color image (Black Sea phytoplankton bloom, NASA SVS31294) is embedded as
the "what PACE sees" inset; downloaded, downscaled, and credited in
`docs/figures/assets/CREDITS.md`. If that asset is missing the inset degrades to
a drawn placeholder, so the script never hard-fails.

The script emits both `pab_summary_dark.png` and `pab_summary_light.png` from a
single `THEMES` dict (one flag / CLI arg). README now embeds them via a
`<picture>` element that swaps dark/light with the viewer's GitHub color scheme;
the old plain flow-chart PNGs were removed.

Notes / gotchas learned:
- NumPy 2.0 removed `ndarray.ptp()`; use `np.ptp(arr)`.
- Direct NASA/nasa.gov image URLs 404'd; the reliable path was the Wikimedia
  Commons API (search namespace 6, then `imageinfo` for the real upload URL and
  license). Filtered to a **public-domain** asset (the Argo float photo was
  CC BY-SA, so the float is drawn in vector instead to stay license-clean).
- Clipping an `imshow` to a rounded box: set a `FancyBboxPatch` (with
  `transform=ax.transData`) as the image's clip path.

Open question for JXP: the figure currently reads well as a talk slide; if you
want a **data-backed** variant (real Rrs + real BING IOP posterior from
`data/fit_chains/`) for the paper/README instead of illustrative curves, say so
and I'll add a `--real` mode.

### 2026-07-11 (Graphic polish pass — task 4)

Applied JXP's edit list to `docs/scripts/pab_graphic.py` and re-rendered both
themes:

- **Larger fonts everywhere** — bumped every text element (title 30→38, actor
  labels 11→16, panel titles/labels ~9→13–15, footer 9.5→12) via the panel
  helpers and a larger default `label()` size.
- **No red dip in Rrs** — dropped the Chl absorption term from `rrs_spectrum()`;
  the spectrum is now a clean blue-green peak tapering gently into the red.
- **Text off lines** — moved the "water-leaving Rrs(λ)" label into clear sky
  beside (not on) the upwelling arrows, parked the `bbp/Chl/T-S · profile(z)`
  labels in open water to the left of the profile curve, and lifted "matched
  water column" clear of the arrows.
- **Bigger panels** — PACE ocean-color inset (15×12 → 24.5×18), BING retrieval
  callout (24×22 → 29.5×31), and the Rrs panel (17×15.5 → 30×19).
- **Less wasted space** — re-anchored the whole composition: sun moved to top
  center (light now enters straight down the column), satellite/inset pulled to
  fill the top-right, BING panel fills the lower-right, and the enlarged bbp(z)
  profile fills the left. Widened the matched column (9→11) and enlarged the
  float. Also made the sun render as a round disc (Ellipse with the x/y
  data-unit aspect) instead of a stretched ellipse.

README needs no change — it already embeds both `pab_summary_{dark,light}.png`.
File sizes ~480 KB each (up from ~320 KB) due to the larger panels + type.

### 2026-07-11 (Graphic readability pass — task 5)

Applied JXP's second edit list to `docs/scripts/pab_graphic.py`:

- **Moved the "PACE / OCI · ocean color" caption off the sea surface.** It was
  drawn just *below* the inset, which landed on the wavy surface line and was
  unreadable. `rounded_image()` now draws the caption *above* the image (as a
  title). Nudged the satellite left (sat_x 71→68) so the enlarged caption clears
  its right solar panel.
- **Longer float aspect ratio** — `draw_float()` cylinder went 4.0×13.5 →
  3.0×18.0, i.e. the tall, thin profiling-float look.
- **Readable "matched water column"** — was low-contrast teal text sitting on
  the busy translucent column. Now a bold, high-contrast label inside a rounded
  "pill" (panel-fill background + surface-color border, alpha 0.95) placed just
  under the surface.
- **Even larger text** — another size bump across the board (title 38→42,
  subtitle 17→20, actor labels 16→19, panel titles 13.5→16–17, Rrs/IOP axis
  labels →15–16, footer 12→14, water-leaving 15→18).

Re-rendered both themes (~495 KB each) and verified in light and dark: the
caption, pill, and long float all read cleanly and nothing collides. README
still needs no change (same file names). The `--real` (data-backed) variant
remains available if wanted.

### 2026-07-11 (Graphic fine-tuning pass — task 6)

Applied JXP's third edit list to `docs/scripts/pab_graphic.py`:

- **`a_nw` moved right, off the curve** — the a_nw label sat on the aph
  fluorescence bump near the right end of the BING panel. Compressed the IOP
  curves into the left ~64% of the panel (xs range 0.74→0.64 of width) and moved
  both the `a_nw` and `b_b,nw` labels into the clear right-hand margin,
  left-aligned just past each curve's endpoint.
- **"BGC-Argo float" text up and off the BING panel** — was at (64, 33), which
  overlapped the BING panel's top-left corner. Moved up-and-left to (60, 51),
  above the float and clear of both the panel and the float's up-arrow.
- **Darker bbp/Chl/T-S labels** — switched the profile labels from the muted
  secondary ink (`ink2`) to the primary ink (`ink`) for maximum contrast in both
  themes.
- **Lowered the Rrs curve** — in `mini_curve()`, dropped the curve baseline and
  amplitude (0.20+0.58h → 0.14+0.50h) so the blue-green peak clears the
  "hyperspectral Rrs…" panel title.
- **Lowered the sea surface + enlarged the top imagery** — `SEA` 66→60, opening
  up the sky. Grew the PACE inset (24.5×18 → 27.5×23) and the Rrs panel
  (30×19 → 34×23), and re-anchored the sun/satellite and the underwater
  elements (profile, float, matched-column pill) to the new surface height.

Re-rendered and verified both themes (~585 KB each). README unchanged (same
file names). The `--real` data-backed variant is still on the table.

### 2026-07-11 (Graphic nudge pass — task 7)

Three position tweaks in `docs/scripts/pab_graphic.py`:

- **"BGC-Argo float" label lowered** — task 6 moved it up too far (y 51); brought
  it back down to y 46, so it sits beside the float rather than floating high.
- **"water-leaving Rrs(λ)" moved left** — x 46 → 41, further from the upwelling
  arrows and into clearer sky.
- **"bbp / Chl / T-S · profile(z)" moved closer to the profile curve** — x 16 →
  22, so the labels read as belonging to the orange bbp(z) curve (kept just left
  of the curve so they don't sit on it).

Re-rendered and verified both themes. README unchanged (same file names).

### 2026-07-11 (Spell out the acronym — task 8)

Changed the graphic's subtitle in `docs/scripts/pab_graphic.py` from
"PACE × BGC-Argo matchup analyses" to **"PACE and BGC-Argo matchup analyses"**.
This spells out the acronym literally — PAB = **P**ACE **a**nd **B**GC-Argo —
using "and" in place of the "×" so the three initials read straight off the
tagline under the big "PAB" title. Re-rendered both themes; no overflow, layout
otherwise unchanged. (The README tagline already reads "PACE and BGC-Argo
matchup analyses", so it needed no change.)
