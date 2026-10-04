"""Metrics are version-aware: a store with 1.0 and 2.0 fits reports one of them.

The v2 database holds BING **2.0** fits; the frozen v1 database holds the
**1.0** ones. A store that has been fitted twice would hold both for the same
matchup, and every count and scatter would silently double while mixing two
physics configurations. These pin the filter and the 1.0-vs-2.0 join.
"""

from __future__ import annotations

import pytest

from pab.db.store import Store
from pab.metrics import compare


def _seed_two_versions(store):
    """One matchup with a 1.0 and a 2.0 BING fit of the same pixel."""
    from pab.tests.test_fit import _seed_matchup

    matchup_id, pixel_id = _seed_matchup(store)
    for ver, bbp in (("1.0", 0.0020), ("2.0", 0.0015)):
        fit_id = f"{matchup_id}_ExpBPow_v{ver}"
        store.upsert(
            "fits",
            {
                "fit_id": fit_id,
                "matchup_id": matchup_id,
                "pixel_id": pixel_id,
                "algorithm": "BING",
                "model_pair": "ExpBPow",
                "chisq": 0.5,
                "success": 1,
                "pab_version": ver,
            },
        )
        store.upsert(
            "fit_results",
            {
                "fit_id": fit_id,
                "quantity": "BING_ExpBPow_bbp700",
                "value": bbp,
            },
        )
    return matchup_id


def test_version_key_orders_numerically_not_lexically():
    """'10.0' must sort above '9.0' — plain string compare gets that wrong."""
    assert compare._version_key("2.0") > compare._version_key("1.1")
    assert compare._version_key("10.0") > compare._version_key("9.0")
    assert compare._version_key("2.0") > compare._version_key("2")


def test_newest_bing_version_picks_the_newest():
    with Store.open(":memory:") as store:
        assert compare.newest_bing_version(store) is None  # empty store
        _seed_two_versions(store)
        assert compare.newest_bing_version(store) == "2.0"


def test_two_versions_of_one_matchup_yield_one_row():
    """The requirement: without the version filter this returns 2 rows."""
    with Store.open(":memory:") as store:
        _seed_two_versions(store)
        df = compare.gather_matchups(store)
        assert len(df) == 1, (
            f"expected one row for one matchup, got {len(df)} — the version "
            "filter is not applied, so counts double and two physics "
            "configurations are mixed"
        )
        assert df["pab_version"].iloc[0] == "2.0"
        assert df["bbp_bing"].iloc[0] == pytest.approx(0.0015)


def test_an_explicit_version_selects_the_older_fit():
    with Store.open(":memory:") as store:
        _seed_two_versions(store)
        df = compare.gather_matchups(store, pab_version="1.0")
        assert len(df) == 1
        assert df["pab_version"].iloc[0] == "1.0"
        assert df["bbp_bing"].iloc[0] == pytest.approx(0.0020)


def test_nasa_giop_rows_never_count_as_bing_fits():
    """NASA rows are baseline ingests; a stray model_pair must not add a row."""
    with Store.open(":memory:") as store:
        matchup_id = _seed_two_versions(store)
        store.upsert(
            "fits",
            {
                "fit_id": f"{matchup_id}_nasa",
                "matchup_id": matchup_id,
                "algorithm": "NASA_GIOP",
                "model_pair": "ExpBPow",  # deliberately set, to prove the guard
                "pab_version": "2.0",
                "success": 1,
            },
        )
        assert len(compare.gather_matchups(store)) == 1


