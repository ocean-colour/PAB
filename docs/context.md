# PAB Context Reference

**Version:** 1.0
**Date:** 2026-06-17
**Authors:** JXP and Claude
**Purpose:** A distilled, single-page reference of the source material (papers,
code repositories, and documentation) relevant to designing **PAB** — the
matchup analysis between **PACE** (satellite ocean color) and **BGC-Argo**
(autonomous float) data. This file condenses the inputs listed in the *Context*
section of `claude_prompts/design_prompts.md` so the design document can be
written without re-reading every source. It is a living reference; bump the
version when material is added.

> Naming note: the design prompts refer to the analysis package as **IOPtics**;
> the Python package in this repo is `pab/`. Treat the two names as the same
> effort here.

---

## 1. The science problem

The goal is to retrieve **Inherent Optical Properties (IOPs)** — non-water
absorption `a_nw(λ)` and particulate backscattering `b_b,p(λ)` (often reported
as `bbp(700)`) — from **remote-sensing reflectance** `Rrs(λ)` measured by PACE,
and to **validate** those retrievals against in-situ **BGC-Argo** float profiles
(which directly measure `bbp(700)` and chlorophyll-a in the water column).
`bbp` is a widely used proxy for particulate organic carbon / phytoplankton
biomass. The workflow:

```
BGC-Argo profiles ──► QC, MLD, average bbp/Chl-a/T/S in mixed layer
       │
       └──► spatio-temporal matchup ──► PACE L2 granule ──► extract ~10 Rrs spectra
                                                                  │
                                                                  └──► BING (IOP retrieval + uncertainties)
                                                                            │
                                                                            └──► metrics, figures, tables, reports (.rst)
```

---

## 2. BING — the IOP retrieval engine (`docs/PDFs/bing.pdf`; Prochaska & Frouin 2025, *Biogeosciences* 22, 4705–4728)

**BING = "Bayesian INferences with Gordon coefficients."** Open-source Python
package for retrieving IOPs from `Rrs(λ)` *with full posterior uncertainties*.
Repo: `github.com/ocean-colour/bing` (Zenodo DOI 10.5281/zenodo.13292700);
companion package `ocpy` (Zenodo 10.5281/zenodo.17088615).

### Forward model (radiative transfer)
- Gordon (1988/1973) quasi-single-scattering: `u = bb/(a+bb)`;
  `rrs = G1·u + G2·u²` with **G1 = 0.0949, G2 = 0.0794** (constants, the
  default mode); above/below water conversion `Rrs = rrs / (0.52 + 1.17·rrs)`
  (Lee et al. 2002). Optional Raman scattering and chlorophyll-fluorescence
  terms.
- Water IOPs `a_w(λ)`, `b_bw(λ)` are known and act as natural priors: at
  **λ > 500 nm absorption is water-dominated** (constrains `b_b,nw`), at
  **λ < 450 nm backscatter is water-dominated** (constrains `a_nw`).

### The central result — physical degeneracy
`Rrs` depends only on the **ratio** `bb/a` (`rrs = Func(bb/a)`). This is a
**physical degeneracy**: any IOP solution can be replaced by an infinite set
that preserves `bb/a`. Therefore IOPs cannot be retrieved without strong priors
on the functional forms of `a(λ)` and `b_b(λ)`. Information-content analyses
(Cael et al. 2023) find only ~2 degrees of freedom in multispectral `Rrs`.

### IOP models (increasing complexity, `k` = # free parameters)
| k | `a_nw(λ)` | `b_b,p(λ)` | Notes |
|---|---|---|---|
| 2 | `A_cst` (const) | `B_nw` (const) | baseline |
| 3 | `A_dg·exp[−S_dg(λ−400)]` | `B_nw` | exponential CDOM+detritus |
| 4 | exponential | `B_nw·(λ/600)^β_nw` | adds backscatter power law |
| 5 | `A_dg·exp[...] + A_ph·a_ph(λ)` | power law | adds phytoplankton (Bricaud 1998: `a_ph = A·Chl^E`) |
| 2b | const + `A_ph·a_ph` (Chl, B_nw) | — | phytoplankton, no CDOM/detritus |
| arbitrary | one free param per λ (61 λ) | per-λ | unconstrained reference |

