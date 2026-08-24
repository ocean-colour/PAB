# PAB Full-Run Report

**`pab_version = 1.0` — first complete production run of the PAB pipeline over the full PACE mission, executed on NSF/Nautilus. Completed 2026-08-20.**

This document is the factual record of the run: what was processed, what was
produced, what broke and how it was fixed, and where the data now lives.

---

## 1. Summary

PAB produces matchup analyses between **PACE** (NASA satellite ocean color,
OCI L2 AOP Rrs) and **BGC-Argo** (autonomous ocean float) profiles. This run
carried the entire PACE mission (2024-03-05 → mid-2026) through all six
pipeline stages — ingest, discover, match, fit, figure, report — on
NSF/Nautilus, ending with a fully stamped, integrity-verified database and an
off-site backup.

### Headline numbers

| Quantity | Value |
|---|---|
| BGC-Argo floats | 881 |
| Profiles ingested | 54,031 |
| PACE granules discovered | 67,435 |
| Matchups | 14,610 |
| Matchup pixels | 146,100 (10 per matchup) |
| Successful fits | 14,609 (99.99%) |
| Fit results (IOP values) | 146,090 (10 per fit) |
| Matchup rate | ≈ 27% of ingested profiles |
| MCMC chain archive | ~18.1 GiB (14,654 objects) |
| Provenance stamping | `pab_version = "1.0"` on 100% of matchups, fits, mld_summary |

Roughly 27% of ingested profiles (14,610 / 54,031) produced a matchup; the
remainder had no coincident cloud-free PACE pixel within the matchup window.
Exactly one matchup's fit failed
(`5906568_97_PACE_OCI.20250809T225220.L2.OC_AOP.V3_2.nc`), for a fit success
rate of 14,609 / 14,610 = 99.99%.

---

## 2. Selection and environment

### Target selection

- **Floats/profiles:** BGC-Argo profiles over the PACE mission window
  (2024-03-05 → mid-2026), restricted to floats carrying `BBP700` or `CHLA`.
- **Satellite data:** PACE OCI L2 AOP Rrs granules, discovered via
  earthaccess/CMR.
- **Fit model pair:** **ExpBPow** — Exponential-Bricaud a_ph plus power-law
  particulate backscatter, inverted with the BING Bayesian MCMC framework
  (emcee).

### Run environment

| Component | Detail |
|---|---|
| Platform | NSF/Nautilus (Kubernetes + Ceph storage + S3) |
| Namespace | `sea-meets-the-stars` |
| Container image | `gitlab-registry.nrp-nautilus.io/profx/pab` (canonical tag `1.0.3`) |
| Storage | 500 GiB CephFS PVC `pab-data` |
| Data layout | `/data/full/pab.db`, `/data/fit_chains`, `/data/full/pipeline/site` |
| Compute model | One pod = one SQLite writer; heavy stages parallelized in-process across cores (`--jobs`) |

Granules were **read lazily from NASA `us-west-2` S3** — only ~MB-per-pixel
transfers were made against each granule. The ~18.55 TB of candidate granules
were never downloaded or staged. A Task-1 measurement had shown lazy reads at
~4.4 s/granule from Nautilus, and this proved reliable in production (apart
from ~2% transient S3 jitter; see Section 6).

All stages are idempotent and resumable, which mattered repeatedly during the
run.

---

## 3. Results by stage

| Stage | Output | Count |
|---|---|---|
| ingest | floats | 881 |
| ingest | profiles | 54,031 |
| ingest | mld_summary rows | 54,031 |
| discover | PACE granules | 67,435 |
| match | matchups | 14,610 |
| match | matchup_pixels | 146,100 |
| fit | fits | 14,609 |
| fit | fit_results | 146,090 |
| figure | fit figures | 14,609 |
| figure | PACE scene images | 14,586 |
| report | RST site | 7 pages + release manifest |

Notes:

- **Ingest** was per-profile-resilient: of the ~54,506 originally selected
  profiles, a small number failed the transient argopy fetch and were skipped,
  leaving 54,031 ingested.
- **Match** was stopped at 14,610 matchups (~2026-08-14) when the rate
  plateaued — each resume pass re-scans not-yet-matched profiles and was
  adding <1% per pass, indicating the remainder are genuinely unmatchable
  (no coincident cloud-free granule). Stopping was safe: matchups are durable
  and fit is idempotent.
- **Figure** produced scene images for 14,586 of 14,609 fits; 23 scenes hit
  granule edge cases.

---

## 4. Fit outputs and provenance

### The 10 IOP quantities

Every fit stores exactly 10 inherent-optical-property quantities, all
non-null across all 14,609 fits, named `BING_ExpBPow_<quantity>`:

| | | | | |
|---|---|---|---|---|
| Adg | Aph | Bnw | Sdg | anw440 |
| anw700 | bbp440 | bbp700 | beta | chl |

### Provenance

- **Version stamping:** `pab_version = "1.0"` is present on **100%** of
  records in `matchups` (14,610), `fits` (14,609), and `mld_summary`
  (54,031). No unstamped rows.
- **Environment capture:** every fit's `pkg_versions` JSON records the full
  software environment, e.g.: pab 1.0, bing 0.0.dev0, ocpy 0.1.dev0,
  argopy 1.4.0, remote_sensing 0.0.dev0, earthaccess 0.17.0, numpy 2.4.6,
  scipy 1.18.0, xarray 2025.9.0.

### MCMC chains

One NPZ per fit, ~1.3 MB each, totaling **~18.1 GiB** across 14,654 objects.
This is far below an early ~180 GB estimate (which assumed ~13 MB/chain);
real chains compressed to ~1.3 MB.

