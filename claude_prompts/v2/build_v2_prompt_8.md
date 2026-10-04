# Build v2 — Prompt 8: report layer for 2.0 (version-aware metrics, the 1.0-vs-2.0 section, figures, site)

## Goals

Make the report read the v2 database correctly, add the **"1.0 vs 2.0"**
comparison section fed from the frozen v1 database, render the 2.0 fit
figures (scenes reused from v1), and regenerate `report_site/`
(`run_full_inelastic.md` Plan §3 f, §5 step 9; Q7, R7).

## Claude

### Skills

- **`dataviz`** when adding the new comparison figure.

### Working agreements

As in `build_v2_prompt_1.md`. `v1/pab.db` is read **only** via
`ATTACH … AS v1` / a read-only `Store.open(create=False)`. The committed
`report_site/` stays small (thumbnail galleries auto-suppress above
`MAX_INLINE_FIGURES`; interactive Bokeh only below `MAX_INTERACTIVE_MATCHUPS`).

## Context

- Plan §3 f, §5 step 9 of `claude_prompts/v2/run_full_inelastic.md`.
- `pab/metrics/compare.py` (`gather_matchups` filters by `model_pair`
  **only**; `gather_nasa_giop`; `log_comparison`), `pab/report/rst.py`
  (`build_site`, `nasa_giop_section` — the template for a new section;
  `_NASA_BBP_CAVEAT` style for single-sourced wording; `downloads_page`;
  `provenance_block`; `methods_page`), `pab/pipeline.py` (`--emit-site`,
  `--downloads-base-url`), `pab/plotting/fit_fig.py` (robust dispatch from
  Prompt 3), `nautilus/full_figrep_job.yaml` (16 workers / 100 Gi;
  `figure` is memory-bound).
- R7: **fit figures re-rendered for all 2.0 fits; existing scenes reused
  from v1** — `matchups.scene_path` was carried into v2 by the split, so
  `figure` must not re-render a scene whose path exists; scenes are rendered
  only for the backfilled matchups.
- `HOWTO.md` §7a (regenerate + preview: `pab --db … --emit-site report_site`,
  `sphinx-build`).

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below

## Tasks

1. **Version-aware metrics.** `gather_matchups(store, model_pair=…,
   pab_version=None)` — default to the store's newest BING version and
   filter on it (a test: a store holding 1.0 and 2.0 fits for one matchup
   yields one row); `gather_version_pair(store_v2, v1_path)` → one row per
   matchup with both fits (`bbp700`, `chl`, `aph`, `Bp` where present, χ²),
   joined on `matchup_id` + `pixel_id` via `ATTACH`. The summary page's
   coverage counts must count 2.0 BING fits only. Tests. Log.

2. **"1.0 vs 2.0" section** on the Comparisons page (mirror
   `nasa_giop_section`): what changed (emulator, Raman, Chl fluorescence,
   720 nm, free `B_p`) stated once in a module-level constant; scatters
   `bbp700` / `chl` (2.0 vs 1.0, 1:1 + median-ratio lines; interactive
   below `MAX_INTERACTIVE_MATCHUPS`, static PNG above), `log_comparison`
   stats, a `B_p` posterior-median histogram; the methods page gains the
   2.0 configuration and the two-database provenance (`v1` frozen, `v2`
   this run, `pab_version` semantics); a summary-page headline block.
   `--compare-db PATH` on `--emit-site`; the section returns `""` when
   absent. Tests. Log.

3. **Figures on Nautilus.** `figure` stage: render **fit figures** for every
   BING 2.0 fit; render **scenes only where `scene_path` is NULL**
   (backfilled matchups) — add that guard + test. The chains live on the
   PVC, so this stage runs **in-pod**: upload the current workstation
   `v2/pab.db` to `/data/v2/pab.db` (sha both ends; the PVC copy is the
   writer for this one stage), run `nautilus/v2_figrep_job.yaml`
   (16 workers / 100 Gi, DB-local wrapper, `--stage figure` then
   `--stage report` on `/data/v2`), then copy the DB back and re-lock the
   PVC copy. Log counts (fit figures ≈ 2.0 fits; new scenes ≈ backfilled
   matchups) and wall-clock.

