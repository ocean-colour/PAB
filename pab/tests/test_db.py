"""Stage 1 tests for the SQLite storage layer (``pab.db``)."""

import sqlite3

import pytest

from pab.config import pab_version
from pab.db import Store, schema


@pytest.fixture
def store():
    """An in-memory store with the schema created."""
    s = Store.open(":memory:")
    yield s
    s.close()


@pytest.fixture
def seeded(store):
    """A store seeded with one float -> profile -> granule -> matchup chain."""
    store.upsert("floats", {"wmo": 6903823})
    store.upsert(
        "profiles",
        {
            "wmo": 6903823,
            "cycle": 387,
            "latitude": 45.0,
            "longitude": -30.0,
            "time": "2024-05-01T00:00:00",
            "data_mode": "D",
        },
    )
    pid = store.query("SELECT profile_id FROM profiles")[0]["profile_id"]
    store.upsert(
        "granules",
        {
            "granule_id": "G1",
            "short_name": "PACE_OCI_L2_AOP",
            "time_start": "2024-05-01T00:30:00",
            "cloud_cover": 5.0,
            "data_url": "s3://bucket/G1.nc",
        },
    )
    store.upsert(
        "matchups",
        {
            "matchup_id": "M1",
            "profile_id": pid,
            "granule_id": "G1",
            "distance_km": 2.3,
            "dtime_hours": 0.5,
            "n_spectra": 10,
            "created": "2026-06-19T00:00:00",
            "pab_version": pab_version,
        },
    )
    return store, pid


