# Improving the PAB report on readthedocs

## Goals

Improve the PAB report on readthedocs

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

### Prep

1.  I wish to report a number of things shown in the report at: `https://pab-report.readthedocs.io/en/develop/index.html`:
    - While it was correct to hold the b_bp values for GIOP and BING at their separately evaluated wavelengths, for the comparions in the Report, we need to shift GIOP to 700nm.
    We can use the power-law slope for b_bp that they adopted in their fits. 
    - This page shows no figures: `https://pab-report.readthedocs.io/en/develop/figures.html` and writes that it is because there are too many.  There are too many to show, but we can show a few representative ones.  Please modify that
    - The comparison figures on this page: `https://pab-report.readthedocs.io/en/develop/comparisons.html` are difficult to read.  The b_bp figure is skewed by a set of outliers with very high satellite b_bp values.  And the dots are large enough that we can't
    see the distribution well.  Can you generate a figure that shows the 2D histogram where
    the data density is high and then dots where the data density is low?
    - On the same comparisons page, use a different color for the Chlorophyll-a figure.  
    Similarly, we wish for a 2D histogram where the data density is high and then dots where the data density is low.
    - On the same page, the matchup locations figure is lame.  We can't tell where land is, the dots are too large, and the color bar range is skewed by this set of outliers.
    - Again, the GIOP vs BING figure is skewed by a set of outliers with very high satellite b_bp values.  Let's ignore them in this figure.  And, again, let's use a separate color for this figure and a 2D histogram where the data density is high and then dots where the data density is low.  Instead of a solid color, we might use a gradient color bar
    that expresses a useful other quanitity from the fit, e.g. CDOM or Chl concentration.

Before doing any of these changes, have a conversation with me to discuss the changes and get my approval.  Put your questions in the Q&A/v2 section below.
Use Fable if you can.  Log your work.

2. I have answered your first round of questions.  Please read my responses
and ask any follow-up questions.
Use Fable if you can.  Log your work.

3. I have answered your second round of questions.  Please read my responses
and then create a series of prompts to implement the changes in the Edits section below.
Use Fable if you can.  Log your work.

### Edits

Seven prompts (E1, E1b, E2–E6), to be run **in order on the workstation**, on the
`report-improvements` branch (E1b only has to precede E5). Every decision they
rely on is recorded in **Q&A/v2** (rounds 1 and 2) and **Q&A/Edits** — read
them before starting any of them.
Common rules for all of them: git is the user's (no `git add/commit/push`); each
prompt ends with `ruff check pab` and the named tests green; each logs its work
under **Logs** in this file in the usual format; anything surprising goes in the
log, not silently worked around. Shared constants: the v2 database is
`$PAB_DATA_DIR/v2/pab.db` and the frozen v1 database `$PAB_DATA_DIR/v1/pab.db`
(open v1 read-only only, per HOWTO §5b); the published downloads prefix is
`https://s3-west.nrp-nautilus.io/pab/v2`; `BBP_IMPLAUSIBLE = 1.0` m⁻¹ in
`pab/report/rst.py` is the runaway threshold.

**E1 — Find the per-matchup figure files on the workstation and finalize E5/E6.**
The galleries (E5) need files, not just rows, and the database records PVC
paths. Do, read-only:
1. Query `$PAB_DATA_DIR/v2/pab.db` (`file:…?mode=ro`) for the distinct directory
   prefixes and row counts of `fits.figure_path` (BING, `pab_version='2.0'`),
   `matchups.scene_path`, and `mld_summary.qa_path`. Expected: ~15,971 under
   `/data/v2/pipeline/figures/`, ~14,586 under `/data/v1/pipeline/figures/`,
   ~58,181 under `/data/run1k/pipeline/argo_qa/`.
2. For each set, locate a workstation root: look under `$PAB_DATA_DIR` (`v1/`,
   `v2/`, `full/`, `run1k/`, `pipeline/`, `figures/`, `argo_qa/`), then
   `find`/`mdfind` by the basename of three sample files per set. Count how
   many of the set's basenames exist under the best candidate root (sample
   500 rows, not all).
3. If a set is absent locally, check the two other sources without changing
   anything: the rclone backup (`rclone lsd AIOcean:PAB/`, `rclone size` on the
   matching folder — the 2.0 fit figures are known to be at
   `AIOcean:PAB/v2/figures/`, 17,363 files) and the PVC (`kubectl get pods`
   per HOWTO; if a pod is up, `kubectl exec … ls /data/v1/pipeline/figures |
   head`). Record, per set, the cheapest way to fetch a *handful* of named
   files (an `rclone copy --files-from` or `kubectl cp` one-liner).
4. Confirm `$PAB_DATA_DIR/v1/pab.db` and `$PAB_DATA_DIR/v2/pab.db` exist, their
   sizes, and whether v2 is byte-identical to the 2026-10-07 Drive copy
   (217,325,568 bytes; compare size and sha256). Note the current
   `pab_version`/fit counts if they differ from the Q&A numbers.
5. Write a **Findings** subsection directly under this prompt: a table
   *set | stored prefix | rows | workstation root (or "absent") | sampled
   files found | fallback fetch*. Then **edit prompts E5 and E6 below**,
   replacing the `<FIT_FIG_ROOT>`, `<SCENE_ROOT>`, `<ARGO_QA_ROOT>`
   placeholders with the real roots, and for any absent set replacing the
   bracketed "if absent" clause in E5 with the concrete fetch command. No
   code changes in this prompt. Use Fable if you can. Log your work.

**E1 Findings (2026-10-17).** All stored paths are flat (basename directly
under the prefix, no subdirectories). Searched `$PAB_DATA_DIR`
(`/mnt/tank/Oceanography/data/Color/PAB`; `~/Oceanography` is a symlink to
`/mnt/tank/Oceanography`), `$HOME` and `/mnt/tank` to depth 9: **none of the
three sets is on the workstation** except the 965 run1k Argo Q&A plots. The
Drive backup (`AIOcean:PAB/`) holds every set except the 2.0-backfill Argo
Q&A plots, which exist only on the PVC. Roots used by E5/E6: the fetched
files go into a new `$PAB_DATA_DIR/gallery/{v2_figures,v1_scenes,argo_qa}/`
(outside the frozen `v1/`); `<list>.txt` below is one basename per line,
written from the E5 selection, split by stored prefix.

| set | stored prefix | rows | workstation root | sampled files found | fallback fetch |
| --- | --- | ---: | --- | --- | --- |
| BING 2.0 fit figures | `/data/v2/pipeline/figures/` | 15,971 | absent | 0/500 local; 500/500 in `AIOcean:PAB/v2/figures/` (15,971/15,971 by name) | `rclone copy AIOcean:PAB/v2/figures/ $PAB_DATA_DIR/gallery/v2_figures/ --files-from fits.txt --no-traverse` |
| scene quick-looks, 1.0 run | `/data/v1/pipeline/figures/` | 14,586 | absent (249 same-named files in `run1k/pipeline/figures/` are the run1k renders; not used) | 450/450 in `AIOcean:PAB/site/_static/scenes/` (14,586/14,586 by name) | `rclone copy AIOcean:PAB/site/_static/scenes/ $PAB_DATA_DIR/gallery/v1_scenes/ --files-from scenes_v1.txt --no-traverse` |
| scene quick-looks, 2.0 backfill | `/data/v2/pipeline/figures/` | 1,390 | absent | 50/50 in `AIOcean:PAB/v2/figures/` (1,390/1,390 by name) | same remote folder and local root as the fit figures: add the names to `fits.txt` |
| Argo Q&A, 1.0 full run | `/data/full/pipeline/argo_qa/` | 51,763 | absent | 458/458 in `AIOcean:PAB/site/_static/argo_qa/` (52,728 files = 51,763 full + 965 run1k) | `rclone copy AIOcean:PAB/site/_static/argo_qa/ $PAB_DATA_DIR/gallery/argo_qa/ --files-from qa.txt --no-traverse` |
| Argo Q&A, run1k | `/data/run1k/pipeline/argo_qa/` | 965 | `$PAB_DATA_DIR/run1k/pipeline/argo_qa/` | 11/11 sampled, 965/965 by name | none needed (also in the Drive folder above) |
| Argo Q&A, 2.0 backfill | `/data/v2/pipeline/argo_qa/` | 5,453 | absent | 0 — in no Drive folder | PVC only: `kubectl -n sea-meets-the-stars cp <pod>:/data/v2/pipeline/argo_qa/<WMO>_<cycle>.png <dest>`; needs a pod (none up, none launched) |

Notes:
- Counts vs the prompt's expectations: fit figures 15,971 as expected;
  `scene_path` is non-null on all 15,976 matchups = 14,586 v1 + 1,390 v2
  (the "~14,586" was the v1 part); `qa_path` is non-null on 58,181 of 59,620
  `mld_summary` rows (1,439 NULL) but split over **three** prefixes, mostly
  `/data/full/`, not `/data/run1k/` as the prompt assumed.
- Profiles behind the 15,971 BING 2.0 fits, by Q&A prefix: 14,564 full, 300
  run1k, 684 v2 (PVC-only), 423 NULL — so ~7 % of candidate fits have no
  fetchable Q&A plot; E5 must tolerate a missing panel (see Q&A/Edits 1).
- Databases: `v1/pab.db` 169,938,944 B, sha256 `09de0a6d…8273` (the HOWTO
  §5b invariant). `v2/pab.db` 217,325,568 B, sha256
  `1e69f6eef09b85add89b04ac45d423d9d981fbd81b097d0856dab59687d8a3f8`;
  `rclone hashsum sha256 AIOcean:PAB/pab_v2_2026-10-07.db` returns the same
  (md5 `c5ba6c3a…4b88` also equal) — **byte-identical** to the Drive copy.
  Fit counts unchanged from the Q&A: BING `2.0` 15,971 (all with a
  `figure_path`), NASA_GIOP `1.1` 15,976 (no figures). Matchups: 14,610 `1.0`
  + 1,366 `2.0`. The HOWTO §5b sha for v2 (`eb9a341a…`, 207,638,528 B) is the
  pre-NASA-GIOP state, preserved as `v2/pab_pre_nasagiop_20261003.db`.
- Drive layout: `AIOcean:PAB/` = `pab.db`, `pab_merged_nasa_giop_2026-09-10.db`,
  `pab_v2_2026-10-07.db`, `fit_chains/` (empty), `site/_static/{argo_qa 52,728
  files 2.03 GiB, scenes 14,586 / 794 MiB, figures 14,609 v1 fits / 864 MiB,
  downloads}`, `v2/{figures 17,361 files 1,018 MiB (15,971 fits + 1,390
  scenes), fit_chains (empty), site/}`. The Q&A's "17,363" was off by two.
- Kubernetes: `kubectl get pods` in the default namespace is forbidden; use
  `kubectl -n sea-meets-the-stars get jobs,pods` — no jobs or pods exist.
- The three `rclone copy … --files-from … --no-traverse` commands were
  verified with `--dry-run` on two names each (35–83 KB per file;
  `--no-traverse` avoids listing the 52 k-entry Drive folder).
- **Superseded by E1b (Q&A/Edits 1 = C):** the "Argo Q&A, 2.0 backfill" row
  becomes root `$PAB_DATA_DIR/gallery/v2_argo_qa/` (whole folder copied off
  the PVC) with a Drive copy at `AIOcean:PAB/v2/argo_qa/`.
- **Correction (E1b, 2026-10-17):** the two `fit_chains/` folders are *not*
  empty — `rclone size` gives `AIOcean:PAB/fit_chains/` 14,654 files /
  18.087 GiB (1.0) and `AIOcean:PAB/v2/fit_chains/` 15,971 / 18.327 GiB
  (2.0, matching the PVC). See Q&A/Edits 6.

**E1b — Copy the 2.0-backfill Argo Q&A plots off the PVC and back them up
(Q&A/Edits 1 = C).** The 5,453 plots under `/data/v2/pipeline/argo_qa/` exist
only on the (un-backed-up) PVC. Bring the whole folder to the workstation
once, then `rclone copy` it to Drive, so E5 needs no pod. No code changes;
nothing on the PVC is written.
1. Write `nautilus/argo_qa_copy_pod.yaml`: a pod `pab-argoqa-copy` in
   namespace `sea-meets-the-stars`, image `python:3.12-slim` (has `tar`),
   `command: ["sleep", "14400"]`, `restartPolicy: Never`,
   `activeDeadlineSeconds: 14400`, small requests (cpu 500m, 1 Gi), the
   `pab-data` PVC mounted at `/data` with **`readOnly: true`**; header
   comment with usage and cleanup, in the style of `nautilus/inspect_pod.yaml`
   (which exits immediately, so it cannot be used for `kubectl cp`).
2. **The user launches it.** Stop and ask them to run
   `! kubectl apply -f nautilus/argo_qa_copy_pod.yaml`, then wait until
   `kubectl -n sea-meets-the-stars get pod pab-argoqa-copy` is `Running`.
3. In the pod: `ls /data/v2/pipeline/argo_qa | wc -l`, `du -sh` on it, and an
   md5 list (`cd /data/v2/pipeline/argo_qa && md5sum *.png > /tmp/qa.md5`,
   then `cat` it back). Record the count; if it differs from the DB's 5,453
   `/data/v2/pipeline/argo_qa/` rows, say by how much and copy the whole
   folder anyway. While the pod is up, also record `ls /data/v2/fit_chains |
   wc -l`, `du -sh /data/v2/fit_chains` and `tail -40 /data/v2/backup.log`
   (the log of the earlier `v2_backup_job.yaml` run — it should say why the
   chains never reached Drive) for the chains side task below (Q&A/Edits 3);
   do not copy the chains.
4. Transfer **compressed, as a stream** (HOWTO §5b transfer note: a plain
   `kubectl cp` has no resume and has died mid-file before):
   `kubectl -n sea-meets-the-stars exec pab-argoqa-copy -- tar czf - -C
   /data/v2/pipeline argo_qa > $PAB_DATA_DIR/gallery/v2_argo_qa.tgz`, `gzip -t`
   it, then extract into `$PAB_DATA_DIR/gallery/` and rename to
   `$PAB_DATA_DIR/gallery/v2_argo_qa/`. Verify the local file count and
   `md5sum -c` against the in-pod list (all OK); then delete the `.tgz`.
5. Back up: `rclone copy $PAB_DATA_DIR/gallery/v2_argo_qa/
   AIOcean:PAB/v2/argo_qa/ --transfers 8` (**`copy`, never `sync`** — the
   destination is the shared 1.0/2.0 backup), then `rclone check
   $PAB_DATA_DIR/gallery/v2_argo_qa/ AIOcean:PAB/v2/argo_qa/ --one-way` (0
   differences) and the remote count.
6. Clean up: `kubectl -n sea-meets-the-stars delete pod pab-argoqa-copy`
   and confirm it is gone. If anything failed before this point, still
   delete the pod and log where it stopped.
7. Update E5/E6 if anything differs from what they now assume (root
   `$PAB_DATA_DIR/gallery/v2_argo_qa/` for prefix
   `/data/v2/pipeline/argo_qa/`), and add a line to HOWTO's backup paragraph
   (the one naming `AIOcean:PAB/`) that `v2/argo_qa/` was added on this date.
   Use Fable if you can. Log your work.

**E2 — GIOP `b_bp` at 700 nm (Q1 = A, Q2 = A, F3 agreed).**
Derive, never persist. In `pab/metrics/compare.py::gather_nasa_giop` add a
`LEFT JOIN` on `NASA_GIOP_bbp_s` and new columns `bbp_s_nasa`,
`bbp_700_nasa`, `bbp_700_nasa_lo`, `bbp_700_nasa_hi`, where
`bbp_700 = bbp_442 × (442/700) ** bbp_s` and the bounds scale by the same
factor (NaN where the slope is null; keep every 442 column). Put the factor
in one helper (e.g. `giop_bbp_to_700(bbp_442, slope)`) so the Methods text and
the code cannot drift. Then in `pab/report/rst.py`:
- `nasa_giop_section`: statistics (`compare.log_comparison`) on `bbp_700_nasa`
  vs `bbp_bing`; the stats line reads "median NASA(700)/BING(700)"; the figure
  (still `population.comparison_scatter` for now — E3 swaps it — but pass
  `clip_percentile=99.0` so it is readable in the interim) plots 700 vs 700
  with matching axis labels; the Bokeh branch likewise.
- Replace `_NASA_BBP_CAVEAT` with a note that states the formula, that the
  slope is NASA's own per-pixel `bbp_s`, the **computed** fraction of slopes
  sitting at GIOP's ceiling of 2.0 (expected ≈ 14.6 %; compute as
  `bbp_s >= 1.99`, never hard-code) with the sentence that those pixels' 700 nm
  values are the least constrained, and the unadjusted 442-vs-700 median ratio
  **computed from the same frame** (expected ≈ 2.16) quoted once "for
  continuity with the previous release".
- `methods_page`: update the NASA-GIOP paragraph the same way (formula +
  ceiling caveat); remove every remaining "as-is, no spectral adjustment"
  phrasing (grep for `442` in `rst.py`).
- Downloads: there is no NASA-GIOP table today (`publish.export_tables` writes
  only `gather_matchups`). Add `nasa_giop_summary.{csv,parquet}` from
  `gather_nasa_giop` to `export_tables`, and list it on the Downloads page
  next to the matchup summary (same `downloads_base_url` mechanism).
Tests: `pab/tests/test_metrics.py` — a synthetic store with a NASA-GIOP row
(value, bounds, slope) checks the 700 nm value/bounds and the null-slope → NaN
path; `pab/tests/test_report.py` — the section text mentions 700 nm, no longer
contains "no spectral adjustment", and the stats are those of the 700 nm
column; `export_tables` writes the new table. Acceptance on the real v2 DB
(read-only, a throw-away `outdir`): median NASA(700)/BING(700) ≈ 0.94,
Spearman ≈ 0.89, ceiling fraction ≈ 14.6 %. Use Fable if you can. Log your work.

**E3 — The density-plus-dots scatter (Q5, Q6, F4).**
Add `pab.plotting.population.density_scatter(df, sat_col, insitu_col, *,
label, unit, xlabel=None, ylabel=None, cmap="Blues", bins=50, min_count=5,
clip_percentile=99.0, outfile=None, dpi=100)`:
- Both axes log10. Plot range = the central `clip_percentile` of the pooled
  finite positive values of both columns, × 0.7 below and × 1.4 above (the same
  rule `comparison_scatter` uses), and the number of matchups outside the range
  printed in the title as `[N off-scale]`.
- `numpy.histogram2d` on the log10 values over that range, `bins × bins`.
  Cells with **≥ `min_count`** matchups are drawn with `pcolormesh` on the
  given sequential colormap with a `LogNorm` count colorbar labelled
  "matchups per cell". Matchups falling in cells below the threshold are drawn
  individually as dots (marker size 2.5, alpha 0.6) in a dark shade of the same
  hue (e.g. `cmap(0.75)`).
- Keep the 1:1 line, the dashed median-ratio line, the legend, and the title
  format `n=… ρ=… bias=… RMS=… (log10)` — with the statistics from
  `log_comparison` on **all** finite positive pairs, runaways included (Q6).
- Stay under `SIZE_BUDGET`; set `rasterized=True` on the mesh and dots.
Keep `comparison_scatter` (tests and the interim E2 figure use it). Wire
`density_scatter` into: `_static_comparison_figures` (`b_bp` → `Blues`,
chlorophyll → `Greens`), `nasa_giop_section` (`Purples`; x = BING 700, y =
NASA 700 from E2), and `_version_static_figures` (`Blues` / `Greens`, replacing
`clip_percentile=99.0` + dots). Each caption says what is drawn: "filled cells
where ≥ 5 matchups fall in a cell, individual points elsewhere; N matchups lie
outside the axes and are counted in the statistics". Tests
(`test_metrics.py`): file written and under budget; a 20-point frame (all
dots, no cells) renders; NaN/≤0 rows are ignored; a frame with three values
at 1e4 reports `3 off-scale` in the title and the same `n` as
`log_comparison`; `test_report.py`: the new captions appear on the
Comparisons page. Acceptance: render the four panels from the real v2 DB and
look at the PNGs (the Read tool displays them) — the runaways must no longer
set the axes, and the dense core must show structure. Use Fable if you can.
Log your work.

