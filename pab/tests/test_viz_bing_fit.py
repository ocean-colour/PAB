"""The BING-fit editor (claude_prompts/viz/viz_bing_fit.md).

The view tests use an in-memory store and a stand-in forward model (no chains,
no JAX). One test runs the real :class:`~pab.viz.fits.ForwardModel` on a
2.1 fit when the v2 database and its chains are on this machine, and is
skipped otherwise.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pytest

from pab.db.store import Store
from pab.tests.test_viz_argo_pace import _curves, _seed
from pab.viz import bing_fit as bf
from pab.viz import data
from pab.viz import fits as vfits

WAVE = np.linspace(400.0, 700.0, 7)
RRS = np.linspace(4e-3, 1e-4, 7)


class FakeForward:
    """The :class:`~pab.viz.fits.ForwardModel` interface on a toy model:
    ``Rrs = obs · (1 + 10 (Adg + 2))``; ``B_p`` above 0.03 is "out of domain"."""

    def __init__(self, stored_chisq=None):
        self.specs = [
            vfits.ParamSpec("Adg", True, -6.0, 1.0, -2.0, -2.1, -1.9),
            vfits.ParamSpec("Bp", False, 0.004, 0.05, 0.01, 0.008, 0.02),
        ]
        self.wave = WAVE
        self.rrs_obs = RRS
        self.var = (0.02 * RRS) ** 2
        self.start_domain = ()
        self._stored = stored_chisq
        self.calls = 0

    @property
    def names(self):
        return [s.name for s in self.specs]

    @property
    def start(self):
        return np.array([s.median for s in self.specs])

    @property
    def stored_chisq(self):
        if self._stored is not None:
            return self._stored
        rrs = RRS + 1e-5  # the model at the start vector
        return float(np.sum((rrs - RRS) ** 2 / self.var) / (RRS.size - 2))

    def settings(self):
        return {"rt_backend": "robust_hybrid", "Raman": True, "Chl-fl": True,
                "CDOM-fl": False, "phi_c": 0.02, "geometry": (0.0, 0.0, 0.0),
                "geom_mode": "normalized", "chl_seed": 0.2, "wave": (400.0, 700.0, 7)}

    def evaluate(self, params):
        self.calls += 1
        p = np.asarray(params, dtype=float)
        if p[1] < 0:
            raise ValueError("negative B_p")
        rrs = RRS * (1.0 + 10.0 * (p[0] + 2.0)) + 1e-5
        chisq = float(np.sum((rrs - RRS) ** 2 / self.var) / (RRS.size - 2))
        one = np.ones_like(WAVE)
        domain = self.start_domain
        if p[1] > 0.03:
            domain = (*domain, "B_p: 100.0% outside [0.01, 0.018] (worst 0.04)")
        return vfits.Evaluation(
            params=p, rrs=rrs,
            iops={"anw": 0.25 * one, "adg": 0.1 * one, "aph": 0.15 * one, "bbp": 2e-3 * one},
            chisq=chisq, quantities={"bbp700": 2.2e-3, "chl": 0.3, "Bp": p[1],
                                     "adg440": 0.05},
            domain=domain)


def _text(div):
    return re.sub(r"<[^>]+>", " ", div.text)


def _view(store, **kw):
    *_, f21 = _seed(store)
    return bf.make_bing_fit(store, 7902226, 5, forward=kw.pop("forward", FakeForward()),
                            curves=_curves(f21), **kw)


def _bands(view):
    return {r.visible for r in (*view.rrs_bands, *view.iop_bands)}


def test_step_value_scales_the_physical_value():
    """BF-I8: ±10 % of the physical value; BF-I9: never clipped to the prior."""
    log = vfits.ParamSpec("Adg", True, -6.0, 1.0, -2.0, -2.1, -1.9)
    assert 10 ** bf.step_value(log, -2.0, +1) == pytest.approx(1.1e-2)
    assert 10 ** bf.step_value(log, -2.0, -1) == pytest.approx(0.9e-2)
    assert bf.step_value(log, 0.99, +1) == pytest.approx(0.99 + np.log10(1.1))  # past 1.0
    lin = vfits.ParamSpec("Bp", False, 0.004, 0.05, 0.01, 0.008, 0.02)
    assert bf.step_value(lin, 0.01, +1) == pytest.approx(0.011)
    assert bf.step_value(lin, 0.0042, -1) == pytest.approx(0.00378)  # below 0.004
    beta = vfits.ParamSpec("beta", False, 0.0, 2.0, 0.5, 0.1, 1.0)
    assert bf.step_value(beta, 0.0, +1) == 0.0                    # % of zero
    assert bf.plain_label("Adg") == "log10 A_dg"


def test_start_state():
    """BF-Q1: the modified model starts at the posterior medians, bands shown."""
    with Store.open(":memory:") as store:
        view = _view(store)
        assert "WMO 7902226 · cycle 5" in view.header.text
        assert "modified" in view.header.text
        assert not view.edited and _bands(view) == {True}
        assert np.allclose(view.mod_src.data["rrs"], RRS + 1e-5)
        assert len(view.mod_resid_src.data["rs"]) == 7
        assert np.allclose(view.mod_iop_src.data["bbp"], 2e-3)
        assert view.argo_src.data["x"] == [700.0]              # BF-Q13
        assert view.argo_src.data["y"] == [pytest.approx(5e-4)]
        assert all(not r.visible for r in view.giop_renderers)  # GIOP off at start
        assert view.giop_src.data["x"] == [700.0]
        table = _text(view.table)
        for t in ("modified", "Argo (ML)", "0.0022", "0.05 [0.04–0.06]"):
            assert t in table
        assert "Forward model (fixed)" in view.settings.text
        assert "Chl = 0.2" in view.settings.text
        assert "vector:" in view.param_text.text
        assert view.notes.text == ""                             # self-check passed
        assert [b.value for b in view.boxes] == ["-2", "0.01"]
        assert [b.label for b in (view.downs[0], view.ups[0])] == ["−10 %", "+10 %"]
        assert view.rrs_fig.y_range.reset_start == view.rrs_fig.y_range.start


def test_edit_keeps_bands_and_reset_restores():
    """BF-Q5 = B: the fit's bands stay through edits; reset restores the start."""
    with Store.open(":memory:") as store:
        view = _view(store)
        assert view.set_param(0, -1.9)
        assert view.edited and _bands(view) == {True}
        assert np.allclose(view.mod_src.data["rrs"], RRS * 2.0 + 1e-5)
        assert view.boxes[0].value == "-1.9"
        assert view.rrs_fig.y_range.end > 2.0 * 4e-3          # auto-range on edit
        view.auto_range.active = False
        top = view.rrs_fig.y_range.end
        view.set_param(0, -1.8)
        assert view.rrs_fig.y_range.end == top                 # a zoom is kept
        view.set_param(0, -1.9)
        assert "(edited)" in view.infos[0].text
        view.reset_param(0)
        assert not view.edited and _bands(view) == {True}
        view.set_param(1, 0.02)
        view.reset()
        assert not view.edited and view.boxes[1].value == "0.01"
        assert np.allclose(view.mod_src.data["rrs"], RRS + 1e-5)


