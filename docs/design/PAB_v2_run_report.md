# PAB v2 Run Report — the inelastic re-analysis

**`pab_version = 2.0` — re-analysis of the full PACE-mission matchup set with an
inelastic radiative-transfer forward model, executed on NSF/Nautilus. Completed
2026-10-05.**

This document is the factual record of the 2.0 run: what changed, what was
processed, what the results are, what broke along the way, and where the data
lives. It is the 2.0 counterpart of
[`PAB_full_run_report.md`](PAB_full_run_report.md) (the 1.0 run).

---

## 1. Summary

The 1.0 run fitted every matchup with the **elastic** Gordon radiative-transfer
model: `Rrs` is produced by absorption and elastic scattering alone. 2.0 re-fits
the same spectra with an **inelastic** forward model, and re-runs the matchup
discovery over an extended mission window.

### What changed

| | 1.0 | 2.0 |
|---|---|---|
| RT backend | `gordon` (analytic) | **`robust_hybrid`** (neural-network emulator of a full RT solution) |
| Raman scattering | — | **included** |
| Chlorophyll fluorescence | — | **included**, quantum yield `phi_C = 0.02` |
| CDOM fluorescence | — | available, **off in this run** |
| Phase-function `B_p` | fixed | **free**, 6th fitted parameter, uniform prior `[0.004, 0.05]` |
| Viewing geometry | not used | **required** — new `geometry` stage reads `theta_s`/`theta_v`/`dphi` from L1B |
| Fit window | 400–700 nm | 400–700 nm (**unchanged**) |
| Schema | v4 | **v5** |

The fit window did **not** change. The red edge (713/719 nm), where Raman and
fluorescence are strongest and where a longer window was originally planned,
was evaluated and deliberately excluded: on a 97-matchup diagnostic sample
`Rrs(719)` is negative or noise-dominated on **44 %** of matchups, so including
it would feed the inelastic terms mostly noise. CDOM fluorescence was likewise
planned and left off. Both are stated as such throughout the reporting rather
than listed as improvements.

### Headline numbers

| Quantity | Value |
|---|---|
| BGC-Argo floats | 912 |
| Profiles ingested | 59,620 |
| PACE granules discovered | 72,803 |
| Matchups | 15,976 |
| Matchup pixels | 159,760 (10 per matchup) |
| — with viewing geometry | 159,710 (50 missing = 5 whole matchups) |
| BING 2.0 fits | **15,971** (99.97 % of matchups) |
| NASA-GIOP baseline rows | 15,976 (14,609 carried + 1,367 new), stamped `1.1` |
| Fit results | 303,489 (175,681 BING + 127,808 NASA) |
| Quantities per BING fit | **11** (`…_Bp` added in 2.0) |
| Fit figures / scenes | 15,971 / 15,976 |
| MCMC chain archive | **18.3 GB** (15,971 objects) |
| Profile time range | 2024-03-05 → 2026-09-17 |
| Matchup rate | 26.8 % of ingested profiles |

The 5 matchups without a fit are the 5 with **no L1B viewing geometry at all**
(all 10 pixels each). R3 refuses to fit a spectrum without geometry rather than
silently defaulting `theta_s`, so these are a designed refusal, not a failure:
**15,971 fits + 5 refused = 15,976 matchups**, exactly.

---

## 2. Results

### 2.1 Against the floats — the question the run exists to answer

Paired subset (same matchup, same pixel, fitted in both versions; n = 14,604):

| | n | sat/float ratio | Spearman ρ | log bias | log RMS |
|---|---|---|---|---|---|
| `b_bp`(700) 1.0 | 13,965 | 1.561 | 0.498 | **+0.169** | 0.371 |
| `b_bp`(700) 2.0 | 13,965 | **1.145** | 0.426 | **+0.013** | 0.643 |
| Chl 1.0 | 13,834 | 0.782 | 0.523 | −0.287 | 0.856 |
| Chl 2.0 | 13,834 | **0.939** | **0.734** | **−0.092** | **0.586** |

**Chlorophyll improves on every axis**: bias cut 3×, rank correlation
0.52 → 0.73, scatter 0.86 → 0.59.

**Backscatter removes nearly all of a +17 % log bias** (ratio 1.56 → 1.15,
bias +0.169 → +0.013) while the scatter doubles (RMS 0.371 → 0.643). That reads
as a trade until the ill-conditioned clear-water regime is excluded:

