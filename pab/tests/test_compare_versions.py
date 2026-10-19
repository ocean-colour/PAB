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
    # ...unless SQLite was built with SQLITE_USE_URI=1 (e.g. Ubuntu's system
    # libsqlite3, which CI links against): then URIs are honoured on every
    # connection, the attach succeeds read-only, and there is nothing to test.
    if "USE_URI" in {r[0] for r in conn.execute("PRAGMA compile_options")}:
        conn.close()
        pytest.skip("this SQLite build honours URI filenames by default")
    conn.row_factory = sqlite3.Row
    store = Store(conn)
    store.create()
    with pytest.raises(sqlite3.Error):
        compare.gather_version_pair(store, str(v1))
    conn.close()


# -- the patch-version overlay (O7, Q&A/Outliers 1 = C) -----------------------
PATCH_PRIOR_SET = "bing_standard+ceiling:bbp600<=0.1,adg<=10,aph<=10"


def _add_bing_fit(
    store,
    matchup_id,
    pixel_id,
    *,
    version,
    bbp,
    chl=None,
    success=1,
    prior_set=None,
    figure_path=None,
    chains_path=None,
    model_pair="ExpBPow",
):
    """One BING ``fits`` row (+ ``bbp700``/``chl`` results) at ``version`` on
    ``pixel_id``; returns its ``fit_id`` (``…_v<version>``, like production)."""
    fit_id = f"{matchup_id}_{pixel_id}_{model_pair}_v{version}"
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "pixel_id": pixel_id,
            "algorithm": "BING",
            "model_pair": model_pair,
            "chisq": 0.5,
            "success": success,
            "prior_set": prior_set,
            "figure_path": figure_path,
            "chains_path": chains_path,
            "pab_version": version,
        },
    )
    vals = {"bbp700": bbp}
    if chl is not None:
        vals["chl"] = chl
    for q, v in vals.items():
        store.upsert(
            "fit_results",
            {"fit_id": fit_id, "quantity": f"BING_{model_pair}_{q}", "value": v},
        )
    return fit_id


def _seed_patched_runaway(store):
    """The O6 shape on one matchup: a 2.0 runaway (5e4) and its 2.0.1 re-fit
    (4e-4, Chl 0.005, ``success = 0``) on the **same** pixel. Returns
    ``(matchup_id, pixel_id, fit_2_0, fit_2_0_1)``."""
    from pab.tests.test_fit import _seed_matchup

    matchup_id, pixel_id = _seed_matchup(store)
    f20 = _add_bing_fit(store, matchup_id, pixel_id, version="2.0", bbp=5e4, chl=0.01)
    f201 = _add_bing_fit(
        store, matchup_id, pixel_id, version="2.0.1", bbp=4e-4, chl=0.005,
        success=0, prior_set=PATCH_PRIOR_SET,
    )
    return matchup_id, pixel_id, f20, f201


def test_version_helpers_and_family():
    assert compare.is_patch_version("2.0.1") and not compare.is_patch_version("2.0")
    assert compare.base_version("2.0.1") == "2.0" and compare.base_version("2.0") == "2.0"
    with Store.open(":memory:") as store:
        assert compare.version_family(store) == (None, [])
        assert compare.resolve_versions(store) == []
        _seed_two_versions(store)  # 1.0 and 2.0: two families, no patch
        assert compare.version_family(store) == ("2.0", [])
        assert compare.version_family(store, "1.0") == ("1.0", [])
    with Store.open(":memory:") as store:
        matchup_id, pixel_id, _, _ = _seed_patched_runaway(store)
        assert compare.version_family(store) == ("2.0", ["2.0.1"])
        # an explicit base is exactly the base (what --figure-version 2.0 means)
        assert compare.version_family(store, "2.0") == ("2.0", [])
        assert compare.version_family(store, "2.0.1") == ("2.0", ["2.0.1"])
        assert compare.resolve_versions(store) == ["2.0", "2.0.1"]
        assert compare.resolve_versions(store, "2.0") == ["2.0"]
        assert compare.resolve_versions(store, ["2.0", "2.0.1"]) == ["2.0", "2.0.1"]
        assert compare.newest_bing_version(store) == "2.0.1"


