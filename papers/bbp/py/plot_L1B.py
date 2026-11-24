"""
Plot the PACE OCI L1B scene around a matchup (``papers/bbp/prompts/scrutinize.md``,
Prompts/Atmospheric Corrections 3-4; decisions in Q&A/Plot L1B).

The box is set **in kilometres on the ground** (default 400 km across), not in
pixels: OCI pixels grow away from nadir (here ~2.1 km across-track against
~1.2 km along-track), so a fixed pixel count is neither square nor a fixed
size. The panels are drawn with the pixel aspect ratio that makes the box
roughly square on the ground.

Figure (``fig_L1B_<wmo>_<cycle>.png``, in ``papers/bbp/figs/``), on pixel/scan axes:
    left    TOA reflectance ``rhot`` at ~650 nm (red CCD), log colour scale;
    right   the L1B flags set in the same box: per-band saturation in the red
            CCD and in the SWIR (yes/no over all bands of each), and land.

Both panels mark the fitted PACE pixel and the nearest pixel to the Argo
profile. The L1B carries no cloud / glint / stray-light flags (those are L2
``l2_flags``); saturation and land are all it has, apart from HAM-B striping,
geolocation-quality and scan-quality flags, which are reported in the printed
summary but not drawn (they are rarely set).

The L1B granule is looked for in ``$PAB_DATA_DIR/scrutinize/<wmo>_<cycle>/l1b/``
and **downloaded there if it is absent** (~1.9 GB, a few minutes, needs the
Earthdata login in ``~/.netrc``). Pass ``download=False`` to forbid that.

Usage:
    python papers/bbp/py/plot_L1B.py                       # 5906209 / 224, 400 km box
    python papers/bbp/py/plot_L1B.py <wmo> <cycle> [half_width_km]
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap, LogNorm
from matplotlib.patches import Patch

from pab.config import DATA_DIR
from pab.pace import cloud as pcloud
from pab.pace import l1b as pl1b
from pab.viz import data as vdata

# ── defaults ──────────────────────────────────────────────────────────────────

DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"
SCRUTINIZE_DIR = Path(DATA_DIR) / "scrutinize"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "figs"

#: The matchup of the scrutinize prompts.
DEFAULT_PROFILE = (5906209, 224)

#: Wavelength of the left panel (nm); the nearest red-CCD band is used.
WAVE = 650.0

#: Half-width of the box on the ground (km): 400 km across (Q&A/Plot L1B, Q2).
HALF_WIDTH = 200.0

#: Flag categories of the right panel: code -> (label, colour).
CATEGORIES = {
    0: ("no flag", "#eeeeea"),
    1: ("red CCD saturated", "#d1495b"),
    2: ("SWIR saturated", "#2a78d6"),
    3: ("red + SWIR saturated", "#5b2a86"),
    4: ("land", "#8c6d31"),
}

PIXEL_COLOR = "#ff7f0e"      # the fitted PACE pixel
ARGO_COLOR = "#00c8ff"       # the Argo profile position

RC = {
    "font.size": 12, "axes.labelsize": 13, "axes.titlesize": 13,
    "xtick.labelsize": 11, "ytick.labelsize": 11, "legend.fontsize": 10,
    "figure.dpi": 150, "savefig.dpi": 300,
}


# ── data ──────────────────────────────────────────────────────────────────────

def find_matchup(wmo: int, cycle: int, db=None) -> dict:
    """The matchup of ``(wmo, cycle)``: granule, fitted pixel, Argo position.

    Returns a dict with ``granule_id`` (the L2 AOP granule), ``l1b_name``,
    ``scan`` / ``pixel`` (PAB ``ix`` / ``iy`` of the rank-1 pixel, 0-based),
    ``pix_lat`` / ``pix_lon`` and ``argo_lat`` / ``argo_lon``.
    """
    store = vdata.open_store(Path(db or DEFAULT_DB))
    try:
        rows = store.query(
            "SELECT m.granule_id, p.latitude AS argo_lat, p.longitude AS argo_lon, "
            "x.ix, x.iy, x.latitude AS pix_lat, x.longitude AS pix_lon "
            "FROM profiles p JOIN matchups m USING (profile_id) "
            "JOIN matchup_pixels x USING (matchup_id) "
            "WHERE p.wmo = ? AND p.cycle = ? ORDER BY x.rank LIMIT 1",
            (wmo, cycle))
    finally:
        store.close()
    if not rows:
        raise ValueError(f"No matchup pixel for wmo {wmo}, cycle {cycle}")
    r = rows[0]
    return {
        "granule_id": r["granule_id"],
        "l1b_name": pl1b.l1b_name_for_aop(r["granule_id"]),
        "scan": int(r["ix"]), "pixel": int(r["iy"]),
        "pix_lat": float(r["pix_lat"]), "pix_lon": float(r["pix_lon"]),
        "argo_lat": float(r["argo_lat"]), "argo_lon": float(r["argo_lon"]),
    }


def l1b_path(wmo: int, cycle: int, m: dict, download: bool = True,
             l1b_dir=None) -> Path:
    """The local L1B file of this matchup, downloaded first if it is absent.

    The file lives in ``l1b_dir``, by default ``SCRUTINIZE_DIR/<wmo>_<cycle>/l1b/``
    (the galleries pass the shared cache ``$PAB_DATA_DIR/L1B/``). When it is not
    there and ``download`` is true, the L1B URL is resolved from the matchup's
    AOP granule through CMR (:func:`pab.pace.l1b.l1b_source_for_aop`) and the
    granule is fetched with :func:`pab.pace.cloud.download_granule`
    (``earthaccess``, Earthdata login from ``~/.netrc``).

    Args:
        wmo, cycle: The float profile.
        m: The :func:`find_matchup` dict (``granule_id``, ``l1b_name``).
        download: Fetch a missing file; if false, a missing file raises.
        l1b_dir: Directory holding the L1B file; default
            ``SCRUTINIZE_DIR/<wmo>_<cycle>/l1b/``.

    Raises:
        FileNotFoundError: the file is absent and ``download`` is false, or
            the download did not produce it.
    """
    l1b_dir = Path(l1b_dir) if l1b_dir is not None else (
        SCRUTINIZE_DIR / f"{wmo}_{cycle}" / "l1b")
    path = l1b_dir / m["l1b_name"]
    if path.exists():
        return path
    if not download:
        raise FileNotFoundError(f"{path} is missing (download=False)")
    print(f"L1B not on disk; downloading {m['l1b_name']} (~1.9 GB) to {l1b_dir}")
    url = pl1b.l1b_source_for_aop(m["granule_id"])
    got = pcloud.download_granule(url, l1b_dir)
    if not Path(got).exists():
        raise FileNotFoundError(f"download of {url} did not produce {path}")
    return Path(got)


def _great_circle_km(lat1, lon1, lat2, lon2):
    """Haversine distance (km); arrays broadcast."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def load_l1b_box(path, scan: int, pixel: int, half_width: float = HALF_WIDTH,
                 wave: float = WAVE) -> dict:
    """Read the box of ``+/- half_width`` km around ``(scan, pixel)``.

    The box limits are the pixels within ``half_width`` km of the matchup
    pixel along its own scan line (across-track) and along its own pixel
    column (along-track). Only the box is read from the 1.9 GB file. The box
    is clipped at the granule edges, so it can be smaller than requested.

    Returns a dict with the box limits ``s0, s1, p0, p1`` (half-open),
    ``rhot`` (reflectance at the red band nearest ``wave``), ``band_wave``,
    ``lat``, ``lon``, the boolean maps ``sat_red``, ``sat_swir``, ``land``,
    the red wavelengths saturated anywhere in the box (``sat_red_waves``) and
    the counts of the flags that are not drawn (``other_flags``).
    """
    with netCDF4.Dataset(path) as ds:
        obs = ds["observation_data"]
        geo = ds["geolocation_data"]
        red_wave = np.asarray(ds["sensor_band_parameters"]["red_wavelength"][:])
        lat0, lon0 = geo["latitude"][scan, pixel], geo["longitude"][scan, pixel]
        d_row = _great_circle_km(np.ma.filled(geo["latitude"][scan, :], np.nan),
                                 np.ma.filled(geo["longitude"][scan, :], np.nan),
                                 lat0, lon0)
        d_col = _great_circle_km(np.ma.filled(geo["latitude"][:, pixel], np.nan),
                                 np.ma.filled(geo["longitude"][:, pixel], np.nan),
                                 lat0, lon0)
        inp, ins = np.nonzero(d_row <= half_width)[0], np.nonzero(d_col <= half_width)[0]
        p0, p1 = int(inp.min()), int(inp.max()) + 1
        s0, s1 = int(ins.min()), int(ins.max()) + 1
        box = (slice(s0, s1), slice(p0, p1))
        ib = int(np.argmin(np.abs(red_wave - wave)))

        rhot = np.ma.filled(obs["rhot_red"][(ib, *box)].astype(float), np.nan)
        qred = np.ma.filled(obs["qual_red"][(slice(None), *box)], 0)
        qswir = np.ma.filled(obs["qual_SWIR"][(slice(None), *box)], 0)
        gq = np.ma.filled(geo["quality_flag"][box], 0)
        sq = np.ma.filled(
            ds["scan_line_attributes"]["scan_quality_flags"][s0:s1], 0)
        out = {
            "s0": s0, "s1": s1, "p0": p0, "p1": p1,
            "rhot": rhot, "band_wave": float(red_wave[ib]),
            "lat": np.ma.filled(geo["latitude"][box], np.nan),
            "lon": np.ma.filled(geo["longitude"][box], np.nan),
            # bit 1 = saturation (qual_red, qual_SWIR), over all bands
            "sat_red": ((qred & 1) > 0).any(axis=0),
            "sat_swir": ((qswir & 1) > 0).any(axis=0),
            # watermask: 1 = water
            "land": np.ma.filled(geo["watermask"][box], 1) == 0,
            "sat_red_waves": red_wave[((qred & 1) > 0).any(axis=(1, 2))],
            "other_flags": {
                "HAM-B striping (qual_red bit 2)": int(((qred & 2) > 0).any(axis=0).sum()),
                "geolocation quality_flag": int((gq > 0).sum()),
                "scan_quality_flags (scans)": int((sq > 0).sum()),
            },
        }
    return out