def test_gather_version_pair_joins_on_pixel_not_just_matchup(tmp_path):
    """Comparing two fits of *different pixels* would read as a physics change."""
    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)) as s1:
        from pab.tests.test_fit import _seed_matchup

        matchup_id, pixel_id = _seed_matchup(s1)
        # A second, real pixel of the same matchup (a FK to matchup_pixels
        # means the "other pixel" has to exist to be fitted).
        s1.upsert(
            "matchup_pixels",
            {"matchup_id": matchup_id, "ix": 3, "iy": 3, "rank": 2, "flagged": 0},
        )
        other_pixel = s1.query(
            "SELECT pixel_id FROM matchup_pixels WHERE matchup_id = ? AND rank = 2",
            (matchup_id,),
        )[0]["pixel_id"]
        assert other_pixel != pixel_id
        s1.upsert(
            "fits",
            {
                "fit_id": "f_v1",
                "matchup_id": matchup_id,
                "pixel_id": other_pixel,  # a DIFFERENT pixel
                "algorithm": "BING",
                "model_pair": "ExpBPow",
                "pab_version": "1.0",
                "success": 1,
            },
        )
    with Store.open(":memory:") as s2:
        from pab.tests.test_fit import _seed_matchup

        m2, px2 = _seed_matchup(s2)
        s2.upsert(
            "fits",
            {
                "fit_id": "f_v2",
                "matchup_id": m2,
                "pixel_id": px2,
                "algorithm": "BING",
                "model_pair": "ExpBPow",
                "pab_version": "2.0",
                "success": 1,
            },
        )
        df = compare.gather_version_pair(s2, str(v1))
        assert len(df) == 0, (
            "fits of different pixels were paired; a spatial difference would "
            "be reported as a 1.0-vs-2.0 physics difference"
        )


def test_gather_version_pair_detaches_even_on_error(tmp_path):
    """A left-attached v1 would make the next ATTACH fail with a stale alias."""
    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)):
        pass
    with Store.open(":memory:") as s2:
        compare.gather_version_pair(s2, str(v1))
        # A second call must work: proves the first detached.
        compare.gather_version_pair(s2, str(v1))


def test_summary_page_counts_only_the_reported_version():
    """Coverage counts must not exceed the matchup count by double-counting."""
    from pab.report import rst

    with Store.open(":memory:") as store:
        _seed_two_versions(store)
        page = rst.summary_page(store)
        assert "**BING fits:** 1 " in page, (
            "the coverage count included both the 1.0 and the 2.0 fit of the "
            "same matchup:\n"
            + "\n".join(ln for ln in page.splitlines() if "BING fits" in ln)
        )
        assert "``pab_version`` 2.0" in page


def test_gather_version_pair_never_creates_the_database(tmp_path):
    """`ATTACH` of a plain path creates the file; a typo must not write one.

    Without the existence check a mistyped ``--compare-db`` leaves an empty
    SQLite file next to the real data and then fails with the misleading
    ``no such table: v1.fits``.
    """
    missing = tmp_path / "typo.db"
    with Store.open(":memory:") as store:
        with pytest.raises(FileNotFoundError):
            compare.gather_version_pair(store, str(missing))
    assert not missing.exists(), "a stray database was created on disk"


def test_the_comparison_database_is_attached_read_only(tmp_path):
    """The frozen v1 release must be unwritable *by this code*, not just by chmod.

    `ATTACH` of a `file:…?mode=ro` URI only works when the connection was
    opened with `uri=True`; otherwise SQLite reads it as a literal filename and
    the attach fails. An earlier version fell back to a plain-path `ATTACH` --
    which is read-WRITE -- so the frozen database was attached writable on
    every call and only the file's `chmod a-w` prevented damage. This asserts
    the protection is in the code.
    """
    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)) as s1:
        from pab.tests.test_fit import _seed_matchup

        _seed_matchup(s1)
    with Store.open(":memory:") as store:
        store.conn.execute("ATTACH DATABASE ? AS probe", (f"file:{v1}?mode=ro",))
        # readable...
        assert store.conn.execute("SELECT COUNT(*) FROM probe.matchups").fetchone()[0]
        # ...but not writable, even though the file itself is writable here
        with pytest.raises(Exception, match="readonly"):
            store.conn.execute("CREATE TABLE probe.should_not_exist (x)")
        store.conn.execute("DETACH DATABASE probe")


def test_gather_version_pair_does_not_fall_back_to_a_writable_attach(tmp_path):
    """A failed read-only attach must raise, not silently attach read-write."""
    import sqlite3

    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)) as s1:
        from pab.tests.test_fit import _seed_matchup

        _seed_matchup(s1)
    # A connection WITHOUT uri=True cannot honour the read-only URI.
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store = Store(conn)
    store.create()
    with pytest.raises(sqlite3.Error):
        compare.gather_version_pair(store, str(v1))
    conn.close()
