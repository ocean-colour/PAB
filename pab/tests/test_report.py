"""Stage 7 tests: the reporting layer (``pab.report``)."""

import numpy as np
import pytest

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.report import aggregate, publish, rst


def _seed(
    store,
    matchup_id,
    wmo,
    cycle,
    *,
    lat,
    lon,
    time,
    bbp_argo,
    bbp_bing,
    chla=0.1,
    chl_bing=0.12,
    chains_path=None,
    figure_path=None,
):
    pid = persist_summary(
        store,
        wmo=wmo,
        cycle=cycle,
        summary={
            "mld": 30.0,
            "mld_method": "x",
            "bbp700": bbp_argo,
            "chla": chla,
            "n_points": 6,
        },
        latitude=lat,
        longitude=lon,
        time=time,
    )
    gid = f"G_{cycle}"
    store.upsert("granules", {"granule_id": gid, "data_url": f"s3://b/{gid}.nc"})
    store.upsert(
        "matchups",
        {
            "matchup_id": matchup_id,
            "profile_id": pid,
            "granule_id": gid,
            "n_spectra": 1,
        },
    )
    store.upsert(
        "matchup_pixels",
        {"matchup_id": matchup_id, "ix": 2, "iy": 2, "rank": 1, "flagged": 0},
    )
    fit_id = f"{matchup_id}_2_2_ExpBPow"
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "algorithm": "BING",
            "model_pair": "ExpBPow",
            "chisq": 1.1,
            "chains_path": chains_path,
            "figure_path": figure_path,
            "pab_version": "0",
        },
    )
    for q, v in (("bbp700", bbp_bing), ("chl", chl_bing)):
        store.upsert(
            "fit_results",
            {
                "fit_id": fit_id,
                "quantity": f"BING_ExpBPow_{q}",
                "value": v,
                "value_lo": v * 0.9,
                "value_hi": v * 1.1,
                "unit": "",
            },
        )
    return fit_id


def _two_matchups(store, **kw):
    _seed(
        store,
        "M1",
        7902226,
        5,
        lat=27.0,
        lon=-46.0,
        time="2025-02-18T20:00:00",
        bbp_argo=1e-3,
        bbp_bing=2e-3,
        **kw,
    )
    _seed(
        store,
        "M2",
        7902136,
        8,
        lat=4.0,
        lon=-137.0,
        time="2025-07-25T13:00:00",
        bbp_argo=2e-3,
        bbp_bing=4e-3,
    )


# -- aggregation ------------------------------------------------------------
def test_aggregate_by_region():
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _two_matchups(store)
        df = compare.add_strata(compare.gather_matchups(store))
        out = aggregate.aggregate_by(df, "region")
        assert set(out["region"]) == {"subtropics", "tropics"}
        # both matchups have bbp_bing = 2x bbp_argo
        assert np.allclose(out["median_ratio"], 2.0)


def test_magnitude_bins():
    labels = aggregate.magnitude_bins([5e-4, 2e-3, 8e-3], edges=(1e-3, 3e-3))
    assert list(labels) == ["low", "mid", "high"]


def test_aggregate_healpix():
    pytest.importorskip("healpy")
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _two_matchups(store)
        df = compare.gather_matchups(store)
        hp = aggregate.aggregate_healpix(df, cell_size_deg=5.0)
        assert len(hp) == 2  # the two floats fall in different cells
        assert {"hpix", "lon", "lat", "n", "median_ratio"} <= set(hp.columns)
        assert (hp["lon"].between(-180, 180)).all()
        assert np.allclose(hp["median_ratio"], 2.0)


# -- rst generation ---------------------------------------------------------
def test_build_site_fixed_pages_no_per_matchup(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path)
        # the fixed page set + the reporting conf.py — never one page per matchup
        assert set(written) == set(rst.PAGE_STEMS) | {"conf"}
        assert len(list(tmp_path.glob("*.rst"))) == len(rst.PAGE_STEMS)
        assert (tmp_path / "conf.py").exists()  # separate, buildable Sphinx target
        summary = written["summary"].read_text()
        assert "Matchups:" in summary and "median sat/float ratio" in summary
        # static fallback (no bokeh) -> a list-table is still emitted
        assert "list-table" in rst.aggregates_page(store, sortable=False)