Named model strings combine the two, e.g. `"expb_pow"` / `"ExpBricaudPow"`
(exponential-Bricaud absorption + power-law backscatter) is the workhorse; GIOP
and GSM are reproduced as constrained `k=5` variants with fixed steep
`S_dg ≈ 0.018–0.0206 nm⁻¹`.

### Inference
- **MCMC via `emcee`** (Foreman-Mackey 2013): ~16 walkers, ~75 000 iterations,
  analyze last ~7000. Gaussian likelihood `−½ Σ(pred−Rrs)²/varRrs`; priors
  (log-uniform / uniform / Gaussian / ratio) double as hard bounds.
- **Levenberg–Marquardt χ² minimization** available as a fast warm-start and
  for reproducing GIOP/GSM.
- **Uncertainties = posterior percentiles** (e.g. 68% / 5th–95th) of the
  reconstructed IOPs from the chains.
- Model selection via **AIC / BIC** (ΔBIC < 0 favors the more complex model).

### Key findings (drive validation expectations)
- **Multispectral sensors (MODIS, SeaWiFS) cannot recover > 3 parameters**;
  phytoplankton absorption `a_ph` is not retrievable without strict priors
  (< 1% of L23 spectra favor the phytoplankton model with MODIS noise).
- **PACE/OCI can recover ~4 (possibly 5) parameters**, but only ~30% of the
  L23 dataset statistically favors including phytoplankton — and even then
  `a_ph(440)` retrievals can be biased low / consistent with zero at low Chl-a.
- `b_b,p` (amplitude `B_nw` + slope `β`) is the most robustly retrieved
  quantity → this is why **bbp** is the natural matchup observable against
  BGC-Argo.

### Validation dataset used in BING
- **Loisel et al. 2023 (L23)** — 3320 Hydrolight-simulated `a(λ)`,`b_b(λ)`
  spectra (Case I + Case II, Chl-a 0.01–10 mg m⁻³), 350–750 nm (analysis
  restricted to 400–700 nm). **Ground-truth IOPs known.** Loaded via
  `loisel23.load_ds()` in `ocpy`. Paper: `docs/PDFs/Loisel_et_al_ESSD_2023.pdf`
  (referenced; see also `$OS_COLOR/Loisel2023`).
- PACE noise model from a single L2 granule
  (`PACE_OCI..L2.OC_AOP.V2_0.NRT.nc`), median `Rrs_unc`; MODIS/SeaWiFS noise
  from SeaBASS matchups (Tables 1–2 of the paper).

### BING repo layout (for the design, not code spec)
- `bing/models/` — `anw.py`, `bbnw.py` (parameterization classes), `utils.init()`.
- `bing/rt/rrs.py` — Gordon forward model (`calc_Rrs`), Raman, fluorescence.
- `bing/fitting/` — `chisq_fit.py` (LM), `inference.py` (MCMC `fit_one`/`fit_batch`),
  `l23.py` (L23 driver).
- `bing/priors/`, `bing/parameters/`, `bing/data/` (incl. `PACE_error.csv`).
- `papers/biomass/` — **the most relevant template for PAB**: PACE↔BGC-Argo
  matchup of `bbp`. Scripts (`Analysis/py/`): `fitting.py` (`closest_Rrs()` to
  grab nearest PACE spectrum; two-stage LM→MCMC with `expb_pow`),
  `fit_giop.py` (GIOP baseline), `grab_pace_granules.py`, `argo.py`. The
  `stoer_py/` subdir reproduces Stoer et al. 2024 carbon-stock pipeline
  (Argo download → QC/bin → satellite preproc → bbp→carbon via Graff et al.
  2015). Figure `figs_biomass.py::fig_giop_vs_bnw_colored` (log-log GIOP vs
  BING bbp). Matchup CSVs: `matched_argo_bgc_profiles_bbp.csv`.

---

## 3. Matchup methodology — Bisson et al. (the template for PAB)

### Bisson et al. 2019, *Optics Express* 27, 30191 (`docs/PDFs/bisson2019.pdf`)
"Evaluating satellite estimates of particulate backscatter in the global open
ocean using autonomous profiling floats." **The canonical bbp matchup recipe:**
- n = 2486 surface matchups across 3 satellites; median satellite/float bbp
  ratio **0.77–1.66** depending on algorithm/sensor; **skill degrades where
  Rrs spatial variability is high.**