**E4 — The two maps (Q8 = Robinson, 2nd–98th percentile, HEALPix; F5 agreed).**
1. Rewrite `pab.plotting.population.matchup_map` (keep the existing call
   signature working; add keywords): cartopy `Robinson()` axes, land filled
   light grey (`cartopy.feature.LAND`, facecolor `0.85`) with coastlines at
   linewidth 0.4; dots at marker size 3, alpha 0.6, `transform=PlateCarree()`;
   colour = `log10(sat/float b_bp)` (compute from the two columns; the caller
   no longer passes a `ratio` column) on `RdBu_r`, **symmetric** about 0 with
   `vmax = max(|p2|, |p98|)` of the per-matchup log-ratio, colorbar labelled
   `log10(satellite / float b_bp)`; title with n. Fallback, in this order: no
   cartopy importable → plain lon/lat axes with a `_log.warning`; cartopy
   present but the Natural Earth download fails (no network) → Robinson axes
   without land/coast and a warning. Add a `projection=None` keyword that
   forces the plain-axes path so tests never touch the network.
2. Add `pab.plotting.population.healpix_map(df, *, cell_size_deg=5.0,
   min_count=5, vmax=None, …)`: assign cells with
   `pab.report.aggregate.assign_healpix` / `nside_for_cell_size`, per-cell
   median log-ratio and count, draw only cells with `≥ min_count` matchups as
   polygons from `healpy.boundaries(nside, pix, step=4, lonlat=True)` through
   `PlateCarree` onto the same Robinson/land background; split or drop
   polygons that straddle the dateline (log how many); **same colour scale
   as the dot map** — the caller computes `vmax` once from the per-matchup
   log-ratio and passes it to both. Title with the number of cells drawn and
   the matchups they hold.
3. Wire both into `_static_comparison_figures` (`matchup_map.png`,
   `healpix_map.png`) with captions stating the clip and the ≥ 5 rule.
4. Add `cartopy` to `requirements.txt`. In HOWTO §7a note that the first
   cartopy use downloads Natural Earth coastlines (network once; cached under
   `~/.local/share/cartopy`) and that the Docker image was **not** rebuilt for
   this pin because the report stage runs on the workstation (F6).
Tests (`test_metrics.py`): both functions with a synthetic frame using
`projection=None`, files written; the shared `vmax` is symmetric; the HEALPix
threshold drops thin cells; a size budget for maps of 250 KB. Acceptance:
render both from the real v2 DB and look at them — land visible, no colourbar
driven by the runaways. Use Fable if you can. Log your work.

**E5 — Representative figure galleries (Q4 = A; paths from E1).**
Roots found by E1 (none of the sets is on the workstation except the run1k
Q&A plots; the rest is fetched from the Drive backup into
`$PAB_DATA_DIR/gallery/`): fit figures and 2.0 scenes
`$PAB_DATA_DIR/gallery/v2_figures/` (stored prefix
`/data/v2/pipeline/figures/`), 1.0 scene quick-looks
`$PAB_DATA_DIR/gallery/v1_scenes/` (`/data/v1/pipeline/figures/`), Argo Q&A
`$PAB_DATA_DIR/gallery/argo_qa/` (`/data/full/pipeline/argo_qa/`), the 2.0
backfill Q&A plots `$PAB_DATA_DIR/gallery/v2_argo_qa/`
(`/data/v2/pipeline/argo_qa/`; the whole folder, copied by E1b — nothing to
fetch) and the existing `$PAB_DATA_DIR/run1k/pipeline/argo_qa/`
(`/data/run1k/pipeline/argo_qa/`).
Fetch only the files selected below: after implementing the selection, write
the selected basenames to three lists split by stored prefix (`fits.txt` =
fit figures + any `/data/v2/…` scenes, `scenes_v1.txt` = `/data/v1/…` scenes,
`qa.txt` = `/data/full/…` and `/data/run1k/…` Q&A plots) and run
```
mkdir -p $PAB_DATA_DIR/gallery/{v2_figures,v1_scenes,argo_qa}
rclone copy AIOcean:PAB/v2/figures/ $PAB_DATA_DIR/gallery/v2_figures/ --files-from fits.txt --no-traverse
rclone copy AIOcean:PAB/site/_static/scenes/ $PAB_DATA_DIR/gallery/v1_scenes/ --files-from scenes_v1.txt --no-traverse
rclone copy AIOcean:PAB/site/_static/argo_qa/ $PAB_DATA_DIR/gallery/argo_qa/ --files-from qa.txt --no-traverse
```
(verified with `--dry-run` in E1; ~35–85 KB per file). If E1b has not been
run, stop and run it first. Only the 423 candidate fits whose profile has no
`qa_path` (2.6 %) have no Q&A plot at all: the Q&A gallery drops such a panel
with the counted warning of step 1 and the log says how many (Q&A/Edits 1:
no selection bias toward fits that have a plot).
1. **Path remap.** Add a repeatable `--figure-root OLD=NEW` option to
   `--emit-site` in `pab/pipeline.py`, passed as `figure_roots: dict` into
   `rst.build_site` and applied inside `_stage_static` (longest-prefix
   match). A source that still does not exist on disk is dropped with one
   `_log.warning` per gallery (counted, not per file).