| Chl > 0.05 mg m⁻³ (n = 12,502) | sat/float | ρ | log bias | log RMS |
|---|---|---|---|---|
| `b_bp` 1.0 | 1.563 | 0.522 | +0.184 | 0.337 |
| `b_bp` 2.0 | **1.152** | 0.442 | **+0.032** | **0.383** |

Outside clear water **2.0 removes ~6/7 of the bias for almost no cost in
scatter** (0.337 → 0.383). The apparent doubling of RMS over the full
population is almost entirely the ultra-oligotrophic tail.

**One caveat not explained by that tail:** rank correlation falls even in
productive water (0.522 → 0.442). Bias and spread improve; ordering does not.
This is unexplained and is carried to the follow-ups.

### 2.2 1.0 vs 2.0 — attribution

| | n | 2.0/1.0 | ρ | log offset | log RMS |
|---|---|---|---|---|---|
| `b_bp`(700) | 14,604 | **0.750** | 0.924 | −0.157 | 0.536 |
| Chl | 14,604 | **1.165** | 0.704 | +0.191 | 0.644 |

2.0 retrieves ~25 % less backscatter and ~17 % more chlorophyll. **The shift is
not uniform** — by tercile of the 1.0 `b_bp` the ratio runs 0.66 / 0.74 / 0.81,
and below `b_bp` = 2e-4 m⁻¹ it is ~0.02, i.e. fifty times less.

**This is the expected behaviour of the physics.** Raman and chlorophyll
fluorescence contribute a roughly fixed radiance; what varies is how much
*elastic* signal sits underneath. In clear water the elastic contribution is
small, the inelastic terms are a large fraction of `Rrs`, and the 1.0 model —
having no inelastic terms — could only explain that radiance by inventing
particulate backscatter. 2.0 attributes it to the processes that produce it.
In productive water the elastic signal dominates and the two versions converge.

The headline ratio is a population median and **not** a correction factor for a
single retrieval.

### 2.3 NASA-GIOP baseline

| | n | ratio | ρ | log bias | log RMS |
|---|---|---|---|---|---|
| NASA `b_bp`(442) / BING(700) 2.0 | 15,964 | 2.154 | 0.874 | +0.359 | 0.648 |

The wavelengths differ **by design** and no spectral adjustment is applied; a
ratio above 1 is expected from the blue-to-red decrease of particulate
backscatter. Read it as a consistency check, not a validation. NASA rows are
the same product read by the same code as in 1.0 and are stamped `1.1`, not
re-stamped `2.0` — a re-stamp would imply a re-analysis that did not happen
(R6).

### 2.4 Free `B_p`

`B_p` was fixed in 1.0 and fitted in 2.0. The posterior medians are **bimodal
with mass against both bounds** of the uniform `[0.004, 0.05]` prior: 2.8 %
within 1 % of a bound, 7.1 % within 2 %, 15.4 % within 5 %; the 1st percentile
sits at the floor and the 99th at the ceiling, median 0.0236. For those fits
the **bound, not the spectrum, sets `B_p`**, so the distribution should be read
as censored at both ends. The bounds are physically motivated and were kept.

### 2.5 Non-physical retrievals

**51 of 15,971 2.0 fits (0.32 %)** return `b_bp`(700) above 1 m⁻¹ — impossible
for seawater — the largest 9.3×10⁴ m⁻¹. The same matchups fitted in 1.0 produce
**zero** such values (v1 maximum 0.0337 m⁻¹), so they are specific to the 2.0
configuration.

They are **not** a node, granule or sampler artifact: 47 distinct granules,
every convergence flag set, identical `nsteps`/`nwalkers`, and viewing
geometry, separation and spectrum count indistinguishable from the rest.

*Corrected 2026-10-18.* As written on 2026-10-07 this section went on to call
them "the extreme tail of the same clear-water behaviour as §2.2", on the
strength of a table of failure rate by **retrieved** Chl (2.8–9.6 % below
Chl 0.02 mg m⁻³, zero between 0.05 and 0.3). That reading rested on the
retrieved Chl of ~0.01 mg m⁻³ — which is part of the failed fit — and the
investigation in [`versions/v2/high_bbp_outliers.md`](../../versions/v2/high_bbp_outliers.md)
(Outliers 1; Q&A/Outliers 4 = A) overturned it, so the table was retired from
this report and from the Comparisons page (O3). What the 51 actually are:

- **Productive marginal seas, not clear water.** 25 in the Baltic, 9 in the
  tropical Atlantic/Caribbean, 7 in the Arabian Sea/Gulf of Oman, singles in
  the Black, Ligurian, Barents and Labrador Seas, the Kuroshio, the NE Pacific
  coast, the California Current and the Agulhas. The floats under them have a
  median Chl of **0.93 mg m⁻³** (population 0.15) and a median `b_bp`(700) of
  **3.6×10⁻³ m⁻¹** (population 6.9×10⁻⁴). Three floats account for 25 of them.
- **Depressed or negative blue `Rrs`.** 40 of the 51 have `Rrs` < 0 at
  400–450 nm (a failed atmospheric correction, typically at a cloud edge; none
  carries a standard-mask `l2_flags` bit); the other 11, all Baltic, are
  positive everywhere but have Rrs(440)/Rrs(555) of 0.24–0.55 against a
  population median of 4.1 — CDOM-rich, green-peaked water. All 51 peak at
  490–580 nm.
- **The optimiser, not the sampler or the data.** Every one of the 51 chains
  *started* with `Bnw` (log₁₀ `b_bp`(600)) above 4.5: the LM warm-start
  delivered the 1 % walker ball to `expb_pow`'s `Bnw` prior ceiling of
  10⁵ m⁻¹, where `b_b ≫ a`, the reflectance saturates and only `a/b_b` is
  constrained (`Bnw`–`A_dg` correlation +0.9), and a χ² wall of 10²–10⁵ at
  `b_bp` ≈ 1–10 m⁻¹ kept it there. A physical basin with a **better** χ²
  (1.5–23× lower) and a `b_bp`(700) within ~2× of the float and of the 1.0
  Gordon fit exists in every re-fitted case. Masking the negative bands does
  not remove the spurious basin; the depressed-blue *shape* creates it.

**What the report does with them (O3, 2026-10-18).** They are optimiser
failures, not measurements, so they are **excluded** from every `b_bp`
statistic and figure behind the `compare.BBP_IMPLAUSIBLE = 1 m⁻¹` gate
(`compare.gate_bbp`; the 52nd-largest 2.0 value is 0.03 m⁻¹, so the gate
sits in a six-decade gap), with the computed count in every caption and a
Methods paragraph; the Chl of the same fits is not gated (Q&A/Outliers 6 = A),
the gallery keeps its runaway example, and the downloadable table keeps the
raw values with a `bbp_bing_implausible` flag. The acceptance run on this
database: the `b_bp` headline went from n = 15,274, median ratio 1.15,
ρ = 0.415, RMS 0.645 to **n = 15,224, 1.14, 0.411, RMS 0.492** (50 of the 51
have a float value); NASA/BING RMS 0.52 → 0.29; 2.0/1.0 RMS 0.536 → 0.325.
A re-fit of the 51 under `pab_version` 2.0.1 with physical prior ceilings is
the next step (O5–O7); a per-fit count of negative 400–450 nm bands is stored
as a QA quantity (O4) rather than used to refuse fits — that screen catches
40 of 51 at ≈ 0.7 % false positives, but no spectral screen separates the 11
Baltic cases from good Baltic fits. Still true from the 2026-10-07 reading:
no *post-hoc* single-variable filter isolates them (χ² > 1.5 catches 47/51
but flags 700 sound fits; Chl < 0.05 catches 48/51 and flags 1,636).

---

## 3. Timings by stage

| stage | wall-clock | notes |
|---|---|---|
| `ingest` (backfill) | ~17 h | 5,662 new profiles at ~11 s/profile — 5× the planned 2.1 s |
| `discover` | — | folded into the match sweeps |
| `match` | **13 h 32 m** | 2026-09-25 15:04 → 09-26 04:36 UTC |
| `geometry` | **~20.9 h** | projected at 47 h; see §4 |
| `fit` | **~35 h** | 50 workers, 15,872 attempted |
| NASA-GIOP | ~1.5 h | 1,367 new rows at ~4 s each |
| `figure` | **4.12 h** | 16 workers, 15,971 fit figures + 1,390 scenes, 0 failures |
| `report` (in-pod) | **7.09 h** | almost all of it a bug — see §4 |
| `report` (after fix) | **8.8 s** | the same work on the workstation |