---

## 5. Data integrity and verification

Verified against the production DB `/data/full/pab.db` (backed up locally at
`PAB/data/backup/pab.db`):

- Row counts are internally consistent: 146,100 matchup_pixels = exactly
  10 pixels x 14,610 matchups; 146,090 fit_results = exactly 10 quantities
  x 14,609 fits.
- **Referential integrity: 0 orphan matchups, fits, or fit_results.**
- All 10 IOP quantities are non-null across all fits.
- Exactly one fit failure in the entire run
  (`5906568_97_PACE_OCI.20250809T225220.L2.OC_AOP.V3_2.nc`).
- `pab_version = "1.0"` stamped on 100% of matchups, fits, and mld_summary
  rows.

---

## 6. Operational history

Four incidents from the run are worth recording.

**1. Match stage file-descriptor leak (~2.4 days in).** The 50k-profile match
stage (`--jobs 16`) wedged after ~2.4 days. The parallel path kills and
recreates its worker pool on each transient S3-read stall — ~192 times over
the run, driven by ~1,283 granule-read timeouts on ~1,228 unique granules
(~2% transient S3 jitter). The old pool teardown did not reap workers or
close their pipes, leaking ~5 pipes per kill → ~1,000 pipes → `ulimit -n
1024` exhausted → `OSError: [Errno 24]`. Fixed in `pab/matchup/engine.py`
(`_reclaim_pool`: kill → reap → `shutdown(wait=True)` with a 30 s watchdog
thread so the recovery itself cannot hang), plus `ulimit -n 65536` headroom.
After the fix, FDs stayed bounded across stalls.

**2. Match declared done at 14,610 matchups (~2026-08-14).** The matchup rate
plateaued: each resume added <1% per pass, and the remaining profiles are
genuinely unmatchable (no coincident cloud-free granule). Stopping was safe
because matchups are durable and fit is idempotent.

**3. Fit stage hard-hangs on CephFS.** The fit stage (`--jobs` up to 50, then
32) repeatedly hard-hung. Root cause: **SQLite's sustained locked access to
the DB on CephFS**, not raw throughput — the gather phase (14,610 matchups x
4 queries) hung 12+ minutes against the CephFS DB but ran in 0.6 s on a local
copy. Fixed with a Job-wrapper strategy, no code change: copy `pab.db` to
node-local ephemeral disk (`emptyDir /scratch`), run `fit` against the local
DB, keep writing the bulk chain files to CephFS (bulk writes were never the
problem), and periodically checkpoint the DB back to CephFS via local backup
→ file-copy (never `sqlite3.backup()` straight to CephFS, which re-triggers
the hang). Fits then climbed steadily at ~4–5/min, fully resumable.

**4. Figure/report shape retune (completed 2026-08-20, ~18 h).** The first
figure+report launch reused fit's 32-worker / 64 GiB shape and OOM-killed
pods. Lesson: `figure` re-opens PACE granules for scene images, so it is
memory-bound like `match`, not CPU-bound like `fit`. Retuned to 16 workers /
100 GiB (match's proven ratio) and the run was stable. Figure produced 14,609
fit figures and 14,586 scenes (23 granule edge cases); report produced the
7-page RST site and release manifest.

---

## 7. Publishing and backup status

To be precise about what is and is not published:

- **The run itself used a local stub; the DB is now published to S3.** During
  the run the `report` stage's release backend was the `LocalStubBackend`,
  which "uploads" by copying artifacts into `outdir/release/store/` on the same
  PVC — so the run's manifest `n_uploaded = 29,218` reflects that **local**
  copy, not an S3 upload. Since then, **`NautilusS3Backend` has been
  implemented** (live Ceph-RGW S3, path-style, public-read) and the full
  production DB is published at
  **`https://s3-west.nrp-nautilus.io/pab/full/pab.db`** (public-read; size +
  row counts verified against the local copy). **Still pending:** publishing
  the **bulk artifacts** (chains + figures) to `s3://pab` via
  `publish_release(..., backend=NautilusS3Backend(...))` so the manifest
  carries real S3 URLs, the Read-the-Docs report site, and (if wanted) a
  citable Zenodo DOI (`ZenodoBackend` is still a `NotImplementedError` stub).
- **Off-site backup is complete and verified.** Nautilus PVCs are not backed
  up, so the full dataset was rcloned to the Google shared drive
  **`AIOcean:PAB/`**: `pab.db` (132 MB), `fit_chains/` (18.09 GiB, 14,654
  objects), and `site/` (~3.67 GiB). Verified present 2026-08-21. The
  redundant ~19 GB `release/store` local stub was intentionally not backed up.

---

## 8. Reproducibility — where the data lives

| Artifact | Location |
|---|---|
| Production database | Nautilus PVC `pab-data`: `/data/full/pab.db` |
| MCMC chains | Nautilus PVC `pab-data`: `/data/fit_chains` |
| Report site | Nautilus PVC `pab-data`: `/data/full/pipeline/site` |
| Container image | `gitlab-registry.nrp-nautilus.io/profx/pab:1.0.3` |
| Local DB backup | `PAB/data/backup/pab.db` |
| Published DB (public) | `https://s3-west.nrp-nautilus.io/pab/full/pab.db` |
| Off-site backup | Google shared drive `AIOcean:PAB/` (`pab.db`, `fit_chains/`, `site/`) |

The namespace is `sea-meets-the-stars`. Every fit's `pkg_versions` JSON
records the exact package environment, and every matchup, fit, and
mld_summary row is stamped `pab_version = "1.0"`.

---

*This is a living record; it will be updated as the release backends (S3,
Read the Docs, Zenodo) are completed.*
