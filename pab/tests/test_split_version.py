"""Tests for ``pab.db.split_version`` (the v1 -> v2 database split).

Everything runs against a small **synthetic schema-v4 store** built on disk in
``tmp_path``, so the tests never touch the frozen release.
"""

import sqlite3
from pathlib import Path

import pytest

from pab.db import Store, schema, split_version


def _seed(path, *, n_matchups=3, n_pixels=2):
    """Build a synthetic v4 store with BING **and** NASA-GIOP fits.

    One float, ``n_matchups`` profile/granule/matchup chains, ``n_pixels``
    pixels each, and for every pixel a BING fit (2 result rows) plus a
    NASA-GIOP fit (3 result rows). ``scene_path`` is set on every matchup.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    store = Store.open(path)
    store.upsert("floats", {"wmo": 6903823, "project_name": "P", "data_center": "IF"})
    for m in range(n_matchups):
        store.upsert(
            "profiles",
            {"wmo": 6903823, "cycle": m, "latitude": 1.0 * m, "longitude": -30.0},
        )
        pid = store.query(
            "SELECT profile_id FROM profiles WHERE wmo = ? AND cycle = ?",
            (6903823, m),
        )[0]["profile_id"]
        store.upsert("mld_summary", {"profile_id": pid, "mld": 20.0, "chla": 0.3})
        gid = f"G{m}"
        store.upsert("granules", {"granule_id": gid, "short_name": "PACE_OCI_L2_AOP"})
        mid = f"M{m}"
        store.upsert(
            "matchups",
            {
                "matchup_id": mid,
                "profile_id": pid,
                "granule_id": gid,
                "n_spectra": n_pixels,
                "scene_path": f"/scenes/{mid}.png",
                "pab_version": "1.0",
            },
        )
        for ix in range(n_pixels):
            store.upsert(
                "matchup_pixels",
                {"matchup_id": mid, "ix": ix, "iy": 0, "rank": ix + 1},
            )
            pxid = store.query(
                "SELECT pixel_id FROM matchup_pixels "
                "WHERE matchup_id = ? AND ix = ? AND iy = 0",
                (mid, ix),
            )[0]["pixel_id"]
            for algo, ver, quantities in (
                ("BING", "1.0", ("BING_ExpBPow_bbp440", "BING_ExpBPow_chl")),
                (
                    "NASA_GIOP",
                    "1.1",
                    ("NASA_GIOP_bbp_442", "NASA_GIOP_adg_442", "NASA_GIOP_aph_442"),
                ),
            ):
                fit_id = f"{mid}_{ix}_{algo}"
                store.upsert(
                    "fits",
                    {
                        "fit_id": fit_id,
                        "matchup_id": mid,
                        "pixel_id": pxid,
                        "algorithm": algo,
                        "model_pair": "ExpBPow" if algo == "BING" else None,
                        "chains_path": f"/chains/{fit_id}.npz",
                        "pab_version": ver,
                    },
                )
                for q in quantities:
                    store.upsert(
                        "fit_results",
                        {"fit_id": fit_id, "quantity": q, "value": 0.01},
                    )
    store.close()
    return path


@pytest.fixture
def v1_db(tmp_path):
    """A synthetic, frozen (read-only) v1 database."""
    path = _seed(tmp_path / "v1" / "pab.db")
    path.chmod(0o444)
    return path


def test_seed_is_schema_v4(v1_db):
    conn = sqlite3.connect(f"file:{v1_db}?mode=ro", uri=True)
    assert schema.get_version(conn) == schema.SCHEMA_VERSION == 4
    conn.close()


def test_split_drops_bing_and_keeps_the_rest(v1_db, tmp_path):
    dst = tmp_path / "v2" / "pab.db"
    report = split_version.split_version(v1_db, dst)

    assert report["ok"], report["problems"]
    assert report["deleted"] == {"fits": 6, "fit_results": 12}
    # 3 matchups x 2 pixels = 6 fits per algorithm.
    assert report["src_counts"]["fits"] == 12
    assert report["dst_counts"]["fits"] == 6
    assert report["dst_algorithms"] == {"NASA_GIOP": 6}
    assert report["dst_quantity_prefixes"] == {"NASA": 18}
    assert report["integrity_check"] == ["ok"]
    assert report["foreign_key_violations"] == 0


def test_every_other_table_is_untouched(v1_db, tmp_path):
    dst = tmp_path / "v2" / "pab.db"
    report = split_version.split_version(v1_db, dst)
    for table in schema.TABLE_NAMES:
        if table in ("fits", "fit_results"):
            continue
        assert report["dst_counts"][table] == report["src_counts"][table], table


def test_scene_path_survives(v1_db, tmp_path):
    """R7: the v2 site reuses v1's PACE scene quick-looks."""
    dst = tmp_path / "v2" / "pab.db"
    split_version.split_version(v1_db, dst)
    conn = sqlite3.connect(dst)
    paths = [r[0] for r in conn.execute("SELECT scene_path FROM matchups ORDER BY 1")]
    conn.close()
    assert paths == ["/scenes/M0.png", "/scenes/M1.png", "/scenes/M2.png"]