def test_build_site_without_healpy(tmp_path, monkeypatch):
    # lean env (no healpy/remote_sensing): the HEALPix table degrades gracefully,
    # the rest of the site still builds. (Regression for the CI failure.)
    def _raise(*a, **k):
        raise ModuleNotFoundError("No module named 'healpy'")

    monkeypatch.setattr(aggregate, "aggregate_healpix", _raise)
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path, sortable=False)
        assert set(written) == set(rst.PAGE_STEMS) | {"conf"}
        agg_text = written["aggregates"].read_text()
        assert "HEALPix aggregation requires" in agg_text  # degraded, not crashed
        assert "By region" in agg_text  # the flat bins still rendered


def test_build_site_sortable_tables_when_bokeh(tmp_path):
    pytest.importorskip("bokeh")
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path)  # sortable=True (default)
        agg_text = written["aggregates"].read_text()
        assert (
            ".. raw:: html" in agg_text
        )  # embedded sortable DataTable, not list-table


def test_reporting_site_builds(tmp_path):
    pytest.importorskip("sphinx")
    import subprocess
    import sys

    with Store.open(":memory:") as store:
        _two_matchups(store)
        rst.build_site(store, tmp_path, sortable=False)  # static tables -> fast build
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "html",
            str(tmp_path),
            str(tmp_path / "_build"),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr[-2000:]
    assert (tmp_path / "_build" / "summary.html").exists()


def test_stats_table_is_sortable():
    pytest.importorskip("bokeh")
    import pandas as pd

    from pab.report import interactive

    table = interactive.stats_table(pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]}))
    assert table.sortable and all(col.sortable for col in table.columns)


def test_rst_table_renders():
    import pandas as pd

    out = rst.rst_table(pd.DataFrame({"a": [1, 2], "b": [0.123456, np.nan]}))
    assert ".. list-table::" in out and ":header-rows: 1" in out
    assert "0.123" in out and "—" in out  # float fmt + NaN placeholder


def test_build_site_embeds_figures_and_copies_them(tmp_path):
    pytest.importorskip("bokeh")
    fig = tmp_path / "M1_fit.png"
    fig.write_bytes(b"fake-png")
    with Store.open(":memory:") as store:
        _seed(
            store,
            "M1",
            7902226,
            5,
            lat=27.0,
            lon=-46.0,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            bbp_bing=2e-3,
            figure_path=str(fig),
        )
        site = tmp_path / "site"
        rst.build_site(store, site)  # sortable=True -> interactive figures
        summary = (site / "summary.rst").read_text()
        # the interactive scatter/map are embedded on the landing page
        assert "Figures" in summary and ".. raw:: html" in summary
        # the per-matchup figure was copied into the static tree and linked
        copied = site / "_static" / "figures" / "M1_fit.png"
        assert copied.exists()
        assert "_static/figures/M1_fit.png" in summary  # gallery + tap-to-open URL
        # conf serves the static tree
        assert 'html_static_path = ["_static"]' in (site / "conf.py").read_text()


def test_build_site_embeds_chl_scatter(tmp_path):
    pytest.importorskip("bokeh")
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path)  # sortable=True default
        summary = written["summary"].read_text()
        # both the b_bp and the Chl scatter are embedded on the landing page
        assert "satellite vs in-situ b_bp" in summary
        assert "satellite vs in-situ Chl" in summary


def test_comparison_scatter_oc4_overlay():
    pytest.importorskip("bokeh")
    from pab.metrics import compare
    from pab.report import interactive

    with Store.open(":memory:") as store:
        _two_matchups(store)
        df = compare.gather_matchups(store)
        df = df.copy()
        df["chl_oc"] = df["chla_argo"] * 1.1  # a synthetic OC4 cross-check series
        fig = interactive.comparison_scatter(
            df,
            sat_col="chl_bing",
            insitu_col="chla_argo",
            label="Chl",
            extra_series=[("chl_oc", "OC4 band-ratio Chl")],
        )
        script, _ = interactive.embed(fig)
        assert "OC4 band-ratio Chl" in script  # the overlay legend is present


