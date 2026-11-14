"""The ``n_neg_blue`` backfill (O4 step 2): ``pab.fit.rrs_qa_backfill``.

A synthetic store plus tmp chain NPZs stand in for the v2 database and the
workstation copy of the 2.0 chains; the real run's write discipline (backup
copy, before/after fingerprints, the pre-existing-rows checksum) is exercised
on a file database under ``tmp_path``. Nothing here touches ``$PAB_DATA_DIR``.
"""

from __future__ import annotations

import logging
import sqlite3

import numpy as np
import pytest

from pab.db.store import Store
from pab.fit import rrs_qa_backfill as bf
from pab.tests.test_metrics import _seed

Q = "BING_ExpBPow_n_neg_blue"
PVC_ROOT = "/data/v2/fit_chains"  # what fits.chains_path records (the pod's path)

#: Spectra by fit: (wave, Rrs). Two negative blue bands, none, one at the edge.
SPECTRA = {
    "M1_2_2_ExpBPow": (np.array([400.0, 425.0, 450.0, 560.0, 700.0]), np.array([-1e-4, -2e-4, 1e-3, 2e-3, -1e-5])),
    "M2_2_2_ExpBPow": (np.array([400.0, 425.0, 450.0, 560.0, 700.0]), np.array([1e-3, 1e-3, 1e-3, 2e-3, 1e-4])),
    "M3_2_2_ExpBPow": (np.array([400.0, 425.0, 450.0, 560.0, 700.0]), np.array([1e-3, 1e-3, -1e-6, 2e-3, 1e-4])),
}
EXPECTED = {"M1_2_2_ExpBPow": 2, "M2_2_2_ExpBPow": 0, "M3_2_2_ExpBPow": 1}


def _write_npz(root, fit_id, wave, rrs):
    root.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        root / f"{fit_id}.npz",
        chains=np.zeros((4, 8, 6), dtype=np.float32),
        wave=wave,
        Rrs=rrs,
        varRrs=np.full(wave.size, 1e-10),
        param_names=np.array(["Adg", "Sdg", "Aph", "Bnw", "beta", "Bp"]),
        Chl=0.1,
    )


def _seed_v2(store, *, version="2.0"):
    """Three 2.0 fits (M1 a runaway) with PVC chain paths, like the real store."""
    for i, bbp in ((1, 5e4), (2, 2e-3), (3, 3e-3)):
        _seed(
            store, f"M{i}", 7902220 + i, i, lat=20.0 + i, lon=-50.0,
            time=f"2025-05-0{i}T12:00:00", bbp_argo=1e-3, chla=0.1, bbp_bing=bbp,
            chl_bing=0.2,
        )
        fit_id = f"M{i}_2_2_ExpBPow"
        store.execute(
            "UPDATE fits SET pab_version = ?, chains_path = ? WHERE fit_id = ?",
            (version, f"{PVC_ROOT}/{fit_id}.npz", fit_id),
        )


@pytest.fixture
def chains(tmp_path):
    root = tmp_path / "fit_chains"
    for fit_id, (wave, rrs) in SPECTRA.items():
        _write_npz(root, fit_id, wave, rrs)
    return root


def _values(store):
    return {
        r["fit_id"]: r["value"]
        for r in store.query("SELECT fit_id, value FROM fit_results WHERE quantity = ?", (Q,))
    }


# -- the per-fit pieces --------------------------------------------------------
def test_quantity_name_matches_persist_fit_prefix():
    assert bf.quantity_name() == Q
    assert bf.quantity_name("Other") == "BING_Other_n_neg_blue"


def test_resolve_chain_by_basename(chains):
    assert bf.resolve_chain(f"{PVC_ROOT}/M1_2_2_ExpBPow.npz", chains) == chains / "M1_2_2_ExpBPow.npz"
    assert bf.resolve_chain(f"{PVC_ROOT}/nope.npz", chains) is None
    assert bf.resolve_chain(None, chains) is None
    assert bf.resolve_chain("", chains) is None


