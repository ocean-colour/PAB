# BING vs. GIOP: Comparison of bbp700 Bias Against BGC-Argo

## Overview

Following the full PAB pipeline run (n = 14,610 matchups, March 2024 – June 2026), PACE OCI bbp700 retrievals from both the BING and GIOP algorithms were compared against co-located BGC-Argo float mixed-layer-mean bbp700. The goal was to determine whether the systematic positive bias previously identified in BING is shared by GIOP — which would implicate the Rrs(λ) input (e.g., residual aerosol contamination in atmospheric correction) rather than BING-specific inversion assumptions.

---

## Dataset

- **n = 13,965** matchups with valid BING, GIOP, and Argo bbp700 values.
- GIOP bbp700 extrapolated from the retrieved bbp(442 nm) and spectral slope η using bbp(700) = bbp(442) × (442/700)^η.
- Relative difference defined as δ = (satellite − Argo) / satellite for each algorithm.
- Extreme outliers with δ < −1.5 excluded.

---

## Key Statistics

| Metric | BING | GIOP |
|---|---|---|
| % matchups with satellite > Argo | 81.1% | 59.0% |
| Median δ | +0.360 | +0.097 |
| Median ratio (satellite / Argo) | 1.56× | 1.11× |
| Log₁₀ bias | +0.17 | +0.01 |
| Log₁₀ RMS | 0.37 | 0.31 |
| RMS (%) | 253% | 133% |
| Median absolute % error | — | 30.5% |
| Spearman ρ(δ_BING, δ_GIOP) | 0.88 | — |

---

## Figures

### Figure 1 — 1:1 Scatter: Argo vs. BING (left) and Argo vs. GIOP (right)

![1:1 scatter]({{artifact:b1e6f873-d0fc-4627-a5c8-d7772e79b4c8}})

BING (blue) sits well above the 1:1 line with a median ratio of 1.56×. GIOP (orange) is much closer to the 1:1 line with a median ratio of 1.11×, indicating substantially better agreement with Argo.

### Figure 2 — δ_BING vs. δ_GIOP

![delta scatter]({{artifact:4042938b-2253-48c2-9770-e49f73064dec}})

Each point is one matchup. The two algorithms are highly correlated (Spearman ρ = 0.88), meaning the same matchups are biased in both — consistent with a shared upstream cause in Rrs(λ). However, the cloud sits below the 1:1 diagonal: for any given BING bias, GIOP's bias is smaller, confirming that BING-specific inversion assumptions amplify the bias beyond what Rrs alone explains.

### Figure 3 — Distribution of δ: BING vs. GIOP

![histogram]({{artifact:4305fd68-f32d-49d2-98d5-b937328c3292}})

BING (blue) is strongly right-skewed with a median δ = +0.360. GIOP (orange) is nearly centered around zero with a median δ = +0.097. Both distributions have a spike at −1.5 from clipping of extreme outliers.

---

## Interpretation

**Both algorithms show a positive bias relative to Argo**, but BING overestimates by 3–4× more than GIOP. The high correlation between δ_BING and δ_GIOP (ρ = 0.88) indicates a shared signal in the Rrs(λ) input — the same matchups that are biased in one algorithm are biased in the other. This is consistent with residual aerosol contamination in PACE atmospheric correction inflating Rrs(λ) across all wavelengths, which both algorithms then interpret as elevated backscattering.

At the same time, GIOP's substantially smaller bias (median δ = +0.097 vs. BING's +0.360, log₁₀ bias essentially zero) shows that the inversion algorithm matters. BING's Bayesian priors, spectral shape constraints, or model parameterization amplify the Rrs-level signal into a much larger bbp700 overestimate. The cause is therefore not purely in Rrs — BING-specific model choices also contribute meaningfully.

**Summary:** The bias is likely two-part — (1) a modest, shared positive offset in Rrs(λ) (aerosol residuals, ~10% level per GIOP's near-zero log bias) that both algorithms inherit, and (2) a BING-specific amplification that raises the total overestimate to ~36%.

---

## Next Steps

- Identify what BING does differently from GIOP that would amplify a small Rrs offset into a large bbp700 overestimate (spectral weighting, prior on bbp, model parameterization).
- Test the aerosol hypothesis directly: filter matchups by aerosol optical depth (when available) and check whether δ_GIOP decreases under low-AOD conditions.
- Compare against shipboard Rrs measurements (AERONET-OC) to quantify the Rrs-level offset directly.
