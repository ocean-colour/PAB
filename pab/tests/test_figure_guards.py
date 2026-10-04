"""The `figure` stage renders only what it can and only what is missing.

Two guards, both measured on the v2 store (15,976 matchups / 31,947 fits):

* the ``fits`` table holds 15,976 NASA-GIOP rows with **no MCMC chains**, so
  rendering a fit figure for one cannot succeed — half the stage would be
  guaranteed failures;
* 14,586 of 15,976 matchups already carry a ``scene_path``, and the scene is
  the half that re-opens the ~1.8 GB granule.

Together they are the difference between the stage doing ~16k renders with
1,390 granule reads and doing ~32k renders with 16k granule reads, half of
them failing.
"""

from __future__ import annotations

from pab.db.store import Store
from pab.pipeline import PipelineConfig, figure


def _seed_fit(store, matchup_id, *, algorithm, version, scene_path=None, wmo=7902226):
    """A matchup + one fit; ``scene_path`` pre-set to simulate a previous run."""
    from pab.argo.summary import persist_summary

    pid = persist_summary(
        store,
        wmo=wmo,
        cycle=int(matchup_id[-1]) if matchup_id[-1].isdigit() else 1,
        summary={"mld": 30.0, "mld_method": "x", "chla": 0.1, "n_points": 6},
        latitude=20.0,
        longitude=-50.0,
        time="2025-05-01T12:00:00",
    )
    gid = f"G_{matchup_id}"
    store.upsert("granules", {"granule_id": gid, "data_url": f"s3://b/{gid}.nc"})
    store.upsert(
        "matchups",
        {
            "matchup_id": matchup_id,
            "profile_id": pid,
            "granule_id": gid,
            "n_spectra": 1,
            "scene_path": scene_path,
        },
    )
    store.upsert(
        "matchup_pixels",
        {"matchup_id": matchup_id, "ix": 2, "iy": 2, "rank": 1, "flagged": 0},
    )
    fit_id = f"{matchup_id}_{algorithm}_{version}"
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "algorithm": algorithm,
            "model_pair": "ExpBPow" if algorithm == "BING" else None,
            "pab_version": version,
            "success": 1,
        },
    )
    return fit_id


def _capture(monkeypatch):
    """Replace the renderer; return the list of (fit_id, matchup_id, want_scene)."""
    from pab import pipeline

    calls = []

    def _fake(db_path, fit_id, matchup_id, figdir, opener, *, store=None,
              want_scene=True):
        from pathlib import Path

        calls.append((fit_id, matchup_id, want_scene))
        fpath = Path(figdir) / f"{fit_id}_fit.png"
        fpath.write_bytes(b"png")
        if not want_scene:
            return str(fpath), None
        sp = Path(figdir) / f"{matchup_id}_scene.png"
        sp.write_bytes(b"png")
        return str(fpath), str(sp)

    monkeypatch.setattr(pipeline, "_render_figure", _fake)
    return calls


def test_nasa_giop_rows_are_never_rendered(monkeypatch, tmp_path):
    """They have no chains: every one of these renders would fail."""
    calls = _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="2.0")
        _seed_fit(store, "M2", algorithm="NASA_GIOP", version="1.1", wmo=7902227)
        out = figure(store, PipelineConfig(outdir=tmp_path, jobs=1))
    rendered = {c[0] for c in calls}
    assert rendered == {"M1_BING_2.0"}, (
        f"a NASA-GIOP row was sent to the fit renderer: {rendered}"
    )
    assert out["failed"] == []


def test_only_the_newest_bing_version_is_rendered(monkeypatch, tmp_path):
    calls = _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="1.0")
        store.upsert(
            "fits",
            {
                "fit_id": "M1_BING_2.0",
                "matchup_id": "M1",
                "algorithm": "BING",
                "model_pair": "ExpBPow",
                "pab_version": "2.0",
                "success": 1,
            },
        )
        figure(store, PipelineConfig(outdir=tmp_path, jobs=1))
    assert [c[0] for c in calls] == ["M1_BING_2.0"]


