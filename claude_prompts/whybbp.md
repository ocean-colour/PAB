# Investigating the PACE–Argo bbp700 bias

## Goal

The full PAB run shows PACE OCI bbp700 systematically exceeds co-located BGC-Argo float bbp700 in ~83% of matchups (median δ = +0.37, median ratio 1.59×). The bias is concentrated in oligotrophic waters and nearly disappears in productive waters. The pipeline has already run — this prompt doc is about **understanding why**.

Use the thesis, the database, and the literature to work through the competing hypotheses, run targeted diagnostic analyses, and write a discussion-ready synthesis of the most likely causes.

## Claude

### Working agreements

- **Git is handled by the user.** No state-changing git commands.
- **Python only.** No MATLAB.
- **Read-only.** Do not modify the database. Write outputs to `$PAB_DATA_DIR/bias_analysis/`.
- **Cite the literature.** When you invoke a paper, fetch it and read it — do not cite from memory. Use the thesis (`papers/thesis.pdf`) as the starting point; branch out from its bibliography.
- **Be honest about what the data can and cannot show.** If a test is inconclusive, say so clearly.

## Context

### What we know from the full run

- **n = 13,563 matchups** (δ ≥ −1.5 filter), March 2024 – June 2026.
- **83.5% positive** (PACE > Argo); median δ = +0.371; median ratio = 1.59×.
- Spearman ρ = 0.54 (bbp_PACE vs bbp_Argo); log₁₀ bias = +0.21; RMS = 0.30.
- **By regime:** Low Argo bbp (<0.001 m⁻¹): δ = +0.45, 90% positive. Mid: +0.16, 67%. High (>0.005): −0.03, 46%.
- **Flat (no signal):** δ vs MLD, δ vs Δt, δ vs distance.
- **FLH ρ = −0.25 with δ** — high fluorescence → lower bias (rules out inelastic scattering).
- **Poor fits (χ²ᵣ ≥ 1):** median δ = +0.57 vs +0.35 for good fits.
- BING vs GIOP comparison: **not yet done** — highest-priority diagnostic.

### Thesis

The thesis (`papers/thesis.pdf`) contains:
- Results section with all figures from the run1k dataset (278 matchups).
- Discussion arguing residual aerosol contamination as the primary driver, with inelastic scattering ruled out via FLH.
- Bibliography with the key ocean optics and BGC-Argo validation papers.

Read the thesis discussion before running analyses — it sets up the hypotheses and what was already tested on the smaller dataset.

### Key literature to engage with

- **Bisson et al. (2021)** — global bbp comparison (lidar + ocean color + floats); DOI 10.1029/2020GL090909.
- **Bailey & Werdell (2006)** — matchup protocol; defines the gold-sample co-location criteria.
- **Schmechtig et al. (2015)** — BGC-Argo bbp processing guidelines; dark count corrections.
- **Gordon et al. (1988)** — radiative transfer basis for Rrs → IOP inversion.
- Fetch additional papers from the thesis bibliography as needed.

## Prompts

0. Execute the 0th task in Tasks below. First check to see whether I have answered any new Q&A questions.
1. Execute the 1st task in Tasks below. First check to see whether I have answered any new Q&A questions.
2. Execute the 2nd task in Tasks below. First check to see whether I have answered any new Q&A questions.
3. Execute the 3rd task in Tasks below. First check to see whether I have answered any new Q&A questions.
4. Execute the 4th task in Tasks below. First check to see whether I have answered any new Q&A questions.
5. Execute the 5th task in Tasks below. First check to see whether I have answered any new Q&A questions.
6. Execute the 6th task in Tasks below. First check to see whether I have answered any new Q&A questions.

## Tasks

0. **Read the thesis and confirm the key numbers.** Read the thesis discussion section. Summarize the hypotheses it raises and the evidence it cites for each. Then pull the full-run bias statistics from the database and confirm they are consistent with (or updated from) the thesis numbers. Note any changes between run1k (278 matchups) and the full run (13,563). Log.  Use Fable if you can.

1. **Literature review on the bias.** Fetch and read the papers listed in Context — at minimum Bisson et al. (2021) and Schmechtig et al. (2015). Summarize what each says about (a) satellite vs. float bbp discrepancies and their likely causes, and (b) Argo sensor calibration issues in clear water. Add any additional papers from the thesis bibliography that are directly relevant. Log a concise summary of what the literature says about each hypothesis.  Use Fable if you can.