def flag_categories(box: dict) -> np.ndarray:
    """The right panel's category code per pixel (see :data:`CATEGORIES`)."""
    cat = box["sat_red"].astype(int) + 2 * box["sat_swir"].astype(int)
    cat[box["land"]] = 4
    return cat


# ── figure ────────────────────────────────────────────────────────────────────

def _mark(ax, m, box, argo_sp):
    """The fitted pixel and the Argo position on ``ax``."""
    ax.plot(m["pixel"], m["scan"], marker="o", ms=11, mfc="none",
            mec=PIXEL_COLOR, mew=2.0, ls="none", label="PACE pixel")
    if argo_sp is not None:
        ax.plot(argo_sp[1], argo_sp[0], marker="+", ms=11, color=ARGO_COLOR,
                mew=2.0, ls="none", label="Argo profile")
    ax.set_xlim(box["p0"] - 0.5, box["p1"] - 0.5)
    ax.set_ylim(box["s1"] - 0.5, box["s0"] - 0.5)       # scan 0 at the top
    ax.set_xlabel("pixel")


def plot_l1b(wmo: int, cycle: int, half_width: float = HALF_WIDTH, out=None,
             db=None, wave: float = WAVE, download: bool = True):
    """Two-panel L1B figure for one matchup: reflectance at ~650 nm, and flags.

    Args:
        wmo, cycle: The float profile.
        half_width: Half-width of the box on the ground (km).
        out: Path to save the PNG; nothing is saved if ``None``.
        db: Path to ``pab.db``; default :data:`DEFAULT_DB`.
        wave: Wavelength of the left panel (nm).
        download: Download the L1B granule if it is not on disk.

    Returns:
        ``(fig, m, box)``: the Figure, the matchup dict and the data box.
    """
    m = find_matchup(wmo, cycle, db)
    box = load_l1b_box(l1b_path(wmo, cycle, m, download), m["scan"], m["pixel"],
                       half_width, wave)
    extent = (box["p0"] - 0.5, box["p1"] - 0.5, box["s1"] - 0.5, box["s0"] - 0.5)

    # nearest L1B pixel to the Argo profile, if it falls inside the box
    d_argo = _great_circle_km(box["lat"], box["lon"], m["argo_lat"], m["argo_lon"])
    j = np.unravel_index(np.nanargmin(d_argo), d_argo.shape)
    argo_sp = (box["s0"] + j[0], box["p0"] + j[1]) if d_argo[j] < 3.0 else None

    # size of the box on the ground, through the matchup pixel
    js, jp = m["scan"] - box["s0"], m["pixel"] - box["p0"]
    km_x = _great_circle_km(box["lat"][js, 0], box["lon"][js, 0],
                            box["lat"][js, -1], box["lon"][js, -1])
    km_y = _great_circle_km(box["lat"][0, jp], box["lon"][0, jp],
                            box["lat"][-1, jp], box["lon"][-1, jp])

    # km per scan / km per pixel: draws the box square on the ground
    aspect = (km_y / (box["s1"] - box["s0"] - 1)) / (km_x / (box["p1"] - box["p0"] - 1))
    box["km_x"], box["km_y"] = float(km_x), float(km_y)

    cat = flag_categories(box)
    codes = sorted(CATEGORIES)
    cmap = ListedColormap([CATEGORIES[c][1] for c in codes])
    norm = BoundaryNorm(np.arange(len(codes) + 1) - 0.5, cmap.N)

    lat_h = "S" if m["pix_lat"] < 0 else "N"
    lon_h = "W" if m["pix_lon"] < 0 else "E"
    where = (f"{abs(m['pix_lat']):.2f}° {lat_h}, {abs(m['pix_lon']):.2f}° {lon_h}"
             f"   (scan {m['scan']}, pixel {m['pixel']})")

    with mpl.rc_context(RC):
        fig, (ax, axf) = plt.subplots(1, 2, figsize=(12.5, 6.2),
                                      constrained_layout=True, sharey=True)

        im = ax.imshow(box["rhot"], extent=extent, cmap="gray", interpolation="nearest",
                       aspect=aspect, norm=LogNorm(vmin=0.03, vmax=1.0))
        cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02, extend="both")
        cb.set_label(r"TOA reflectance $\rho_t$")
        _mark(ax, m, box, argo_sp)
        ax.set_ylabel("scan")
        ax.set_title(f"(a) L1B $\\rho_t$ at {box['band_wave']:.1f} nm", loc="left")
        ax.legend(loc="upper left", framealpha=0.9)

        axf.imshow(cat, extent=extent, cmap=cmap, norm=norm, interpolation="nearest",
                   aspect=aspect)
        _mark(axf, m, box, argo_sp)
        handles = [Patch(fc=CATEGORIES[c][1], ec="#888888",
                         label=f"{CATEGORIES[c][0]}  ({100 * np.mean(cat == c):.1f} %)")
                   for c in codes]
        axf.legend(handles=handles, loc="upper left", framealpha=0.9)
        axf.set_title("(b) L1B flags (saturation in any band; land)", loc="left")

        fig.suptitle(f"{wmo} / {cycle}   {m['l1b_name']}\n"
                     f"PACE pixel at {where};  box ≈ {km_x:.0f} × {km_y:.0f} km",
                     fontsize=12)
        if out is not None:
            fig.savefig(out)
    return fig, m, box


