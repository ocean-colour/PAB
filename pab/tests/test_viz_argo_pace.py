"""The Argo + PACE viz tool (claude_prompts/viz_tools.md, Argo+PACE).

No network and no chains: the store is in memory, the Argo profile and the
reconstructed curves are injected.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from pab.argo import summary
from pab.db.store import Store
from pab.tests.test_compare_versions import _add_bing_fit, _seed_patched_runaway
from pab.viz import app, data
from pab.viz import argo as vargo
from pab.viz import bokeh_argo_pace as ap
from pab.viz import fits as vfits


def _seed(store):
    """2.0 + 2.0.1 + 2.1 fits (2.1 at 1.2 × the 2.0.1 b_bp) and a NASA row."""
    matchup_id, pixel_id, f20, f201 = _seed_patched_runaway(store)
    f21 = _add_bing_fit(store, matchup_id, pixel_id, version="2.1", bbp=4.8e-4, chl=0.2)
    store.upsert("fit_results", {"fit_id": f21, "quantity": "BING_ExpBPow_beta",
                                 "value": 0.8, "value_lo": 0.5, "value_hi": 1.1})
    store.upsert("fits", {"fit_id": "giop", "matchup_id": matchup_id, "pixel_id": pixel_id,
                          "algorithm": "NASA_GIOP", "model_pair": "GIOP",
                          "pab_version": "1.1"})
    for q, v in (("bbp_442", 1e-3), ("bbp_s", 1.0), ("bbp_unc_442", 1e-4)):
        store.upsert("fit_results", {"fit_id": "giop", "quantity": f"NASA_GIOP_{q}",
                                     "value": v})
    store.execute("UPDATE mld_summary SET bbp700 = 5e-4, bbp700_std = 5e-5")
    return matchup_id, pixel_id, f20, f201, f21


def _profile(mld=30.0):
    pres = np.arange(1.0, 101.0)
    bbp = np.where(pres <= mld, 5e-4, 2e-4) + 1e-6 * np.sin(pres)
    bbp[[4, 10]] = [5e-2, 4e-2]  # two isolated spikes the de-spike removes
    bbp[20] = 3e-3              # a 3-point plateau the IQR filter must catch
    bbp[19] = bbp[21] = 3e-3
    return vargo.ArgoProfile(wmo=7902226, cycle=5, latitude=20.0, longitude=-50.0,
                             variables={"PRES": pres, "BBP700": bbp,
                                        "BBP700_QC": np.ones_like(pres)})


def _gapped_profile(mld=30.0):
    """BBP700 on every 2nd pressure level (NaN between), as many floats merge."""
    prof = _profile(mld)
    bbp = prof.bbp.copy()
    bbp[1::2] = np.nan            # samples on the even indices only
    bbp[10] = 5e-2                # one isolated spike between two good samples
    return vargo.ArgoProfile(wmo=7902226, cycle=5, latitude=20.0, longitude=-50.0,
                             variables={**prof.variables, "BBP700": bbp})


def _curves(fit_id):
    wave = np.linspace(400, 700, 7)
    rrs = np.linspace(4e-3, 1e-4, 7)
    return vfits.FitCurves(fit_id=fit_id, wave=wave, rrs_obs=rrs, sigma=0.02 * rrs,
                           rrs_med=rrs * 1.01, rrs_lo=rrs * 0.95, rrs_hi=rrs * 1.05,
                           adg440=(0.05, 0.04, 0.06),
                           iops={"anw": (0.2 * wave / wave, 0.1 * wave / wave, 0.3 * wave / wave),
                                 "bbp": (2e-3 * wave / wave, 1e-3 * wave / wave,
                                         3e-3 * wave / wave)})


def test_open_store_is_read_only(tmp_path):
    path = tmp_path / "s.db"
    with Store.open(path) as s:
        _seed(s)
    st = data.open_store(path)
    with pytest.raises(sqlite3.OperationalError):
        st.conn.execute("DELETE FROM fits")
    st.close()


def test_families_and_fit_selection_are_version_generic():
    with Store.open(":memory:") as store:
        matchup_id, pixel_id, _, f201, f21 = _seed(store)
        assert data.version_families(store) == ["2.1", "2.0"]
        assert data.family_label(store, "2.0") == "2.0 (+2.0.1)"
        assert data.family_label(store, "2.1") == "2.1"
        fit = data.bing_fit(store, matchup_id, "2.1")
        assert fit["fit_id"] == f21 and not fit["patched"]
        assert fit["results"]["bbp700"][0] == pytest.approx(4.8e-4)
        assert fit["results"]["beta"] == pytest.approx((0.8, 0.5, 1.1))
        old = data.bing_fit(store, matchup_id, "2.0")  # the patch supersedes 2.0
        assert old["fit_id"] == f201 and old["patched"]
        assert data.wmos_with_matchups(store) == [7902226]
        assert data.cycles_for_wmo(store, 7902226) == [5]
        assert data.matchup_for(store, 7902226, 5)["matchup_id"] == matchup_id
        assert data.matchup_for(store, 7902226, 6) is None


def test_giop_moves_to_700_with_its_own_slope():
    with Store.open(":memory:") as store:
        matchup_id, pixel_id, *_ = _seed(store)
        g = data.giop_fit(store, matchup_id, pixel_id)
        assert g["bbp700"] == pytest.approx(1e-3 * 442 / 700)
        assert g["bbp700_unc"] == pytest.approx(1e-4 * 442 / 700)


def test_bbp_layers_reproduce_the_mixed_layer_summary():
    prof = _profile()
    layers = vargo.bbp_layers(prof.pres, prof.bbp, 30.0, prof.bbp_qc)
    mean, std, n = summary.mixed_layer_mean(prof.pres, prof.bbp, 30.0,
                                            despike_values=True, iqr_filter=True)
    assert layers.mean == pytest.approx(mean) and layers.std == pytest.approx(std)
    assert layers.n == n
    assert not layers.ingest_differs                 # dense sampling: same recipe
    assert layers.dropped[[19, 20, 21]].all()        # the plateau is rejected
    assert not layers.in_ml[prof.pres > 30].any()
    none = vargo.bbp_layers(prof.pres, prof.bbp, float("nan"))
    assert not none.in_ml.any() and np.isnan(none.mean)


def test_gapped_profile_is_despiked_sample_to_sample():
    """AP-Q16: the ingest median over every level neither de-spikes nor counts."""
    prof = _gapped_profile()
    layers = vargo.bbp_layers(prof.pres, prof.bbp, 30.0)
    assert np.isnan(layers.despiked[1::2]).all()      # nothing on the empty levels
    assert layers.despiked[10] < 1e-3                 # the spike is gone
    assert layers.n_samples_ml == 15                  # pres 1, 3, …, 29
    _, _, ingest_n = summary.mixed_layer_mean(prof.pres, prof.bbp, 30.0,
                                              despike_values=True, iqr_filter=True)
    assert layers.ingest_n == ingest_n > layers.n_samples_ml  # samples copied
    assert layers.ingest_differs
    with Store.open(":memory:") as store:
        _seed(store)
        view = ap.make_argo_pace(store, 7902226, 5, fetch=False, argo_profile=prof)
        assert view.fixed_line.data["x"] == [layers.mean, layers.mean]
        assert "sample de-spike" in view.table.text
        assert "AP-Q16" not in view.notes.text            # GE-Q12: note removed


def test_reproduces_tolerance():
    assert vargo.reproduces(1e-3, 1.01e-3)
    assert not vargo.reproduces(1e-3, 1.05e-3)
    assert vargo.reproduces(None, 1e-3)             # nothing stored: nothing to flag
    assert not vargo.reproduces(1e-3, float("nan"))


def test_adg_at_440():
    flat = np.array([[np.log10(0.1), 0.015], [np.log10(0.2), 0.01]])
    got = vfits.adg_at(flat, ["Adg", "Sdg"])
    assert got == pytest.approx([0.1 * np.exp(-0.6), 0.2 * np.exp(-0.4)])


def test_make_argo_pace_builds_both_panels():
    with Store.open(":memory:") as store:
        *_, f21 = _seed(store)
        view = ap.make_argo_pace(store, 7902226, 5, fetch=False, show_giop=True,
                                 argo_profile=_profile(), curves=_curves(f21))
        assert "WMO 7902226 · cycle 5" in view.header.text and "BING 2.1" in view.header.text
        assert "θ" not in view.header.text  # AP-Q8: no geometry in the header
        assert view.argo_fig.y_range.start == pytest.approx(60.0)  # 2 × MLD
        assert view.mld_span.visible and view.mld_span.location == pytest.approx(30.0)
        assert len(view.raw_src.data["x"]) == 100
        assert len(view.drop_src.data["x"]) == 3
        assert view.argo_line.data["x"] == [5e-4, 5e-4]
        assert view.pace_line.data["x"][0] == pytest.approx(4.8e-4)
        assert all(r.visible for r in view.giop_renderers)
        assert len(view.model_src.data["wave"]) == 7
        # (obs − 1.01·obs) / (0.02·obs) = −0.5 σ in every band
        assert np.allclose(view.resid_src.data["rs"], -0.5)
        for text in ("b<sub>bp</sub>(700)", "0.05 [0.04–0.06]", "NASA-GIOP"):
            assert text in view.table.text
        assert "CDOM (ppb" not in view.table.text       # prompt 4: row removed
        assert view.fixed_line.data["x"] == []          # dense profile: no dotted line
        assert view.rrs_fig.y_range.start == 0.0        # prompt 4: Rrs from 0
        assert any(getattr(r, "location", None) == 0 and r.line_dash == [6]
                   for r in view.rrs_fig.center)       # dashed zero line
        view.set_giop_visible(False)
        assert "NASA-GIOP" not in view.table.text
        assert not any(r.visible for r in view.giop_renderers)


def test_edits_1_reset_targets_log_toggle_and_iop_panel():
    """Edits #1: reset returns to the data view; linear/log10 Rrs; the IOP panel."""
    with Store.open(":memory:") as store:
        *_, f21 = _seed(store)
        view = ap.make_argo_pace(store, 7902226, 5, fetch=False,
                                 argo_profile=_profile(), curves=_curves(f21))
        for rng in (view.rrs_fig.y_range, view.rrs_log_fig.y_range, view.argo_fig.x_range,
                    view.argo_fig.y_range, view.iop_fig.y_range,
                    view.iop_fig.extra_y_ranges["bbp"]):
            assert (rng.reset_start, rng.reset_end) == (rng.start, rng.end)
        assert view.rrs_fig.y_range.end == pytest.approx(4e-3 * 1.05 * 1.05, rel=0.02)
        lo, hi = view.rrs_log_fig.y_range.start, view.rrs_log_fig.y_range.end
        assert 0 < lo < 0.95e-4 and hi > 4.2e-3
        assert view.rrs_fig.visible and not view.rrs_log_fig.visible
        view.rrs_scale.active = 1                       # the toggle drives it
        assert view.rrs_log_fig.visible and not view.rrs_fig.visible
        assert view.resid_fig.yaxis[0].__class__.__name__ == "LinearAxis"
        view.set_rrs_scale(False)
        assert view.rrs_fig.visible and view.rrs_scale.active == 0
        assert view.rrs_log_fig.x_range is view.rrs_fig.x_range is view.iop_fig.x_range
        d = view.iop_src.data
        assert np.allclose(d["anw"], 0.2) and np.allclose(d["bbp_hi"], 3e-3)
        assert np.isnan(d["adg"]).all()                 # not in the curves: blank
        assert view.iop_fig.y_range.end == pytest.approx(0.3 * 1.05)
        assert view.iop_fig.extra_y_ranges["bbp"].end == pytest.approx(3e-3 * 1.05)
        assert view.rrs_log_fig.y_range.start > 0
        view.show_selection(view._sel)                  # a new selection clears it
        assert len(view.iop_src.data["wave"]) == 0


