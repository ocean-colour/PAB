"""
Galleries of PACE OCI L1B scenes around PACE/BGC-Argo bbp(700) matchups
(``papers/bbp/prompts/build_l1b_galleries.md``, Prompts/Test gallery 1-3;
decisions in Q&A/Test gallery 1-2).

The galleries are for spotting cloud near the matchups. A gallery is defined
by a JSON file in ``papers/bbp/galleries/``:

    criteria    keyword arguments of :func:`find_examples.find_examples`
                (``argo_target``, ``ratio_target``, ``dtime_max``,
                ``cloud_max`` -- ``null`` = no granule cloud cut --,
                ``one_per_float``)
    selection   ``n`` matchups (best score first), ``n_per_page`` per figure
    plot        ``wave`` (nm), ``half_width_km``, ``pace_circle_km``,
                ``argo_circle_km`` (lists of radii), ``scale_km``,
                ``ncols``, ``nrows``, ``figsize``, ``dpi``
    out         the PNG, relative to ``papers/bbp/``; with more than one page
                ``_<page>`` is appended before ``.png`` (Q&A 2, A3)

Each panel shows the L1B TOA reflectance ``rhot`` at ~650 nm (red CCD, no
flags) on one grey log scale shared by every panel. The box is
``2 * half_width_km`` on a side **on the ground**, centred on the fitted PACE
pixel and drawn on the scan/pixel grid with the aspect that makes it square.
Where the box runs off the granule the panel is padded with a flat colour
("outside granule", Q&A 2, A4). The panel marks the PACE pixel with a small
orange dot and draws dotted circles of ``pace_circle_km`` around it (orange,
30 km) and of ``argo_circle_km`` around the Argo profile (cyan, 20 km)
(prompt 4). The circles are contours of the great-circle distance on the L1B
geolocation grid, so they are true circles on the ground. A scale bar of
``scale_km`` replaces the axis ticks.

L1B granules are read from the shared cache ``$PAB_DATA_DIR/L1B/`` and
downloaded there if missing (~1.9 GB each; Q&A 1, A4).

Usage:
    python papers/bbp/py/l1b_gallery.py              # figure 1: the test gallery
    python papers/bbp/py/l1b_gallery.py <n>          # figure n of FIGURES
    python papers/bbp/py/l1b_gallery.py <file.json>  # any gallery JSON
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import find_examples as fe
import plot_L1B as pl
from pab.config import DATA_DIR

# ── defaults ──────────────────────────────────────────────────────────────────

BBP_DIR = Path(__file__).resolve().parent.parent      # papers/bbp/
GALLERY_DIR = BBP_DIR / "galleries"
L1B_DIR = Path(DATA_DIR) / "L1B"                      # shared L1B cache

#: Shared colour scale of rhot (as in plot_L1B.py).
RHOT_MIN, RHOT_MAX = 0.03, 1.0

PIXEL_COLOR = pl.PIXEL_COLOR      # orange: PACE pixel and its circle
ARGO_COLOR = pl.ARGO_COLOR        # cyan: circle around the Argo profile
PAD_COLOR = "#e6d9b8"             # outside the granule (not grey: not cloud)
SCALE_KM = 50.0                   # default length of the scale bar

#: Retries of an L1B lookup/download (NASA CMR intermittently returns 500).
N_TRY = 4
WAIT_S = 30.0                     # first wait; doubled after each failure

RC = {
    "font.size": 10, "axes.titlesize": 10.5, "legend.fontsize": 10,
    "figure.dpi": 100,
}


# ── configuration and selection ───────────────────────────────────────────────

def load_config(path) -> dict:
    """Read a gallery JSON file (see the module docstring for its keys)."""
    with open(path) as f:
        cfg = json.load(f)
    cfg["_path"] = str(path)
    return cfg


def select_matchups(cfg: dict):
    """The gallery's matchups: :func:`find_examples.find_examples` on ``criteria``.

    Returns the ranked frame (best score first) of ``selection.n`` rows.
    """
    df = fe.find_examples(n=cfg["selection"]["n"], **cfg["criteria"])
    a = df.attrs
    print(f"{a['n_all']} matchups -> {a['n_cloud']} after cloud cut "
          f"-> {a['n_dtime']} after |dt| cut ({a['n_floats']} floats); "
          f"using top {len(df)} (score <= {df['score'].max():.3f})")
    return df


# ── data per panel ────────────────────────────────────────────────────────────

def fetch_l1b(wmo: int, cycle: int, m: dict) -> Path:
    """The L1B file of the matchup in :data:`L1B_DIR`, downloaded if missing.

    Wraps :func:`plot_L1B.l1b_path` in :data:`N_TRY` attempts with a doubling
    wait, because the CMR granule search behind the download intermittently
    fails with HTTP 500 (seen twice while building the low 1e-3 gallery).
    """
    wait = WAIT_S
    for i in range(N_TRY):
        try:
            return pl.l1b_path(wmo, cycle, m, download=True, l1b_dir=L1B_DIR)
        except Exception as e:                       # network / CMR errors
            if i == N_TRY - 1:
                raise
            print(f"    L1B fetch failed ({type(e).__name__}: {str(e)[:80]}); "
                  f"retry {i + 2}/{N_TRY} in {wait:.0f} s", flush=True)
            time.sleep(wait)
            wait *= 2


def load_panel(row, plot_cfg: dict) -> dict:
    """Read everything one panel needs for the matchup in ``row``.

    Args:
        row: A row of :func:`select_matchups` (``wmo``, ``cycle``, ``lat``,
            ``lon``, ``bbp_argo``, ``bbp_pace``).
        plot_cfg: The JSON ``plot`` block.

    Returns:
        A dict with the matchup (``m``, from :func:`plot_L1B.find_matchup`),
        the L1B ``box`` (from :func:`plot_L1B.load_l1b_box`, clipped at the
        granule), the local scales ``km_per_pixel`` / ``km_per_scan``, the
        padded axis limits ``xlim`` / ``ylim``, the distance from the PACE
        pixel ``d_pix`` and from the Argo profile ``d_argo`` (km, on the
        box grid) and ``edge`` (the box was clipped by the granule).
    """
    wmo, cycle = int(row["wmo"]), int(row["cycle"])
    hw = float(plot_cfg["half_width_km"])
    m = pl.find_matchup(wmo, cycle)
    path = fetch_l1b(wmo, cycle, m)
    box = pl.load_l1b_box(path, m["scan"], m["pixel"], hw, plot_cfg["wave"])
    with netCDF4.Dataset(path) as ds:                  # granule size
        n_scan, n_pix = ds["geolocation_data"]["latitude"].shape

    # mean ground size of a pixel / scan through the matchup pixel
    js, jp = m["scan"] - box["s0"], m["pixel"] - box["p0"]
    lat, lon = box["lat"], box["lon"]
    km_x = pl._great_circle_km(lat[js, 0], lon[js, 0], lat[js, -1], lon[js, -1])
    km_y = pl._great_circle_km(lat[0, jp], lon[0, jp], lat[-1, jp], lon[-1, jp])
    kpp = km_x / max(box["p1"] - box["p0"] - 1, 1)
    kps = km_y / max(box["s1"] - box["s0"] - 1, 1)

    # The frame: on each side, the box edge itself (the last pixel within
    # ``hw`` km, so the frame is hw km from the PACE pixel on the ground even
    # though OCI pixels grow away from nadir) -- unless the granule ends
    # there, in which case the frame is extrapolated with the mean scale and
    # the gap is padded.
    hx, hy = hw / kpp, hw / kps
    clip = {"left": box["p0"] == 0, "right": box["p1"] == n_pix,
            "top": box["s0"] == 0, "bottom": box["s1"] == n_scan}
    x_lo = m["pixel"] - hx if clip["left"] else box["p0"] - 0.5
    x_hi = m["pixel"] + hx if clip["right"] else box["p1"] - 0.5
    y_lo = m["scan"] - hy if clip["top"] else box["s0"] - 0.5
    y_hi = m["scan"] + hy if clip["bottom"] else box["s1"] - 0.5
    xlim, ylim = (x_lo, x_hi), (y_hi, y_lo)            # scan 0 at the top
    # mean ground scales over the whole frame, for the aspect and scale bar
    kpp, kps = 2 * hw / (x_hi - x_lo), 2 * hw / (y_hi - y_lo)
    edge = any(clip.values())

    d_pix = pl._great_circle_km(lat, lon, m["pix_lat"], m["pix_lon"])
    d_argo = pl._great_circle_km(lat, lon, m["argo_lat"], m["argo_lon"])

    return {"row": row, "m": m, "box": box, "km_per_pixel": float(kpp),
            "km_per_scan": float(kps), "xlim": xlim, "ylim": ylim,
            "d_pix": d_pix, "d_argo": d_argo, "edge": bool(edge)}


# ── drawing ───────────────────────────────────────────────────────────────────

def _latlon(lat: float, lon: float) -> str:
    """``36.80°N 17.13°E``."""
    return (f"{abs(lat):.2f}°{'S' if lat < 0 else 'N'} "
            f"{abs(lon):.2f}°{'W' if lon < 0 else 'E'}")


def draw_panel(ax, p: dict, plot_cfg: dict):
    """Draw one matchup panel on ``ax``; returns the image (for the colourbar)."""
    m, box, row = p["m"], p["box"], p["row"]
    extent = (box["p0"] - 0.5, box["p1"] - 0.5, box["s1"] - 0.5, box["s0"] - 0.5)

    ax.set_facecolor(PAD_COLOR)                        # shows where padded
    im = ax.imshow(box["rhot"], extent=extent, cmap="gray", interpolation="nearest",
                   norm=LogNorm(vmin=RHOT_MIN, vmax=RHOT_MAX))

    # dotted circles of fixed radius on the ground: around the PACE pixel
    # (orange) and around the Argo profile (cyan)
    xx = np.arange(box["p0"], box["p1"])
    yy = np.arange(box["s0"], box["s1"])
    for dist, radii, color in ((p["d_pix"], plot_cfg["pace_circle_km"], PIXEL_COLOR),
                               (p["d_argo"], plot_cfg["argo_circle_km"], ARGO_COLOR)):
        if radii:
            ax.contour(xx, yy, dist, levels=sorted(radii), colors=color,
                       linewidths=1.3, linestyles=":")

    # the PACE pixel: a small dot
    ax.plot(m["pixel"], m["scan"], marker="o", ms=2.5, color=PIXEL_COLOR,
            mec="none", ls="none")

    # padded, ground-square frame; no ticks
    ax.set_xlim(*p["xlim"])
    ax.set_ylim(*p["ylim"])
    ax.set_aspect(p["km_per_scan"] / p["km_per_pixel"])
    ax.set_xticks([])
    ax.set_yticks([])

    # scale bar, bottom left
    x0 = p["xlim"][0] + 0.06 * (p["xlim"][1] - p["xlim"][0])
    y0 = p["ylim"][0] - 0.07 * (p["ylim"][0] - p["ylim"][1])
    scale_km = float(plot_cfg.get("scale_km", SCALE_KM))
    ax.plot([x0, x0 + scale_km / p["km_per_pixel"]], [y0, y0], color="w", lw=2.0,
            solid_capstyle="butt")
    ax.text(x0, y0 - 0.025 * (p["ylim"][0] - p["ylim"][1]), f"{scale_km:g} km",
            color="w", fontsize=8, va="bottom", ha="left")

    # labels: wmo / cycle and lat/lon in the title; bbp(700) in the panel
    ax.set_title(f"{int(row['wmo'])} / {int(row['cycle'])}", loc="left",
                 fontweight="bold")
    ax.set_title(_latlon(row["lat"], row["lon"]), loc="right", fontsize=9)
    ax.text(0.98, 0.03,
            f"Argo {row['bbp_argo']:.2e}\nPACE {row['bbp_pace']:.2e} m$^{{-1}}$",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8.5,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.8))
    if p["edge"]:
        ax.text(0.02, 0.97, "edge", transform=ax.transAxes, ha="left", va="top",
                fontsize=8.5, color="#8a5a00", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc=PAD_COLOR, ec="none"))
    return im


def plot_page(panels: list, plot_cfg: dict, title: str, out=None):
    """One gallery page: ``nrows x ncols`` panels, a shared colourbar, a legend.

    Args:
        panels: :func:`load_panel` dicts, in display order.
        plot_cfg: The JSON ``plot`` block.
        title: Figure title.
        out: Path to save the PNG (at ``plot_cfg['dpi']``); nothing saved if None.

    Returns:
        The Figure.
    """
    nrows, ncols = plot_cfg["nrows"], plot_cfg["ncols"]
    with mpl.rc_context(RC):
        fig, axes = plt.subplots(nrows, ncols, figsize=tuple(plot_cfg["figsize"]),
                                 layout="constrained", squeeze=False)
        im = None
        for ax, p in zip(axes.flat, panels):
            im = draw_panel(ax, p, plot_cfg)
        for ax in axes.flat[len(panels):]:             # unused slots
            ax.set_axis_off()

        cb = fig.colorbar(im, ax=axes, shrink=0.6, pad=0.01, extend="both")
        cb.set_label(f"L1B TOA reflectance $\\rho_t$ "
                     f"({plot_cfg['wave']:.0f} nm)")

        handles = [
            Line2D([], [], marker="o", ms=4, color=PIXEL_COLOR, mec="none",
                   ls="none", label="PACE pixel"),
            *[Line2D([], [], color=PIXEL_COLOR, ls=":", lw=1.5,
                     label=f"{r:g} km from PACE pixel")
              for r in sorted(plot_cfg["pace_circle_km"])],
            *[Line2D([], [], color=ARGO_COLOR, ls=":", lw=1.5,
                     label=f"{r:g} km from Argo profile")
              for r in sorted(plot_cfg["argo_circle_km"])],
        ]
        if any(p["edge"] for p in panels):
            handles.append(Patch(fc=PAD_COLOR, ec="none", label="outside granule"))
        fig.legend(handles=handles, loc="outside lower center", ncols=len(handles),
                   frameon=False)
        fig.suptitle(title, fontsize=12)
        if out is not None:
            fig.savefig(out, dpi=plot_cfg["dpi"])
    return fig


# ── gallery ───────────────────────────────────────────────────────────────────

def page_paths(out: Path, n_pages: int) -> list[Path]:
    """``out`` itself for one page; ``<stem>_1.png, <stem>_2.png, ...`` for more."""
    if n_pages == 1:
        return [out]
    return [out.with_name(f"{out.stem}_{i + 1}{out.suffix}") for i in range(n_pages)]


def build_gallery(json_path) -> list[Path]:
    """Build every page of the gallery defined in ``json_path``.

    Returns:
        The paths of the PNGs written.
    """
    cfg = load_config(json_path)
    plot_cfg = cfg["plot"]
    df = select_matchups(cfg)

    per_page = int(cfg["selection"].get("n_per_page", len(df)))
    n_pages = math.ceil(len(df) / per_page)
    out = BBP_DIR / cfg["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    paths = page_paths(out, n_pages)

    c = cfg["criteria"]
    cloud = ("no cloud cut" if c.get("cloud_max") is None
             else f"granule cloud < {c['cloud_max']:g} %")
    for ip, path in enumerate(paths):
        rows = df.iloc[ip * per_page:(ip + 1) * per_page]
        panels = []
        for rank, row in rows.iterrows():
            print(f"  {rank + 1:2d} {int(row.wmo)}/{int(row.cycle)}", flush=True)
            panels.append(load_panel(row, plot_cfg))
        title = (f"PACE OCI L1B around PACE/Argo matchups — Argo $b_{{bp}}$(700) ≈ "
                 f"{c['argo_target']:.1e} m$^{{-1}}$, PACE/Argo ≈ {c['ratio_target']:g}, "
                 f"|Δt| ≤ {c['dtime_max']:g} h, {cloud}  "
                 f"(ranks {ip * per_page + 1}–{ip * per_page + len(rows)})")
        fig = plot_page(panels, plot_cfg, title, out=path)
        plt.close(fig)
        n_edge = sum(p["edge"] for p in panels)
        print(f"✓ {path}  ({len(panels)} panels, {n_edge} padded at a granule edge)")
    return paths


# ── CLI ───────────────────────────────────────────────────────────────────────

#: Galleries by number: ``python l1b_gallery.py <n>``.
FIGURES = {
    1: "test gallery (galleries/test.json -> figs/l1b_gallery_test.png)",
    2: "high 1e-3 gallery, top 36 (galleries/high_1e-3.json -> "
       "figs/l1b_gallery_high_1e-3_{1,2,3}.png)",
    3: "matched 1e-3 gallery, top 36 (galleries/matched_1e-3.json -> "
       "figs/l1b_gallery_matched_1e-3_{1,2,3}.png)",
    4: "low 1e-3 gallery, top 36 (galleries/low_1e-3.json -> "
       "figs/l1b_gallery_low_1e-3_{1,2,3}.png)",
}


def main(flg):
    """Build gallery ``flg`` (see :data:`FIGURES`), or the JSON file ``flg``.

    1: the test gallery, :file:`galleries/test.json`.
    2: the high 1e-3 gallery, :file:`galleries/high_1e-3.json` (3 pages).
    3: the matched 1e-3 gallery, :file:`galleries/matched_1e-3.json` (3 pages).
    4: the low 1e-3 gallery, :file:`galleries/low_1e-3.json` (3 pages).
    """
    if isinstance(flg, str) and flg.endswith(".json"):
        build_gallery(Path(flg))
    elif int(flg) == 1:
        build_gallery(GALLERY_DIR / "test.json")
    elif int(flg) == 2:
        build_gallery(GALLERY_DIR / "high_1e-3.json")
    elif int(flg) == 3:
        build_gallery(GALLERY_DIR / "matched_1e-3.json")
    elif int(flg) == 4:
        build_gallery(GALLERY_DIR / "low_1e-3.json")
    else:
        raise ValueError(f"Unknown figure {flg}; choose from {FIGURES} or a .json")


if __name__ == "__main__":
    # python l1b_gallery.py [<n> | <file.json>]; no argument means figure 1
    main(sys.argv[1] if len(sys.argv) > 1 else 1)