2. **BING vs GIOP comparison (highest-priority diagnostic).** Check whether GIOP results already exist in the database. If not, run GIOP on the stored Rrs(λ) spectra (answer Q1 first). Compute δ_GIOP and compare to δ_BING: sign, magnitude, Spearman correlation. If both overestimate by similar amounts, the issue is in Rrs(λ) upstream of inversion — the strongest single piece of evidence for aerosol contamination. Save a scatter plot and summary table. Log.  Use Fable if you can.

3. **Float age vs. bias.** Retrieve deployment dates for each WMO float (from the Argo GDAC or local metadata). Compute float age in days at each matchup. Plot δ vs. float age and compute Spearman ρ. A strong positive correlation (older float → larger bias) would support Argo dark-count drift as a contributor; a flat result weakens it. Save figure. Log.  Use Fable if you can.

4. **AOD and atmospheric correction quality analysis.** Check whether the PACE L2 granules include aerosol optical depth (AOD) or AC quality flags. If so, split matchups into clean-sky and hazy subsets and compare median δ. Smaller bias under low-AOD conditions directly supports the aerosol contamination hypothesis. If the flag is not available, note it and discuss what additional data would be needed. Log.  Use Fable if you can.

5. **RT.** It is possible that the bias is due to the Rrs(λ) retrieval algorithm.  JXP has recently updated the inelastic scattering correction in the Rrs(λ) retrieval algorithm.  Please check whether this has any effect on the bias.  You may wish to examine the work in `retrieve-or-bust` and `IOPtics` repositories. Log your work. Use Fable if you can.

6. **Synthesis and discussion draft.** Drawing on Tasks 0–4, the thesis, and the literature, write a 3–4 paragraph discussion of the bias suitable for the paper. Address: (a) what the data establish, (b) what they cannot resolve, (c) the most likely explanation and why, (d) what future work would confirm it. Save as `bias_analysis/bias_discussion_draft.md`. Log.  Use Fable if you can.

## Q&A

**Q1 — Does the database already contain GIOP fit results, or does GIOP need to be run fresh on the stored Rrs spectra?**

>A.  The database now contains GIOP fit results performed by the PACE team

**Q2 — Are the Argo float NetCDF metadata files (containing deployment date) available locally, or does this need a live GDAC fetch?**

>A. I am not sure.  Please check.

**Q3 — Do the PACE L2 granules include an AOD or AC quality variable, and are the granules accessible locally?**

>A. I am not sure.  Please check as best you can.

## Reports

## Logging

Append entries below as:

```
### <Date> (Short summary)

<Detailed description of work and findings>
```

## Logs

### 2026-09-11 (Task 0 — thesis read, full-run bias statistics confirmed)

Read the thesis discussion and confirmed the full-run statistics against the
database. Full summary saved to `$PAB_DATA_DIR/bias_analysis/task0_thesis_and_stats.md`.

- **Thesis location:** `papers/thesis.pdf` does not exist locally. The thesis
  was read from Google Drive — the "thesis draft" Doc (allejame@ucsc.edu,
  modified 2026-06-29; `james_thesis.pdf` also in the Drive Thesis folder).
- **Thesis hypotheses:** (1) residual aerosol contamination — favored, on the
  BING/GIOP agreement, δ scaling with the PACE value but not the Argo value,
  and basin/season uniformity; (2) inelastic scattering — ruled out via
  Hydrolight (Raman ~10%, spectrally flat; fluorescence peak at 685 nm) and
  the FLH–δ anticorrelation (ρ = −0.25); (3) float calibration — secondary at
  most (~20% ECO uncertainty vs. 57% thesis median bias); (4) matchup
  representativeness — acknowledged, but the bias is insensitive to stricter
  Bailey & Werdell (2006) criteria (n = 144, median δ = 0.546).
- **Dataset lineage:** the current thesis draft reports its own N = 1,163
  dataset (median δ = +0.57, 90.3% positive, Apr 2024–May 2025) — not the
  run1k set described in this doc. run1k recomputed: n = 262 valid, median
  δ = +0.352, 84.7% positive.