def test_count_from_npz_reads_the_stored_spectrum(chains):
    assert bf.count_from_npz(chains / "M1_2_2_ExpBPow.npz") == 2
    assert bf.count_from_npz(chains / "M2_2_2_ExpBPow.npz") == 0
    assert bf.count_from_npz(chains / "M3_2_2_ExpBPow.npz") == 1  # 450 nm inclusive


# -- the backfill ----------------------------------------------------------------
def test_backfill_writes_one_row_per_fit(chains):
    with Store.open(":memory:") as store:
        _seed_v2(store)
        before = store.count("fit_results")
        summary = bf.backfill(store, chains_root=chains)
        assert summary["n_fits"] == 3 and summary["n_written"] == 3
        assert summary["n_computed"] == 3 and summary["n_flagged"] == 2
        assert summary["n_missing_npz"] == 0 and summary["n_skipped_existing"] == 0
        assert summary["values"] == EXPECTED
        assert _values(store) == EXPECTED
        assert store.count("fit_results") == before + 3
        row = store.query("SELECT * FROM fit_results WHERE fit_id = 'M1_2_2_ExpBPow' AND quantity = ?", (Q,))[0]
        assert row["value"] == row["value_lo"] == row["value_hi"] == 2.0
        assert row["unit"] == "bands"


def test_backfill_is_idempotent_and_refuses_existing_without_replace(chains):
    with Store.open(":memory:") as store:
        _seed_v2(store)
        bf.backfill(store, chains_root=chains)
        again = bf.backfill(store, chains_root=chains)
        assert again["n_written"] == 0 and again["n_computed"] == 0
        assert again["n_skipped_existing"] == 3
        assert store.count("fit_results") == 6 + 3  # bbp700 + chl per fit, + the count
        assert _values(store) == EXPECTED


def test_backfill_replace_overwrites(chains):
    with Store.open(":memory:") as store:
        _seed_v2(store)
        bf.backfill(store, chains_root=chains)
        # the spectrum "changes" (a re-copied NPZ): --replace picks it up
        _write_npz(chains, "M2_2_2_ExpBPow", np.array([410.0, 560.0]), np.array([-1e-3, 1e-3]))
        summary = bf.backfill(store, chains_root=chains, replace=True)
        assert summary["n_written"] == 3 and summary["n_skipped_existing"] == 0
        assert _values(store) == {**EXPECTED, "M2_2_2_ExpBPow": 1}
        assert store.count("fit_results") == 9  # overwritten, not duplicated


def test_dry_run_writes_nothing(chains):
    with Store.open(":memory:") as store:
        _seed_v2(store)
        summary = bf.backfill(store, chains_root=chains, dry_run=True)
        assert summary["dry_run"] is True
        assert summary["n_written"] == 0
        assert summary["n_computed"] == 3 and summary["values"] == EXPECTED  # the plan
        assert _values(store) == {}
        assert store.count("fit_results") == 6
        assert "DRY RUN" in bf.format_summary(summary)
        assert "would write" in bf.format_summary(summary)


def test_missing_npz_is_counted_not_fatal(chains, caplog):
    (chains / "M3_2_2_ExpBPow.npz").unlink()
    (chains / "M2_2_2_ExpBPow.npz").write_bytes(b"not a zip file")  # unreadable
    with Store.open(":memory:") as store:
        _seed_v2(store)
        with caplog.at_level(logging.WARNING, logger="pab.fit.rrs_qa_backfill"):
            summary = bf.backfill(store, chains_root=chains)
        assert summary["n_written"] == 1 and summary["n_missing_npz"] == 2
        assert [f for f, _ in summary["missing"]] == ["M2_2_2_ExpBPow", "M3_2_2_ExpBPow"]
        assert _values(store) == {"M1_2_2_ExpBPow": 2}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1  # one summary warning, not one per file
    assert "2 of 3 fits have no readable chain NPZ" in warnings[0].getMessage()
    # the skipped fits are picked up by a re-run once their NPZs exist
    _write_npz(chains, "M3_2_2_ExpBPow", *SPECTRA["M3_2_2_ExpBPow"])
    _write_npz(chains, "M2_2_2_ExpBPow", *SPECTRA["M2_2_2_ExpBPow"])


