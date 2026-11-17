# Figures for the paper

## Goals

Deal with Figures for our paper.

## Context

- The majority of Python scripts to make the figures for this paper are in `pab/matchup`
- There is a master script to make all the figures in `PAB/papers/bbp/make_paper_figures.py`

## Prompts

### Prep

1. I wish to start by making one of the paper figures using the `make_paper_figures.py` script.  
I wish to confirm that we are using the v2.0.1 version of the PAB database, although we are
soon going to updated to v2.1. 
Let's start with the `scatter` figure.  
I tried to run the script with: `python make_paper_figures.py --which scatter` but it failed.
I believe this is because I am missing files on my laptop.
Please explore and advise.  Do not create any new files but you can advise
me how to do so and/or what to download.
Put your findings and any questions in the Q&A/Prep section below.
Use Opus 5.5.  Log your work.

2. Ok, I have downloaded the v2 DB files and answered the questions in the Q&A/Prep 
section below. Please read the answers and then make modifications to the 
`make_paper_figures.py` script. 
Use Opus 5.5.  Log your work.


## Q&A

### Prep

**Prep 1 — findings (2026-11-16, Opus 5.5)**

The `--which scatter` run fails for **three** separate reasons. Missing files
is only the first. Fixing it alone will not produce the figure.

**F1. Wrong database on the laptop (v1.0, not v2.0.1).**
`$PAB_DATA_DIR` = `/Users/xavier/Oceanography/data/Color/PAB`. It holds only
`pab.db` (141 MB, 5 Sep) and `fit_chains/`. That `pab.db` is the **v1.0** DB:
`SELECT pab_version, count(*) FROM fits` → `1.0 | 14609`. It has no 2.0 or
2.0.1 fits and no NASA-GIOP rows. There is no `v2/` subfolder on the laptop.

The v2.0.1 release is the public `s3://pab/v2/pab.db`. I checked it today with
an HTTP HEAD: 220,819,456 B, last-modified 2026-10-20. HOWTO §5b gives its
sha256 as `9503015b…cad92` and its contents as 15,971 2.0 fits + 51 2.0.1
re-fits + 15,976 NASA-GIOP rows. `gather_matchups(store)` with its default
`pab_version=None` uses the newest version family with the patch overlaid. On
that file that means 15,920 rows at 2.0 + 51 at 2.0.1 = **v2.0.1**. So
`make_analysis_figures` uses v2.0.1 automatically once it is pointed at that
DB. The paper does not need to pass a version.

**F2. File names the master script expects but nothing publishes.**
`make_paper_figures.py` looks for `$PAB_DATA_DIR/matchup_summary.parquet`. If
that file is missing it exits with `ERROR: parquet not found`, which is the
failure you saw. It also looks for `$PAB_DATA_DIR/pab_full.db`. No PAB stage
or S3 object is named `pab_full.db`. It looks like Allie's local name for the
full DB, i.e. today's `v2/pab.db`. Downloads:

```
mkdir -p $PAB_DATA_DIR/v2 && cd $PAB_DATA_DIR/v2
curl -O https://s3-west.nrp-nautilus.io/pab/v2/pab.db                    # 220.8 MB
curl -O https://s3-west.nrp-nautilus.io/pab/v2/matchup_summary.parquet   # 2.7 MB
shasum -a 256 pab.db matchup_summary.parquet
#   expect 9503015b…cad92 and cda3bc42…85f1 (HOWTO §5b)
```

Keep them in a `v2/` subfolder rather than over the v1 `pab.db`. That matches
the HOWTO convention, and v2.1 can go in its own folder later. Then either
symlink `pab_full.db → pab.db` or (better, see Q2) fix the script to take
`--db`.

**F3. The master script does not match `make_analysis_figures.py`. It fails
even with the files in place.** `run_analysis_figures()` calls
`maf.load_data(parquet=…, db=…)` and then `maf.scatter(df, out_dir=…)`. Neither
function exists. The module has `_load(db)`, `scatter_1to1(df, out)` and a
`FIGURES` dict whose `'scatter'` key maps to `bbp700_pace_vs_argo_scatter.png`,
driven by `generate_all(db, out_dir, which)`. The `AttributeError` is caught
and printed as `ERROR in analysis figures: …`, so the run prints "Done." with
no figure. The same mismatch hits `geometry` (`dtime`/`dist` are FIGURES keys,
not functions) and `basin` (the function is `by_basin`). Other problems in
the master script:
- `--parquet` / `--db` are parsed but **ignored**. The `run_*` functions and
  the existence checks read the module globals `PARQUET`/`DB`. A CLI override
  currently does nothing.
- The scatter path never reads the parquet. `_load` builds everything from the
  DB. The parquet check blocks `scatter` for no reason.
- It mkdirs the output folder before the input checks, so a failed run still
  leaves an empty `paper_figures/`. Your run had created one. I removed it
  because it was empty.
