# PACE – Argo CDOM Comparison (Qualitative/Correlative)

**Date:** 2026-09-07
**Database:** `pab.db` (full production run — `pab_version = "1.0"`, 881 floats)
**Scripts:** `pab/matchup/cdom/` — `data.py` (shared loader + caveats),
`plot_cdom_scatter.py`, `plot_cdom_regional.py`, `plot_cdom_seasonal.py`,
`plot_cdom_map.py`, `plot_cdom_example_profile.py`, `run_all.py`
**Figures:** `pab/matchup/cdom/*.png`

---

## Why this comparison is qualitative only, not a bias analysis

Unlike the Chl-a and bbp700 deep dives, **this report makes no bias claim,
plots no 1:1 line, and states no "PACE is +X% relative to Argo" number.**
Argo's `CDOM` is a fluorescence proxy in **ppb QSDE** (Quinine Sulfate
Dihydrate Equivalent); the nearest PACE-side retrieval, BING's
`ExpBPow_Adg`, is the amplitude of a **combined CDOM + particulate detrital**
absorption term in **m⁻¹** — a different physical quantity, in different
units, with no fixed conversion between them. A ppb→absorption factor exists
only empirically and is instrument- and region-dependent; PAB does not invent
one. Every figure below carries this caveat explicitly, and the comparison is
restricted throughout to rank correlation (Spearman ρ) and qualitative
regional/seasonal pattern-matching, per the plan agreed in
`claude_prompts/chl_cdom_matchups.md` (C1–C4).

