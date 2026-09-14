# Build v2 — Prompt 2: per-pixel viewing geometry from PACE L1B (`geometry` stage)

## Goals

Give every matchup pixel the solar/sensor geometry the RoB backend requires
(`theta_s`, `theta_v`, `dphi`), read from the co-temporal **PACE L1B**
granule, stored on `matchup_pixels` (schema **v5**) and filled by a new
**parallel `geometry` stage** — so the `fit` stage never pays the L1B open
in its serial parent loop (`run_full_inelastic.md` Plan §2.1, §3 c; Q3 = A,
R3).

## Claude

### Skills

- **`batch-fit-argo`** — the workers-read / parent-writes pattern the new
  stage copies from `match`.

### Working agreements

As in `build_v2_prompt_1.md`: user's git; Python in `ocean14`; explicit
`--db`; **`v1/pab.db` frozen** (develop against `v2/pab.db` or a scratch
copy of it); log; use Fable if you can.

## Context

- Plan §2.1 (the verified L1B read) and §3 c/k of
  `claude_prompts/v2/run_full_inelastic.md`.
- **Verified facts (2026-09-14):** for `PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc`
  the CMR short name **`PACE_OCI_L1B_SCI`** returns the same-stamp
  `PACE_OCI.20250309T131631.L1B.V3.nc` (1.8 GB; **each granule is listed
  twice — dedupe by name**). `xr.open_datatree(earthaccess.open(...)[0],
  engine="h5netcdf")` → group `geolocation_data` with `solar_zenith`,
  `sensor_zenith`, `solar_azimuth`, `sensor_azimuth`, `latitude`,
  `longitude`, dims `(scans, pixels)` = `(1709, 1272)` — **identical grid to
  the L2**, lat/lon bit-identical at pixel `(868, 142)`; open + 4-value read
  7.6 s out-of-region. At that pixel `theta_s = 29.47°`, `theta_v = 54.58°`,
  `solar_azimuth = −19.75°`, `sensor_azimuth = 61.58°`.
- Precedents to mirror: `pab/pace/iop.py` (`iop_source_for_aop` name swap,
  flag-free nearest pixel, grid check) and `pab/matchup/engine.py` (the
  parallel `match` shape: `GranuleIndex`, `_open_with_timeout`, chunked
  pools, `_reclaim_pool`, `--jobs`).
- `pab/db/schema.py` (`MIGRATIONS`, `_v3_to_v4` as the template),
  `docs/db_schema.rst`.
- The three cached V3.2 granules in `/mnt/tank/Oceanography/data/PAB/pilot/granules/`
  (for local tests of the L2 side; the L1B read is a live network call).

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below

## Tasks

1. **Schema v5 (pixels).** Add `matchup_pixels.theta_s`, `theta_v`, `dphi`
   (degrees, REAL, NULL on legacy rows) and `geom_source` (TEXT, e.g.
   `"L1B_V3"`), via a registered `_v4_to_v5` forward migration;
   `SCHEMA_VERSION = 5`; migration test; `docs/db_schema.rst` updated with
   units and the `dphi = sensor_azimuth − solar_azimuth` (wrapped to
   (−180, 180]) convention. (The `fits` v5 columns are added in Prompt 3 —
   the same migration function may carry both; coordinate.) Log.

2. **L1B reader** (`pab/pace/l1b.py`, replacing the current
   `NotImplementedError` stub's *module*, keeping `rrs_from_l1b` untouched):
   `l1b_source_for_aop(aop_granule_id_or_url)` (name-swap `L2.OC_AOP.V3_2`
   → `L1B.V3` **plus** a CMR lookup by `PACE_OCI_L1B_SCI` + the stamp's
   time window to obtain the real URL, deduped), `open_l1b_geolocation(source)`
   (lazy datatree, `geolocation_data` only, bounded by the same
   `_open_with_timeout`), and `pixel_geometry(ds, ix, iy, *, lat, lon,
   tol_deg=0.01)` → `(theta_s, theta_v, dphi)` after a **grid check**
   against the stored pixel lat/lon (raise on mismatch — never silently
   assume alignment). Offline tests with a synthetic geolocation dataset;
   one live test guarded by an env flag reproducing the numbers above. Log.

3. **The `geometry` stage.** Add `"geometry"` to `pab.pipeline.STAGES`
   **between `match` and `fit`** (default run order), implemented like
   `match`: gather all `matchup_pixels` rows with `theta_s IS NULL` grouped
   by granule (one L1B open per granule — 11,494 granules carry today's
   14,610 matchups), workers open + read all that granule's pixels, parent
   writes; `--jobs`; idempotent (skips filled pixels; `--replace` refills);
   per-granule failures logged and counted, never aborting the stage; a
   `"failed"` list in the summary. `--stage geometry` on the CLI; `dry-run`
   lists it. Tests: serial + parallel (module-level stub opener) agree;
   resume does zero opens; a grid-check failure is recorded, not raised.
   Log.

4. **Local validation.** On a scratch copy of `v2/pab.db`, run
   `--stage geometry` for the matchups whose granules are cached locally
   (the 3 pilot granules → their L1Bs fetched live, lazily): confirm the
   rows are filled, `geom_source` set, values physically sensible
   (`0 ≤ theta_s < 90`, `0 ≤ theta_v ≲ 60`), and re-running skips them.
   Measure s/granule for the projection in Prompt 5. Report in **Reports**;
   `HOWTO.md` gains the stage row + the "geometry before fit" rule. Log.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