def test_other_fit_results_rows_are_untouched(chains):
    with Store.open(":memory:") as store:
        _seed_v2(store)
        before_rows = store.query("SELECT * FROM fit_results WHERE quantity != ? ORDER BY fit_id, quantity", (Q,))
        before_fits = store.query("SELECT * FROM fits ORDER BY fit_id")
        before_sum = bf.rows_checksum(store.conn, exclude_quantity=Q)
        bf.backfill(store, chains_root=chains)
        bf.backfill(store, chains_root=chains, replace=True)
        after_rows = store.query("SELECT * FROM fit_results WHERE quantity != ? ORDER BY fit_id, quantity", (Q,))
        assert after_rows == before_rows
        assert store.query("SELECT * FROM fits ORDER BY fit_id") == before_fits  # pab_version still 2.0
        assert bf.rows_checksum(store.conn, exclude_quantity=Q) == before_sum
        assert all(r["pab_version"] == "2.0" for r in before_fits)


def test_backfill_scopes_by_version_and_model_pair(chains):
    with Store.open(":memory:") as store:
        _seed_v2(store)
        store.execute("UPDATE fits SET pab_version = '1.0' WHERE fit_id = 'M3_2_2_ExpBPow'")
        summary = bf.backfill(store, chains_root=chains, pab_version="2.0")
        assert summary["n_fits"] == 2 and set(summary["values"]) == {"M1_2_2_ExpBPow", "M2_2_2_ExpBPow"}
        assert bf.backfill(store, chains_root=chains, pab_version="2.0.1")["n_fits"] == 0
        assert bf.backfill(store, chains_root=chains, model_pair="Other")["n_fits"] == 0


# -- the CLI and its write discipline -----------------------------------------------
def _file_store(tmp_path, name="pab.db"):
    path = tmp_path / name
    with Store.open(str(path)) as store:
        _seed_v2(store)
    return path


def test_cli_dry_run_leaves_the_file_byte_identical(tmp_path, chains, capsys):
    db = _file_store(tmp_path)
    sha = bf.sha256(db)
    rc = bf.main(["--db", str(db), "--chains-root", str(chains), "--dry-run"])
    assert rc == 0
    assert bf.sha256(db) == sha
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "with n_neg_blue >= 1   2" in out
    assert f"sha256 {sha}" in out and "integrity_check      ['ok']" in out
    assert not (tmp_path / "pab.db-journal").exists()


def test_cli_real_run_needs_a_backup_copy(tmp_path, chains):
    db = _file_store(tmp_path)
    sha = bf.sha256(db)
    with pytest.raises(SystemExit) as exc:
        bf.main(["--db", str(db), "--chains-root", str(chains)])
    assert exc.value.code == 2  # argparse error
    assert bf.sha256(db) == sha  # refused before touching it


def test_cli_real_run_makes_the_backup_and_verifies(tmp_path, chains, capsys):
    db = _file_store(tmp_path)
    sha = bf.sha256(db)
    backup = tmp_path / "pab_pre_negblue_20261018.db"
    rc = bf.main(["--db", str(db), "--chains-root", str(chains), "--backup-copy", str(backup)])
    assert rc == 0
    assert backup.is_file() and bf.sha256(backup) == sha  # the pre-run bytes
    assert bf.sha256(db) != sha
    with Store.open(f"file:{db}?mode=ro", create=False) as store:
        assert _values(store) == EXPECTED
    out = capsys.readouterr().out
    assert "[before]" in out and "[after]" in out
    assert "verified: only fit_results changed (+3 rows)" in out
    assert out.count("integrity_check      ['ok']") == 2
    # the checksums over the pre-existing rows are printed twice and agree
    lines = [ln for ln in out.splitlines() if "checksum fit_results" in ln]
    assert len(lines) == 2 and lines[0] == lines[1]