- **BGC-Argo processing:** profiles of `bbp(700)`; remove QC "bad data" and
  outliers (>1.5×IQR of log-transformed bbp); **compute MLD = depth where
  density exceeds the 10 m density by 0.03 kg m⁻³** (de Boyer Montégut–style);
  **de-spike with a 3-point moving median within the MLD** (removes bubble
  spikes); **average de-spiked bbp within the MLD** (MLD ≈ active mixing depth).
- **Satellite processing:** MODIS (1 km), VIIRS (750 m), OLCI (1.2 km) L2 Rrs;
  identify scenes coincident with a float observation; derive bbp via NASA
  inversion products (GIOP/GSM/QAA).

### Bisson et al. 2021, *Applied Optics* 60, 6978 (`docs/PDFs/bisson2021.pdf`)
"Seasonal bias in global ocean color observations." **Caveats for validation:**
- A **seasonal bias exists in satellite `Rrs(λ)`** at the MOBY validation site
  across MODIS/VIIRS/SeaWiFS; propagates to derived products (**bbp varies up to
  ~50%/yr, Chl ~25%, absorption ~15%**). Artifactual seasonality is strongest in
  **low-biomass (subtropical-gyre) waters.**
- Likely partly from the **aquatic BRDF** and residual **atmospheric
  correction** effects; no community fix yet → expect systematic, season- and
  region-dependent offsets when validating PACE against floats.
- **Matchup protocol used:** satellite pixels in a **5×5 box** around the in-situ
  point, **all unflagged**, neighbors within 3 h, within 3 h of each other;
  monthly averages; extrapolate float `bbp(700)` to the satellite band (e.g.
  531/532 nm). CALIOP lidar used as an independent bbp reference.

**Takeaways for PAB matchup design:** (1) average float bbp/Chl within the MLD,
de-spike first; (2) use a small (e.g. 5×5) unflagged pixel box near the float and
a tight time window; (3) flag/weight by `Rrs_unc` and by Rrs spatial
variability; (4) anticipate seasonal/regional biases, especially in oligotrophic
gyres; (5) account for the wavelength offset between float `bbp(700)` and the
PACE band used.

---

## 4. argopy — fetching & processing BGC-Argo (`argopy.readthedocs.io`; local source at `../argopy`)

`import argopy` → analysis-ready `xarray.Dataset` / `pandas.DataFrame` from the
Argo dataset (DOI 10.17882/42182). Hides DACs, R/A/D data modes, QC tables.

### Fetching
- Core class **`argopy.DataFetcher`** with three axes (set via
  `argopy.set_options(...)`, a context manager, or kwargs):
  - `ds=` → `'phy'` (default) or **`'bgc'`** (biogeochemical — what PAB needs).
  - `src=` → **`'erddap'`** (default; **only source that supports BGC**),
    `'gdac'`, `'argovis'`.
  - `mode=` → `'standard'` (default), **`'research'`** (delayed-mode, QC=1, best
    for MLD), `'expert'` (raw).
- Access points (chainable): **`.region([lon_min,lon_max,lat_min,lat_max,
  pres_min,pres_max,date_min,date_max])`** (primary for matchup; upper time
  bound exclusive), `.float(WMO)`, `.profile(WMO, cyc)`.
- BGC-only kwargs: **`params=`** (variables to return, e.g.
  `['CHLA','BBP700']`) and **`measured=`** (variables that must be non-NaN —
  useful to keep only valid surface CHLA/BBP700).

```python
import argopy
with argopy.set_options(ds='bgc', src='erddap', mode='standard'):
    f = argopy.DataFetcher(params=['CHLA','BBP700'], measured=['CHLA'])
    ds = f.region([-75,-45, 20,30, 0,10, '2024-03','2024-06']).load().data
```

### Variables (uppercase Argo names)
`CHLA` (chlorophyll-a), **`BBP700`** (particulate backscatter @700 nm), `DOXY`,
`PSAL` (salinity), `TEMP`, `PRES`, plus `NITRATE`, `PH_IN_SITU_TOTAL`,
`DOWNWELLING_PAR`, irradiance, `CDOM`. Helper lists in `argopy.utils`
(`list_bgc_s_parameters`, `list_standard_variables(ds='bgc')`).

### Returned objects
- `.data` → `xarray.Dataset` (default 1-D **`N_POINTS`** collection);
  `.index` → `pandas.DataFrame` of profiles; `.domain` → the selection box.
