# Build v2 — Prompt 4: image `pab:2.0.0`, PVC re-layout, in-pod validation

## Goals

Containerize the 2.0 code with `robust`/JAX, re-lay the Nautilus PVC into
`/data/v1` (frozen) and `/data/v2` (the run), stage the v2 database there,
and prove the whole cloud path in-pod with a small validation job
(`run_full_inelastic.md` Plan §3 i, §5 steps 2–3; Q10).

## Claude

### Skills

- None specific; the Nautilus patterns live in `nautilus/*.yaml` and
  `claude_prompts/nautilus_prompts.md`.

### Working agreements

As in `build_v2_prompt_1.md`. **Outward-facing steps need confirmation**:
`docker push` needs the user's `docker login` (deploy token); PVC renames
and Job launches are confirmed first. Manifests: literal `|` blocks, one-line
`python -c`, no here-docs (the 2026-07-19 lesson); `backoffLimit`, no
`rm -rf` on production dirs.

**Settled in Prompts 1–3 — no longer open:**

- **`ocean14`** is the only env; test baseline **334 passed, 1 skipped**
  (the skip is the env-gated live L1B test, `PAB_LIVE_L1B=1`).
- `pab_version` is **`"2.0"`** and the installed dist agrees (`setup.py` +
  `pab/config.py` + a reinstall). `package_versions()["pab"] == "2.0"`.
- `v1/pab.db` frozen at `09de0a6d…f978273`, schema **v4**, `a-w` — read it
  with `Store.open(..., create=False)`.
- `v2/pab.db` is at schema **v5**, and both repos are **committed**:
  PAB `eeda46f`, retrieve-or-bust `e1f4289`.
- `ruff check pab/` has 8 pre-existing errors in
  `pab/argo/check_argo_coverage.py`. Not yours.

## Context

- Plan §3 i, §5 of `claude_prompts/v2/run_full_inelastic.md`.
- `Dockerfile`, `nautilus/build_image.sh` (staged 90 MB context; `TAG`;
  the six Task-5 packaging fixes — `bing/data`, `ocpy/data`,
  `ocpy/hydrolight/__init__.py`, the Loisel `Hydrolight400.nc`, argopy/
  erddapy pins, the build guards `FIT DEPS OK` / `LOISEL OK`).
- `retrieve-or-bust/requirements.txt` (`jax`, `flax`, `optax`, `jaxtyping`;
  CPU-only JAX); the emulator weights ship inside the `robust` package.
- `nautilus/validate_job.yaml` (5 profiles → 1 fit; currently `pab:1.0.3`,
  `PAB_DATA_DIR=/data`, wipes `/data/val`), `nautilus/inspect_pod.yaml`.
- Namespace `sea-meets-the-stars`; PVC `pab-data` (500 Gi, `rook-cephfs`);
  secrets `earthdata-netrc`, `prp-s3-credentials`, `rclone-config`;
  registry `gitlab-registry.nrp-nautilus.io/profx/pab` (public).
- Current PVC layout: `/data/full/{pab.db,pipeline/,run.log,…}` (stale DB —
  pre-`cdom_chl`, pre-NASA), `/data/fit_chains/` (18.09 GiB, 14,654 files),
  `/data/run1k/`, `/data/val/`, `/data/src/` (retired checkout).

### What Prompts 1–3 delivered, and what this prompt must carry (2026-09-17)

**The image MUST be built from `retrieve-or-bust` ≥ `e1f4289` ("off nadir").**
That commit fixes an inference bug in `robust`'s emulator: features that were
constant in L23 training (`cos_theta_v`, `cos_dphi`) were divided by the 1e-8
standardisation guard, so a real 54.6° sensor zenith standardised to −4.2e7,
saturated every `tanh`, and collapsed the correction to a **flat −0.219 at all
81 wavelengths — a silent −22 % bias on `Rrs` at every real PACE pixel**. An
image built from `5ca740d` or earlier will produce quietly wrong 2.0 fits with
no error. Prompt 3 Task 3 has the measurements; the build guard below is the
in-image check.

**`robust`'s packaged data files are runtime-critical**, not optional:

- `robust/rt/files/emulator_l23.npz` — the emulator weights.
- `robust/rt/data/ed_l23.npz` — the **Loisel+23 `Ed(theta_s)` table**
  (350–750 nm). PAB's `set_inelastic_Ed` reads it for **every** 2.0 fit,
  because PACE L2 carries no `Ed` and BING's Raman and fluorescence kernels
  both need one. Without it a fit raises
  `IndexError: … array is 0-dimensional` (fluorescence) or silently falls
  back to a flat Raman ratio. The repo is only 62 MB, but `context/` is 16 MB
  and `notebooks/` 3.3 MB — exclude those, **never** `robust/rt/files` or
  `robust/rt/data`.

**The five git SHAs** for the `PAB_GIT_SHAS` label are keyed exactly as
`PAB`, `bing`, `ocpy`, `remote_sensing`, **`retrieve-or-bust`** (the repo
name, not `robust`). As of 2026-09-17:

```json
{"PAB": "eeda46f", "bing": "bf56f6d", "ocpy": "c3132a6",
 "remote_sensing": "2b85c65", "retrieve-or-bust": "e1f4289"}
```