4. **Regenerate the site.** `pab --db $PAB_DATA_DIR/v2/pab.db --emit-site
   report_site --compare-db $PAB_DATA_DIR/v1/pab.db --downloads-base-url
   https://s3-west.nrp-nautilus.io/pab/v2`; `sphinx-build` preview; check:
   coverage counts (matchups ≈ 16.8k, BING fits = 2.0 count), the NASA
   comparison now against 2.0 `bbp700`, the new section, galleries
   suppressed at scale, site size. Do **not** commit. Log the headline
   numbers.

## Q&A

### Q1 (Task 2) — 48 non-physical 2.0 `b_bp` retrievals

**48 of 14,604 2.0 fits (0.33 %) return `b_bp`(700 nm) above 1 m⁻¹, the
largest 9.3×10⁴ m⁻¹.** Seawater cannot do this: the open ocean spans roughly
1e-4 to 1e-1 m⁻¹. The *same matchups* fitted in 1.0 produce **zero** such
values (v1 maximum 0.0337 m⁻¹), so this is specific to the 2.0 configuration,
not to those spectra. There are also 386 2.0 fits below 1e-4 m⁻¹ against 10 in
1.0.

For now they are **left in every statistic and flagged in the report** — the
medians and Spearman ρ are rank-based and barely move, and filtering them
silently would hide a failure rate. But what to *do* about them is yours:

- **(a)** Leave as-is, reported. (What I have implemented.)
- **(b)** Investigate the 48 — are they a particular node, a particular
  granule, an emulator out-of-domain region, or non-converged chains? I can
  pull their `chisq`/`accept_frac`/`B_p` and granule and look for a pattern.
- **(c)** Add a physical-plausibility gate to the fit stage so 2.0 refuses to
  write a `b_bp` above some bound, and re-fit the affected matchups.

I'd suggest **(b) before deciding** — 0.33 % is small enough to live with but
the mechanism may well affect the other 99.67 % less visibly.

**Answer:**

### Q2 (Task 2) — the 2.0/1.0 shift is strongly level-dependent

The headline is `b_bp` 2.0/1.0 = **0.75**, but that is a population median over
a very non-uniform effect. By tercile of the 1.0 value the ratio is **0.66 /
0.74 / 0.81**, and the trend continues hard at the extremes:

| 1.0 `b_bp`(700) | n | median 2.0/1.0 |
|---|---|---|
| < 2e-4 | 52 | **0.018** |
| 2–4e-4 | 228 | 0.037 |
| 4–7e-4 | 1,986 | 0.613 |
| 0.7–1.2e-3 | 4,536 | 0.727 |
| > 1.2e-3 | 7,802 | 0.791 |

In the clearest water 2.0 retrieves **~50× less** backscatter than 1.0. That is
either a real consequence of the inelastic terms dominating a weak elastic
signal (Raman is a larger *fraction* of Rrs in clear water, so the elastic
model had to invent backscatter to explain it — which would make 2.0 the more
correct answer) or a numerical failure of the emulator at the low end. The 280
matchups below 4e-4 are few, but they are exactly the regime where the physics
change should matter most.

I have added a tercile line to the report so the single median is not read as a
correction factor. **Is the clear-water behaviour expected?** If it is the
intended physics, it deserves its own paragraph as a result rather than a
caveat.

**Answer:**

### Q3 (Task 2) — `B_p` posterior piles up at both prior bounds

The free `B_p` posterior medians are **bimodal with mass at both edges** of the
uniform `[0.004, 0.05]` prior: 2.8 % within 1 % of an edge, 7.1 % within 2 %,
15.4 % within 5 %; the 1st percentile is 0.0043 and the 99th is 0.0492. The
median is 0.0236.

A pile-up at a prior bound means the data wanted a value the prior forbade, so
the bound — not the spectrum — is setting those retrievals. Options: widen the
prior and re-fit a slice to see whether the modes move out, or accept the
bounds as physically motivated and say so in Methods. Prompt 3's n=20 slice put
edge-pinning at 15 %, then the Prompt 6 slice at 2 %; at n=14,604 it is 2.8 %
at the same tolerance, so the Prompt 6 figure held and the Prompt 3 one did
not.