- `chl` imports `pab.matchup.plot_chl_matchup_scatter`, which was deleted in
  commit `5257434`. The `maps` hints point at `pab/matchup/plot_*_global.py`.
  Those are actually in `papers/bbp/` on `origin/bbppaper` (Allie's commits
  `0d9cb9d`, `df8ed99`), which are **not yet pulled** into your local branch.

**Verified that the underlying code works.** In the scratchpad I ran
`make_analysis_figures.generate_all(<laptop v1 pab.db>, …, ['scatter'])`. It
produced `bbp700_pace_vs_argo_scatter.png` (13,562 valid matchups, 774 floats,
median δ = +0.371). Those are v1.0 numbers and a pipeline check only. Do not
use them in the paper.

**Fastest path to a v2.0.1 scatter today** (after the downloads above, with
no code changes):

```
python pab/matchup/make_analysis_figures.py \
    --db $PAB_DATA_DIR/v2/pab.db --out-dir $PAB_DATA_DIR/v2/paper_figures --which scatter
```

**Questions**

- **Q1.** Was the v1-only laptop DB intended, or should Allie's figures (and
  hence `pab_full.db`) also be confirmed to be the 2026-10-20 `v2/pab.db`
  (sha `9503015b…`) and not the earlier `v2/pab_2026-10-07.db`? The
  2026-10-07 file is pre-2.0.1 and has the 51 runaway fits.
>A. All figures should be made from the v2.0.1 DB.  Soon, we will update to v2.1.
- **Q2.** Shall I fix `make_paper_figures.py`? The changes would be: (a) call
  `maf._load` and the `FIGURES` functions, (b) honor `--db`/`--parquet`,
  (c) require the parquet only for groups that read it, (d) default to
  `$PAB_DATA_DIR/v2/pab.db`, not `pab_full.db`, (e) fix the `chl` and `maps`
  paths. Or should Allie own that?
>A. Yes, please make those fixes
- **Q3.** The figure numbers in the master script's docstring ("Fig 4 —
  scatter") should come from the draft (`paper_allie_2026nov16.docx`). Should
  output filenames carry the paper figure numbers (e.g. `fig04_scatter.png`)?
>A. No, do not put the figure names in the output filenames.
- **Q4.** For v2.1: should `--db` (or a `--version-dir v2`) be the switch, so
  the same command re-renders every figure against the new release?
>A. Yes, have --db be the switch

**Prep 2 — `make_paper_figures.py` rewritten (2026-11-16, Opus 5.5)**

Your downloads check out. `v2/pab.db` sha256 = `9503015b…cad92` and
`v2/matchup_summary.parquet` = `cda3bc42…85f1`, both matching HOWTO §5b. The
parquet has 15,971 rows, one per matchup, with 15,920 at 2.0 and 51 at 2.0.1.
So it is already the v2.0.1 overlay.

What changed in [make_paper_figures.py](../make_paper_figures.py):
- **`--db` is the release switch (Q4).** The default is
  `$PAB_DATA_DIR/v2/pab.db`. `--parquet` defaults to `matchup_summary.parquet`
  **next to `--db`**. `--out-dir` defaults to `paper_figures/` next to `--db`.
  For v2.1 you would run `--db $PAB_DATA_DIR/v2.1/pab.db` and nothing else.
  `pab_full.db` is gone.
- **Analysis figures (Q2a).** The master script now calls
  `make_analysis_figures._load(db)` once and then the functions in its
  `FIGURES` dict. `geometry` → `dtime` + `dist`; `basin` → `by_basin`. It
  prints the `pab_version` mix it loaded so the version can be checked on every
  run.
- **CLI paths are honored (Q2b).** The `run_*` functions take `db`/`parquet`
  as arguments; there are no more module globals.
- **Inputs are checked per group (Q2c).** A `NEEDS` table lists what each group
  reads. Only those files must exist, and the error says which group needed
  the missing file. `scatter` no longer needs the parquet. The checks run
  before the output folder is created, so a failed run leaves no empty folder.