def test_argo_qa_gallery_copies_and_links(tmp_path):
    qa = tmp_path / "qa_src.png"
    qa.write_bytes(b"fake-png")
    with Store.open(":memory:") as store:
        _two_matchups(store)
        store.execute(
            "UPDATE mld_summary SET qa_path = ? WHERE profile_id = "
            "(SELECT profile_id FROM profiles WHERE wmo = 7902226)",
            (str(qa),),
        )
        site = tmp_path / "site"
        out = rst.argo_qa_gallery(store, site)
        assert "Argo profile Q&A" in out and "_static/argo_qa/" in out
        assert (site / "_static" / "argo_qa" / "qa_src.png").exists()


def test_argo_qa_gallery_empty_without_paths():
    with Store.open(":memory:") as store:
        _two_matchups(store)  # no qa_path set
        assert rst.argo_qa_gallery(store, "unused") == ""


def test_figure_gallery_guarded_above_threshold():
    import pandas as pd

    df = pd.DataFrame(
        {
            "wmo": [1, 2, 3],
            "cycle": [1, 2, 3],
            rst.FIGURE_URL_COL: ["_static/figures/a.png"] * 3,
        }
    )
    # small N -> inline thumbnails
    assert "<img" in rst.figure_gallery(df, max_inline=50)
    # above threshold -> suppressed with a downloads note, no <img>
    out = rst.figure_gallery(df, max_inline=2)
    assert "too many to show inline" in out and "<img" not in out


# -- interactive (bokeh) ----------------------------------------------------
def test_comparison_scatter_embed():
    pytest.importorskip("bokeh")
    from pab.metrics import compare
    from pab.report import interactive

    with Store.open(":memory:") as store:
        _two_matchups(store)
        df = compare.gather_matchups(store)
        fig = interactive.comparison_scatter(df)
        script, div = interactive.embed(fig)
        assert script.strip().startswith("<script") and div.strip().startswith("<div")
        assert ".. raw:: html" in interactive.raw_html(fig)


# -- publish / manifest -----------------------------------------------------
def test_export_tables_roundtrip(tmp_path):
    import pandas as pd

    with Store.open(":memory:") as store:
        _two_matchups(store)
        out = publish.export_tables(store, tmp_path)
        assert out["summary_csv"].exists()
        back = pd.read_csv(out["summary_csv"])
        assert len(back) == 2 and {"bbp_bing", "bbp_argo"} <= set(back.columns)


def test_build_manifest_and_stub_upload(tmp_path):
    chains = tmp_path / "M1.npz"
    chains.write_bytes(b"fake-npz")
    fig = tmp_path / "M1.png"
    fig.write_bytes(b"fake-png")
    with Store.open(":memory:") as store:
        _seed(
            store,
            "M1",
            7902226,
            5,
            lat=27.0,
            lon=-46.0,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            bbp_bing=2e-3,
            chains_path=str(chains),
            figure_path=str(fig),
        )
        manifest = publish.build_manifest(store, base_url="https://store.example/pab")
        kinds = sorted(r["kind"] for r in manifest)
        assert kinds == ["chains", "figure"]
        for r in manifest:
            assert r["matchup_id"] == "M1"
            assert r["url"].startswith("https://store.example/pab/")
            assert r["checksum"] and len(r["checksum"]) == 16
            assert r["pab_version"]

        backend = publish.LocalStubBackend(tmp_path / "store")
        url = backend.upload(chains)
        assert (tmp_path / "store" / "M1.npz").exists()
        assert backend.uploaded == [(str(chains), url)]  # recorded; no network


def test_publish_release_local(tmp_path):
    chains = tmp_path / "M1.npz"
    chains.write_bytes(b"fake")
    with Store.open(":memory:") as store:
        _seed(
            store,
            "M1",
            7902226,
            5,
            lat=27.0,
            lon=-46.0,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            bbp_bing=2e-3,
            chains_path=str(chains),
        )
        res = publish.publish_release(store, tmp_path / "rel")
        assert res["manifest_path"].exists()
        assert res["n_uploaded"] == 1  # the one existing artifact
        assert res["pkg_versions"]["pab"]


def test_real_backends_are_deferred():
    with pytest.raises(NotImplementedError):
        publish.NautilusS3Backend()
    with pytest.raises(NotImplementedError):
        publish.ZenodoBackend()