**Answer:**

## Reports

### Task 1 — Version-aware metrics

**What changed.** `pab/metrics/compare.py` gained three things and
`pab/report/rst.py` one.

- `_version_key(v)` — a sort key that compares `pab_version` numerically
  where it can. `"2.0" > "1.1"` happens to be right under plain string
  comparison; `"10.0" > "9.0"` is not, and the version strings are
  user-supplied (`--pab-version`), so the ordering is pinned rather than
  inherited from `max()` on strings.
- `newest_bing_version(store)` → the newest `pab_version` among `algorithm
  = 'BING'` rows, or `None` on a store with no BING fits.
- `gather_matchups(store, *, model_pair, pab_version=None)` — the `fits`
  join now filters on `algorithm = 'BING'` **and** a single `pab_version`,
  defaulting to `newest_bing_version`.
- `gather_version_pair(store, v1_path, *, model_pair)` — attaches the
  frozen v1 database read-only and returns one row per matchup fitted in
  both versions.

**Why the version filter is not cosmetic.** `gather_matchups` returns one
row per *fit*, not per matchup. A store that has been fitted twice holds a
1.0 and a 2.0 BING fit for the same matchup and the same pixel, so without
the filter every count doubles, the headline "BING fits" exceeds the
matchup count, and the bbp/chl scatter silently contains two different
physics configurations plotted as one population. The v2 database happens
not to carry 1.0 BING rows today — the v2 split carried the NASA-GIOP rows
across but not the BING ones — so the filter changes nothing *now*; it is
there so that a re-fit, or a merge of the two databases, cannot quietly
corrupt the report.

**Why the join is on `pixel_id` too.** `matchup_id` identifies the
profile/granule pair, not which pixel was fitted. Joining on it alone
pairs a 1.0 fit of one pixel with a 2.0 fit of another whenever the chosen
pixel differs between runs, and the resulting difference — spatial — would
be read off the plot as the inelastic-physics change. That is the single
most expensive way this function could be wrong, so it has its own test.

**Read-only ATTACH.** `v1/pab.db` is `chmod a-w` and at schema v4 while the
code is at v5; `Store.open` on it would attempt a migration and die with
`attempt to write a readonly database`. `ATTACH DATABASE
'file:…?mode=ro'` avoids both.

> **Correction (found during Task 2).** As written in Task 1 this did **not**
> work. `ATTACH` only parses a `file:…?mode=ro` URI when the connection was
> opened with `uri=True`, and `Store.open` used a plain
> `sqlite3.connect(path)`. So the read-only attach failed on every call and
> the `except` fell back to a plain-path `ATTACH`, which is **read-write** —
> the frozen v1 release was attached writable each time, and only its
> `chmod a-w` prevented harm. Fixed in Task 2: `Store.open` now passes
> `uri=True`, the fallback is **removed** (a failed read-only attach must
> raise, not silently succeed unsafely), and two tests assert the frozen
> database is unwritable *through the code* rather than only through the
> filesystem. The `DETACH` is in a `finally`, because a
left-attached alias makes the *next* call fail on a name clash rather than
at the point of the bug.

**The summary page.** `summary_page` now resolves `newest_bing_version`
**once** and hands the same value to both `gather_matchups` and the
`n_fits` coverage query, so the count and the metrics table can never
describe different sets of fits. Two senses of "version" meet on that page
and conflating them would be a quiet error: `pab_version` (the parameter)
is the *running code's* version for the provenance line, `_bing_version`
is the version of the *fits being reported*; they differ whenever the
report is regenerated by newer code over an older run. The coverage line
now reads ``**BING fits:** N (``pab_version`` 2.0)``.

**Verification on the real databases** (`ocean14`, `v2/pab.db` +
`v1/pab.db`):

```
newest BING version: 2.0
gather_matchups rows: 15971   versions: ['2.0']
paired rows: 14604
bbp700 v2/v1 median: 0.7497   n=14604
Bp_v2 non-null: 14604
```

