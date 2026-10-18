"""Stage 7 tests: the reporting layer (``pab.report``)."""

import numpy as np
import pytest

from pab.argo.summary import persist_summary
from pab.db import Store
from pab.plotting import population
from pab.report import aggregate, publish, rst


@pytest.fixture(autouse=True)
def _plain_maps(monkeypatch):
    """Every map a report test renders uses plain lon/lat axes: no cartopy,
    no Natural Earth download, so the suite never touches the network."""
    monkeypatch.setattr(population, "MAP_PROJECTION", None)


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


def test_aggregate_healpix_tolerates_retracted_positions():
    # An Argo delayed-mode refresh can NULL a matched profile's lat/lon
    # (seen in production: float 2903938); healpy must not be handed NaN.
    pytest.importorskip("healpy")
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _two_matchups(store)
        store.execute(
            "UPDATE profiles SET latitude = NULL, longitude = NULL WHERE wmo = ?",
            (7902226,),
        )
        df = compare.gather_matchups(store)
        hp = aggregate.aggregate_healpix(df, cell_size_deg=5.0)
        assert len(hp) == 1  # the unpositioned matchup is dropped, not fatal
        assert int(hp["n"].iloc[0]) == 1


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
        # interactive scatter/map live on the Comparisons page
        assert ".. raw:: html" in (site / "comparisons.rst").read_text()
        # the per-matchup figure gallery lives on the Figures page
        figures = (site / "figures.rst").read_text()
        copied = site / "_static" / "figures" / "M1_fit.png"
        assert copied.exists()
        assert "_static/figures/M1_fit.png" in figures  # gallery + tap-to-open URL
        # conf serves the static tree
        assert 'html_static_path = ["_static"]' in (site / "conf.py").read_text()


def test_build_site_embeds_chl_scatter(tmp_path):
    pytest.importorskip("bokeh")
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path)  # sortable=True default
        # both the b_bp and the Chl scatter are on the Comparisons page
        comparisons = written["comparisons"].read_text()
        assert "satellite vs in-situ b_bp" in comparisons
        assert "satellite vs in-situ Chl" in comparisons


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


def test_scene_gallery_copies_and_links(tmp_path):
    scene = tmp_path / "scene_src.png"
    scene.write_bytes(b"fake-png")
    with Store.open(":memory:") as store:
        _two_matchups(store)
        store.execute(
            "UPDATE matchups SET scene_path = ? WHERE matchup_id = 'M1'", (str(scene),)
        )
        site = tmp_path / "site"
        out = rst.scene_gallery(store, site)
        assert "PACE scene quick-looks" in out and "_static/scenes/" in out
        assert (site / "_static" / "scenes" / "scene_src.png").exists()


def test_scene_gallery_empty_without_paths():
    with Store.open(":memory:") as store:
        _two_matchups(store)  # no scene_path set
        assert rst.scene_gallery(store, "unused") == ""


def test_matchup_quality_table():
    with Store.open(":memory:") as store:
        _two_matchups(store)
        out = rst.matchup_quality_table(store, sortable=False)
        assert "Matchup quality" in out
        assert "n_spectra" in out and "distance_km" in out


def test_index_page_has_description_and_toctree():
    out = rst.index_page()
    assert "matchup analyses between PACE" in out  # reader-facing description
    assert "What PAB does" in out and "What's on this site" in out
    # clickable links off the main page to every content sub-page
    for stem in (
        "summary",
        "comparisons",
        "figures",
        "aggregates",
        "methods",
        "downloads",
    ):
        assert f"<{stem}>" in out  # :doc:`Title <stem>` link
    assert ".. toctree::" in out