# -- schema -----------------------------------------------------------------
def test_schema_version_and_tables(store):
    assert schema.get_version(store.conn) == schema.SCHEMA_VERSION
    names = {
        r["name"]
        for r in store.query("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for t in schema.TABLE_NAMES:
        assert t in names


def test_create_is_idempotent(store):
    store.create()  # second call must not raise
    store.create()
    assert schema.get_version(store.conn) == schema.SCHEMA_VERSION


def test_migration_adds_qa_path(tmp_path):
    # a v1 database (mld_summary without qa_path) migrates forward to add it
    import sqlite3

    db = tmp_path / "v1.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE mld_summary (profile_id INTEGER PRIMARY KEY, mld REAL)")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    schema.migrate(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(mld_summary)")}
    assert "qa_path" in cols
    assert schema.get_version(conn) == schema.SCHEMA_VERSION == 2
    conn.close()


# -- create / insert / query round trip -------------------------------------
def test_insert_query_roundtrip(seeded):
    store, pid = seeded
    store.upsert(
        "mld_summary",
        {
            "profile_id": pid,
            "mld": 42.0,
            "mld_method": "deBoyerMontegut_0.03",
            "bbp700": 1.2e-3,
            "chla": 0.35,
            "psal": 35.1,
            "temp": 18.4,
            "n_points": 12,
            "created": "2026-06-19T00:00:00",
            "pab_version": pab_version,
        },
    )
    rows = store.query("SELECT * FROM mld_summary WHERE profile_id = ?", (pid,))
    assert len(rows) == 1
    assert rows[0]["mld"] == 42.0
    assert rows[0]["bbp700"] == pytest.approx(1.2e-3)


# -- idempotent upserts keyed by matchup ID ---------------------------------
def test_upsert_idempotent_by_matchup_id(seeded):
    store, pid = seeded
    base = {
        "matchup_id": "M1",
        "profile_id": pid,
        "granule_id": "G1",
        "distance_km": 9.9,  # changed
        "dtime_hours": 0.5,
        "n_spectra": 8,  # changed
        "created": "2026-06-19T00:00:00",
        "pab_version": pab_version,
    }
    store.upsert("matchups", base)  # re-upsert same key
    assert store.count("matchups") == 1  # no duplicate
    row = store.query("SELECT * FROM matchups WHERE matchup_id='M1'")[0]
    assert row["distance_km"] == 9.9  # updated in place
    assert row["n_spectra"] == 8


def test_upsert_updates_non_key_columns(store):
    store.upsert("floats", {"wmo": 1, "project_name": "A"})
    store.upsert("floats", {"wmo": 1, "project_name": "B"})
    assert store.count("floats") == 1
    assert store.query("SELECT project_name FROM floats")[0]["project_name"] == "B"


def test_upsert_missing_key_raises(store):
    with pytest.raises(KeyError):
        store.upsert("profiles", {"cycle": 1})  # missing 'wmo'


def test_upsert_unknown_table_raises(store):
    with pytest.raises(KeyError):
        store.upsert("not_a_table", {"x": 1})


# -- schema constraints ------------------------------------------------------
def test_foreign_key_enforced(store):
    # profile referencing a non-existent float must fail (FK pragma is ON).
    with pytest.raises(sqlite3.IntegrityError):
        store.insert("profiles", {"wmo": 999999, "cycle": 1})


def test_unique_constraint_enforced(seeded):
    store, _ = seeded
    with pytest.raises(sqlite3.IntegrityError):
        # duplicate (wmo, cycle) via plain insert
        store.insert("profiles", {"wmo": 6903823, "cycle": 387})


# -- export equals query -----------------------------------------------------
def test_export_csv_equals_query(seeded, tmp_path):
    store, _ = seeded
    out = store.export_csv("matchups", tmp_path / "matchups.csv")
    import csv

    with out.open() as fh:
        rows = list(csv.DictReader(fh))
    queried = store.query("SELECT * FROM matchups")
    assert len(rows) == len(queried) == 1
    # CSV stringifies; compare on the key field and a numeric field.
    assert rows[0]["matchup_id"] == queried[0]["matchup_id"]
    assert float(rows[0]["distance_km"]) == pytest.approx(queried[0]["distance_km"])


def test_export_parquet_roundtrip(seeded, tmp_path):
    store, _ = seeded
    pd = pytest.importorskip("pandas")
    out = store.export_parquet("matchups", tmp_path / "matchups.parquet")
    df = pd.read_parquet(out)
    assert list(df["matchup_id"]) == ["M1"]
    assert df["n_spectra"].iloc[0] == 10


# -- namespaced fit results pivot -------------------------------------------
def test_fit_results_wide(seeded):
    store, pid = seeded
    store.upsert(
        "fits",
        {
            "fit_id": "F1",
            "matchup_id": "M1",
            "algorithm": "BING",
            "model_pair": "ExpBPow",
            "rrs_source": "L2_AOP",
            "pab_version": pab_version,
            "created": "2026-06-19T00:00:00",
        },
    )
    store.upsert_many(
        "fit_results",
        [
            {
                "fit_id": "F1",
                "quantity": "BING_ExpBPow_bbp",
                "value": 1.5e-3,
                "value_lo": 1.0e-3,
                "value_hi": 2.0e-3,
                "unit": "m^-1",
            },
            {
                "fit_id": "F1",
                "quantity": "BING_ExpBPow_beta",
                "value": 0.8,
                "value_lo": 0.6,
                "value_hi": 1.0,
                "unit": "",
            },
        ],
    )
    wide = store.fit_results_wide()
    assert "BING_ExpBPow_bbp" in wide.columns
    assert "BING_ExpBPow_bbp_lo" in wide.columns
    assert wide.loc["F1", "BING_ExpBPow_bbp"] == pytest.approx(1.5e-3)
    assert wide.loc["F1", "BING_ExpBPow_beta_hi"] == pytest.approx(1.0)


def test_idempotent_fit_results_upsert(seeded):
    store, _ = seeded
    store.upsert(
        "fits",
        {"fit_id": "F1", "matchup_id": "M1", "pab_version": pab_version},
    )
    row = {
        "fit_id": "F1",
        "quantity": "BING_ExpBPow_bbp",
        "value": 1.0e-3,
        "unit": "m^-1",
    }
    store.upsert("fit_results", row)
    store.upsert("fit_results", {**row, "value": 2.0e-3})  # update
    res = store.query("SELECT value FROM fit_results WHERE fit_id='F1'")
    assert len(res) == 1
    assert res[0]["value"] == pytest.approx(2.0e-3)