The 14,604 pairs are the matchups fitted in both versions (15,971 v2 fits;
the shortfall is matchups v1 never fitted or fitted at a different pixel).
`bbp700` v2/v1 = **0.7497** — 2.0 retrieves ~25 % less backscatter than
1.0, consistent with the n=20 Prompt 3 slice (0.741) and the Prompt 6
slice (0.7375). This is the headline number Task 2 will plot; it is
reported here as a gather-layer check, not yet as a result.

**Tests** — `pab/tests/test_compare_versions.py`, 8 tests, each verified
load-bearing by reverting the fix it covers:

| test | breaks when |
|---|---|
| `test_version_key_orders_numerically_not_lexically` | `_version_key` falls back to string compare |
| `test_newest_bing_version_picks_the_newest` | — (covers the `None` and the ordering path) |
| `test_two_versions_of_one_matchup_yield_one_row` | the `pab_version` filter is dropped → 2 rows |
| `test_an_explicit_version_selects_the_older_fit` | ditto |
| `test_nasa_giop_rows_never_count_as_bing_fits` | the `algorithm = 'BING'` guard is dropped |
| `test_gather_version_pair_joins_on_pixel_not_just_matchup` | the `pixel_id` condition is dropped → 1 bogus pair |
| `test_gather_version_pair_detaches_even_on_error` | the `finally: DETACH` is dropped |
| `test_summary_page_counts_only_the_reported_version` | the coverage query's version filter is dropped |

Full suite in `ocean14`: **369 passed, 1 skipped** (baseline 361 + 8 new;
the skip is the live-L1B test).

### Task 2 — the "1.0 vs 2.0" section

**What was built.**

- `rst.V2_CHANGES` — a module-level constant stating what 2.0 changed, used by
  the Comparisons section, the Methods page, and (indirectly) the summary
  headline. Three places that would otherwise drift apart.
- `rst.version_section(store, compare_db, …)` — mirrors `nasa_giop_section`:
  `log_comparison` stats for `bbp700` and `chl`, scatters (interactive Bokeh
  below `MAX_INTERACTIVE_MATCHUPS`, static PNGs above), and a `B_p`
  posterior-median histogram with the prior bounds drawn. Returns `""` when
  `compare_db` is absent, missing, unreadable, or shares no matchup.
- `rst._version_headline` — the summary-page block (median ratios + n only).
- `methods_page(compare_db=…)` — the 2.0 configuration, the `pab_version`
  semantics (`1.0` elastic, `2.0` inelastic, `1.1` the unchanged NASA ingest),
  and the two-database provenance.
- `population.value_histogram` — new; and `comparison_scatter` gained
  `clip_percentile`.
- `build_site(compare_db=…)` and `pab --emit-site --compare-db PATH`.

**Three places the brief did not match the run**, each checked against the
`fits` rows rather than taken on trust:

1. **CDOM fluorescence is off.** `include_cdom_fl = 0` on all 15,971 2.0 fits.
   Listed as available-but-off, not as an improvement.
2. **The fit window is unchanged.** `wave_min`/`wave_max` are 400/700 in
   *both* releases, so "720 nm" is not a 1.0→2.0 difference. The constant says
   the window is unchanged and explains why the red edge was excluded (the R4
   diagnostic: Rrs(719) negative or noise-dominated on 44 % of matchups).
3. **`aph` duplicates `chl`.** The stored `Aph` is the linear amplitude and
   `chl = Aph / 0.05582`, so an `A_ph` stats line reproduced the Chl line
   digit for digit — ratio 1.17, ρ 0.704, identical IQR. Two identical rows
   under different names read as two independent agreements. Dropped the line;
   the relationship is stated once. Both columns stay in the gathered frame.

**Results** (14,604 paired matchups, same pixel both sides):

| | n | median 2.0/1.0 | IQR | ρ | log10 bias | RMS |
|---|---|---|---|---|---|---|
| `b_bp`(700 nm) | 14,604 | **0.75** | 0.612–0.877 | 0.924 | −0.157 | 0.536 |
| chlorophyll | 14,604 | **1.17** | 1.01–1.42 | 0.704 | +0.191 | 0.644 |

