import sqlite3
from pathlib import Path

db_path = Path("data/pab.db")
if not db_path.exists():
    print(f"No database found at {db_path}")
    raise SystemExit

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

tables = ["floats", "profiles", "mld_summary", "granules",
          "matchups", "matchup_pixels", "fits", "fit_results"]

for table in tables:
    try:
        rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:20s}  {rows:>6} rows")
    except Exception as e:
        print(f"  {table:20s}  (error: {e})")

print()

# Show profiles
print("=== profiles ===")
for r in conn.execute("SELECT wmo, cycle, latitude, longitude, time FROM profiles"):
    print(f"  {r['wmo']} cy{r['cycle']:>3}  {r['latitude']:.3f}°N {r['longitude']:.3f}°E  {r['time']}")

print()

# Show granules
print("=== granules ===")
for r in conn.execute("SELECT id, time, short_name FROM granules"):
    print(f"  {r['id']}  {r['time']}  {r['short_name']}")

print()

# Show matchups
print("=== matchups ===")
for r in conn.execute("""
    SELECT m.matchup_id, p.wmo, p.cycle, m.dtime_hours, m.distance_km, m.n_spectra
    FROM matchups m JOIN profiles p USING (profile_id)
"""):
    print(f"  {r['matchup_id']}  wmo={r['wmo']} cy{r['cycle']}  "
          f"Δt={r['dtime_hours']:.1f}h  dist={r['distance_km']:.1f}km  "
          f"n_spectra={r['n_spectra']}")

print()

# Show fit_results summary if any
n_fits = conn.execute("SELECT COUNT(*) FROM fits").fetchone()[0]
if n_fits:
    print("=== fits ===")
    for r in conn.execute("SELECT fit_id, matchup_id, model_pair FROM fits LIMIT 10"):
        print(f"  {r['fit_id']}  {r['matchup_id']}  {r['model_pair']}")

conn.close()