### The slice gates (Prompt 6)

Before committing to the full ~35 h fit, a 100-matchup slice was run against
pre-agreed gates:

| gate | threshold | measured | verdict |
|---|---|---|---|
| median s/fit | > 240 s → pause | **164 s** | clear |
| `b_bp` shift | JXP's judgement | **0.7375**, reproducing Prompt 3's 0.741 at 5× the sample | proceed |

The naive total-wall ÷ fits figure was 385 s/fit, which would have tripped the
pause trigger. The gap was a one-time ~11 min JAX compile per worker pool,
amortised over only ~3 fits per worker in the slice. `build_fits` now logs
startup cost separately so this cannot be misread again. At n = 14,604 the
final `b_bp` ratio was **0.750** — the small-slice number held.

---

## 4. What broke, and what it taught

**`geometry` was projected at 47 h and ran in ~20.9 h.** Splitting the
per-granule cost showed CMR lookup was ~1 % and the L1B open 4.7–7.4 s from the
workstation. Probing nodes found **one California worker beat an entire
8-worker South Dakota pod by 1.8×** — the data are in AWS `us-west-2`. Pinning
to California nodes gave 3.2 s/granule. Per-node rates: Fresno 3.2–4.6, SDSC
4.9–6.5, calit2 5.8–6.4, Humboldt 8.5–8.9, South Dakota 13.7 s/granule.
Humboldt gave 7.7 s with *one* worker and 8.5 with eight — bandwidth-limited,
like South Dakota. "Pin to Fresno-class nodes" would be better than "pin to
California".

**SQLite on CephFS wedges pods.** Four pods in the 1.0 run hung uninterruptibly
(state D) from Ceph MDS thrash; 12+ min on CephFS vs 0.6 s on a local copy.
Every 2.0 job copies the DB to an `emptyDir`, runs there, and checkpoints back
every 2 min via a local `sqlite3.backup()` plus a file copy. Never
`sqlite3.backup()` onto CephFS.

**The `report` stage took 7.09 h — longer than the entire figure stage — and
that was a bug.** The N-guards (`MAX_INLINE_FIGURES`,
`MAX_INTERACTIVE_MATCHUPS`) suppress the gallery *HTML*, but `_stage_static`
had already **copied every figure**: the site staged ~17,000 PNGs, **1.3 GB**,
to display none of them, at 2.8 files/s on CephFS. The guard protected the
cheap half of the operation. Staging now happens inside the gallery, after the
N-check; the same work takes 8.8 s and produces a 1.1 MB site.

**Half the figure stage would have been guaranteed failures.** `figure`
iterated every row of `fits`, and 15,976 of 31,947 are NASA-GIOP ingests with
no MCMC chains — a fit figure for one cannot succeed. A second guard renders
only BING fits of the target `pab_version`. A third renders scenes **only where
`scene_path` is NULL**, since 14,586 matchups already had one and the scene is
the half that re-opens the ~1.8 GB granule.

**NASA-GIOP rows were briefly stamped `2.0`.** The driver used
`config.pab_version` instead of the product's own version. 1,367 rows were
corrected and a `PRODUCT_VERSION` constant added. An existing test had been
*holding the bug in place* by asserting against the same wrong source.

**14,586 `scene_path` values were dangling pointers.** They pointed at
`/data/full/pipeline/figures/`, a PVC directory renamed `full` → `v1` during
the version split; the column was never updated. Nothing was visibly broken —
the gallery is suppressed at this scale and `_stage_static` tests `is_file()`
and skips silently — which is exactly why a 91 %-dangling column survived. The
files were intact at `/data/v1/pipeline/figures/`; all 14,586 remapped paths
were verified to resolve before the column was repaired. Found only because the
verification spot-check checked **files**, not columns.

**Image/manifest mismatches, twice.** A job was launched naming `:2.0.3` forty
seconds after `:2.0.4` was verified — verifying the image is not verifying the
manifest. The figure job's manifest now **asserts on its own source** at
startup, greping `pipeline.figure` for the guards and exiting 1 if absent, so a
stale image cannot run the expensive wrong version.

