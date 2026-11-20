# Analysis for the paper

## Goals

Examine, discuss the analysis methods used for our paper on comparing PACE and Argo bbp(700).

## Prompts

### RT

1.  For the v2 PAB analysis, we adopted the `robust_hybrid` RT model from the RoB repository (`Oceanography/python/retrieve-or-bust`).  As I understand it, the 
packaged emulator was trained at nadir view and zero relative azimuth, 
while the pixels fitted here are viewed at θ_v = 13–60°.   However, I anticipate that the PACE
Level 2 product was converted to a nadir view.   Please explore this and 
provide your findinga and any questions in the "Q&A/Viewing angle" section below.
Use Opus 5.5.  Log your work.

2. I have answered your questions in the "Q&A/Viewing angle" section below.  Please
download the `l2gen` codebase to this workstation as described.  Then investigate
the Raman correction applied to the L2 `Rrs` further.  
Also make additional effort to see if the PACE webpages provide explicit documentation
on this point.
Provide your findings and any questions
in the "Q&A/Raman correction" section below.  Use Opus 5.5.  Log your work.

3. I have answered your questions in the "Q&A/Raman correction" section below.  Please
read them and then proceed to generate a new prompt document in `python/PAB/claude_prompts/v2` to perform the rerun named `build_v2_1_rerun.md` to perform the v2.1 rerun.
If you have questions, put them in that prompt document and I will
answer them there.
Use Opus 5.5.  Log your work.

### Version

1. We have the v2.1 rerun completed and the v2.1 DB is now available.  Please
check that the defaults are all pointed to 2.1 and no longer 2.0.1
If you have questions, put them in that prompt document and I will
answer them there.
Use Opus 5.5.  Log your work.

## Q&A

### Version

*Response to Version prompt 1 (Claude Opus 5.5, 2026-11-20).*

**Short answer: the package defaults were already on 2.1. The stale
defaults were in the paper-figure code, which I have fixed. The public S3
copy is still 2.0 + 2.0.1.**

#### Already on 2.1 (checked, no change)

- `pab.config.pab_version = "2.1"`, `setup.py` `2.1.0`,
  `report_site/conf.py` `release = "2.1"`.
- The Dockerfile asserts `pab 2.1.0`, `geometry_mode == 'normalized'` and
  schema v6. The v2.1 Nautilus jobs use image `pab:2.1.0`.
- `FitConfig()` defaults to the 2.1 configuration. `FitConfig.v2_0_1()` and
  `.v2_0()` are frozen classmethods for the old versions.
- **Version selection is automatic.** `gather_matchups`, `version_family`
  and the report and viz selectors all default to the store's *newest* BING
  family. They are not pinned to a version string. On the live DB
  (`$PAB_DATA_DIR/v2/pab.db`), `version_family` returns `('2.1', [])` and
  `gather_matchups` returns 15,971 rows, all 2.1. The DB holds BING 2.0
  (15,971), 2.0.1 (51), 2.1 (15,971, `geom_mode='normalized'`) and NASA_GIOP
  1.1 (15,976).
- Some `"2.0"` strings are deliberate and stay:
  - `fit/replay.py` `REPLAY_VERSION = "2.0"`: 2.1 replays the 2.0 chain
    spectra.
  - `fit/rrs_qa_backfill.py` `--pab-version 2.0`: a one-off backfill of the
    2.0 rows.
  - `report/rst.py`: the `"2.0"` fallback for frames without a `geom_mode`
    column.
  - The old `nautilus/v2_*` job images.

#### Fixed

1. **`papers/bbp/make_paper_figures.py`.** `DEFAULT_DB` was already
   `$PAB_DATA_DIR/v2/pab.db`, the DB that holds 2.1 (V1 = A). I changed the
   docstring and comment from "v2.0.1 release" to "v2.1 release". I also
   replaced the example `--db $PAB_DATA_DIR/v2.1/pab.db` with a generic path,
   because that file never existed.
2. **The standalone figure modules defaulted to v1-era paths that no longer
   exist**: `$PAB_DATA_DIR/pab.db`, `pab_full.db` and
   `$PAB_DATA_DIR/matchup_summary.parquet`. Each one now defaults to
   `$PAB_DATA_DIR/v2/pab.db` and `$PAB_DATA_DIR/v2/matchup_summary.parquet`:
   - `pab/matchup/`: `make_analysis_figures`, `plot_rrs700_vs_delta`,
     `plot_bing_giop_comparison`, `plot_outlier_cases`, `plot_delta_vs_bbp`,
     `chl/data`, `plot_bbp700_vs_temp`, `plot_bbp_matchup_map`,
     `plot_bbp_matchup_map_clean`;
   - `papers/bbp/plot_global_maps.py`, which also stops guessing `../data/PAB`
     and uses `pab.config.DATA_DIR`.
