# ToDo

## Done — full-run prep & release (`pab_version = 1.0`)

See `claude_prompts/run_full_pipeline.md` + `nautilus_prompts.md` logs and
`docs/design/PAB_full_run_report.md` for details.

- [x] Implement parallel `fit_batch` across cores (plus parallel `match` / `figure` / `ingest`)
- [x] Bump `pab_version` from `0.0.dev0` to `1.0`
- [x] Create a Nautilus namespace (`sea-meets-the-stars`) + S3 bucket (`s3://pab`, public-read)
- [x] Run the full PACE-mission pipeline on Nautilus (54,031 profiles → 14,610 matchups → 14,609 fits)
- [x] Back up the dataset off-site to `AIOcean:PAB/`; publish the DB + summary tables to `s3://pab/full/`

## Remaining

- [ ] Merge `first-full-run` → `develop` so the report site on Read the Docs shows the full run
- [ ] Publish the bulk per-matchup artifacts (MCMC chains + figures) to `s3://pab` and wire the release manifest to real S3 URLs
- [ ] (optional) Citable Zenodo DOI snapshot (`ZenodoBackend` is still a stub)
- [ ] Rerun the Jacqueline S (MBARI) analysis
