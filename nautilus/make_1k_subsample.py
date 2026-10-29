"""Build a 1000-profile stratified subsample of the full selection, then
simulate how the current discover/match candidate logic behaves on it.

Stratification: even across year-quarters (seasons + the whole PACE window),
<= 3 profiles per float (spreads the 882 floats), fixed seed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SRC = "/mnt/tank/Oceanography/data/PAB/full_profiles.csv"
OUT = "/mnt/tank/Oceanography/data/PAB/run1k_profiles.csv"
N = 1000
RNG = np.random.default_rng(20260726)

df = pd.read_csv(SRC)
df["dt"] = pd.to_datetime(df["date"], format="mixed", utc=True)
df["q"] = df["dt"].dt.to_period("Q").astype(str)
print(f"source: {len(df)} profiles / {df.wmo.nunique()} floats  "
      f"{df.dt.min().date()} → {df.dt.max().date()}")

# cap 3 profiles/float (sampled at random within each float)
capped = (
    df.sample(frac=1.0, random_state=1)
    .groupby("wmo", group_keys=False)
    .head(3)
)
print(f"after <=3/float cap: {len(capped)} candidates / {capped.wmo.nunique()} floats")

# even split across quarters, then top up at random if a quarter is short
quarters = sorted(capped["q"].unique())
per_q = N // len(quarters)
picks = []
for q in quarters:
    pool = capped[capped["q"] == q]
    take = min(per_q, len(pool))
    picks.append(pool.sample(take, random_state=int(RNG.integers(1e6))))
sel = pd.concat(picks)
if len(sel) < N:
    rest = capped.drop(sel.index).sample(N - len(sel), random_state=7)
    sel = pd.concat([sel, rest])
sel = sel.sort_values(["wmo", "cycle"]).reset_index(drop=True)

print(f"\nselected: {len(sel)} profiles / {sel.wmo.nunique()} floats")
print(f"  time:  {sel.dt.min().date()} → {sel.dt.max().date()}  "
      f"({len(quarters)} quarters, {per_q}/quarter)")
print(f"  lat:   {sel.latitude.min():.1f} → {sel.latitude.max():.1f}")
print(f"  lon:   {sel.longitude.min():.1f} → {sel.longitude.max():.1f}")
basin = pd.cut(
    sel.longitude, [-180, -70, 20, 147, 180],
    labels=["Pacific(E)", "Atlantic", "Indian", "Pacific(W)"],
)
print("  basin:", basin.value_counts().to_dict())
print("  profiles/float:", sel.groupby("wmo").size().describe()[["min", "50%", "max"]].to_dict())

sel[["wmo", "cycle", "date", "latitude", "longitude"]].to_csv(OUT, index=False)
print(f"\nwrote {OUT}")

# ---- simulate the CURRENT discover() skip test (location-blind) -------------
# A profile is skipped if ANY granule already in the table is within +-24 h of
# its time, regardless of where on Earth that granule is.
t = sel["dt"].astype("int64").to_numpy()          # DB/CSV order
H = 3600 * 1_000_000_000
gran: list[int] = []                               # granule times in the table
searched = skipped = 0
for ti in t:
    g = np.array(gran)
    if g.size and np.any(np.abs(g - ti) <= 24 * H):
        skipped += 1
        continue
    searched += 1
    # ~5.67 granules found, times spread within +-24 h of the profile
    gran.extend((ti + RNG.uniform(-24, 24, 6) * H).astype("int64").tolist())
print(f"\ncurrent discover(): {searched} profiles searched, {skipped} SKIPPED "
      f"({100*skipped/len(t):.0f}% never get their own granules)")

# ---- candidate_granules() size at this N (location-blind +-24 h) ------------
# With a correct discover, the table would hold ~5.67 granules per profile,
# times within +-24 h of each profile.
gt = np.sort(np.concatenate([
    (t[:, None] + RNG.uniform(-24, 24, (len(t), 6)) * H).astype("int64").ravel()
]))
lo = np.searchsorted(gt, t - 24 * H)
hi = np.searchsorted(gt, t + 24 * H)
c = hi - lo
print(f"candidate_granules() per profile at N={len(t)}: mean {c.mean():.0f} "
      f"median {np.median(c):.0f} max {c.max()}  → {c.sum():,} granule opens "
      f"(vs ~{int(5.67*len(t)):,} truly relevant, {c.mean()/5.67:.1f}x)")
print(f"  match wall-clock @4.4 s/open: serial {c.sum()*4.4/3600:.1f} h, "
      f"50 cores {c.sum()*4.4/3600/50:.1f} h")