- `ds.argo.point2profile()` ↔ `profile2point()` (2-D `N_PROF × N_LEVELS`).
- `ds.argo.interp_std_levels([...])`, `ds.argo.groupby_pressure_bins(...)`.
- Per-float: `argopy.ArgoFloat(WMO).open_dataset('Sprof')` (BGC synthetic file).
- Index-first pre-selection: **`argopy.ArgoIndex(index_file='bgc-s')`** with
  `search_lat_lon([...])`, `search_wmo()`, etc. — natural for building matchups.

### Mixed-layer depth (MLD)
**No public MLD accessor.** argopy gives the ingredients:
`ds.argo.teos10(['SA','CT','SIG0','N2'])` → potential density `SIG0` for a
**de Boyer Montégut density-threshold MLD** (compute externally with `gsw`),
and `ds.argo.reduce_profile(func, params=[...])` to apply a custom per-profile
function. (An internal, unexported `argopy/utils/optical_modeling.py::MLD_Func`
implements the 0.03 kg m⁻³ criterion and is a usable reference.) Optical-depth
helpers exist too: `ds.argo.optic.Zeu()` (euphotic), `.DCM()` (deep Chl max).

### QC / filtering (matchup-relevant)
`ds.argo.filter_qc(QC_list=[1,2], ...)`, `ds.argo.datamode.filter(...)`,
`ds.argo.filter_researchmode()`. Geolocation: `LATITUDE`, `LONGITUDE`, `TIME`,
`PLATFORM_NUMBER` (WMO), `CYCLE_NUMBER`.

---

## 5. PACE / OCI — the satellite Rrs source (NASA PACE, OB.DAAC)

PACE launched Feb 2024; science data from **2024-03-05**. Sensor: **OCI (Ocean
Color Instrument)** — first global **hyperspectral** ocean-color sensor.

### OCI characteristics
- Continuous **~340–895 nm at 5 nm bandwidth (2.5 nm sampling**, finer near
  fluorescence/O₂) + **7 SWIR bands** (940–2260 nm, for atmospheric correction).
- **~1.2 km nadir** resolution, ~2700 km swath, ~2-day global coverage.
- vs MODIS/VIIRS (multispectral, fixed bands): OCI gives continuous spectra →
  more IOP/phytoplankton-community information (consistent with BING's finding
  that PACE can constrain ~4–5 parameters vs ≤3 for MODIS).