def test_source_is_not_modified(v1_db, tmp_path):
    """The frozen source must be byte-identical afterwards."""
    before = split_version.sha256(v1_db)
    report = split_version.split_version(v1_db, tmp_path / "v2" / "pab.db")
    assert split_version.sha256(v1_db) == before
    assert report["src_sha256"] == before
    assert report["src_sha256_expected"] == before


def test_copy_of_readonly_source_is_writable(v1_db, tmp_path):
    """A ``shutil.copy2`` would carry ``a-w`` across and break the DELETE."""
    dst = split_version.copy_database(v1_db, tmp_path / "v2" / "pab.db")
    conn = sqlite3.connect(dst)
    conn.execute("CREATE TABLE _probe (x INT)")  # must not raise
    conn.close()


def test_dst_parent_is_created(v1_db, tmp_path):
    dst = tmp_path / "deep" / "nested" / "pab.db"
    split_version.split_version(v1_db, dst)
    assert dst.exists()


def test_refuses_to_clobber_without_overwrite(v1_db, tmp_path):
    dst = tmp_path / "v2" / "pab.db"
    split_version.split_version(v1_db, dst)
    with pytest.raises(FileExistsError):
        split_version.split_version(v1_db, dst)
    report = split_version.split_version(v1_db, dst, overwrite=True)
    assert report["ok"], report["problems"]


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        split_version.split_version(tmp_path / "nope.db", tmp_path / "out.db")


def test_vacuum_shrinks_the_copy(v1_db, tmp_path):
    """Without VACUUM the freed pages stay in the file."""
    big = split_version.split_version(v1_db, tmp_path / "a" / "pab.db", vacuum=False)
    small = split_version.split_version(v1_db, tmp_path / "b" / "pab.db", vacuum=True)
    assert small["dst_bytes"] <= big["dst_bytes"]
    assert small["ok"] and big["ok"]


def test_verify_flags_a_tampered_copy(v1_db, tmp_path):
    """verify() must fail when the copy diverges beyond the dropped algorithm."""
    dst = tmp_path / "v2" / "pab.db"
    split_version.split_version(v1_db, dst)
    conn = sqlite3.connect(dst)
    conn.execute("DELETE FROM matchup_pixels WHERE ix = 0")
    conn.execute("UPDATE matchups SET scene_path = NULL")
    conn.commit()
    conn.close()

    report = split_version.verify(v1_db, dst, dropped="BING")
    assert not report["ok"]
    assert any("matchup_pixels" in p for p in report["problems"])
    assert any("scene_path" in p for p in report["problems"])


def test_verify_flags_a_changed_source(v1_db, tmp_path):
    dst = tmp_path / "v2" / "pab.db"
    split_version.split_version(v1_db, dst)
    report = split_version.verify(v1_db, dst, dropped="BING", src_sha256="deadbeef")
    assert not report["ok"]
    assert any("IS NOT FROZEN" in p for p in report["problems"])


def test_dropping_nasa_instead(v1_db, tmp_path):
    """The algorithm to drop is a parameter, not a hard-coded 'BING'."""
    dst = tmp_path / "v2" / "pab.db"
    report = split_version.split_version(v1_db, dst, dropped="NASA_GIOP")
    assert report["ok"], report["problems"]
    assert report["dst_algorithms"] == {"BING": 6}
    assert report["dst_quantity_prefixes"] == {"BING": 12}


def test_cli_entry_point(v1_db, tmp_path, capsys):
    dst = tmp_path / "v2" / "pab.db"
    rc = split_version.main(["--src", str(v1_db), "--dst", str(dst), "--fit-chains"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK — no problems found." in out
    assert (dst.parent / "fit_chains").is_dir()


def test_cli_returns_nonzero_on_problems(v1_db, tmp_path, monkeypatch):
    def _bad(*a, **k):
        return {"ok": False, "problems": ["boom"], "src": "s", "dst": "d"}

    monkeypatch.setattr(split_version, "split_version", _bad)
    monkeypatch.setattr(split_version, "_format_report", lambda r: "bad")
    rc = split_version.main(["--src", str(v1_db), "--dst", str(tmp_path / "x.db")])
    assert rc == 1