---

## 5. Data integrity and verification

All gates pass on the published database:

| gate | result |
|---|---|
| `PRAGMA integrity_check` | ok |
| `PRAGMA foreign_key_check` | 0 violations |
| `PRAGMA user_version` | 5 |
| all 15,971 BING fits `pab_version='2.0'` | pass |
| `rt_backend='robust_hybrid'` | pass |
| `include_raman=1`, `include_chl_fl=1`, `include_cdom_fl=0`, `fit_bp=1` | pass |
| `wave_min=400.0`, `wave_max=700.0` | pass |
| no BING fit on a pixel without geometry (R3) | pass |
| fits + refused == matchups | 15,971 + 5 = 15,976 |
| NASA rows all stamped `1.1` | pass |
| no duplicate `fit_id` | pass |
| 11 quantities on every BING fit | pass |
| every BING fit has `chains_path` + `figure_path` | pass |
| every matchup has a resolving `scene_path` | 15,976 checked, 0 missing |
| no NASA row has a figure | pass |

**v1 is byte-identical to its frozen state** across three independent copies —
the recorded value, the workstation file (`-r--r--r--`), and the S3 object
downloaded from the public URL and re-hashed:
`09de0a6d334dc02e73494b198567a37707e1942e5cfd1173c89822b35f978273`,
169,938,944 bytes.

---

## 6. Where the data lives

| artifact | location | size | sha256 |
|---|---|---|---|
| v2 database | `https://s3-west.nrp-nautilus.io/pab/v2/pab.db` | 217,325,568 | `1e69f6ee…87d8a3f8` |
| matchup summary (CSV) | `…/pab/v2/matchup_summary.csv` | 6,102,869 | `6622a78c…070f0f74` |
| matchup summary (Parquet) | `…/pab/v2/matchup_summary.parquet` | 2,645,441 | `4754e237…fe9c0627c` |
| v1 database (frozen) | `…/pab/v1/pab.db` | 169,938,944 | `09de0a6d…f978273` |
| v2 database (backup) | `AIOcean:PAB/pab_v2_2026-10-07.db` | 217,325,568 | — |
| v2 chains | `AIOcean:PAB/v2/fit_chains/` | 18.3 GB, 15,971 files | — |
| v2 figures | `AIOcean:PAB/v2/figures/` | 1,022 MB, 17,361 files | — |
| v2 site | `AIOcean:PAB/v2/site/` | 1.1 MB | — |
| chains + figures (live) | Nautilus PVC `pab-data`, `/data/v2/` | — | — |

The published objects were each re-downloaded from the public URL and
sha256-verified, not trusted from a listing. Nautilus PVCs are **not** backed
up, which is why the chains and figures are copied to the shared drive.

---

## 7. Follow-ups

1. **The clear-water regime.** Rank correlation for `b_bp` falls even in
   productive water (0.522 → 0.442) while bias and scatter improve — not
   explained by the ill-conditioned tail, and not explained at all.
2. **The 51 non-physical retrievals.** *Resolved 2026-10-18* — understood and
   gated. They are not a low-backscatter/emulator-domain effect but the LM
   warm-start running to the `Bnw` prior ceiling on depressed-blue marginal-sea
   spectra; see §2.5 and
   [`versions/v2/high_bbp_outliers.md`](../../versions/v2/high_bbp_outliers.md).
   O3 excludes them from every `b_bp` statistic; the 2.0.1 re-fit with physical
   prior ceilings (O5–O7), the negative-blue QA count (O4) and an
   emulator-domain slice test (O8) follow in
   `claude_prompts/v2/report_improvements.md`.
3. **`B_p` prior bounds.** 15.4 % of posteriors sit within 5 % of a bound. A
   slice re-fitted with a wider prior would show whether the modes move out.
4. **CDOM fluorescence** is implemented and was off in this run; enabling it is
   a one-flag experiment.
5. **Bulk-artifact publish.** Chains and figures are backed up but not
   published to `s3://pab`, so the release manifest still carries local URLs.
   This is what would let the reporting site reference figures by S3 URL instead
   of committing thumbnails.
6. **Zenodo / DOI.** `ZenodoBackend` remains an explicit `NotImplementedError`.
7. **Gap C** (see `run_full_inelastic.md`).
