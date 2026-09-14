# Discussion draft — the PACE−Argo bbp700 bias

*Task 6 synthesis, 2026-09-13. Draws on Tasks 0–5 (`task0`–`task5` write-ups
in this directory), the thesis draft, and the papers read for Task 1. The
numbers below are from the full-run database (n = 13,562 matchups, March
2024 – June 2026) and the Task 2–5 diagnostics unless noted.*

---

Across 13,562 co-locations spanning all major ocean basins and 27 months of
PACE operations, OCI-derived bbp(700) exceeds concurrent BGC-Argo
measurements in 83.5% of matchups, with a median relative bias δ = (PACE −
Argo)/PACE of +0.37 (median ratio 1.59×). The discrepancy is strongly
regime-dependent — median δ = +0.45 in oligotrophic water (Argo bbp < 0.001
m⁻¹, 90% positive) but −0.03 in productive water (> 0.005 m⁻¹) — and our
diagnostics exclude the mundane explanations. The bias is insensitive to
co-location quality (δ is uncorrelated with time separation and only weakly
correlated with distance, ρ = 0.15, and it survives the strict Bailey &
Werdell (2006) criteria), to vertical sampling (flat against mixed-layer
depth), and to float sensor drift: using deployment dates for 787 of 788
matchup floats, δ is flat against float age both across floats (ρ = −0.003
over 0–8.2 years) and within individual float lifetimes (356 floats, median
within-float ρ = −0.002), so time-dependent dark-count or sensitivity drift
is ruled out. A static, fleet-wide float calibration offset cannot be
excluded by these tests, but the documented ECO error budget of 10–15%
(Bisson et al., 2019; up to ~20% in Serra-Pompei et al., 2023) is well short
of the observed 59% median ratio. Fluorescence contamination of the
*observed* signal is likewise disfavored: fluorescence line height
anticorrelates with δ (ρ = −0.25), the opposite of that hypothesis's
prediction.

Two independent lines of evidence localize the dominant errors to the
satellite side, and together they decompose the bias into two comparably
sized parts. The first is missing inelastic physics in the retrieval
configuration. The production BING fits modeled Rrs(400–700 nm) with elastic
scattering only, so real Raman-scattered and chlorophyll-fluoresced photons
— which contribute disproportionately at 700 nm, where the elastic
water-leaving signal is small — were necessarily absorbed into the retrieved
bbp. Refitting the same spectra with the recently corrected inelastic
treatment (a validated Ed(λ′)/Ed(λ) Raman correction and a fluorescence term
carrying the Lu = Eu/π conversion, both pinned to Loisel et al. (2023)
HydroLight truth) lowers retrieved bbp(700) by a nearly uniform factor of
0.78 (Raman ~14%, fluorescence at φ_C = 0.02 ~8%) while slightly improving
fit quality, cutting the subsample median δ from +0.35 to +0.15 (paired p ≈
10⁻⁴⁴) and, extrapolated to the full dataset, the headline bias from +0.37
to roughly +0.19. The second line is an Rrs-level residual that survives
this correction. An independent inversion (NASA's GIOP, anchored at 442 nm
and insensitive to the red-band issues above) still overestimates float bbp
by ≥ 23% in oligotrophic water — a floor, since GIOP's spectral slope sits
at its cap — and the inelastically corrected BING converges to nearly the
same value (~+0.27). This shared residual carries a direct atmospheric
fingerprint: δ rises monotonically with the PACE-retrieved aerosol optical
depth (ρ = +0.16, p ≈ 10⁻⁸², robust to regime control; median δ +0.29 under
clean skies vs +0.43 under hazy ones), is elevated on moderate-glint pixels,
and is larger under coarse (low-Ångström) aerosol.

The most likely explanation is therefore a combination: roughly half of the
originally reported bias is a retrieval-configuration artifact — elastic-only
fitting of inelastically contaminated red-band Rrs — and the remainder is an
additive error in Rrs(λ) itself, upstream of any inversion, most plausibly
residual aerosol (and glint) radiance from the atmospheric correction. The
radiative-transfer leverage makes the latter quantitatively easy: with
rrs ≈ g₁·bb/(a + bb) (Gordon et al., 1988) and absorption at 700 nm dominated
by water, δbbp ≈ (a_w/g₁)·δrrs, so the residual oligotrophic overestimate of
~2×10⁻⁴ m⁻¹ requires only ~2×10⁻⁵ sr⁻¹ of spurious Rrs(700) — far below
red-band atmospheric-correction uncertainties, and consistent with Bisson et
al.'s (2021) observation that small aerosol-correction errors produce large
relative Rrs errors in the green and red. An additive Rrs error of this kind
also reproduces the regime structure naturally: a fixed δrrs is a large
fraction of bbp where bbp ≈ 5×10⁻⁴ m⁻¹ and negligible where it is ten times
larger. What the data cannot yet resolve is the composition of that additive
term. The clean-sky floor (median δ ≈ +0.38 in the low regime even at
aot(865) < 0.05, before inelastic correction) shows that retrieved AOD alone
does not index the residual — consistent either with aerosol-model error that
persists in clear skies (retrieved AOD comes from the same correction) or
with a second additive component such as glint residual, BRDF, or red-band
vicarious-calibration error. Nor can a modest static float-calibration
contribution (≤ 10–15%) be separated from the satellite residual with
matchup data alone.

Three measurements would settle the attribution. First, re-run the
production retrievals with the corrected Raman and fluorescence terms
enabled — converting our subsample extrapolation into a measured full-run
number and testing whether the corrected bias indeed converges on the
algorithm-independent (GIOP-floor) value of ~+0.2. Second, quantify the
Rrs-level offset directly by comparing PACE Rrs(650–720 nm) against in situ
radiometry (AERONET-OC and PACE validation cruises); the prediction is an
additive offset of order +2×10⁻⁵ sr⁻¹ in oligotrophic scenes, growing with
AOD. Third, repeat the matchup analysis on NASA's forthcoming reprocessing
with polarimeter-informed (SPEXone/HARP2) aerosol characterization: if the
remaining bias shrinks in step with improved aerosol models — and vanishes
fastest in the clean-sky subset — residual atmospheric correction is
confirmed as the final term; if it does not, attention shifts to red-band
calibration and to the float side of the ledger, where a community
recalibration of ECO scale factors has precedent (Poteau et al., 2017;
Barnard, 2021).

---

*Numbers cited: full-run and regime statistics (Task 0), float-age test
(Task 3), BING/GIOP comparison and GIOP floor (Task 2), AOD dose-response
and clean-sky floor (Task 4), inelastic refit (Task 5), literature bounds
(Task 1). Papers cited were fetched and read for Task 1 except Poteau et
al. (2017), known via the Barnard (2021) SEANOE record and secondary
citations — verify before final submission; Gordon et al. (1988) is cited
via its formulation in IOCCG Report 5.*