2.0 retrieves ~25 % less backscatter and ~17 % more chlorophyll. The `b_bp`
ratio matches the small slices (0.741 at n=20, 0.7375 at n=100).

**Two findings that changed what the section reports** — both raised in Q&A:

- **The shift is not uniform** (Q2). By tercile of the 1.0 value the ratio is
  0.66 / 0.74 / 0.81, and 0.018 below 1.0 `b_bp` = 2e-4. Quoting 0.75 alone
  would invite a reader to apply it as a correction factor, so the section
  reports the terciles and says explicitly that it is not one.
- **48 non-physical 2.0 retrievals** (Q1): `b_bp` > 1 m⁻¹, up to 9.3e4,
  against **zero** in 1.0 on the same matchups. Left in every statistic and
  reported with their count; `clip_percentile=99` keeps the scatter readable
  and prints the off-scale count in the panel rather than hiding it.

**A defect found while testing.** `gather_version_pair` on a missing path
**created an empty SQLite file** and then failed with `no such table:
v1.fits` — `ATTACH` of a plain path creates the database. A mistyped
`--compare-db` would have left junk next to the production data. Now it checks
the path first and raises `FileNotFoundError`.

**A third, and the worst.** Cleaning up a stray `file:None?mode=ro` left in
the repo root by one of those experiments led to the real bug: **the
"read-only" ATTACH was never read-only.** `ATTACH` parses a `file:…?mode=ro`
URI only when the connection was opened with `uri=True`, and `Store.open` used
a plain `sqlite3.connect(path)` — so the URI attach failed every single time
and the `except` fell back to a plain-path `ATTACH`, which is **read-write**.
The frozen v1 release was attached writable on all 14,604-row queries,
including against production. Nothing was damaged, but only because the file
is `chmod a-w`: the protection came from the filesystem, not from the code
that claimed to provide it. `Store.open` now passes `uri=True` and the
**fallback is deleted** — a failed read-only attach now raises. Two tests
assert the frozen database is unwritable through the code. The Task 1 report
has been corrected.

**A second one found the same way.** The broad `except` around
`gather_version_pair` meant a corrupt or wrong v1 removed the section from the
published site with *no trace* — indistinguishable from "no v1 was given".
Both swallow sites now log a warning; the tests assert that the legitimate
empty cases log *nothing* and the failure cases log *something*.

**Tests** — `pab/tests/test_report_versions.py` (19) + 1 added to
`test_compare_versions.py`, each verified load-bearing:

| break | caught by |
|---|---|
| `version_section` guard removed | the two "empty, and silent" tests |
| failure note removed | `test_failure_note_counts_non_physical_bbp` |
| `V2_CHANGES` dropped from Methods | 2 tests |
| `--compare-db` accepted but not forwarded | `test_cli_compare_db_reaches_build_site` |
| `clip_percentile` ignored | `test_clip_percentile_bounds_the_axes…` |
| tercile split removed | `test_ratio_is_reported_by_level…` |
| existence check removed | `test_gather_version_pair_never_creates_the_database` |

Full suite in `ocean14`: **387 passed, 1 skipped** (369 → 387).

Not yet done: Task 3 (figures on Nautilus) and Task 4 (regenerate the site).

### Task 3 — figures on Nautilus

**Status: the code half is done and verified; the pod has NOT been launched.**
Two blockers, below.

**The `figure` stage gained two filters**, both in `pab/pipeline.py`:

1. **Only BING fits of one `pab_version`** (`--figure-version`, default the
   store's newest). The stage previously iterated *every* row of `fits`. On
   the v2 store that is 31,947 rows, of which **15,976 are NASA-GIOP ingests
   with no MCMC chains** — a fit figure for one cannot succeed. Half the stage
   was guaranteed failures, each costing a worker slot and an exception
   traceback.
2. **Scenes only where `matchups.scene_path IS NULL`** — the guard Task 3
   asked for. The scene is the half that re-opens the ~1.8 GB granule, and
   **14,586 of 15,976** matchups already carry one from the previous release.
   Re-rendering produces a byte-identical PNG for the price of the granule
   read. `_render_figure` gained `want_scene`; the set is resolved **once in
   the parent** (the only writer — a worker cannot see another worker's
   scene), and two fits of one matchup render its scene once, not twice.

**Verified against the real v2 database** (read-only, selection logic only):

```
version selected      : 2.0
fit figures to render : 15971
of those with a scene : 1390
NASA rows included    : 0
```

**The manifest** `nautilus/v2_figrep_job.yaml` — 16 workers / 100 Gi,
DB-local wrapper (copy to emptyDir, 2-min checkpoints, never
`sqlite3.backup()` onto CephFS), `--stage figure` then `--stage report`,
`PYTHONWARNINGS=ignore`, `MPLBACKEND=Agg`, `backoffLimit: 4`,
`activeDeadlineSeconds: 43200`, everything tee'd to `/data/v2/figrep.log`.
`kubectl apply --dry-run=client` passes.

It also carries an **in-pod guard assertion**: before copying the database it
greps its own `pipeline.figure` source for `want_scene` and `algorithm =
'BING'` and **exits 1** if they are absent. An image predating Task 3 cannot
silently do the 31,947-render version — this is the Prompt 7 lesson
(verifying the image is not verifying the manifest) turned into something the
pod checks for itself.

**Cost: ~3–6 h at 16 workers.** The spread is honest, not padding. The
42 s/matchup from the 1.0 run is fit-figure **plus** scene combined and was
never split, and only the scene half is being skipped. The job logs each
stage's wall-clock separately so the next one can be sized from measurement.

**Blocker 1 — the image does not contain the guards.** `:2.0.5` was built
from `69efcd4`; the guards are uncommitted. Running the job against `:2.0.5`
is precisely the 31,947-render, 14,586-granule-read case the guards exist to
prevent. Required order: commit → build → push → **point this manifest at the
new tag** → re-verify the manifest names the tag that was verified.

**Blocker 2 — Q1–Q3 are unanswered.** They do not block rendering (it reads
existing chains and re-fits nothing), but Q1(c) and Q3 both end in *re-fit*,
which would invalidate the figures for whatever is re-fitted. Q1 is 48 fits —
negligible rework. Q3 could be a slice or the whole run. Worth a decision
before spending 3–6 h of 16-core time.

**Tests** — `pab/tests/test_figure_guards.py` (8), each verified
load-bearing:

| break | caught by |
|---|---|
| algorithm/version filter removed | 3 tests |
| `want_scene` always True in the parent | 3 tests |
| `_render_figure` ignores `want_scene` | `test_render_figure_skips_the_granule…` |

Two existing `test_pipeline.py` figure tests needed updating and both were
**underspecified rather than wrong**: `_seed_fits` left `algorithm` NULL
(production always sets it), and `_stub_render` did not mirror the real
signature. The second is worth noting — `figure` catches a failed render and
logs it, so a stub missing a keyword surfaced as "every render failed"
rather than as a `TypeError`.

Full suite in `ocean14`: **399 passed, 1 skipped**.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-10-04 (Prompt 8 Task 1 — version-aware metrics)

Made the metrics layer pick exactly one `pab_version`, and added the
1.0-vs-2.0 gatherer that Task 2 will plot. Details in the Task 1 report
above; what I learned:

- **`gather_matchups` returns one row per fit, not per matchup**, and
  nothing in the function said so. It has been correct only because the v2
  database happens to hold a single BING version. That is a property of the
  *data*, not of the code, and it would have been destroyed by the first
  re-fit — with no error, just counts that quietly double and two physics
  configurations averaged together. The filter costs nothing and removes a
  class of silent corruption; I would rather pay it than rely on the data
  staying convenient.

- **The expensive bug in a version comparison is the join key, not the
  filter.** Joining the two databases on `matchup_id` alone looks right and
  runs fine; it just pairs fits of *different pixels* whenever the chosen
  pixel differed between runs, and hands back a spatial difference labelled
  as the inelastic-physics change — exactly the quantity the whole v2
  analysis is about. Nothing downstream could catch it. It gets the one
  test whose failure message says what the wrong number would have meant.

- **Writing the test taught me the schema.** My first version of the
  "different pixel" test invented a `pixel_id` by adding 999, and SQLite
  rejected it: `matchup_pixels` has a foreign key, so the other pixel has
  to actually exist. Seeding a real rank-2 pixel is both correct and a
  better analogue of the real case (two runs picking different pixels of
  the same matchup).

- **A test can hold a bug in place.** Last prompt's NASA-GIOP version bug
  survived because an existing test asserted against `config.pab_version`
  — the same wrong source the code used. So for each of the 8 new tests I
  reverted the specific fix and confirmed the test fails; 4 of them fail
  when the version filter goes, 1 when the algorithm guard goes, 1 when the
  `pixel_id` condition goes, 1 when the `DETACH` goes, 1 when the coverage
  query's filter goes. A test I have not watched fail is a test I do not
  know the meaning of.

- **Two things called "version" on one page.** `summary_page` already took
  a `pab_version` argument meaning *the running code's version* (for
  provenance). The fits' version is a different thing, and they diverge the
  moment a report is regenerated by newer code. I resolved the fit version
  once into `_bing_version`, passed it to both consumers, and left a
  comment naming the distinction — the counts and the table can no longer
  describe different sets.