- **Full-run numbers confirmed** from `full/pab.db` (BING bbp700 vs. Argo
  mixed-layer bbp700, δ ≥ −1.5): n = 13,562, 83.5% positive, median
  δ = +0.371, ratio 1.59×, Spearman ρ = 0.54, log₁₀ bias +0.20, RMS 0.30.
  Regime and χ²ᵣ breakdowns match the tables below to within one matchup.
- **Changes from thesis to full run:** median δ drops from +0.57 to +0.371;
  ρ(δ, bbp_PACE) weakens from +0.75 to +0.35; ρ(δ, bbp_Argo) = −0.53. The
  thesis headline numbers need updating for the paper.
- **Caveat:** δ vs. distance is not perfectly flat in the full run
  (ρ = +0.15, p ≈ 4e-67) — weak, and far too small to explain the bias, but
  "flat" oversells it. δ vs. MLD (ρ = +0.07) and δ vs. Δt (ρ = +0.03) are
  genuinely negligible.
- **For Task 2:** GIOP is already in the DB (14,609 `NASA_GIOP` fits,
  confirming Q1), but stores `bbp_442` + slope `bbp_s` — bbp700 must be
  extrapolated as bbp_442 × (442/700)^bbp_s.

### 2026-09-11 (Task 1 — literature review on the bias)

Fetched and read the key papers; full review with per-paper quotes saved to
`$PAB_DATA_DIR/bias_analysis/task1_literature_review.md`.

- **Read directly:** Bisson et al. (2021, GRL; full text via PMC), Bisson et
  al. (2019, Opt. Express; PMC), Schmechtig et al. (2015/v1.4 2018 DAC
  processing doc; PDF), Dall'Olmo et al. (2023 bbp RTQC manual; PDF),
  Serra-Pompei et al. (2023; bioRxiv preprint PDF), Gordon et al. (1988)
  formulation via the open IOCCG Report 5, Barnard (2021) SEANOE
  scale-factor-correction record. **Not readable:** Bailey & Werdell (2006)
  primary PDF (paywalled — criteria verified verbatim from Bisson et al. 2019)
  and Poteau et al. (2017) (bot-blocked at Wiley and HAL).
- **Satellite-vs-float discrepancies:** heritage sensors at 443–532 nm are
  biased *low* vs floats in the median (MODIS GIOP −21%, CALIOP −11%,
  Bisson 2021; ratios 0.77–0.88 for MODIS/VIIRS GIOP/QAA, Bisson 2019) — so
  the PACE +59% at 700 nm is not a generic "satellites run high" result. But
  Serra-Pompei et al. (2023) show MODIS-GIOP *overestimates floats
  specifically in the low-bbp oligotrophic tail* — a direct precedent for the
  PAB regime structure.
- **Aerosol hypothesis (H1):** mechanism explicitly documented — "small
  uncertainties in the aerosol correction lead to large uncertainties in Rrs
  at green and red bands" (Bisson 2021). New leverage argument from Gordon
  (1988): at 700 nm, δbbp ≈ (aw/g1)·δrrs, so the entire oligotrophic-regime
  bias (+0.4×10⁻³ m⁻¹) needs only ~3–4×10⁻⁵ sr⁻¹ of residual Rrs(700); an
  additive Rrs error also naturally reproduces the regime dependence.
- **Argo calibration (H3):** quantified at 10–15% (Bisson 2019) to ≤20%
  (Serra-Pompei 2023 citing Bittig 2019 — the open Bittig text contains no
  explicit % — so 10–15% is the better-anchored bound). Documented systematic
  issues: factory-only darks, drift/biofouling, parking-hook contamination
  (QC manual), and a real fleet-wide scale-factor correction after ADMT18
  (wrong weighted-phase-function constants; Barnard 2021, origin Poteau et
  al. 2017). Big enough to contribute in the low regime, far too small for a
  1.59× ratio.
- **Inelastic (H4):** uncorrected Raman shifts retrieved bbp by up to ~20%
  (Bisson 2019) — but BING models inelastics, and FLH–δ anticorrelation
  stands; literature consistent with ruling out as primary.
- **Phase function (H5):** float χ spans 1.076–1.142 across sensor models;
  phase-function effects on Rrs can reach 65% (Xiong et al. 2017 via Bisson
  2021); multiplicative, so cannot explain a bias that vanishes at high bbp.