def test_widgets_drive_the_model():
    """BF-Q4 as answered: Enter in a number box, or a ±10 % click."""
    with Store.open(":memory:") as store:
        view = _view(store)
        fm = view.fm
        n = fm.calls
        assert view.step_param(1, +1)                         # +10 %: 0.01 → 0.011
        assert view.params[1] == pytest.approx(0.011) and fm.calls == n + 1
        assert view.boxes[1].value == "0.011"
        view.step_param(0, -1)                                # log: −0.046 dex
        assert view.params[0] == pytest.approx(-2.0 + np.log10(0.9))
        view._on_box(0, "value", "", "-0.5")
        assert view.params[0] == -0.5
        view._on_box(0, "value", "", "abc")
        assert "not a number" in view.notes.text and view.params[0] == -0.5
        view._on_box(0, "value", "", "inf")
        assert "not finite" in view.notes.text and view.params[0] == -0.5
        assert view.boxes[0].value == "-0.5"
        n = fm.calls
        view._on_box(0, "value", "", "-0.5")                 # no change: no evaluation
        assert fm.calls == n
        assert "Refused" not in view.notes.text               # a good entry clears it


def test_any_value_is_accepted_outside_the_prior():
    """BF-I9: no clipping and no refusal at the prior; a note says so, and
    clears once the value is back inside."""
    with Store.open(":memory:") as store:
        view = _view(store)
        view._on_box(0, "value", "", "3")                    # Adg prior is [-6, 1]
        assert view.params[0] == 3.0
        assert "Adg = 3 is outside its prior" in view.notes.text
        view.set_param(0, -2.0)
        assert "outside its prior" not in view.notes.text
        view.set_param(1, 0.0455)
        view.step_param(1, +1)                                # 0.05005 > 0.05
        assert view.params[1] == pytest.approx(0.05005)
        view.step_param(1, +1)                                # and on past the ceiling
        assert view.params[1] == pytest.approx(0.055055)
        assert "Bp = 0.055055 is outside its prior" in view.notes.text