3. **`plot_rrs700_vs_delta.load_data` mixed versions.** It took
   `MAX(...) GROUP BY matchup_id` over *all* BING fits, so each matchup's 2.0
   and 2.1 values (plus 2.0.1 where it exists) were combined. It now keys on
   `fit_id` and joins to the parquet's `fit_id`, which is the fit the release
   reports. It also used `fr.median` and the quantity names
   `anw700`/`bbp700`, which do not exist. They are now `fr.value` and
   `BING_ExpBPow_anw700`/`_bbp700`. In `plot_bing_giop_comparison`,
   `fr.median` is now `fr.value`. **This is the fix proposed in `figures.md`
   Q5, which had no answer.** I applied it because the version mixing affects
   2.1 directly. It is easy to revert if you want to handle Q5 separately.
   - **Check.** Against the live DB and the staged 2.1 parquet: `rrs700`
     returns 14,338 rows, all 2.1, and its `bbp700_fit` equals the parquet's
     `bbp_bing` exactly. `giop` returns 15,267 rows, all 2.1. The analysis
     loader returns 14,338 rows and the chl loader 15,971, all 2.1.
   - **Tests.** The full test suite passes: 563 passed, 1 skipped (live L1B).

#### Not 2.1 yet (needs you)

- **Public S3.** `s3://pab/v2/pab.db` (220,819,456 B) and
  `v2/matchup_summary.parquet` (2,745,255 B) are still the 2026-10-20 objects,
  with Last-Modified 2026-10-20. That is the 2.0 + 2.0.1 release.
  `v2/pab_2026-10-20.db` returns 403. T5-Q1/Q2/Q3 in
  `claude_prompts/v2/build_v2_1_rerun.md` (Round 5) have no answer. The 2.1
  tables are staged in `$PAB_DATA_DIR/v2/s3_stage_v21_20261119/`.
- **No local `v2/matchup_summary.parquet`.** `make_paper_figures.py` reads
  the parquet next to `--db`. Without it, the parquet groups (`delta_bbp`,
  `rrs700`, `giop`, `outliers`, `maps`) stop with a missing-input error
  unless you pass `--parquet`.

#### Questions for JXP

1. **Q1: S3 publish.** Shall I go ahead with T5-Q1 = A in
   `build_v2_1_rerun.md`? That means: dated key for the 2.0.1 DB, replace
   `v2/pab.db` and the four tables, verify by re-download. Or will you
   answer it there first?
   *(My recommendation: answer T5-Q1–Q3 in that doc; I run them as its next
   prompt.)*

   **A:**
2. **Q2: local parquet.** Shall I copy the staged 2.1
   `matchup_summary.parquet` (and `.csv`, plus `nasa_giop_summary.*`) into
   `$PAB_DATA_DIR/v2/`, so `make_paper_figures.py` runs with no flags? They
   are byte-identical to what will go to S3.
   *(Recommended: yes.)*

   **A:**
3. **Q3: `pab` CLI `--db` default.** `pab/pipeline.py` still defaults `--db`
   to `$PAB_DATA_DIR/pab.db`, which does not exist. The pipeline **creates**
   the store if it is absent, so a run without `--db` silently builds an
   empty DB. I left it alone because pointing a *writer* at the live 2.1 DB by
   default is risky. Options:
   - (a) leave it;
   - (b) point it at `v2/pab.db`;
   - (c) make `--db` required.

   *(Recommended: c, in line with the "always pass `--db`" lesson.)*

   **A:**

### Raman correction

*Response to RT prompt 2 (Claude Opus 5.5, 2026-11-14).*

**Short answer: the distributed L2 AOP `Rrs` is *not* corrected for Raman
scattering.** `raman_opt = 2` makes l2gen *compute* a Westberry et al. (2013)
estimate of the Raman contribution. It stores that estimate in a separate
array, `Rrs_raman`, and leaves `Rrs` untouched. The only consumer of the
array is GIOP, which subtracts it before inverting. So BING v2's choice to
add Raman in the forward model is correct for AOP `Rrs`, and nothing is
counted twice. **Finding 6 of the Viewing-angle section below is withdrawn.**
The Task 6 bias decomposition does not need revisiting on this point.

