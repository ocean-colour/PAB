# PAB explanatory notebooks

Jupyter notebooks that describe and demonstrate key PAB methods and analyses,
created as the package is developed stage by stage (see
[`../design/PAB_coding_plan.md`](../design/PAB_coding_plan.md)).

Unlike the offline test suite, these notebooks **may pull live data from the
internet** (e.g. via `argopy` / `earthaccess`), so they serve as runnable worked
examples. Where useful they are rendered into the docs site.

Notebooks are built per stage and executed (offline-safe) so they carry their
outputs. To re-run one:

```bash
jupyter nbconvert --to notebook --execute --inplace docs/nb/<name>.ipynb
```

## Available

- [`00_getting_started.ipynb`](00_getting_started.ipynb) — package import,
  `pab_version`, config paths, and `package_versions()` (Stage 0).
- [`01_database_layer.ipynb`](01_database_layer.ipynb) — `Store` create →
  upsert → query → export, idempotency, and the namespaced fit-results pivot
  (Stage 1).
- [`02_argo_mld_summary.ipynb`](02_argo_mld_summary.ipynb) — MLD (de Boyer
  Montégut), `BBP700` de-spike, whole-profile summary, DB persistence, and a
  Q&A plot; ends with an **optional `RUN_LIVE`** argopy fetch (Stage 2).
- [`03_pace_access.ipynb`](03_pace_access.ipynb) — `l2_flags` decoding, the
  canonical granule dataset, and nearest-unflagged-pixel `Rrs` extraction on a
  synthetic granule; ends with an **optional `RUN_LIVE`** earthaccess granule
  discovery (Stage 3).
- [`04_matchup.ipynb`](04_matchup.ipynb) — the matchup engine on a synthetic
  profile + granule: `build_matchups`, the selected pixels and written records,
  idempotent re-run, and flagged-pixel exclusion; ends with an **optional
  `RUN_LIVE`** real float↔PACE matchup (Stage 4).
- [`05_matchup_7902226_4.ipynb`](05_matchup_7902226_4.ipynb) — a **fully live**
  dig-in for float 7902226 / cycle 5: fetch the profile (argopy), discover and
  match the PACE granule (earthaccess + engine), and plot the profile, the
  granule, and the closest-pixel `Rrs`; a final cell over-plots the JR (Frouin)
  L1B-AC `Rrs` spectrum (imported via the biomass-paper `jr_utils`). Needs
  network + an Earthdata Login, so it is **not** part of the offline docs build
  (Stage 4).

The offline sections run without network; the Stage 2 live section is guarded by
a `RUN_LIVE = False` flag (flip to `True` to pull a real profile from argopy).
Notebook `05` is the exception — it is live end-to-end by design.

## Planned (added as the relevant stage lands)

- A worked BING fit on an extracted spectrum (Stage 5)
- Matchup metrics & figures (Stage 6)