- `bbp700` v2/v1 = **0.7497** over 14,604 paired matchups. The n=20 Prompt
  3 slice said 0.741 and the Prompt 6 slice 0.7375, so this one held up at
  730× the sample — unlike the Prompt 3 χ² and `B_p` edge-pinning numbers,
  which did not. The pattern continues to be that measurements *of the
  data* generalised from the small slices and measurements of *how well the
  model fits* did not.

Files touched: `pab/metrics/compare.py`, `pab/report/rst.py`, new
`pab/tests/test_compare_versions.py`. Not committed — git is JXP's.

### 2026-10-04 (Prompt 8 Task 2 — the 1.0 vs 2.0 section)

Built the comparison section, the summary headline, the Methods additions and
the `--compare-db` flag. Details in the Task 2 report; what I learned:

- **Three of the brief's claims were wrong about the actual run, and the only
  way to know was to read the `fits` rows.** CDOM fluorescence is off, the fit
  window never changed, and `aph` is `chl` times a constant. Writing any of
  the three the way the brief phrased them would have put a false statement in
  a published report. The brief describes what was *planned*; the database
  records what *ran*, and for a results page only the second one is evidence.

- **The identical `chl` and `aph` statistics were the tell.** Two rows
  agreeing to three significant figures on ratio, IQR, ρ, bias and RMS is not
  two measurements agreeing — it is one measurement printed twice. I nearly
  shipped it as a second line of corroboration. The check that caught it was
  reading the numbers rather than the labels.

- **A median over a non-uniform effect is a misleading number.** `b_bp`
  2.0/1.0 = 0.75 is true and useless on its own: by tercile it is 0.66 / 0.74
  / 0.81, and in the clearest water 0.018. Someone would have multiplied a
  single retrieval by 0.75. The section now reports the terciles and says in
  words that it is not a correction factor.

- **Looking at the figure is part of generating it.** The scatter and the
  histogram both only gave up their real content when rendered and viewed: the
  scatter showed 48 points at 10⁴ m⁻¹ dragging every real point into a corner,
  and the histogram showed a bimodal pile-up at *both* prior bounds. Neither
  was visible in the summary statistics I had already computed and written up —
  the medians are robust, which is exactly why they hid it.

- **Two silent-failure bugs, both found by trying to break my own tests.** The
  "returns empty without a v1" tests passed with the guard deleted, because the
  broad `except` caught the resulting error and returned `""` anyway — passing
  for the wrong reason. Chasing that down found (a) `ATTACH` of a plain path
  *creates* the database, so a typo'd `--compare-db` wrote a stray file next to
  production data, and (b) a bad v1 dropped the section from the published site
  with no log line at all. Both fixed; the tests now distinguish the legitimate
  empty case (logs nothing) from the failure case (logs something). A test that
  passes when the code is broken is worse than no test, and the only way to
  find one is to break the code on purpose.