**A second, independent caveat: raw CDOM only, with a known, unapplied,
manufacturer-identified calibration bias.** Sea-Bird Scientific (who make the
CDOM fluorometers on BGC-Argo floats) issued a customer notice (2024-12-11)
that **all SBS CDOM fluorometers calibrated/serviced before 2023-01-13** —
most of the historical Argo fleet, given multi-year deployments — read
**~5.6x too low**, with a determined Reference Adjustment Factor (RAF) of
**5.62**. A second, separate sensor-reference bias is also documented but has
no published correction factor. A direct spot-check against live GDAC data
(`chl_cdom_prompt_1.md`, Task 1) found this correction is **not baked into
any archived value**: `CDOM_ADJUSTED` is entirely empty, fleet-wide — no
BGC-Argo float has ever had CDOM delayed-mode processed (confirmed again
below: 100% of this analysis's matchups carry `cdom_data_mode = 'R'`). Every
CDOM value plotted here is therefore raw, uncorrected, and — for most
pre-2023 sensors — likely reading substantially low relative to what a
corrected value would show. JXP has indicated an intent to apply a correction
after consulting BGC-Argo colleagues; that has not happened yet, and no
correction is applied or estimated here.

---

## Summary

Across **7,083 matchups** (48.5% of the 14,609 in the full Chl-a matchup set
— consistent with CDOM's known ~46-48% fleet coverage relative to
CHLA/BBP700), raw Argo CDOM shows **essentially no rank correlation** with
the fitted `Adg` amplitude: **Spearman ρ = -0.03** overall (statistically
distinguishable from zero only because of the large sample size — the effect
size itself is negligible). This holds up under every stratification tried:
by ocean basin (ρ from -0.09 to +0.19), and by season (ρ from -0.06 to +0.01).
No basin or season shows a materially different story.

This is a genuinely different, and on its face more surprising, result than
the companion Chl-a report's finding that the *Chl-a bias* correlates
modestly with `Adg` (ρ=-0.24) — here, the in-situ quantity `Adg` is supposed
to relate to (CDOM) shows almost no relationship with `Adg` itself. The two
findings are not in tension (one is about a bias, the other about a raw
quantity), but together they suggest `Adg`'s connection to actual dissolved
CDOM is weak, and whatever else `Adg` is picking up — detrital particulate
absorption, retrieval noise, or aliasing from other fitted terms — may
dominate it in much of the ocean.

**One important methodological point for future work on this dataset:**
Spearman rank correlation is invariant under any monotonic increasing
transform of either variable. Since the Sea-Bird RAF (multiplying every raw
CDOM value by the constant 5.62) is exactly such a transform, **applying the
still-pending correction would not change any of the correlations reported
here.** If JXP's planned correction pass ends up being a uniform
multiplicative factor, this report's qualitative finding — CDOM and `Adg`
are essentially rank-uncorrelated — will not need to be redone.

---

## Data

Reuses `pab.matchup.chl.data.load_chl_matchups()` (the CDOM population is a
subset of the exact same joined matchup table the Chl-a report draws from —
see `pab.matchup.cdom.data` for the CDOM-specific validity filter and caveat
text) rather than a separate query path.

| | Value |
|---|---|
| Matchups with a BING `ExpBPow` fit | 14,609 |
| Valid for this comparison (finite, positive `cdom` and `adg_bing`) | **7,083** (48.5%) |
| `cdom_data_mode` breakdown | 100% `'R'` (real-time); 0% `'A'`/`'D'` |
| Basin split | Atlantic 3,123 / Pacific 2,608 / Indian 808 / Southern 544 |
| Season split | MAM 2,263 / JJA 1,646 / DJF 1,614 / SON 1,560 |

---

## Methodology

### Argo: CDOM ingestion and processing

CDOM profiles are fetched via `argopy`'s BGC `DataFetcher` (`ds='bgc',
src='gdac', mode='expert'`), the same mechanism already used for CHLA and
BBP700; `"CDOM"` was added to `pab/argo/fetch.py::DEFAULT_PARAMS` in the
Stage 10 pass. For each profile, `pab/argo/fetch.py::iter_profiles` extracts
the per-level `CDOM` array along with the per-parameter `CDOM_DATA_MODE`.

`pab/argo/summary.py::summarize_profile` then computes a mixed-layer mean and
standard deviation of CDOM as a plain arithmetic mean over all levels within
the mixed layer. No de-spiking and no IQR outlier rejection are applied —
that treatment is BBP700-specific (following Bisson et al.'s recipe); CHLA
and CDOM both receive the plain mean.

Two limitations of this ingestion path should be stated plainly:

1. **No QC-flag filtering is applied.** This was verified directly against
   the live pipeline code rather than assumed. A
   `pab.argo.fetch.filter_quality()` function exists (default: keep QC flags
   1 and 2), but a repo-wide search confirms it has zero call sites in
   `pab/pipeline.py` or anywhere else in the ingestion path. `fetch_profile()`
   calls `build_fetcher(...).profile(wmo, cycle).load().data` and hands the
   raw fetched dataset directly to `iter_profiles`/`summarize_profile`.
   Consequently, every per-level CDOM (and CHLA) value within the mixed layer
   is averaged in regardless of its Argo QC flag (1 = good, 2 = probably
   good, 3 = probably bad, 4 = bad).
2. **All CDOM values are real-time.** A fleet-wide spot-check during the
   implementation pass found `cdom_data_mode` to be 100% `'R'`: no BGC-Argo
   float has had CDOM delayed-mode/QC-reprocessed by any DAC. Every CDOM
   value in this analysis is therefore real-time, unfiltered, and
   uncorrected for the known Sea-Bird calibration low-bias discussed
   elsewhere in this report.

The resulting `cdom`, `cdom_std`, and `cdom_data_mode` are persisted into the
`mld_summary` table (schema v4) via `persist_summary()`, keyed by
`profile_id`.

### PACE/BING: the fitted Adg amplitude

BING is the Bayesian MCMC spectral-inversion framework PAB uses to fit each
matchup's nearest-pixel PACE `Rrs(λ)` spectrum (400–700 nm). All fits in this
report use the `ExpBPow` model pair (Exponential–Bricaud a_ph + power-law
particulate backscatter). Each fit is an LM warm-start followed by full MCMC
(`emcee`), producing a posterior over the model parameters.

`Adg` is the amplitude of an exponential CDOM+detrital absorption term of the
form `A_dg * exp[-S_dg * (wavelength - 400)]`. It is a term in the
*satellite* radiative-transfer/absorption model — not any processing of the
Argo CDOM measurement. It has no knowledge of, and is not tuned against,
in-situ CDOM in any way, which is part of why this report's comparison is
strictly qualitative.

Every fit stores 10 posterior IOP quantities in the long-format
`fit_results` table (as `BING_ExpBPow_<quantity>`), each recorded as a
posterior median plus a 5–95% credible interval (`value`, `value_lo`,
`value_hi`). `Adg` (`BING_ExpBPow_Adg`) is one of these 10.

---

## Example: One Float, One Matchup, One Fit

To make the pipeline concrete, this section walks one real matchup end to
end: float WMO 5907147, cycle 258 (43.08°N, 9.11°E, 2026-04-24), which pairs
with a PACE granule fitted by BING. This is the same matchup used in Figure
1's scatter — not a cherry-picked illustration built separately from the
analysis population.

### The Argo profile

![CDOM and CHLA vs. pressure for WMO 5907147 cycle 258, points colored by QC flag, MLD marked](../../pab/matchup/cdom/cdom_example_argo_profile.png)

The figure shows CDOM and CHLA vs. pressure as fetched — no QC screen
applied by PAB — with points colored by their Argo QC flag and the 16.9 m
mixed-layer depth marked as a dashed line. The stored `mld_summary` row for
this profile is:

| Quantity | Value |
|---|---|
| `mld` | 16.9 m |
| `cdom` | 0.219 ppb QSDE |
| `cdom_std` | 0.279 |
| `cdom_data_mode` | `'R'` |
| `chla` (raw) | 0.057 mg/m³ |
| `chla_adjusted` | 0.032 mg/m³ |
| `chla_data_mode` | `'A'` |
| `n_points` | 45 |

Note that `cdom_std` exceeds half the mean — a noisy real-time signal. A
fresh live re-fetch of this exact profile (via the same `argopy` path, no
filtering) found that every CDOM point in the profile carries Argo QC flag 3
("probably bad") and every CHLA point carries QC flag 4 ("bad") — none were
QC 1 or 2. All of these unscreened points are what got averaged into the
`mld_summary` values above. This is a concrete illustration, for this one
profile, of the no-QC-filtering behavior documented in the Methodology; it
is not a claim about the QC-flag distribution of the fleet as a whole.

### The BING fit

![Standard two-panel BING fit figure: observed vs. median Rrs with credible band, and retrieved bbp spectrum](../../pab/matchup/cdom/cdom_example_bing_fit.png)

The figure is PAB's standard two-panel fit figure
(`pab.plotting.fit_fig.fit_figure`): the top panel shows the observed vs.
BING-median `Rrs(λ)` with a 5–95% credible band; the bottom panel shows the
retrieved `b_bp(λ)` spectrum with its own credible band, 700 nm marked.
(This format predates the CDOM work and does not plot `Adg` directly.) The
fit here is a real production fit, reconstructed from its archived MCMC
chain — visual agreement between observed and median Rrs is excellent
across the full 400–700 nm range with a narrow credible band, and the
retrieved `b_bp(λ)` declines smoothly.

- `fit_id`: `5907147_258_PACE_OCI.20260424T111536.L2.OC_AOP.V3_2.nc_743_198_ExpBPow`
- Reduced `chisq = 0.093` (well below 1), `success = True`

Retrieved quantities (posterior median [5–95% interval]):

| Quantity | Value |
|---|---|
| `Adg` | 0.036 [0.032, 0.045] m⁻¹ |
| `Sdg` | 0.018 |
| `chl` | 0.152 mg/m³ |
| `bbp700` | 0.00051 m⁻¹ |
| `Aph` | 0.0085 |
| `Bnw` | 0.00067 |
| `beta` | 1.81 |

(For context only: BING's `chl` of 0.152 mg/m³ sits well above this
profile's Argo raw chla of 0.057 and adjusted chla of 0.032 mg/m³, but
chlorophyll is outside this report's scope.)

This fit's `Adg = 0.036 m⁻¹` is the value paired against this profile's
mixed-layer CDOM of 0.219 ppb QSDE as one point in the Figure 1 scatter.

---

## Figure 1 — Argo CDOM vs. PACE-fitted Adg

**File:** `cdom_vs_adg_scatter.png`

![CDOM vs Adg scatter](../../pab/matchup/cdom/cdom_vs_adg_scatter.png)

**Key observations:**
- No 1:1 line, by design (see above). Spearman ρ = -0.03 (n=7,083, p=0.014 —
  significant only in the large-sample statistical sense, not practically
  meaningful).
- The point cloud is broad and largely unstructured: CDOM values span roughly
  four orders of magnitude (~10⁻⁵ to ~10² ppb QSDE, with the bulk between
  ~0.1 and ~5), and for any given CDOM value, `Adg` spans roughly two orders
  of magnitude.
- A small number of very low `Adg` values (below ~10⁻³ m⁻¹) sit at
  moderate-to-high CDOM — a handful of BING fits pushing the CDOM/detrital
  amplitude toward its lower bound regardless of the in-situ CDOM reading.

---

## Figure 2 — Regional Pattern: by Ocean Basin

**File:** `cdom_vs_adg_by_basin.png`

![CDOM vs Adg by basin](../../pab/matchup/cdom/cdom_vs_adg_by_basin.png)

**Key observations:**
- Atlantic (n=3,123, ρ=-0.06) and Southern (n=544, ρ=-0.09) show mild
  negative correlation; Indian (n=808, ρ=+0.06) is close to zero; **Pacific
  (n=2,608, ρ=+0.19) is the one basin with a correlation worth noting**, though
  still weak in absolute terms.
- No basin shows anything resembling the strong rank agreement seen in the
  Chl-a-vs-Argo comparison (ρ=0.78) — CDOM/`Adg` agreement is uniformly weak
  to absent, everywhere.
- The Pacific's mild positive signal is not obviously explained by this
  comparison alone (e.g., a specific water mass or CDOM source) and is flagged
  as the one pattern worth a closer look if this comparison is revisited after
  the Sea-Bird correction is applied.

---

## Figure 3 — Seasonal Pattern

**File:** `cdom_vs_adg_seasonal.png`

![CDOM vs Adg by season](../../pab/matchup/cdom/cdom_vs_adg_seasonal.png)

**Key observations:**
- All four seasons show near-zero correlation (DJF -0.03, MAM -0.03, JJA
  -0.06, SON +0.01) — no meaningful seasonal modulation of the CDOM/`Adg`
  relationship, in either direction.
- This rules out a seasonal confound (e.g., productivity-driven CDOM
  production varying by season in a way that would show up differently in
  different quarters) as an explanation for the weak overall correlation —
  the weakness is consistent year-round.

---

## Figure 4 — Global Coverage

**File:** `cdom_global_map.png`

![CDOM matchup coverage map](../../pab/matchup/cdom/cdom_global_map.png)

**Key observations:**
- Descriptive only: color encodes raw Argo CDOM magnitude, not a PACE
  comparison (per C3, no bias metric exists for CDOM).
- Coverage tracks the general BGC-Argo matchup population (dense in the
  Atlantic and western Pacific, sparser in the Indian Ocean and Southern
  Ocean) rather than concentrating in any particular CDOM-source region (e.g.
  major river plumes are not obviously over-represented in this matchup set).
- The highest single CDOM value in the set is a visibly isolated point in the
  South Pacific; no broad regional hot-spot of elevated CDOM stands out
  otherwise. This map is provided for coverage/context, not as evidence for
  or against any hypothesis about the CDOM/`Adg` relationship.

---

## Interpretation

1. **CDOM and the fitted `Adg` amplitude are essentially rank-uncorrelated,
   globally and in every basin/season slice tried.** The overall ρ=-0.03 is
   not practically different from zero, and no stratification surfaces a
   materially different story (Pacific's ρ=+0.19 is the largest magnitude
   seen anywhere, and still weak).

2. **This is not an artifact of the unapplied Sea-Bird correction.** Spearman
   ρ is invariant under a uniform multiplicative rescaling, so applying the
   RAF (5.62x) to every raw CDOM value — if that is what the eventual
   correction turns out to be — would not change any correlation reported
   here. If the eventual, fuller correction (including the second,
   currently-unpublished sensor-reference bias) is *not* a uniform factor,
   this conclusion would need to be revisited; that cannot be evaluated until
   that correction is published.

3. **Plausible reasons `Adg` might not track in-situ CDOM well, none
   confirmed here** (out of scope for a qualitative comparison, but worth
   naming for follow-on work):
   - **`Adg` is a combined quantity.** JXP's own framing when scoping this
     comparison (C3) anticipated detrital absorption is generally much
     smaller than CDOM absorption; this result does not confirm that
     expectation — if detritus is negligible, a cleaner signal between CDOM
     and `Adg` might be expected than what is observed.
   - **Unit/quantity mismatch nonlinearity.** A fluorescence proxy (ppb QSDE)
     and an absorption coefficient (m⁻¹) need not be even monotonically
     related if the underlying optical relationship is regime-dependent (e.g.
     changes with CDOM source, degradation state, or particle load) — this
     could suppress rank correlation even without either measurement being
     "wrong."
   - **CDOM sensor data quality.** Every value used here is real-time only —
     no BGC-Argo float has ever had CDOM delayed-mode quality control applied
     (Figure 1's `cdom_data_mode` breakdown, corroborating the fleet-wide
     spot-check in `chl_cdom_prompt_1.md`) — so real-time-grade sensor noise
     is plausibly larger, relative to the signal, than for the more mature
     CHLA/BBP700 QC pipelines.

4. **Net assessment:** this comparison does not support treating BING's
   `Adg` as a usable proxy for in-situ CDOM concentration in its current
   form, though it remains a physically motivated absorption-budget term in
   its own right. The companion Chl-a report's `Adg`-vs-Chl-bias correlation
   (ρ=-0.24) should not be read as validating `Adg` against CDOM — that
   finding and this one address different questions and are not in tension,
   but this report does not provide independent support for the physical
   CDOM-aliasing mechanism hypothesized there.

---

## How to Reproduce

```bash
cd /path/to/PAB
conda activate ocean14

# Regenerate every figure and print the headline correlations
python -m pab.matchup.cdom.run_all --outdir pab/matchup/cdom
```

Individual figures:

```bash
python -m pab.matchup.cdom.plot_cdom_scatter --out cdom_vs_adg_scatter.png
python -m pab.matchup.cdom.plot_cdom_regional --out cdom_vs_adg_by_basin.png
python -m pab.matchup.cdom.plot_cdom_seasonal --out cdom_vs_adg_seasonal.png
python -m pab.matchup.cdom.plot_cdom_map --out cdom_global_map.png
```

All scripts accept `--db` (default: `$PAB_DATA_DIR/pab.db`).

---

## Notes

- All scripts are in `pab/matchup/cdom/`, reusing the Chl-a report's shared
  loader (`pab.matchup.chl.data.load_chl_matchups()`) rather than a separate
  query path — the CDOM matchup population is a strict subset of the same
  joined table.
- **No `cdom_adjusted` field exists in `pab.db`.** Per `chl_cdom_prompt_1.md`
  Q1, JXP chose to ingest raw `cdom` only, deferring any Sea-Bird correction
  pending a BGC-Argo consult. When that correction is applied and re-ingested,
  Interpretation point 2 above explains exactly when this report's
  conclusions would (and would not) need revisiting.
- This report is intentionally narrower in scope than the Chl-a report: no
  bias number, no 1:1 line, and no claim about which quantity is "more
  correct" — per C3, that is a deliberate, agreed limitation given the
  units/quantity mismatch, not an oversight.