## Summary of the bias

From the full PAB dataset (n = 13,563 matchups after outlier removal, δ ≥ −1.5, March 2024 – June 2026):

| Metric | Value |
|---|---|
| PACE > Argo | 83.5% of matchups |
| Median δ = (PACE − Argo) / PACE | +0.371 |
| Median ratio PACE/Argo | 1.59× |
| Spearman ρ | 0.54 |
| Log₁₀ bias | +0.21 |
| Log₁₀ RMS | 0.30 |

**The bias is strongly concentrated in low-backscattering (oligotrophic) waters:**

| Argo bbp regime | n | Median δ | PACE > Argo |
|---|---|---|---|
| Low (<0.001 m⁻¹) | 9,887 | +0.45 | 90% |
| Mid (0.001–0.005 m⁻¹) | 3,498 | +0.16 | 67% |
| High (>0.005 m⁻¹) | 178 | −0.03 | 46% |

**Fit quality tracks the bias:**

| BING χ²ᵣ | n | Median δ | PACE > Argo |
|---|---|---|---|
| Good fit (<1.0) | 12,108 | +0.35 | 83% |
| Poor fit (≥1.0) | 1,455 | +0.57 | 90% |

---

## Hypotheses, ranked by evidence

### 1. Residual aerosol contamination in atmospheric correction (primary driver)

PACE Rrs(λ) is derived by subtracting the atmospheric signal from the top-of-atmosphere radiance. Residual aerosol contamination — imperfect removal of aerosol scattering — adds a spectrally broad positive offset to Rrs(λ) across all bands. Because BING inverts the full Rrs spectrum, any additive offset inflates all retrieved IOPs, including bbp700.

**Supporting evidence:**
- The bias persists across **both BING and GIOP** retrievals applied to the same Rrs(λ). Since the two algorithms use completely different inversion approaches but agree on the sign and magnitude of the overestimate, the problem is upstream — in the Rrs(λ) input, not in the inversion model.
- δ shows a moderate positive correlation with **PACE bbp700** (Spearman ρ = 0.34 in the full dataset; ρ = 0.75 in the earlier run1k subset), meaning higher PACE retrievals tend to accompany larger relative overestimates. This is consistent with an inflated Rrs input.
- The bias is **geographically widespread and basin-independent** — Atlantic, Pacific, Indian, and Southern Ocean all show similar positive offsets. A globally uniform Rrs bias from aerosol residuals is consistent with this; a globally uniform Argo calibration failure is much harder to argue.
- **Poor BING spectral fits (χ²ᵣ ≥ 1) show higher δ** (median +0.567 vs. +0.351 for good fits). Poor fits indicate Rrs spectra inconsistent with the forward model — consistent with aerosol-contaminated inputs.

### 2. Near-surface vertical stratification

PACE measures Rrs from approximately the first optical depth of the ocean (~5–20 m in clear water). Argo averages bbp700 over the entire mixed layer (median MLD = 40 m, range 10–557 m). In stratified oligotrophic gyres, particles may be elevated in a thin near-surface layer, which the MLD average dilutes.

**Weakened by:** The δ vs. MLD analysis showed no relationship with mixed-layer depth — if this were the primary driver, deeper MLDs should produce larger bias.

### 3. Argo sensor calibration (minor contributor)

BGC-Argo ECO sensors have factory calibration uncertainties of ~20–30%, dark-count drift over float lifetime, and β_sw subtraction errors that are largest in very clear water.

**Argued against as the primary driver:**
- The known ECO calibration uncertainty (~20%) is smaller than the median δ = +0.37, so calibration alone cannot explain the full offset.
- The bias is **consistent across independent floats from multiple manufacturers and programs worldwide**.
- δ shows a moderate negative correlation with Argo bbp (ρ = −0.52) — consistent with a calibration offset having its largest relative effect in low-bbp oligotrophic water, so this correlation does not rule out the calibration hypothesis. The key argument against calibration as the *primary* driver is quantitative: the magnitude of the bias (~37%) exceeds what ECO sensor uncertainty alone (~20%) can explain.

### 4. Inelastic scattering — tested and ruled out