The env var **takes precedence over `git rev-parse`**, deliberately: the image
has no `.git`, and a stray one copied in must not override what the build
stamped. Malformed JSON is ignored rather than fatal. See
`pab/config.py::git_shas` (Prompt 3 **Task 4**, not Task 3 — JXP inserted a
new Task 3, so the task numbering in this doc's Task 1 was off by one).

**`$PAB_DATA_DIR/v2/pab.db` as it stands today** — what Task 3 stages:

| | |
|---|---|
| size | **120,635,392 B** |
| sha256 | **`ef552419174507eb25c77da7ea72484646d3ce162dc2f51259b438d8c127b735`** |
| schema | v5 (`user_version = 5`) |
| contents | 881 floats / 54,031 profiles / 67,435 granules / 14,610 matchups / 146,100 pixels / 14,609 `NASA_GIOP` fits / 116,872 `fit_results` |
| **geometry** | **0 of 146,100 pixels filled** — the `geometry` stage has never been run against it |
| BING fits | 0 |

That last row matters for Prompt 5, not this one: the full run must budget
`--stage geometry` over **11,494 distinct granules** before any fitting.

**Measured 2.0 cost (workstation, Prompt 3 Task 6, 20 real matchups):**

| | s/fit |
|---|---:|
| 2.0 `robust_hybrid` | ~181 (3 arms contended) / ~101 (uncontended, `--jobs 2`) |
| 2.0 `robust_ztt` | ~178 |
| 1.0 `gordon` | ~36 |

2.0 is **~5× the cost of 1.0**. Chains are **~1.15 MB/fit** → **~17 GB** for
14,610 matchups, on top of v1's 18.09 GiB already on the PVC (500 Gi, fine).
Task 4's in-pod number is the one Prompt 5 should actually size from — the
workstation figures above were measured under contention and are conservative.

**Thread caps are automatic now.** `pab.parallel.init_worker` sets
`XLA_FLAGS=--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1`
alongside the BLAS caps, and `pab.fit.run._worker_init` delegates to it, so
`--jobs 4` in-pod will not have each worker spawn an ncores-wide XLA pool. No
manifest-level env var is needed for that; setting one anyway is harmless
(`setdefault`).

**Expect `DomainWarning` on every forward call.** `robust` correctly reports
that the emulator is unvalidated off-nadir (`cos_theta_v`/`cos_dphi` were
never varied in training). After `e1f4289` the correction is geometry-*blind*
by explicit assumption rather than corrupted, but the warning still fires —
once per forward call, so **thousands of lines per fit**. Suppress it in the
job (`PYTHONWARNINGS`, or a filter) or the pod log is unusable. Note
`on_out_of_domain="ztt"` is **not** the answer: the geometry features are
recorded as trained over `[1, 1]`, so every pixel counts as out of domain and
that policy degenerates to plain `robust_ztt`.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below

## Tasks

1. **Image.** Extend the staged build to include `retrieve-or-bust`
   (add it to the `for pkg in …` rsync loop in `nautilus/build_image.sh`;
   exclude `.git`/`notebooks`/`reports`/`context`/`design`/`docs`, but
   **keep `robust/rt/files/` and `robust/rt/data/`** — the emulator weights
   and the `Ed` table are runtime-critical, see Context) and add
   `jax flax optax jaxtyping` to the `pip install`. **Check out
   `retrieve-or-bust` at ≥ `e1f4289` before staging** (Context: an older
   commit ships the −22 % emulator bug silently).

   The build guard must do more than import. Make it:
   (i) `robust.rt.ed.load_table()` → 81 wavelengths spanning 350–750 nm;
   (ii) one `robust_hybrid` forward call at **off-nadir** geometry
   (`theta_s=29.47, theta_v=54.58, dphi=81.33`) asserting the relative
   correction is **spectrally varying, not a flat constant** — the in-image
   regression test for the `e1f4289` fix, which fails loudly on a stale
   `robust`;
   (iii) `from pab.fit.run import fit_spectrum, set_inelastic_Ed` and
   `pab.config.package_versions()["pab"] == "2.0"`.
   Print `ROBUST OK` / `ED OK` beside the existing `FIT DEPS OK` / `LOISEL OK`.

   `TAG=2.0.0`; bake the five SHAs in as the `PAB_GIT_SHAS` **env var** (the
   seam is `pab/config.py::git_shas`, Prompt 3 **Task 4**), and `--label`
   them too for `docker inspect`. Build, smoke-test `pab --dry-run`
   (**`--rm`, bounded**), then — after the user's `docker login` — push
   `:2.0.0` + `:latest` and verify with `docker manifest inspect`. Record the
   image digest. Log.

2. **PVC re-layout** (via a short-lived helper pod, confirm first): `mv
   /data/full /data/v1`; `mv /data/fit_chains /data/v1/fit_chains`;
   `mkdir -p /data/v2/fit_chains /data/v2/pipeline`; leave `/data/run1k`,
   `/data/val`; delete `/data/src` (retired). Note that `fits.chains_path`
   in the **v1** DB still says `/data/fit_chains/...` — leave v1 as is (it
   is frozen; record the path change in `HOWTO.md`). Report `du -sh` per
   dir. Log.

3. **Stage v2.** Copy the workstation `$PAB_DATA_DIR/v2/pab.db` to
   `/data/v2/pab.db` (`kubectl cp` via the helper pod, or an S3 hop through
   `s3://pab/v2/pab.db` if faster); verify sha256 both ends against
   **`ef552419174507eb25c77da7ea72484646d3ce162dc2f51259b438d8c127b735`**
   (120,635,392 B, schema v5 — Context). Confirm in-pod that
   `PRAGMA user_version` is **5** and that `matchup_pixels` carries the four
   geometry columns: a v4 copy would be silently fitted without them.

   The staged DB has **no geometry filled** — expected, and Prompt 5's first
   job, not a staging error.

   From now on **`/data/v2/pab.db` is the single writer's copy**; mark the
   workstation copy read-only (`chmod a-w`) until Prompt 7 brings the DB
   back. Log.

4. **In-pod validation.** New `nautilus/v2_validate_job.yaml` from
   `validate_job.yaml`: image `:2.0.0`, `PAB_DATA_DIR=/data/v2val`, its own
   scratch DB (wiped — fine for a 5-profile smoke), stages `ingest →
   discover → match → geometry → fit → figure → report`, `--jobs 4`.
   Gates, with the concrete values Prompt 3 Task 6 established:

   - **`geometry`**: every pixel has `theta_s`/`theta_v`/`dphi` and
     `geom_source = 'L1B_V3'`; `failed` and `mismatched` both empty. This
     stage does a **live CMR lookup plus a lazy read of a 1.8 GB L1B granule
     per granule**, so the pod needs Earthdata credentials and outbound
     network — the one new external dependency in 2.0.
   - **`fit`**: `rt_backend='robust_hybrid'`, `include_raman=1`,
     `include_chl_fl=1`, `include_cdom_fl=0`, `fit_bp=1`, `phi_c=0.02`,
     `wave_max=720.0`, `pab_version='2.0'`, `fit_id` ending **`_v2.0`**.
   - **chains**: 6-column `(nsteps, nwalkers, 6)`, ~1.15 MB each, under
     `/data/v2val/fit_chains` — which requires `PAB_DATA_DIR=/data/v2val`,
     since `chains_path()` keys off the root of `PAB_DATA_DIR`, not `--db`.
   - **`pkg_versions`**: carries `robust` (under its *import* name; the
     distribution is `retrieve-or-bust`) and a `git_sha` map whose five
     values are **not** `"unknown"` — the check that the `PAB_GIT_SHAS`
     label actually reached the running process.
   - **sanity on the numbers**, not just on completion: `bbp700` in the
     1e−4–2e−3 range, `Bp` inside `[0.004, 0.05]`, χ² order-unity,
     acceptance ~0.2–0.4 (2.0 runs below 1.0's ~0.47 — six parameters).
   - JAX compiles in the spawned workers, no `theta_s` error, and no
     `DomainWarning` flood (suppress it — Context).

   Report **in-pod s/fit**; the workstation saw ~101 s/fit uncontended and
   ~181 s under 3-way contention, so anything in that band is expected and
   anything far outside it is worth understanding before Prompt 5 sizes the
   full run from it. Delete the scratch dir after. Log.

5. **Update.** Based on what you have done, update the prompt doc
   `build_v2_prompt_5.md`, as needed. Log.
   *(Added 2026-09-17, mirroring the Task 5 JXP added to
   `build_v2_prompt_1.md`. Delete it if that is not the intent.)*

## Q&A

### Q1 (carried from Prompt 3 Q2, 2026-09-17) — settle `wave_max` **before** the image is built

Prompt 3 Q2 is **open**, and it sits on this prompt's critical path: if the
answer changes `FitConfig.wave_max` or adds a non-positive-band screen to
`prepare_spectrum`, that change must be in the code **before** `:2.0.0` is
built, or the image ships a configuration the full run will not use and has to
be rebuilt and re-pushed.

Briefly: at 719 nm — the band the 2.0 window newly includes — `Rrs` is
**negative on 6 of 20** local matchups and swamped by its own uncertainty on 2
more (**40 % unusable**), and the four worst 2.0 χ² in the set are exactly the
four most negative `Rrs(719)`. Full numbers and three options in
`build_v2_prompt_3.md` Q2.

**If JXP has not answered by the time this prompt runs**, build `:2.0.0` from
the current defaults (`wave_max = 720`) — nothing is blocked, every fit
succeeded — but **do not treat the image as final** until Q2 is settled, and
say so in the report.

>A. I have answered the question in the prompt_3.md doc.  Read that an proceed accordingly.

### Q2 (Task 2, 2026-09-17) — confirm the PVC re-layout, and what to do with the **stale** DB it renames to `v1/pab.db`

**Survey first** (read-only helper pod, already run and deleted). `pab-data`
holds **45 G of 500 G**, 456 G free, and **neither `/data/v1` nor `/data/v2`
exists yet** — a clean slate:

| path | size | note |
|---|---:|---|
| `/data/full` | **27 G** | `pab.db` (138,854,400 B, **stale**), `pipeline/`, `run.log` (66 MB), 2 probe logs, a `pab.db.tmp-journal` |
| `/data/fit_chains` | **19 G** | **14,633** files (the doc said 18.09 GiB / 14,654 — close, now measured) |
| `/data/run1k` | 507 M | leave |
| `/data/val` | 2.3 M | leave |
| `/data/valj1` | 577 K | **not mentioned in the task** — leaving it |
| `/data/src` | 2.9 M | retired checkout → delete |
| loose top-level files | ~3 M | `coverage_check.py`, `fitdbg.log`, `full_profiles.csv`, `rediscover_csv.py`, `rediscover_profiles.csv` — **not mentioned** → leaving them |

**The judgement call.** The task says `mv /data/full /data/v1`. But
`/data/full/pab.db` is the **stale** database — 138,854,400 B, pre-`cdom_chl`,
pre-NASA-GIOP — and it is *not* the published v1 release:

| | bytes | |
|---|---:|---|
| PVC `/data/full/pab.db` | 138,854,400 | stale |
| workstation `v1/pab.db` | 169,938,944 | **the published 1.0**, sha `09de0a6d…` |
| workstation `v2/pab.db` | 120,635,392 | the v2 build |

Renaming it to `/data/v1/pab.db` would put a *different* database at the one
path `HOWTO.md` §5b defines by sha256. Anyone later checking "is the PVC's v1
the released v1?" gets a mismatch and has to re-derive why.

So I propose renaming the file as part of the move:
`/data/v1/pab.db` → **`/data/v1/pab_stale_2026-08-20.db`**, leaving
`/data/v1/pab.db` **absent** rather than wrong. The 19 G of chains under
`/data/v1/fit_chains/` *are* genuine 1.0 chains, so the directory is still
honestly named.

**Full proposed plan** (one short-lived helper pod, `mv` only — no `rm -rf`):

1. `mv /data/full /data/v1`
2. `mv /data/v1/pab.db /data/v1/pab_stale_2026-08-20.db`  ← the call above
3. `mv /data/fit_chains /data/v1/fit_chains`
4. `mkdir -p /data/v2/fit_chains /data/v2/pipeline`
5. `rm -rf /data/src` (retired checkout, 2.9 M) — **the only deletion**
6. `du -sh` per directory afterwards

All renames are within one CephFS volume, so they are metadata-only and
instant even for the 19 G of chains.

**Questions:**

- **(a)** Go ahead with the plan?
- **(b)** Rename the stale DB as proposed, or leave it at `/data/v1/pab.db`?
- **(c)** Delete `/data/src`, or leave it?
- **(d)** Should Prompt 4 also upload the *real* `v1/pab.db` to
  `/data/v1/pab.db`? Not in the task, and not needed for the v2 run — but it
  would make the PVC match the documented layout. It is a 170 MB transfer.

*My recommendation: (a) yes, (b) rename, (c) delete, (d) not now — the v2 run
does not read v1, and Prompt 7's comparison can pull it from `s3://pab/v1/`.*

>A. (a) yes, (b) rename, (c) delete, (d) not now — the v2 run does not read v1, and Prompt 7's comparison can pull it from `s3://pab/v1/`.

### Q3 (Task 1, 2026-09-17) — confirm the `docker push` of `pab:2.0.0`

The image is **built and verified locally**; only the outward-facing push is
held. `gitlab-registry.nrp-nautilus.io` credentials are already stored in
`~/.docker/config.json`, so no fresh `docker login` should be needed.

| | |
|---|---|
| tags | `:2.0.0` **and** `:latest` |
| size | **9.21 GB** (1.0.3 was 7.71 GB; +1.5 GB is the JAX stack) |
| local id | `sha256:414480445fce78aa1143510c3633bb335cf4676ef1b2fa6836eccdb6d009786f` |
| registry | `gitlab-registry.nrp-nautilus.io/profx/pab` — **public** |
| baked provenance | `{"PAB":"3efc987","bing":"bf56f6d","ocpy":"c3132a6","remote_sensing":"2b85c65","retrieve-or-bust":"e1f4289"}` |

Build guards all passed, including the off-nadir regression test that proves
the fixed `robust` is inside (`ROBUST OK off-nadir delta 0.0116..0.0926
std 0.0245` — spectrally varying, not the flat constant a stale `robust`
would give). A real 2.0 fit runs inside the container: chains `(300, 16, 6)`,
`Bp` 0.0498 inside its prior.

**What makes this outward-facing:** it publishes a 9.2 GB public image, and it
**moves `:latest` off `1.0.3`**, so anything pulling `:latest` gets 2.0 code
with the new inelastic defaults.

**Questions:**

- **(a)** Push `:2.0.0`?
- **(b)** Also move `:latest`, or push only the version tag and leave
  `:latest` on `1.0.3` until the in-pod validation (Task 4) passes?

*My recommendation: (a) yes; (b) push both — the manifests here pin an explicit
tag, `:latest` is a convenience, and leaving it on 1.0.3 after 2.0 ships is the
more confusing state.*

>A. Let's use your Recommendations


### Q4 (Task 4, 2026-09-17) — the in-pod run found a real bug; confirm a **`:2.0.1`** rebuild

The validation passed every gate, but the `figure` stage **failed** on the one
robust fit — and my gates did not notice, because they only inspected the
database and a stage that produces nothing leaves no row to check. Both are
now fixed; the question is what to do about the image.

**The bug.** `fit_fig` peels the chain's trailing `B_p`, giving one value per
posterior sample, and passed it straight to the robust forward model. `robust`
wants `B_p` in its batched **`(nsamples, nwave)`** layout (the same broadcast
`bing.evaluate.reconstruct_from_chains` does), so JAX died with
`Incompatible shapes for broadcasting: [(48000, 136), (48000,)]`.

It escaped every local test for a specific reason worth recording: the *other*
caller (`_fit_diagnostics`) passes a **scalar**, which broadcasts fine, and the
dispatch unit tests **mock** `calc_Rrs_from_models_robust`, so nothing ever put
a real batch through the real backend. Prompt 3 Task 6 never caught it either —
it fitted 60 spectra but never rendered a figure.

**Fixed and verified:** `reconstruct_rrs` now normalises `B_p` via
`_broadcast_bp` (scalar and `None` pass through untouched), proven by
**rendering a figure from a real `robust_hybrid` fit** off the Prompt 3 Task 6
store — 54,561 bytes, under the 100 KB budget. Two regression tests added, one
of which pushes a genuine batch through the **unmocked** backend. Suite now
**336 passed**. The gate script gained a figure check.

**So `:2.0.0` on the registry contains a `figure` stage that fails for every
2.0 fit.** Everything else in it is good — geometry, fit, provenance, schema
all validated in-pod.

**Questions:**

- **(a)** Rebuild and push **`:2.0.1`** (and move `:latest`), then re-run the
  validation against it?
- **(b)** Or leave `:2.0.0` and run the full production run with
  `--no-figures`, deferring figures to a later image?

*My recommendation: (a).* The fix is three lines with tests behind it, the
rebuild is ~10 minutes, and Prompt 5's full run would otherwise log 14,610
figure failures and produce no per-matchup figures for the report site. I would
also re-run the validation job, since the point of it is to gate the image that
actually runs.

>A. Let's go with your recommendation.

## Reports

### Task 1 — image `pab:2.0.0` (2026-09-17): **built, pushed, verified**

**Q2's answer landed first and changed the build.** JXP chose option 2 —
"drop back to 700nm for 2.0" — so before building I moved
`FitConfig.wave_max` 720 → **700.0** in code, tests and docs. 2.0 and 1.0 now
fit the **same 400–700 nm band** and differ only by radiative transfer. That
was the whole point of raising Q1 here: the image freezes the configuration,
and settling it after the build would have meant a rebuild and re-push.

| | |
|---|---|
| tags | `:2.0.0`, `:latest` |
| **registry digest** | **`sha256:1afd4cc9cd97943a5a0b078e1daccbb6e83d794ee715b9824738430a3fab14c1`** (both tags) |
| local image id | `sha256:414480445fce78aa1143510c3633bb335cf4676ef1b2fa6836eccdb6d009786f` |
| size | **9.21 GB** (1.0.3 was 7.71 GB; +1.5 GB = the JAX stack) |
| baked provenance | `{"PAB":"3efc987","bing":"bf56f6d","ocpy":"c3132a6","remote_sensing":"2b85c65","retrieve-or-bust":"e1f4289"}` as both `PAB_GIT_SHAS` env and an OCI `image.revision` label |

**Build guards, all passing:**

```
FIT DEPS OK / LOISEL OK          (unchanged from 1.0.3)
ED OK 350 750 (3, 81)
ROBUST OK off-nadir delta 0.0116..0.0926 std 0.0245
PAB 2.0 OK robust_hybrid 400.0 700.0 | git_sha {...}
PROVENANCE OK (all five SHAs non-"unknown")
STAGES OK ('ingest','discover','match','geometry','fit','figure','report')
```

The `ROBUST OK` line is the one that matters: it is a **regression test, not a
smoke test**. A stale `robust` (< `e1f4289`) imports fine and returns a number
from the forward call — the same number at every wavelength. Asserting the
correction *varies* (std 0.0245) is what proves the off-nadir fix is inside.

Beyond `pab --dry-run`, I ran a **real 2.0 fit inside the container** (no
network): chains `(300, 16, 6)`, `param_names[-1] == 'Bp'`, `Bp` 0.0498 inside
its prior. The image can fit, not merely import.

**One blocker had to be solved: the build was broken for everyone.**
`bing/setup.py` pins
`retrieve-or-bust @ git+https://github.com/ocean-colour/retrieve-or-bust.git@cdom-rt`,
and that branch was merged (PR #21 → `5ca740d`) and **deleted from the
remote** — `git ls-remote` returns nothing. pip died with
`error: pathspec 'cdom-rt' did not match any file(s) known to git`.

I did **not** edit `bing`. That pin exists so ReadTheDocs can build without a
local checkout, and re-pointing it is bing's call (its own comment says
"re-point or drop the @cdom-rt once robust/rt merges to main"). Instead
`nautilus/build_image.sh` now strips that single line from the **staged copy
only**, guarded by a `grep` so it reports if the pin is ever fixed upstream.
`retrieve-or-bust` is installed from staged source in the same pip command, so
the requirement is redundant here. A blanket `--no-deps` would have silently
dropped bing's other ~25 dependencies (`timm`, `umap-learn`, `astropy`, …).

**Also changed:** `retrieve-or-bust` added to the staging rsync (excluding
`context/` 16 MB, `notebooks/`, `reports/`); three staging guards that fail the
build if the emulator weights, the `Ed` table, or the off-nadir fix are missing
from the staged tree; `jax flax optax jaxtyping` in the pip install; `TAG=2.0.0`.

### Task 2 — PVC re-layout (2026-09-17): **done**

Executed exactly as approved in Q2 — (a) yes, (b) rename, (c) delete, (d) not
now. One short-lived pod, `mv` only, with preconditions that refuse to run if
`/data/v1` or `/data/v2` already exist.

| | before | after |
|---|---|---|
| `/data/full` (27 G) | stale `pab.db`, `pipeline/`, `run.log` | → **`/data/v1`** |
| `/data/full/pab.db` | 138,854,400 B, **stale** | → **`/data/v1/pab_stale_2026-08-20.db`** |
| `/data/fit_chains` (19 G) | 14,633 files | → **`/data/v1/fit_chains`** (14,633, verified) |
| — | — | **`/data/v2/{fit_chains,pipeline}`** created |
| `/data/src` (2.9 M) | retired checkout | **deleted** |
| `/data/run1k`, `/data/val`, `/data/valj1`, 5 loose files | | untouched |

`du -sh`: `/data/v1` **45 G**, `/data/v2` **116 M**, `/data/run1k` 507 M,
`/data/val` 2.3 M, `/data/valj1` 577 K. Volume **46 G of 500 G, 455 G free** —
ample for the ~17 GB of v2 chains.

**Two corrections to the doc's stated layout**, now measured: `fit_chains` is
**14,633** files (the doc said 14,654), and `/data/valj1` (577 K) plus five
loose top-level files exist that the task did not mention. Left alone, as they
were outside the instruction.

**The rename is the substantive decision.** `/data/full/pab.db` was never the
published v1 — it is 138,854,400 B against the release's 169,938,944 B and
sha `09de0a6d…`. Renaming it to `/data/v1/pab.db` would have put a *different*
database at the one path `HOWTO.md` §5b pins by checksum. `/data/v1/pab.db`
is now **absent** rather than wrong. Recorded in `HOWTO.md`, along with the
fact that `fits.chains_path` in the v1 DB still records the old
`/data/fit_chains/...` paths — deliberately not rewritten, since v1 is frozen,
so prepend `/data/v1` when resolving them.

### Task 3 — stage v2 on the PVC (2026-09-17): **done**

`/data/v2/pab.db` in place and **verified byte-identical**:

| check | result |
|---|---|
| size | 120,635,392 B, both ends |
| **sha256 in-pod** | **`ef552419174507eb25c77da7ea72484646d3ce162dc2f51259b438d8c127b735`** |
| sha256 workstation | **identical** |
| `PRAGMA user_version` | **5** |
| `matchup_pixels` v5 columns | all four present |
| `fits` v5 columns | all six present |
| `PRAGMA integrity_check` | `ok` |

Contents: 881 floats / 54,031 profiles / 67,435 granules / 14,610 matchups /
146,100 pixels / 14,609 `NASA_GIOP` fits / 116,872 `fit_results` /
14,586 non-null `scene_path`. **0 BING fits and 0 filled geometry** — expected,
and Prompt 5's first job.

The in-pod schema check was worth doing rather than trusting the checksum
alone: a matching sha proves the bytes arrived, but `user_version = 5` plus the
column lists is what proves the *right* database was staged. A v4 copy would
have been fitted without the geometry columns and failed much later.

**The workstation copy is now `chmod a-w`** (`-r--r--r--`), verified: a
`CREATE TABLE` against it raises `attempt to write a readonly database`, while
read-only opens still work. `/data/v2/pab.db` is the single writer's copy until
Prompt 7 brings it back.


### Task 4 — in-pod validation of `pab:2.0.0` (2026-09-17): **gates passed; one real bug found and fixed**

New `nautilus/v2_validate_job.yaml` + `nautilus/v2_validate_gates.py` (mounted
as a ConfigMap). The gate script **exits non-zero** on failure rather than
printing numbers to be eyeballed — a validation job should go red when 2.0 is
wrong.

**Job succeeded.** 5 profiles → 12 granules → 1 matchup → 10 pixels → 1 fit.
Every gate passed:

```
PASS schema is v5 / matchups exist / fits exist
PASS every pixel has geometry — 10/10
PASS geom_source is L1B_V3
     geometry ranges: theta_s 41.38..41.42  theta_v 31.41..31.62  dphi 14.57..14.94
PASS theta_s / theta_v / dphi physical and wrapped
PASS fits.rt_backend='robust_hybrid' include_raman=1 include_chl_fl=1
     include_cdom_fl=0 fit_bp=1 phi_c=0.02 wave_max=700.0 pab_version='2.0'
PASS fit_id is version-aware — …_ExpBPow_v2.0
PASS pkg_versions has robust — 0.0.dev0
PASS git_sha has all five repos, none "unknown"
PASS bbp700 4.376e-04 / Bp 0.0108 / chisq 0.58 / accept_frac 0.257
PASS chains under /data/v2val/fit_chains — shape (10000, 16, 6), 0.97 MB
PASS chain filename is version-aware
```

**The provenance chain is proven end to end**: the SHAs went image build →
`PAB_GIT_SHAS` env → running process → `pkg_versions` JSON on the persisted
row, with no `"unknown"`. The geometry stage worked in-pod on a live CMR lookup
plus a 1.8 GB L1B read — 2.0's one new external dependency.

**In-pod timings** (single fit, `--jobs 4`, whole run ~8 min):

| stage | wall |
|---|---:|
| ingest (5 profiles) | 73 s |
| discover | 15 s |
| match | 75 s |
| **geometry** (1 granule, 10 px) | **47 s** |
| **fit** (1 fit) | **226 s** |
| figure | 10 s (failed — see below) |

**`s/fit` in-pod is ~226 s**, above the workstation's ~101 s uncontended and
~181 s under 3-way contention. Prompt 5 should size from 226 s, not the
workstation numbers — but note this is **one** fit including JAX's first
compile, so it is an upper bound and the amortised figure over thousands will
be lower. Likewise the 47 s geometry is one granule including pool startup
against the workstation's ~9 s/granule; worth re-measuring on a bigger slice
before committing to an 11,494-granule budget.

**The bug the run found.** The `figure` stage failed for the fit, and — the
part that matters — **my gates reported ALL PASSED anyway**, because they only
queried the database and a stage that writes nothing leaves nothing to query.
Full detail and the rebuild question in **Q4**; in short, `fit_fig` passed a
per-sample `B_p` array where `robust` wants its `(nsamples, nwave)` batched
layout. Fixed in `reconstruct_rrs::_broadcast_bp`, verified by rendering a
figure from a real `robust_hybrid` fit, two regression tests added (one through
the **unmocked** backend), and the gate script now checks the figures exist and
that `fits.figure_path` was recorded. Suite **336 passed**.

**One stale gate in this doc, corrected in the script:** the task text says
`wave_max=720.0`, but JXP's Q2 answer in Prompt 3 moved 2.0 back to **700**.
The gate asserts 700, and the fit persisted 700.

`/data/v2val` deleted as instructed. PVC back to `/data/v1` 45 G + `/data/v2`
116 M, 46 G of 500 G used.


### Task 5 — `build_v2_prompt_5.md` updated + `:2.0.1` rebuilt (2026-09-17): **done**

**`:2.0.1` built** (Q4 answer: option (a)). The PAB tree was **clean at
`8c7ab8a`** before staging — checked deliberately, because the build rsyncs the
*working tree* while `git_shas()` reads `git rev-parse HEAD`: an uncommitted fix
would have produced an image whose provenance names a commit that does not
contain it, which is exactly the lie the SHA exists to prevent.

All guards passed again, including the off-nadir regression test
(`ROBUST OK … std 0.0245`) and `PAB 2.0 OK robust_hybrid 400.0 700.0`. Baked
provenance now `{"PAB":"8c7ab8a", …,"retrieve-or-bust":"e1f4289"}`. Pushing
`:2.0.1` + `:latest`.

**`build_v2_prompt_5.md` updated.** Every number checked against the live
store rather than carried forward.

- **Image `:2.0.0` → `:2.0.1`** in Task 2, with the reason in the agreements —
  `:2.0.0`'s `figure` stage fails for every 2.0 fit.
- **`PYTHONWARNINGS=ignore` is now a stated requirement for every 2.0 job.**
  Not cosmetic: the `DomainWarning` flood buried the figure traceback in the
  Prompt 4 validation until it was suppressed.
- **The as-built PVC and database state** — `/data/v2/pab.db` sha, schema v5,
  the counts, and the one that matters here: **0 of 146,100 pixels have
  geometry**, so Task 5 owns the entire backlog. Plus `/data/v1`'s layout and
  the absent `v1/pab.db`.
- **The measured in-pod costs, labelled as upper bounds.** 47 s/granule and
  226 s/fit are each a *single* startup-dominated measurement; the workstation
  figures disagree 5× and 2×. I wrote the naive projections out (geometry 4–22 h,
  fit 29–66 h) specifically so the *spread* is visible, and changed Task 5's
  geometry step to **measure a ~200-granule slice before committing** rather
  than book a day-long job off one data point.
- **Two findings about the `geometry` stage**, verified in the code:
  it issues **one uncached CMR query per granule** (~13.5 k searches), so
  Task 5's `--jobs 16` would mean 16 concurrent CMR searches against the same
  shared infrastructure the doc's own agreements cap at `--discover-jobs 8` —
  **recommended `--jobs 8`**, flagged rather than silently changed; and it is
  idempotent on `theta_s IS NULL`, so the gate's "sweep re-run" is simply
  running the stage again, with zero network work for filled pixels.
- Confirmed by query that the existing granule count is **11,494**.
- Added a Task 6 ("update `build_v2_prompt_6.md`"), flagged as removable.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-17 (Prompt 4 Tasks 1–3 — image 2.0.0 built and pushed, PVC re-laid out, v2 staged)

`pab:2.0.0` is on the registry at digest `sha256:1afd4cc9…`, the PVC is
`/data/v1` + `/data/v2`, and `/data/v2/pab.db` is staged and checksum-verified.

What I learned / want to remember:

- **The image build was broken for everyone and nobody knew.** `bing/setup.py`
  pins `retrieve-or-bust @ git+…@cdom-rt`; that branch was merged and deleted
  from the remote, so `pip install ./bing` now fails with
  `pathspec 'cdom-rt' did not match any file(s)`. It worked five weeks ago at
  1.0.3. A direct-reference dependency on a *branch* is a time bomb: it is
  fine until someone tidies up the branch list, and then an unrelated build
  fails with a message that points at git rather than at the pin. I fixed it in
  the staged copy only — the live pin serves ReadTheDocs, where there is no
  local checkout, and that is bing's call to change.
- **"Fix it in the staging copy" beat both alternatives.** Editing bing would
  have broken its ReadTheDocs build; `--no-deps` on bing would have silently
  dropped ~25 real dependencies. Modifying the *artifact of a build step*,
  with a `grep` guard that reports when the upstream pin is repaired, keeps the
  blast radius to this image.
- **A smoke test that only asserts "no exception" cannot catch a wrong
  number.** The prompt originally asked for a guard that imports `robust.rt`
  and runs one forward call — which passes happily on the broken emulator,
  because a saturated network still returns a float. Asserting the correction
  *varies across the band* costs the same and is the actual regression test. It
  passed (std 0.0245), so the shipped image demonstrably contains `e1f4289`.
- **Renaming the stale DB was the right call and worth the question.** Doing
  what the task literally said — `mv /data/full /data/v1` — would have created
  `/data/v1/pab.db` holding a database that is *not* the v1 release, at the one
  path `HOWTO.md` defines by sha256. Absent beats wrong: someone checking the
  PVC against the documented checksum now gets "no such file" rather than a
  mismatch they have to explain.
- **Verify the schema, not just the checksum.** The sha proves the bytes
  survived the wire; `PRAGMA user_version = 5` and the column lists prove the
  *right* file was sent. Those are different failures, and only the second
  catches "you staged last month's copy".
- CephFS renames within one volume are metadata-only: 19 G of chains (14,633
  files) moved instantly. Worth knowing before anyone plans a maintenance
  window for a PVC re-layout.
- Measured, not assumed: `fit_chains` holds **14,633** files, not the 14,654
  the doc carried forward, and there are two directories plus five loose files
  on the PVC that no task mentions. I left everything unmentioned alone.

### 2026-09-17 (Prompt 4 Task 4 — in-pod validation: every gate green, and a real bug underneath)

`pab:2.0.0` ran the full seven-stage pipeline on Nautilus. Geometry, fit,
schema v5, version-aware ids, chains and provenance all validated in-pod. The
`figure` stage failed, my gates did not notice, and that is the most useful
thing that happened today.

What I learned / want to remember:

- **A gate set that only queries the database cannot see a stage that produced
  nothing.** Every one of my ~25 checks passed while `figure` failed for the
  only fit in the run, because a failed stage writes no row to contradict. The
  job even exited 0. I have added a figures-on-disk check and a
  `fits.figure_path` check, but the general lesson is the one to keep: when
  validating a pipeline, assert on **artefacts produced**, not only on rows
  that exist — "nothing was written" and "nothing was checked" look identical.
- **The bug was invisible locally for two compounding reasons.** The other
  caller of `reconstruct_rrs` (`_fit_diagnostics`) passes a *scalar* `B_p`,
  which broadcasts fine; and my dispatch unit tests **mocked**
  `calc_Rrs_from_models_robust` to assert routing. So nothing ever pushed a
  real *batch* through the real backend — and Prompt 3 Task 6 fitted 60
  spectra without rendering a single figure. Mocking the thing you are
  integrating with tests the call, not the contract. The new regression test
  deliberately uses the unmocked backend.
- **BING had already solved it, and I hand-rolled instead.**
  `evaluate.reconstruct_from_chains` does the same peel-and-broadcast, with the
  `(nsamples, nwave)` convention documented in its own docstring. Had I looked
  for an existing helper when writing `fit_fig`'s reconstruction in Task 5, the
  shape question would never have arisen. I fixed it at my dispatch point
  rather than switching wholesale, because `reconstruct_from_chains` returns
  ±σ bands while the figure draws 5–95 percentiles — but the reuse instinct
  should have fired first.
- **In-pod is ~2× slower per fit than the workstation** (226 s vs ~101 s
  uncontended). I am reporting it as an upper bound rather than a cost model:
  it is a single fit including JAX's first compile, and the geometry figure
  (47 s for one granule vs ~9 s locally) is similarly startup-dominated. One
  sample is a data point, not a rate — Prompt 5 should re-measure on a real
  slice before booking cluster time.
- The `PYTHONWARNINGS=ignore` in the manifest did its job: no `DomainWarning`
  flood, and the log stayed readable enough that the figure traceback was
  visible at a glance.

### 2026-09-17 (Prompt 4 Task 5 — rebuilt :2.0.1 and handed Prompt 5 the measured state)

`:2.0.1` built from a clean tree at `8c7ab8a` with the `B_p` fix, and
`build_v2_prompt_5.md` updated with what Prompts 1–4 actually established.

What I learned / want to remember:

- **Check the tree is clean before baking a SHA into an image.** The build
  stages the *working tree* by rsync, but `git_shas()` records
  `git rev-parse HEAD`. Build with an uncommitted fix and the image's
  provenance names a commit that does not contain the code inside it — a
  precisely wrong answer, worse than `"unknown"`, and undetectable later. It
  happened to be clean; it was worth the one command to find out.
- **The most useful thing I put in Prompt 5 was a spread, not a number.** I
  have two cost measurements that disagree 5× (geometry) and 2× (fit), both
  from single startup-dominated samples. Writing "47 s/granule" alone would
  have been treated as a rate and turned into a cluster booking. Writing
  "4–22 h depending on which measurement you believe, so measure a 200-granule
  slice first" is honest about what is actually known and converts the
  uncertainty into a cheap action.
- **`--jobs 16` on `geometry` is a manners problem, not just a speed knob.**
  The stage does an uncached CMR lookup per granule, so the job's parallelism
  is also its CMR concurrency — ~13.5 k searches, 16 at a time, against shared
  NASA infrastructure that the same document already agrees to hit 8-wide. I
  flagged it with the reasoning instead of quietly editing the number, because
  it is the kind of thing the author may have decided deliberately.
- Carried forward the small operational facts that are invisible until they
  bite: `PYTHONWARNINGS=ignore` (a correct warning, thousands of lines per
  fit), the gate-script-exits-non-zero pattern, and that `/data/v1/pab.db`
  deliberately does not exist.