def test_overlay_patch_keeps_the_newest_per_matchup_and_pixel():
    import numpy as np
    import pandas as pd

    df = pd.DataFrame(
        {
            "matchup_id": ["M1", "M1", "M1", "M2", "M3", "M3"],
            "pixel_id": [1, 1, 2, 1, None, None],
            "pab_version": ["2.0", "2.0.1", "2.0", "2.0", "2.0", "2.0.1"],
            "fit_id": ["a", "b", "c", "d", "e", "f"],
            "bbp_bing": [5e4, 4e-4, 2e-3, 3e-3, 7e4, 1e-3],
        }
    )
    out = compare.overlay_patch(df, carry=("bbp_bing", "fit_id"))
    # M1/pixel 1: the 2.0.1 row supersedes the 2.0 one; M1/pixel 2 is a
    # different pixel and stays; M2 untouched; M3 (no pixel) overlays on the
    # matchup alone since NULL matches NULL
    assert list(out["fit_id"]) == ["b", "c", "d", "f"]
    assert list(out["pab_version"]) == ["2.0.1", "2.0", "2.0", "2.0.1"]
    sup = out["bbp_bing_superseded"].to_numpy(dtype=float)
    assert sup[0] == 5e4 and sup[3] == 7e4 and np.isnan(sup[1]) and np.isnan(sup[2])
    fs = list(out["fit_id_superseded"])
    assert fs[0] == "a" and fs[3] == "e" and pd.isna(fs[1]) and pd.isna(fs[2])
    # the input is untouched; a frame without the version column passes through
    assert len(df) == 6 and "bbp_bing_superseded" not in df
    plain = compare.overlay_patch(df.drop(columns="pab_version"), carry=("bbp_bing",))
    assert len(plain) == 6 and plain["bbp_bing_superseded"].isna().all()
    # model_pair, when present, is part of the key
    df["model_pair"] = ["ExpBPow", "Cst", "ExpBPow", "ExpBPow", "ExpBPow", "ExpBPow"]
    assert len(compare.overlay_patch(df)) == 5  # M1/1 2.0 ExpBPow is not superseded by a Cst row


def test_gather_matchups_overlays_the_patch_on_the_same_pixel():
    """A 2.0 and a 2.0.1 fit of one pixel -> one row, the 2.0.1 values, with
    the superseded 2.0 fit and value carried for the exported table."""
    import numpy as np

    with Store.open(":memory:") as store:
        matchup_id, pixel_id, f20, f201 = _seed_patched_runaway(store)
        df = compare.gather_matchups(store)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["pab_version"] == "2.0.1" and row["fit_id"] == f201
        assert row["pixel_id"] == pixel_id
        assert row["bbp_bing"] == pytest.approx(4e-4) and row["chl_bing"] == pytest.approx(0.005)
        assert row["bbp_bing_superseded"] == pytest.approx(5e4)
        assert row["fit_id_superseded"] == f20
        assert row["bbp_bing_implausible"] == 0  # the gate has nothing left to exclude
        # an explicit version is exactly that version, no overlay
        base = compare.gather_matchups(store, pab_version="2.0")
        assert len(base) == 1 and base.iloc[0]["fit_id"] == f20
        assert base.iloc[0]["bbp_bing"] == 5e4 and base.iloc[0]["bbp_bing_implausible"] == 1
        import pandas as pd

        assert np.isnan(base.iloc[0]["bbp_bing_superseded"])
        assert pd.isna(base.iloc[0]["fit_id_superseded"])
        patch = compare.gather_matchups(store, pab_version="2.0.1")
        assert len(patch) == 1 and patch.iloc[0]["fit_id"] == f201
        assert compare.fit_version_counts(store) == {"2.0": 0, "2.0.1": 1}
        assert compare.fit_version_counts(store, "2.0") == {"2.0": 1}