### Level-2 products ("granules")
- **`PACE_OCI_L2_AOP`** (AOP suite — holds **Rrs**; NRT: `..._NRT`); companion
  **`PACE_OCI_L2_IOP`** (NASA's own absorption/backscatter). Version **3.1**,
  netCDF-4, **OB.DAAC**. DOI `10.5067/PACE/OCI/L2/OC_AOP/3.1`. Dedicated
  cloud-mask product also available (`cloud_flag`, `cloud_flag_dilated`).
- **NetCDF group structure** (open as a datatree):
  - `geophysical_data` → **`Rrs`**, **`Rrs_unc`** (per-pixel uncertainty),
    **`l2_flags`** (bitmask).
  - `navigation_data` → `latitude`, `longitude` (2-D swath arrays).
  - `sensor_band_parameters` → wavelengths via the **`wavelength_3d`**
    coordinate.
  - `Rrs` shape `(number_of_lines, pixels_per_line, wavelength_3d≈172)`,
    **stored as scaled integers** — apply `scale_factor`/`add_offset`
    (xarray `mask_and_scale=True` does this).

### Access (Python)
```python
import earthaccess, xarray as xr
earthaccess.login(persist=True)                 # Earthdata Login (~/.netrc)
results = earthaccess.search_data(
    short_name="PACE_OCI_L2_AOP",
    temporal=("2024-04-01","2024-04-23"),
    bounding_box=(W, S, E, N),                   # small box around the float
    cloud_cover=(0, 50))
paths = earthaccess.open(results)                # lazy (S3 streaming in us-west-2)
dt = xr.open_datatree(paths[0])
```
- Data live on **Earthdata Cloud, AWS `us-west-2`** (S3 bucket
  `ob-cumulus-prod-public`). Direct S3 streaming is fast only **in-region**
  (PACE Hackweek / 2i2c JupyterHubs); otherwise `earthaccess` falls back to
  HTTPS download.

### Extracting individual spectra (~10) rather than full granules
1. **Lazy xarray + nearest-pixel indexing (recommended for ~10 spectra):** L2
   lat/lon are 2-D swath arrays (`xr.sel` won't work directly) — compute
   distance to the float `(lon,lat)`, take `argmin`, then
   `Rrs.isel(number_of_lines=i, pixels_per_line=j)` → a ~172-length spectrum.
   Prefer the **nearest *unflagged*** pixel, and consider a 5×5 box (per Bisson).
2. **OPeNDAP** (OB.DAAC Hyrax) — server-side variable/index subsetting.
3. **Harmony** (`harmony.earthdata.nasa.gov`) — cloud subsetting at scale;
   heavier setup than option 1 for only ~10 points.

### Quality control (`l2_flags`)
Decode the bitmask via `flag_meanings`/`flag_masks`. Standard ocean mask:
`ATMFAIL, LAND, HIGLINT, HILT, STRAYLIGHT, CLDICE, COCCOLITH, HISATZEN,
HISOLZEN, LOWLW, CHLFAIL, NAVFAIL, MAXAERITER`. Weight/QC each spectrum by
`Rrs_unc`; record view/solar zenith for glint; align overpass time with the
float profile time. (Recall Bisson: skill degrades where Rrs spatial
variability is high → check box homogeneity.)

**Tutorials:** OB.DAAC oceandata-notebooks (`nasa.github.io/oceandata-notebooks`),
PACE Hackweek 2024 (`pacehackweek.github.io/pace-2024`), NASA-Openscapes
earthdata-cloud-cookbook (OPeNDAP/Harmony recipes).

---

## 6. Candidate in-situ / reference datasets (for IOPtics validation)

| Dataset | What | Use | Source |
|---|---|---|---|
| **L23 (Loisel et al. 2023)** | 3320 Hydrolight-simulated `a`,`bb`,`Rrs` spectra; **ground-truth IOPs** | primary algorithm validation | `$OS_COLOR/Loisel2023`; `ocpy/hydrolight/loisel23.py`; `docs/PDFs/Loisel_et_al_ESSD_2023.pdf` |
| **PANGAEA / PANAGEA** | real spectra + in-situ IOP measurements | real-data validation | `ocpy/insitu/panagea.py`, `ocpy/docs/panagea.rst`; doi.pangaea.de/10.1594/PANGAEA.941318 |
| **GLORIA (Werdell+ 2013, "G13")** | global in-situ Rrs/IOP archive | validation | (to be sourced) |
| **BGC-Argo** | global float `bbp(700)`, Chl-a profiles | the PACE matchup target | via argopy |
| **SeaBASS / NOMAD** | NASA in-situ Rrs + IOP matchup archive | satellite-product validation | seabass.gsfc.nasa.gov |
| **MOBY** | Marine Optical Buoy hyperspectral Rrs time series (Lanai, HI) | "gold standard" vicarious cal; seasonal-bias reference | (Bisson 2021) |
| **CALIOP** | lidar bbp(532), independent of ocean color | cross-check on bbp bias | (Bisson 2021) |
| *Others to explore* | e.g. AERONET-OC, Tara Oceans, SOCCOM, NAAMES | TBD | internet search pending |

---

## 7. Source index

| Source | Location / URL |
|---|---|
| BING paper (Prochaska & Frouin 2025) | `docs/PDFs/bing.pdf` — *Biogeosciences* 22, 4705–4728 |
| Bisson et al. 2019 (bbp float matchups) | `docs/PDFs/bisson2019.pdf` — *Opt. Express* 27, 30191 |
| Bisson et al. 2021 (seasonal Rrs bias) | `docs/PDFs/bisson2021.pdf` — *Appl. Opt.* 60, 6978 |
| BING repository | `github.com/ocean-colour/bing` (esp. `papers/biomass/`) |
| ocpy (L23 loader, helpers) | `github.com/ocean-colour/ocpy` |
| argopy docs / source | `argopy.readthedocs.io/en/stable`; local `../argopy` |
| PACE / OCI data | `pace.oceansciences.org`, `oceancolor.gsfc.nasa.gov` (OB.DAAC) |
| earthaccess | `earthaccess.readthedocs.io` |

---

*End of context reference v1.0.*
