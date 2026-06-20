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

The offline sections run without network; the Stage 2 live section is guarded by
a `RUN_LIVE = False` flag (flip to `True` to pull a real profile from argopy).

## Planned (added as the relevant stage lands)

- PACE granule discovery + nearest-pixel Rrs extraction (Stage 3)
- A worked BING fit on an extracted spectrum (Stage 5)
- Matchup metrics & figures (Stage 6)
