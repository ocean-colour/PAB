# PAB development data

Small, version-controlled **manifests** that pin the data PAB development works
against. Bulk data (Argo NetCDF, PACE granules) is *not* committed here — it is
cached under `PAB_DATA_DIR` at run time. Only lightweight manifests live in this
directory.

## `dev_profiles.csv` — the development BGC-Argo profile set

A fixed set of **10 BGC-Argo profiles** used for Stage 4+ development and live
demos. Two are known PACE matchups (seeds supplied by JXP — `7902226` cycle 5
and `7902136` cycle 8); the other eight are drawn **at random** (four per float)
from each float's PACE-era cycles, so the matchup engine sees both hits and
misses. The draw is reproducible: NumPy `default_rng(20260620)`, pool restricted
to profiles on/after the PACE science-data start (**2024-03-05**, per
`docs/context.md`).

Columns:

| column | meaning |
|---|---|
| `wmo` | Argo float WMO id |
| `cycle` | Argo **cycle number** (from the synthetic-profile index filename) |
| `date` | profile time (UTC, ISO-8601) |
| `latitude` / `longitude` | profile position (deg) |
| `region` | coarse biome label |
| `known_matchup` | 1 = JXP-confirmed PACE matchup seed, 0 = candidate |

Two floats, two biomes:

- **7902226** — North Atlantic subtropical gyre (~27 °N, 46 °W); profiles
  2025-01 → 2026-06.
- **7902136** — equatorial Pacific (~4 °N, 137 °W); profiles 2024-11 → 2026-06.

Both floats appear in the GDAC `argo_synthetic-profile_index.txt` (53 and 57
profiles respectively), all in the PACE era. Cycle numbers here come from that
index; JXP's original seed numbering was profile-relative and ran one low ("my
numbering, room for error") — his seed timestamps (`2025-02-18T20:26` and
`2025-01-25T13:05`) pin to index cycles **5** and **8**, which are the canonical
`cycle` values recorded above.

Regenerated from the synthetic-profile index with `argopy.ArgoIndex`; positions
and times are index metadata, so this file can be rebuilt offline-of-ERDDAP.
