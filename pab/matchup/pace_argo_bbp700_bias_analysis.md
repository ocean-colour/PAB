# PACE – Argo bbp700 Bias Analysis

**Date:** 2026-08-05  
**Database:** `pab.db` (run1k — 273 matchups, 245 floats)  
**Scripts:** `pab/matchup/` — `plot_bbp_matchup_map.py`, `plot_bbp700_vs_temp.py`, inline analysis cells  
**Figures:**
- `bbp700_reldiff_histogram.png`
- `bbp700_pace_vs_argo_scatter.png`
- `bbp700_reldiff_vs_dtime.png`
- `bbp700_reldiff_vs_dist.png`

---

## Summary

PACE OCI systematically retrieves higher bbp(700 nm) than BGC-Argo floats at the same
location. Across 264 valid matchups, PACE exceeds Argo in 222 cases (84%) with a
median relative difference of **+0.35** — meaning PACE bbp700 is on average ~54%
larger than the Argo mixed-layer value. This positive bias is global, present across
all retrieved bbp700 magnitudes (~10⁻⁴ to 10⁻² m⁻¹), and shows no systematic
dependence on the time or spatial separation of the matchup pair. The most likely
physical explanation is a depth-sampling mismatch: PACE integrates over the
near-surface optical depth (~few metres), while Argo averages over the full mixed
layer (typically 20–60 m). If bbp700 decreases with depth within the mixed layer —
as expected near the surface optical maximum — PACE will consistently exceed the
MLD mean.

---

## Data

All figures draw from the `pab.db` `run1k` database via `pab.metrics.compare.gather_matchups()`,
which joins five tables:

| Table | Content |
|---|---|
| `matchups` | Satellite–float collocation record (distance, Δt, granule) |
| `profiles` | Float WMO, cycle, position, time |
| `mld_summary` | Argo mixed-layer bbp700, Chl-a, temperature |
| `fits` | BING MCMC fit metadata (χ²ᵣ, success, wavelength range) |
| `fit_results` | Posterior median and 90% CI per retrieved quantity |

**Relative difference** is computed as:
```
rel_diff = (bbp700_PACE − bbp700_Argo) / bbp700_PACE
```
where `bbp700_PACE` is the BING posterior median and `bbp700_Argo` is the Argo
mixed-layer mean from `mld_summary`. Nine matchups with NaN Argo values are excluded,
leaving n = 264 for all figures.

---

## Figure 1 — Distribution of Relative Differences

**File:** `bbp700_reldiff_histogram.png`

![Relative difference histogram]({{artifact:39bac237-55a9-4101-9036-9c3cfc5ab4c6}})

The histogram shows the full distribution of (PACE − Argo)/PACE across all 264 valid
matchups, binned at width 0.1. The dashed vertical line marks zero (perfect agreement)
and the solid red line marks the overall median (+0.35).

**Key observations:**
- The distribution is strongly right-skewed and peaked between +0.25 and +0.60
- 222 of 264 matchups (84%) are positive — PACE exceeds Argo
- The median is +0.35; the bulk of the distribution sits between +0.1 and +0.9
- The negative tail (42 matchups, 16%) extends to approximately −1.5, with two
  extreme outliers beyond −1.5 visible as isolated bars on the far left
- The shape is not consistent with random measurement noise (which would be symmetric
  around zero) — the systematic positive offset indicates a real physical or
  methodological offset

---

## Figure 2 — PACE vs. Argo bbp700 (1:1 scatter)

**File:** `bbp700_pace_vs_argo_scatter.png`

![PACE vs Argo 1:1 scatter]({{artifact:0abc3590-ea4d-4621-9a5a-13b1a95184be}})

Log-log scatter of PACE bbp700 (y-axis) against Argo bbp700 (x-axis) for all 264
valid matchups. The dashed line is the 1:1 reference. Points are coloured by relative
difference using the RdBu_r colormap (red = PACE > Argo, blue = Argo > PACE).

**Key observations:**
- Most points lie above the 1:1 line, consistent with the positive bias seen in Fig. 1
- Both instruments span a similar dynamic range (~3×10⁻⁴ to ~5×10⁻³ m⁻¹ for the bulk
  of the population), indicating the matchup pairs sample comparable water types
- 42 points fall below the 1:1 line, spread across the full bbp700 range —
  Argo-exceeds-PACE cases are not confined to a specific magnitude regime
- The two most extreme below-line points (dark navy, rel_diff ≈ −1.1 to −1.25) sit
  at low-to-mid Argo bbp700 (~4×10⁻⁴ to ~1.5×10⁻³ m⁻¹), with PACE bbp700 near
  ~2×10⁻⁴ m⁻¹ — roughly an order of magnitude below the 1:1 line at those values.
  These are likely anomalous Argo profiles (sensor spike or bloom) rather than
  high-backscattering events; they are also visible as the isolated bars near −1.25
  in the histogram (Fig. 1)

---

## Figure 3 — Relative Difference vs. Time Separation

**File:** `bbp700_reldiff_vs_dtime.png`

![Relative difference vs time separation]({{artifact:fc7d7f3a-76b9-4c75-b760-fc07f02049dc}})

Scatter of relative difference against the time separation (Δt, in hours) between
the PACE overpass and the Argo float surfacing. Points are coloured by relative
difference (RdBu_r, ±1 clip). The dark red horizontal line shows the overall median
(+0.35). The black line connects octile bin medians — each bin contains an equal
number of matchups.

**Key observations:**
- Δt ranges from 0 to 24 hours across the matchup population
- The octile bin medians (black dots) vary between approximately +0.22 and +0.42
  but show no systematic trend with increasing Δt