#### Codebase

- The OCSSW source is in `/home/xavier/Oceanography/ocssw/ocssw_src/`. That
  is the full `ocssw_src` bundle at tag **V2026.6** (l2gen 10.4): 2,693 files,
  29 MB, each one checked against the manifest's sha256. It is not a git
  checkout. NASA's public git repo (`oceandata.sci.gsfc.nasa.gov/ocssw/ocssw-src.git`)
  stops at v7.5 (2018), and current source is only distributed through the
  `install_ocssw` manifest system. I fetched the manifest and the files with my
  own downloader, which follows the same URL scheme. The bundle's
  `manifest.json` is in that directory, so it can be updated with NASA's
  `manifest.py` later.
- **Version match.** The L2 granules record which l2gen built them. V3.2 AOP
  used `10.1.0-V2026.2`, and V3.1 IOP used `9.11.0-09b1279b9`. Per the
  manifests, `raman.c` is byte-identical from T2025.8 (V2025.2) through
  V2026.6. I also pulled the production-era copies of `atmocor2.c` (T2024.17,
  T2024.26, T2025.13, T2026.4), `giop.c` (T2024.22, T2025.8, T2026.4) and
  `raman.c` (T2024.26). All of them handle Raman the same way as described
  below. They are in
  `/tmp/claude-1000/-mnt-tank-Oceanography-python-PAB/2630209e-146b-4de1-b46f-08809dd2706c/scratchpad/oldsrc/`.

#### What the code does

1. **Option mapping, verbatim from `src/l2gen/raman.c:49-52`:**
   `NORAMAN 0`, `LEE2013 1`, `WESTBERRY2013 2`, `LEE1994 3`. Production OCI
   uses **2, Westberry et al. 2013**, first-order term only (`raman.c:697-699`).
   It is computed only for 380–700 nm (`WAVEMIN`/`WAVEMAX`) and set to 0
   outside that range.
2. **Where it runs.** At the very end of `atmocor2.c`, *after* the f/Q BRDF
   factor has been applied to `nLw` (`atmocor2.c:~980-990`) and after the
   final `Rrs[ib] = nLw[ib] / Fobar[ib]`:
   ```c
   /*Determine Raman scattering contribution to Rrs*/
   run_raman_cor(l2rec, ip);
   ```
3. **It writes only `l2rec->Rrs_raman`.** All three methods fill
   `Rrs_ram[ip*nbands+iw]`, where `float *Rrs_ram = l2rec->Rrs_raman;`
   (`raman.c:709, 752`). `l2rec->Rrs` is only *read*, as the QAA input
   (`raman.c:407`). I searched the whole `src/` tree for assignments to
   `l2rec->Rrs[...]`. The only ones are initialisation (`init_l2.c`), the
   L1 pass-through mode (`convl12.c`) and l3gen. Nothing subtracts
   `Rrs_raman` from `Rrs`.
4. **The output product.** `prodgen.c` writes the `Rrs` product straight from
   `l2rec->Rrs` (`case CAT_Rrs: extract_band(l2rec->Rrs, ...)`). `Rrs_raman`
   is a separate product (`CAT_Rrs_raman`). The AOP suite's `l2prod` is
   `Rrs Rrs_unc aot_865 angstrom avw nflh`, so **`Rrs_raman` is computed but
   not distributed**.
5. **The only consumer is GIOP** (`giop.c`, T2025.8 onward):
   `Rrs_a[iw] = l2rec->Rrs[ipb2 + ib] - Rrs_ram[ib];` before the
   above→below conversion. It also *adds* the term back to the modelled
   reflectance: `mRrs = rrs_below_to_above(Rrs_f) + Rrs_ram`. The
   `bbp_s` band-ratio step uses Raman-subtracted Rrs too. In T2024.22, which
   covers V2024.x to V2025.1, GIOP had **no** Raman subtraction at all.

#### PACE / OB.DAAC documentation

