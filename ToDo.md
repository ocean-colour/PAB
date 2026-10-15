# ToDo

## Done — full-run prep & release (`pab_version = 1.0`)

See `claude_prompts/run_full_pipeline.md` + `nautilus_prompts.md` logs and
`docs/design/PAB_full_run_report.md` for details.

- [x] Implement parallel `fit_batch` across cores (plus parallel `match` / `figure` / `ingest`)
- [x] Bump `pab_version` from `0.0.dev0` to `1.0`
- [x] Create a Nautilus namespace (`sea-meets-the-stars`) + S3 bucket (`s3://pab`, public-read)
- [x] Run the full PACE-mission pipeline on Nautilus (54,031 profiles → 14,610 matchups → 14,609 fits)
- [x] Back up the dataset off-site to `AIOcean:PAB/`; publish the DB + summary tables to `s3://pab/full/`

## Done — the inelastic re-analysis (`pab_version = 2.0`)

See `claude_prompts/v2/build_v2_prompt_*.md` logs and
`docs/design/PAB_v2_run_report.md` for details.

- [x] Schema v5: per-pixel viewing geometry + the RT configuration on `fits`
- [x] New `geometry` stage (PACE L1B `theta_s`/`theta_v`/`dphi`), between `match` and `fit`
- [x] Inelastic fit defaults: `robust_hybrid`, Raman, Chl fluorescence, free `B_p`
- [x] Two-database layout: `v1/` frozen (`chmod a-w`, schema v4) + `v2/` (schema v5)
- [x] Re-run the full pipeline (59,620 profiles → 15,976 matchups → 15,971 fits)
- [x] NASA-GIOP baseline extended to the new matchups (1,367 rows, stamped `1.1`)
- [x] Figures + report on Nautilus; version-aware metrics and a 1.0-vs-2.0 site section
- [x] Publish to `s3://pab/v2/`; back up off-site to `AIOcean:PAB/`

## Remaining

- [ ] Merge `full-inelastic` → `develop` so Read the Docs shows the 2.0 results, then verify `/en/develop/`
- [ ] Publish the bulk per-matchup artifacts (MCMC chains + figures) to `s3://pab` and wire the release manifest to real S3 URLs
- [ ] (optional) Citable Zenodo DOI snapshot (`ZenodoBackend` is still a stub)
- [ ] Rerun the Jacqueline S (MBARI) analysis

### Open questions from the 2.0 run

- [ ] **Rank correlation falls.** `b_bp` ρ drops 0.522 → 0.442 against the floats
      even in productive water, while bias and scatter improve. Unexplained.
- [ ] **51 non-physical `b_bp` retrievals** (0.32 %), all in ultra-oligotrophic
      water; no single-variable filter isolates them (every cut costs 14–30×
      false positives). Is the emulator out of domain at very low backscatter?
- [ ] **`B_p` posteriors are censored at both prior bounds** (15.4 % within 5 %
      of a bound). Re-fit a slice with a wider prior to see whether the modes
      move out.
- [ ] **CDOM fluorescence** is implemented and was off in this run — a one-flag
      experiment.
- [ ] Gap C (see `claude_prompts/v2/run_full_inelastic.md`)
