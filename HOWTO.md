# HOWTO — running the PAB pipeline

This is the operator's guide to running the **PAB** end-to-end matchup pipeline
(Stage 8). The pipeline ties Stages 2–7 together —
**ingest → discover → match → fit → figure → report** — as a single, resumable
stage runner driven off a SQLite store. Re-runs skip work already done, so it is
safe to interrupt and resume.

> **Scope.** This documents the pipeline **as it exists today**. A few agreed
> enhancements (single-matchup targeting, parallel fitting, a config file) are
> not implemented yet — see [Planned enhancements](#planned-enhancements).


## 1. Prerequisites

### Python environment
Install the package (editable) from the repo root. This puts the `pab` console
script on your `PATH`:

```bash
pip install -e .
```

The core requirements install from `requirements.txt`. Three special-source
packages are **not** on PyPI yet and must be installed separately (see the notes
at the bottom of `requirements.txt`):

- **`bing`** — the spectral fitting engine (Stage 5). Install from source.
- **`ocpy`** — ocean-color helpers. Install from source / local checkout.
- **`remote_sensing`** — provides `remote_sensing.healpix` (used by the report
  aggregates). Install from source.

> The `fit` and `figure` stages also need **`emcee`** (MCMC sampler) and BING's
> **Loisel** reconstruction data on disk. Without them, the pipeline still runs
> ingest → discover → match → report; the fit stage is best-effort and is simply
> skipped per-matchup if BING isn't available.

### Earthdata Login (PACE granule access)
Granule **discovery** and **opening** go through `earthaccess`, which reads your
NASA Earthdata credentials from `~/.netrc`:

```
machine urs.earthdata.nasa.gov login <username> password <password>
```

A working `~/.netrc` is already present on the workstation. No interactive login
is needed once it exists.

### Argo source
Profiles are fetched via **argopy** using the **GDAC / expert** source by default
(`argo_src="gdac"`, `argo_mode="expert"`) — chosen because the ERDDAP source was
returning 408s for recent profiles. The offline dev runs use precomputed
summaries and don't touch argopy at all.


## 2. Quick start

A safe first command — print the plan and exit without touching anything:

```bash
pab --dry-run
```

Run the full pipeline against the default dev set
(`data/dev_profiles.csv` — 10 profiles across 2 floats):

```bash
pab --db data/pab.db
```

Outputs land under `DATA_DIR/pipeline/` by default (see
[Outputs](#5-outputs)). `DATA_DIR` is the repo's `data/` directory unless you
override it with the `PAB_DATA_DIR` environment variable.


## 3. The CLI

```
pab [-h] [--db DB] [--stage {ingest,discover,match,fit,figure,report}]
    [--outdir OUTDIR] [--profiles-csv PROFILES_CSV] [--replace]
    [--no-figures] [--download] [--cache-dir CACHE_DIR] [--dry-run]
```

| Flag | Meaning |
| --- | --- |
| `--db DB` | SQLite store path (created if absent; parent dirs are made). Default: `DATA_DIR/pab.db`. |
| `--stage STAGE` | Run only this stage. **Repeatable** — e.g. `--stage match --stage fit`. Default: all stages, in order. |
| `--outdir OUTDIR` | Base output directory. Default: `DATA_DIR/pipeline`. |
| `--profiles-csv PROFILES_CSV` | Profile-selection CSV. Default: `data/dev_profiles.csv`. |
| `--replace` | Re-do completed work instead of skipping it. |
| `--no-figures` | Skip the `figure` stage. |
| `--download` | Pre-download each granule to a local cache and read it locally (the reliable **off-cloud** path). Use this whenever you are **not** running in-region (`us-west-2`). |
| `--cache-dir CACHE_DIR` | Where downloaded granules live. Default: `DATA_DIR/granules`. |
| `--dry-run` | Print the stage plan and exit without touching anything. |

### Granule access: in-region vs. `--download`

The `match` (and `figure`/`fit` scene) stages read pixels out of PACE L2
granules. There are two ways to get the bytes:

- **In-region (default).** Running on AWS `us-west-2`, granules are read lazily
  from S3 — only the chunks under the nearest pixel transfer. Fast, no local
  copy. This is the design target.
- **Off-cloud (`--download`).** From a workstation outside `us-west-2`, lazy
  HTTPS byte-range reads are unreliable and can stall indefinitely. Pass
  `--download` to fetch each granule once (a robust streaming download via
  `earthaccess`) into `--cache-dir` and read it locally instead. The download is
  idempotent — a granule already in the cache is reused — so it is safe to
  interrupt and resume. Budget ~0.5 GB per granule on disk.

```bash
# Off-cloud first run (this workstation): pre-download granules as match needs them
pab --db data/pab.db --download
```


## 4. Stages, idempotency & resume

| Stage | What it does | Reads / writes |
| --- | --- | --- |
| `ingest` | Persist BGC-Argo profiles + mixed-layer summaries. | → `mld_summary` |
| `discover` | Find in-window PACE granules per profile (earthaccess). | → `granules` |
| `match` | Build PACE↔Argo matchups (Stage 4 spatial/temporal gate). | → `matchups` |
| `fit` | Run BING spectral fits per matchup (needs BING + emcee). | → `fit_results` |
| `figure` | Render per-matchup figures (best-effort; needs Loisel data). | → `outdir/figures` |
| `report` | Build the static site + a release manifest (Stage 7). | → `outdir/site`, `outdir/release` |

**Idempotent & resumable.** Each stage skips records that already exist (keyed on
their natural keys — profile, `matchup_id`, `fit_id`). Re-running the pipeline
resumes where it left off. `discover` additionally skips any profile that already
has an in-window granule, so it won't re-query the network on resume. Use
`--replace` to force re-doing completed work.

**Provenance.** Records carry the `pab_version` and a `created` timestamp.
Re-running under a *new* `pab_version` **adds** records rather than overwriting,
so historical runs are preserved.

Run a single stage (e.g. just rebuild the report after a fit run):

```bash
pab --db data/pab.db --stage report
```


## 5. Outputs

Relative to `--outdir` (default `DATA_DIR/pipeline`):

- `site/` — the static report site (`summary.rst` + aggregate pages). Build it to
  HTML with Sphinx, or browse the `.rst` directly.
- `release/manifest.json` — the release manifest listing the published artifacts
  and package versions.
- `figures/` — per-matchup figures (when the `figure` stage runs).

The SQLite store (`--db`) holds all the structured results and is the source of
truth; the site and manifest are derived from it.


## 6. Notes & gotchas

- **Granule opens are slow out-of-region.** Opening a PACE L2 granule from S3
  takes ~140–160 s each when you're **not** in `us-west-2`. On the workstation
  this is the dominant cost of a real run. (In-region it's fast.)
- **The closest-in-time granule may not cover the float**, or may be cloudy. The
  Stage-4 spatial gate correctly rejects granules that don't cover the profile —
  a profile yielding zero matchups is expected, not an error.
- **Fits are best-effort.** If BING or its Loisel data aren't present, the `fit`
  and `figure` stages are skipped gracefully; ingest → discover → match → report
  still complete.


## 7. Publishing — set up later, NOT yet

The `report` stage writes a release **manifest** and uploads artifacts through a
pluggable backend. Today only the **local stub** backend is active; the real
**Nautilus S3** and **Zenodo** backends are stubbed and **must not be wired up
yet**.

> **TODO (do not do now):** when we're ready to publish to the community, set up
> the Nautilus S3 and/or Zenodo publishing backends (credentials + the
> `publish` configuration) and switch `report` over from the local stub. Until
> then, releases stay local under `outdir/release/`.


## Planned enhancements

Agreed but **not yet implemented** — don't expect these flags to work yet:

- **Single-matchup targeting** (e.g. `--matchup` / `--wmo` / `--cycle`) to run
  one profile/matchup instead of the whole selection.
- **Parallel fitting** — matchup-level parallelism in the `fit` stage.
- **Config file** — load run configuration from a file (TOML) instead of flags.