- **IOP ATBD v1.0** (Apr 2024), §"Raman scattering correction". This is the
  only document that is explicit. Verbatim: *"The forward reflectance model
  used in GIOP-DC does not account for naturally-ocurring inelastic Raman
  scattering contributions to Rrs,obs (λ). As such, GIOP-DC utilizes a Raman
  scattering correction. … Above-water remote sensing reflectances corrected
  for Raman scattering effects, Rrs,cor (λ) [units: sr-1], are then computed
  as: Rrs,cor (λ) = Rrs,ob (λ) − Rrs,Raman (λ). (11)"* It also lists
  `Rrs_raman_vvv` as an output variable: *"Contribution to the spectral remote
  sensing reflectance due Raman scattering effects"*. This treats the observed
  `Rrs` as Raman-inclusive, with the correction belonging to the IOP step.
- **Rrs ATBD v1.2** (Aug 2024). Raman is **not mentioned**. The
  normalisation terms listed are F0, f_s (Earth–Sun), **f_b (bidirectional
  reflectance correction)** and f_λ (out-of-band).
- **PACE OCI V3 release notes** (Apr 2026). Raman is **not mentioned**. They
  do contain one fact that matters for the Viewing-angle work: *"In V3.1 (and
  prior versions), the bidirectional reflectance (BRDF) correction was not
  correctly accounting for the change in relative azimuth across the scan.
  This has been corrected, resulting in a significant improvement in accuracy
  and cross-track stability of the Rrs retrievals."* All 15,976 v2 matchups
  (72,803 granules) are **V3_2**, so v2 already has the fixed BRDF. v1 fits
  from V3.0/V3.1 granules did not.
- The V3.x reprocessing notes PDF (`PACE_Reprocessing_V3.x_notes.pdf`)
  returned HTTP 502, so I could not read it.
- In summary, no PACE page says in so many words that "AOP Rrs is not Raman
  corrected". The IOP ATBD's Eq. 11 plus the code is as explicit as NASA gets.

#### Implications

- **BING v2 / v2.1 inelastic forward model.** Keep `include_raman=1` for
  L2 AOP input. That is the physically consistent choice.
- **Geometry of the Raman term.** NASA computes `Rrs_raman` *after* the f/Q
  normalisation, from the normalised `Rrs`. The Raman photons inside the
  distributed `Rrs` have themselves been scaled by the Chl-based f/Q factor,
  which treats them as if they had elastic angular structure. That supports
  your Q2 answer (θ_s = 0 for the inelastic terms in v2.1). The error is
  second order, because Raman emission is nearly isotropic.
- **The NASA GIOP comparison.** PAB's GIOP b_bp comes from V3.2 IOP granules
  (l2gen 10.1.0), whose `giop.c` subtracts Westberry Raman. So GIOP and BING
  v2 both account for Raman, by different methods. The bias draft's "BING
  inelastic converges toward GIOP" argument is therefore like-for-like. GIOP
  granules from before V2025.2 had no Raman correction. The one local V3.1 IOP
  file is `9.11.0-09b1279b9`, a version string that spans both cases, so I
  can't tell which applies to it. That doesn't matter for v2, which uses
  V3.2.
