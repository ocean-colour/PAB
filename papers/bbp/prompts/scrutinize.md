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


## Q&A

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
