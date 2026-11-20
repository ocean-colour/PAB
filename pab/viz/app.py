"""The ``pab-viz`` Bokeh server document: one tab per view (I-Q7).

Tab 1 is the Argo + PACE view (:mod:`pab.viz.bokeh_argo_pace`); tab 2 the
Global explorer (:mod:`pab.viz.global_explorer`), whose "Open in Argo + PACE"
loads a matchup into tab 1 and switches to it (``?tab=global`` opens on it). Slow work
(the Argo fetch, the fit reconstruction) runs in a thread pool and lands in
the document through ``doc.add_next_tick_callback``, so the page stays live and
shows "loading" while it runs. A token discards results that arrive after the
user has moved on to another profile.
"""

from __future__ import annotations

import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from bokeh.layouts import column, row
from bokeh.models import AutocompleteInput, Select, TabPanel, Tabs, Toggle

from pab.viz import argo as vargo
from pab.viz import bokeh_argo_pace as ap
from pab.viz import data
from pab.viz import fits as vfits
from pab.viz import global_explorer as gx

log = logging.getLogger("pab.viz")

#: Shared by every session of the server.
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pab-viz")


@dataclass(frozen=True)
class AppConfig:
    """What :mod:`pab.viz.__main__` hands every session."""

    db_path: str
    model_pair: str = data.DEFAULT_MODEL_PAIR
    wmo: int | None = None
    cycle: int | None = None
    family: str | None = None


def _arg(doc, name: str):
    """A URL query argument (``?wmo=…``) of this session, or ``None``."""
    try:
        vals = doc.session_context.request.arguments.get(name)
    except AttributeError:
        return None
    return vals[0].decode() if vals else None