def test_failed_evaluation_is_a_note_that_clears():
    """Any value may be typed, so the forward model may fail: shown, not raised;
    the last good curve stays; the next good evaluation clears the note."""
    with Store.open(":memory:") as store:
        view = _view(store)
        before = np.array(view.mod_src.data["rrs"])
        assert view.set_param(1, -0.01)
        assert "Evaluation failed (ValueError: negative B_p)" in view.notes.text
        assert np.array_equal(view.mod_src.data["rrs"], before)
        assert view.params[1] == -0.01 and view.boxes[1].value == "-0.01"
        view.set_param(1, 0.02)
        assert "Evaluation failed" not in view.notes.text


def test_domain_warning_note():
    """BF-Q14: out-of-domain evaluations are named in the notes."""
    with Store.open(":memory:") as store:
        view = _view(store)
        view.set_param(1, 0.04)
        assert "training range" in view.notes.text and "B_p: 100.0%" in view.notes.text
        view.set_param(1, 0.02)
        assert "training range" not in view.notes.text


def test_domain_breach_of_the_fit_itself_is_not_a_warning():
    """A breach already at the posterior medians is a grey standing line;
    only a newly breached feature is the amber warning."""
    with Store.open(":memory:") as store:
        fm = FakeForward()
        fm.start_domain = ("eta_bb: 10.0% outside [0.02, 0.9] (worst 0.95)",)
        view = _view(store, forward=fm)
        assert "The fit itself" in view.notes.text and "eta_bb" in view.notes.text
        assert "modified model is outside" not in view.notes.text
        view.set_param(1, 0.04)
        assert "modified model is outside" in view.notes.text
        assert "B_p: 100.0%" in view.notes.text


def test_self_check_note_when_chisq_disagrees():
    with Store.open(":memory:") as store:
        view = _view(store, forward=FakeForward(stored_chisq=123.0))
        assert "Self-check failed" in view.notes.text


def test_async_updates_drop_stale_results():
    """BF-Q4: with a doc, the pool evaluates and only the newest result lands."""

    class Doc:
        def __init__(self):
            self.callbacks = []

        def add_next_tick_callback(self, cb):
            self.callbacks.append(cb)

    with Store.open(":memory:") as store:
        view = _view(store)
        view.doc = Doc()
        view.set_param(0, -1.95)
        first = view._future
        view.set_param(0, -1.9)
        first.result()
        view._future.result()
        assert "evaluating" in view.header.text
        for cb in view.doc.callbacks:
            cb()
        assert np.allclose(view.mod_src.data["rrs"], RRS * 2.0 + 1e-5)
        assert "evaluating" not in view.header.text