def test_downloads_page_stages_tables(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        site = tmp_path / "site"
        out = rst.downloads_page(store, site)
        assert "Downloads" in out
        csv = site / "_static" / "downloads" / "matchup_summary.csv"
        assert csv.exists()
        assert "_static/downloads/matchup_summary.csv" in out
        assert "Nautilus S3" in out  # bulky artifacts noted as deferred


def test_downloads_page_links_s3_and_stages_nothing(tmp_path):
    # At scale: link the tables at an S3 URL prefix instead of committing them.
    with Store.open(":memory:") as store:
        _two_matchups(store)
        site = tmp_path / "site"
        base = "https://s3-west.nrp-nautilus.io/pab/full"
        out = rst.downloads_page(store, site, downloads_base_url=base)
        assert f'href="{base}/matchup_summary.csv"' in out
        assert f'href="{base}/matchup_summary.parquet"' in out
        # no NASA-GIOP ingest -> no link to a table that would not exist
        assert "nasa_giop_summary" not in out
        # nothing staged into the committed tree
        assert not (site / "_static" / "downloads").exists()
        assert "_static/downloads/" not in out
        # with an ingest the NASA-GIOP table is linked at the same prefix
        _seed_nasa_giop(store, "M1")
        out = rst.downloads_page(store, site, downloads_base_url=base)
        assert f'href="{base}/nasa_giop_summary.csv"' in out
        assert f'href="{base}/nasa_giop_summary.parquet"' in out
        assert not (site / "_static" / "downloads").exists()


def test_comparisons_page_static_figures_at_scale(tmp_path):
    # Above max_interactive the page renders static PNGs, not a giant Bokeh embed.
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _two_matchups(store)
        df = compare.gather_matchups(store)
        out = rst.comparisons_page(df, outdir=tmp_path, max_interactive=1)
        assert ".. figure:: _static/comparisons/bbp_scatter.png" in out
        assert (tmp_path / "_static" / "comparisons" / "bbp_scatter.png").is_file()
        assert ".. figure:: _static/comparisons/chl_scatter.png" in out
        assert "suppressed at this scale" in out
        assert ".. raw:: html" not in out  # no multi-MB inline Bokeh embed
        # the density-panel captions: what is drawn, and the off-scale count
        assert out.count("Filled cells where ≥ 5 matchups fall in a cell") == 2
        assert "0 matchups lie outside the axes and are counted in the statistics" in out
        # the two maps, with captions stating the clip and the ≥ 5 rule
        for name in ("matchup_map.png", "healpix_map.png"):
            assert f".. figure:: _static/comparisons/{name}" in out
            assert (tmp_path / "_static" / "comparisons" / name).is_file()
        # Q&A/v2 Edits 5 = B: a fixed ±0.5 dex clip, with the saturated count
        assert out.count("clipped at a fixed ±0.5 dex (a factor of 3.2 either way)") == 2
        assert "at or beyond ±0.5 dex saturate to the end colours" in out
        assert "only cells holding ≥ 5 matchups are drawn" in out
        assert "(0 cells, 0 matchups; 2 sparser cells left out)" in out
        assert "saturated (median at or beyond ±0.5 dex): 0 of the 0 drawn cells" in out


def test_comparisons_captions_quote_the_offscale_count(tmp_path):
    import pandas as pd

    rng = np.random.default_rng(1)
    # log-uniform, so the 99 % clip (padded x0.7 / x1.4) covers every value
    # and only the injected runaways are off-scale
    insitu = 10 ** rng.uniform(-3.5, -2.5, 400)
    df = pd.DataFrame(
        {
            "bbp_bing": insitu * 1.2,
            "bbp_argo": insitu,
            "chl_bing": insitu * 100,
            "chla_argo": insitu * 90,
            "latitude": rng.uniform(-60, 60, 400),
            "longitude": rng.uniform(-180, 180, 400),
        }
    )
    df.loc[[0, 1, 2], "bbp_bing"] = 1e4  # three non-physical runaways
    out = rst.comparisons_page(df, outdir=tmp_path, max_interactive=1)
    # The gate (O3, Q&A/Outliers 1 = B): the three runaways are excluded from
    # the b_bp panel, so nothing is off-scale on either panel, and the b_bp
    # captions (panel, dot map, HEALPix map) all carry the computed count.
    assert out.count("0 matchups lie outside the axes and are counted") == 2
    assert "3 matchups lie outside the axes" not in out
    gate = "3 failed retrievals (0.75 %, ``b_bp`` > 1 m⁻¹) excluded"
    assert out.count(gate) == 3
    # the maps' shared colour clip is a fixed ±0.5 dex (Q&A/v2 Edits 5 = B);
    # with the runaways gated no matchup saturates (every other ratio is 1.2,
    # i.e. 0.08 dex), the 397 with a ratio are counted, and the three gated
    # matchups are the grey "without a ratio" dots
    assert out.count("clipped at a fixed ±0.5 dex") == 2
    assert (
        "The 0 matchups (0.0 % of the 397 with a ratio) at or beyond ±0.5 dex "
        "saturate to the end colours"
    ) in out
    assert "The 3 matchups without a ratio (no float ``b_bp``, or a failed retrieval) are grey" in out
    assert "saturated (median at or beyond ±0.5 dex): 0 of the" in out
    # the 2.0-vs-1.0 panels carry the same caption form, gated on bbp700_v2
    df2 = pd.DataFrame(
        {
            "bbp700_v1": insitu,
            "bbp700_v2": df["bbp_bing"],
            "chl_v1": insitu * 90,
            "chl_v2": insitu * 100,
        }
    )
    out2 = rst._version_static_figures(df2, tmp_path)
    assert ".. figure:: _static/comparisons/v2_vs_v1_bbp700.png" in out2
    assert ".. figure:: _static/comparisons/v2_vs_v1_chl.png" in out2
    assert out2.count("0 matchups lie outside the axes and are counted") == 2
    assert out2.count(gate) == 1  # the b_bp panel only; the Chl panel is not gated
    assert out2.count("Filled cells where ≥ 5 matchups fall in a cell") == 2
    for name in ("v2_vs_v1_bbp700.png", "v2_vs_v1_chl.png"):
        assert (tmp_path / "_static" / "comparisons" / name).is_file()


#: ``(442/700) ** 1`` — the 700 nm shift factor for a seeded slope of 1.0.
_SHIFT_1 = 442.0 / 700.0


def _seed_nasa_giop(store, matchup_id, *, bbp_442=3e-3, bbp_s=1.0):
    """Add the parallel NASA_GIOP sibling fit + namespaced results (the
    ``pab.fit.nasa_giop`` shape, slope included) for an already-seeded
    matchup. ``bbp_s=None`` seeds no slope row (the null-slope path)."""
    fit_id = f"{matchup_id}_2_2_NASA_GIOP"
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "algorithm": "NASA_GIOP",
            "model_pair": None,
            "pab_version": "1.1",
        },
    )
    for q, v in (("bbp_442", bbp_442), ("adg_442", 0.007), ("aph_442", 0.013)):
        store.upsert(
            "fit_results",
            {
                "fit_id": fit_id,
                "quantity": f"NASA_GIOP_{q}",
                "value": v,
                "value_lo": v * 0.9,
                "value_hi": v * 1.1,
                "unit": "m^-1",
            },
        )
    if bbp_s is not None:
        store.upsert(
            "fit_results",
            {
                "fit_id": fit_id,
                "quantity": "NASA_GIOP_bbp_s",
                "value": bbp_s,
                "value_lo": None,
                "value_hi": None,
                "unit": "",
            },
        )
    return fit_id


