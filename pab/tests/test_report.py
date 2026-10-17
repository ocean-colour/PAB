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
        assert "suppressed at this scale" in out
        assert ".. raw:: html" not in out  # no multi-MB inline Bokeh embed


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
        assert "0.0 % of the slopes sit at the ceiling" in methods
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