def test_missing_fit_or_chains_raise():
    with Store.open(":memory:") as store:
        _seed(store)
        with pytest.raises(LookupError, match="no matchup"):
            bf.make_bing_fit(store, 7902226, 99, forward=FakeForward())
        with pytest.raises(LookupError, match="no BING"):
            bf.make_bing_fit(store, 7902226, 5, family="9.9", forward=FakeForward())
        with pytest.raises(LookupError, match="no db_path"):
            bf.make_bing_fit(store, 7902226, 5)
        with pytest.raises(LookupError, match="no chain file"):
            bf.select_fit(store, 7902226, 5, check_chains=True)
        mid = data.matchup_ids_for(store, 7902226, 5)
        assert bf.select_fit(store, 7902226, 5, matchup_id=mid[0]).matchup["matchup_id"] == mid[0]
        with pytest.raises(LookupError):
            bf.select_fit(store, 7902226, 5, matchup_id="nope")


def test_domain_messages_parse():
    msg = ("the emulator is being evaluated outside its training range, where M3 ...: "
           "eta_bb 35.3% of values outside [0.01757, 0.966], worst 0.9885 — 3% of the "
           "trained span beyond it; B_p 100.0% of values outside [0.01026, 0.018], worst "
           "0.05 — 400% of the trained span beyond it. Consider mode='ztt'.")
    assert vfits.domain_messages(msg) == [
        "eta_bb: 35.3% outside [0.01757, 0.966] (worst 0.9885)",
        "B_p: 100.0% outside [0.01026, 0.018] (worst 0.05)"]
    assert vfits.domain_messages("something else") == ["something else"]


def test_cli_args(tmp_path, capsys):
    with pytest.raises(SystemExit):
        bf.parse_args([])                                     # wmo/cycle required
    assert bf.main(["--wmo", "1", "--cycle", "1", "--db", str(tmp_path / "x.db")]) == 2
    path = tmp_path / "s.db"
    with Store.open(path) as s:
        _seed(s)
    assert bf.main(["--wmo", "7902226", "--cycle", "5", "--db", str(path),
                    "--host", "0.0.0.0"]) == 2
    assert "allow-remote" in capsys.readouterr().err
    # no chains next to this DB: refused before any server starts (BF-Q17)
    assert bf.main(["--wmo", "7902226", "--cycle", "5", "--db", str(path)]) == 2
    assert "no chain file" in capsys.readouterr().err
    assert bf.parse_args(["--wmo", "1", "--cycle", "2"]).port == 5007


_ROOT = os.environ.get("PAB_DATA_DIR")
_DB = Path(_ROOT) / "v2" / "pab.db" if _ROOT else None


@pytest.mark.skipif(_DB is None or not _DB.is_file(), reason="needs the v2 DB")
def test_forward_model_reproduces_the_stored_fit():
    """BF-Q1 self-check on real data: χ² at the posterior medians equals
    ``fits.chisq``, and the parameters / Chl match ``fit_results``."""
    data.set_data_dir(_DB.parent)
    store = data.open_store(_DB)
    try:
        row = store.query("SELECT fit_id, chisq FROM fits WHERE pab_version = '2.1' "
                          "AND algorithm = 'BING' ORDER BY fit_id LIMIT 1")[0]
        if not data.has_chains(row["fit_id"]):
            pytest.skip("no chains for the probe fit")
        fm = vfits.ForwardModel(store, row["fit_id"])
        ev = fm.evaluate(fm.start)
        assert ev.chisq == pytest.approx(row["chisq"], rel=1e-5)
        res = data._results(store, row["fit_id"])
        for q in ("Adg", "Aph", "Bp", "chl"):
            assert ev.quantities[q] == pytest.approx(res[f"BING_ExpBPow_{q}"][0], rel=1e-5)
        assert set(ev.iops) == {"anw", "adg", "aph", "bbp"}
        assert isinstance(ev.domain, tuple)  # most 2.1 fits breach the B_p domain
    finally:
        store.close()