def test_a_patch_on_a_different_pixel_does_not_supersede():
    with Store.open(":memory:") as store:
        from pab.tests.test_fit import _seed_matchup

        matchup_id, pixel_id = _seed_matchup(store)
        store.upsert(
            "matchup_pixels",
            {"matchup_id": matchup_id, "ix": 3, "iy": 3, "rank": 2, "flagged": 0},
        )
        other = store.query(
            "SELECT pixel_id FROM matchup_pixels WHERE matchup_id = ? AND rank = 2",
            (matchup_id,),
        )[0]["pixel_id"]
        f20 = _add_bing_fit(store, matchup_id, pixel_id, version="2.0", bbp=5e4)
        f201 = _add_bing_fit(store, matchup_id, other, version="2.0.1", bbp=4e-4)
        df = compare.gather_matchups(store)
        assert sorted(df["fit_id"]) == sorted([f20, f201]), (
            "a 2.0.1 fit of another pixel superseded the 2.0 fit"
        )
        assert df["bbp_bing_superseded"].isna().all()
        assert compare.fit_version_counts(store) == {"2.0": 1, "2.0.1": 1}


def test_gather_nasa_giop_has_no_duplicate_after_a_patch():
    from pab.tests.test_report import _seed_nasa_giop

    with Store.open(":memory:") as store:
        matchup_id, pixel_id, f20, f201 = _seed_patched_runaway(store)
        _seed_nasa_giop(store, matchup_id)
        df = compare.gather_nasa_giop(store)
        assert len(df) == 1, "the re-fitted matchup appeared once per version"
        assert df.iloc[0]["bing_fit_id"] == f201 and df.iloc[0]["pab_version"] == "2.0.1"
        assert df.iloc[0]["bbp_bing"] == pytest.approx(4e-4)
        assert df.iloc[0]["pixel_id"] == pixel_id


def test_gather_version_pair_pairs_the_patch_with_1_0(tmp_path):
    """The 51 pairs become 1.0 vs 2.0.1, one row each, version_v2 saying so."""
    from pab.tests.test_fit import _seed_matchup

    v1 = tmp_path / "v1.db"
    with Store.open(str(v1)) as s1:
        m, px = _seed_matchup(s1)
        _add_bing_fit(s1, m, px, version="1.0", bbp=2e-3)
    with Store.open(":memory:") as store:
        matchup_id, pixel_id, f20, f201 = _seed_patched_runaway(store)
        assert (matchup_id, pixel_id) == (m, px)
        df = compare.gather_version_pair(store, str(v1))
        assert len(df) == 1, "the re-fitted matchup was paired once per version"
        assert df.iloc[0]["version_v2"] == "2.0.1" and df.iloc[0]["version_v1"] == "1.0"
        assert df.iloc[0]["bbp700_v2"] == pytest.approx(4e-4)
        assert df.iloc[0]["bbp700_v1"] == pytest.approx(2e-3)


def test_summary_page_counts_the_overlaid_family():
    """"BING fits: 2 (1 at 2.0, 1 re-fitted at 2.0.1)" -- computed."""
    from pab.report import rst
    from pab.tests.test_report_versions import _seed_one

    with Store.open(":memory:") as store:
        _seed_patched_runaway(store)
        _seed_one(store, "M2", wmo=7902227, cycle=2, bbp=2e-3, chl=0.1, version="2.0")
        page = rst.summary_page(store)
        assert "- **BING fits:** 2 (1 at 2.0, 1 re-fitted at 2.0.1)\n" in page
        # the b_bp headline sees the re-fitted value, so nothing is excluded
        assert "0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded" in page
