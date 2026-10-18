# The high-`b_bp` outliers in the BING 2.0 fits

*Investigation for `claude_prompts/v2/report_improvements.md` → Prompts/Outliers 1
(2026-10-18, run with Fable). Database: `$PAB_DATA_DIR/v2/pab.db`, opened
read-only. Spectra and chains: the 51 outlier NPZs plus a 300-fit random sample
copied from the Drive backup `AIOcean:PAB/v2/fit_chains/`. Figures in
[`high_bbp_outliers/`](high_bbp_outliers/). Nothing in `pab/` was changed; the
re-fits below are exploratory, not production results.*

## Summary

- **51 of 15,971 BING 2.0 fits have `b_bp`(700) above 1 m⁻¹, and all 51 are
  above 10⁴ m⁻¹** (5.0×10⁴–9.3×10⁴). The two thresholds select the same set:
  the 52nd-largest value is 0.03 m⁻¹, six orders of magnitude lower. There is
  no continuum of "somewhat high" values, so this report covers exactly those
  51. All 51 have `success = 1`, 47 distinct granules, 25 floats.
- **They are not clear-water retrievals.** The run report (§2.5) called them
  the "ultra-oligotrophic tail" because the *retrieved* Chl is 0.01 mg m⁻³ —
  but that Chl is part of the failed fit. The floats under them have a median
  Chl of **0.93 mg m⁻³** (population 0.15) and median `b_bp`(700) of
  **3.6×10⁻³ m⁻¹** (population 6.9×10⁻⁴). They sit in optically complex
  marginal seas: **25 in the Baltic**, 9 in the tropical Atlantic/Caribbean,
  7 in the Arabian Sea/Gulf of Oman, and singles in the Black Sea, the
  Ligurian Sea, the Barents and Labrador Seas, the Kuroshio–Oyashio region,
  the NE Pacific coast, the California Current and the Agulhas.
- **The observed spectra are pathological in the blue.** 40 of 51 (type A)
  have *negative* Rrs at 400–450 nm (down to −4.3×10⁻³ sr⁻¹; median minimum
  −1.0×10⁻³, i.e. −1.2 σ of the stored `Rrs_unc`) — the signature of a failed
  atmospheric correction, typically at a cloud edge (median granule cloud
  cover 68 %). The other 11 (type B, all Baltic) are positive everywhere but
  have Rrs(440)/Rrs(555) = 0.24–0.55 against a population median of 4.1 — a
  CDOM-rich, green-peaked spectrum that is plausibly real water.
- **What went wrong is the optimiser, not the sampler.** Every one of the 51
  chains *started* with `Bnw` (log₁₀ of `b_bp`(600)) above 4.5 — the LM
  warm-start delivered the walkers to the prior ceiling (`Bnw` ≤ 5, i.e.
  10⁵ m⁻¹) and the 1 % walker ball never left it (minimum `Bnw` seen anywhere
  in any chain: 2.9). The χ² surface has **two basins**: a physical one
  (`b_bp`(600) ≈ 5×10⁻⁴–8×10⁻³ m⁻¹) and a spurious one at the ceiling, where
  `b_b ≫ a` and the forward model's reflectance saturates at a level set by
  the backscatter ratio `B_p` rather than by `b_b`; they are separated by a
  χ² wall of 10²–10⁵ at `b_bp` ≈ 1–10 m⁻¹. In all four re-fitted cases the
  physical basin is the *better* fit (reduced χ² 1.8 vs 11.1, 0.45 vs 10.5,
  2.3 vs 7.0, 0.21 vs 1.7), and its `b_bp`(700) agrees with the float and
  with the 1.0 Gordon fit to within a factor of ~2. The production LM, run
  from the same initial guess, lands in the spurious basin for 3 of the 4;
  perturbed starts land there 0, 2, 6 and 3 times out of 12.
- **A pre-fit screen "any Rrs < 0 at 400–450 nm" catches 40/51** and flags
  about 0.7 % of the rest (2 of 300 sampled, ≈ 100 fits), and those two are
  themselves doubtful. Adding "Rrs(440)/Rrs(555) < 0.6" catches 50/51 but
  the extra flags are *good* Baltic/high-latitude fits.
- **Recommended:** (i) keep reporting the 51 as failed retrievals and drop
  them from the `b_bp` statistics behind an explicit plausibility gate; (ii)
  re-fit the 51 under a new `pab_version` with a physical ceiling on the
  `Bnw` prior (10⁻¹ m⁻¹ instead of 10⁵) and/or a multi-start LM, and verify
  that the chains start in the physical basin; (iii) record a per-fit Rrs QA
  flag (negative blue bands) rather than refusing to fit. Questions are in
  the prompt doc under Q&A/Outliers.

## 1. Identification

Quantity `BING_ExpBPow_bbp700` on the 15,971 `fits` rows with
`algorithm = 'BING'`, `pab_version = '2.0'`:

| threshold | fits |
|---|---|
| `b_bp`(700) > 0.01 m⁻¹ | 92 |
| > 0.03 | 51 |
| > 1 (`BBP_IMPLAUSIBLE`, the report's gate) | 51 |
| > 10⁴ (the prompt's number) | 51 |
| maximum | 9.32×10⁴ m⁻¹ (6903874/139) |

The 51 are the same whichever of the two thresholds is used. By region
(float position) and by observed-spectrum type:

| region | n | with negative Rrs at 400–450 nm | float Chl (median, mg m⁻³) | float `b_bp`(700) (median, m⁻¹) |
|---|---|---|---|---|
| Baltic Sea (floats 1902683, 4903784, 2903902, 4903850) | 25 | 14 | 1.25 | 5.6×10⁻³ |
| tropical Atlantic / Caribbean | 9 | 8 | 0.25 | 1.1×10⁻³ |
| Arabian Sea / Gulf of Oman | 7 | 7 | 0.60 | 1.3×10⁻³ |
| NW Pacific (Kuroshio–Oyashio) | 2 | 1 | 4.2 | 5.0×10⁻³ |
| NE Pacific coast | 2 | 2 | 1.0 | 1.5×10⁻³ |
| Agulhas, Barents, Labrador, California, Black Sea, Ligurian | 6 | 6 | 0.3–2.4 | 0.7–5.7×10⁻³ |

Three floats account for 25 of the 51 (1902683: 10, 4903784: 10, 2903902: 5),
all in the Baltic. 48 of the 51 are 1.0-era matchups and 3 are from the 2.0
backfill, in proportion to the two populations (14,605 : 1,366).

Against the full population (medians):

| | 51 outliers | all 15,971 |
|---|---|---|
| reduced χ² | 5.9 (4 below 1.5) | 0.42 (747 above 1.5) |
| retrieved Chl (from `Aph`) | 0.012 | 0.17 |
| retrieved `A_dg` (m⁻¹) | 1,975 (49 above 10; two "mirror" fits have `A_ph` 50–330 instead) | 0.018 |
| `B_p` | 0.0053 (17 at the 0.004 floor) | 0.024 |
| β | 1.57 (27 above 1.5, 11 below 0.2) | 0.40 |
| float Chl (mg m⁻³) | **0.93** (35 of 50 above 0.5; population 27 %) | 0.15 |
| float `b_bp`(700) (m⁻¹) | **3.6×10⁻³** (31 of 50 above 2×10⁻³; population 10 %) | 6.9×10⁻⁴ |
| NASA-GIOP `b_bp`(700) (m⁻¹) | 1.5×10⁻³ (GIOP/float median 0.64) | 8.2×10⁻⁴ |
| BING 1.0 `b_bp`(700), same pixel (48 found) | 3.8×10⁻³ (1.0/float median 0.95; max 8.8×10⁻³) | — |
| latitude > 40° | 33 (65 %) | 19 % |
| θ_s > 60° (the emulator's supported limit) | 3 (71°, 65°, 65°) | 8.8 % |
| granule cloud cover (%) | 68 | 64 |
| separation, Δt | 0.75 km, 10.4 h | 0.80 km, 10.2 h |

The 5–95 % band of `Bnw` reaches 9.5–9.97×10⁴ m⁻¹ on every one of the 51 —
the posterior is pressed against the prior ceiling of 10⁵ m⁻¹
(`bing.parameters.standard.expb_pow`: `Bnw` log-uniform on [10⁻⁶, 10⁵]).
The `Bnw`–`A_dg` posterior correlation is +0.9 for 49 of the 51: it is the
ratio `a/b_b`, not `b_b`, that the data constrain there.

## 2. What the observed spectra look like

![outlier spectra](high_bbp_outliers/outlier_spectra.png)

*The observed Rrs of the 51 runaway fits (left: the 40 type-A spectra with
negative Rrs at 400–450 nm; right: the 11 type-B spectra, all Baltic) over
the 5–95 % envelope and median of a random 300-fit sample of the population.
Every outlier spectrum is green-peaked (Rrs maximum at 490–580 nm) and sits
below the population's 5th percentile in the blue; the population median
peaks at 400 nm.*

![b_bp vs blue](high_bbp_outliers/bbp_vs_blue.png)

*BING 2.0 `b_bp`(700) against two blue-band diagnostics of the observed
spectrum. Left: Rrs(440)/Rrs(555) — the population spans 0.7–10 (1st–99th
percentile), the outliers −0.8 to 1.9 (44 of 51 below 0.6). Right: the
minimum Rrs at 400–450 nm — 40 outliers are negative; 0.7 % of the sample is.
Note the low-end pile-up of sample values at 2–4×10⁻⁶ m⁻¹ (the prior floor;
a separate issue, not treated here) sits at perfectly ordinary blue ratios.*

![map](high_bbp_outliers/outlier_map.png)

*Positions of the 51 (float positions) over all 15,971 fits.*

Type A is the signature of a failed atmospheric correction: the negative
values are concentrated at 400–430 nm, grow toward 400 nm, and the pixels
carry none of the `l2_flags` in `STANDARD_OCEAN_MASK` (`ATMFAIL`, `HILT`,
`STRAYLIGHT`, `CLDICE`, `LOWLW`, …) — the L2 processor did not consider them
failures. The stored `Rrs_unc` at 400 nm is 6–12×10⁻⁴ sr⁻¹ on these pixels,
so a value of −10⁻³ is only 1–2 σ from zero and the likelihood does not
object to it much (the blue bands contribute 16 % of the stored fit's χ² on
6903874/139). The quick-looks show the kind of scene: 6903874/139 is a few
clear pixels in a 96 %-cloudy swath, the float at the edge of the patch.

Type B spectra (positive everywhere, Rrs(440)/Rrs(555) ≈ 0.2–0.5, Rrs(555)
≈ 2.5–3.4×10⁻³ sr⁻¹) are what summer Baltic water looks like: strong CDOM
absorption in the blue and a green/red reflectance peak; the July 2024 scene
of 4903784/112 shows the bright green bloom around the float. Their fits
fail for the same reason as type A, without the negative values — the shape
alone is enough.

## 3. A few of the fits

The stored 2.0 fit figures (observed Rrs, BING posterior median and 5–95 %
band; `b_bp(λ)` below). In every panel the model curve *rises* toward 400 nm
while the data fall — the runaway solution has no blue absorption shape at
all.

| | |
|---|---|
| ![](high_bbp_outliers/6903874_139_fit.png) | ![](high_bbp_outliers/6903874_139_scene.png) |

*6903874/139, equatorial Atlantic (1.1°S, 5.0°W), 2024-08-25, θ_s = 20°,
Δt 2.1 h, 0.4 km. Type A: Rrs from −1.6×10⁻³ at 400 nm through zero at ~435 nm
to 1.9×10⁻³ at 490 nm. `b_bp`(700) = 9.3×10⁴ m⁻¹ (5–95 %: 7.8–9.9×10⁴),
`A_dg` = 633 m⁻¹, β = 0.04, `B_p` = 0.004, χ² = 11.1. Float `b_bp`(700)
1.0×10⁻³, BING 1.0 7.0×10⁻⁴, GIOP 1.2×10⁻³. Right: the scene quick-look — a
96 %-cloudy granule, the float at the edge of a small clear patch.*

![](high_bbp_outliers/7901007_400_fit.png)

*7901007/400, Barents Sea (75.9°N, 43.0°E), 2025-06-05, θ_s = 54°. The most
negative spectrum of the 51: −4.3×10⁻³ sr⁻¹ at 400 nm, 20 negative bands up
to 457 nm. `b_bp`(700) = 6.3×10⁴, `A_dg` = 661, β = 1.79, χ² = 7.0. Float
2.9×10⁻³, BING 1.0 4.6×10⁻³. The physical LM solution (§4) gives 3.6×10⁻³.*

| | |
|---|---|
| ![](high_bbp_outliers/4903784_112_fit.png) | ![](high_bbp_outliers/4903784_112_scene.png) |

*4903784/112, Baltic (55.4°N, 15.3°E), 2024-07-07, θ_s = 34°. Type B: no
negative band, Rrs(440)/Rrs(555) = 0.24, peak 2.7×10⁻³ at 560 nm.
`b_bp`(700) = 7.2×10⁴, `A_dg` = 2,050, β = 1.82, χ² = 10.5. Float `b_bp`(700)
1.8×10⁻², BING 1.0 8.0×10⁻³, GIOP 6.0×10⁻³; the physical LM solution gives
7.6×10⁻³. Four consecutive cycles of this float (111–114) on the same
granule are all runaways. Right: the scene — a bright green summer bloom
around the float.*

![](high_bbp_outliers/2903902_30_fit.png)

*2903902/30, Baltic (55.3°N, 15.6°E), 2024-06-21. The "mirror" mode: here
`A_ph` ran away instead of `A_dg` (`A_ph` = 330 m⁻¹, retrieved Chl 5,900
mg m⁻³, `A_dg` = 0.01), with the same `b_bp` at the ceiling (7.1×10⁴) and a
deceptively ordinary χ² of 1.7 — the lowest-χ² runaway is 0.60, so χ² alone
cannot isolate them. The physical LM solution gives χ² = 0.21 and
`b_bp`(700) = 6.5×10⁻³ against the float's 6.2×10⁻³.*

![](high_bbp_outliers/1902660_51_fit.png)

*1902660/51, Gulf of Oman (24.6°N, 62.6°E), 2026-01-02, Δt 18 h. Type A with
a mild negative blue (−5×10⁻⁴ at 400 nm) — the Arabian Sea group (7 fits,
floats 1902660, 1902751, 2902272, 6990700) is the dust-aerosol regime where
the standard atmospheric correction is known to over-correct the blue.*

![](high_bbp_outliers/4902683_264_fit.png)

*4902683/264, NE Pacific coast (51.8°N, 131.2°W), 2026-01-23, **θ_s = 71°** —
outside the emulator's supported solar-zenith range (0–60°; 3 of the 51 and
8.8 % of all fits are). A winter high-latitude scene with Rrs negative to
460 nm and a second dip at 660 nm. `b_bp`(700) = 8.3×10⁴, χ² = 1.6.*

## 4. Why BING answers a depressed blue with `b_bp` = 10⁵ m⁻¹

**The saturation limit.** In any reflectance model Rrs is driven by
`u = b_b/(a + b_b)`. Once `b_b ≫ a`, `u → 1` and Rrs stops depending on the
*magnitude* of `b_b`; only the ratio `a/b_b` matters (which is why `Bnw` and
`A_dg` are +0.9-correlated in the outlier posteriors, with `A_dg` at
10²–10⁴ m⁻¹). In the ZTT backbone that 2.0 uses
(`robust.rt.ztt.rrs_ZTT`),

    rrs = (1/µ_d)(β(ψ)/b_b) / [ (a/b_b)(1 − cosθ_v Ψ/µ_∞) + f_L(1 − 1/b̃_b) + 1/b̃_b ],

and in the `a/b_b → 0` limit the denominator is set by `1/b̃_b`, where
`b̃_b = b_b/b ≈ B_p` once particles dominate. With `B_p` at its 0.004 floor
(17 of the 51 are there) the saturated reflectance is a few ×10⁻⁴ sr⁻¹ —
the same order as these dim spectra — and nearly flat in wavelength, with
what spectral shape remains coming from `f_L(ψ, λ)`, the residual `a/b_b`
term, and the hybrid emulator's correction. That correction is evaluated far
outside its training domain here (features `log₁₀ u ≈ 0` and
`b_bw/b_b ≈ 10⁻⁸`); BING calls `robust.rt.forward` with the default
`on_out_of_domain = "warn"` policy, and under `jit` the warning is silent, so
the emulator extrapolates freely. The result is the blue-rising model curve
in every figure above. (`µ_∞` from TT2017 is likewise fitted only over
`b_b/a` = 10⁻⁴–10⁻¹.)

**Two basins, and the chains began in the wrong one.** The χ² profile below
fixes `Bnw` and re-optimises the other five parameters. For all four cases
there is a physical minimum at `b_bp`(600) ≈ 5×10⁻⁴–8×10⁻³ m⁻¹, a wall at
1–10 m⁻¹ (reduced χ² 10²–10⁵, where `u` passes through the emulator's edge),
and a second, shallower basin that descends monotonically to the prior
ceiling at 10⁵ m⁻¹. The stored posteriors (triangles) are in that second
basin, 1.5–23× worse in χ² than the physical one.

![profiles](high_bbp_outliers/refit_profiles.png)

*(a) Reduced-χ² profile versus fixed log₁₀ `Bnw` (`b_bp` at 600 nm) for four
outliers, other parameters re-optimised by LM at each point; triangles mark
the stored posterior-median χ² at the ceiling. (b, c) Observed Rrs with the
stored runaway model and the physical-basin LM solution for 6903874/139 and
4903784/112.*

The chains confirm which basin the sampler was *given*: at step 0 of every
one of the 51 chains the median walker `Bnw` is 4.7–4.99, and no walker in any
chain ever went below 2.9. PAB's `fit_spectrum` seeds the 16 walkers in a 1 %
ball around the LM warm-start (`bing.fitting.inference.init_walkers`,
`frac = 0.01`), and emcee's stretch move cannot carry such a ball across a
χ² wall of 10⁵; so the LM warm-start (`bing.fitting.chisq_fit.fit`, i.e.
`scipy.optimize.curve_fit` with the prior bounds) must have ended at the
ceiling. The `success` flag only records that `curve_fit` returned, which it
did.

**Exploratory re-fits** (LM only, no MCMC; same `Rrs`/`Rrs_unc`, geometry and
Chl seed as the stored fit; forward model `robust_hybrid` with Raman and
Chl fluorescence; run on the workstation CPU in float32 — *not* production
results):

| fit | stored χ² (ceiling) | LM from the production initial guess | LM with physical ceilings (`b_bp`(600) ≤ 0.1, `A_dg`, `A_ph` ≤ 10 m⁻¹) | physical `b_bp`(700) | float / BING 1.0 / GIOP | 12 perturbed starts ending at the ceiling |
|---|---|---|---|---|---|---|
| 6903874/139 (type A) | 11.1 | **1.81**, physical basin | 1.81 | 4.3×10⁻⁴ | 1.0×10⁻³ / 7.0×10⁻⁴ / 1.2×10⁻³ | 0 |
| 4903784/112 (type B) | 10.5 | 10.5, ceiling | **0.45** | 7.6×10⁻³ | 1.8×10⁻² / 8.0×10⁻³ / 6.0×10⁻³ | 2 |
| 7901007/400 (type A) | 7.0 | 7.0, ceiling | **2.35** | 3.6×10⁻³ | 2.9×10⁻³ / 4.6×10⁻³ / 1.4×10⁻³ | 6 |
| 2903902/30 (type A, `A_ph` mirror) | 1.7 | 1.7, ceiling | **0.21** | 6.5×10⁻³ | 6.2×10⁻³ / 7.9×10⁻³ / 5.0×10⁻³ | 3 |

Three findings from this:

1. The physical basin exists and wins on χ² in every case; its `b_bp`(700)
   is within a factor of ~2 of the float and of the 1.0 Gordon fit. The data
   are usable — the optimiser just did not find the right minimum.
2. The LM is start-sensitive on these spectra: from the production initial
   guess it reproduces the ceiling for three of four, and perturbing the
   start by ±0.3 dex sends 0–50 % of runs to the ceiling. (For 6903874/139
   the workstation LM found the physical basin where the pod's did not; the
   JAX forward model ran on a GPU there and on the CPU here, and a
   path-dependent optimiser next to a wall can diverge on such differences.
   The chains leave no doubt about where the production LM ended.)
3. **Removing the negative bands does not fix it.** With the negative bands
   masked and the full prior bounds, 6903874/139 and 7901007/400 still go to
   the ceiling (χ² 10.2 and 2.5); 2903902/30 goes physical (χ² 0.04). The
   negative values mark the bad pixels but are not what the runaway fits —
   the depressed-blue *shape* is, which is why the all-positive Baltic
   spectra fail identically. A physical ceiling on the prior removes the
   spurious basin outright; a screen merely avoids some of the spectra that
   have it.

## 5. Would a pre-fit screen catch them?

Catch rate on the 51, false-positive rate on the 300-fit random sample
(scaled to the 15,920 non-outliers):

| screen | catches (of 51) | flags in the sample | ≈ non-outlier fits flagged |
|---|---|---|---|
| any Rrs < 0 at 400–450 nm | **40** | 2 (0.7 %) | ~100 |
| any Rrs < 0 anywhere in 400–700 nm | 40 | 21 (7.0 %) | ~1,100 |
| any Rrs < −1 σ (stored `Rrs_unc`) | 40 (by construction of the 51) | 6 (2.0 %) | ~300 |
| Rrs(440)/Rrs(555) < 0.6 | 44 | 3 (1.0 %) | ~160 |
| Rrs(440)/Rrs(555) < 1.0 | 46 | 11 (3.7 %) | ~580 |
| negative blue **or** ratio < 0.6 | **50** | 3 (1.0 %) | ~160 |

The two sample fits the negative-blue screen flags are 4903784/178 (Baltic;
19 negative bands; BING 1.2×10⁻³ against a float value of 4.8×10⁻² — a
40-fold underestimate, so a failed fit of a different kind) and 3902472/64
(Agulhas; minimum −1.3×10⁻³; BING 6.5×10⁻⁴ vs float 1.0×10⁻³, χ² 1.0 — a
plausible fit on a doubtful pixel). The negative-blue screen therefore costs
essentially no *good* fits. The ratio screen does: the 11 sample fits with
Rrs(440)/Rrs(555) < 1 are Baltic and subpolar fits with χ² 0.1–1.1 and
sat/float ratios 0.6–1.4 — exactly the productive-water matchups the report
wants to keep. "Any negative anywhere" is useless (the 600–700 nm bands dip
below zero on 7 % of ordinary clear-water spectra).

Note the 11 type-B outliers are indistinguishable *by their spectra* from
good Baltic fits (the sample's 2903902/39, on the same float series, has
ratio 0.73 and a sat/float `b_bp` ratio of 1.3). No Rrs screen separates
them; only the fit set-up can.

Context, not treated here: the low-end pile-up of 2.0 `b_bp` at 2–4×10⁻⁶ m⁻¹
(the prior floor; 9 of the 300 sampled fits, none with a negative blue band,
blue ratio 4.7 — clear water) and the GIOP floor band at 2–4×10⁻⁴ m⁻¹ are
separate problems with ordinary spectra.

## 6. Recommended next steps

1. **Report now.** Keep the 51 out of the `b_bp` statistics behind the
   existing `BBP_IMPLAUSIBLE = 1 m⁻¹` gate and say so in the caption (51
   failed retrievals, 0.32 %), rather than leaving them in the medians; and
   amend the run report's §2.5 — the regime is marginal seas with a depressed
   or negative blue Rrs, not oligotrophic water.
2. **Re-fit the 51** under a new `pab_version` (the design's rule: a new
   record, never an overwrite), with the spurious basin removed: a physical
   ceiling on `Bnw` (10⁻¹ m⁻¹ at 600 nm; the open ocean spans 10⁻⁴–10⁻¹) and
   on `A_dg`/`A_ph` (≈10 m⁻¹), applied as a PAB-side override of
   `expb_pow`'s priors so BING's own defaults are untouched; and/or a
   multi-start LM (best of N perturbed starts, or seeded from the 1.0 Gordon
   solution, which exists for 48 of the 51). Then check that step 0 of every
   chain is in the physical basin. Expected cost: 51 × ~3 min.
3. **Store an Rrs QA flag** per fit — "n bands with Rrs < 0 at 400–450 nm"
   as a `fit_results` quantity or a `matchup_pixels` column — so the report
   can show it and a reader can filter on it. Refusing to fit such pixels is
   not recommended: 2903902/30 fits well once the right basin is found, and
   the Baltic type-B spectra are not screenable anyway.
4. **Ask the emulator to stay in domain.** `robust.rt.forward` has an
   `on_out_of_domain = "ztt"` policy (fall back to the analytic backbone
   outside the training range); BING uses the default `"warn"`, which is
   silent under `jit`. Running with `"ztt"` would at least make the
   out-of-domain Rrs the analytic one. Worth a slice test; it may change
   the wall, not the basin.
5. **Look at the 1.0-vs-2.0 comparison for the Baltic.** 10 of the 51 are
   one float (4903784) and four of them are consecutive cycles on one
   granule; the same float and granule produce good fits in the sample. A
   per-float view of the 2.0/1.0 ratio for the three Baltic floats would show
   how far the ceiling basin reaches below the 1 m⁻¹ gate (nothing between
   0.03 and 10⁴ m⁻¹ suggests it is all-or-nothing, but the `A_dg`-mirror case
   with χ² = 1.7 says the basin is not always detectable).

## Appendix A — the 51 fits

Sorted by `b_bp`(700). `A_dg` and Chl are the 2.0 posterior medians; "n(Rrs<0)"
counts negative observed bands at 400–450 nm; the float value is the mixed-layer
`bbp700`; BING 1.0 is the Gordon fit of the same pixel (blank where none);
GIOP is NASA's `bbp_442` shifted to 700 nm with its per-pixel slope.

| WMO/cycle | date | lat | lon | region | b_bp(700) BING 2.0 [m⁻¹] | 5–95 % | A_dg [m⁻¹] | Chl_BING | β | B_p | χ²_red | n(Rrs<0, 400–450) | Rrs(440)/Rrs(555) | float b_bp(700) | BING 1.0 b_bp(700) | GIOP b_bp(700) | dist [km] | Δt [h] | θ_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6903874/139 | 2024-08-25 | -1.1 | -5.0 | tropical Atlantic / Caribbean | 9.32e+04 | 7.8e+04–9.9e+04 | 633 | 0.00673 | 0.04 | 0.0040 | 11.11 | 12 | 0.40 | 1.01e-03 | 7.04e-04 | 1.19e-03 | 0.4 | 2.1 | 20 |
| 6990528/121 | 2024-09-16 | 42.7 | 8.3 | Mediterranean | 9.29e+04 | 7.4e+04–9.9e+04 | 8.31e+03 | 0.0102 | 0.01 | 0.0040 | 15.34 | 4 | 1.88 | 7.44e-04 | 4.84e-04 | 4.71e-04 | 0.3 | 22.1 | 43 |
| 1902601/95 | 2025-01-29 | 11.9 | -25.8 | tropical Atlantic / Caribbean | 9.29e+04 | 7.4e+04–9.9e+04 | 2.21e+03 | 0.003 | 0.02 | 0.0040 | 12.94 | 3 | 1.44 | 1.07e-03 | 6.07e-04 | 3.77e-04 | 2.8 | 22.6 | 31 |
| 4903904/6 | 2025-08-14 | 17.8 | -67.9 | tropical Atlantic / Caribbean | 9.05e+04 | 6.9e+04–9.9e+04 | 4.46e+03 | 0.0175 | 0.02 | 0.0040 | 11.12 | 1 | 1.53 | 6.07e-04 | 1.20e-04 | 1.31e-04 | 3.4 | 10.4 | 18 |
| 4903489/51 | 2024-07-22 | -2.9 | -16.5 | tropical Atlantic / Caribbean | 9.01e+04 | 6.7e+04–9.9e+04 | 5.92e+03 | 0.00666 | 0.02 | 0.0040 | 11.20 | 0 | 1.44 | 1.13e-03 | 3.45e-04 | 3.38e-04 | 0.6 | 11.7 | 30 |
| 1902498/12 | 2024-06-06 | -5.3 | -3.1 | tropical Atlantic / Caribbean | 9.01e+04 | 6.8e+04–9.9e+04 | 6.31e+03 | 0.00726 | 0.03 | 0.0040 | 11.38 | 6 | 1.12 | 7.58e-04 | 5.93e-04 | 1.01e-03 | 0.8 | 15.8 | 35 |
| 4903462/128 | 2026-05-05 | 10.0 | -53.7 | tropical Atlantic / Caribbean | 8.69e+04 | 6.3e+04–9.7e+04 | 1.92e+03 | 0.00637 | 0.09 | 0.0041 | 9.41 | 10 | 0.50 | 8.98e-04 | 1.24e-03 | 1.30e-03 | 0.7 | 20.6 | 15 |
| 6903877/215 | 2026-07-09 | -0.1 | -23.7 | tropical Atlantic / Caribbean | 8.35e+04 | 5.5e+04–9.7e+04 | 8.05e+03 | 0.0225 | 0.07 | 0.0041 | 12.12 | 2 | 0.56 | 1.21e-03 | — | 7.94e-04 | 0.8 | 4.2 | 24 |
| 4902683/264 | 2026-01-23 | 51.8 | -131.2 | NE Pacific coast | 8.30e+04 | 5.9e+04–9.6e+04 | 184 | 0.0091 | 0.30 | 0.0041 | 1.61 | 18 | -0.29 | 8.79e-04 | 5.81e-04 | 8.70e-04 | 0.3 | 9.0 | 71 |
| 2903886/75 | 2025-01-08 | 32.2 | -122.9 | California Current | 8.23e+04 | 5.4e+04–9.8e+04 | 1.97e+03 | 0.00947 | 0.05 | 0.0040 | 5.94 | 10 | 0.58 | 1.27e-03 | 1.08e-03 | 1.16e-03 | 0.7 | 18.7 | 56 |
| 1902660/51 | 2026-01-01 | 24.6 | 62.6 | Arabian Sea / Gulf of Oman | 8.11e+04 | 5.1e+04–9.7e+04 | 2.01e+03 | 0.00809 | 0.11 | 0.0041 | 5.06 | 9 | 0.48 | 8.39e-04 | 2.02e-03 | 1.48e-03 | 0.1 | 18.3 | 48 |
| 1902683/192 | 2024-07-22 | 55.3 | 19.3 | Baltic Sea | 7.95e+04 | 6.4e+04–9.2e+04 | 3.33e+03 | 0.00411 | 1.07 | 0.0092 | 14.45 | 0 | 0.33 | 6.27e-03 | 6.42e-03 | 5.91e-03 | 1.0 | 22.1 | 36 |
| 2903902/49 | 2024-08-17 | 55.4 | 15.7 | Baltic Sea | 7.41e+04 | 5.7e+04–9.0e+04 | 6.24e+03 | 0.00756 | 1.38 | 0.0077 | 12.56 | 0 | 0.49 | 4.80e-03 | 5.09e-03 | 4.16e-03 | 0.8 | 0.1 | 42 |
| 1902683/158 | 2024-05-21 | 55.3 | 19.3 | Baltic Sea | 7.30e+04 | 6.2e+04–8.1e+04 | 3.15e+03 | 0.00498 | 1.73 | 0.0102 | 15.13 | 0 | 0.38 | 7.75e-03 | 7.50e-03 | 7.83e-03 | 0.6 | 8.4 | 35 |
| 4902679/162 | 2025-04-02 | 50.6 | -132.0 | NE Pacific coast | 7.26e+04 | 5.5e+04–8.5e+04 | 622 | 0.00761 | 1.45 | 0.0041 | 7.99 | 20 | -0.37 | 2.15e-03 | 2.86e-03 | 9.65e-04 | 4.5 | 12.7 | 46 |
| 6903874/140 | 2024-09-04 | -1.1 | -5.2 | tropical Atlantic / Caribbean | 7.23e+04 | 4.3e+04–9.0e+04 | 1.15e+04 | 0.0148 | 0.78 | 0.0043 | 12.92 | 2 | 0.65 | 1.15e-03 | 1.60e-03 | 1.49e-03 | 4.5 | 17.6 | 22 |
| 4903784/112 | 2024-07-08 | 55.4 | 15.3 | Baltic Sea | 7.22e+04 | 6.2e+04–7.8e+04 | 2.05e+03 | 0.00892 | 1.82 | 0.0090 | 10.50 | 0 | 0.24 | 1.83e-02 | 7.97e-03 | 5.97e-03 | 0.9 | 19.7 | 34 |
| 4903784/113 | 2024-07-08 | 55.4 | 15.3 | Baltic Sea | 7.22e+04 | 6.0e+04–7.9e+04 | 2.45e+03 | 0.00483 | 1.83 | 0.0092 | 11.12 | 0 | 0.28 | 1.84e-02 | 8.78e-03 | 7.06e-03 | 0.8 | 21.8 | 34 |
| 4903784/111 | 2024-07-08 | 55.4 | 15.3 | Baltic Sea | 7.21e+04 | 6.0e+04–7.8e+04 | 2.07e+03 | 0.00979 | 1.83 | 0.0089 | 10.50 | 0 | 0.24 | 1.83e-02 | 7.97e-03 | 5.97e-03 | 0.8 | 17.8 | 34 |
| 4903784/114 | 2024-07-08 | 55.4 | 15.3 | Baltic Sea | 7.19e+04 | 5.9e+04–7.9e+04 | 2.35e+03 | 0.00448 | 1.82 | 0.0093 | 11.12 | 0 | 0.28 | 1.84e-02 | 8.80e-03 | 7.06e-03 | 0.5 | 23.8 | 34 |
| 2902272/215 | 2025-03-13 | 18.4 | 59.8 | Arabian Sea / Gulf of Oman | 7.15e+04 | 4.1e+04–9.2e+04 | 480 | 0.00894 | 0.61 | 0.0042 | 4.31 | 20 | -0.76 | — | 4.03e-04 | 8.95e-04 | 1.6 | 3.4 | 27 |
| 2903902/30 | 2024-06-20 | 55.3 | 15.6 | Baltic Sea | 7.11e+04 | 3.1e+04–9.3e+04 | 0.0104 | 5.92e+03 | 0.49 | 0.0056 | 1.71 | 16 | 0.01 | 6.23e-03 | 7.85e-03 | 5.03e-03 | 0.9 | 21.5 | 32 |
| 2903902/50 | 2024-08-20 | 55.3 | 15.6 | Baltic Sea | 6.99e+04 | 5.3e+04–7.6e+04 | 820 | 0.00637 | 1.87 | 0.0100 | 9.64 | 17 | -0.01 | 4.76e-03 | 5.48e-03 | 3.04e-03 | 1.1 | 0.2 | 43 |
| 6990668/89 | 2025-06-16 | 59.4 | -50.7 | Labrador Sea | 6.99e+04 | 4.6e+04–9.1e+04 | 2.16e+04 | 0.00932 | 1.60 | 0.0052 | 17.42 | 3 | 0.66 | 2.69e-03 | 2.20e-03 | 1.01e-03 | 1.0 | 0.2 | 37 |
| 4903850/28 | 2026-04-22 | 42.3 | 152.1 | NW Pacific (Kuroshio-Oyashio) | 6.91e+04 | 5.1e+04–7.6e+04 | 1.51e+03 | 0.00299 | 1.88 | 0.0116 | 9.79 | 0 | 0.26 | 6.03e-03 | 5.41e-03 | 4.03e-03 | 0.3 | 2.5 | 30 |
| 7901065/58 | 2024-11-30 | 42.7 | 34.8 | Black Sea | 6.90e+04 | 4.3e+04–8.7e+04 | 8.59e+03 | 0.0156 | 1.62 | 0.0050 | 15.38 | 13 | 0.09 | 5.73e-03 | 4.13e-03 | 3.51e-03 | 0.5 | 1.6 | 65 |
| 4903784/185 | 2025-06-11 | 55.1 | 14.5 | Baltic Sea | 6.86e+04 | 4.8e+04–8.0e+04 | 2.16e+03 | 0.00724 | 1.74 | 0.0055 | 8.45 | 18 | -0.08 | 4.78e-02 | 4.04e-03 | 2.04e-03 | 0.4 | 0.9 | 33 |
| 4902620/139 | 2026-07-23 | -27.2 | 33.2 | Agulhas / Mozambique Ch. | 6.79e+04 | 3.4e+04–9.4e+04 | 2.66e+03 | 0.0321 | 0.18 | 0.0041 | 4.21 | 11 | 0.50 | 7.74e-04 | — | 8.62e-04 | 1.0 | 5.1 | 49 |
| 4903784/173 | 2025-04-12 | 55.1 | 14.4 | Baltic Sea | 6.71e+04 | 3.8e+04–8.7e+04 | 2.28e+03 | 0.0129 | 1.26 | 0.0045 | 3.48 | 12 | 0.06 | 4.78e-02 | 2.59e-03 | 1.56e-03 | 0.7 | 23.5 | 47 |
| 1902683/208 | 2024-08-20 | 55.2 | 19.2 | Baltic Sea | 6.68e+04 | 4.3e+04–8.0e+04 | 1.14e+04 | 0.0193 | 1.78 | 0.0047 | 9.67 | 0 | 0.55 | 5.58e-03 | 5.93e-03 | 3.80e-03 | 0.7 | 7.4 | 43 |
| 4903784/129 | 2024-09-08 | 55.0 | 14.3 | Baltic Sea | 6.42e+04 | 3.7e+04–7.8e+04 | 1.14e+03 | 0.0104 | 1.75 | 0.0045 | 4.74 | 15 | 0.05 | 4.27e-03 | 4.06e-03 | 2.20e-03 | 0.6 | 23.7 | 49 |
| 2902878/195 | 2025-04-20 | 42.0 | 146.0 | NW Pacific (Kuroshio-Oyashio) | 6.28e+04 | 2.9e+04–8.1e+04 | 1.25e+03 | 0.0164 | 1.64 | 0.0079 | 3.56 | 3 | 0.20 | 3.92e-03 | 4.55e-03 | 2.84e-03 | 0.7 | 20.8 | 34 |
| 7901007/400 | 2025-06-05 | 75.9 | 43.0 | Barents Sea | 6.26e+04 | 3.1e+04–7.8e+04 | 661 | 0.012 | 1.79 | 0.0084 | 7.04 | 20 | -0.34 | 2.92e-03 | 4.63e-03 | 1.39e-03 | 0.2 | 1.3 | 54 |
| 1902683/217 | 2024-09-06 | 55.2 | 19.3 | Baltic Sea | 6.12e+04 | 3.1e+04–7.9e+04 | 2.46e+03 | 0.0182 | 1.73 | 0.0061 | 4.54 | 0 | 0.34 | 4.81e-03 | 5.68e-03 | 3.17e-03 | 0.7 | 4.0 | 49 |
| 1902751/19 | 2025-05-17 | 20.3 | 59.6 | Arabian Sea / Gulf of Oman | 5.99e+04 | 2.5e+04–8.4e+04 | 3.47e+03 | 0.0145 | 1.31 | 0.0044 | 5.76 | 13 | 0.21 | 8.30e-04 | 9.76e-04 | 1.35e-03 | 0.5 | 16.2 | 19 |
| 1902683/223 | 2024-09-17 | 55.2 | 19.3 | Baltic Sea | 5.99e+04 | 2.0e+04–8.6e+04 | 0.00203 | 903 | 1.11 | 0.0047 | 1.50 | 20 | -0.33 | 4.33e-03 | 3.81e-03 | 1.20e-03 | 0.5 | 3.9 | 53 |
| 1902660/21 | 2025-05-12 | 21.6 | 59.8 | Arabian Sea / Gulf of Oman | 5.94e+04 | 3.0e+04–7.7e+04 | 3.24e+03 | 0.00979 | 1.79 | 0.0053 | 7.83 | 16 | 0.07 | 1.42e-03 | 1.87e-03 | 1.67e-03 | 0.6 | 10.8 | 17 |
| 1902683/216 | 2024-09-04 | 55.2 | 19.3 | Baltic Sea | 5.90e+04 | 2.8e+04–7.7e+04 | 1.55e+03 | 0.0202 | 1.77 | 0.0051 | 4.71 | 8 | 0.19 | 5.42e-03 | 6.08e-03 | 2.63e-03 | 2.1 | 0.5 | 49 |
| 1902660/56 | 2026-02-18 | 24.9 | 63.4 | Arabian Sea / Gulf of Oman | 5.89e+04 | 2.3e+04–7.7e+04 | 119 | 0.0348 | 1.78 | 0.0115 | 4.02 | 17 | -0.05 | 3.61e-03 | 4.75e-03 | 1.82e-03 | 2.5 | 0.8 | 36 |
| 1902683/218 | 2024-09-08 | 55.2 | 19.3 | Baltic Sea | 5.84e+04 | 1.8e+04–8.1e+04 | 584 | 0.0166 | 1.65 | 0.0086 | 2.54 | 11 | 0.15 | 4.51e-03 | 4.62e-03 | 2.54e-03 | 0.7 | 7.5 | 50 |
| 2903902/58 | 2024-09-15 | 55.3 | 15.1 | Baltic Sea | 5.77e+04 | 2.3e+04–7.6e+04 | 443 | 0.015 | 1.73 | 0.0060 | 4.51 | 18 | -0.03 | 5.35e-03 | 3.84e-03 | 2.24e-03 | 0.6 | 1.9 | 53 |
| 1902683/330 | 2025-04-01 | 55.3 | 19.6 | Baltic Sea | 5.65e+04 | 2.3e+04–8.1e+04 | 595 | 0.0197 | 1.54 | 0.0054 | 2.43 | 18 | -0.13 | 2.46e-03 | 3.95e-03 | 1.73e-03 | 4.8 | 16.4 | 51 |
| 6990700/56 | 2026-04-19 | 24.8 | 59.4 | Arabian Sea / Gulf of Oman | 5.27e+04 | 1.9e+04–7.6e+04 | 1.36e+03 | 0.0121 | 1.71 | 0.0063 | 4.63 | 13 | 0.10 | 1.66e-03 | 1.77e-03 | 1.44e-03 | 3.8 | 3.4 | 14 |
| 4903784/170 | 2025-03-28 | 55.1 | 14.4 | Baltic Sea | 5.23e+04 | 1.6e+04–8.0e+04 | 296 | 0.0129 | 1.50 | 0.0053 | 2.31 | 20 | -0.23 | 4.78e-02 | 2.31e-03 | 8.55e-04 | 0.7 | 22.9 | 52 |
| 6990700/59 | 2026-05-18 | 23.7 | 59.7 | Arabian Sea / Gulf of Oman | 5.06e+04 | 1.8e+04–8.0e+04 | 2.38e+03 | 0.0133 | 1.61 | 0.0054 | 4.51 | 16 | 0.10 | 1.23e-03 | 1.52e-03 | 1.54e-03 | 0.9 | 16.5 | 19 |
| 2903902/19 | 2024-05-18 | 55.3 | 15.7 | Baltic Sea | 5.01e+04 | 1.4e+04–7.8e+04 | 120 | 0.0196 | 1.62 | 0.0066 | 1.50 | 13 | 0.04 | 3.54e-03 | 2.46e-03 | 1.45e-03 | 0.6 | 1.1 | 36 |
| 1902683/318 | 2025-03-10 | 55.3 | 19.7 | Baltic Sea | 5.01e+04 | 1.9e+04–7.6e+04 | 251 | 0.0235 | 1.67 | 0.0050 | 2.58 | 20 | -0.33 | 1.46e-03 | 6.46e-03 | 1.44e-03 | 3.1 | 8.9 | 59 |
| 1902499/86 | 2026-06-19 | -4.3 | 2.2 | tropical Atlantic / Caribbean | 5.01e+04 | 1.8e+04–7.8e+04 | 763 | 0.0186 | 1.59 | 0.0054 | 5.04 | 20 | -0.32 | 1.60e-03 | — | 1.25e-03 | 0.8 | 11.0 | 29 |
| 1902683/310 | 2025-02-24 | 55.3 | 19.7 | Baltic Sea | 4.59e+04 | 9.4e+03–7.8e+04 | 242 | 0.0178 | 1.57 | 0.0073 | 1.44 | 15 | 0.01 | 2.61e-03 | 4.69e-03 | 1.52e-03 | 4.1 | 15.2 | 65 |
| 4903784/179 | 2025-05-12 | 55.1 | 14.4 | Baltic Sea | 4.26e+04 | 8.8e+03–8.4e+04 | 11.8 | 0.357 | 0.99 | 0.0054 | 0.60 | 17 | -0.03 | 4.78e-02 | 1.58e-03 | 7.80e-04 | 0.1 | 0.0 | 38 |
| 4903784/86 | 2024-03-17 | 55.2 | 14.5 | Baltic Sea | 4.11e+04 | 9.3e+03–7.7e+04 | 66.7 | 0.0192 | 1.47 | 0.0061 | 0.71 | 19 | -0.16 | 1.77e-02 | 3.16e-03 | 1.34e-03 | 1.6 | 0.5 | 58 |

## Appendix B — how this was done

- Outlier table and population statistics: SQL on `fits`/`fit_results`/
  `matchups`/`profiles`/`mld_summary`/`matchup_pixels`/`granules` (read-only).
- Spectra: `wave`, `Rrs`, `varRrs` from the chain NPZs (`fits.chains_path`
  basenames fetched with `rclone copy AIOcean:PAB/v2/fit_chains/ …
  --files-from … --no-traverse`), 51 outliers + 300 random non-outliers
  (seed 42); fit figures from `AIOcean:PAB/v2/figures/`, scene quick-looks
  from `AIOcean:PAB/site/_static/scenes/`.
- Re-fits: `pab.fit.models.build_models` + `pab.fit.run` helpers
  (`_initial_guess`, `_prior_bounds`, `set_inelastic_Ed`, `reconstruct_rrs`)
  with `bing.fitting.chisq_fit.fit`; masked bands were given a variance of
  10⁶ sr⁻²; the profile re-optimises from three starts per point. Scratch
  scripts: `/tmp/claude-1000/pab-outliers/{outliers_query,spectra_out,
  spectra_sample,chain_start,refit2,tables,figs}.py`.
- Nothing was written to any database, nothing under `$PAB_DATA_DIR/v1/`, no
  code under `pab/` changed.