- **A fallback can convert a safety failure into a safety breach.** The
  `except` under the read-only `ATTACH` was written to tolerate old SQLite
  builds. What it actually did was catch "the read-only attach did not work"
  and respond by attaching the frozen production database **read-write** —
  every call, for the whole of Task 1, while the docstring and my own report
  said the opposite. The `chmod a-w` saved it. Two lessons: a fallback for a
  *safety* mechanism should raise rather than degrade, and a claim like
  "attached read-only" is a testable assertion, not a comment — the test I
  should have written in Task 1 is four lines (attach, read, try to write,
  expect a refusal).

- **The stray file was the only evidence.** Nothing failed, no test went red,
  and the numbers were all correct. The one visible symptom was a
  zero-byte `file:None?mode=ro` in `git status` from an earlier deliberate
  break — which I could easily have deleted as noise. It was the literal
  filename SQLite created when it read the URI as a path, and following it up
  was what exposed the fallback.

- `clip_percentile` deliberately **counts** the off-scale points in the panel
  title instead of dropping them. The temptation with 48 bad fits out of 14,604
  is to filter and move on; the number is small enough that nobody would
  notice, which is the reason not to.

Files touched: `pab/report/rst.py`, `pab/metrics/compare.py`,
`pab/plotting/population.py`, `pab/pipeline.py`, `pab/db/store.py`
(`uri=True`), new `pab/tests/test_report_versions.py`,
`pab/tests/test_compare_versions.py`.
Not committed — git is JXP's. Q1–Q3 await answers before Task 3.

### 2026-10-04 (Prompt 8 Task 3 — figure-stage guards; pod not launched)

Added both `figure` stage guards, the manifest, and the tests. Did **not**
launch: the image predates the guards, and Q1–Q3 are unanswered. What I
learned:

- **The guard Task 3 asked for was the smaller of the two.** The brief named
  the `scene_path IS NULL` guard. Measuring the stage first turned up a bigger
  one it did not mention: the stage iterated *all* of `fits`, and half that
  table is NASA-GIOP rows with no chains. Nobody had noticed because the figure
  stage had only ever run on a store where that was not true. Rendering the
  brief's guard alone would have left a run that failed 15,976 times.

- **Reading the counts out of the database before writing code decided the
  design.** 14,586 of 15,976 matchups already have a scene; 1,390 do not. That
  one query is the difference between 16k granule reads and 1,390, and it is
  also what makes the expected-counts block in the manifest possible — the job
  now prints what it is about to do and can be killed in seconds if the numbers
  are wrong.

- **I put the Prompt 7 lesson into the pod instead of into a checklist.** Twice
  now a job has run with an image or flag that did not match what was verified.
  A checklist step did not prevent the second one. So the manifest now asserts
  on its own source — it greps `pipeline.figure` for `want_scene` and the BING
  filter and exits 1 if absent. A stale image cannot start the expensive
  version of this job even if I point the manifest at the wrong tag.

- **A test double that does not mirror the real signature hides behind an
  `except`.** Updating `_render_figure` broke two existing tests not because
  the logic was wrong but because `_stub_render` lacked the new keyword — and
  the symptom was "every render failed", not `TypeError`, because `figure`
  catches render failures by design. Same shape as the Task 2 finding: a broad
  `except` converting a signal into silence.

- **The shell dropped out of `ocean14` again** and a full-suite run reported
  "12 failed, 355 passed, **33 skipped**". The 33 skips were the tell — the
  usual number is 1. Two of the 12 were real (the fixture + stub above) and ten
  were `bing` missing from base conda. Checking `which python` alongside the
  result is the only thing that separates them; the skip count is a second,
  cheaper tell worth remembering.

Files touched: `pab/pipeline.py` (`figure`, `_render_figure`,
`_figures_parallel`, `PipelineConfig.figure_version`, `--figure-version`),
new `nautilus/v2_figrep_job.yaml`, new `pab/tests/test_figure_guards.py`,
`pab/tests/test_pipeline.py`. Not committed — git is JXP's.