class ArgoPaceTab:
    """The controls + view of tab 1 and their callbacks, for one session."""

    def __init__(self, doc, cfg: AppConfig, *, autoload: bool = True):
        self.doc = doc
        self.cfg = cfg
        self.store = data.open_store(cfg.db_path)
        self.view = ap.ArgoPaceView()
        self.token = 0
        self.notes: list[str] = []
        self._pending: set[str] = set()
        self._quiet = False

        self.wmos = [str(w) for w in data.wmos_with_matchups(self.store)]
        families = data.version_families(self.store)
        self.version = Select(
            title="BING version",
            options=[(f, data.family_label(self.store, f)) for f in families],
            value=families[0] if families else "", width=170,
        )
        self.wmo = AutocompleteInput(title="WMO", completions=self.wmos, min_characters=1,
                                     case_sensitive=False, width=150, restrict=True)
        self.cycle = Select(title="cycle", options=[], width=110)
        self.giop = Toggle(label="NASA-GIOP", active=False, width=110, margin=(24, 5, 5, 5))

        wmo = _arg(doc, "wmo") or (str(cfg.wmo) if cfg.wmo else None)
        cycle = _arg(doc, "cycle") or (str(cfg.cycle) if cfg.cycle else None)
        fam = _arg(doc, "version") or cfg.family
        if fam in families:
            self.version.value = fam
        if wmo not in self.wmos:
            wmo = self.wmos[0] if self.wmos else None
            cycle = None
        if wmo is not None:
            self.wmo.value = wmo
            self._set_cycles(wmo, cycle)

        self.wmo.on_change("value", self._on_wmo)
        self.cycle.on_change("value", lambda a, o, n: self._on_change())
        self.version.on_change("value", lambda a, o, n: self._on_change())
        self.giop.on_change("active", lambda a, o, n: self.view.set_giop_visible(n))

        controls = row(self.wmo, self.cycle, self.version, self.giop)
        self.layout = column(controls, self.view.layout)
        if autoload:
            self.load()

    # -- controls ------------------------------------------------------------
    def _set_cycles(self, wmo: str, cycle: str | None = None) -> None:
        cycles = [str(c) for c in data.cycles_for_wmo(self.store, int(wmo))]
        self.cycle.options = cycles
        self.cycle.value = cycle if cycle in cycles else (cycles[0] if cycles else "")

    def _on_change(self) -> None:
        if not self._quiet:
            self.load()

    def show(self, wmo: int, cycle: int, family: str | None = None) -> None:
        """Load ``(wmo, cycle)`` (from the Global tab), one load only."""
        self._quiet = True
        try:
            if family in [o[0] for o in self.version.options]:
                self.version.value = family
            if str(wmo) in self.wmos:
                self.wmo.value = str(wmo)
                self._set_cycles(str(wmo), str(cycle))
        finally:
            self._quiet = False
        self.load()

    def _on_wmo(self, attr, old, new) -> None:
        if self._quiet:
            return
        if new and new in self.wmos:
            before = self.cycle.value
            self._set_cycles(new)
            if self.cycle.value == before:  # no change event fired
                self.load()

    # -- loading -------------------------------------------------------------
    def _status(self) -> None:
        pending = [f"<i>{p}…</i>" for p in sorted(self._pending)]
        self.view.set_notes(pending + self.notes)

    def load(self) -> None:
        """Show the stored values now; fetch and reconstruct in the background."""
        if not self.wmo.value or not self.cycle.value:
            return
        self.token += 1
        token = self.token
        sel = ap.load_selection(self.store, int(self.wmo.value), int(self.cycle.value),
                                self.version.value or None, model_pair=self.cfg.model_pair)
        self.view.show_selection(sel)
        self.view.set_giop_visible(self.giop.active)
        self.notes = []
        self._pending = set()
        if sel.matchup is None:
            self._status()
            return
        self._pending.add("Fetching the Argo profile from the GDAC")
        _POOL.submit(self._fetch_job, token, sel)
        if sel.fit is not None:
            fid = sel.fit["fit_id"]
            if data.has_chains(fid):
                obs = vfits.observed_spectrum(fid)
                if obs is not None:
                    self.view.show_observed(*obs)
                self._pending.add("Reconstructing the BING fit")
                _POOL.submit(self._fit_job, token, fid)
            else:
                self.notes.append(f"No chain file for {fid} under "
                                  f"{data.chains_file(fid).parent}: the model curve "
                                  "cannot be drawn.")
                self.view.show_no_curves()
        self._status()

    def _fetch_job(self, token: int, sel: ap.Selection) -> None:
        t0 = time.monotonic()
        try:
            prof = vargo.fetch_argo_profile(sel.wmo, sel.cycle)
            layers = vargo.bbp_layers(prof.pres, prof.bbp, sel.mld, prof.bbp_qc)
            result = (layers, vargo.recompute_summary(prof), None)
        except Exception as exc:  # noqa: BLE001 - shown in the page (AP-Q15)
            result = (None, None, f"Argo fetch failed ({type(exc).__name__}: {exc}); "
                                  "showing the stored ML mean and MLD only.")
        log.info("argo %s/%s: %s in %.1f s", sel.wmo, sel.cycle,
                 "failed" if result[2] else "fetched", time.monotonic() - t0)
        self.doc.add_next_tick_callback(functools.partial(self._fetch_done, token, sel, *result))

    def _fetch_done(self, token, sel, layers, recomputed, error) -> None:
        if token != self.token:
            return
        self._pending.discard("Fetching the Argo profile from the GDAC")
        self.view.show_profile(layers)
        if error:
            self.notes.append(error)
        self.notes.extend(ap.profile_notes(sel, layers, recomputed))
        self._status()

    def _fit_job(self, token: int, fit_id: str) -> None:
        t0 = time.monotonic()
        try:
            result = (vfits.reconstruct(self.cfg.db_path, fit_id), None)
        except Exception as exc:  # noqa: BLE001 - shown in the page (AP-Q15)
            result = (None, f"Reconstruction failed ({type(exc).__name__}: {exc}).")
        log.info("fit %s: %s in %.1f s", fit_id, "failed" if result[1] else "rebuilt",
                 time.monotonic() - t0)
        self.doc.add_next_tick_callback(functools.partial(self._fit_done, token, *result))

    def _fit_done(self, token, curves, error) -> None:
        if token != self.token:
            return
        self._pending.discard("Reconstructing the BING fit")
        if curves is not None:
            self.view.show_curves(curves)
        else:
            self.notes.append(error)
            self.view.show_no_curves()
        self._status()


def make_document(doc, cfg: AppConfig) -> None:
    """Fill a new session's document (the server's ``FunctionHandler``)."""
    start_global = _arg(doc, "tab") == "global"
    # opening on the Global tab: no fetch for tab 1 until a matchup is opened
    tab = ArgoPaceTab(doc, cfg, autoload=not start_global or bool(_arg(doc, "wmo")))

    def open_matchup(wmo: int, cycle: int, family: str | None) -> None:
        tab.show(wmo, cycle, family)
        tabs.active = 0

    glob = gx.GlobalTab(tab.store, cfg.db_path, model_pair=cfg.model_pair,
                        open_matchup=open_matchup)
    tabs = Tabs(tabs=[TabPanel(child=tab.layout, title="Argo + PACE"),
                      TabPanel(child=glob.layout, title="Global")])
    if start_global:
        tabs.active = 1

    def on_tab(attr, old, new) -> None:  # tab 1 shown before anything was loaded
        if new == 0 and tab.token == 0:
            tab.load()

    tabs.on_change("active", on_tab)
    doc.add_root(tabs)
    doc.title = "PAB viz"
    doc.on_session_destroyed(lambda ctx: tab.store.close())