**Ruled out:**
- Raman scattering is spectrally broad and approximately uniform — not concentrated at 700 nm.
- BING's forward model already accounts for fluorescence.
- FLH (fluorescence line height) showed Spearman ρ = −0.25 with δ — **high fluorescence correlates with lower bias**, the opposite of what fluorescence contamination would predict.

### 5. Phase function / spectral model assumptions (minor, hard to test)

χ factor varies with particle type; small oligotrophic particles may differ from the assumed value. Difficult to separate from aerosol effects without particle size data.

---

## What the data rules out

- **Temporal mismatch:** No trend in δ vs. Δt.
- **Spatial mismatch:** No increase in δ with distance.
- **Simple PACE calibration offset:** Bias disappears in productive waters — inconsistent with a constant offset.
- **Inelastic scattering:** FLH–δ anticorrelation rules it out.

---

## Most likely explanation

**Residual aerosol contamination in PACE atmospheric correction** is the primary driver. The clearest evidence: the bias persists across two independent retrieval algorithms (BING and GIOP) applied to the same Rrs(λ), which localizes the problem to the Rrs input. Argo calibration error is real but quantitatively insufficient (~20% uncertainty vs. ~37% median bias). Inelastic scattering is tested and ruled out by the FLH–δ anticorrelation.

**Testable next steps (see Tasks above):**
- BING vs. GIOP comparison (Task 2) — the single most diagnostic test.
- Float age vs. bias (Task 3) — tests the Argo calibration drift hypothesis.
- Actual PACE Rrs(700) vs. δ (Task 4) — tests spectral specificity of the bias.
- AOD filter test (Task 5) — direct test of the aerosol hypothesis.



## Summary of the bias

From the full PAB dataset (n = 13,563 matchups after outlier removal, March 2024 – June 2026):

| Metric | Value |
|---|---|
| PACE > Argo | 83.5% of matchups |
| Median δ = (PACE − Argo) / PACE | +0.371 |
| Median ratio PACE/Argo | 1.59× |
| Spearman ρ | 0.54 |
| Log₁₀ bias | +0.21 |
| Log₁₀ RMS | 0.30 |

**The bias is not uniform — it is strongly concentrated in low-backscattering (oligotrophic) waters:**

| Argo bbp regime | n | Median δ | PACE > Argo |
|---|---|---|---|
| Low (<0.001 m⁻¹) | 9,887 | +0.45 | 90% |
| Mid (0.001–0.005 m⁻¹) | 3,498 | +0.16 | 67% |
| High (>0.005 m⁻¹) | 178 | −0.03 | 46% |

In productive, high-backscattering waters the two sensors essentially agree. The discrepancy is an oligotrophic-ocean phenomenon.

**Fit quality also tracks the bias:**

| BING χ²ᵣ | n | Median δ | PACE > Argo |
|---|---|---|---|
| Good fit (<1.0) | 12,108 | +0.35 | 83% |
| Poor fit (≥1.0) | 1,455 | +0.57 | 90% |

Poor spectral fits produce even larger positive offsets, suggesting model mismatch contributes.

---

## Hypotheses, ranked by evidence

### 1. Residual aerosol contamination in atmospheric correction (primary driver)

PACE Rrs(λ) is derived by subtracting the atmospheric signal from the top-of-atmosphere radiance. Residual aerosol contamination — imperfect removal of aerosol scattering — adds a spectrally broad positive offset to Rrs(λ) across all bands. Because BING inverts the full Rrs spectrum, any additive offset inflates all retrieved IOPs, including bbp700.

**Supporting evidence:**
- The bias persists across **both BING and GIOP** retrievals applied to the same Rrs(λ). Since the two algorithms use completely different inversion approaches but agree on the sign and magnitude of the overestimate, the problem is upstream — in the Rrs(λ) input, not in the inversion model.
- δ shows a moderate positive correlation with **PACE bbp700** (Spearman ρ = 0.34 in the full dataset; ρ = 0.75 in the earlier run1k subset), meaning higher PACE retrievals tend to accompany larger relative overestimates. This is consistent with an inflated Rrs input.
- The bias is **geographically widespread and basin-independent** — Atlantic, Pacific, Indian, and Southern Ocean all show similar positive offsets. A globally uniform Rrs bias from aerosol residuals is consistent with this; a globally uniform Argo calibration failure is much harder to argue.
- **Poor BING spectral fits (χ²ᵣ ≥ 1) show higher δ** (median +0.567 vs. +0.351 for good fits). Poor fits indicate Rrs spectra inconsistent with the forward model — consistent with aerosol-contaminated inputs.

