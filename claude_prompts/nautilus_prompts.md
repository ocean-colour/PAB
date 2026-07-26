# Processing the full PAB run on Nautilus

## Goals

The full selection needs to **read 124,218 PACE granules (18.55 TB)** to build
matchups — infeasible off-cloud on the workstation (~2× its free disk, ~weeks).
This doc explores **running the whole pipeline on NSF/Nautilus** (Kubernetes +
Ceph + S3), where compute and storage are **co-located** — so the granule reads,
the 124k fits, and the artifact store all live in one place, and the workstation's
9.8 TB limit stops mattering. Deliverable: a concrete, safe plan (and, once the
open questions resolve, execution) for a version-stamped `pab_version = 1.0` run
on Nautilus.

## Claude

### Skills

- **`batch-fit-argo`** — batch/parallel-fit + checkpointing; the fit fan-out.
- **`run-bing-fit`** — the per-spectrum fit.
- **`diagnose-mcmc`** / **`debug-priors`** — convergence triage at scale.

### Working agreements (unchanged from Stages 0–9)

- **Git is handled by the user.** No state-changing git commands.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Drive the existing `pab` CLI / stage functions;
  containerize them, don't fork them.
- **Nautilus is not backed up.** Everything we want to keep is also copied to the
  Google Shared Drive **`AIOcean:`** via rclone (per N5: back up *everything*).
- **Outward-facing infra needs confirmation.** Creating namespaces, pushing images,
  staging TBs, or launching large jobs is confirmed with the user first (quotas +
  cost are shared on the National Research Platform).

## Context

Read these before running:

- **Parent run doc** — `claude_prompts/run_full_pipeline.md` (Q1–Q11 + N1–N6, the
  pilot, the 18.55 TB discover-count, and why off-cloud was ruled out).
- **Operator guide / design / implementation** — `HOWTO.md`,
  `docs/design/PAB_design.md`, `docs/design/PAB_implementation.md`.

**What's decided / known:**

1. **Selection:** 54,506 profiles / 882 floats, window 2024-03-05→today, filter
   `BBP700` or `CHLA`. CSV: `$PAB_DATA_DIR/full_profiles.csv`.
2. **Granule volume:** 124,218 unique PACE `L2_AOP` granules = **18.55 TB**
   (157 MB avg), 5.67 candidates/profile.
3. **Storage:** Nautilus S3 endpoint `https://s3-west.nrp-nautilus.io`, bucket
   **`s3://pab`** (now **public read-only**; writes via creds). rclone remotes:
   `nautilus_s3:` (→ Nautilus S3), `AIOcean:` (→ Google shared drive, backup),
   `GDrive:`. `kubectl` context `nautilus` is active on the workstation.
4. **Code is scale-ready:** parallel `fit_batch` (`--jobs`), tqdm suppressed,
   `ingest` per-profile resilient, schema auto-migrates to v3, `pab_version = 1.0`.
5. **The pivot (N4):** run **compute on Nautilus**, not storage-only — so the
   18.55 TB reads happen where the data/compute live.

