# Build v2 — Prompt 6: the leading slice (go/no-go gate)

## Goals

Fit **100 matchups** under the 2.0 configuration in-pod, measure what the
full send will cost and what the physics change does, and stop for JXP's
review before committing ~16.8k fits (`run_full_inelastic.md` Plan §5
step 6; Q12, R2 c, R4).

## Claude

### Skills

- **`diagnose-mcmc`**, **`debug-priors`** — the first real look at
  6-parameter robust chains at scale.

### Working agreements

As in `build_v2_prompt_1.md`. The slice's 2.0 fits are **real** (they stay
in `/data/v2/pab.db`, idempotently skipped by the full run); the
`B_p`-fixed diagnostic fits go to a **scratch DB copy** and scratch chains,
never to v2. Job launches confirmed with the user.

## Context

- Plan §3 (cost), §5 step 6 of `claude_prompts/v2/run_full_inelastic.md`;
  the NASA-GIOP leading-slice pattern in `claude_prompts/pace_giop_gsm.md`
  (Full Run Task 2).
- `nautilus/full_fit_job.yaml` — the **DB-local wrapper** (copy the DB to
  `emptyDir`, run, checkpoint back by local backup + file copy every 2 min;
  never `sqlite3.backup()` onto CephFS). Reuse it; add a slice mechanism —
  the `fit` stage has no `--limit`; either add `--limit N` / `--matchup ID`
  (the long-planned single-matchup targeting) to the CLI, or stage a
  100-matchup selection via a SQL view/temporary table. Pick the least code.
- v1 numbers for the same matchups: `v1/pab.db` (frozen) — read-only
  `ATTACH`.
- Pause triggers agreed in Q12: median s/fit > 4 min; failure rate > 2 %;
  a `b_bp` shift JXP considers implausible.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below

## Tasks

1. **Slice selection + mechanism.** Choose 100 matchups stratified by
   basin/season/`theta_v` (include some swath-edge pixels) that have a v1
   fit; implement the slicing mechanism; `nautilus/v2_fit_slice_job.yaml`
   (image `:2.0.0`, DB-local wrapper, `PAB_DATA_DIR=/data/v2`, `--jobs 32`,
   100 Gi). Run it. Log.

2. **Measure.** From the pod log + the v2 DB: s/fit (median, p90; and CPU
   time per fit), failure count + causes, χ² and acceptance-fraction
   distributions vs the same matchups' v1 fits, `bbp700(2.0)/bbp700(1.0)`
   and `chl(2.0)/chl(1.0)` distributions, `Bp` posterior medians and widths
   (how often it pins to a prior edge), per-band residuals around 685 nm
   and at 713/719 nm plus `Rrs_unc(719)/Rrs(719)` (R4). Project the full
   send (~16.8k fits, 50 workers) in hours and chain GB. Log.

3. **Attribution (diagnostic).** Fit the same 100 with `fit_Bp=False`
   (`Bp_value=0.01`), otherwise 2.0, on a scratch copy; report how much of
   the `bbp700` shift is the free `B_p` vs the emulator + inelastic terms.
   Write the whole gate under **Reports** with a clear **go / pause**
   recommendation against the Q12 triggers, and **stop — JXP reviews before
   Prompt 7.** Put any questions in Q&A. Log.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