def test_an_explicit_figure_version_overrides_the_default(monkeypatch, tmp_path):
    calls = _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="1.0")
        store.upsert(
            "fits",
            {
                "fit_id": "M1_BING_2.0",
                "matchup_id": "M1",
                "algorithm": "BING",
                "model_pair": "ExpBPow",
                "pab_version": "2.0",
                "success": 1,
            },
        )
        figure(
            store, PipelineConfig(outdir=tmp_path, jobs=1, figure_version="1.0")
        )
    assert [c[0] for c in calls] == ["M1_BING_1.0"]


# -- the scene guard ----------------------------------------------------------
def test_scene_rendered_only_where_scene_path_is_null(monkeypatch, tmp_path):
    """The requirement: an existing scene is not re-read from the granule."""
    calls = _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="2.0", scene_path="/old.png")
        _seed_fit(
            store, "M2", algorithm="BING", version="2.0", scene_path=None, wmo=7902227
        )
        figure(store, PipelineConfig(outdir=tmp_path, jobs=1))
    want = {mid: ws for _, mid, ws in calls}
    assert want == {"M1": False, "M2": True}, (
        "a matchup that already had a scene was re-rendered; the scene is the "
        "half that re-opens the granule"
    )


def test_an_existing_scene_path_is_not_overwritten(monkeypatch, tmp_path):
    """The old path must survive — the stage is additive, not destructive."""
    _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="2.0", scene_path="/old.png")
        figure(store, PipelineConfig(outdir=tmp_path, jobs=1))
        row = store.query("SELECT scene_path FROM matchups WHERE matchup_id='M1'")[0]
    assert row["scene_path"] == "/old.png"


def test_a_new_scene_path_is_recorded(monkeypatch, tmp_path):
    _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="2.0", scene_path=None)
        figure(store, PipelineConfig(outdir=tmp_path, jobs=1))
        row = store.query("SELECT scene_path FROM matchups WHERE matchup_id='M1'")[0]
    assert row["scene_path"] and row["scene_path"].endswith("M1_scene.png")


def test_two_fits_of_one_matchup_render_its_scene_once(monkeypatch, tmp_path):
    """Otherwise a second model_pair pays the granule read a second time."""
    calls = _capture(monkeypatch)
    with Store.open(":memory:") as store:
        _seed_fit(store, "M1", algorithm="BING", version="2.0", scene_path=None)
        store.upsert(
            "fits",
            {
                "fit_id": "M1_BING_2.0_b",
                "matchup_id": "M1",
                "algorithm": "BING",
                "model_pair": "ExpNMF",
                "pab_version": "2.0",
                "success": 1,
            },
        )
        figure(store, PipelineConfig(outdir=tmp_path, jobs=1))
    assert len(calls) == 2, "both fit figures should still be rendered"
    assert sum(1 for _, _, ws in calls if ws) == 1, "the scene was rendered twice"


def test_render_figure_skips_the_granule_when_scene_not_wanted(monkeypatch, tmp_path):
    """`want_scene=False` must not reach `scene_from_store` at all.

    Asserted by **counting calls**, not by raising from the mock: the scene
    render sits inside a `try/except Exception: pass` (a bad scene must not
    fail the fit figure), so a mock that raises is swallowed and the test
    passes whether or not the guard is there.
    """
    from pathlib import Path

    from pab import pipeline
    from pab.plotting import fit_fig, scene

    monkeypatch.setattr(
        fit_fig,
        "fit_figure",
        lambda store, fit_id, outfile: Path(outfile).write_bytes(b"png"),
    )
    seen = []

    def _spy(store, matchup_id, *, opener=None, outfile=None):
        seen.append(matchup_id)
        Path(outfile).write_bytes(b"png")
        return outfile

    monkeypatch.setattr(scene, "scene_from_store", _spy)
    with Store.open(":memory:") as store:
        fit_id = _seed_fit(store, "M1", algorithm="BING", version="2.0")
        _, spath = pipeline._render_figure(
            None, fit_id, "M1", tmp_path, None, store=store, want_scene=False
        )
        assert seen == [], "the granule was opened for a matchup that has a scene"
        assert spath is None
        # ...and the same call with want_scene=True does reach it.
        _, spath2 = pipeline._render_figure(
            None, fit_id, "M1", tmp_path, None, store=store, want_scene=True
        )
        assert seen == ["M1"]
        assert spath2 is not None
