# Coding up PAB — Stage 8 (End-to-end pipeline & CLI)

## Goals

Implement **Stage 8** of the coding plan: the **semi-automated stage runner**
that ties Stages 2–7 together into one resumable, config-driven pipeline —
**discover → match → fit → figure → report** — plus a **CLI** entry point. This
is the integration stage: it adds **no new science**, only orchestration over the
modules already built (`pab.argo`, `pab.pace`, `pab.matchup`, `pab.fit`,
`pab.plotting`, `pab.report`), with each stage **idempotent and resumable** off
the matchup store.

We continue to be guided by the design document `docs/design/PAB_design.md`
(especially *Semi-automation* and *Provenance & versioning*) and the coding plan
`docs/design/PAB_coding_plan.md`, and we record what we build in
`docs/design/PAB_implementation.md`.

## Claude

### Skills

Reporting-style glue over the existing modules; a couple of fitting skills inform
the batch stage:

- **`batch-fit-argo`** — the batch/parallel-fit + checkpointing pattern (mirrors
  `pab.fit.build_fits` over the population; BING `fit_batch` across cores).
- **`run-bing-fit`** — the per-spectrum fit the batch stage invokes.

### Working agreements (unchanged from Stages 0–7)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written; do **not** copy
  the one-off `bing/papers/biomass/Analysis` scripts. Stage 8 should call the
  existing stage functions, not re-implement them.

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md` → *Semi-automation* (the stage runner:
  idempotent stages skipping completed work, store-in/store-out, single-matchup
  debug vs full batch, BING `fit_batch` for the heavy fits) and *Provenance &
  versioning* (every result stamped with `pab_version`; re-running under a new
  version produces a new record, not a silent overwrite).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 8* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current state;
  the per-stage seams the runner chains; update it at the close of this stage).
- **Existing PAB seams the runner chains (all already implemented):**
  - `pab.argo.{fetch,summary}` — fetch BGC profiles + persist mixed-layer
    summaries (`persist_summary`, idempotent). `data/dev_profiles.csv` is the dev
    selection.
  - `pab.pace.{discover,cloud}` — `search_granules`/`granule_table`/
    `persist_granules` (the candidate set) and `open_granule` (the `opener=` test
    seam).
  - `pab.matchup.build_matchups(store, opener=, …)` — space+time match → records
    (idempotent/resumable, returns `{written, skipped, unmatched}`).
  - `pab.fit.build_fits(store, opener=, …)` — LM→MCMC per matchup, chains NPZ +
    `fits`/`fit_results` (idempotent by `fit_id`, returns `{written, skipped,
    failed}`).
  - `pab.plotting.{fit_fig,scene}` — per-matchup figures (write to `fits.figure_path`).
  - `pab.report.{build_site,publish_release}` — the aggregate site + downloads.
  - `pab.db.store.Store` — the shared state every stage reads/writes; `pab.config`
    (`pab_version`, `DATA_DIR`, `package_versions`).

## Prompts

1. Read this doc and the context files. Execute the 1st task in the "Stage 8"
   section below.

2. Do you have any questions or requests?  If you have any questions, write them in the Q&A section below.  If you have any requests, write them in the Requests section below.

3. I have read your questions and requests and have provided responses.  Please read those and ask any additional questions or requests. Log your work.

## Stage 8

### Tasks

1. Read this doc and the context files. Implement Stage 8 (below). If you have
   questions, write them in the Q&A section. If you have any requests, write them
   in the Requests section. Log your work in the Logs section.

### Q&A

**Q (Claude, 2026-06-26):** Three items from the Stage 8 scope I **deferred** —
confirm defer to Stage 9, or add now?
1. **Single-target debug** (`--matchup`/`--wmo`). I implemented stage subsetting
   (`--stage`) and full-population runs, but not a single-matchup/float filter.
   (Recommend: defer — easy to add; the dev set is small enough to run whole.)
A. I would prefer single-matchup too.

2. **Parallel fitting.** The `fit` stage calls `build_fits` **sequentially**
   (one matchup at a time); the scope mentioned BING `fit_batch` across cores.
   (Recommend: defer until we run at ~10⁴ scale; correctness is unaffected.)

A. We should enable parallel fitting.

3. **Config *file*.** `PipelineConfig` is set in code + CLI flags; there's no
   YAML/JSON loader. Want `--config run.yaml`, or are flags enough for now? — *JXP:*
A. We should use a config file.

**Q (Claude, 2026-06-26):** Stages 0–8 are complete and the pipeline runs
end-to-end offline. Do you want me to do a **first real run** over the dev set
(live argopy + earthaccess + BING) to produce the first actual matchup site? If
so: run it **here** (out-of-region — granule opens were ~140–160 s each, plus a
BING MCMC per matchup) or in **us-west-2**? And the BING Loisel aph-basis data
mount has been intermittent here — worth pinning before a real fit run. — *JXP:*

A. Yes, I will run this on my workstation later today.  Just confirm that it is ready to go and provide me a HOWTO.md file on how to run it.

**Follow-up (Claude, 2026-06-26):** Noted — I'll add **single-matchup targeting**,
**parallel fitting**, and a **config file**, then write `HOWTO.md`. Four specifics
so I build the right thing:

1. **Config format** — I propose **TOML** (`--config run.toml`): Python stdlib
   `tomllib` reads it, so **no new dependency**. (PyYAML is installed but isn't in
   `requirements.txt`, so YAML would add a declared dep.) OK with TOML, or do you
   want YAML? — *JXP:*
2. **Parallel mechanism** — BING's `fit_batch` parallelizes spectra that share
   **one** model/wave grid, but across matchups the granule grids differ, so the
   natural PAB parallelism is **matchup-level**: a `ProcessPoolExecutor` over
   `fit_matchup` with a configurable `n_workers` (each worker fits one matchup,
   opens its own granule). Good? (vs forcing BING `fit_batch`.) — *JXP:*
3. **Single-target selectors** — `--matchup <id>` and `--wmo <wmo> [--cycle <n>]`,
   filtering **every** stage to that target. Both selectors OK? — *JXP:*
4. **HOWTO timing** — I'll write `HOWTO.md` **after** the three land so it
   documents the real CLI (config file + `--matchup`). Confirm that ordering, and
   that the first live run targets the **dev set** (`data/dev_profiles.csv`, 10
   profiles). — *JXP:*

**Readiness:** the pipeline is functionally ready to run live **today** on the
current CLI (`pab --db pab.db`; argopy `gdac`/`expert` + earthaccess + BING, with
`~/.netrc` present). I recommend landing the three enhancements first so the
HOWTO matches the CLI you'll actually run.

### Requests

- For a **first real run**: where should the generated report site live? Right now
  `build_site`/`publish_release` write under `PAB_DATA_DIR/pipeline` with the
  object-store/Zenodo backends **stubbed** (local). To publish for real we'd wire
  the Nautilus/NSF S3 + Zenodo backends (deferred, config-gated) — say the word
  and I'll add them with credentials handling.

A. Add a reminder to the HOWTO.md to set this up, but we should not do it yet.

- Otherwise, no blockers — Stage 9 (Extensibility: NASA-L2-IOP baseline ingest,
  the `L1B → Rrs` hook, extra model pairs, the once-exported interactive lookup
  table) holds the remaining carried-forward deferrals if/when you want them.

## Pull Request

1. I have executed a Pull Request on GitHub for Stage 8. Please review the Pull
   Request and post it to GitHub.

2. Make edits to the Repo to address the review comments. If you have any
   questions, write them in the Q&A section below. If you have any requests,
   write them in the Requests section below.

## Stage 8 — End-to-end pipeline & CLI

Here is some additional context.

### Scope

One resumable, config-driven runner over the existing stages — **no new
science**:

- **Stages, in order** — `discover` (PACE granules for the selected profiles) →
  `match` (`build_matchups`) → `fit` (`build_fits`) → `figure` (per-matchup fit
  + scene PNGs) → `report` (`build_site` + `publish_release`). Argo ingestion
  (profiles + mixed-layer summaries) is the input stage; start from
  `data/dev_profiles.csv` (or a config'd selection).
- **Idempotent + resumable** — each stage skips already-completed work using the
  store's natural keys (the existing `persist_*`/`build_*` idempotency:
  `matchup_id`, `fit_id`); a stage with nothing new to do is a fast no-op, so a
  re-run resumes. A `replace`/`clobber=False`-style guard controls re-doing
  finished work. Re-running under a **new `pab_version`** adds records rather than
  overwriting (per *Provenance & versioning*).
- **Granularity** — run the **full population** (batch; heavy fits via BING
  `fit_batch` across cores when enabled) or a **single matchup/profile** for
  debugging; run **all stages** or a **subset** (e.g. just `report`).
- **Config-driven** — a `PipelineConfig` (the profile selection, granule
  discovery params, `FitConfig`, output dirs under `DATA_DIR`, parallelism,
  `replace`) — constructed in code and/or loaded from a small config file.
- **CLI** — a console entry point (e.g. `pab run`/`pab-pipeline`) with
  `--config`, stage selection (`--stage`/`--only`/`--from`), `--matchup`/`--wmo`
  for single-target debug, `--replace`, and `--dry-run` (print the plan, touch
  nothing).

Keep the network/heavy seams (argopy, earthaccess/`open_granule`, BING) **injectable
and mockable** (pass an `opener=` / fetcher / fit hook) so the end-to-end test
runs **offline** on a synthetic granule + toy fit; keep the **orchestration**
(stage order, skip/resume decisions, the run summary) in pure, testable code.

### Deliverables

- `pab.pipeline` — `PipelineConfig`, the per-stage callables (thin wrappers over
  the Stage 2–7 functions), and a `run(config, *, stages=…, opener=…, …)` runner
  returning a structured per-stage summary (counts written/skipped/failed);
  idempotent + resumable.
- A **CLI entry point** — an `argparse` (or click) interface wired as a
  `console_scripts` entry in `setup.py` (e.g. `pab`), plus `python -m pab.pipeline`.
- Update `pab/pipeline.py` (currently a stub) and any `__init__` exports.

### Tests (offline; `pytest`)

- **End-to-end on a tiny fixture** — 1–2 profiles + 1 synthetic granule (injected
  via `opener=`); run the pipeline through `report` and assert it produces the
  expected DB rows (`matchups`/`fits`/`fit_results`) + artifacts + a generated
  site dir. Use a toy `FitConfig` (short MCMC) guarded by
  `pytest.importorskip("bing")`, or a fit hook/mock so the orchestration is
  testable without bing.
- **Idempotency / resume** — a second `run` writes nothing new (all stages skip);
  running a **subset** of stages does only those; `--dry-run` touches nothing.
- **CLI smoke** — the entry point parses args, `--help` works, `--dry-run` prints
  the plan; a single-target (`--matchup`/`--wmo`) selects only that work.
- Continue the convention: orchestration tested with injected seams; no network;
  heavy/optional deps mocked or `importorskip`.

### Docs

- A **pipeline / quickstart page** (`docs/pipeline.rst`): the stage order, the
  idempotent/resumable model and the `pab_version` re-run behavior, the config,
  and the CLI (full batch vs single-matchup debug, stage subsets, `--dry-run`).
  Add it to the `index.rst` *Package* toctree and autodoc `pab.pipeline`.

### Notebook

- `docs/nb/09_pipeline.ipynb` — run the whole pipeline **offline** on a tiny
  synthetic fixture (injected granule), show the resulting DB row counts and the
  generated report site, demonstrate an idempotent re-run (all-skip), and end
  with an optional `RUN_LIVE` full run. Built executed (offline-safe), rendered
  via `myst-nb`, added to the *Notebooks* toctree.

### Definition of done (the Stage 0–7 standard)

- `pytest` green (new Stage 8 tests included); `ruff check pab` and
  `ruff format --check pab` clean; `sphinx-build -W` succeeds.
- Google-style docstrings on every public function; provenance (`pab_version`)
  carried through; the CLI entry point installed via `setup.py`.
- `docs/design/PAB_implementation.md` updated: flip Stage 8 to ✅ in the status
  table, add a Stage 8 section (modules/API, key decisions, tests, docs,
  notebook), update the module index and the verification line; bump its
  version/date.
- Work logged (see below).

### Q&A

(Write any questions for JXP here; he answers inline. Do not block on interactive
prompts.)

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-06-26 (Stage 8 — read JXP's answers; raised implementation follow-ups)

JXP answered the Q&A: **add single-matchup targeting**, **enable parallel
fitting**, **use a config file**; he'll do the **first live run** on his
workstation and wants a **`HOWTO.md`** + a readiness confirmation; **defer
publishing** (Nautilus S3/Zenodo) but note it in the HOWTO.

Recorded the agreed plan and raised four implementation specifics (in the Q&A
follow-up) so the next step is well-defined:

1. **Config format** — proposed **TOML** (`tomllib`, stdlib, no new dep) vs YAML
   (PyYAML installed but not a declared dep).
2. **Parallel mechanism** — matchup-level `ProcessPoolExecutor` over
   `fit_matchup` (configurable `n_workers`), since BING `fit_batch` only
   parallelizes spectra sharing one model/wave grid and matchup granules differ.
3. **Single-target selectors** — `--matchup <id>` and `--wmo [--cycle]`, filtering
   every stage.
4. **HOWTO timing** — write it *after* the three features so it matches the real
   CLI; confirm the first live run targets the dev set.

Confirmed the pipeline is functionally ready to run live today on the current
CLI. No code changed this turn (planning/clarification).

### 2026-06-26 (Stage 8 — implemented the end-to-end pipeline & CLI)

Implemented `pab.pipeline`: `PipelineConfig`, the six stage wrappers
(`ingest`/`discover`/`match`/`fit`/`figure`/`report`), the `run()` orchestrator,
and the ``pab`` CLI (wired in `setup.py` `console_scripts`).

- **No new science** — each stage calls the existing Stage 2–7 function and
  shares the `Store`; idempotency comes from the per-stage natural keys
  (`mld_summary`/`matchup_id`/`fit_id`), so a re-run resumes. `figure` is
  best-effort per fit; `report` builds the site + stub release.
- **Injectable seams** — `run(..., opener=, fetcher=, searcher=)` forwards only
  the seams each stage accepts (via `func.__code__.co_varnames`), so the whole
  chain runs offline on a synthetic granule + inline summaries + a discovery
  seam. `dry_run` returns the plan.
- **CLI** — `pab --dry-run/--stage/--outdir/--profiles-csv/--replace/--no-figures`;
  `pab = pab.pipeline:main` entry point + `python -m pab.pipeline`.
- **Tests** `test_pipeline.py` (9): dry-run, stage-subset, idempotent ingest,
  discover-via-searcher, match+resume, report-on-empty, CLI dry-run + parser, and
  a `bing`-guarded end-to-end. Suite **116** (114 + 2 BING-data skips when the
  mount is down). `ruff` + `sphinx -W` clean.
- **Docs** `pipeline.rst` + **notebook** `09_pipeline.ipynb` (offline). Impl
  record → Stage 8 ✅ (v0.7.0) — Stages 0–8 now complete; Stage 9 is future.

What I learned / decisions:

- **Seam forwarding by signature** — `run` inspects each stage's
  `co_varnames` and passes only the seams it declares, so one `run` call drives
  all stages without every stage taking every kwarg.
- **Test bug, not code bug**: my first end-to-end used one granule for both
  profiles via `opener=lambda s: gran`; the 2nd float was then >5 km from those
  pixels and (correctly) rejected by the matchup distance gate → 1 matchup. Fixed
  with a per-URL opener (a granule centred on each float) — good confirmation the
  Stage-4 spatial gate works through the pipeline.
- Output (site/release/figures) goes under `DATA_DIR/pipeline` (or `--outdir`),
  never the repo; tests use tmp dirs.