def test_nasa_giop_section_stats_and_caveat():
    pytest.importorskip("bokeh")
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _two_matchups(store)
        _seed_nasa_giop(store, "M1", bbp_442=3e-3, bbp_s=2.0)  # at GIOP's ceiling
        _seed_nasa_giop(store, "M2", bbp_442=6e-3, bbp_s=1.0)
        out = rst.nasa_giop_section(store)
        assert "BING vs NASA GIOP" in out
        # the comparison is at 700 nm on both sides, with the formula stated
        assert "700 nm" in out and "no spectral adjustment" not in out
        assert "as-is" not in out
        assert compare.GIOP_BBP_SHIFT_FORMULA in out
        assert "median NASA(700)/BING(700)" in out
        # the stats are those of the 700 nm column: ratios 1.5*(442/700)**2
        # and 1.5*(442/700) -> the median is their mean
        df = compare.gather_nasa_giop(store)
        stats = compare.log_comparison(df["bbp_700_nasa"], df["bbp_bing"])
        r1, r2 = 1.5 * _SHIFT_1**2, 1.5 * _SHIFT_1
        assert stats["median_ratio"] == pytest.approx((r1 + r2) / 2)
        assert "n = 2" in out and rst._fmt(stats["median_ratio"]) in out
        # the computed ceiling fraction (one of two slopes at 2.0) ...
        assert "50.0 % of the 2 slopes" in out
        assert "least constrained" in out
        # ... and the unadjusted 442-vs-700 ratio (1.5) quoted once for continuity
        assert "unadjusted median NASA(442)/BING(700) ratio on the same matchups is 1.5" in out
        assert out.count("continuity with the previous release") == 1
        # the interactive Bokeh embed is present below the interactive cap
        assert ".. raw:: html" in out


def test_nasa_giop_section_null_slope_is_nan_not_default():
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _two_matchups(store)
        _seed_nasa_giop(store, "M1", bbp_442=3e-3, bbp_s=1.0)
        _seed_nasa_giop(store, "M2", bbp_442=6e-3, bbp_s=None)  # no slope row
        df = compare.gather_nasa_giop(store)
        by_id = df.set_index("matchup_id")
        assert by_id.loc["M1", "bbp_700_nasa"] == pytest.approx(3e-3 * _SHIFT_1)
        assert np.isnan(by_id.loc["M2", "bbp_700_nasa"])
        # the section's stats drop the NaN pair: n = 1, not 2
        out = rst.nasa_giop_section(store, sortable=False)
        assert "n = 1;" in out
        assert "0.0 % of the 1 slopes" in out


def test_nasa_giop_section_empty_without_ingest():
    with Store.open(":memory:") as store:
        _two_matchups(store)  # BING fits only, no NASA_GIOP rows
        assert rst.nasa_giop_section(store) == ""


