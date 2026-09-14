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

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below

## Tasks

1. **Image.** Extend the staged build to include `retrieve-or-bust`
   (rsync `robust/` + `setup.py`, minus `.git`/notebooks/reports) and add
   `jax flax optax jaxtyping` to the `pip install`; a build guard that
   imports `robust.rt`, runs one `robust_hybrid` forward call, and imports
   `pab.fit.run`; `TAG=2.0.0`; `--label` the five git SHAs (Prompt 3 Task 3's
   seam — e.g. `PAB_GIT_SHAS` env baked in). Build, smoke-test `pab
   --dry-run` (**`--rm`, bounded**), then — after the user's `docker login`
   — push `:2.0.0` + `:latest` and verify with `docker manifest inspect`.
   Record the image digest. Log.

2. **PVC re-layout** (via a short-lived helper pod, confirm first): `mv
   /data/full /data/v1`; `mv /data/fit_chains /data/v1/fit_chains`;
   `mkdir -p /data/v2/fit_chains /data/v2/pipeline`; leave `/data/run1k`,
   `/data/val`; delete `/data/src` (retired). Note that `fits.chains_path`
   in the **v1** DB still says `/data/fit_chains/...` — leave v1 as is (it
   is frozen; record the path change in `HOWTO.md`). Report `du -sh` per
   dir. Log.

3. **Stage v2.** Copy the workstation `$PAB_DATA_DIR/v2/pab.db` (Prompt 1
   Task 3) to `/data/v2/pab.db` (`kubectl cp` via the helper pod, or an
   S3 hop through `s3://pab/v2/pab.db` if faster); verify sha256 both
   ends. From now on **`/data/v2/pab.db` is the single writer's copy**;
   mark the workstation copy read-only (`chmod a-w`) until Prompt 7 brings
   the DB back. Log.

4. **In-pod validation.** New `nautilus/v2_validate_job.yaml` from
   `validate_job.yaml`: image `:2.0.0`, `PAB_DATA_DIR=/data/v2val`, its own
   scratch DB (wiped — fine for a 5-profile smoke), stages `ingest →
   discover → match → geometry → fit → figure → report`, `--jobs 4`.
   Gates: geometry filled for every pixel (`geom_source` set), the fit
   succeeds with `rt_backend='robust_hybrid'`, 6-column chains under
   `/data/v2val/fit_chains`, `pkg_versions` carries `robust` + SHAs, JAX
   compiles in the spawned workers (log lines), no `theta_s` error. Report
   in-pod s/fit for one fit (first estimate of the 2.0 cost). Delete the
   scratch dir after. Log.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