**The crux to resolve first:** Nautilus nodes are spread across the US, **not** in
AWS `us-west-2` where PACE L2 lives. So the key unknown is **Nautilus↔NASA-AWS
throughput**: can a pod lazily read PACE granules from NASA S3 fast enough
(~MB/pixel, the design's lazy path), or must we **stage the 18.55 TB into Ceph/S3
once** and read locally? Task 1 measures this before we commit to either.

## Prompts

1. Execute the first task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below
6. Execute the 6th task in Tasks below
7. Execute the 7th task in Tasks below

## Tasks

1. **Measure Nautilus↔NASA granule-read performance (decides everything).** Launch a
   small CPU pod in the sea-meets-the-stars namespace (see example YAML files in the nenya Repository), 
   install/`pab`-image (we will need to create this), and time `earthaccess`
   lazy reads (open + nearest-pixel extract) of a handful of real PACE granules from
   NASA `us-west-2` S3 — compare to the workstation's ~17 s/granule. If lazy reads
   are fast, we skip staging (read NASA S3 directly from pods). If slow/hangs, plan
   a one-time **stage-to-Ceph/S3** of the candidate 18.55 TB. Log the numbers +
   the decision. **Put open questions in Q&A.**

2. **Q&A**.  I have answered the questions in the Q&A section below.  Please read them and respond to them in the Q&A section below, as needed.  Log your work.

3. **Containerize PAB.** Build a Docker image with `pab` + `bing` + `ocpy` +
   `argopy` + `earthaccess` + the sci stack (editable-install the repo; entrypoint =
   the `pab` CLI). Push to the registry (NRP GitLab registry vs Docker Hub — see
   Q&A). Smoke-test `pab --dry-run` in the image.

4. **Namespace, secrets, storage.** Confirm/request a PAB K8s namespace (+ quota);
   create secrets for the Earthdata `~/.netrc`, Nautilus S3 creds, and the rclone
   config (AIOcean). Provision a **CephFS/RBD PVC** for the SQLite `pab.db` +
   working dir; decide granule location (Ceph PVC vs `s3://pab`) and artifact
   location (`s3://pab` + AIOcean backup).

5. **Data-access + DB strategy.** Wire the read path from Task 1 (lazy NASA-S3 vs
   staged Ceph/S3). Keep the SQLite DB on the shared PVC (single-writer — our
   stages write from one process, so it's safe) or reconsider if fan-out needs
   concurrent writers. Confirm `--emit-site`/artifacts land on `s3://pab`.

6. **YAML fix.**  I have looked at the logs for the `inspect_pod.yaml` run and they give:

```
/bin/bash: line 4: warning: here-document at line 1 delimited by end-of-file (wanted `EOF')
/bin/bash: -c: line 4: syntax error near unexpected token `('
/bin/bash: -c: line 4: `echo "=== /data tree ==="; find /data -maxdepth 3 -type f 2>/dev/null | head -40; echo "=== /data usage ==="; du -sh /data/* 2>/dev/null; echo "=== db counts ==="; python - <<'EOF' import os, sqlite3 db="/data/val/pab.db" if not os.path.exists(db): print("NO pab.db at", db); raise SystemExit c=sqlite3.connect(db) for t in ("profiles","granules","matchups","matchup_pixels","fits","fit_results"):
```
Modify the file in `nautilus/inspect_pod.yaml` to fix the syntax error and I will relaunch the pod.  If you have any questions, ask them in the Q&A section below.  Log your work.  Use Fable if you can.

7. **Run the pipeline as K8s Jobs.** ingest → discover → match → fit → figure →
   report via the containerized `pab` CLI. Fan out the heavy stages (match/fit)
   across pods where safe; rely on stage idempotency/resume for preemption. Monitor
   progress, disk/quota, and failures. Log per-stage counts + wall-clock.

8. **Publish + back up.** Implement + wire `NautilusS3Backend` (upload artifacts to
   `s3://pab`, real URLs in the manifest); emit `report_site/` and push to RTD; then
   **rclone everything to `AIOcean:PAB/`** (N5). Log published counts + backup.

9. **Verify & close out.** Spot-check matchups, confirm `pab_version = 1.0` on every
   record, update `docs/design/PAB_implementation.md` + `HOWTO.md` (§7b → activated),
   and write the full-run report. Log your work.

## Q&A

**M1 — Namespace & quota.** Do you already have a Nautilus/NRP namespace for this
(name? CPU/mem/storage quota?), or should we request one? (Storage-only didn't need
it; compute does.)
>A. Yes, use the `sea-meets-the-stars` namespace.  I have already created it.  And, no, there is no storage quota needed.

**M2 — Container registry.** Push the PAB image to the **NRP GitLab registry**
(`gitlab-registry.nrp-nautilus.io/...`) or **Docker Hub**? Any existing base image
with the sci stack you prefer?
>A. Yes, let's push to the NRP GitLab registry.  I do not have a preferred base image. Please provide me instructions on what to do in the Container section below.
>
>**Claude (Task 2) →** Instructions written in the **Container** section (create a
>GitLab project + a `write_registry` deploy token + `docker login`; base image
>`python:3.12`). Two things I need back: the registry path and public-vs-private.

**M3 — Nautilus↔AWS connectivity.** Any prior knowledge of read throughput from
Nautilus pods to NASA `us-west-2` S3 (or should Task 1 just measure it)? Do the
`pace-ucicl` namespace / `modis-l2` bucket owners have a pattern we can mirror?
>A. **RESOLVED by Task 1** — measured ~4.4 s/granule (open+pixel), reliable, ~4×
>the workstation. Good enough; no prior pattern needed.

**M4 — Granules: lazy-read vs stage-to-Ceph.** If Task 1 shows lazy NASA reads are
slow, are you OK with a **one-time 18.55 TB stage into Ceph/`s3://pab`** (uses a big
chunk of quota) — or would you rather **subsample** at that point?
>A. **RESOLVED by Task 1 — lazy-read, NO staging.** Lazy reads from Nautilus are
>fast + reliable and move only ~MB/pixel, so the 18.55 TB never downloads. (M1
>namespace = `sea-meets-the-stars`, confirmed. **M2 registry + M5 compute-shape
>still open** for Task 2/Task 5.)

**M5 — Compute shape.** CPU-only is fine (BING MCMC is CPU-bound; no GPU). How many
cores/pods can we reasonably use (fair-use)? Preemption is fine given resumable
stages — confirm?
>A. We can use 50 cores for sure.  Why do you want to use multiple pods?
>
>**Claude (Task 2) →** Good push-back — **we don't need multiple pods.** One pod
>with **50 cores** is simpler *and* safer: all stages write one local SQLite DB, so
>there's a single writer (multiple pods sharing a DB on a CephFS/RBD volume would
>fight over SQLite locks — it's notoriously unreliable for concurrent writers). The
>only reason I mentioned pods: the `fit` stage already parallelizes across cores
>(`--jobs`), but the **`match` stage is still serial in code** — one process would
>do the ~304k granule opens one-at-a-time (~15 days). The fix isn't more pods, it's
>to **parallelize `match` in code** exactly like `fit` (workers open+extract; the
>main process does all DB writes). Then a single 50-core pod runs match (~7–8 h at
>50×) + fit (~1 h) against one SQLite — no multi-writer risk. **Plan: 1 pod × 50
>cores + a small "parallelize match" code task** (I'll add it before the run;
>folds in near Task 6). Preemption-resilience still matters (the pod can be
>evicted) — the stages resume, so it's fine.

## Container

Image goal: one image with `pab` + `bing` + `ocpy` + `remote_sensing` +
`earthaccess`/`argopy` + the sci stack, entrypoint = the `pab` CLI, pushed to the
**NRP GitLab registry** (M2). All four repos are public on GitHub
(`ocean-colour/{PAB,bing,ocpy}`, `Sea-Meets-the-Stars/remote_sensing`) **but** this
session's fixes (parallel `fit_batch`, `ingest` resilience, `moving_median`,
`pab_version=1.0`) are **uncommitted** — so the image should be built from the
**local working tree**, not a fresh `git clone`. Conveniently, all four repos live
under one parent: `/mnt/tank/Oceanography/python/` → that's the Docker build context.

### What you need to do on NRP GitLab (one-time)

1. **Create a project** at `https://gitlab.nrp-nautilus.io` — e.g. name it `pab`
   under your user/group. Its image path becomes
   `gitlab-registry.nrp-nautilus.io/<your-namespace>/pab`.
2. **Make a registry credential** for `docker login`: project → **Settings →
   Repository → Deploy tokens** → create one with **`read_registry` +
   `write_registry`** (note the token *username* + *token*). (A Personal Access
   Token with `write_registry` also works.)
3. **Tell me two things:** the exact registry path (`gitlab-registry.nrp-nautilus.io/…/pab`)
   and whether the project is **public** (pods pull with no secret) or **private**
   (I'll add an `imagePullSecret` to `sea-meets-the-stars`).
4. On the build host (this workstation — confirm `docker` is installed), log in:
   `docker login gitlab-registry.nrp-nautilus.io -u <token-user> -p <token>`.

### What I'll do (Task 3)

Add a `Dockerfile` (below) + `.dockerignore` (skip each repo's `.git`,
`report_site/_build`, caches), then from `/mnt/tank/Oceanography/python`:

```bash
docker build -f PAB/Dockerfile -t gitlab-registry.nrp-nautilus.io/<ns>/pab:1.0 .
docker push gitlab-registry.nrp-nautilus.io/<ns>/pab:1.0
docker run --rm gitlab-registry.nrp-nautilus.io/<ns>/pab:1.0 --dry-run   # smoke test
```

Draft `Dockerfile` (build context = the python/ parent):

```dockerfile
FROM python:3.12
ENV MPLBACKEND=Agg PIP_NO_CACHE_DIR=1
RUN pip install --upgrade pip
WORKDIR /opt/src
# local working tree (captures this session's uncommitted fixes), deps first
COPY remote_sensing/ remote_sensing/
COPY ocpy/ ocpy/
COPY bing/ bing/
COPY PAB/ PAB/
RUN pip install ./remote_sensing ./ocpy ./bing ./PAB \
    earthaccess argopy gsw healpy emcee bokeh boto3 \
    sphinx sphinx-rtd-theme
ENTRYPOINT ["pab"]
```

(If you'd rather I build from committed GitHub sources instead, commit + push the
PAB/bing changes first and I'll switch the `COPY`s to `pip install git+https://…`.)

## Reports

### Nautilus

#### Task 1 — granule-read measurement (decisive: lazy-read wins)

Launched a CPU Job (`python:3.12-slim`, 2 CPU) in `sea-meets-the-stars` that
`earthaccess.open`s 4 real PACE `L2_AOP` granules from NASA `us-west-2` and reads a
pixel's spectrum, timing open vs pixel separately (netrc via a new
`earthdata-netrc` secret; script via the `pab-readtest` ConfigMap).

| | **Nautilus pod (lazy)** | workstation (pilot, `--download`) |
| --- | --- | --- |
| open | **~3.1 s** | ~14–21 s |
| pixel read | **~1.3 s** | — |
| **total / granule** | **~4.4 s** | ~17 s (+ 141 MB downloaded) |
| reliability | 4/4, no hangs | 2 h wedge out-of-region |
| bytes moved | **~MB/pixel** | full ~141 MB granule |

**Decision: read lazily from Nautilus pods — NO staging.** Nautilus↔NASA is fast
and reliable (~4× the workstation) and, being lazy, transfers only the pixel chunks
— so **the 18.55 TB is never downloaded** (answers **M4**: no stage-to-Ceph needed;
resolves **Q11**: it's the design's "in-region" lazy path, just from Nautilus). At
~4.4 s/granule-open, the ~304k match opens fan out across pods (e.g. ~50 pods →
~hours) with no bulk transfer and no disk pressure.

*Follow-up noted for the match stage:* the current engine opens a granule **once per
profile** (≈304k candidate refs), not once per unique granule (124k) — grouping/
caching opens per granule, or fanning out by granule, would roughly halve the opens.
Not a blocker (parallelism dwarfs it), but a cheap win. Cleanup: the throwaway Job
self-deletes (ttl 1 h); kept the `earthdata-netrc` secret + `pab-readtest` ConfigMap
for the next pod.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-07-14 (Task 1 — Nautilus granule-read measurement; lazy-read wins)

Ran the measurement in `sea-meets-the-stars` (nenya Job pattern). Created an
`earthdata-netrc` secret (none existed) + `pab-readtest` ConfigMap; a
`python:3.12-slim` CPU Job `earthaccess.open`ed 4 PACE `L2_AOP` granules from NASA
`us-west-2` and read a pixel each. First pass failed (`h5netcdf` needs `h5py`, not
auto-pulled) — added `h5py`+`netcdf4` and re-ran.

**Result: ~3.1 s open + ~1.3 s pixel = ~4.4 s/granule, 4/4, no hangs** — ~4× faster
than the workstation's ~17 s and **lazy** (only ~MB/pixel moves, not the 141 MB
granule). **Decision: run compute on Nautilus with lazy reads, no staging** — the
18.55 TB never downloads. This resolves the read-path question (Q11 / M4): it's the
design's in-region lazy path, delivered from Nautilus pods; the ~304k match opens
parallelize across pods (~hours) with no disk pressure. Flagged a cheap follow-up:
`match` opens a granule per-profile (~304k) rather than per-unique-granule (124k) —
group/cache to ~halve opens. Kept the netrc secret + ConfigMap for the next pod;
the Job self-deletes (ttl). No package code changed.

### 2026-07-14 (Task 2 — answered the Q&A; wrote Container instructions)

Read M1–M5 answers and responded in Q&A. **M1** sea-meets-the-stars (no quota) —
noted. **M2** NRP GitLab registry — wrote step-by-step in the new **Container**
section (create GitLab project → `write_registry` deploy token → `docker login`;
draft `Dockerfile` on `python:3.12`; build from the **local working tree** under
`/mnt/tank/Oceanography/python` since this session's fixes are uncommitted — all
four repos are public on GitHub but the image must capture the current code).
Confirmed `docker` 29.6 is on the workstation. Need back from the user: the exact
registry path + public/private.

**M5 (the substantive one):** answered "why multiple pods" — **we don't need them.**
One 50-core pod is simpler + avoids the SQLite concurrent-writer hazard (multiple
pods on a shared CephFS/RBD DB fight over locks). The real gap is that **`match` is
still serial in code** (only `fit` parallelizes via `--jobs`); the fix is to
**parallelize `match` in-code** like `fit` (workers open+extract, main writes),
then a single 50-core pod does match (~7–8 h) + fit (~1 h) against one DB. Added
"parallelize match" to the plan (near Task 6). No package code changed this task.

### 2026-07-15 (Task 3 — built the PAB image; push pending `docker login`)

Registry (M2): `gitlab-registry.nrp-nautilus.io/profx/pab`, **Public** (→ no
imagePullSecret needed). Wrote `PAB/Dockerfile` (base `python:3.12`, entrypoint
`pab`). **bing is 94 GB** (papers/posters) — so built from a **staged 90 MB
context** (rsync of the four packages minus `.git`/`papers`/`posters`), capturing
the **local working tree** (this session's uncommitted fixes). Build succeeded;
the in-build import check + `docker run … --dry-run` both confirm **`pab 1.0`** and
a working CLI. Image `…/profx/pab:1.0` (+`:latest`), **7.63 GB**.

**Push is blocked on the user's `docker login`** (deploy token stays with them;
`~/.docker/config.json` shows not-logged-in). Observation: 7.63 GB is bloated by
`torch` + NVIDIA CUDA libs pulled transitively via `remote_sensing`/`ocpy` — unused
by PAB's CPU pipeline; offered to slim later (non-blocking). `docker` 29.6 on the
host. Next: on "logged in", push + verify in the registry. Code changed: added
`PAB/Dockerfile`.

**Update (pushed):** user logged in; `docker push` of both tags succeeded and
`docker manifest inspect` confirms **`pab:1.0` + `:latest` are in the registry**
(public → pods pull with no secret). **Task 3 done.**

### 2026-07-16 (Task 4 — namespace, secrets, storage)

Namespace `sea-meets-the-stars` confirmed (M1). **Secrets** now in place:
`earthdata-netrc` (Task 1), `prp-s3-credentials` (existing; key `credentials` =
`.aws/credentials` for Nautilus S3), and a new **`rclone-config`** (from
`~/.config/rclone/rclone.conf`; remotes GDrive/AIOcean=drive, nautilus_s3=s3 — for
the AIOcean backup). **PVC `pab-data`** created **500Gi RWX** and **Bound**.

Storage-class gotcha (learning): the listed `cephfs`
(`rook-ceph.cephfs.csi.ceph.com`) never provisioned (Pending 11 min) — the
namespace's working PVCs use **`rook-cephfs`** (`rook-system.cephfs.csi.ceph.com`);
recreated on that → Bound in seconds. Use `rook-cephfs` for future PVCs.

**Storage layout decided:** granules **lazy-read from NASA** (Task 1 — never stored
on PVC/Ceph); the SQLite `pab.db` + working dir (chains, figures, argo_qa,
report_site) live on **PVC `pab-data`** during the run; artifacts publish to
**`s3://pab`** + back up to **`AIOcean:PAB/`** (N5).

Flag for Task 5/6: at the default `FitConfig.nsteps=10000`, MCMC chains are ~13 MB
each × ~13.6k matchups ≈ **~180 GB** — fits in 500Gi alongside the DB/figures, but
we should **upload chains to `s3://pab` and evict locally as they're produced** (or
thin them) so the PVC doesn't fill. No package code changed (kubectl infra only).

### 2026-07-19 (Task 6 — fixed inspect_pod.yaml YAML/heredoc bug)

The `pab-inspect` pod errored (`syntax error near unexpected token '('`). Cause:
`args: - >` is a YAML **folded** scalar → newlines become spaces, so the
`python - <<'EOF' … EOF` here-doc flattened onto one line (the `EOF` terminator
never matched and the multi-line python collapsed). Fix (delegated to a **Fable**
subagent, per the user's ask): switched `>` → `|` (literal block, newlines kept)
and replaced the here-doc with a single-line `python -c` counts query. `yaml.safe_load`
confirms it parses. User will relaunch. No package code changed (manifest only).

Process learning for all embedded-script K8s manifests: use `|` (literal), never `>`
(folded), for shell/python blocks — and prefer a one-line `python -c` over a
here-doc to avoid indentation/terminator-column pitfalls.

### 2026-07-22 (Task 5 — in-container validation passes end-to-end; six image/packaging bugs fixed)

Drove a 5-profile validation Job (`nautilus/validate_job.yaml`, float 1901614)
to a **clean pass on the final image** (`…/profx/pab:1.0`, digest
`49c83e9…`): `ingest 5 / discover 12 / match 1 (10 px) / fit 1 / figure 1 /
report 7-page site`; DB counts `profiles 5 · granules 12 · matchups 1 ·
matchup_pixels 10 · fits 1 · fit_results 10`. This confirms the whole cloud
path in-pod: container + `pab-data` PVC + secrets (netrc/S3) + **lazy S3 reads**
(no `--download`) + **parallel `fit` (`--jobs 4`)** + reporting.

Getting there uncovered **six bugs**, each caught *before* the next rebuild by
exercising the real code path against the image (so one rebuild per fix, not
blind iteration):

1. **argopy/erddapy skew** → `cannot import name '_quote_string_constraints'`,
   0 profiles. Fix: pin `argopy==1.4.0 erddapy==3.2.1` + build guard.
2. **earthaccess never logged in** → `match` open: `'NoneType' has no attribute
   'open'` (`earthaccess.__store__` is None). Masked on the workstation by a
   prior interactive login. Fix: guarded `earthaccess.login(strategy="netrc")`
   in `pab/pace/cloud.py::open_s3`.
3. **`bing/data` dropped by the wheel** — `bing` uses `find_packages()` with no
   `package_data`, so `pip install ./bing` omits `data/` (the
   `gordon_coefficients*.csv` every fit needs + adg `.mat`).
4. **`ocpy/data` dropped** — same gap; its Bricaud table loads at *import* of
   `bing.models.anw`. Fix (3+4): Dockerfile copies each pkg's `data/` into the
   installed location (path found via the module, no py-version hardcoding).
5. **`ocpy.hydrolight` missing `__init__.py`** → `find_packages()` dropped the
   whole subpackage from the wheel; `bing.models.bbnw` imports
   `ocpy.hydrolight.loisel23` on every fit. Works on the workstation only
   because editable installs expose the source (namespace-package). Fix: add
   `ocpy/hydrolight/__init__.py`.
6. **Loisel `Hydrolight400.nc` absent** — `bbNWModel.init_bbw` (base class → hit
   by *every* bbnw model incl. `ExpBPow`/`Pow`) calls `loisel23.load_ds(4,0)` to
   seed `bb_w` from `$OS_COLOR/Loisel2023/Hydrolight400.nc`. Fix: bundle the one
   18 MB file (not the 19 GB dataset) + `ENV OS_COLOR=/opt/os_color`.

Diagnosis notes: the fit failure was **not** a parallelism bug — `jobs=1`
(serial) failed identically in-pod while the same fit *succeeded* on the
workstation, pointing at environment/packaging, not the ProcessPool. Confirmed
by reproducing locally with the `try/except` removed and by a debug Job on the
current image. Also **added traceback logging** to the fit stage's four
swallowed `except` blocks (`pab/fit/run.py`) — silent per-fit failures across
54k profiles would be untenable; this is exactly how bugs 5/6 were isolated.

Build guard now imports `bing.models.anw`+`bbnw`, asserts the bing data
resolves, and runs `loisel23.load_ds(4,0)` (`LOISEL OK (81,)`), so a green build
means the full fit dependency chain is satisfied in-image. Code changed: PAB
`pab/pace/cloud.py`, `pab/fit/run.py`, `Dockerfile`; ocpy
`ocpy/hydrolight/__init__.py` (new). **Task 5 done.** Next: parallelize `match`
in-code (still serial), then a small **pilot** (few hundred–1k profiles) to
measure matchup rate / per-fit time / memory / chains storage before the full
54,506-profile run.