def test_nasa_giop_section_static_at_scale(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        _seed_nasa_giop(store, "M1")
        _seed_nasa_giop(store, "M2")
        out = rst.nasa_giop_section(store, outdir=tmp_path, max_interactive=1)
        assert ".. figure:: _static/comparisons/nasa_giop_bbp_scatter.png" in out
        png = tmp_path / "_static" / "comparisons" / "nasa_giop_bbp_scatter.png"
        assert png.is_file()
        assert "shifted to 700 nm" in out and "no spectral adjustment" not in out
        assert ".. raw:: html" not in out  # no giant Bokeh embed at scale
        # the density-panel caption
        assert "Filled cells where ≥ 5 matchups fall in a cell" in out
        assert "0 matchups lie outside the axes and are counted in the statistics" in out


def test_build_site_includes_nasa_giop_everywhere(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        _seed_nasa_giop(store, "M1")
        _seed_nasa_giop(store, "M2")
        written = rst.build_site(store, tmp_path, sortable=False)
        assert "BING vs NASA GIOP" in written["comparisons"].read_text()
        summary = written["summary"].read_text()
        assert "BING vs NASA GIOP (b_bp)" in summary
        assert "median NASA(700 nm)/BING(700 nm)" in summary
        # the parallel NASA_GIOP fits rows must not inflate the BING fit count
        assert "**BING fits:** 2" in summary
        methods = written["methods"].read_text()
        assert "GSM" in methods and "GIOP" in methods
        assert 'pab_version = "1.1"' in methods
        # Methods carries the formula + the computed ceiling fraction, and no
        # trace of the old "not spectrally adjusted" stance
        from pab.metrics import compare

        assert compare.GIOP_BBP_SHIFT_FORMULA in methods
        assert "0.0 % of the slopes sit at that ceiling" in methods
        assert "not** spectrally adjusted" not in methods
        assert "no spectral adjustment" not in methods
        # the NASA-GIOP table is staged and linked next to the matchup summary
        downloads = written["downloads"].read_text()
        assert "_static/downloads/nasa_giop_summary.csv" in downloads
        assert (tmp_path / "_static" / "downloads" / "nasa_giop_summary.csv").is_file()


def test_methods_page_without_store_defers_ceiling_fraction():
    out = rst.methods_page()
    assert "Comparisons* page reports the fraction" in out
    assert "least constrained" in out
    assert "not** spectrally adjusted" not in out


def test_build_site_no_nasa_giop_section_without_ingest(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path, sortable=False)
        assert "BING vs NASA GIOP" not in written["comparisons"].read_text()
        assert "BING vs NASA GIOP (b_bp)" not in written["summary"].read_text()


def test_provenance_block_lists_versions():
    out = rst.provenance_block(pab_version="9.9.test")
    assert "Provenance" in out
    assert "9.9.test" in out
    assert "pab" in out and "version" in out  # the package-versions table


def test_build_site_methods_has_provenance(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        written = rst.build_site(store, tmp_path, sortable=False)
        methods = written["methods"].read_text()
        assert "Provenance" in methods and "Methods" in methods


def test_summary_coverage_stats(tmp_path):
    with Store.open(":memory:") as store:
        _two_matchups(store)
        # give the matchups a separation so the medians render
        store.execute("UPDATE matchups SET distance_km = 0.5, dtime_hours = 3.0")
        summary = rst.summary_page(store)
        assert "Profiles ingested:" in summary
        assert "Median separation:" in summary and "Median Δtime:" in summary


def _one_runaway(store):
    """M1 a sound fit, M2 a runaway (b_bp 5e4 m^-1) -- the O3 gate fixture."""
    _seed(
        store, "M1", 7902226, 5, lat=27.0, lon=-46.0, time="2025-02-18T20:00:00",
        bbp_argo=1e-3, bbp_bing=2e-3, chla=0.1, chl_bing=0.15,
    )
    _seed(
        store, "M2", 7902136, 8, lat=4.0, lon=-137.0, time="2025-07-25T13:00:00",
        bbp_argo=2e-3, bbp_bing=5e4, chla=0.2, chl_bing=0.3,
    )


_GATE_ONE_OF_TWO = "1 failed retrieval (50.00 %, ``b_bp`` > 1 m⁻¹) excluded"
_OUTLIERS_URL = (
    "https://github.com/ocean-colour/PAB/blob/main/versions/v2/high_bbp_outliers.md"
)


def test_summary_headline_is_gated_and_says_so():
    """O3 (Q&A/Outliers 1 = B): the b_bp headline excludes the runaway and
    carries the computed clause; the Chl headline is not gated (6 = A)."""
    with Store.open(":memory:") as store:
        _one_runaway(store)
        out = rst.summary_page(store)
        assert "- n = 1; median sat/float ratio = 2;" in out  # M1 only
        assert _GATE_ONE_OF_TWO in out
        assert "see the :doc:`Methods <methods>` page" in out
        # Chl: both fits, 1.5x each
        assert "- n = 2; median sat/float ratio = 1.5;" in out
        # BING fits counted as fits, not as gated pairs
        assert "**BING fits:** 2" in out


def test_methods_page_failed_retrievals_paragraph():
    with Store.open(":memory:") as store:
        _one_runaway(store)
        out = rst.methods_page(store=store)
        assert "**Failed retrievals.**" in out
        assert "above 1 m⁻¹" in out
        assert f"In this release that is {_GATE_ONE_OF_TWO}." in out
        assert "``bbp_bing_implausible``" in out
        assert _OUTLIERS_URL in out
        # the paragraph sits with the retrieval description, before 2.0's config
        assert out.index("**Failed retrievals.**") < out.index("Retrieval configuration (2.0)")
    # without a store the count is deferred, never quoted
    out = rst.methods_page()
    assert "**Failed retrievals.**" in out and _OUTLIERS_URL in out
    assert "*Comparisons* page reports how many fits this excludes" in out
    assert "failed retrieval (" not in out


def test_aggregates_come_from_the_gated_frame():
    with Store.open(":memory:") as store:
        _one_runaway(store)
        out = rst.aggregates_page(store, sortable=False)
        assert _GATE_ONE_OF_TWO in out
        # M2 (tropics) is the runaway: its region bin has no pair left, while
        # M1's (subtropics) keeps its ratio of 2
        assert "   * - tropics\n     - 0\n     - —" in out
        assert "   * - subtropics\n     - 1\n     - 2\n" in out


def test_comparisons_page_gates_the_interactive_figures_too():
    """Below `max_interactive` the Bokeh b_bp scatter/map get the gated frame
    (the intro carries the clause); the Chl scatter still has both fits."""
    pytest.importorskip("bokeh")
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _one_runaway(store)
        df = compare.gather_matchups(store)
        out = rst.comparisons_page(df, sortable=True)
        assert f"``b_bp``: {_GATE_ONE_OF_TWO}." in out
        assert ".. raw:: html" in out


def test_export_tables_keep_raw_values_and_add_the_flag(tmp_path):
    import pandas as pd

    with Store.open(":memory:") as store:
        _one_runaway(store)
        out = publish.export_tables(store, tmp_path)
        back = pd.read_csv(out["summary_csv"]).set_index("matchup_id")
        assert back.loc["M2", "bbp_bing"] == 5e4  # raw, not NaN
        assert back.loc["M1", "bbp_bing"] == 2e-3
        assert list(back["bbp_bing_implausible"]) == [0, 1]
        if "summary_parquet" in out:
            pq = pd.read_parquet(out["summary_parquet"]).set_index("matchup_id")
            assert pq.loc["M2", "bbp_bing"] == 5e4
            assert list(pq["bbp_bing_implausible"]) == [0, 1]


def test_gallery_selection_is_not_gated():
    """The representative gallery keeps its "non-physical retrieval" pick: it
    is built from the raw frame (the whole point of the slot)."""
    from pab.metrics import compare

    with Store.open(":memory:") as store:
        _one_runaway(store)
        df = compare.gather_matchups(store)
        # on two rows the runaway is already the 95th-percentile pick (the
        # "non-physical" reason de-duplicates away); what matters is that it
        # is selectable from the raw frame and would not be from the gated one
        assert "M2" in set(rst.select_representative_fits(df)["matchup_id"])
        gated, _ = compare.gate_bbp(df)
        assert "M2" not in set(rst.select_representative_fits(gated)["matchup_id"])
    # and the old import location still works
    assert rst.BBP_IMPLAUSIBLE == compare.BBP_IMPLAUSIBLE == 1.0


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


# -- representative galleries (E5) -------------------------------------------
def _synthetic_frame(n=300, *, runaway=True, seed=0):
    """A comparison frame with a log-normal sat/float ratio and a Chl range."""
    import pandas as pd

    rng = np.random.default_rng(seed)
    bbp_argo = 10 ** rng.uniform(-3.5, -2.0, n)
    ratio = 10 ** rng.normal(0.0, 0.3, n)
    bbp_bing = bbp_argo * ratio
    chl = 10 ** rng.uniform(-2, 0.5, n)
    if runaway:
        bbp_bing[7] = 2.0e3  # the largest runaway
        bbp_bing[11] = 5.0  # a smaller one
    df = pd.DataFrame(
        {
            "matchup_id": [f"M{i:04d}" for i in range(n)],
            "fit_id": [f"M{i:04d}_fit" for i in range(n)],
            "wmo": 7900000 + np.arange(n),
            "cycle": np.arange(n) % 50,
            "latitude": rng.uniform(-70, 70, n),
            "longitude": rng.uniform(-180, 180, n),
            "time": "2025-03-01T00:00:00",
            "bbp_argo": bbp_argo,
            "bbp_bing": bbp_bing,
            "chl_bing": chl,
        }
    )
    # a few unusable pairs: must be ignored, not selected
    df.loc[0, "bbp_argo"] = np.nan
    df.loc[1, "bbp_argo"] = 0.0
    return df


def test_select_representative_fits_is_deterministic_with_reasons():
    df = _synthetic_frame()
    sel = rst.select_representative_fits(df)
    assert len(sel) == 8
    reasons = list(sel["reason"])
    assert [r.split(" ")[0] for r in reasons[:5]] == ["5th", "25th", "50th", "75th", "95th"]
    assert all("percentile of sat/float b_bp, ratio" in r for r in reasons[:5])
    assert reasons[5].startswith("non-physical retrieval, b_bp = 2.0e3 m⁻¹")
    assert sel.iloc[5]["matchup_id"] == "M0007"  # the largest runaway, not M0011
    assert reasons[6].startswith("clearest tercile, Chl ")
    assert reasons[7].startswith("most productive tercile, Chl ")
    # captions are "WMO/cycle — reason"
    for _, r in sel.iterrows():
        assert r["caption"] == f"{r['wmo']}/{r['cycle']} — {r['reason']}"
    # the percentile picks bracket the population in order; the unusable rows
    # are never chosen
    lr = sel["log_ratio"].to_numpy()[:5]
    assert np.all(np.diff(lr) > 0)
    assert not {"M0000", "M0001"} & set(sel["matchup_id"])
    # the clearest pick is in the clearest tercile and the productive one in the top
    lo, hi = np.percentile(df["chl_bing"][2:], [100 / 3, 200 / 3])
    assert sel.iloc[6]["chl_bing"] < lo and sel.iloc[7]["chl_bing"] >= hi
    # deterministic: the same rows in the same order, whatever the input order
    again = rst.select_representative_fits(df.sample(frac=1, random_state=3))
    assert list(again["matchup_id"]) == list(sel["matchup_id"])
    assert list(again["reason"]) == reasons


def test_select_representative_fits_without_runaway_and_dedup():
    sel = rst.select_representative_fits(_synthetic_frame(runaway=False))
    assert len(sel) == 7
    assert not any(r.startswith("non-physical") for r in sel["reason"])
    # a tiny population collapses onto the same rows: de-duplicated, order kept
    tiny = _synthetic_frame(n=4, runaway=False).iloc[2:]
    sel = rst.select_representative_fits(tiny)
    assert len(sel) == len(set(sel["matchup_id"])) <= 2
    assert sel.iloc[0]["reason"].startswith("5th percentile")
    # ties go to the smallest matchup_id (identical ratios everywhere)
    import pandas as pd

    same = pd.DataFrame(
        {
            "matchup_id": ["M3", "M1", "M2"],
            "wmo": [3, 1, 2],
            "cycle": [1, 1, 1],
            "bbp_argo": [1e-3] * 3,
            "bbp_bing": [2e-3] * 3,
            "chl_bing": [0.1, 0.1, 0.1],
        }
    )
    assert list(rst.select_representative_fits(same)["matchup_id"]) == ["M1"]
    # empty in, empty out (with the documented columns)
    empty = rst.select_representative_fits(same.iloc[:0])
    assert len(empty) == 0 and {"reason", "caption"} <= set(empty.columns)


def test_select_representative_scenes_one_per_region():
    from pab.metrics import compare

    df = compare.add_strata(_synthetic_frame())
    sel = rst.select_representative_scenes(df)
    regions = list(sel["region"])
    assert len(regions) == len(set(regions)) == 4  # one per latitude band
    usable = df[np.isfinite(df["bbp_argo"]) & (df["bbp_argo"] > 0)]
    counts = usable["region"].value_counts()  # the pairs the medians are over
    assert regions == sorted(regions, key=lambda r: (-counts[r], r))  # most populous first
    for _, r in sel.iterrows():
        assert r["reason"].startswith(f"{r['region']} band, nearest its median")
        assert f"(n={counts[r['region']]:,})" in r["reason"]
    assert len(rst.select_representative_scenes(df, max_regions=2)) == 2
    # the pick is the one nearest its band's median log-ratio
    tropics = df[(df["region"] == "tropics") & np.isfinite(df["bbp_argo"])]
    tropics = tropics[tropics["bbp_argo"] > 0]
    lr = np.log10(tropics["bbp_bing"] / tropics["bbp_argo"])
    nearest = tropics["matchup_id"].iloc[int(np.argmin(np.abs(lr - np.median(lr))))]
    assert sel[sel["region"] == "tropics"]["matchup_id"].iloc[0] == nearest


def test_figure_root_remap_resolves_prefix_and_drops_missing(tmp_path):
    roots = {
        "/data": str(tmp_path / "all"),
        "/data/v2/pipeline/figures/": str(tmp_path / "v2figs"),  # longest wins
    }
    src = "/data/v2/pipeline/figures/M1_fit.png"
    assert rst.remap_figure_path(src, roots) == str(tmp_path / "v2figs" / "M1_fit.png")
    assert rst.remap_figure_path("/data/v1/pipeline/figures/s.png", roots) == str(
        tmp_path / "all" / "v1" / "pipeline" / "figures" / "s.png"
    )
    # a prefix matches whole components only, and no match leaves the path alone
    assert rst.remap_figure_path("/data/v2/pipeline/figures_old/x.png", roots) == str(
        tmp_path / "all" / "v2" / "pipeline" / "figures_old" / "x.png"
    )
    assert rst.remap_figure_path("/elsewhere/x.png", roots) == "/elsewhere/x.png"
    assert rst.remap_figure_path(src, None) == src
    # staging resolves through the remap …
    (tmp_path / "v2figs").mkdir()
    (tmp_path / "v2figs" / "M1_fit.png").write_bytes(b"fake-png")
    site = tmp_path / "site"
    url = rst._stage_static(src, site, "figures", figure_roots=roots)
    assert url == "_static/figures/M1_fit.png"
    assert (site / "_static" / "figures" / "M1_fit.png").read_bytes() == b"fake-png"
    # … and a file that is still missing (even under a nonexistent root) is dropped
    assert rst._stage_static("/data/v2/pipeline/figures/M2_fit.png", site, "figures", figure_roots=roots) is None
    missing_root = {"/data/v2/pipeline/argo_qa": str(tmp_path / "does-not-exist")}
    assert rst._stage_static("/data/v2/pipeline/argo_qa/1_2.png", site, "argo_qa", figure_roots=missing_root) is None
    assert rst._stage_static(None, site, "figures", figure_roots=roots) is None


def test_stage_static_downscales_large_images(tmp_path):
    from PIL import Image

    big = tmp_path / "big_fit.png"
    Image.new("RGBA", (3000, 1500), (10, 20, 30, 255)).save(big)
    small = tmp_path / "small_fit.png"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(small)
    site = tmp_path / "site"
    url = rst._stage_static(str(big), site, "figures")
    assert url == "_static/figures/big_fit.png"
    with Image.open(site / url) as im:
        assert im.size == (rst.GALLERY_MAX_SIDE, rst.GALLERY_MAX_SIDE // 2)
    staged = site / "_static" / "figures" / "big_fit.png"
    assert staged.stat().st_size < big.stat().st_size
    # already small enough: copied verbatim
    rst._stage_static(str(small), site, "figures")
    assert (site / "_static" / "figures" / "small_fit.png").read_bytes() == small.read_bytes()
    # max_side=None switches the downscale off
    rst._stage_static(str(big), site, "raw", max_side=None)
    assert (site / "_static" / "raw" / "big_fit.png").read_bytes() == big.read_bytes()


def _seed_population(store, tmp_path, n):
    """``n`` matchups spanning a range of ratios, each with a fit figure, a
    scene and a Q&A plot on disk (stub bytes) — enough to exceed a small
    ``MAX_INLINE_FIGURES``."""
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    for i in range(n):
        fit_id = _seed(
            store,
            f"M{i:03d}",
            7900000 + i,
            i,
            lat=-60 + 120 * i / max(n - 1, 1),
            lon=-100 + i,
            time="2025-02-18T20:00:00",
            bbp_argo=1e-3,
            bbp_bing=1e-3 * 10 ** (-0.6 + 1.2 * i / max(n - 1, 1)),
            chl_bing=0.01 * 10 ** (2 * i / max(n - 1, 1)),
            figure_path=str(src / f"M{i:03d}_fit.png"),
        )
        for name in (f"M{i:03d}_fit.png", f"M{i:03d}_scene.png", f"M{i:03d}_qa.png"):
            (src / name).write_bytes(b"png")
        store.execute(
            "UPDATE matchups SET scene_path = ? WHERE matchup_id = ?",
            (str(src / f"M{i:03d}_scene.png"), f"M{i:03d}"),
        )
        store.execute(
            "UPDATE mld_summary SET qa_path = ? WHERE profile_id = "
            "(SELECT profile_id FROM matchups WHERE matchup_id = ?)",
            (str(src / f"M{i:03d}_qa.png"), f"M{i:03d}"),
        )
        assert fit_id
    return src


def test_figures_page_above_max_inline_shows_only_the_selection(tmp_path, monkeypatch, caplog):
    import logging
    import re

    monkeypatch.setattr(rst, "MAX_INLINE_FIGURES", 5)
    monkeypatch.setattr(rst, "MAX_INTERACTIVE_MATCHUPS", 5)
    site = tmp_path / "site"
    with Store.open(":memory:") as store:
        src = _seed_population(store, tmp_path, 12)
        # one selected Q&A plot is missing on disk: dropped with a counted warning
        df = rst._gather_with_figures(store, site)
        fits = rst.select_representative_fits(df)
        scenes = rst.select_representative_scenes(df)
        assert 5 <= len(fits) <= 8 and 1 <= len(scenes) <= rst.MAX_SCENE_REGIONS
        gone = fits["matchup_id"].iloc[2]
        (src / f"{gone}_qa.png").unlink()
        with caplog.at_level(logging.WARNING, logger="pab.report"):
            page = rst.figures_page(store, site, df)
    # exactly the selected thumbnails, with their reasons, in each gallery
    imgs = re.findall(r'<img src="([^"]+)"', page)
    assert len(imgs) == len(fits) + len(scenes) + len(fits) - 1
    assert [u for u in imgs if "_static/figures/" in u] == [
        f"_static/figures/{m}_fit.png" for m in fits["matchup_id"]
    ]
    assert [u for u in imgs if "_static/scenes/" in u] == [
        f"_static/scenes/{m}_scene.png" for m in scenes["matchup_id"]
    ]
    assert [u for u in imgs if "_static/argo_qa/" in u] == [
        f"_static/argo_qa/{m}_qa.png" for m in fits["matchup_id"] if m != gone
    ]
    for cap in list(fits["caption"]) + list(scenes["caption"]):
        assert f"<figcaption>{cap}</figcaption>" in page
    assert "12 matchups — too many to show inline" in page
    assert f"The {len(fits)} below were chosen to span the sat/float agreement" in page
    assert "plus one failed retrieval" not in page  # no runaway in this population
    assert "the clearest and most productive regimes" in page
    assert "one per latitude band" in page
    assert f"The {len(fits) - 1} below are the profiles behind" in page
    assert f"(1 of the {len(fits)} chosen have no file reachable" in page
    # only the selected files were staged, nothing else
    assert sorted(p.name for p in (site / "_static" / "figures").iterdir()) == sorted(
        f"{m}_fit.png" for m in fits["matchup_id"]
    )
    assert len(list((site / "_static" / "scenes").iterdir())) == len(scenes)
    assert len(list((site / "_static" / "argo_qa").iterdir())) == len(fits) - 1
    # one counted warning for the Q&A gallery, none for the others
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "Argo profile Q&A" in warnings[0]
    assert f"1 of {len(fits)} representative files dropped" in warnings[0]


def test_build_site_passes_figure_roots_to_every_gallery(tmp_path, monkeypatch):
    """Stored (in-pod) paths resolve through ``figure_roots`` for fits, scenes
    and Q&A plots alike; nothing is staged for a prefix that has no root."""
    monkeypatch.setattr(rst, "MAX_INLINE_FIGURES", 5)
    monkeypatch.setattr(rst, "MAX_INTERACTIVE_MATCHUPS", 5)
    site = tmp_path / "site"
    with Store.open(":memory:") as store:
        src = _seed_population(store, tmp_path, 8)
        # rewrite every stored path to a pod-style prefix
        store.execute(
            "UPDATE fits SET figure_path = replace(figure_path, ?, '/data/v2/pipeline/figures')",
            (str(src),),
        )
        store.execute(
            "UPDATE matchups SET scene_path = replace(scene_path, ?, '/data/v1/pipeline/figures')",
            (str(src),),
        )
        store.execute(
            "UPDATE mld_summary SET qa_path = replace(qa_path, ?, '/data/full/pipeline/argo_qa')",
            (str(src),),
        )
        roots = {
            "/data/v2/pipeline/figures": str(src),
            "/data/v1/pipeline/figures": str(src),
            "/data/v2/pipeline/argo_qa": str(tmp_path / "absent"),  # tolerated
        }
        written = rst.build_site(store, site, sortable=False, figure_roots=roots)
        page = written["figures"].read_text()
        assert "_static/figures/" in page and "_static/scenes/" in page
        assert "_static/argo_qa/" not in page  # no root for /data/full/…
        assert "too many to show inline" in page
        # without the remap nothing resolves and the old downloads notes remain
        plain = tmp_path / "plain"
        rst.build_site(store, plain, sortable=False)
        assert "<img" not in (plain / "figures.rst").read_text()


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
        # no NASA-GIOP ingest -> no NASA-GIOP table
        assert "nasa_giop_csv" not in out
        assert not (tmp_path / "nasa_giop_summary.csv").exists()


def test_export_tables_writes_nasa_giop_table(tmp_path):
    import pandas as pd

    with Store.open(":memory:") as store:
        _two_matchups(store)
        _seed_nasa_giop(store, "M1", bbp_442=3e-3, bbp_s=1.0)
        _seed_nasa_giop(store, "M2", bbp_442=6e-3, bbp_s=None)
        out = publish.export_tables(store, tmp_path)
        assert out["nasa_giop_csv"] == tmp_path / "nasa_giop_summary.csv"
        back = pd.read_csv(out["nasa_giop_csv"]).set_index("matchup_id")
        assert len(back) == 2
        # the stored 442 nm value, the slope and the derived 700 nm columns all travel
        assert {
            "bbp_442_nasa",
            "bbp_s_nasa",
            "bbp_700_nasa",
            "bbp_700_nasa_lo",
            "bbp_700_nasa_hi",
            "bbp_bing",
        } <= set(back.columns)
        assert back.loc["M1", "bbp_700_nasa"] == pytest.approx(3e-3 * _SHIFT_1)
        assert np.isnan(back.loc["M2", "bbp_700_nasa"])
        if "nasa_giop_parquet" in out:
            assert out["nasa_giop_parquet"].exists()


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


def test_zenodo_backend_is_deferred():
    with pytest.raises(NotImplementedError):
        publish.ZenodoBackend()


class _FakeS3Client:
    """Records upload_file calls so the S3 backend can be tested without a network."""

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    def upload_file(self, filename, bucket, key):
        self.calls.append((filename, bucket, key))


def test_nautilus_s3_backend_uploads_and_returns_public_url(tmp_path):
    art = tmp_path / "M1.npz"
    art.write_bytes(b"fake")
    fake = _FakeS3Client()
    backend = publish.NautilusS3Backend(bucket="pab", prefix="full", client=fake)

    url = backend.upload(art)  # key defaults to the file name
    assert fake.calls == [(str(art), "pab", "full/M1.npz")]
    assert url == "https://s3-west.nrp-nautilus.io/pab/full/M1.npz"
    assert backend.uploaded == [(str(art), url)]

    # explicit key overrides the file name (and a leading slash is tolerated)
    url2 = backend.upload(art, key="/db/pab.db")
    assert fake.calls[-1] == (str(art), "pab", "full/db/pab.db")
    assert url2 == "https://s3-west.nrp-nautilus.io/pab/full/db/pab.db"


def test_publish_release_with_s3_backend_writes_real_urls(tmp_path):
    chains = tmp_path / "M1.npz"
    chains.write_bytes(b"fake")
    fake = _FakeS3Client()
    backend = publish.NautilusS3Backend(bucket="pab", prefix="artifacts", client=fake)
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
        res = publish.publish_release(store, tmp_path / "rel", backend=backend)
        assert res["n_uploaded"] == 1
        urls = [r["url"] for r in res["manifest"] if r["kind"] == "chains"]
        assert urls == ["https://s3-west.nrp-nautilus.io/pab/artifacts/M1.npz"]


# -- the negative-blue QA count (O4) --------------------------------------------
def _record_neg_blue(store, **counts):
    """Seed ``BING_ExpBPow_n_neg_blue`` rows, e.g. ``M1=0, M2=3``."""
    for m, n in counts.items():
        store.upsert(
            "fit_results",
            {
                "fit_id": f"{m}_2_2_ExpBPow",
                "quantity": "BING_ExpBPow_n_neg_blue",
                "value": float(n), "value_lo": float(n), "value_hi": float(n),
                "unit": "bands",
            },
        )


_NEG_BLUE_ONE_OF_TWO = (
    "1 of 2 fitted spectra (50.00 %) have at least one negative band at "
    "400–450 nm (``n_neg_blue`` ≥ 1); 1 of the 1 failed retrieval does."
)


def test_neg_blue_sentence_is_computed_and_omitted_when_unrecorded():
    import pandas as pd

    assert rst._neg_blue_sentence(None) == ""
    assert rst._neg_blue_sentence(pd.DataFrame({"bbp_bing": [1.0]})) == ""
    # the column exists but nothing is recorded (before the backfill): omitted,
    # never "0 of 0"
    df = pd.DataFrame({"n_neg_blue": [np.nan, np.nan], "bbp_bing_implausible": [0, 1]})
    assert rst._neg_blue_sentence(df) == ""
    # a partial backfill counts only the recorded fits
    df = pd.DataFrame(
        {"n_neg_blue": [np.nan, 2.0, 0.0, 1.0], "bbp_bing_implausible": [1, 1, 0, 0]}
    )
    assert rst._neg_blue_sentence(df) == (
        "2 of 3 fitted spectra with the count recorded (66.67 %) have at least "
        "one negative band at 400–450 nm (``n_neg_blue`` ≥ 1); 1 of the 2 "
        "failed retrievals do."
    )
    # without the flag column the second clause is dropped
    df = pd.DataFrame({"n_neg_blue": [0.0, 0.0]})
    assert rst._neg_blue_sentence(df) == (
        "0 of 2 fitted spectra (0.00 %) have at least one negative band at "
        "400–450 nm (``n_neg_blue`` ≥ 1)."
    )


def test_methods_page_defines_n_neg_blue_and_quotes_the_rate_only_when_recorded():
    with Store.open(":memory:") as store:
        _one_runaway(store)
        out = rst.methods_page(store=store)
        assert "**Negative-blue QA count.**" in out
        assert "``BING_ExpBPow_n_neg_blue``" in out and "``n_neg_blue`` column" in out
        assert "between 400 and 450 nm (inclusive)" in out
        assert "a flag, not a screen" in out
        # nothing recorded yet: no rate, and it says so
        assert "no rate is quoted" in out and "fitted spectra (" not in out
        # the paragraph sits with the retrieval description
        assert out.index("**Failed retrievals.**") < out.index("**Negative-blue QA count.**")
        assert out.index("**Negative-blue QA count.**") < out.index("Retrieval configuration (2.0)")

        _record_neg_blue(store, M1=0, M2=3)
        out = rst.methods_page(store=store)
        assert f"In this release {_NEG_BLUE_ONE_OF_TWO}" in out
        assert "no rate is quoted" not in out
    # without a store: the definition, no numbers
    out = rst.methods_page()
    assert "**Negative-blue QA count.**" in out and "fitted spectra (" not in out


def test_export_tables_carry_n_neg_blue(tmp_path):
    import pandas as pd

    with Store.open(":memory:") as store:
        _one_runaway(store)
        _record_neg_blue(store, M2=3)
        out = publish.export_tables(store, tmp_path)
        back = pd.read_csv(out["summary_csv"]).set_index("matchup_id")
        assert back.loc["M2", "n_neg_blue"] == 3.0
        assert np.isnan(back.loc["M1", "n_neg_blue"])  # not recorded, not 0
        if "summary_parquet" in out:
            pq = pd.read_parquet(out["summary_parquet"]).set_index("matchup_id")
            assert pq.loc["M2", "n_neg_blue"] == 3.0 and np.isnan(pq.loc["M1", "n_neg_blue"])