- **chl / maps (Q2e).** `chl` now uses `pab.matchup.chl.data.load_chl_matchups`
  + `plot_chl_scatter`. `maps` imports `papers/bbp/plot_global_maps.py`
  (Allie's merged map script) and draws all four maps. The cartopy maps run
  fine on this laptop (cartopy 0.25).
- **Failures are no longer hidden.** Each group prints its traceback, and the
  script ends `FAILED groups: […]` with exit code 1, not "Done.".
- **No figure numbers (Q3).** Output names chosen by the master script are now
  `rrs700_vs_delta.png`, `bing_giop_comparison.png` and `outlier_cases.png`.
  The docstring no longer lists figure numbers either.

**Test run** against `v2/pab.db`, all groups, output to scratchpad:
- 10 of 12 groups OK.
- `scatter`: n = 13,861 (13,822 at 2.0 + 39 at 2.0.1), 819 floats, ρ = 0.50,
  bias +0.10 dex, RMS 0.27 dex, median ratio 1.23. I looked at the plot and it
  looks sane.
- **`rrs700` and `giop` FAIL** with `no such column: fr.median`. See Q5.

To make the scatter for real:
`python papers/bbp/make_paper_figures.py --which scatter`
→ `$PAB_DATA_DIR/v2/paper_figures/bbp700_pace_vs_argo_scatter.png`.

**Questions**

- **Q5.** `plot_rrs700_vs_delta.py` and `plot_bing_giop_comparison.py` query
  `fit_results.median`, but the column is `value` (with `value_lo`/`value_hi`).
  `plot_global_maps.py` already uses `value`. There is also a **v2.0.1 bug**
  hiding behind the crash. `plot_rrs700_vs_delta` takes
  `MAX(...) GROUP BY matchup_id` over **all** BING fits. The 51 re-fitted
  matchups each have two fits, 2.0 and 2.0.1, so `MAX` would pick the 2.0
  runaway value (~10⁵ m⁻¹ wall). The right fix is to join on the parquet's
  `fit_id`, which is already the 2.0.1-overlaid fit, rather than grouping
  over `fits`. GIOP is a single version (1.1), so for `giop` only the column
  rename is needed. Shall I make these two fixes?
- **Q6.** Some modules still hard-code figure numbers in their output names:
  `plot_delta_vs_bbp.py` (`fig7_…`, `fig8_…`) and `plot_global_maps.py`
  (`fig2_…`, `fig14_…`, `fig15_…`, `fig_strict_…`). Per Q3, should I rename
  those too (e.g. `delta_vs_bbp_pace.png`, `global_map_bing.png`)?
- **Q7.** The figures do not all use the same sample. `make_analysis_figures`
  keeps δ ≥ −1.5, which gives n = 13,861. `plot_delta_vs_bbp` and
  `plot_outlier_cases` keep every positive pair, which gives n = 15,274. Is
  that intentional for the paper, or should all bbp figures share one sample
  definition?

## Logs

### 2026-11-16 (Prep 1: diagnosed `make_paper_figures.py --which scatter` failure)

Ran the failing command, which stopped at the missing
`$PAB_DATA_DIR/matchup_summary.parquet`. Then checked, read-only, the local data
dir, the DB version, the master script against `pab/matchup/make_analysis_figures.py`,
git history, and the public S3 objects (HEAD requests only). Learned the
following. The laptop's `pab.db` is v1.0 (14,609 fits). v2.0.1 lives in
`s3://pab/v2/pab.db` (2026-10-20). `gather_matchups` overlays 2.0.1 by default,
so no version argument is needed. `pab_full.db` is not a published name. The
master script is out of sync with `make_analysis_figures` (`load_data`/`scatter`
don't exist), ignores its `--db`/`--parquet` flags, and references a deleted
chl script and map scripts not yet pulled from `origin/bbppaper`. Confirmed the
real code path works by rendering the scatter from the v1 DB into the
scratchpad. The first run had left an empty `paper_figures/` in
`$PAB_DATA_DIR`; I removed it. No other files were created. Findings and
questions Q1–Q4 are in Q&A/Prep.
### 2026-11-16 (Prep 2: rewrote `make_paper_figures.py` around `--db`; verified on v2.0.1)

Read the Q1–Q4 answers. Checked the downloaded `v2/pab.db` and parquet sha256
against HOWTO §5b; both match. The parquet is already the v2.0.1 overlay
(15,920 rows at 2.0 + 51 at 2.0.1). Noted that the user had pulled
`origin/bbppaper`, where Allie had merged the four map scripts into
`papers/bbp/plot_global_maps.py`.

Rewrote `papers/bbp/make_paper_figures.py`:
- `--db` is the release switch, defaulting to `$PAB_DATA_DIR/v2/pab.db`. The
  parquet and output dir default to locations next to the DB.
- The analysis groups go through `make_analysis_figures._load` + `FIGURES`.
- A per-group `NEEDS` table drives the input checks, which run before the
  `mkdir`.
- `chl` now uses `pab.matchup.chl`, and `maps` imports `plot_global_maps`.
- Each group's traceback is printed; any failure gives exit 1.
- Figure numbers are gone from the names the master script chooses and from
  the docstring.

Ran every group against `v2/pab.db` into the scratchpad. 10 of 12 render.
`scatter` gives n = 13,861 with 39 rows at 2.0.1; I inspected the plot.
`rrs700` and `giop` crash in their own modules on `fit_results.median` (the
column is `value`). `rrs700` also has a latent version bug: its
`MAX … GROUP BY matchup_id` over all BING fits would pick the 2.0 runaway over
the 2.0.1 re-fit for the 51 patched matchups. Also checked that a missing
`--db` exits 1 and creates no folder. Left the downstream modules untouched and
raised them as Q5–Q7.