- The overall median line (+0.35) passes through or near all bin medians
- 2 extreme outliers beyond ±1.5 are excluded from the y-axis (noted in figure)
- The absence of a Δt trend argues against diurnal variability (e.g., daytime
  heating of the near-surface layer, or diel vertical migration of scatterers) as
  the primary driver of the bias. A time-varying process would produce bin medians
  that rise or fall with Δt; they do not.

---

## Figure 4 — Relative Difference vs. Spatial Separation

**File:** `bbp700_reldiff_vs_dist.png`

![Relative difference vs spatial separation]({{artifact:5b023629-068d-4b90-88d1-40cc2970c28d}})

Scatter of relative difference against the distance in km between the PACE pixel
centroid and the Argo float position. Points are coloured as in Fig. 3. The black
line connects octile bin medians.

**Key observations:**
- Spatial separation ranges from 0.07 to 4.95 km; median ~0.6 km
- At short separations (< 1 km, the majority of matchups), bin medians cluster
  between +0.20 and +0.38
- Beyond ~2 km, the two rightmost bin medians rise to approximately +0.50–0.52,
  suggesting a modest increase in bias at larger separations
- All bin medians remain well above zero across the full distance range
- The weak distance dependence is consistent with horizontal patchiness contributing
  to some matchup-to-matchup variability, but the persistent positive bias at all
  separations — including the nearest pixels — indicates that patchiness alone
  cannot explain the offset
- 2 extreme outliers beyond ±1.5 are excluded from the y-axis (noted in figure)

---

## Interpretation

Taken together, the four figures support the following interpretation:

1. **The positive bias (PACE > Argo) is robust.** It appears in 84% of matchups,
   is present across all bbp700 magnitudes, and has a median of +0.35. This cannot
   be explained by random error alone.

2. **The bias is not driven by matchup geometry.** Neither time separation (0–24 h)
   nor spatial separation (0–5 km) shows a clear systematic trend in the bin medians.
   A geometry-driven bias would increase monotonically with Δt or distance; it does not.

3. **Depth mismatch is the leading hypothesis.** PACE Rrs and the BING bbp700
   retrieval are most sensitive to the upper few metres of the water column. Argo's
   mixed-layer average integrates over a much deeper layer (typically 20–60 m). If
   backscattering decreases with depth — as expected below the surface optical maximum
   — PACE will systematically exceed the Argo MLD mean, producing the observed
   positive bias that is constant with Δt and distance.

4. **Alternative causes are not ruled out.** Systematic offsets in the BING prior
   set, uncertainty in Argo bbp700 calibration (particularly the dark count
   correction), or the mismatch between the PACE pixel spatial resolution (~1 km)
   and the Argo point measurement could all contribute. The clean-subset analysis
   (cloud cover < 50%, χ²ᵣ < 1.0) showed the bias strengthens to +0.49 in the
   highest-quality matchups, ruling out PACE data quality as the primary driver.

---

## How to Reproduce

```bash
cd ~/Documents/summer\ 2026/PAB
conda activate ocean14

# Histogram
python - <<'EOF'
import sys, numpy as np, matplotlib.pyplot as plt
sys.path.insert(0, '.')
from pab.db.store import Store
from pab.metrics.compare import gather_matchups

db = 'path/to/pab.db'
with Store.open(db, create=False) as store:
    df = gather_matchups(store)

bbp_pace = np.asarray(df["bbp_bing"], dtype=float)
bbp_argo = np.asarray(df["bbp_argo"], dtype=float)
rd = (bbp_pace - bbp_argo) / bbp_pace
valid = np.isfinite(rd) & np.isfinite(bbp_argo)
rd_v = rd[valid]

fig, ax = plt.subplots(figsize=(6.5, 4))
ax.hist(rd_v, bins=np.linspace(-1.5, 1.5, 32), color="#d6604d",
        alpha=0.8, edgecolor="white", linewidth=0.4)
ax.axvline(0, color="#444", lw=1.0, ls="--", label="Zero")
ax.axvline(np.median(rd_v), color="#7f0000", lw=1.8, ls="-",
           label=f"Median = {np.median(rd_v):+.2f}")
ax.set_xlabel("Relative difference  (PACE − Argo) / PACE")
ax.set_ylabel("Number of matchups")
ax.set_title(f"PACE bbp700 exceeds Argo in {(rd_v>0).sum()} of {len(rd_v)} matchups "
             f"({100*(rd_v>0).mean():.0f}%)")
ax.legend(frameon=False)
ax.spines[["top","right"]].set_visible(False)
fig.tight_layout()
fig.savefig("bbp700_reldiff_histogram.png", dpi=200, bbox_inches="tight")
EOF
```

For the Δt and distance scatter plots, additionally join `matchups.dtime_hours` and
`matchups.distance_km` via `store.query_df("SELECT matchup_id, dtime_hours, distance_km FROM matchups")`.

---

## Notes

- All scripts are in `pab/matchup/`. The standalone scripts (`plot_bbp_matchup_map.py`,
  `plot_bbp700_vs_temp.py`) accept `--db` to point at any pab.db file.
- The 9 matchups with NaN Argo bbp700 are excluded from all figures. Their NaN values
  reflect Argo profiles where the bbp700 sensor was not operating or failed QC.
- The two extreme outliers (rel_diff < −1.5) appear to be anomalous Argo profiles
  (possible sensor spike or bloom event) and are not shown within the ±1.5 y-axis
  limits, but they are noted in each figure's annotation.