### 2. Near-surface vertical stratification

PACE measures Rrs from approximately the first optical depth of the ocean (~5–20 m in clear water). Argo averages bbp700 over the entire mixed layer (median MLD = 40 m, range 10–557 m). In stratified oligotrophic gyres, particles may be elevated in a thin near-surface layer, which the MLD average dilutes.

**Weakened by:** The δ vs. MLD analysis showed no relationship with mixed-layer depth — if this were the primary driver, deeper MLDs should produce larger bias. The flat result suggests depth mismatch is at most a secondary contributor.

### 3. Argo sensor calibration (minor contributor)

BGC-Argo ECO sensors have factory calibration uncertainties of ~20–30%, dark-count drift over float lifetime, and β_sw subtraction errors that are largest in very clear water. These could contribute a systematic low bias in oligotrophic conditions.

**Argued against as the primary driver:**
- The known ECO calibration uncertainty (~20%) is smaller than the median δ = +0.37 observed here, so calibration alone cannot explain the full offset.
- The bias is **consistent across independent floats from multiple manufacturers and programs worldwide** — a globally coordinated Argo underestimation is implausible.
- δ shows a moderate negative correlation with Argo bbp (ρ = −0.52) — consistent with a calibration offset having its largest relative effect in low-bbp oligotrophic water, so this correlation does not rule out the calibration hypothesis. The key argument against calibration as the *primary* driver is quantitative: the magnitude of the bias (~37%) exceeds what ECO sensor uncertainty alone (~20%) can explain.

### 4. Inelastic scattering — tested and ruled out

At 700 nm, Raman scattering and chlorophyll fluorescence contribute to Rrs. If BING attributed these to elastic bbp, bbp700 would be inflated — especially in low-Chl waters.

**Ruled out:**
- Raman scattering is spectrally broad and approximately uniform across the visible — it is not concentrated at 700 nm and is not consistent with a purely red-band inflation of bbp.
- BING's forward model already accounts for fluorescence contributions to Rrs.
- FLH (fluorescence line height, a direct measure of fluorescence signal) showed Spearman ρ = −0.25 with δ — **high fluorescence correlates with lower bias**, the opposite of what fluorescence contamination would predict. High-Chl, high-fluorescence waters show smaller δ (median +0.31 vs. +0.47 at low Chl).

### 5. Phase function / spectral model assumptions (minor, hard to test)

bbp is defined relative to the scattering phase function χ factor (~1.08 in most algorithms), which varies with particle type. Small particles dominant in oligotrophic gyres may have different χ than assumed. This could contribute to the regime-dependent pattern but is difficult to separate from aerosol effects without particle size data.

---

## What the data rules out

- **Temporal mismatch:** No trend in δ vs. Δt. The bias is not from floats and satellites sampling different water masses hours apart.
- **Spatial mismatch:** No systematic increase in δ with distance. Co-location quality is not the explanation.
- **Simple PACE calibration offset:** If PACE had a fixed calibration error, the bias would be uniform across all bbp regimes. Instead it disappears in productive waters and reverses at very high bbp — inconsistent with a constant offset.
- **Inelastic scattering:** See above — FLH correlation is opposite to what this hypothesis predicts.

---

## Most likely explanation

**Residual aerosol contamination in PACE atmospheric correction** is the primary driver. The clearest evidence: the bias persists across two independent retrieval algorithms (BING and GIOP) applied to the same Rrs(λ), which localizes the problem to the Rrs input. Argo calibration error is a real but quantitatively insufficient explanation (~20% uncertainty vs. ~37% median bias). Inelastic scattering is tested and ruled out by the FLH–δ anticorrelation.

**Testable next steps:**
- Compare against PACE Rrs(λ) reprocessed with an updated aerosol correction (when available from NASA) — if the bias decreases, that confirms the aerosol hypothesis.
- Repeat the analysis restricting to low-aerosol-optical-depth scenes (using PACE-retrieved AOD) — if the bias is smaller under clear-sky conditions, that further supports residual aerosol contamination.
- Compare BING retrievals against concurrent AERONET-OC shipboard Rrs measurements to quantify the Rrs-level offset directly.