def test_cli_accepts_a_matching_backup_and_refuses_a_stale_one(tmp_path, chains, capsys):
    db = _file_store(tmp_path)
    good = bf.prepare_backup(db, tmp_path / "copy.db", db_sha256=bf.sha256(db))
    assert bf.sha256(good) == bf.sha256(db)
    # a backup of some *other* database state is refused
    stale = tmp_path / "stale.db"
    stale.write_bytes(b"not this database")
    rc = bf.main(["--db", str(db), "--chains-root", str(chains), "--backup-copy", str(stale)])
    assert rc == 1 and "REFUSED" in capsys.readouterr().out
    with Store.open(f"file:{db}?mode=ro", create=False) as store:
        assert _values(store) == {}  # nothing written
    # the matching one is accepted
    rc = bf.main(["--db", str(db), "--chains-root", str(chains), "--backup-copy", str(good)])
    assert rc == 0
    with pytest.raises(ValueError, match="must not be the database itself"):
        bf.prepare_backup(db, db, db_sha256="x")


def test_refuses_v1_and_an_open_transaction(tmp_path, chains):
    v1 = tmp_path / "v1" / "pab.db"
    v1.parent.mkdir()
    with Store.open(str(v1)) as store:
        _seed_v2(store)
    with pytest.raises(PermissionError, match="frozen"):
        bf.refuse_unwritable_target(v1)
    with pytest.raises(SystemExit):
        bf.main(["--db", str(v1), "--chains-root", str(chains), "--backup-copy", str(tmp_path / "b.db")])
    with Store.open(f"file:{v1}?mode=ro", create=False) as store:
        assert _values(store) == {}

    db = _file_store(tmp_path)
    (tmp_path / "pab.db-journal").write_bytes(b"")
    with pytest.raises(RuntimeError, match="journal"):
        bf.refuse_unwritable_target(db)
    with pytest.raises(FileNotFoundError):
        bf.refuse_unwritable_target(tmp_path / "missing.db")


def test_verify_after_catches_a_changed_row(tmp_path, chains):
    db = _file_store(tmp_path)
    before = bf.fingerprint(db, exclude_quantity=Q)
    assert before["integrity"] == ["ok"] and before["n_quantity_rows"] == 0
    with Store.open(str(db), create=False) as store:
        summary = bf.backfill(store, chains_root=chains)
    after = bf.fingerprint(db, exclude_quantity=Q)
    assert bf.verify_after(before, after, summary) == []
    assert after["n_quantity_rows"] == 3
    assert after["counts"]["fit_results"] == before["counts"]["fit_results"] + 3
    # tamper with a pre-existing row: the checksum catches it
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE fit_results SET value = value * 2 WHERE quantity = 'BING_ExpBPow_bbp700' AND fit_id = 'M2_2_2_ExpBPow'")
    conn.commit()
    conn.close()
    tampered = bf.fingerprint(db, exclude_quantity=Q)
    problems = bf.verify_after(before, tampered, summary)
    assert any("checksum" in p for p in problems)
    # and a lost non-QA row
    conn = sqlite3.connect(str(db))
    conn.execute("DELETE FROM fit_results WHERE quantity = 'BING_ExpBPow_chl' AND fit_id = 'M2_2_2_ExpBPow'")
    conn.commit()
    conn.close()
    problems = bf.verify_after(before, bf.fingerprint(db, exclude_quantity=Q), summary)
    assert any("other than n_neg_blue" in p for p in problems)