2. **Selection**, in `pab/report/rst.py`, deterministic and documented:
   - `select_representative_fits(df)` → 8 rows: the matchups whose
     `log10(bbp_bing/bbp_argo)` is nearest the 5th, 25th, 50th, 75th and 95th
     percentiles (finite positive pairs only; ties → smallest `matchup_id`);
     the runaway with the largest `bbp_bing` above `BBP_IMPLAUSIBLE` (skip if
     none); and, within the clearest and the most productive `chl_bing`
     tercile, the matchup nearest that tercile's median log-ratio. De-duplicate
     while keeping order. Each caption: `WMO/cycle — <why>` (e.g. "50th
     percentile of sat/float b_bp, ratio 1.08", "non-physical retrieval,
     b_bp = 9.3e4 m⁻¹", "clearest tercile, Chl 0.03 mg m⁻³").
   - Scenes: one per `region` from `compare.add_strata` (the matchup nearest
     the region's median log-ratio), 6 at most — the 6 most populous regions
     if there are more.
   - Argo Q&A: the profiles behind the 8 selected fits.
3. **Rendering.** `_thumbnail_gallery` gains a `representative=` argument:
   above `max_inline` it renders the subset with an intro "N matchups — too
   many to show inline. The 8 below were chosen to span the sat/float
   agreement from the 5th to the 95th percentile, plus one failed retrieval
   and the clearest and most productive regimes; every figure is available as
   a download (Downloads page)." `_gather_with_figures` stops staging the
   whole population (it already does above the thresholds) and stages only
   the selected files. Stage **downscaled** copies (longest side 1200 px, via
   Pillow/Matplotlib, PNG) so the committed site grows by a few MB at most;
   the thumbnail links to the staged copy; log the total bytes staged.
4. Tests (`test_report.py`): the selection is deterministic and returns the
   documented reasons on a synthetic frame (with and without a runaway); the
   remap resolves a prefix and drops a missing file; above `max_inline` the
   figures page contains exactly the selected thumbnails. Acceptance: run
   `pab --db $PAB_DATA_DIR/v2/pab.db --emit-site <tmp> --figure-root …` and
   check `figures.rst` lists 8 / ≤6 / 8 items with reasons. Use Fable if you
   can. Log your work.

**E6 — Rebuild the site, verify, close out (F2).**
1. Regenerate:
   `pab --db $PAB_DATA_DIR/v2/pab.db --compare-db $PAB_DATA_DIR/v1/pab.db
   --emit-site report_site --downloads-base-url
   https://s3-west.nrp-nautilus.io/pab/v2
   --figure-root /data/v2/pipeline/figures=$PAB_DATA_DIR/gallery/v2_figures
   --figure-root /data/v1/pipeline/figures=$PAB_DATA_DIR/gallery/v1_scenes
   --figure-root /data/full/pipeline/argo_qa=$PAB_DATA_DIR/gallery/argo_qa
   --figure-root /data/v2/pipeline/argo_qa=$PAB_DATA_DIR/gallery/v2_argo_qa
   --figure-root /data/run1k/pipeline/argo_qa=$PAB_DATA_DIR/run1k/pipeline/argo_qa`
   (one `--figure-root` per stored prefix from E1/E1b), then
   `python -m sphinx -b html report_site report_site/_build` with no new
   warnings. (E5 ran before E1b: all 8 selected fits sit on `/data/full/…`
   Q&A profiles, so the galleries need nothing from `gallery/v2_argo_qa/`;
   keep the flag anyway — the remap tolerates a root that does not exist.)
2. Verify by looking (Read each PNG): the four density panels, the two maps,
   the galleries, and in `comparisons.rst` the GIOP numbers (median ratio
   ≈ 0.94, ρ ≈ 0.89, ceiling ≈ 14.6 %, the unadjusted 2.15 — E2 measured
   2.15, not the Q&A's 2.16 — quoted once). Check `du -sh
   report_site` and `git status --short report_site` so the committed tree
   stays small (target: under 10 MB added); no `_build` or stray files.
2b. **Upload the NASA-GIOP table (Q&A/Edits 4 = A).** The Downloads page
   links `https://s3-west.nrp-nautilus.io/pab/v2/nasa_giop_summary.{csv,parquet}`,
   which do not exist yet. Run `publish.export_tables` against the v2 DB
   (read-only) into a scratch folder; first check (anonymous `curl -sI` on the
   two public URLs) that neither object exists — if one does, stop and
   report rather than overwrite. Then upload each file with
   `NautilusS3Backend(bucket="pab", prefix="v2").upload(path)` (HOWTO §7b;
   write credentials from the boto3 chain — if none are configured, stop and
   ask the user, do not hunt for keys), re-download each from its public URL
   and compare sha256 with the local file, and `curl -sI` the existing
   `v2/matchup_summary.csv` to confirm it was not touched. Record the two
   URLs, sizes and sha256s in the log and add `v2/nasa_giop_summary.*` to
   HOWTO §5b's S3 row.
3. Docs: update `docs/design/PAB_implementation.md` (reporting section: the
   700 nm derivation, `density_scatter`, the two maps, representative
   galleries, `--figure-root`), HOWTO §7a (the new flags and the rebuild
   command above), and `docs/reporting.rst` if it describes the figures.
4. Run the full suite (`pytest pab/tests -q`) and `ruff check pab`.
5. Hand-off: list for the user the files to commit (code, tests, docs,
   `requirements.txt`, `report_site/`) and remind that RTD rebuilds on push
   to the branch the report project tracks. Do not commit. Use Fable if you
   can. Log your work.

*Retired (Q&A/Edits 6 = A, 2026-10-18): E1b found the v2 chains already on
Drive (15,971 files, 18.33 GiB); nothing to re-run. Kept for the record.*

**Side task (not part of the E-sequence; Q&A/Edits 3 = A) — re-run the v2
chains backup.** Any time after E1b (which records the chain count/size and
the tail of `/data/v2/backup.log`). Read `nautilus/v2_backup_job.yaml` and
that log; if it shows why the chains step failed, say so and propose a fix to
the job (e.g. the 24 h `activeDeadlineSeconds`) before anything runs. The
user creates the temporary `aiocean-rclone` secret and applies the job
(`kubectl -n sea-meets-the-stars delete job pab-v2-backup
--ignore-not-found; kubectl apply -f nautilus/v2_backup_job.yaml`); Claude may
monitor `kubectl logs -f job/pab-v2-backup`. When it reports
`V2_BACKUP_DONE`, confirm `rclone size AIOcean:PAB/v2/fit_chains/` matches the
PVC count (15,971) and size, remind the user to delete the secret
(`kubectl -n sea-meets-the-stars delete secret aiocean-rclone`) and the
finished job, and note the backup in HOWTO. `rclone copy`, never `sync`.
Use Fable if you can. Log your work.

### Outliers

1. Now, let us dig in on the outliers in the b_bp figure.  Please identify these -- they have satellite b_bp > 1e4.  Create a separate file named "versions/v2/high_bbp_outliers.md" with a report showing a few of these fits and discuss what may have gone wrong.
If you have any questions or suggestions for next steps, 
put them under Q&A/Outliers.
Use Fable if you can. Log your work.

2. I have read your report and then answered your questions.  
Please generate a series of prompts in this Prompts/Outliers section starting with #3 that I will execute to complete the work.
Use Fable if you can. Log your work.

*Seven prompts (O3–O9), to be run **in order on the workstation** (`ocean14`)
on the `report-improvements` branch; O8 is independent and can run any time
after the chains are local. The decisions they rely on are **Q&A/Outliers**
1–5 (answered) and **6–9** (new — answer each before the prompt that cites
it). The Edits rules carry over: git is the user's; each prompt ends with
`ruff check pab` and the named tests green; each logs under **Logs**;
surprises go in the log, not silently worked around. What is new: **O4 and O6
write to `$PAB_DATA_DIR/v2/pab.db`** (the live copy, HOWTO §5b), which the
E-series never did. Write discipline for both: a dated copy first
(`v2/pab_pre_<step>_<date>.db`, the `pab_pre_nasagiop_20261003.db`
precedent), sha256 + per-table counts before and after, **no existing 2.0 row
changed** (a checksum over the 2.0 `fits`/`fit_results` rows identical before
and after — the design's provenance rule), `v1/` read-only as always, and
`PAB_DATA_DIR=$PAB_DATA_DIR/v2` for anything that writes chains (they land at
`$PAB_DATA_DIR/fit_chains/`, never next to `--db`). Facts from the report and
the code the prompts lean on: the 51 runaways are the BING `pab_version='2.0'`
fits with `BING_ExpBPow_bbp700 > 1` (the same set at > 10⁴);
`bing.parameters.standard.expb_pow` puts log-uniform [10⁻⁶, 10⁵] priors on
`Adg`, `Aph` (ExpBricaud pnames `['Adg','Sdg','Aph']`) and `Bnw` (Pow pnames
`['Bnw','beta']`, `Bnw` = `b_bp` at the 600 nm pivot); `expb_pow(**kwargs)`
forwards `apriors=`/`bpriors=` into the `p` namedtuple and
`set_standard_priors` uses them verbatim, so PAB can cap the ceilings without
touching BING; `fits.prior_set` (today always `"bing_standard"`) is where a
changed prior set is recorded, no schema change needed.*

3. **O3 — Gate the 51 out of the `b_bp` statistics; amend the run report
   (Q&A/Outliers 1 = B, 4 = A; Q&A/Outliers 6).** No re-fit, no DB write.
   1. Move `BBP_IMPLAUSIBLE = 1.0` to `pab/metrics/compare.py` (keep
      `rst.BBP_IMPLAUSIBLE` importable) and add `compare.implausible_bbp(values)
      -> mask` and `compare.gate_bbp(df, col="bbp_bing") -> (df_gated,
      n_excluded)` (the column set to NaN where the mask is true; nothing else
      touched). Feed the gated frame to **every `b_bp` statistic and figure**
      built from `bbp_bing`/`bbp700_v2`: `summary_page` headline,
      `_static_comparison_figures` (the `b_bp` density panel, `matchup_map`,
      `healpix_map` — gated matchups become "without a ratio", grey), the
      `aggregate.aggregate_by`/`aggregate_healpix` callers (Aggregates page),
      `nasa_giop_section` (BING side) and `version_section` (`bbp700_v2` in
      the stats line, `_version_ratio_by_level`, `_ratio_figure_block`,
      `_version_static_figures`). Do **not** gate `select_representative_fits`
      (the gallery keeps its "non-physical retrieval" pick) or the exported
      tables (raw values stay; add a derived 0/1 column `bbp_bing_implausible`
      in `gather_matchups` so a reader can filter). Chl of the same fits: per
      Q&A/Outliers 6 (default if unanswered: gate `b_bp` only).
   2. Wording, computed never hard-coded: every gated caption and stats line
      carries "N failed retrievals (x.xx %, ``b_bp`` > 1 m⁻¹) excluded";
      `_version_failure_note` says excluded instead of "left in"; **delete
      `_runaway_regime_note` and `_RUNAWAY_CHL_EDGES`** (the Chl-rate table *is*
      the misreading) and put one paragraph in their place: marginal-sea
      spectra with a depressed or negative blue Rrs (float Chl median 0.93
      mg m⁻³ — not clear water), the LM warm-start delivered to the `Bnw`
      prior ceiling of 10⁵ m⁻¹ while a better physical basin exists in every
      re-fitted case, a re-fit under 2.0.1 is pending (O7 rewrites this
      sentence), and a pointer to
      `https://github.com/ocean-colour/PAB/blob/main/versions/v2/high_bbp_outliers.md`.
      Methods page: a "Failed retrievals" paragraph with the gate, the
      computed count and the same pointer.
   3. `docs/design/PAB_v2_run_report.md` §2.5: replace the regime paragraph
      and the Chl-rate table with the corrected reading, keeping one line that
      says what was believed on 2026-10-07 and when/why it was corrected; §7
      item 2 → resolved, with the pointer. `PAB_implementation.md` §13.5 and
      §5e.2: a one-line pointer each.
   4. Tests: `test_metrics.py` — `gate_bbp` masks only above the gate, counts,
      leaves other columns; `test_report_versions.py` —
      `test_failure_note_counts_non_physical_bbp` asserts "excluded" and that
      the Chl-rate table is gone; `test_report.py` — summary/comparisons/
      methods text carries the count and the pointer, aggregates come from the
      gated frame, `export_tables` keeps raw values plus the flag column.
      Acceptance on the real v2 DB (read-only, throw-away `outdir`): the
      `b_bp` headline n drops by the number of runaways that have a float
      value (50–51 of 15,274); record the new median ratio / ρ / RMS next to
      the old 1.15 / 0.41 / 0.65 in the log. Use Fable if you can. Log your
      work.

4. **O4 — The negative-blue QA count as a `fit_results` quantity
   (Q&A/Outliers 3 = A; Q&A/Outliers 7 for the chains).**
   1. `pab/fit/run.py`: `BLUE_QA_BAND = (400.0, 450.0)` and a pure
      `rrs_qa_quantities(wave, Rrs) -> list[dict]` returning one quantity
      `n_neg_blue` (value = number of finite bands with `Rrs < 0` and
      `400 ≤ λ ≤ 450`; `value_lo = value_hi = value`; unit `"bands"`), computed
      on the **windowed** spectrum (`wave_w`, `Rrs_w` from `prepare_spectrum`
      — exactly what the chain NPZs store, so fit-time and backfilled values
      agree by construction). `fit_spectrum` appends it to `quantities`; the
      existing `persist_fit` writes it as `BING_ExpBPow_n_neg_blue` — no
      schema change. **Never a refusal:** `build_fits` fits such a spectrum as
      before (test it).
   2. Backfill for the 15,971 existing 2.0 fits: `python -m
      pab.fit.rrs_qa_backfill --db … --chains-root DIR [--pab-version 2.0]
      [--dry-run] [--replace]` — resolves `fits.chains_path` by **basename**
      under `--chains-root` (the stored paths are PVC paths
      `/data/v2/fit_chains/…`), reads `wave`/`Rrs` from each NPZ, upserts
      **only** the `n_neg_blue` row per fit (refuses a fit that already has
      one unless `--replace`; a missing NPZ is counted and skipped with one
      summary warning), prints the plan under `--dry-run`. This is a QA
      backfill on existing records at the same version — the design's
      documented precedent (the 1.0 Chl-a/CDOM re-ingest) — not a
      re-analysis. Chains: per Q&A/Outliers 7 (recommended: `rclone copy
      AIOcean:PAB/v2/fit_chains/ $PAB_DATA_DIR/v2/fit_chains/ --transfers 8`,
      15,971 files / 18.3 GiB, then `rclone check … --one-way`; this also
      makes HOWTO §5b's workstation row true — check `df -h` first). Write
      discipline as in the preamble; after: `fit_results` +15,971 rows, every
      other table and every pre-existing `fit_results` row identical,
      `PRAGMA integrity_check` ok. Expected: ≈ 0.7 % of the non-runaways and
      40 of the 51 with `n_neg_blue ≥ 1` (report §5).
   3. Report + table: `gather_matchups` LEFT JOINs the quantity as
      `n_neg_blue` (NaN where absent); the Comparisons failure note gains a
      computed sentence ("N of M spectra (x %) have at least one negative
      band at 400–450 nm; K of the N failed retrievals do"); the Methods
      *Retrieval* section defines the quantity; `matchup_summary.{csv,parquet}`
      carry the column (re-uploaded in O9).
   4. Tests: `test_fit.py` — `rrs_qa_quantities` on synthetic spectra (0 and 3
      bands, the 450 nm edge inclusive, NaN bands ignored, bands outside
      400–450 ignored), `fit_spectrum`'s quantities include it (extend the
      robust known-answer test), `persist_fit` writes it; new
      `test_rrs_qa_backfill.py` — synthetic store + tmp NPZ: writes the row,
      idempotent, `--dry-run` writes nothing, `--replace` overwrites, a
      missing NPZ is counted not fatal, other `fit_results` rows untouched;
      `test_metrics.py`/`test_report.py` — the column and the sentence. Use
      Fable if you can. Log your work.

5. **O5 — The 2.0.1 configuration: physical prior ceilings, step-0 check,
   replay seam (Q&A/Outliers 2 = A; Q&A/Outliers 8).** Code and tests only —
   nothing fitted, no DB write.
   1. `FitConfig` gains `bbp600_max: float | None = 0.1`, `adg_max: float |
      None = 10.0`, `aph_max: float | None = 10.0` (m⁻¹; `None` = BING's
      10⁵). `build_models` applies them as a **PAB-side override**: call the
      factory as now, then `p = p._replace(apriors=…, bpriors=…)` with copies
      of the factory's own prior dicts whose `pmax` is `log10(ceiling)` for
      `Adg` (index 0 of `['Adg','Sdg','Aph']`), `Aph` (index 2) and `Bnw`
      (index 0 of `['Bnw','beta']`; confirm the 600 nm pivot in
      `bing/models/bbnw.py` before naming it), nothing else changed.
      `set_standard_priors` takes `p.apriors`/`p.bpriors` verbatim, so BING is
      untouched and both `_prior_bounds` (the LM bounds) and BING's `log_prob`
      see the ceiling. `persist_fit` stamps `prior_set` from the config
      (`"bing_standard"` when all three are `None`, else
      `"bing_standard+ceiling:bbp600<=0.1,adg<=10,aph<=10"`, built by one
      helper so text and bounds cannot drift). Add `FitConfig.v2_0()` — the
      frozen, unceilinged 2.0 configuration, like `v1()` — and make `v1()` set
      the three to `None` (the 1.0 priors must not change retroactively).
      Rename `test_fitconfig_defaults_are_the_2_0_configuration` to the 2.0.1
      one; add `v2_0()` and `v1()` ceiling tests.
   2. `pab.config.pab_version = "2.0.1"` and `setup.py` to match (`pip install
      -e . --no-deps`; `test_pab_version_is_2_0` → `_is_2_0_1`). `make_fit_id`
      then yields `…_v2.0.1`, so the new rows coexist with the 2.0 ones (a new
      record, never an overwrite). Say in the `pab_version` docstring what
      2.0.1 is: same data, physics and matchups as 2.0, priors capped at
      physical ceilings, applied as a **patch** to the runaways (O7 defines
      how the report overlays it).
   3. Step-0 check: `pab.fit.run.chain_start_report(chains, param_names,
      config) -> dict` — the step-0 walker-median of each capped parameter in
      dex below its ceiling and a boolean `started_below_wall` (`Bnw` median
      ≥ 0.5 dex under `log10(bbp600_max)`; `Adg`/`Aph` likewise);
      `fit_spectrum` logs a **warning** when it is false (never fails) and
      `FitSpectrumResult` carries the dict, so O6 can tabulate it from the
      NPZs as well.
   4. Replay seam (only if Q&A/Outliers 8 = C): `build_fits(…, spectra=None)`
      and `fit_matchup(…, spectrum=None)` accept a callable `inp -> (wave,
      Rrs, Rrs_unc)`; when given, **no granule is opened**.
      `pab.fit.replay.spectrum_from_chains(root)` returns such a callable: it
      names the **2.0** fit of the same matchup/pixel
      (`make_fit_id(…, version="2.0")`), loads its NPZ under `root` by
      basename and returns `wave`, `Rrs`, `sqrt(varRrs)` — the spectrum the
      2.0 fit saw. `rrs_source` is stamped `"L2_AOP:replay:<2.0 fit_id>"`.
      CLI: `--replay-chains DIR` on the `fit` stage (`pab/pipeline.py`; HOWTO
      §3 row). If Q&A 8 = A or B, skip this step.
   5. `fit_fig._config_from_row` must still rebuild a config from a row (it
      needs no priors; test that a ceiling `prior_set` string round-trips).
      Tests for 1–4 in `test_fit.py`: `_prior_bounds` returns the `log10`
      ceilings, a `None` leaves BING's 5, the `prior_set` string, the replay
      callable reproduces the NPZ spectrum, `build_fits` with `spectra=` never
      calls the opener. Use Fable if you can. Log your work.

6. **O6 — Re-fit the 51 under 2.0.1 (the run; Q&A/Outliers 8).** On the
   workstation; ~51 × 3 min of CPU over `--jobs 8` plus the one-time JAX
   compile — under an hour. The v2 database is **written** here.
   1. Pre-flight: O5 in the working tree, `pytest pab/tests -q` green,
      `python -c "from pab.config import pab_version; print(pab_version)"` →
      `2.0.1` and `pip show pab` the same. Dated copy
      `$PAB_DATA_DIR/v2/pab_pre_v201_<date>.db`; record sha256, per-table
      counts, and a checksum over the 15,971 2.0 `fits` rows + their
      `fit_results`.
   2. The selection, by SQL, never from Appendix A: the 2.0 BING fits with
      `BING_ExpBPow_bbp700 > 1` → `versions/v2/high_bbp_outliers/refit_51.csv`
      (`matchup_id, fit_id_2_0, pixel_id, wmo, cycle, bbp700_2_0`; 51 rows).
      Chains for the replay: nothing to fetch if O4's `rclone` brought all of
      `v2/fit_chains/`; else `rclone copy AIOcean:PAB/v2/fit_chains/
      $PAB_DATA_DIR/v2/fit_chains/ --files-from <51 basenames> --no-traverse`.
   3. Run (replay path, Q&A 8 = C): `PAB_DATA_DIR=$PAB_DATA_DIR/v2 pab --db
      $PAB_DATA_DIR/v2/pab.db --outdir $PAB_DATA_DIR/v2/pipeline --stage fit
      --jobs 8 --matchups-csv versions/v2/high_bbp_outliers/refit_51.csv
      --replay-chains $PAB_DATA_DIR/v2/fit_chains 2>&1 | tee
      $PAB_DATA_DIR/v2/logs/refit_51_<date>.log`. The `PAB_DATA_DIR` override
      puts the new NPZs in `v2/fit_chains/`; the `--matchups-csv` is the only
      thing between this command and a 15,971-fit re-run under 2.0.1 (the 2.0
      `fit_id`s do not block the 2.0.1 ones) — the log line "fit: selection
      restricts to 51" must appear before anything is fitted. (Q&A 8 = A:
      drop `--replay-chains`, add `--download --cache-dir
      $PAB_DATA_DIR/granules`, budget ~25 GB and hours; = B: write
      `nautilus/v201_refit_job.yaml` on the `v2_fit_slice_job.yaml` pattern —
      rebuilt image, DB-local dance, DB returned compressed — and the user
      applies it.) Then `PAB_DATA_DIR=$PAB_DATA_DIR/v2 pab --db … --outdir …
      --stage figure --figure-version 2.0.1 --jobs 4` (fit figures only;
      every scene exists).
   4. Verify: exactly 51 rows with `pab_version='2.0.1'`, `fit_id` ending
      `_v2.0.1`, `prior_set` the ceiling string, `rrs_source` the replay
      stamp, `success=1`, `chains_path` under `v2/fit_chains/`, `figure_path`
      set, `n_neg_blue` present (O4); the 2.0 checksum unchanged; `fits` +51,
      `fit_results` +12 × 51 (the 11 quantities + `n_neg_blue`);
      `integrity_check` ok. Science: `chain_start_report` over the 51 NPZs
      (all started below the wall — list any that did not); posterior
      `bbp600`/`Adg`/`Aph` upper bounds versus the ceilings (within 5 % of
      one is a finding, not a success); χ²(2.0.1) vs χ²(2.0) per fit (expect
      lower in all or nearly all — §4 saw 1.5–23×); `b_bp`(700) at 2.0.1 vs
      float, 1.0 and GIOP (Appendix A has the columns). Append **Appendix C —
      the 2.0.1 re-fit** to `versions/v2/high_bbp_outliers.md`: the 51-row
      table, a two-panel figure (2.0 vs float with the 51 in orange; 2.0.1 vs
      float) in `high_bbp_outliers/`, and a short reading — how many are now
      physical, how many still sit at a ceiling and what those look like.
   5. Back up: `rclone copy` the 51 NPZs to `AIOcean:PAB/v2/fit_chains/` and
      the 51 figures to `AIOcean:PAB/v2/figures/` (`copy`, never `sync`), a
      dated DB copy to `AIOcean:PAB/pab_v2_<date>.db`, `rclone check …
      --one-way`; HOWTO §5b: new DB sha/size, the 2.0.1 rows, the chains now
      on the workstation. Nothing on the PVC is touched. Use Fable if you can.
      Log your work.

7. **O7 — Show the 2.0.1 values in the report: the patch-version overlay
   (Q&A/Outliers 1 = C).** Today the gatherers either filter to **one**
   `pab_version` (`gather_matchups` via `newest_bing_version`, and
   `_version_key` already ranks `2.0.1` above `2.0` — so after O6 the site
   would silently shrink to **51 matchups**) or to **none**
   (`gather_nasa_giop` and `gather_version_pair` join `fits` on `model_pair`
   only — the 51 matchups would appear **twice**). One rule fixes both.
   1. `compare.version_family(store, version=None) -> (base, patches)`: a
      patch version `X.Y.Z` reports its base `X.Y` superseded, per
      `(matchup_id, pixel_id)`, by the patch rows; `compare.overlay_patch(df)`
      drops a base row where a patch row exists for the same matchup **and
      pixel**. Apply it in `gather_matchups`, `gather_nasa_giop`,
      `gather_version_pair` (those 51 pairs become 1.0 vs 2.0.1) and the
      figure stage's default version (`--figure-version` stays explicit).
      Every frame keeps its per-row `pab_version` so the exported tables say
      which rows are patched. `summary_page`: "BING fits: 15,971 (15,920 at
      2.0, 51 re-fitted at 2.0.1)", computed. `publish.build_manifest` and
      the Downloads page list the chains/figures of both versions.
   2. Text: `_version_failure_note` becomes the 2.0.1 story — in 2.0, N fits
      (computed from the 2.0 rows, which stay in the database) ran away; they
      were re-fitted under 2.0.1 with the physical ceilings (quote
      `prior_set`); K of them now sit below the gate and are what every
      statistic on this page uses; any still above it remain excluded by O3's
      gate (count computed; the gate stays permanently). Methods: the
      `pab_version` paragraph gains 2.0.1 and the overlay rule in one
      sentence; the *Retrieval* section names the ceilings.
      `select_representative_fits`: the "non-physical retrieval" slot becomes
      "re-fitted runaway" — the matchup with the largest **2.0** `b_bp`, shown
      with its 2.0.1 figure and the caption "2.0 ``b_bp`` 9.3e4 → 2.0.1 x m⁻¹
      (float y)"; the old behaviour stays when no patch exists (test both).
   3. `docs/design/PAB_design.md` *Provenance & versioning*: a paragraph on
      patch versions (same database and matchup set; rows keep their own
      stamp; the report overlays by matchup **and pixel**; base rows are never
      deleted). `docs/fitting.rst` and HOWTO §5b: the 2.0.1 semantics in one
      line each.
   4. Tests (`test_metrics.py`, `test_compare_versions.py`, `test_report.py`,
      `test_report_versions.py`): a synthetic store with a 2.0 and a 2.0.1 fit
      on the same pixel → one row with the 2.0.1 values; a 2.0.1 fit on a
      *different* pixel of the same matchup does not supersede; no duplicates
      in the NASA-GIOP and version-pair frames; `version_family` on a
      2.0-only store → `("2.0", [])`; the summary sentence; the gallery slot
      in both regimes; `export_tables` rows carry `pab_version`. Acceptance on
      the real DB (read-only): 15,971 rows, 51 of them `2.0.1`, the `b_bp`
      headline now excludes only what is still above the gate (expected
      0–few); record median/ρ/RMS again next to O3's. Use Fable if you can.
      Log your work.

8. **O8 — The emulator out-of-domain slice test, `on_out_of_domain="ztt"`
   (Q&A/Outliers 5 = A).** BING-side and **non-blocking**: run any time after
   the chains are local (O4/O6); no database or BING code changes, nothing
   persisted. `bing.evaluate` builds its jitted forward model with
   `robust_rt.forward(…, mode, inelastic, corrections=False, emulator=…)` and
   never passes `on_out_of_domain`, so production runs the default `"warn"`
   (silent under `jit`); `"ztt"` is traceable (`robust/rt/hybrid.py`, zeroes
   the emulator correction outside the training range) and the default
   emulator **does carry a domain** (`load_default().domain.shape == (2, 7)`,
   checked 2026-10-18), so the policy would act.
   1. Script `versions/v2/ztt_slice/run_ztt_slice.py` (kept in the repo; run
      with `PAB_DATA_DIR=<scratch>` so no chain can land in `v2/`): installs
      `robust.rt.forward = functools.partial(forward,
      on_out_of_domain="ztt")` **before** `bing.evaluate` builds (and
      `lru_cache`s) its forward function — in the parent and in every worker
      initializer — and proves the patch is live on a known out-of-domain IOP
      set (`"ztt"` must equal `mode="ztt"` there). Inputs from the NPZs: the
      51 runaways + 50 ordinary 2.0 fits (seed 42; the report's 300-fit sample
      list if it survives in scratch, else re-drawn), geometry and Chl seed
      from the DB (read-only). Arms, both under the **2.0 priors**
      (`FitConfig.v2_0()` — the question is whether the basin survives, not
      whether the ceiling hides it): (i) `"warn"` control, (ii) `"ztt"`. LM
      only for all 101 × 2 (seconds each); full MCMC (production `nsteps`)
      for 8 runaways + 8 ordinary × 2 arms (~1.5 h at 8 jobs). Record per
      spectrum and arm: `emulator.out_of_domain(...)` at the LM solution and
      the `DomainWarning`s BING raises at the initial guess and posterior
      median (`warnings.catch_warnings(record=True)`; do **not** set
      `PYTHONWARNINGS=ignore` as the pods do).
   2. Questions, each answered with a number: of the 51, how many LM runs end
      at the 10⁵ ceiling under `"warn"` (the CPU control; §4 saw 3 of 4) and
      under `"ztt"`; the χ² profile versus fixed `Bnw` (§4 method) for the
      four report cases under `"ztt"` — does the wall at 1–10 m⁻¹ move,
      vanish or stay; for the 50 ordinary fits, `Δlog10 b_bp(700)` and `Δχ²`
      between arms (≈ 0 if production never leaves the domain in the physical
      basin — if not, that is the bigger finding); the out-of-domain fraction
      at the ordinary posterior medians.
   3. Write-up `versions/v2/ztt_slice.md` (figures in `ztt_slice/`): method,
      the numbers, a reading, and a closing section **"Question for the bing
      repo"** — whether `on_out_of_domain` should be exposed through
      `rt_dict`/`FitConfig` and what its default should be, with the evidence
      — phrased for the user to carry into the bing repo; no BING change
      here. Link it from `high_bbp_outliers.md` §6 item 4. Use Fable if you
      can. Log your work.

9. **O9 — Rebuild the site, publish the amended tables, docs, close out
   (Q&A/Outliers 9).** After O3–O7 (O8 optional).
   1. Regenerate with the E6 command (HOWTO §7a: the five `--figure-root`
      flags, `--compare-db`, `--downloads-base-url`), zero dropped-figure
      warnings, `python -m sphinx -b html report_site /tmp/…` with 0 warnings.
      Both databases byte-identical before and after (the site build never
      writes).
   2. Verify by looking (Read each PNG and `.rst`): the `b_bp` panels, maps
      and aggregates built from the gated, overlaid frame; the summary
      "15,971 (15,920 at 2.0, 51 at 2.0.1)"; the failure note with its
      computed counts and pointer; the negative-blue sentence; the Methods
      paragraphs; the gallery's re-fitted-runaway slot; `du -sh` /
      `git status --short report_site` (committable tree still a few MB, no
      `_build`).
   3. Publish: `publish.export_tables` into scratch; **this time the S3
      objects are replaced on purpose** — `v2/matchup_summary.{csv,parquet}`
      (new columns `n_neg_blue`, `bbp_bing_implausible`, `pab_version`; 51
      changed rows) and `v2/nasa_giop_summary.{csv,parquet}` (51 changed
      rows). First download the current objects to
      `$PAB_DATA_DIR/v2/s3_prev_<date>/` and confirm their sha256 against
      HOWTO §5b / run report §6 (`6622a78c…`, `4754e237…`, `21b4b6ce…`,
      `66f6cb27…`), then upload with `NautilusS3Backend(bucket="pab",
      prefix="v2")`, re-download, compare, and record old/new sizes + sha256.
      The database itself per Q&A/Outliers 9 (recommended: upload the
      2026-10-07 file first under the dated key `v2/pab_2026-10-07.db`, then
      replace `v2/pab.db`; verify both by re-download).
   4. Docs: `PAB_implementation.md` new §14 (the gate, `n_neg_blue` + the
      backfill, the 2.0.1 ceilings / `prior_set` / replay seam / step-0
      check, the patch overlay, what the re-fit showed, the O8 pointer);
      HOWTO (§3 `--replay-chains`, §4 `fit` row: ceilings are the default
      from 2.0.1, §5b S3/sha rows and backup folders); `docs/fitting.rst`
      (priors, the QA quantity); `docs/reporting.rst` (gate + overlay);
      `PAB_v2_run_report.md` §6 (a dated row for the amended objects — do not
      rewrite the 2026-10-07 shas) and §7 item 2 resolved;
      `versions/v2/high_bbp_outliers.md` gets a **Status** block at the top
      listing what O3–O8 did, with dates.
   5. `pytest pab/tests -q`, `ruff check pab`. Hand-off: files to commit
      (code, tests, docs, `report_site/`, `versions/v2/…`, `setup.py`), the
      DB/chain backups made, and the RTD reminder (`…/en/develop/` tracks
      `develop`). Do not commit. Use Fable if you can. Log your work.

## Q&A

### Outliers

Raised by Outliers 1 (`versions/v2/high_bbp_outliers.md`). The short version:
the 51 fits above 1 m⁻¹ are all above 10⁴ m⁻¹; they are marginal-sea
spectra (25 Baltic, 9 tropical Atlantic, 7 Arabian Sea …) with a depressed
or negative blue Rrs (40 of 51 negative at 400–450 nm); the LM warm-start
delivered every one of the 51 chains to the `Bnw` prior ceiling (10⁵ m⁻¹)
and the 1 % walker ball never left it, although a physical basin with a
*better* χ² exists in every re-fitted case (`b_bp`(700) within ~2× of the
float). They are not the "ultra-oligotrophic tail" the run report §2.5 says.

**1 — What the v2 report does with the 51 now.** Options: **A** leave them
in every statistic and flag them (what the site does today); **B** drop them
from the `b_bp` statistics behind the existing `BBP_IMPLAUSIBLE = 1 m⁻¹`
gate, with the count ("51 failed retrievals, 0.32 %, excluded") in the
captions and the Methods page (recommended — they are optimiser failures,
not measurements, and the gate is already defined); **C** wait for the
re-fit (item 2) and show the re-fitted values. B now and C when the re-fit
is done are compatible.

**Your answer:** Yes, let's go with B now and C when the re-fit is done.

**2 — Re-fit the 51 under a new `pab_version`?** The spurious basin is a
property of the prior ceiling (`Bnw` log-uniform to 10⁵ m⁻¹) plus a
start-sensitive LM. Options: **A** re-fit only the 51 under `pab_version`
2.1 with a physical ceiling on the priors (`b_bp`(600) ≤ 0.1 m⁻¹, `A_dg`,
`A_ph` ≤ 10 m⁻¹) applied as a PAB-side override of `expb_pow`'s priors
(BING untouched), and a check that step 0 of each chain is below the wall
(recommended; ~51 × 3 min on the workstation or a short pod job);
**B** also add a multi-start LM (best of N perturbed starts, or seeded from
the 1.0 Gordon solution) to the fit stage for every future fit; **C** change
the ceiling in BING's `expb_pow` itself (affects every BING user); **D** leave
the 51 as they are. If A or B, say whether the re-fit should go into the v2
report as a second version or wait for a v3.

**Your answer:** Let's go with A, but call it v2.0.1

**3 — An Rrs QA flag.** "Any Rrs < 0 at 400–450 nm" catches 40 of the 51 and
flags ≈0.7 % of the rest (2 of 300 sampled, both themselves doubtful fits);
no spectral screen separates the 11 all-positive Baltic runaways from good
Baltic fits. Options: **A** store the count of negative 400–450 nm bands per
fit (a `fit_results` quantity, no schema change) and show it in the report
and the downloadable table, without refusing to fit (recommended);
**B** refuse to fit pixels with a negative blue band (loses 2903902/30-type
cases that fit well in the right basin); **C** nothing.

**Your answer:** Let's go with A.

**4 — Amend the run report §2.5 and the Comparisons-page wording?** The
"ultra-oligotrophic regime" reading rests on the retrieved Chl (0.01), which
is part of the failed fit; the floats say Chl 0.93 mg m⁻³ and `b_bp`
3.6×10⁻³ m⁻¹ (productive marginal seas). Options: **A** amend
`docs/design/PAB_v2_run_report.md` §2.5 and the report's non-physical note
with a pointer to `versions/v2/high_bbp_outliers.md` (recommended; small
edit); **B** leave the run report as a record of what was believed at the
time and only link the new report.

**Your answer:** Let's go with A.

**5 — Emulator out-of-domain policy.** BING calls `robust.rt.forward` with
the default `on_out_of_domain="warn"`, which is silent under `jit`; the
runaway basin is evaluated with the emulator extrapolating at `u ≈ 1`.
`robust` offers `"ztt"` (analytic backbone outside the training range).
Options: **A** a slice test (the 51 + ~50 ordinary fits) with `"ztt"` to see
whether the basin survives — a BING-side change, so it would be a question
for the bing repo (recommended as a side experiment, not blocking items
1–4); **B** ignore for now.

**Your answer:** Let's go with A.

Raised by Outliers 2 (writing O3–O9). Each is cited by the prompt that needs
it; the recommended option is what the prompt assumes if the answer is blank.

**6 — Gate the Chl of the same 51 fits (O3)?** Answer 1 = B says "the `b_bp`
statistics". The retrieval failed as a whole, though: the retrieved Chl of
the 51 is 0.01 mg m⁻³ (the `Aph` mirror cases 900–5,900), and it sits in
the Chl headline, density panel and aggregates today (51 of 15,154 Chl pairs,
0.34 %). Options: **A** gate `b_bp` only, as written; **B** gate the whole
fit — `b_bp` *and* Chl — behind the same `b_bp > 1 m⁻¹` rule, with both
counts in the captions (recommended; one rule, one explanation). Either way
O7's overlay makes it moot for any matchup whose 2.0.1 fit lands physical.

**Your answer:**

**7 — Where the 2.0 chains come from for the `n_neg_blue` backfill (O4).**
The spectra live only in the chain NPZs, and the chains are **not** on the
workstation (HOWTO §5b's text: "only the database came back"; its table row
`v2/fit_chains/` is aspirational) — they are on the PVC and on Drive
(`AIOcean:PAB/v2/fit_chains/`, 15,971 files, 18.3 GiB). Options: **A**
`rclone copy` the whole folder to `$PAB_DATA_DIR/v2/fit_chains/` once
(recommended: one transfer, also gives O6 and O8 their inputs and makes the
HOWTO row true; costs 18.3 GB of disk — check `df -h $PAB_DATA_DIR`); **B**
run the backfill in a pod against the PVC (needs an image rebuild carrying
O4 and a DB round trip, since the workstation copy is the authoritative one);
**C** skip the backfill — only new fits carry the quantity (the report then
cannot show the rate).

**Your answer:**

**8 — What the 2.0.1 re-fit reads as its input spectrum (O5 step 4, O6).**
Options: **A** the production path on the workstation — re-read the pixel
from the granule with `--download` (47 granules × ~0.5 GB ≈ 25 GB of cache,
hours; and NASA may have reprocessed the L2 files since the 2.0 run, so a
different Rrs would confound a test whose only intended change is the
prior); **B** the production path in a pod (in-region, but an image rebuild,
the DB-local dance and a DB round trip; the same reprocessing caveat);
**C** replay the 2.0 spectrum from its own chain NPZ (`wave`, `Rrs`,
`varRrs` exactly as `prepare_spectrum` produced them; geometry and Chl seed
from the DB; minutes; stamped `rrs_source = "L2_AOP:replay:<2.0 fit_id>"` so
the provenance says so) — recommended: bit-identical input, so 2.0 → 2.0.1
differs by the prior and nothing else.

**Your answer:**

**9 — Publish the amended v2 database to S3 (O9)?** After O4 and O6 the
workstation `v2/pab.db` has 15,971 new `fit_results` rows and 51 new fits;
the public `s3://pab/v2/pab.db` is the 2026-10-07 file (`1e69f6ee…`).
Options: **A** replace `v2/pab.db`, after uploading the 2026-10-07 file under
a dated key `v2/pab_2026-10-07.db`, and update HOWTO §5b / run report §6 with
the new sha (recommended — otherwise the site describes rows the public
database does not hold); **B** leave `v2/pab.db` at 2026-10-07, publish only
the tables, and say so on the Downloads page.

**Your answer:**

### v2

Numbers below were read from a copy of the v2 database
(`AI_for_Ocean/PAB/pab_v2_2026-10-07.db`: 15,971 BING 2.0 fits, 15,976
NASA-GIOP rows) and from the committed `report_site/_static/comparisons/*.png`.

**Q1 — GIOP `b_bp` to 700 nm: which slope, and what it does.**
The ingest already stores NASA's per-pixel power-law slope
(`NASA_GIOP_bbp_s`, present on all 15,976 rows), so the shift is
`b_bp(700) = b_bp(442) × (442/700)^bbp_s` (the product variable is `bbp_442`,
so I would use 442, not 443, as the reference). Facts worth knowing before
choosing: `bbp_s` has median 1.92, IQR 1.76–1.98; **14.6 % sit at GIOP's
ceiling of 2.0** and 1.4 % are below 0.5. The median shift factor is 0.41.
Effect on the comparison: median NASA/BING ratio **2.16 → 0.94**, Spearman
0.88 → 0.89.
- **A — per-pixel `bbp_s`** (what the prompt asks; recommended).
- **B — one fixed slope** for every pixel (e.g. η = 1 gives a median ratio 1.36).
I would also scale NASA's `bbp_unc_442` by the same factor so the 700 nm
value keeps its uncertainty.

**Your answer:** A

**Q2 — Where the 700 nm value lives.**
- **A — derived on the fly** in `gather_nasa_giop` (new `bbp_700_nasa`,
  `_lo/_hi` columns, `bbp_442_nasa` kept), and added to the downloadable
  NASA-GIOP table. Nothing is written to the database (recommended: it is
  reproducible from stored rows, no new `pab_version`, and the production
  DB lives on Nautilus/S3).
- **B — persist** a new `NASA_GIOP_bbp_700` `fit_results` row (needs a DB
  write, an S3 re-upload and a backup re-sync).

**Your answer:** A

**Q3 — Your sentence "…that they adopted in their fits. And should" is cut
off.** What did you want to add? One guess: BING also stores `bbp440`, so a
second panel **BING b_bp(440) vs GIOP b_bp(442)** would compare at the blue
end with no GIOP slope assumption at all. Options: **A** 700 nm only;
**B** both panels (cheap, and the two together show whether the slopes
agree).

**Your answer:** Ignore that "And should" part.  It was a typo.

**Q4 — Representative figures on the Figures page.**
Populations: 15,971 fit figures, 15,976 scene quick-looks, 58,181 Argo Q&A
plots. Two decisions:
1. *Which ones.* I would pick deterministically (same choice on every
   rebuild) and say in each caption why it was chosen:
   - **A — by agreement:** the fit figures at the 5th / 25th / 50th / 75th /
     95th percentile of the sat/float `b_bp` ratio, plus one of the 51
     non-physical runaways and one from each of the clearest and most
     productive Chl terciles (8 panels). Shows the reader what good, typical,
     poor and failed fits look like (recommended for the fit gallery).
   - **B — by geography:** one per ocean region from `add_strata` (recommended
     for the scene quick-looks).
   - **C — fixed-seed random.**
   Argo Q&A plots: the profiles behind the chosen fit figures, so the three
   galleries tell one story. Proposed counts: 8 fits, 6 scenes, 8 Q&A.
2. *Where the files are.* The recorded paths are in-pod
   (`/data/v2/pipeline/figures/…` for fits, `/data/v1/pipeline/figures/…`
   for scenes, `/data/run1k/pipeline/argo_qa/…` for Q&A), so a laptop
   build cannot stage them. I found a Google-Drive copy of the v2 fit figures
   (`AI_for_Ocean/PAB/v2/figures`, 17,363 files) but not of the scenes or
   Q&A plots. Options: **A** you rebuild the site in-pod after the code
   change; **B** I add a `--figure-root OLD=NEW` remap to `--emit-site` and
   stage what the laptop can reach (fits only, unless you point me at the
   other two sets).

**Your answer:** (1) A; (2) We should be able to rebuild without launching a pod.  But it might be that I need to run this on my workstation and not my laptop.   Assume that we will do this.  After we discuss, I am going to have you create prompts for all of the changes and then execute them on the workstation.

**Q5 — The density + scatter design (shared by the three comparison panels).**
Proposed: 2D histogram in log10–log10 space, ~50 × 50 cells over the plotted
range; cells holding **≥ 5 matchups** drawn as filled cells on a sequential
single-hue colormap with a log-count colorbar; matchups in sparser cells
drawn as small dots (marker size ~2.5) in the same hue; the 1:1 and
median-ratio lines and the n / ρ / bias / RMS title kept. Axis range from the
0.5–99.5 percentile of the data (the `clip_percentile` mechanism already in
`population.comparison_scatter`), with the off-scale count printed in the
title. Note BING `b_bp` has **two** outlier groups: 51 runaways above 1 m⁻¹
and a low-end pile-up (1 % of fits at 2–4 × 10⁻⁶ m⁻¹, apparently the prior
floor); the percentile clip removes both from the axes while they stay in the
statistics.
- Confirm the 5-matchup threshold and the 0.5–99.5 % clip, or give other
  values.
- Colours: `b_bp` **Blues**, chlorophyll **Greens**, GIOP vs BING **Purples**
  (or Oranges)?

**Your answer:** I like you suggestions.  And, Blues, Greens, and Purples are all good choices.

**Q6 — "Ignore" the outliers in the GIOP figure: axes only, or statistics too?**
Today the page's stance is "reported, not removed" and the medians/ρ are
rank-based (they barely move). Options: **A** exclude the 51 BING values
above 1 m⁻¹ from the panel *and* from that panel's title statistics, and say
so in the title and caption (recommended; the section's stats line would be
computed the same way so the two numbers agree); **B** exclude from the axes
only, statistics unchanged.

**Your answer:** Let's include in the statistics for now.  We will separately investigate these and possibly improve them.

**Q7 — The gradient colour on the GIOP figure.** In a density plot the colour
already encodes counts, so a second quantity needs either a second panel or
to replace density.
- **A — two panels:** left = density (Q5 design); right = the same axes
  coloured by a fit quantity (per-cell median where dense, per-point where
  sparse) with its own colorbar (recommended).
- **B — one panel coloured by the quantity only** (density is lost).
Which quantity: **BING Chl** (log10; ties to the clear-water story on the
same page), **BING `Adg`** (the CDOM + detritus amplitude), **NASA `adg_442`**
(from the same GIOP product), or two of these?

**Your answer:** Good point.  Nevermind coloring by a quantity

**Q8 — The map.** Proposed: cartopy (installed locally, 0.25; **not** in
`requirements.txt`, so I would add it; it downloads Natural Earth coastlines
on first use, so an in-pod build needs network once or a seeded cache, with
a no-coastline fallback if the import fails); land filled light grey with
coastlines; dots at marker size ~3, alpha 0.6; colour = **log10(satellite /
float b_bp)** on a diverging red–blue scale centred on 0 and clipped at
±0.5 dex (the current colorbar runs to 1.5 × 10⁸ because of the runaways).
- Projection: **A** Plate Carrée (simple, lon/lat axes) or **B** Robinson
  (nicer global view)?
- Clip: ±0.5 dex, or symmetric at the 2nd–98th percentile?
- Add a second map of **HEALPix-cell median log-ratio** (the aggregation
  already exists in `pab.report.aggregate`), which avoids the over-plotting
  of 16 k dots? Yes / no.

**Your answer:** Projection: let's try B; Clip: try 2nd-98th percentile; Yes, add a second map of HEALPix-cell median log-ratio.
Also, add `cartopy` to the `requirements.txt` file.

**Q9 — Scope and rebuild.** I would put the new figures in
`pab.plotting.population` (a `density_scatter` plus the map upgrade) and wire
them into the **static** branch of the Comparisons page (what the published
site uses above 2,000 matchups), leaving the Bokeh branch for small dev runs
unchanged, with tests and an update to `PAB_implementation.md`. After the
code change, do you want me to regenerate `report_site/` on the laptop from
the Google-Drive `pab_v2_2026-10-07.db` (and which file is the frozen v1 for
`--compare-db`: the Sep-5 `pab.db` or `pab_merged_nasa_giop_2026-09-10.db`?),
or will you rebuild in-pod?

**Your answer:** That sounds good.  But assume the edits will be done on the workstation.

### v2 — follow-up (round 2)

Thanks — Q1, Q2, Q5, Q7, Q8 and Q9 are settled and need nothing more. I read
Q6 as: the GIOP panel treats the runaways exactly as the `b_bp` panel does
(clipped off the axes by the percentile range, counted as "off-scale" in the
title, kept in n / ρ / bias / RMS and in the section's stats line). Say so if
that is not what you meant. The open items are all about the workstation
rebuild and the galleries.

**F1 — Where the per-matchup figures are on the workstation (Q4.2).** The
database records pod paths (`/data/v2/pipeline/figures/…` for the 2.0 fit
figures, `/data/v1/pipeline/figures/…` for the scene quick-looks,
`/data/run1k/pipeline/argo_qa/…` for the Argo Q&A plots), so any build off the
pod needs a prefix translation. I would add a repeatable
`--figure-root OLD=NEW` option to `--emit-site`; a gallery whose files are not
reachable is dropped with a log line rather than failing the build.
Please give the workstation paths for whichever of the three sets exist there:
- 2.0 fit figures (the Drive backup has them under `AIOcean:PAB/v2/figures/`,
  so I expect `$PAB_DATA_DIR/v2/figures/` or similar): ______
- scene quick-looks (14,586, rendered in the 1.0 run): ______
- Argo Q&A plots (58,181): ______
If scenes or Q&A plots are not on the workstation, pick one: **A** I copy
only the handful the galleries need from the PVC (6 scenes + 8 Q&A, a
one-off `kubectl cp` in the prompt); **B** those two galleries stay as they
are for now; **C** something else.

**Your answer:** I'm not sure.  Have your first Edit prompt be to find these and record the paths.

**F2 — Databases for the rebuild (Q9, still open).** From HOWTO §5b I would
use `--db $PAB_DATA_DIR/v2/pab.db` and `--compare-db $PAB_DATA_DIR/v1/pab.db`
on the workstation. Confirm, and tell me whether the workstation's v2 database
differs from the Drive copy I profiled (`pab_v2_2026-10-07.db`,
217,325,568 bytes) — if it has moved on since 2026-10-07 the numbers in my
Q1 answer may shift slightly.

**Your answer:** That sounds fine.  But see my first answer too

**F3 — The GIOP wording.** The 700 nm shift makes the current wavelength
caveat, the figure caption, the "median NASA(442)/BING(700)" stats line and
the Methods-page note all wrong. I would replace them with one note that gives
the formula, says the slope is NASA's own per-pixel `bbp_s`, flags that
14.6 % of those slopes sit at GIOP's ceiling of 2.0 (those pixels' 700 nm
values are the least constrained), and quotes the unadjusted 442 nm ratio
(2.16) once for continuity with the previous release. OK, or drop the 2.16
mention?

**Your answer:** Agreed

**F4 — Apply the density design to the 1.0-vs-2.0 panels too?** The
`v2_vs_v1_bbp700` and `v2_vs_v1_chl` scatters on the same page have the same
oversized-dot problem (the Chl one is the largest PNG on the site). I
recommend yes, with the same hues (Blues for `b_bp`, Greens for Chl) so the
page reads as one set.

**Your answer:** Yes please do.

**F5 — HEALPix map parameters.** `aggregate_healpix` defaults to 5° cells. I
propose: 5° cells; draw only cells holding ≥ 5 matchups; colour = median
log10(satellite / float `b_bp`) per cell on the same red–blue scale as the
dot map, clipped at the 2nd–98th percentile of the **per-matchup** log-ratio
so both maps share one colour scale; Robinson projection; grey land. Any
change (cell size, minimum count, separate colour scale)?

**Your answer:** Ok, use your suggestions.

**F6 — How to cut the Edits prompts.** You said you will have me write the
prompts and run them on the workstation. I propose five, to go under
`### Edits`, each self-contained and re-runnable, each logging its work:
1. **GIOP at 700 nm** — derive `bbp_700_nasa` (+ bounds) in `gather_nasa_giop`,
   update the section text / stats / Methods note (F3), export it in the
   downloads table, tests.
2. **Density scatter** — `pab.plotting.population.density_scatter` (Q5
   design), applied to the `b_bp`, Chl and GIOP panels (+ the 1.0-vs-2.0
   panels if F4 = yes), tests.
3. **Maps** — cartopy Robinson dot map with clipped log-ratio and the
   HEALPix median map; `cartopy` added to `requirements.txt`; graceful
   fallback without cartopy so tests stay network-free.
4. **Representative galleries** — the deterministic Q4 selection, captions
   stating why each was chosen, the `--figure-root` remap (F1).
5. **Rebuild & close out** — regenerate `report_site/` from the workstation
   databases (F2), `sphinx-build` preview, update `PAB_implementation.md` and
   HOWTO §7a, hand off for your commit.
Prefer this, or one prompt per bullet of Prep 1 (six), or fewer, larger ones?
Related: `cartopy` in `requirements.txt` changes the Docker image's
dependency list, but the report stage runs on the workstation, so I would
**not** rebuild the image for this and would note that in HOWTO. OK?

**Your answer:**  That looks good, but add a first one that figures out the paths to the files and then creates the prompts.

### Edits

Questions raised while running E1 (answers feed E5/E6).

**1 — The 2.0-backfill Argo Q&A plots exist only on the PVC.** The 5,453
plots under `/data/v2/pipeline/argo_qa/` are in no Drive folder (the backup's
only `argo_qa/` folder holds the 51,763 full-run + 965 run1k plots), and no
pod is up. 684 of the 15,971 BING 2.0 fits (4.3 %) sit on those profiles and
another 423 on profiles with no `qa_path` at all, so a selected fit has a
~7 % chance of having no fetchable Q&A plot. Options: **A** E5 drops the
missing panel with a log line (the Q&A gallery may show 7 of 8;
recommended, nothing to launch); **B** E5's selection skips fits whose Q&A
plot is unreachable (a small bias in which fits are shown); **C** you launch
`nautilus/inspect_pod.yaml` once so E5 can `kubectl cp` the handful — and,
while a pod is up, `rclone copy` the whole 5,453-file folder to
`AIOcean:PAB/v2/argo_qa/`, which also closes the backup gap (the v2 chains
are likewise not in the backup: `AIOcean:PAB/v2/fit_chains/` is empty).

**Your answer:**  Let's go with C, but you can execute the `rclone copy` command.

**2 — Where the fetched files live.** E5/E6 now use a new
`$PAB_DATA_DIR/gallery/{v2_figures,v1_scenes,argo_qa}/` so nothing is written
under the frozen `v1/`. The alternative is to mirror the PVC layout
(`$PAB_DATA_DIR/v2/pipeline/figures/`, `v1/pipeline/figures/`,
`full/pipeline/argo_qa/`), which would let a single `--figure-root
/data=$PAB_DATA_DIR` cover every prefix. Keep `gallery/`?

**Your answer:** Sure, keep `gallery/`.

**3 — The v2 chains are not in the backup.** `nautilus/v2_backup_job.yaml`
was written to copy `/data/v2/fit_chains` (15,971 files, ~19 GB) to
`AIOcean:PAB/v2/fit_chains/`, but E1 found that folder **empty** while the
figures from the same job arrived (17,361 files). So either the chains step
never ran or failed, and the 2.0 chains exist only on the un-backed-up PVC.
E1b records the in-pod count and size while its pod is up but does not copy
them (19 GB is not a pod-to-workstation stream job). Options: **A** re-run
`v2_backup_job.yaml` (it is resumable, `copy` not `sync`; needs the temporary
`aiocean-rclone` secret again), as a separate step outside these prompts
(recommended); **B** leave it; **C** something else.

**Your answer:** A

**4 — Uploading `nasa_giop_summary.{csv,parquet}` to S3 (raised by E2).** The
Downloads page now links
`https://s3-west.nrp-nautilus.io/pab/v2/nasa_giop_summary.{csv,parquet}` next
to the matchup summary, but those objects do not exist yet: `matchup_summary.*`
reached `s3://pab/v2/` through the Prompt-9 publish step (`NautilusS3Backend`),
which E6 does not repeat, and `publish.build_manifest` lists only chains and
figures. Until the upload happens the two new links 404. Options: **A** add
the upload to E6 — a fresh `export_tables` run against the v2 DB, then
`NautilusS3Backend(bucket="pab", prefix="v2").upload(...)` per file and a
re-download + sha256 at the public URL, as Prompt 9 did (needs the S3
credentials on the workstation; recommended); **B** you upload the two files
by hand (E2 wrote them only to its scratchpad: `nasa_giop_summary.csv` 8.35 MB,
`.parquet` 2.89 MB; I can re-export them wherever you like); **C** hide the
links until the objects exist.

**Your answer:** Follow your recommendation.

**5 — The maps' colour clip is set by one tail (raised by E4).** The agreed
rule (Q8, F5) is a symmetric scale at `max(|p2|, |p98|)` of the per-matchup
`log10(sat/float b_bp)`. On the v2 data that is **±1.86 dex**, because the
2nd percentile is −1.86 (the satellite prior-floor group: 611 matchups below
−1 dex) while the 98th is only +0.62 (78 matchups above +1). So the scale is
fixed by the low tail alone and 88 % of the matchups (|log-ratio| ≤ 0.5)
sit in the palest tints of both maps; the Mediterranean HEALPix cell at
−1.48 is the one feature that reads at a glance. The runaways no longer
drive it (that was the point), but the maps still show less than they could.
Options: **A** keep the rule (what E6 will publish); **B** a fixed **±0.5
dex** (the Q8 proposal before the percentile idea; 12 % of matchups then sit
at the end colours, and the captions say so); **C** symmetric at the
5th–95th percentile (±0.73 dex, 7 % saturated); **D** percentiles of
|log-ratio| instead (e.g. the 90th → ±0.6). I would take **B**: a fixed
limit also makes 1.0-vs-2.0 and future runs comparable at a glance. A
one-line change (`LOG_RATIO_PERCENTILES` → a fixed `LOG_RATIO_VMAX`) either
way; nothing in E4 depends on it.

**Your answer:** I choose B

**6 — The v2 chains *are* in the backup; item 3 / the side task rest on a
false reading (raised by E1b).** `/data/v2/backup.log` on the PVC says the
2026-10-07 `v2_backup_job.yaml` run finished normally (`chains local=15971
remote=15971`, `0 differences found`, `15971 matching files`,
`V2_BACKUP_DONE`), and today `rclone size AIOcean:PAB/v2/fit_chains/`
returns 15,971 objects / 18.327 GiB (and `AIOcean:PAB/fit_chains/`, the 1.0
chains also called "empty" in E1, has 14,654 / 18.087 GiB — the HOWTO's
18.09 GiB). Nothing is in the Drive trash and there are no duplicate-named
folders, so E1 simply misread the remote (most likely `rclone lsd`, which
lists only sub-directories and prints nothing for a flat folder of files).
The only real blemish in the log is a harmless rclone `Failed to save
config … read-only file system` (the token refresh could not be written back
to the mounted secret; transfers were unaffected). Options: **A** drop the
side task — nothing to re-run, no secret to create; the count/size match
with the PVC (15,971 files, 19,678,573,593 B vs 18.3G `du`) is already
recorded in the HOWTO backup paragraph by E1b (recommended); **B** still run
a full-hash `rclone check` from a pod (the job's own check was
`--size-only`); **C** re-run the job anyway.

**Your answer:** A

## Logs

### 2026-10-17 (v2 Prompt 1 — reviewed the report code and data; posted Q1–Q9 for approval)

No code was changed: the prompt asks for a discussion first. Read the report
stack (`pab/report/rst.py`, `interactive.py`, `pab/plotting/population.py`,
`pab/metrics/compare.py`, `pab/pace/iop.py`, `pab/fit/nasa_giop.py`), the
committed `report_site/` pages and PNGs, `PAB_v2_run_report.md` §2.5, and the
GIOP decision record in `claude_prompts/pace_giop_gsm.md` (Q3). Profiled a
read-only copy of the v2 database from the Google-Drive backup
(`pab_v2_2026-10-07.db`; the local `~/data/Color/PAB/pab.db` is the Sep-5 v1
snapshot with no GIOP rows).

What I learned, and what shaped the questions:

- **The GIOP 700 nm shift is cheap.** The ingest already stores NASA's
  per-pixel `bbp_s` on every row, so no new download is needed. The slope
  median is 1.92 with 14.6 % pinned at GIOP's ceiling of 2.0. Shifting with
  the per-pixel slope moves the median NASA/BING ratio from 2.16 to 0.94 and
  leaves Spearman essentially unchanged (0.88 → 0.89). Proposed to derive it
  in `gather_nasa_giop` rather than write to the DB (Q1–Q2).
- **Why the figures are unreadable.** The static `comparison_scatter` is
  called without `clip_percentile` on the Comparisons page (the 1.0-vs-2.0
  panels already use 99 %), so the 51 non-physical BING `b_bp` values
  (up to 9.3 × 10⁴ m⁻¹) set the axes; there is also a low-end pile-up at
  2–4 × 10⁻⁶ m⁻¹ (1 % of fits). The map's colorbar runs to 1.5 × 10⁸ for the
  same reason, and dots are drawn at size 40 with no coastlines. Proposed a
  shared density-plus-sparse-dots design, per-figure hues, and a
  cartopy map coloured by clipped log-ratio (Q5–Q8).
- **Representative galleries need the files.** The recorded figure paths are
  in-pod (`/data/v2/…`, `/data/v1/…`, `/data/run1k/…`); the laptop only has a
  Drive copy of the v2 fit figures. Asked whether the site is rebuilt in-pod
  or whether to add a path-remap flag (Q4).
- Cartopy 0.25 is installed locally but absent from `requirements.txt`; the
  RTD build is unaffected because the PNGs are pre-rendered.

Awaiting answers to Q1–Q9 in the Q&A/v2 section before implementing.

### 2026-10-17 (v2 Prompt 2 — read the Q1–Q9 answers; posted follow-ups F1–F6)

No code changed. All nine first-round answers are in: per-pixel `bbp_s` shift
derived in the gatherer (Q1–Q2); the "And should" fragment was a typo (Q3);
agreement-percentile selection for the galleries, built off-pod on the
workstation (Q4); the density-plus-dots design with Blues/Greens/Purples (Q5);
runaways clipped from axes but kept in statistics (Q6); no third-quantity
colouring (Q7); Robinson map, 2nd–98th percentile clip, a HEALPix median map,
and `cartopy` into `requirements.txt` (Q8); workstation rebuild (Q9).

What the answers left open, and why each follow-up exists:

- **Figure locations off-pod (F1).** The galleries are the one change that
  needs files, not just the database, and the stored paths are PVC paths.
  HOWTO §5b documents the workstation layout for the databases and chains
  but not for the per-matchup figures, scenes or Argo Q&A plots, so I asked
  for the three paths and proposed a `--figure-root OLD=NEW` remap on
  `--emit-site` rather than rewriting paths in the (frozen) databases.
- **Which databases (F2).** Q9's "which v1 file" went unanswered; HOWTO §5b
  gives `$PAB_DATA_DIR/v1/pab.db` and `$PAB_DATA_DIR/v2/pab.db`, so I asked
  for confirmation and whether the workstation v2 DB has moved past the
  2026-10-07 Drive copy I profiled.
- **Text that the 700 nm shift invalidates (F3).** The 442-vs-700 caveat is
  stated in three places (`_NASA_BBP_CAVEAT`, the stats line, the Methods
  note); proposed one replacement note including the 14.6 % slope-ceiling
  caveat.
- **Consistency (F4, F5).** The 1.0-vs-2.0 scatters share the dot problem;
  the HEALPix map needs a cell size, a minimum count and a colour-scale
  decision (proposed sharing the dot map's scale).
- **Prompt structure (F6).** The user intends to run the work as prompts on
  the workstation; proposed five self-contained Edits prompts and asked
  whether to leave the Docker image alone despite the new `cartopy` pin.

Next: on the F1–F6 answers, write the Edits prompts into the file.

### 2026-10-17 (v2 Prompt 3 — read the F1–F6 answers; wrote the six Edits prompts)

No code changed. Round two settled everything except where the per-matchup
figure files live on the workstation (F1 "not sure"), so, per the F6 answer,
the Edits section opens with a read-only discovery prompt (E1) that records
the roots in a Findings table and then edits the placeholders in E5/E6. The
other five follow the F6 cut: E2 GIOP at 700 nm (derived in
`gather_nasa_giop`, text/Methods/downloads updated, the 14.6 % ceiling and
the 2.16 unadjusted ratio computed rather than hard-coded), E3
`density_scatter` applied to five panels (the 1.0-vs-2.0 pair included per
F4), E4 the Robinson dot map plus the HEALPix median map sharing one
symmetric 2nd–98th-percentile colour scale (F5) with `cartopy` pinned and the
Docker image left alone, E5 the deterministic galleries with a
`--figure-root OLD=NEW` remap and downscaled staging, E6 the workstation
rebuild, visual verification and docs/HOWTO close-out.

Choices made while writing the prompts, so they are visible:

- E2 keeps the old `comparison_scatter` with a 99 % clip as an interim GIOP
  figure so each prompt leaves the site buildable on its own; E3 replaces it.
- There is no NASA-GIOP downloads table today (`export_tables` only writes
  the matchup summary), so E2 adds one rather than pretending the 700 nm
  column has somewhere to go.
- The scene gallery is "one per region", and `add_strata` regions are
  latitude bands, so E5 says 6 at most and the most populous bands if more.
- Fit figures are ~56 KB each on the Drive copy, so staging ~22 files is a
  few MB; E5 still downscales to 1200 px to bound the committed site.
- E4's maps compute the log-ratio themselves instead of taking the `ratio`
  column the current caller builds, so the runaways can no longer leak into
  a colour scale through a caller.

Next: the user runs E1–E6 on the workstation.

### 2026-10-17 (v2 Edit E1 — located the per-matchup figure files; finalized E5/E6)

Run with Fable. Read-only throughout: the databases were opened with
`file:…?mode=ro`, rclone was used only for `lsd/lsf/size/hashsum` and a
`copy --dry-run`, kubectl only for `get`; no code or data changed. The only
file edited is this one (Findings table under E1, the E5/E6 placeholders,
two questions under Q&A/Edits, this entry).

What was done:

- Queried `$PAB_DATA_DIR/v2/pab.db` for the directory prefixes of
  `fits.figure_path` (BING, `pab_version='2.0'`; the column is `algorithm`,
  not `method`), `matchups.scene_path` and `mld_summary.qa_path`, then
  sampled 500 rows per set and matched them by path suffix and by basename
  against every candidate directory under `$PAB_DATA_DIR`, a `find` over
  `$HOME` and `/mnt/tank` (depth 9), and the file listings of the Drive
  folders (`rclone lsf`, 17,361 + 14,586 + 52,728 names).
- Hashed both databases locally and the Drive copy remotely
  (`rclone hashsum sha256`, which Google Drive supports directly).
- Checked the PVC side: the namespace is `sea-meets-the-stars` (the default
  namespace is forbidden to this user); no jobs or pods exist and none was
  launched.

What I learned, and what was surprising:

- **The prompt's expected prefixes were partly wrong.** Scenes are
  14,586 under `/data/v1/…` *plus* 1,390 under `/data/v2/…` (every matchup
  has a scene). The 58,181 Q&A paths are split over `/data/full/` (51,763),
  `/data/v2/` (5,453) and `/data/run1k/` (965), not all under `run1k`; 1,439
  rows have no plot. So the remap needs four `--figure-root` flags, not
  three, and one prefix (`/data/v2/pipeline/argo_qa/`) has no off-pod root.
- **Nothing but the 965 run1k Q&A plots is on the workstation.** The
  `run1k/pipeline/figures/` directory holds 249 scenes with the same names as
  v1 rows, but they are the run1k renders and were not used as a root.
- **The Drive backup covers everything except the v2 Q&A plots** (and the
  v2 chains: `AIOcean:PAB/v2/fit_chains/` is empty). `v2/figures/` has
  17,361 files (15,971 fits + 1,390 scenes — the Q&A said 17,363), and the
  1.0 site staging under `site/_static/` has all 14,586 v1 scenes and the
  52,728 full + run1k Q&A plots. `rclone copy --files-from --no-traverse`
  against those folders was verified with `--dry-run`.
- **`v2/pab.db` is byte-identical to `pab_v2_2026-10-07.db`** (217,325,568 B,
  sha256 `1e69f6ee…8a3f8` on both sides), so the Q&A numbers stand: 15,971
  BING 2.0 fits, 15,976 NASA-GIOP 1.1 rows. `v1/pab.db` still matches the
  HOWTO invariant. The HOWTO §5b sha for v2 describes the pre-NASA-GIOP file.
- E5 now fetches the selected files into `$PAB_DATA_DIR/gallery/…` and E6
  carries the four real `--figure-root` flags. Two questions went to
  Q&A/Edits: how E5 should treat the ~7 % of candidate fits whose Q&A plot is
  PVC-only or missing, and whether `gallery/` is the right place.

Next: answers to Q&A/Edits 1–2, then E2.


### 2026-10-17 (v2 — read the Q&A/Edits answers; added E1b, updated E5/E6)

No code changed. The answers were: Q&A/Edits 1 = **C** (bring the 2.0-backfill
Argo Q&A plots off the PVC with a pod, and Claude may run the `rclone copy` to
Drive), and Q&A/Edits 2 = keep `$PAB_DATA_DIR/gallery/`. To act on them I added
a new prompt, **E1b**, between E1 and E2. It only has to run before E5. It
writes a sleep pod with the PVC mounted read-only (`inspect_pod.yaml` exits
immediately, so `kubectl cp` cannot use it), asks the user to launch the pod,
streams the whole `/data/v2/pipeline/argo_qa/` folder as a gzipped tar (per
the HOWTO §5b transfer note) into `$PAB_DATA_DIR/gallery/v2_argo_qa/`, checks
it against an in-pod md5 list, `rclone copy`s it (never `sync`) to
`AIOcean:PAB/v2/argo_qa/` with an `rclone check`, deletes the pod and notes
the new Drive folder in HOWTO.

Because the whole folder ends up local, E5 needs no PVC fetch. I removed its
"cannot be fetched" clause; only the 423 fits whose profile has no `qa_path`
(2.6 %) still lose their Q&A panel. E6 gains a fifth flag,
`--figure-root /data/v2/pipeline/argo_qa=$PAB_DATA_DIR/gallery/v2_argo_qa`.
The Edits intro now says seven prompts, and the E1 Findings carry a note that
E1b replaces the PVC-only row.

Something E1 surfaced that these prompts do not fix: `AIOcean:PAB/v2/fit_chains/`
is empty even though `v2_backup_job.yaml` was written to fill it, so the 2.0
chains have no off-site copy. I posted this as Q&A/Edits 3 rather than adding
19 GB to E1b. E1b records the in-pod chain count and size so the question can
be answered.


### 2026-10-17 (v2 Edit E2 — GIOP b_bp shifted to 700 nm)

Run with Fable, in two sittings. The first run was cut off by a session
logout while it was reworking the slope-ceiling wording; the user's commit
`bc6fcec` (titled "E1") holds most of the E2 code — `pab/metrics/compare.py`,
`pab/report/publish.py`, `pab/report/rst.py`, `pab/tests/test_metrics.py`,
`pab/tests/test_report.py` — and two small uncommitted hunks in `rst.py` /
`test_report.py` were the wording edit in progress. The second sitting
reviewed all of it against the prompt, finished the wording, ran the
acceptance and wrote this entry. The database was opened read-only
(`file:…?mode=ro`); the committed `report_site/` was not touched (E6).

What the code does (derive, never persist — Q1 = A, Q2 = A, F3):

- `compare.py`: the wavelengths (`GIOP_BBP_WAVE = 442`, `BING_BBP_WAVE = 700`),
  GIOP's slope ceiling (`GIOP_BBP_S_CEILING = 2.0`, tolerance 0.01 so the
  fraction is `bbp_s >= 1.99`) and the reader-facing formula string
  `GIOP_BBP_SHIFT_FORMULA` are built from the same constants as the helper
  `giop_bbp_to_700(bbp_442, slope)` — the single source of the
  `(442/700)^bbp_s` factor; `giop_slope_ceiling_fraction(slope)` computes the
  pinned fraction (NaN when no finite slope). `gather_nasa_giop` gains a
  `LEFT JOIN` on `NASA_GIOP_bbp_s` and the columns `bbp_s_nasa`,
  `bbp_700_nasa`, `bbp_700_nasa_lo/_hi` (value and bounds scaled by the same
  per-pixel factor; NaN where the slope row is missing, no default slope);
  every 442 column is kept as stored.
- `rst.py`: `nasa_giop_section` computes `log_comparison` on `bbp_700_nasa`
  vs `bbp_bing`, the stats line reads "median NASA(700)/BING(700)", the
  interim `population.comparison_scatter` panel plots 700 vs 700 with
  `clip_percentile=99.0` (off-scale count in the title, runaways stay in the
  statistics — Q6), and the Bokeh branch is relabelled likewise.
  `_NASA_BBP_CAVEAT` is gone; `_nasa_bbp_note(df)` builds the note from the
  frame: the formula, that the slope is NASA's own per-pixel `bbp_s`, the
  computed ceiling fraction with the "least constrained" sentence, and the
  unadjusted 442-vs-700 median ratio from the same frame quoted once "for
  continuity with the previous release". The ceiling sentence is shared with
  the Methods page through `_NASA_BBP_CEILING_CAVEAT` +
  `_methods_ceiling_sentence(store)` (`methods_page(store=…)`, passed by
  `build_site`; without a store the sentence defers to the Comparisons page
  rather than quoting a number). The summary headline is at 700 nm too. No
  "as-is / no spectral adjustment" phrasing remains in `pab/` (the only
  copies left are in the committed `report_site/*.rst`, which E6 regenerates).
- `publish.export_tables` writes `nasa_giop_summary.{csv,parquet}` (keys
  `nasa_giop_csv/parquet`) when the store holds an ingest; `downloads_page`
  lists it next to the matchup summary in both the `downloads_base_url`
  branch and the staged `_static/downloads/` branch (`_DOWNLOAD_TABLES`,
  skipped when there is no NASA-GIOP fit).
- Tests: `test_metrics.py` — the helper/ceiling-fraction unit test and a
  synthetic store with value + bounds + slope checking the 700 nm columns and
  the null-slope → NaN path; `test_report.py` — the section mentions 700 nm,
  states the formula and "median NASA(700)/BING(700)", no longer contains
  "no spectral adjustment"/"as-is", its stats are those of the 700 nm column,
  the ceiling fraction and the continuity ratio appear once, a null slope
  drops the pair from `n`, the Methods page carries the formula and the
  computed fraction (or the deferral without a store), `export_tables` writes
  the new table and the Downloads page links it only with an ingest.
- This sitting's edits: the shared ceiling caveat now reads "… sit at GIOP's
  ceiling of 2.0 — such a slope is a pinned fit rather than a measurement, so
  those pixels' 700 nm values are the least constrained" on the Comparisons
  page and "GIOP bounds the slope at 2.0, and 14.6 % of the slopes sit at
  that ceiling in this release — such a slope is …" on Methods (the first
  sitting had the ceiling value stated twice in a row); the test string
  followed. Named tests, full suite (415 passed, 1 skipped) and
  `ruff check pab` are green.

Acceptance on `$PAB_DATA_DIR/v2/pab.db` (read-only; section, Methods,
Downloads, tables and the PNG rendered into the scratchpad): the frame has
15,971 rows (one per BING 2.0 `ExpBPow` fit with a NASA sibling), every row
has a slope, 7 rows have a null NASA `bbp_442` → n = 15,964. **Median
NASA(700)/BING(700) = 0.937** (IQR 0.747–1.22), **Spearman ρ = 0.889**,
log10 offset 0.000156, RMS 0.52; **ceiling fraction 14.57 %** (15,971
slopes); **unadjusted NASA(442)/BING(700) median 2.154** (ρ 0.874); slope
median 1.92, IQR 1.76–1.98, 1.4 % below 0.5, median shift factor 0.414 — all
as Q1 predicted. The figure: a clean log-log cloud along the 1:1 line with the
median-ratio line just below it, axes 3×10⁻⁶–10⁻² spanning the central 99 %,
"[173 off-scale]" in the title (the 51 runaways above 1 m⁻¹ among them, kept
in the statistics). `nasa_giop_summary.csv` is 8.35 MB, the parquet 2.89 MB.

Surprising, or worth knowing:

- **The continuity ratio is 2.15, not 2.16.** On this frame the unadjusted
  median comes out 2.154; the Q&A's 2.16 was profiled on the Drive copy
  (byte-identical) but evidently on a slightly different join. The note
  prints 2.15; I changed E6's "the 2.16 quoted once" check to 2.15.
- **GIOP has a floor that the shift does not remove.** The panel shows a
  horizontal band of NASA values at ≈2–4×10⁻⁴ m⁻¹ wherever BING retrieves
  less than 10⁻⁴ (431 matchups: NASA(700) median 2.95×10⁻⁴ against BING
  < 10⁻⁴, and 25 % of those slopes are at the ceiling vs 14.6 % overall).
  It is the 442 nm amplitude that never gets small (1st percentile
  5.1×10⁻⁴), so it is a GIOP property, not an artefact of the 700 nm
  extrapolation. Nothing was done about it; it belongs with the Outliers
  work or E3's density panel, where it will be obvious.
- **`ruff check pab` was not green on arrival**: nine pre-existing findings
  in files E2 never touched (`pab/argo/check_argo_coverage.py`,
  `pab/argo/check_gdac.py`: unsorted/multiple imports and `l` as a name;
  `pab/fit/nasa_giop.py`: unused `config` import; `pab/fit/run.py`: import
  block; `pab/pace/cloud.py`: `zip()` without `strict=`;
  `pab/tests/test_pipeline.py`: unused `as store`). Because the Edits rule
  wants ruff green I fixed them mechanically (`strict=False` so `cloud.py`
  keeps its behaviour; the rest are renames/import sorting/removals). Those
  hunks are separable if you would rather not have them in this commit.
- **The new Downloads links point at objects that do not exist yet.**
  `matchup_summary.*` reached `s3://pab/v2/` through the Prompt-9 publish
  step, which E6 does not repeat, and `build_manifest` lists only chains and
  figures — so `…/pab/v2/nasa_giop_summary.{csv,parquet}` will 404 until
  someone uploads them. Posted as Q&A/Edits 4 (recommended: add the upload
  to E6).

Next: the answer to Q&A/Edits 4, then E3.

### 2026-10-17 (v2 — read Q&A/Edits 3–4 answers; updated E1b and E6, added the chains side task)

No code changed. Q&A/Edits 3 = **A** (re-run the v2 chains backup as a
separate step) and 4 = **A** (E6 uploads the NASA-GIOP table to S3).
- **E6** has a new step 2b. It exports `nasa_giop_summary.{csv,parquet}` from
  the v2 DB (read-only), checks that neither public URL exists yet (it stops
  rather than overwrite), uploads with `NautilusS3Backend(bucket="pab",
  prefix="v2")`, re-downloads to check the sha256, confirms
  `v2/matchup_summary.*` is untouched and adds the objects to HOWTO §5b. If no
  S3 write credentials are configured it stops and asks.
- **E1b** step 3 now also records `tail /data/v2/backup.log` from the PVC, so
  we learn why the earlier `v2_backup_job.yaml` run left
  `AIOcean:PAB/v2/fit_chains/` empty.
- A **side task** after E6, outside the E-sequence: diagnose that failure from
  the log, then re-run `v2_backup_job.yaml`. The user creates the temporary
  `aiocean-rclone` secret and applies the job, and Claude monitors it and
  checks the Drive count/size against the PVC. The side task ends with a
  reminder to delete the secret and the job.

E3–E5 needed no changes for these answers.

### 2026-10-17 (v2 Edit E3 — density-plus-dots scatter)

Run with Fable. Both databases were opened read-only (`file:…?mode=ro`,
`create=False`); the committed `report_site/` was not touched (E6). Files
changed: `pab/plotting/population.py`, `pab/report/rst.py`,
`pab/tests/test_metrics.py`, `pab/tests/test_report.py`, this file.

What the code does (Q5, Q6, F4):

- `population.density_scatter(df, sat_col, insitu_col, *, label, unit,
  xlabel, ylabel, cmap="Blues", bins=50, min_count=5, clip_percentile=99.0,
  outfile, dpi)`: both axes log10; the range is the central
  `clip_percentile` of the pooled finite positive values × 0.7 / × 1.4 — the
  `comparison_scatter` rule, now factored into one `_clipped_range` helper
  both functions call; `numpy.histogram2d` of the log10 values over that
  range; cells with ≥ `min_count` matchups as a `pcolormesh` with a `LogNorm`
  "matchups per cell" colorbar; every matchup in a sparser cell as a dot
  (`ms=2.5`, `alpha=0.6`, `cmap(0.75)`); the 1:1 line, the dashed
  median-ratio line, a legend (cells / dots / 1:1 / median ratio) and the
  `n=… ρ=… bias=… RMS=… (log10)  [N off-scale]` title with the statistics
  from `log_comparison` on **all** finite positive pairs (Q6). Mesh and dots
  are `rasterized=True`. `comparison_scatter` is kept (tests, Bokeh-less
  small runs).
- `population.DENSITY_MIN_COUNT = 5` is the `min_count` default and what the
  captions quote; `population.offscale_count(df, sat_col, insitu_col,
  clip_percentile=99.0)` gives a caption the same `N` the title prints (same
  `_clipped_range`), since the figure function returns a `Figure`/`Path`.
- `rst.py`: `_density_caption(df, sat_col, insitu_col)` builds the shared
  caption clause ("Filled cells where ≥ 5 matchups fall in a cell, individual
  points elsewhere; N matchups lie outside the axes and are counted in the
  statistics. The dashed line is the median ratio; the solid line is 1:1.").
  Wired into `_static_comparison_figures` (`b_bp` Blues, chlorophyll
  Greens), `nasa_giop_section` (Purples; x = BING 700, y = NASA 700, the
  interim `comparison_scatter(..., clip_percentile=99.0)` from E2 removed)
  and `_version_static_figures` (Blues / Greens, replacing
  `clip_percentile=99.0` + dots). The Bokeh branches are untouched.
- Tests. `test_metrics.py`: file written under `SIZE_BUDGET` with a mesh and
  dots present; a 20-point frame renders as dots only (no `QuadMesh`,
  `n=20`, no off-scale); NaN / ≤ 0 rows are ignored (`n` in the title equals
  `log_comparison`'s); three values at 1e4 give `[3 off-scale]`, the same `n`
  as `log_comparison` (1000, runaways kept), `offscale_count` = 3, the upper
  axis limit below 1 m⁻¹, and `clip_percentile=None` reports nothing
  off-scale. `test_report.py`: the Comparisons page carries the caption twice
  (`b_bp`, Chl), the GIOP static section once, a frame with three runaways
  says "3 matchups lie outside the axes" on the `b_bp` panel and "0" on the
  Chl panel, and `_version_static_figures` writes both 2.0-vs-1.0 PNGs with
  the same caption form. Named tests 10 passed; full suite **420 passed,
  1 skipped** (415 after E2 → +5); `ruff check pab` clean.

Acceptance on `$PAB_DATA_DIR/v2/pab.db` (+ `v1/pab.db` for the 1.0-vs-2.0
pair), rendered into the scratchpad and looked at. In every panel the
runaways no longer set the axes and the dense core shows its structure:

- **`bbp_scatter.png`** (Blues, 59.6 KB): n = 15,274, ρ = 0.41, bias +0.01,
  RMS 0.65, median ratio 1.15, **155 off-scale**. Axes 3×10⁻⁶–6×10⁻². The
  core is a blob around 5×10⁻⁴–3×10⁻³ on both axes, hugging 1:1 on its upper
  edge; two features that the old all-dots panel hid are now plain — a
  vertical pile of satellite values at 3×10⁻⁶–10⁻⁴ m⁻¹ (the low-end
  prior-floor group from Q5) sitting under float values of 5×10⁻⁴–10⁻³, and
  a sparse cloud at float `b_bp` ≈ 10⁻² with satellite values an order of
  magnitude lower.
- **`chl_scatter.png`** (Greens, 74.5 KB): n = 15,154, ρ = 0.73, bias −0.09,
  RMS 0.59, median 0.94, **166 off-scale**. Core 0.05–1 mg m⁻³ along 1:1,
  slightly below it; a spray of satellite Chl below 10⁻² mg m⁻³ at every
  float Chl (fits whose `A_ph` went to the floor) is the obvious tail.
- **`nasa_giop_bbp_scatter.png`** (Purples, 52.1 KB): n = 15,964, ρ = 0.89,
  bias 0.00, RMS 0.52, median NASA/BING 0.94, **173 off-scale** (the same
  173 as the E2 interim panel). The dense arc follows 1:1 from 10⁻³ up; the
  GIOP floor the E2 log predicted is the dominant off-diagonal feature — a
  horizontal band of NASA values at 2–4×10⁻⁴ m⁻¹ wherever BING retrieves
  less than 10⁻⁴.
- **`v2_vs_v1_bbp700.png`** (Blues, 53.5 KB): n = 14,604, ρ = 0.92, bias
  −0.16, RMS 0.54, median 2.0/1.0 = 0.75, **156 off-scale**. The clear-water
  result reads straight off the mesh: the cells sit on 1:1 above ~2×10⁻³
  and peel away below it, down to the 3×10⁻⁶ floor at 1.0 values of
  3×10⁻⁴–10⁻³.
- **`v2_vs_v1_chl.png`** (Greens, 90.4 KB — the heaviest): n = 14,604,
  ρ = 0.70, bias +0.19, RMS 0.64, median 1.17, **90 off-scale**. A tight core
  0.05–1 mg m⁻³ just above 1:1 with a wide halo of individual points on both
  sides.

Design choices beyond the prompt, so they are visible:

- The sequential maps start at near-white, so a cell holding exactly five
  matchups vanished into the background and the mesh edge read as dots
  only. The mesh uses the colormap truncated to `[0.2, 1.0]` (the dots stay
  at the full map's 0.75 shade).
- **Minor gridlines are off** (decade grid only). On the real Chl 2.0-vs-1.0
  frame the first render was 115 KB — over `SIZE_BUDGET` — and a probe of
  the knobs showed the minor log grid alone cost 25 KB (112 → 87 KB) while
  PNG `optimize` made the file *larger* and `bins=40` only saved 10 KB. The
  grid was also visible clutter through the light cells. All five panels are
  now 52–90 KB; the synthetic test frames never approach the budget, so the
  budget is really enforced by this acceptance step, not the tests.
- The figure is 5.6 × 5 in (not 5 × 5) to make room for the colorbar at
  the same axes size as before.

Worth knowing: `n` differs per panel (15,274 for `b_bp` vs 15,154 for Chl
vs 15,964 for GIOP on the same 15,971 fits) because each drops its own
non-finite/non-positive pairs, and on the float panels that is entirely the
float side: every BING value is finite and positive, while 697 profiles
have no `bbp700` and 561 have no `chla` plus 256 a `chla` ≤ 0 (checked on
the frame). Nothing was done about it. No new questions for Q&A/Edits.

Next: E4 (the two maps).

### 2026-10-17 (v2 Edit E4 — Robinson dot map and HEALPix median map)

Run with Fable. The v2 database was opened read-only (`file:…?mode=ro`,
`create=False`); the committed `report_site/` was not touched (E6); no
Docker image rebuilt; nothing installed — `cartopy` 0.25.0 and `healpy`
1.19.0 were already in `ocean14`, with the 110m Natural Earth `land` and
`coastline` shapefiles already cached. Files changed:
`pab/plotting/population.py`, `pab/report/rst.py`, `pab/tests/test_metrics.py`,
`pab/tests/test_report.py`, `requirements.txt`, `HOWTO.md` (§7a), this file.

What the code does (Q8, F5, F6):

- `population.matchup_map(df, *, sat_col="bbp_bing", insitu_col="bbp_argo",
  color_col=None, vmax=None, percentiles=(2, 98), projection="default",
  outfile, dpi)`: the old `matchup_map(df, color_col=, outfile=, dpi=)`
  calls still work, but the colour is now `log10(sat/float)` computed
  inside from the two columns (`population.log_ratio`), on `RdBu_r`
  symmetric about 0 with `Normalize(-vmax, vmax)` and an `extend="both"`
  colorbar labelled `log10(satellite / float b_bp)`; cartopy `Robinson()`
  axes, `set_global()`, `cartopy.feature.LAND.with_scale("110m")` at
  facecolor 0.85, 110m coastlines at linewidth 0.4, faint gridlines; dots
  `s=9` (marker size 3), alpha 0.6, `transform=PlateCarree()`, rasterized.
  Matchups with a position but no finite ratio are drawn underneath as
  small grey dots and counted in the title (`15,274 matchups; colour
  clipped at ±1.85 dex (2nd-98th percentile); 695 without a ratio in grey`).
- `population.log_ratio_vmax(df, sat_col, insitu_col, *, percentiles)` =
  `max(|p_lo|, |p_hi|)` of the finite per-matchup log-ratio (1.0 when there
  is none); the caller computes it once and passes it to both maps.
  `population.LOG_RATIO_PERCENTILES = (2.0, 98.0)`;
  `population.percentile_range()` gives the `"2nd-98th"` the titles and
  captions quote.
- The fallback chain lives in one `_map_axes(projection)`: `"robinson"` →
  cartopy; cartopy not importable → plain lon/lat axes (`[-180, 180] ×
  [-90, 90]`, equal aspect) with a `pab.plotting` warning; cartopy present
  but the shapefiles neither cached nor downloadable → Robinson axes
  without land/coast and a warning. The shapefiles are resolved **eagerly**
  with `cartopy.io.shapereader.natural_earth(...)` before any feature is
  added, because cartopy's features otherwise download lazily at draw time
  and a failed download would surface as an exception out of `savefig`,
  not as the warning E4 asked for. `projection=None` forces the plain path;
  `projection="default"` reads the module constant
  `population.MAP_PROJECTION` (`"robinson"`), which `test_report.py` sets
  to `None` in an autouse fixture so no report test ever touches cartopy
  or the network.
- `population.healpix_map(df, *, sat_col, insitu_col, cell_size_deg=5.0,
  min_count=HEALPIX_MIN_COUNT, vmax=None, percentiles, projection, outfile,
  dpi)`: cells from `population.healpix_medians` (a new public helper:
  `nside_for_cell_size` / `assign_healpix` from `pab.report.aggregate`,
  per-cell `n` and median log-ratio of the finite positive, positioned
  pairs — every occupied cell, so the caption can count the ones left
  out); only cells with `n ≥ min_count` are drawn, as a `PolyCollection`
  of 16-vertex outlines from `healpy.boundaries(nside, pix, step=4)` with
  `transform=PlateCarree()` (matplotlib's `_as_mpl_transform` protocol, so
  cartopy projects and cuts each polygon), same colormap/norm/colorbar as
  the dot map. `population.HEALPIX_MIN_COUNT = 5` is a separate constant
  from `DENSITY_MIN_COUNT` (same value, different knob). Two-line title:
  `453 HEALPix cells (nside 8, ≈7.3°) with ≥ 5 matchups, holding 15,143
  matchups / 59 sparser cells not drawn; colour clipped at ±1.85 dex`.
- Dateline handling (`_cell_outline` + `_dateline_pieces`): longitudes
  taken in `[0, 360)`; a cell whose span there exceeds 180° straddles 0°
  and is made compact by shifting its eastern vertices by −360; a cell with
  vertices on both sides of 180° (beyond a 1e-6° tolerance) is split with
  a one-edge Sutherland–Hodgman clip into a western piece ending at 180°
  and an eastern piece starting at −180°, and the number split is logged
  at INFO; a cell wholly east of 180° is shifted by −360; every piece is
  clipped to `[-180, 180]`. The pole vertex of a polar-cap cell comes back
  from `vec2ang` at longitude 0 whatever the cell (`atan2(0, 0)`), so it is
  replaced by the circular mean of its two neighbours.
- `rst._static_comparison_figures`: one `vmax = population.log_ratio_vmax(df,
  "bbp_bing", "bbp_argo")`, passed to both `matchup_map(...)` →
  `matchup_map.png` and `healpix_map(...)` → `healpix_map.png`; the old
  caller-built `ratio` column is gone (and with it the unused `numpy`
  import). Captions: the dot map states the colour, the symmetric clip
  ("±1.86 dex, the 2nd-98th percentile of the per-matchup log-ratio;
  values beyond take the end colours") and the grey dots; the HEALPix map
  states nside and cell width (`population.healpix_cell_deg`), the ≥ 5
  rule with the cells drawn / matchups held / cells left out, and "the same
  scale as the dot map".
- `requirements.txt`: `cartopy` added after `healpy`. HOWTO §7a: a
  paragraph on the first-use Natural Earth download, the cache at
  `~/.local/share/cartopy/shapefiles/natural_earth/physical/` (verified:
  that is `cartopy.config["data_dir"]` here, and the 110m land/coastline
  files are present), the fallbacks, and that the Docker image was not
  rebuilt because `--emit-site` runs on the workstation (F6).
- Tests. `test_metrics.py` (+7): the old scatter test now calls
  `matchup_map(..., projection=None)`; a 2,000-point frame with three 1e4
  runaways renders on plain axes under `MAP_SIZE_BUDGET` (new, 250 KB) with
  the right limits, title and colorbar label; `log_ratio_vmax` equals
  `max(|p2|, |p98|)`, stays in (0.3, 0.7) despite the runaways, both maps'
  norms are exactly `[-vmax, vmax]` when given it, and an all-NaN frame
  gives 1.0; a 40 + 2 matchup frame yields `healpix_medians` counts [2, 40]
  with the right median, draws one polygon, titles "1 HEALPix cells … 1
  sparser cells not drawn", and draws two at `min_count=2`; every nside-8
  cell's pieces lie in `[-180, 180]`, span between 0.5° and 180° (no
  degenerate sliver), the straddlers split into a west piece ending at 180
  and an east piece starting at −180, and a pole cell's pole vertex takes
  its neighbours' longitude; `sys.modules["cartopy"] = None` → the
  "not importable" warning and plain axes; `shapereader.natural_earth`
  raising → the "unavailable" warning on GeoAxes; and one test that takes
  the real Robinson path for both maps, `skipif` the shapefiles are not
  already cached (so it never downloads). `test_report.py`: the autouse
  plain-axes fixture; the at-scale page references and writes both PNGs,
  quotes "2nd-98th percentile of the per-matchup log-ratio" twice, "only
  cells holding ≥ 5 matchups are drawn" and, on two matchups, "(0 cells, 0
  matchups; 2 sparser cells left out)"; the 400-point frame with three
  runaways gives both captions the same clip, below 0.2 dex. Named tests
  14 passed; full suite **427 passed, 1 skipped** (420 after E3 → +7);
  `ruff check pab` clean.

Acceptance on `$PAB_DATA_DIR/v2/pab.db` (15,971 matchups), rendered through
`_static_comparison_figures` into the scratchpad
(`…/scratchpad/e4/site/_static/comparisons/`) and looked at:

- **`matchup_map.png`** (137.1 KB, under the 250 KB budget): 15,274
  coloured dots, 695 grey (697 matchups have no float `b_bp`; 2 of those
  also have no position); p2 = −1.855, p98 = +0.617, **vmax = 1.855**,
  with the extremes at −4.5 / +8.2 clipped to the end colours. Land and
  coastlines are plain; the dots at size 3 no longer over-plot into blobs;
  the dark-blue (satellite ≪ float) dots are visibly clustered — the
  Mediterranean, the Arctic shelf seas, the Gulf of Mexico — where the
  pale-pink majority is not.
- **`healpix_map.png`** (88.9 KB): 512 occupied nside-8 cells, **453 drawn**
  (≥ 5 matchups; 15,143 matchups), 59 dropped; **7 cells straddle the
  dateline and were split** (the equatorial diamonds only touch 180°, the
  rings beside them cross it); per-cell medians run −1.48 to +0.42. No
  smears; the Mediterranean cell at −1.48 is the one saturated feature, the
  subtropical gyres read faintly pink (satellite high), the Southern Ocean
  faintly blue.

Design iterations, so they are visible:

- **The first HEALPix render was a pale-blue planet.** Three cells (nside-8
  pixels 32, 72, 696) have an edge *on* the dateline, and the split then
  produced a zero-width piece with every longitude at 180.0; cartopy
  projects a degenerate ring as an inside-out polygon, i.e. the whole globe
  (checked with `Robinson().project_geometry`: area fraction 1.0). Hence
  the 1e-6° tolerance in the straddle test and the per-piece span assertion
  in the tests; the split count dropped from 13 to the true 7. A first fix
  that clipped the outline instead of shifting it made three *other* cells
  degenerate — the same diagnostic caught it.
- The single-line HEALPix title overflowed the figure into the colorbar
  label; the title is two lines and the colorbar label dropped "per cell"
  (the title says it).
- `{p:g}th` gave "2th-98th"; `percentile_range()` formats ordinals.

Worth knowing: (1) `healpy.boundaries` in healpy 1.19 has **no `lonlat`
keyword** (the prompt assumed one); it returns unit vectors, converted with
`healpy.vec2ang(..., lonlat=True)`. (2) "5° cells" is **nside 8 ≈ 7.3°**:
`nside_for_cell_size` (via `remote_sensing`) picks the nside whose cells
are at least the requested size, as `aggregate_healpix` already did. (3)
The symmetric 2nd–98th rule is set by the low tail alone on these data
(p2 = −1.86 vs p98 = +0.62), which leaves 88 % of the matchups in the
palest tints — raised as Q&A/Edits 5 with a recommendation; E4 publishes
the agreed rule. (4) The 16 of 768 cell outlines that shapely reports as
clockwise (pole-adjacent and 0°-straddling ones) project correctly;
orientation only bit on the degenerate pieces.

Next: E5 (galleries; E1b first).

### 2026-10-17 (v2 Edit E5 — representative figure galleries)

Run with Fable. The v2 database was opened read-only (`create=False`); the
committed `report_site/` was not touched (E6); nothing installed; the only
Drive traffic was the three `rclone copy … --files-from … --no-traverse`
fetches from E5 (20 files into `$PAB_DATA_DIR/gallery/{v2_figures,v1_scenes,
argo_qa}/`; nothing uploaded, nothing under `v1/`). Files changed:
`pab/pipeline.py`, `pab/report/rst.py`, `pab/tests/test_report.py`,
`pab/tests/test_pipeline.py`, `pab/tests/test_report_versions.py` (one test
updated), this file.

**Deviation, approved by the session lead: E1b has not run** (it needs the
user to launch the pod), so `$PAB_DATA_DIR/gallery/v2_argo_qa/` does not
exist. E5 says to stop; instead everything was implemented and the acceptance
run passed `--figure-root /data/v2/pipeline/argo_qa=…/gallery/v2_argo_qa`
anyway (the remap tolerates a nonexistent root). It turned out not to matter:
**all 8 selected fits sit on profiles whose Q&A plot is under
`/data/full/pipeline/argo_qa/`** — none is PVC-only (`/data/v2/…`) and none
lacks a `qa_path` — so **zero Q&A panels are missing because of E1b**, the
Q&A gallery shows 8 of 8, and E6 (after E1b) will pick up nothing new for the
galleries. A note to that effect went into E6 step 1.

What the code does (Q4 = A, F1, Q&A/Edits 1–2):

- `pipeline.py`: repeatable `--figure-root OLD=NEW` on `--emit-site`
  (`figure_root_pair` parses it, expands `~`/`$VAR` in NEW, rejects a value
  without `=`), passed as `figure_roots: dict` into `rst.build_site`.
- `rst.remap_figure_path(src, figure_roots)`: longest-prefix match on whole
  path components (`/data/v2/pipeline/figures` beats `/data`;
  `…/figures_old/x.png` does not match `…/figures`). `_stage_static(src,
  outdir, subdir, *, figure_roots, max_side=GALLERY_MAX_SIDE)` remaps, drops
  a source that still is not on disk (returns `None`), and writes the copy
  through `_downscaled_copy`: Pillow shrinks the longest side to 1200 px and
  re-encodes as PNG **only when the image is larger**; a smaller image, an
  undecodable file (the tests' `b"png"` stubs) or a build without Pillow gets
  a verbatim copy. `_thumbnail_gallery` counts the drops and emits **one**
  `_log.warning` per gallery ("N of M representative files dropped (no
  recorded path, or not on disk after the --figure-root remap)"), and the
  intro says "(N of the M chosen have no file reachable at build time and
  are left out.)" so the page is honest about it.
- `rst.select_representative_fits(df)` → ≤ 8 rows with `log_ratio`, `reason`
  and `caption` (`WMO/cycle — reason`) columns, in order: nearest the
  `REPRESENTATIVE_PERCENTILES` (5, 25, 50, 75, 95) of `log10(bbp_bing /
  bbp_argo)` over finite positive pairs; the runaway with the largest
  `bbp_bing` above `BBP_IMPLAUSIBLE` (skipped when none); the matchup nearest
  the median log-ratio within the clearest and the most productive `chl_bing`
  tercile. The frame is sorted by `matchup_id` first so every `argmin`/
  `argmax` tie goes to the smallest id; duplicates are removed keeping the
  first reason. `select_representative_scenes(df, max_regions=
  MAX_SCENE_REGIONS)`: one per `add_strata` region (nearest the region's
  median log-ratio), the most populous regions first (ties alphabetical).
- `_thumbnail_gallery(..., representative=, representative_intro=)`: above
  `max_inline`, if a representative list is given it is staged (lazily, as
  before) and rendered under the intro (a `{n}`/`{k}` template; `k` is the
  number actually shown); without one the old downloads note stands.
  `figure_gallery(df, representative=sel)` maps the selection to the URLs in
  `FIGURE_URL_COL`; `scene_gallery`/`argo_qa_gallery(store, outdir,
  representative=, figure_roots=)` look up `scene_path`/`qa_path` for the
  selected `matchup_id`s (the Q&A gallery takes the **fit** selection, so the
  three galleries tell one story, same order, same captions). The fit intro
  is built from the reasons present (`_fit_gallery_intro`: "plus one failed
  retrieval" only when a runaway was selected). The `max_inline` defaults are
  now resolved at call time (`None` → `MAX_INLINE_FIGURES`) so the threshold
  can be monkeypatched in tests.
- `figures_page(store, outdir, df, *, figure_roots)` computes both selections
  once above `MAX_INLINE_FIGURES`, passes them to the three galleries and logs
  the staged total ("galleries staged N files, X MB under _static/").
  `_gather_with_figures(..., figure_roots)` above both thresholds now stages
  **only** the selected fit figures (URLs set for those rows, `None`
  elsewhere) instead of nothing; below the thresholds it stages all, as
  before, since the tap-to-open scatter links them.
- Tests. `test_report.py` (+7): the selection on a 300-row synthetic frame
  (log-normal ratio, two runaways, NaN/zero rows) returns 8 rows with the
  documented reasons in order, the largest runaway (not the smaller one),
  captions `WMO/cycle — reason`, monotonic percentile picks, the tercile
  picks inside their terciles, and the same rows/reasons from a shuffled
  input; without a runaway 7 rows, a 2-row frame de-duplicates, identical
  ratios pick the smallest `matchup_id`, an empty frame gives an empty frame
  with the columns; one scene per region, most populous first, with the
  band's count in the reason, `max_regions` honoured, the pick nearest the
  band's median; the remap resolves the longest prefix, matches whole
  components only, leaves unknown paths alone, stages through the remap and
  drops a missing file (also under a nonexistent root); a 3000×1500 PNG is
  staged at 1200×600 and smaller than the source, an 800×600 one verbatim,
  `max_side=None` switches the shrink off; above `max_inline` (patched to 5,
  12 seeded matchups with fit/scene/Q&A stubs) the Figures page carries
  exactly the selected thumbnails with their captions, the three intros, one
  deliberately deleted Q&A file produces exactly one warning and the "(1 of
  the N chosen …)" note, and only the selected files are staged;
  `build_site(figure_roots=…)` resolves pod-style prefixes for all three
  galleries and stages nothing for a prefix without a root.
  `test_pipeline.py` (+1): `--figure-root` is repeatable, expands `~`,
  rejects a value without `=`, and reaches `build_site` as a dict.
  `test_report_versions.py`: `test_fit_figures_not_staged_at_scale` now
  asserts that exactly the representative rows are staged and linked (its
  six identical-ratio matchups collapse to one). Named tests 11 passed; full
  suite **435 passed, 1 skipped** (427 after E4 → +8); `ruff check pab` clean.

Acceptance on `$PAB_DATA_DIR/v2/pab.db` (15,971 matchups). The selection
(deterministic; the `fits.txt`/`scenes_v1.txt`/`qa.txt` lists are in the
scratchpad, 8 + 4 + 8 basenames) and the captions as rendered:

- **Fits (8):** 1902383/79 — 5th percentile of sat/float b_bp, ratio 0.188;
  2903833/36 — 25th percentile, ratio 0.732; 5906450/140 — 50th percentile,
  ratio 1.15; 3902454/42 — 75th percentile, ratio 1.77; 3901586/105 — 95th
  percentile, ratio 3.17; 6903874/139 — non-physical retrieval, b_bp =
  9.3e4 m⁻¹; 4903848/69 — clearest tercile, Chl 0.023 mg m⁻³, ratio 1.36;
  5907252/5 — most productive tercile, Chl 0.32 mg m⁻³, ratio 0.972. No
  duplicates, so all eight slots are filled.
- **Scenes (4, not 6):** 7902104/18 — tropics band, median ratio 1.34
  (n=5,756); 2903862/81 — temperate, 0.977 (n=5,266); 3902615/1 —
  subtropics, 1.27 (n=3,081); 4903365/112 — polar, 0.899 (n=1,171).
  `add_strata` has only four latitude bands, so "6 at most" is four (the
  Prompt-3 log anticipated this). All four scene paths are 1.0-run
  (`/data/v1/…`); none of the 1,390 `/data/v2/…` scenes was selected, so
  `fits.txt` holds only the 8 fit figures.
- **Argo Q&A (8 of 8):** the same eight profiles, all under `/data/full/…`.
- `figures.rst` lists 8 / 4 / 8 items with reasons; the three galleries read
  "15971 matchups — too many to show inline. The 8 below were chosen to span
  the sat/float agreement from the 5th to the 95th percentile, plus one
  failed retrieval and the clearest and most productive regimes; …", "15976
  matchups … The 4 below are one per latitude band …" and "58181 profiles …
  The 8 below are the profiles behind the representative fit figures above".
  No drop warnings. **Staged: 20 files, 1,039,562 bytes (1.04 MB)** under
  `_static/{figures,scenes,argo_qa}`. A `sphinx -b html` of the scratch site
  built with no warnings and 20 figcaptions.
- Looked at (Read tool): the median fit (5906450/140 — a clean Rrs fit with
  a 5–95 % band and a smooth `b_bp(λ)` ≈ 1e-3 m⁻¹), the runaway (below), the
  tropics scene (a mostly cloudy OCI swath with the float at the edge of a
  clear patch — exactly what the quick-look is for) and the median profile's
  Q&A plot (BBP700/CHLA vs pressure, de-spiked trace, MLD 56 dbar). All
  render correctly at thumbnail size.

Surprising, or worth knowing:

- **The runaway's observed Rrs is negative at 400–430 nm** (6903874/139:
  Rrs runs from −1.6e-3 sr⁻¹ at 400 nm up through zero near 435 nm to a peak
  at ~490 nm, with a gap at 590–610 nm). That is a failed atmospheric
  correction, not a bright scene, and BING answered it with `b_bp` ≈ 9.3e4
  m⁻¹ and a 5–95 % band of 8e4–1e5 — the fit "converged" with every flag
  set, as the Prompt-8 investigation found. Negative blue Rrs may be a
  usable pre-fit screen for the 51 runaways; this belongs with the Outliers
  prompt, nothing was done here.
- **The 1200 px downscale never triggers on these data.** The originals
  are 620–640 × 590 (fits), 490 × 410 (scenes) and 630 × 416 (Q&A) pixels,
  so every staged copy is verbatim (37–73 KB each). The cap is a guard for
  larger renders, not a saving today; the committed site will grow by
  ≈1.0 MB for the galleries.
- The E5 lists (`fits.txt` etc.) are written by a scratch script from the
  same `select_representative_*` functions the site uses, so the fetch and
  the build cannot disagree. A first attempt named that script `select.py`,
  which shadowed the stdlib `select` module and broke `import pandas` — a
  reminder of why scratch scripts get distinctive names.
- `du -sh` on the new `gallery/` folders under-reports (4.5 K for 326 KB of
  Q&A plots): ZFS compression/metadata on `/mnt/tank`; `ls -l` sizes are
  right.
- No new Q&A items.

Next: E1b (user launches the pod), then E6.

### 2026-10-17 (v2 Edit E1b — copied the 2.0 Argo Q&A plots off the PVC; Drive backup)

Run with Fable. No code changed; nothing written on the PVC (mounted
read-only). Files changed: `HOWTO.md` (one addition to the backup paragraph),
this file (Q&A/Edits 6, a correction bullet in the E1 Findings, this entry);
`nautilus/argo_qa_copy_pod.yaml` is the new pod spec from step 1 (untracked).
New data: `$PAB_DATA_DIR/gallery/v2_argo_qa/` (5,453 PNGs, 226,830,227 B)
and `$PAB_DATA_DIR/gallery/v2_argo_qa.md5` (the in-pod md5 list, kept next
to the folder); `AIOcean:PAB/v2/argo_qa/`. E5/E6 needed no change — they
already assume root `$PAB_DATA_DIR/gallery/v2_argo_qa/` for prefix
`/data/v2/pipeline/argo_qa/`, and that is what exists now.

What happened, step by step:

- Pod `pab-argoqa-copy` (`python:3.12-slim`, `sleep 14400`, PVC read-only)
  was applied by the user and was `Running` within a minute on
  `tu.gp-engine.greatplains.net`.
- In-pod: `ls /data/v2/pipeline/argo_qa | wc -l` = **5,453**, all `.png`,
  exactly the DB's 5,453 `/data/v2/pipeline/argo_qa/` rows; `du -sh` =
  **218M**. `md5sum *.png > /tmp/qa.md5` (5,453 lines, list md5
  `abf70331…`) and `cat` back — this took ~12 min (CephFS reads from a
  1-CPU pod while the tar stream ran concurrently). Also recorded:
  `ls /data/v2/fit_chains | wc -l` = **15,971**, `du -sh` = **19G**
  (`backup.log` says 18.3G), and `/data/v2/` holds `pab.db` (217,325,568 B,
  the workstation copy's size), `pab.db.pre-task3-bak`, `backup.log` and
  the run logs.
- Transfer: `kubectl exec … tar czf - -C /data/v2/pipeline argo_qa >
  gallery/v2_argo_qa.tgz` streamed 210,237,944 B in ~12 min without an
  error (PNGs barely compress: 0.93x). `gzip -t` OK, 5,453 entries;
  extracted into a temp dir, renamed to `gallery/v2_argo_qa/`; local count
  5,453; `md5sum -c` against the in-pod list: **5,453 OK, 0 failed**;
  `.tgz` deleted.
- Drive: `rclone lsf AIOcean:PAB/v2/` before = `figures/ fit_chains/
  site/` (no `argo_qa/`, nothing to collide with). `rclone copy … --transfers
  8` finished in ~30 min; `rclone check … --one-way`: **0 differences,
  5,453 matching files**; `rclone size AIOcean:PAB/v2/argo_qa/` = 5,453
  objects, 226,830,227 B — byte-for-byte the local total.
- Pod deleted (`kubectl … delete pod pab-argoqa-copy`); `get pod` now
  returns NotFound and `get jobs,pods` shows nothing in the namespace.
- HOWTO: the backup paragraph naming `AIOcean:PAB/` now lists the three
  `v2/` folders with their counts and the 2026-10-17 date for `argo_qa/`.

**The chains side task's premise is wrong — the 2.0 chains have been on
Drive since 2026-10-07.** `tail -40 /data/v2/backup.log` is the complete log
of the `v2_backup_job.yaml` run (it is only 1,628 B) and it ends well:

```
=== CHAINS -> AIOcean:PAB/v2/fit_chains 2026-10-07T15:51:35+00:00 ===
2026/10/07 16:50:06 ERROR : Failed to save config after 20 tries: failed to create temp file for new config: open /cfg/..data/rclone.conf3092218986: read-only file system
=== FIGURES -> AIOcean:PAB/v2/figures 2026-10-07T17:00:11+00:00 ===
…
=== VERIFY — source vs destination counts 2026-10-07T18:14:19+00:00 ===
chains  local=15971 remote=15971
figures local=17361 remote=17361
=== CHECK — re-read a sample and compare hashes 2026-10-07T18:15:58+00:00 ===
2026/10/07 18:16:43 NOTICE: Google drive root 'PAB/v2/fit_chains': 0 differences found
2026/10/07 18:16:43 NOTICE: Google drive root 'PAB/v2/fit_chains': 15971 matching files
=== V2_BACKUP_DONE 2026-10-07T18:16:43+00:00 ===
```

The chains step ran 15:51–17:00 (18.3 GB in 69 min, ~4.4 MB/s), the figures
17:00–18:14, and the job's own verify and `--size-only` check passed. The
only errors are rclone's `Failed to save config … read-only file system`:
the Drive token was refreshed and rclone tried to write it back to the
secret mount, which is read-only — harmless (the refreshed token lives in
memory for the rest of the run), but the same message will recur on every
in-cluster run; `--config` on a writable copy (`cp /cfg/rclone.conf /tmp/`)
would silence it. No `--stats` lines appear because `--stats` logs at INFO
and the job runs at the default NOTICE level. Today, from the workstation:
`rclone size AIOcean:PAB/v2/fit_chains/` = **15,971 objects, 18.327 GiB
(19,678,573,593 B)**, and `AIOcean:PAB/fit_chains/` (also called "empty"
in E1) = 14,654 objects, 18.087 GiB — the HOWTO's 18.09 GiB for the 1.0
chains. `--drive-trashed-only` lists nothing in either, and `lsf -F pi
--dirs-only` shows one folder per name (no Drive duplicate-name confusion).
So E1 misread the remote; the likely mechanism is `rclone lsd` (the command
the E1 prompt names), which lists sub-directories only and prints nothing
for a flat folder of files — the E1 log does not say which command produced
the "empty". Consequence: Q&A/Edits 3 = A (re-run the backup job) is
unnecessary; posted as **Q&A/Edits 6** with the recommendation to drop the
side task. The E1 Findings carry a correction bullet; the side-task text
itself was left for the user to retire.

Other things worth knowing:

- `rclone about AIOcean:` prints nothing (shared drives report no quota).
- The in-pod `md5sum` of 218 MB taking ~12 min is the CephFS small-file
  read rate from this pod class (and it shared one CPU with gzip); the
  tar stream itself was limited by the same reads, not by the network.
- `du -sh` on `gallery/v2_argo_qa/` under-reports on ZFS as E5 noted; the
  `226,830,227` figure is `du -sb --apparent-size`, and matches Drive.
- Scratch outputs (pod inventory, backup.log tail, md5 check, rclone check)
  were written under the session scratchpad
  (`…/scratchpad/e1b/`); the md5 list is the only one kept permanently,
  as `$PAB_DATA_DIR/gallery/v2_argo_qa.md5`.

Next: E6 (which can now pass the `v2_argo_qa` root to a folder that
exists); the chains side task awaits the Q&A/Edits 6 answer.

### 2026-10-17 (v2 — Q&A/Edits 5 = B: maps clipped at a fixed ±0.5 dex)

Run with Fable, in parallel with E1b; that agent did not edit this file, so
the session lead wrote this entry. It replaces E4's symmetric 2nd–98th
percentile clip. In `pab/plotting/population.py`, `LOG_RATIO_VMAX = 0.5`
replaces `LOG_RATIO_PERCENTILES`. `log_ratio_vmax` and `percentile_range` are
gone, so E4's log entry describing them is now historical. `matchup_map` and
`healpix_map` take `vmax=LOG_RATIO_VMAX`, and the new `saturated_count` and
`log_ratio_saturated` feed the titles and captions. `_static_comparison_figures`
captions now state the fixed clip ("a factor of 3.2 either way") and computed
saturation counts. On the v2 DB, 1,858 of the 15,274 matchups with a ratio
(12.2 %) are at or beyond ±0.5 dex (1,090 low, 768 high). Only one of the 453
drawn HEALPix cells saturates: the Mediterranean, with median −1.48 and n = 70.
The regional pattern now reads at a glance: the subtropical gyres are red and
the Southern Ocean, the subpolar North Pacific and the Nordic/Arctic shelves are
blue. Sizes: dot map 163 KB, HEALPix map 104 KB (budget 250 KB). One test was
replaced, so the full suite stays at 435 passed, 1 skipped; `ruff check pab` is
clean. HOWTO and docs never mentioned the percentile rule, so they are
unchanged.

### 2026-10-18 (v2 Edit E6 — rebuilt report_site, verified, closed out)

Run with Fable. No code changed. Both databases were opened by the CLI's
`Store.open(create=False)` path and are **byte-identical before and after**
(v2 `1e69f6ee…8a3f8`, 217,325,568 B; v1 `09de0a6d…8273`, 169,938,944 B; no
`-journal`/`-wal` files appeared). Nothing was written under `v1/`, no pod, no
rclone. Files changed: `report_site/` (regenerated), `HOWTO.md` (§5b S3 row,
§7a rebuild command and a paragraph on the `--emit-site` flags),
`docs/design/PAB_implementation.md` (new §13 and a pointer in §5e.2),
`docs/reporting.rst` (a "Static figures at scale" section and the galleries
bullet), this file. Scratch under `/tmp/claude-1000/pab-e6/` (sphinx builds,
exports, re-downloads, logs).

**Step 1 — regeneration.** Before: `du -sh report_site` = 13M (16,026,833 B
apparent, of which 1,362,563 B is the 18 tracked files; the rest is a stale,
git-ignored `report_site/_build/` from 2026-10-05), `git status --short
report_site` clean. A sphinx build of the pre-regeneration tree into scratch
gave **0 warnings** (the baseline). The E6 command ran exactly as written
(five `--figure-root` flags, `--downloads-base-url
https://s3-west.nrp-nautilus.io/pab/v2`, `--compare-db $PAB_DATA_DIR/v1/pab.db`)
in **10.4 s**; its log: "staging only the 8 representative fit figures",
"healpix_map: 7 of 453 cells straddle the dateline and were split", "galleries
staged 20 files, 1.04 MB under _static/" — **zero dropped-figure warnings,
zero warnings of any kind.** Then `python -m sphinx -b html report_site
/tmp/claude-1000/pab-e6/_build` — built **outside** `report_site/` on purpose
(E6 says `report_site/_build`; that path is git-ignored so it would not have
been committed either way, but building to scratch leaves the tree with
nothing untracked but the new figures): **0 warnings**, same as the baseline.
HOWTO §7a now shows the scratch variant as an option.

**Step 2 — verification.** After: `du -sh report_site` = 15M (17,251,318 B
apparent, still dominated by the stale `_build/`); the committable tree
(everything except `_build/`) is **2,587,048 B, up 1,224,485 B (+1.22 MB)**
from 1,362,563 — well under the 10 MB target. `git status --short
report_site`: 12 modified (six comparison PNGs: `bbp_scatter` 41→60 KB,
`chl_scatter` 69→75, `matchup_map` 53→163, `nasa_giop_bbp_scatter` 41→52,
`v2_vs_v1_bbp700` 59→54, `v2_vs_v1_chl` 161→90; and `aggregates/comparisons/
downloads/figures/methods/summary.rst`) and 21 untracked (`healpix_map.png`,
8 `_static/figures/`, 4 `_static/scenes/`, 8 `_static/argo_qa/`). **No
deleted files** — the 1.0 site never committed per-matchup figures, so
there was nothing to drop. Unchanged by the rebuild: `conf.py`, `index.rst`,
`.readthedocs.yaml`, `requirements.txt`, `v2_bp_hist.png` and
`v2_v1_ratio_vs_level.png` (re-rendered byte-identical). `aggregates.rst`'s
24-line diff is only Bokeh embed UUIDs; `methods.rst`/`summary.rst` carry the
new build date, commit `603d97d` and the 700 nm headline. No `_build`, no
`__pycache__`, no stray files. Looked at with the Read tool:
- `bbp_scatter.png` (Blues): n = 15,274, ρ = 0.41, bias +0.01, RMS 0.65,
  median 1.15, [155 off-scale]; axes 3×10⁻⁶–6×10⁻²; dense core at
  5×10⁻⁴–3×10⁻³ on 1:1, the vertical prior-floor pile at 3×10⁻⁶–10⁻⁴ under
  float 5×10⁻⁴–10⁻³ clearly visible.
- `chl_scatter.png` (Greens): n = 15,154, ρ = 0.73, bias −0.09, RMS 0.59,
  median 0.94, [166 off-scale]; core 0.05–1 mg m⁻³ just below 1:1; the spray
  of satellite Chl below 10⁻² at every float Chl is the obvious tail.
- `nasa_giop_bbp_scatter.png` (Purples): n = 15,964, ρ = 0.89, bias 0.00,
  RMS 0.52, median 0.94, [173 off-scale]; the arc follows 1:1 above 10⁻³,
  the GIOP floor band at 2–4×10⁻⁴ wherever BING < 10⁻⁴ is plain.
- `v2_vs_v1_bbp700.png` (Blues): n = 14,604, ρ = 0.92, bias −0.16, RMS 0.54,
  median 0.75, [156 off-scale]; cells on 1:1 above ~2×10⁻³, peeling to the
  3×10⁻⁶ floor below.
- `v2_vs_v1_chl.png` (Greens): n = 14,604, ρ = 0.70, bias +0.19, RMS 0.64,
  median 1.17, [90 off-scale]; tight core just above 1:1 with a wide halo.
- `matchup_map.png`: Robinson, grey land, coastlines, dots at size 3; title
  "15,274 matchups; colour clipped at ±0.5 dex (1,858 (12.2 %) at or beyond);
  695 without a ratio in grey"; colorbar −0.4…+0.4 with `extend` arrows;
  gyres red, Southern Ocean / subpolar North Pacific / Arctic shelves blue.
- `healpix_map.png`: "453 HEALPix cells (nside 8, ≈7.3°) with ≥ 5 matchups,
  holding 15,143 matchups / 59 sparser cells not drawn; colour clipped at
  ±0.5 dex (1 cell saturated)"; the Mediterranean is the dark-blue cell; no
  smears at the dateline.
- Gallery thumbnails: the runaway fit 6903874/139 (observed Rrs negative at
  400–430 nm, BING `b_bp` ≈ 9.3×10⁴ m⁻¹ with an 8×10⁴–10⁵ band), the
  subtropics scene 3902615/1 (false-colour 645/555/470 swath, float star in
  the analysed pixels), and the Q&A plot 1902383/79 (the 5th-percentile pick:
  BBP700/CHLA vs pressure, MLD 18 dbar, a deep Chl maximum at ~100 dbar under
  a very shallow mixed layer — a plausible reason the satellite sees 0.19× the
  float's `b_bp`). All render correctly.
- `comparisons.rst`: "median NASA(700)/BING(700) ratio = 0.937 (IQR
  0.747–1.22); Spearman ρ = 0.889"; the wavelength note states the formula,
  "14.6 % of the 15,971 slopes sit at GIOP's ceiling of 2.0", and the
  unadjusted ratio **2.15 exactly once** ("for continuity with the previous
  release"); no "no spectral adjustment"/"as-is" phrasing anywhere in
  `report_site/*.rst`. The captions quote the ≥ 5 rule, the off-scale counts
  (155/166/173/156/90), the fixed ±0.5 dex clip ("a factor of 3.2 either
  way"), 1,858 (12.2 %) saturated and the 453/15,143/59 HEALPix counts.
  `figures.rst` lists 8 / 4 / 8 items with the E5 captions; `downloads.rst`
  links the four S3 tables.

**Step 2b — the NASA-GIOP table is on S3.** `publish.export_tables` against
the v2 DB (opened `file:…?mode=ro`) into scratch wrote
`nasa_giop_summary.csv` 8,350,324 B sha256
`21b4b6ceeeb776eb23d6e3dbb7560a9d6b56b6669a6840781580518459c0f60a` and
`nasa_giop_summary.parquet` 2,891,643 B sha256
`66f6cb2705493cac5ffc2e4af894bd45ac93621813a3da50c69e5abd912d91e2` (and, as a
free reproducibility check, `matchup_summary.{csv,parquet}` **byte-identical**
to the objects Prompt 9 published on 2026-10-07: 6,102,869 B
`6622a78c…0f74` / 2,645,441 B `4754e237…c627c`). Anonymous `curl -sI` on both
public URLs returned **403** (absent) before the upload. Credentials: no
`AWS_*` environment variables; `~/.aws/credentials` holds a `[default]`
profile with an access key (the profile Prompt 9 used, per
`build_v2_prompt_9.md`; values not printed), so the boto3 chain was
configured and the upload went ahead with `NautilusS3Backend(bucket="pab",
prefix="v2")`: 0.6 s + 0.3 s. Re-downloaded from
`https://s3-west.nrp-nautilus.io/pab/v2/nasa_giop_summary.csv` and
`…/nasa_giop_summary.parquet`: sizes and sha256 **identical** to the local
files (`cmp` clean); `curl -sI` now gives HTTP 200, `last-modified Sun, 18
Oct 2026 12:15:02/03 GMT`. `v2/matchup_summary.csv` and `.parquet` are
**untouched** (same ETag `9e8bbb22…`/`a5b54e43…` and `last-modified Wed, 07
Oct 2026 15:49:48 GMT` as before). HOWTO §5b's S3 row lists the two objects.

**Step 3 — docs.** HOWTO §7a's "regenerate" block is now the E6 command
(the old one pointed `--db` at `$PAB_DATA_DIR/pab.db`, which no longer
exists) plus a paragraph on `--compare-db`, `--downloads-base-url`,
`--figure-root` (the five stored prefixes and their `gallery/` roots, the
longest-prefix rule, the counted drop warning), the representative galleries
and what `git status` should show after a rebuild (the `aggregates.rst` UUID
noise included). `PAB_implementation.md` §13 records the 700 nm derivation,
`density_scatter`, the two maps with the fixed ±0.5 dex clip and why, the
galleries and `--figure-root`, and what the rebuild showed; §5e.2 points to
it. `docs/reporting.rst` gained "Static figures at scale" (density panels,
maps, the one-wavelength GIOP comparison) and the galleries bullet now
describes the representative selection and the remap; a `sphinx -b html docs`
into scratch built with **0 warnings** (all the new `:func:`/`:data:` targets
resolve).

**Step 4.** `pytest pab/tests -q`: **435 passed, 1 skipped** (the live L1B
read) in 149 s — unchanged from E5; `ruff check pab`: all checks passed.

Worth knowing:
- `$PAB_DATA_DIR` resolves to `/home/xavier/Oceanography/data/Color/PAB`
  (`~/Oceanography` is the symlink to `/mnt/tank/Oceanography`); the HOWTO's
  `/mnt/tank/…` spelling and this one are the same files.
- The stale `report_site/_build/` (2026-10-05, 13.5 MB, git-ignored) still
  sits in the working tree; it is harmless but makes `du -sh report_site`
  read 15M when the committable tree is 2.6 MB. Delete it if the number
  bothers you.
- `docs/reporting.rst` still says, further down, that `NautilusS3Backend`
  "and `ZenodoBackend` are explicit `NotImplementedError` stubs until
  activated" — stale since the S3 backend went live, but outside E6's
  figure-description scope, so left alone.
- Nothing in this prompt needed a decision: **no new Q&A items.**

**Hand-off (nothing committed — git is yours).** Files to commit:
`report_site/` (the 12 modified + 21 new files; nothing under `_build/`),
`HOWTO.md`, `docs/design/PAB_implementation.md`, `docs/reporting.rst`,
`claude_prompts/v2/report_improvements.md`, and — if not already committed
from E2–E5 — `pab/metrics/compare.py`, `pab/report/{rst,publish}.py`,
`pab/plotting/population.py`, `pab/pipeline.py`,
`pab/tests/{test_metrics,test_report,test_report_versions,test_pipeline}.py`,
`requirements.txt`, `nautilus/argo_qa_copy_pod.yaml` (E1b). At commit
`603d97d` all of those are already tracked and clean — only this file, the
docs and `report_site/` are dirty, so the code is already in. Reminder: the `pab-report` RTD project rebuilds on
push **to the branch it tracks** — the published URL is
`…/en/develop/`, so a push to `report-improvements` alone will not update the
site until that branch is merged into `develop` (or the RTD project is pointed
at it).

### 2026-10-18 (v2 Outliers 1 — high-b_bp runaway fits investigated)

Run with Fable. No code changed under `pab/`; the v2 database (and v1 for
one lookup) opened read-only (`file:…?mode=ro`); nothing written to any DB or
under `v1/`; no pod; Drive traffic was `rclone copy … --files-from …
--no-traverse` only (51 + 300 chain NPZs ≈ 420 MB and 51 fit figures + 3
scenes into `/tmp/claude-1000/pab-outliers/`). Files created:
`versions/v2/high_bbp_outliers.md` (the report) and
`versions/v2/high_bbp_outliers/` (4 diagnostic PNGs + 6 fit figures + 2
scene quick-looks, 0.88 MB); Q&A/Outliers 1–5 in this file. No `versions/`
folder existed anywhere in the repo, so it was created at the root as the
prompt names it.

What was found:

- **The prompt's "> 1e4" and the report's "> 1" select the same 51 fits.**
  The 52nd-largest 2.0 `b_bp`(700) is 0.03 m⁻¹; the 51 span 5.0–9.3×10⁴.
  Every posterior is pressed against `expb_pow`'s `Bnw` ceiling (log-uniform
  to 10⁵ m⁻¹), with `A_dg` co-scaled to 10²–10⁴ m⁻¹ (`Bnw`–`A_dg`
  correlation +0.9) — only `a/b_b` is constrained once `b_b ≫ a`.
- **They are not clear water.** 25 Baltic, 9 tropical Atlantic/Caribbean,
  7 Arabian Sea, and singles in the Black, Ligurian, Barents, Labrador seas,
  Kuroshio, NE Pacific coast, California, Agulhas; float Chl median 0.93
  (population 0.15), float `b_bp` 3.6×10⁻³ (6.9×10⁻⁴). The run report's
  "ultra-oligotrophic tail" (§2.5, Prompt 8 Q1) was reading the *retrieved*
  Chl, which is part of the failed fit. Three floats give 25 of the 51.
- **The spectra are blue-depressed.** The Rrs is not in the DB
  (`matchup_pixels` holds pixel index, flags and geometry only); it is in
  the chain NPZs, which is why the fetch was needed. 40 of 51 have negative
  Rrs at 400–450 nm (type A; down to −4.3×10⁻³, median minimum −1.2 σ of
  `Rrs_unc`; none carry an `l2_flags` bit from the standard mask); the 11
  others (type B, all Baltic) are positive with Rrs(440)/Rrs(555) 0.24–0.55
  (population median 4.1). All 51 peak at 490–580 nm.
- **The failure is the LM warm-start, not the sampler or the data.** Step 0
  of every one of the 51 chains already has median `Bnw` 4.7–4.99, and no
  walker ever went below 2.9: the 1 % walker ball around `curve_fit`'s answer
  cannot cross the χ² wall (reduced χ² 10²–10⁵ at `b_bp` ≈ 1–10 m⁻¹, where
  `u → 1` and the hybrid emulator leaves its domain — BING uses
  `on_out_of_domain="warn"`, silent under `jit`). Exploratory LM re-fits
  (CPU, no MCMC) of four outliers found a physical basin in every case with
  a *better* χ² (1.81 vs 11.1, 0.45 vs 10.5, 2.35 vs 7.0, 0.21 vs 1.7) and
  `b_bp`(700) within ~2× of the float and of the 1.0 Gordon fit; from the
  production initial guess the LM reproduces the ceiling for 3 of 4, and
  ±0.3 dex perturbed starts go to the ceiling 0/2/6/3 times out of 12.
  Masking the negative bands does **not** remove the basin (2 of 3 still run
  away) — the depressed-blue shape does it, which is why the all-positive
  Baltic spectra fail the same way.
- **Screen numbers.** "Any Rrs < 0 at 400–450 nm": 40/51 caught, 2 of 300
  sampled non-outliers flagged (≈0.7 %, ≈100 fits, both themselves doubtful).
  Adding Rrs(440)/Rrs(555) < 0.6 reaches 50/51 at ≈1 % but the extra flags
  are good Baltic/subpolar fits. "Any negative anywhere" flags 7 % (red
  bands dip below zero on ordinary clear-water spectra).
- Surprising: the 2903902/30 runaway has χ² = 1.7 and is the `A_ph`-mirror
  mode (`A_ph` 330 m⁻¹, Chl 5,900; `A_dg` 0.01), so χ² and `A_dg` cannot gate
  them either; 4 consecutive cycles of 4903784 on one granule are all
  runaways while the same float series has good fits in the sample; 3 of the
  51 have θ_s > 60°, outside the emulator's supported range (8.8 % of all
  fits do, so not the cause). The workstation LM found the physical basin for
  6903874/139 where the pod's (GPU, float32) evidently did not — the
  optimiser is path-sensitive next to the wall; the chains settle where
  production ended regardless.

Figures were made with matplotlib against the dataviz palette (blue/orange
for the two types, grey population), all looked at. Recommended next steps
(report gate now; re-fit the 51 under a new `pab_version` with a physical
prior ceiling and/or multi-start LM; a stored negative-blue QA count; an
emulator-policy slice test; amend §2.5) are in the report §6 and as
Q&A/Outliers 1–5 with recommendations. Nothing committed — git is yours:
`versions/v2/high_bbp_outliers.md`, `versions/v2/high_bbp_outliers/*.png`
and this file.

### 2026-10-18 (v2 Outliers 2 — wrote the seven Outliers prompts O3–O9)

Run with Fable. No code changed, no database opened, nothing under `v1/`
touched; the only file edited is this one. Read the Q&A/Outliers answers
(1 = B now + C later, 2 = A as **2.0.1**, 3 = A, 4 = A, 5 = A), the outliers
report §4–§6, the E-series prompts as the model, and enough code to make the
prompts name real seams: `pab/fit/{models,run,artifacts}.py`,
`pab/metrics/compare.py`, `pab/report/{rst,publish,aggregate}.py`,
`pab/pipeline.py` (the `fit`/`figure` stages and CLI), `pab/db/schema.py`,
`pab/config.py`, the design doc's *Provenance & versioning*, run report §2.5,
HOWTO §3/§5b, `nautilus/v2_fit_slice_job.yaml`/`v2_bp_attribution.py`, and on
the BING/robust side `bing/parameters/standard.py`, `bing/priors/priors.py`,
`bing/evaluate.py`, `robust/rt/hybrid.py` and `emulator.py`.

The cut: **O3** the `b_bp` gate + the §2.5 correction (no re-fit; retires the
Chl-rate "clear-water tail" table), **O4** the `n_neg_blue` quantity + a
backfill driver for the 15,971 existing fits, **O5** the 2.0.1 code (prior
ceilings as a PAB-side override, `prior_set` stamp, version bump, step-0
check, a replay seam), **O6** the 51-fit run with verification and an
Appendix C, **O7** the patch-version overlay that lets the report show the
2.0.1 values, **O8** the `"ztt"` slice experiment (independent,
non-blocking), **O9** rebuild/publish/docs close-out. Four new Q&A items
(6–9): gate Chl of the same fits; where the chains come from; what the
re-fit reads (replay recommended); publish the amended DB.

What the code reading changed about the plan — worth knowing before O5–O7:

- **The report's version handling would break the moment a 2.0.1 fit
  exists.** `gather_matchups` filters to `newest_bing_version()`, and
  `_version_key` already ranks `"2.0.1"` above `"2.0"`, so the site would
  silently shrink to the 51 re-fitted matchups; `gather_nasa_giop` and
  `gather_version_pair` have **no** version filter at all (they join `fits`
  on `model_pair` only), so the 51 would appear twice there. O7 exists for
  this: a `version_family`/overlay rule keyed on matchup **and pixel**, the
  design's own cross-version join rule.
- **The prior override is trivial on the PAB side.** `expb_pow(**kwargs)`
  does `params.update(kwargs)` into a namedtuple, and `set_standard_priors`
  takes `p.apriors`/`p.bpriors` verbatim, so `p._replace(apriors=…,
  bpriors=…)` after the factory call caps `Adg`/`Aph`/`Bnw` with BING
  untouched; `_prior_bounds` (the LM bounds) reads the same objects, so the
  warm-start sees the ceiling too. `fits.prior_set` (always
  `"bing_standard"` today) records it without a schema change.
- **BING never passes `on_out_of_domain`** to `robust_rt.forward` (two call
  sites in `bing/evaluate.py`), and the default emulator *does* carry a
  domain (`load_default().domain.shape == (2, 7)`, checked in `ocean14`), so
  the `"ztt"` policy would act and O8 is a real test, not a no-op. The pods
  run with `PYTHONWARNINGS=ignore`, so the `DomainWarning`s BING raises at
  the initial guess and posterior median were never seen in production.
- **The chains are not on the workstation.** HOWTO §5b's table lists
  `$PAB_DATA_DIR/v2/fit_chains/` but its text says only the database came
  back; the spectra live only in the NPZs (`matchup_pixels` has no Rrs).
  Hence Q&A 7 (18.3 GiB from Drive) and the replay option in Q&A 8.
- **Replay beats a granule re-read for this test.** The NPZ holds `wave`,
  `Rrs`, `varRrs` exactly as `prepare_spectrum` produced them; a re-read
  would cost ~25 GB of downloads off-cloud or a pod image rebuild, and NASA
  reprocessing since September could change the Rrs — confounding a test
  whose only intended change is the prior.
- Smaller things the prompts encode: `make_fit_id` embeds the version, so
  2.0.1 rows cannot collide with or overwrite 2.0 rows; chains land at
  `$PAB_DATA_DIR/fit_chains/` regardless of `--db`, so O6 sets
  `PAB_DATA_DIR=…/v2`; `--matchups-csv` is the only guard against a
  15,971-fit re-run under the new version; `test_pab_version_is_2_0` ties
  `pab_version` to the installed distribution, so the bump needs `pip install
  -e .`; every BING fit has 11 quantities, 12 after O4; the figure stage's
  `--figure-version 2.0.1` renders only the new fits and needs no granule
  (every scene exists).

Nothing committed — git is yours: this file.