def summarize(m: dict, box: dict) -> None:
    """Print what the box holds, at and around the fitted pixel."""
    js, jp = m["scan"] - box["s0"], m["pixel"] - box["p0"]
    cat = flag_categories(box)
    print(f"L1B: {m['l1b_name']}")
    print(f"box: scans {box['s0']}-{box['s1'] - 1}, pixels {box['p0']}-{box['p1'] - 1}"
          f"  ({box['km_x']:.0f} x {box['km_y']:.0f} km; "
          f"{box['km_x'] / (box['p1'] - box['p0'] - 1):.2f} km/pixel across-track, "
          f"{box['km_y'] / (box['s1'] - box['s0'] - 1):.2f} km/scan)")
    print(f"rhot({box['band_wave']:.1f} nm) at the pixel = {box['rhot'][js, jp]:.4f}; "
          f"box median = {np.nanmedian(box['rhot']):.3f}")
    for c, (label, _) in CATEGORIES.items():
        print(f"  {label:<22s} {100 * np.mean(cat == c):6.2f} %")
    print(f"flag at the pixel: {CATEGORIES[int(cat[js, jp])][0]}")
    yy, xx = np.nonzero(box["sat_red"] | box["sat_swir"])
    if yy.size:
        d = _great_circle_km(box["lat"][yy, xx], box["lon"][yy, xx],
                             box["lat"][js, jp], box["lon"][js, jp])
        print(f"nearest saturated pixel: {d.min():.0f} km away")
    w = box["sat_red_waves"]
    if w.size:
        print(f"red bands saturated in the box: {w.min():.1f}-{w.max():.1f} nm ({w.size} bands)")
    for name, n in box["other_flags"].items():
        print(f"  not drawn: {name}: {n} set")


# ── main ──────────────────────────────────────────────────────────────────────

def main(wmo: int, cycle: int, half_width: float = HALF_WIDTH):
    """Make the figure for ``(wmo, cycle)`` and print the summary."""
    DEFAULT_OUT_DIR.mkdir(exist_ok=True)
    out = DEFAULT_OUT_DIR / f"fig_L1B_{wmo}_{cycle}.png"
    fig, m, box = plot_l1b(wmo, cycle, half_width, out=out)
    plt.close(fig)
    summarize(m, box)
    print(f"✓ {out}")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        main(int(sys.argv[1]), int(sys.argv[2]),
             *(float(a) for a in sys.argv[3:4]))
    else:
        main(*DEFAULT_PROFILE)