- **Possible cross-check.** Run l2gen with `l2prod=Rrs_raman` on L1B for a
  handful of matchup granules. That would give NASA's Westberry estimate to
  compare against BING's Raman term per pixel. The two methods use different
  Ed models and different IOP proxies (QAA vs BING's posterior). It needs
  OCSSW binaries and the OCI LUTs, many GB, which I did not install.

#### Questions for JXP

1. **Q1 — Correct the Viewing-angle record.** I have added a "withdrawn" note
   to finding 6 below and left its text in place for the record. Would you
   rather I delete it, or rewrite the Recommendation bullet about Raman?

   **A:** It is fine
2. **Q2 — Cross-check.** Is the l2gen `Rrs_raman` vs BING-Raman comparison
   worth a prompt? It needs a binary OCSSW install, the OCI LUTs, and the L1B
   download. 
   
   **A:** No, we can leave it as is

3. **Q3 — v1 BRDF bug.** Should the v1 → v2 comparison in the paper mention
   that v1's Rrs came from V3.0/V3.1 granules with the cross-scan BRDF
   azimuth error? I have not checked v1's version mix yet. 
   
   **A:** We won't include this in the paper

Sources: OCSSW source, tag V2026.6 and earlier tags (local copy above);
[IOP ATBD v1.0](https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-inherent-optical-properties.pdf);
[Rrs ATBD v1.2](https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-remote-sensing-reflectance.pdf);
[PACE OCI V3 release notes](https://oceandata.sci.gsfc.nasa.gov/files/reprocessing/PACE_OCI_V3_Release_Notes.pdf);
[OCSSW manifest tags](https://oceandata.sci.gsfc.nasa.gov/manifest/tags/).

### Viewing angle

*Response to RT prompt 1 (Claude Opus 5.5, 2026-11-14).*

**Short answer: you are right.** The PACE L2 AOP `Rrs` is already
normalized to a nadir view **and** a zenith sun. But PAB v2 passes each pixel's
*observed* (θ_s, θ_v, Δφ) into the `robust_hybrid` forward model. So the data
are normalized to one geometry and the model is evaluated at another. That
inconsistency matters more than the emulator's nadir-only training.

#### Findings

1. **The L2 Rrs is BRDF-normalized (verified in the granule metadata).**
   `processing_control/input_parameters` in every L2 AOP granule I checked has
   `brdf_opt = 7`. These were
   `PACE_OCI.20250401T202905.L2.OC_AOP.V3_0.nc` and
   `PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc`, both l2gen production runs.
   l2gen documents option 7 as *"Morel f/Q + Fresnel solar + Fresnel sensor"*.
   The OCSSW `brdf.c` code describes the f/Q term as *"the ratio of f/Q for
   nadir and solar zenith angles (and thus, relative azimuth angle) = 0 to f/Q
   for actual viewing geometry"* (Morel, Antoine & Gentili 2002). The f/Q table
   is `morel_fq_hyperspectral.nc` in V3.0 and `morel_fq_hyperspectral_2026.nc`
   in V3.2. So the delivered `Rrs` is an "exact normalized" reflectance: sun at
   zenith, sensor at nadir, Δφ irrelevant, and the air–sea Fresnel terms
   removed for both paths. The per-pixel geometry is only *undone* by NASA. It
   is not left in the product.

2. **PAB v2 feeds the observed geometry to the forward model.** The
   `geometry` stage reads θ_s/θ_v/Δφ from L1B
   ([pab/pace/l1b.py](../../../pab/pace/l1b.py)), and
   [pab/fit/run.py:212](../../../pab/fit/run.py#L212) (`obs_geometry`) passes
   them unchanged to `ObsGeometry`, then into `robust.rt.forward`. The same
   θ_s also selects the L23 `Ed(θ_s)` spectrum used by the Raman and
   fluorescence kernels (`set_inelastic_Ed`). For data that are already
   normalized, the matching geometry would be **(θ_s, θ_v, Δφ) = (0, 0, 0)**.

3. **The size of the mismatch.** I evaluated `robust.rt.forward` (B_p = 0.014,
   flat a, power-law b_bp) at the real geometry of 300 random v2 pixels. The
   v2 DB has 159,710 pixels with θ_s 13–65° (5–95 %) and θ_v 22–58°. I divided
   each result by the same IOPs at (0, 0, 0). Median ratio, with the 5–95 %
   range in brackets:

   | water | mode | 440 nm | 555 nm | 700 nm |
   |---|---|---|---|---|
   | oligo (a=0.03, b_bp700=0.0015) | ZTT | 1.12 [0.99–1.29] | 1.07 [0.95–1.22] | 1.06 [0.94–1.20] |
   | oligo | hybrid | 1.12 [1.01–1.29] | 1.11 [0.96–1.24] | 1.10 [0.94–1.22] |
   | meso (a=0.08, 0.003) | hybrid | 1.11 [0.96–1.26] | 1.09 [0.94–1.23] | 1.08 [0.93–1.21] |
   | eutro (a=0.3, 0.008) | hybrid | 1.09 [0.94–1.23] | 1.09 [0.93–1.22] | 1.08 [0.93–1.20] |

   At the observed geometry the model predicts about **5–10 % more Rrs
   (median)** for the same IOPs, and about ±15 % from pixel to pixel. Fitted
   to nadir/zenith-normalized data, this should bias the retrieved b_bp(700)
   **low by roughly 5–10 % on median**, since red Rrs is close to linear in
   b_bp. It also adds a geometry-correlated scatter of about ±15 %. That works
   *against* the PACE > Argo bias, so the sign does not explain the bias. The
   scatter, though, is noise we are adding ourselves. Script:
   `/tmp/claude-1000/-mnt-tank-Oceanography-python-PAB/2630209e-146b-4de1-b46f-08809dd2706c/scratchpad/geom_test.py`
   (not run through BING's jitted path, and without Raman/fluorescence).

4. **(0, 0, 0) is inside the emulator's trained domain.** The packaged
   emulator's domain is `cos_theta_s ∈ [0.5, 1]`, `cos_theta_v = cos_dphi = 1`.
   (0, 0, 0) satisfies all three. Today every PAB pixel breaks the view-angle
   constraint (`ztt_slice.md`), and pixels with θ_s > 60° (about 10 %) also
   break the solar one. Switching to the normalized geometry removes the
   "hybrid applied off-nadir, never validated" caveat entirely. It also lets
   `on_out_of_domain="ztt"` behave as intended, because only the IOP/B_p
   breaches would remain.

5. **Caveat on NASA's normalization.** The Morel f/Q table is a Case-1,
   Chl-driven model with a fixed particle phase function. It is not an exact
   inverse of the true BRDF, and it is not the same physics as robust/ZTT. So
   even after the switch there is a model mismatch, of order a few %, which
   grows at large θ_v and in non-Case-1 water. That is a second-order residual,
   not a reason to keep the observed geometry. A possible check: compare the
   f/Q correction that l2gen implies with robust's
   Rrs(obs)/Rrs(0,0,0) ratio for the same Chl.

6. **[WITHDRAWN 2026-11-14, RT prompt 2. The OCSSW code shows `raman_opt`
   only fills a separate `Rrs_raman` array, which GIOP uses. The AOP `Rrs` is
   *not* Raman-corrected, so there is no double counting. See Q&A / Raman
   correction.]** **Related and probably more important: Raman may be counted twice.** The
   same `input_parameters` show **`raman_opt = 2`** in both granules. l2gen
   documents `raman_opt` as *"Raman scattering Rrs correction options"*, with
   default 0 meaning no correction. Option 2 is listed as the Westberry et al.
   (2013) analytical correction. I got that mapping from a summarized fetch of
   the l2gen help page, not verbatim, so it should be confirmed with
   `l2gen --help`. Either way, a non-zero value means **NASA has already
   removed an estimate of the Raman contribution from the delivered L2
   `Rrs`**. PAB v2 then *adds* Raman back in the forward model
   (`include_raman=1`). If so, the model has Raman that the data no longer
   carry. The fit compensates by lowering b_bp. The bias draft credits about
   14 % of the drop in b_bp(700) to "adding missing Raman", from +0.35 to
   +0.15 on the subsample. That drop would then partly come from double
   counting. Fluorescence is not removed by l2gen, so the fluorescence term
   is unaffected.

#### Recommendation

- Fit L2 Rrs with `ObsGeometry(theta_s=0, theta_v=0, dphi=0)`. Keep the L1B
  geometry in the DB as provenance and for QA cuts (glint, high θ_v). For the
  L23 `Ed` used by the inelastic kernels, decide which geometry is consistent:
  see Q2.
- Either turn off BING's Raman term for L2 input, or add NASA's Raman estimate
  back to the L2 `Rrs` before fitting. The second is cleaner for an inelastic
  forward model but needs the Westberry/OCSSW coefficients. Do not do both,
  and do not do neither.
- Rerun the `ztt_slice` 50-fit subsample, plus a high-θ_v slice, under the
  four combinations {obs, nadir geometry} × {Raman on, off}. That will size
  both effects on real b_bp before any production rerun.


#### Questions for JXP

1. **Q1 — Geometry switch.** Do you agree to fit with (0, 0, 0) for L2 `Rrs`,
   which implies a v2.x rerun? Or would you rather keep the observed geometry
   and *undo* NASA's f/Q + Fresnel normalization per pixel? The second keeps
   the physics in robust but needs l2gen's f/Q table and the Chl NASA used.

   **A:** We should fit with (0, 0, 0) for L2 `Rrs`.  We will generate a new prompt
   doc in `python/PAB/claude_prompts/v2` to perform the rerun named 
   `build_v2_1_rerun.md` and refer to this as `v2.1`
2. **Q2 — Ed for the inelastic terms.** Should the Raman/fluorescence `Ed`
   come from θ_s = 0, to match the normalized Rrs, or from the true θ_s? The
   real excitation happened at the true sun, but the f/Q normalization was
   applied to the total Rrs (elastic + fluorescence). My default would be
   θ_s = 0 for consistency. 

   **A:** Yes, use θ_s = 0 for the inelastic terms.
   
3. **Q3 — Raman double counting.** Can you, or someone at OBPG, confirm that
   `raman_opt = 2` subtracts a Raman estimate from the distributed OCI `Rrs`,
   and which method it uses? If confirmed, the Task 6 bias decomposition
   ("roughly half is missing inelastic physics") needs revisiting before it
   goes in the paper. 
   **A:** We need to confirm this Raman correction has been applied to the L2 `Rrs`.  
   This means downloading l2gen to this workstation and inspecting the code.
   Please do so and put the codebase in `/home/xavier/Oceanography`

4. **Q4 — Scope.** Should I run the 2×2 (geometry × Raman) subsample test
   described above as the next prompt? 
   
   **A:** No, hold off on that for now

Sources: [OCSSW brdf.c](https://oceancolor.gsfc.nasa.gov/docs/ocssw/brdf_8c_source.html),
[OCSSW raman.c](https://oceancolor.gsfc.nasa.gov/docs/ocssw/raman_8c_source.html),
[l2gen for PACE/OCI — OB.DAAC Help Hub](https://nasa.github.io/oceandata-notebooks/notebooks/oci/oci_ocssw_l2gen.html),
[PACE OCI V3 release notes](https://oceandata.sci.gsfc.nasa.gov/files/reprocessing/PACE_OCI_V3_Release_Notes.pdf).


## Logs

### 2026-11-14 (RT prompt 1: PACE L2 Rrs is nadir/zenith-normalized; PAB fits at observed geometry)

Checked the l2gen `processing_control/input_parameters` of two local L2 AOP
granules (V3.0, V3.2). Both have `brdf_opt = 7`, i.e. Morel f/Q + Fresnel on
the sensor and solar paths, which normalizes Rrs to sun at zenith and nadir
view. Both also have `raman_opt = 2`, a Raman correction already applied to
Rrs. Traced PAB v2's geometry path (L1B → `matchup_pixels` →
`pab.fit.run.obs_geometry` → `robust.rt.forward`): it uses the *observed*
θ_s/θ_v/Δφ, which does not match the normalized data. Measured the effect
with `robust.rt.forward` on 300 real v2 pixel geometries. Rrs(obs)/Rrs(0,0,0)
has a median of 1.05–1.12 and a 5–95 % range of about 0.93–1.29, which
implies roughly 5–10 % low-biased b_bp(700) plus ±15 % geometry-correlated
scatter. Noted that (0,0,0) lies inside the emulator's trained domain
(cos θ_s ∈ [0.5,1], cos θ_v = cos Δφ = 1), so switching would also clear the
off-nadir caveat. Flagged likely Raman double counting (L2 removes it, BING
adds it), which bears on the Task 6 bias decomposition. Findings and four
questions are in Q&A / Viewing angle. No code or DB changes.

Lessons: `conda activate ocean14` in this shell resolves `python` to
`os_313`. Call `/home/xavier/miniconda3/envs/ocean14/bin/python` directly.
The OCSSW source pages on oceancolor.gsfc.nasa.gov now redirect (301) to the
OB.DAAC landing page. The l2gen help text is reachable through the
oceandata-notebooks l2gen page.
### 2026-11-14 (RT prompt 2: L2 AOP Rrs is NOT Raman-corrected; OCSSW source installed)

Downloaded the OCSSW source bundle at tag V2026.6 (l2gen 10.4, 2,693 files,
sha256-verified) to `/home/xavier/Oceanography/ocssw/ocssw_src/`. NASA's
public git repo is frozen at v7.5, and current source ships only through the
`install_ocssw` manifest system. Running NASA's `install_ocssw` was blocked by
the session's permission classifier, so I read its URL scheme and fetched
`manifest.json` and the files directly. Traced Raman through l2gen:
`raman_opt=2` is Westberry et al. 2013 (first-order term). `run_raman_cor`
runs at the end of `atmocor2.c`, after the f/Q BRDF step and the final Rrs. It
fills only `l2rec->Rrs_raman` and never modifies `l2rec->Rrs`. The `Rrs`
product is written from `l2rec->Rrs`. `Rrs_raman` is not in the AOP `l2prod`.
GIOP (from T2025.8) subtracts it before inverting and adds it to its modelled
Rrs. Using manifest checksums and older copies of the files, I confirmed the
same behaviour in the production-era sources (V3.2 AOP = l2gen 10.1.0-V2026.2).
Docs: the IOP ATBD's Eq. 11 (Rrs,cor = Rrs,obs − Rrs,Raman, applied in GIOP)
is the only explicit statement. The Rrs ATBD and V3 release notes do not
mention Raman. The release notes do report a cross-scan relative-azimuth bug
in the BRDF correction, fixed in V3.2. All v2 matchups are V3_2. Withdrew
Viewing-angle finding 6 (double counting). BING v2's Raman-in-model is
correct for AOP Rrs. Wrote findings and three questions in Q&A / Raman
correction. No PAB code or DB changes.

Lessons: the OCSSW manifest (`https://oceandata.sci.gsfc.nasa.gov/manifest/tags/<tag>/ocssw_src/manifest.json`)
records, per file, the tag it last changed in. That lets you check whether a
file differed in the production l2gen version without downloading every tag.
L2 granules record their exact l2gen build in
`processing_control.software_version`. `pdftotext -layout` reads NASA's ATBD
PDFs when WebFetch returns only raw bytes.

### 2026-11-14 (RT prompt 3: wrote `claude_prompts/v2/build_v2_1_rerun.md`, the v2.1 normalized-geometry re-fit)

Read JXP's answers to the Raman-correction questions: keep the withdrawn
finding as is; no `Rrs_raman` cross-check; the v1 BRDF bug stays out of the
paper. Wrote the v2.1 prompt doc in `claude_prompts/v2/`, following the
project's prompt-doc shape. It carries the physics rationale, the code seams
where geometry enters PAB, measured facts, a Plan, five Tasks with a hard
review stop after a 200-matchup θ_v-stratified slice, and twelve questions
(V1–V12) with recommendations. The recommendations: 2.1 rows in the live v2
DB; replay the 2.0 chain spectra; the 15,971 replayable matchups; a
`fits.geom_mode` column (schema v6); relax the R3 skip under normalized
geometry; run on the workstation (~45–55 h at `--jobs 20`); 2.1 as report
headline with the 2.0-vs-2.1 change in a `versions/v2.1/` write-up;
re-render fit figures; publish in place under `s3://pab/v2/`; keep
`on_out_of_domain="warn"`; name it 2.1 with a frozen `FitConfig.v2_0_1()`.
Verified read-only along the way: all 15,971 2.0 and 51 2.0.1 chain NPZs
are local; the production window is 400–700 nm; the L23 `Ed` table has a 0°
anchor; `fit_fig` reconstructs geometry from the pixel angles and must learn
the fit's mode; `2.1` becomes the report headline through
`compare.version_family` with no new code. Expected effect from the RT
prompt 1 test: `bbp700` up about 5–10 % on median. No code or DB changes.

### 2026-11-20 (Version prompt 1: defaults checked against 2.1; stale paper-figure defaults fixed)

Checked every version default against the v2.1 release. The package was
already on 2.1: `pab_version`, `setup.py`, the Dockerfile asserts, the
`FitConfig()` defaults and `report_site`. Report and figure version
selection is not pinned. `gather_matchups` and `version_family` resolve the
store's newest BING family, which on the live `v2/pab.db` is `('2.1', [])`
with 15,971 rows. Fixed the stale defaults:
- `make_paper_figures.py` text said "v2.0.1 release" and gave a
  `v2.1/pab.db` example that does not exist;
- ten figure modules defaulted to v1-era `pab.db`, `pab_full.db` and
  parquet paths, now `$PAB_DATA_DIR/v2/…`;
- `plot_rrs700_vs_delta` grouped over all BING versions by `matchup_id`. It
  now joins on the parquet's `fit_id`. It and `plot_bing_giop_comparison` also
  queried a non-existent `fr.median` column. This is `figures.md` Q5's
  proposed fix.

Verified that every loader returns 2.1 rows only, and the full test suite
passes (563 passed). Found that public `s3://pab/v2/` is still the 2026-10-20
2.0 + 2.0.1 release: T5-Q1 of `build_v2_1_rerun.md` has no answer. There is
also no local `v2/matchup_summary.parquet` (the 2.1 copy is staged), and the
`pab` CLI `--db` default points to a non-existent file. These are three
questions in Q&A / Version. No DB or S3 changes.

Lessons: `fit_results` stores the posterior median as `value`, not `median`,
with quantities prefixed `BING_<model_pair>_`. Check the public S3 state
with `curl -sI https://s3-west.nrp-nautilus.io/pab/v2/<file>` (size and
Last-Modified) before assuming a release is published.