def test_range_helpers():
    assert ap.lin_limits([[1.0, 2.0], [np.nan]]) == pytest.approx((0.0, 2.1))
    assert ap.lin_limits([[-1.0, 1.0]]) == pytest.approx((-1.1, 1.1))
    assert ap.lin_limits([[np.nan]]) is None
    assert ap.log_limits([[-1.0, 1e-3], [1e-2]]) == pytest.approx((1e-3 / 1.4, 1.4e-2))
    assert ap.log_limits([[0.0, -2.0]]) is None


def test_failure_cases_are_messages_not_crashes():
    with Store.open(":memory:") as store:
        _, _, f20, _, f21 = _seed(store)
        store.execute("UPDATE fits SET success = 0 WHERE fit_id = ?", (f21,))
        store.execute("UPDATE mld_summary SET mld = NULL, bbp700 = NULL")
        view = ap.make_argo_pace(store, 7902226, 5, fetch=False)  # no profile, no chains
        assert "LM success = 0" in view.header.text
        assert "No MLD" in view.notes.text and "No chain file" in view.notes.text
        assert view.argo_fig.y_range.start == pytest.approx(ap.NO_MLD_DEPTH)
        assert not view.mld_span.visible
        none = ap.make_argo_pace(store, 7902226, 99, fetch=False)
        assert "no matchup" in none.header.text


def test_profile_note_when_the_gdac_changed():
    with Store.open(":memory:") as store:
        _seed(store)
        sel = ap.load_selection(store, 7902226, 5)
        notes = ap.profile_notes(sel, None, {"bbp700": 9e-4, "mld": 31.0})
        assert any("GDAC file changed" in n for n in notes)
        assert not ap.profile_notes(sel, None, {"bbp700": 5.01e-4, "mld": 30.0})


def test_cli_refuses_remote_bind_and_missing_db(tmp_path, capsys):
    from pab.viz import __main__ as cli

    assert cli.main(["--db", str(tmp_path / "nope.db")]) == 2
    path = tmp_path / "s.db"
    with Store.open(path) as s:
        _seed(s)
    assert cli.main(["--db", str(path), "--host", "0.0.0.0"]) == 2
    assert "allow-remote" in capsys.readouterr().err
    assert isinstance(app.AppConfig(db_path=str(path)), app.AppConfig)
