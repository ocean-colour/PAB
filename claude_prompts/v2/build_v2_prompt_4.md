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

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
