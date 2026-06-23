"""Per-matchup scene quick-look (Stage 6).

A small PNG of the PACE scene around the float for visual QC: by default a
**false-color RGB composite** of the granule neighbourhood (``Rrs`` at three
wavelengths mapped to R/G/B), with the **Argo location marked**, the **analyzed
(matchup) pixels highlighted**, and the ``l2_flags`` mask shown (flagged pixels
greyed). A single-band view (``mode="band"``, with a colorbar) is also available.
It makes the granule-quality assessment checkable at a glance — was the float
under cloud/glint, and which pixels fed the fit.

Pure NumPy + Matplotlib + :mod:`pab.pace.flags` (no ``bing``); the granule is the
canonical dataset from :func:`pab.pace.cloud.open_granule`, so the store wrapper
is mockable offline via the ``opener=`` seam.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pab.pace import flags as _flags

#: Default size budget (bytes) for a quick-look PNG.
SIZE_BUDGET = 100 * 1024

#: Wavelengths (nm) mapped to (Red, Green, Blue) for the false-color composite.
RGB_WAVES: tuple[float, float, float] = (645.0, 555.0, 470.0)

#: RGBA used for flagged (and non-finite) pixels in the composite.
_FLAG_RGBA = (0.6, 0.6, 0.6, 1.0)


def locate_float_pixel(ds, lat: float, lon: float) -> tuple[int, int]:
    """Return the ``(ix, iy)`` of the granule pixel nearest ``(lat, lon)``."""
    from pab.pace.extract import haversine_km

    lats = np.asarray(ds["latitude"].values, dtype=float)
    lons = np.asarray(ds["longitude"].values, dtype=float)
    dist = haversine_km(lats, lons, lat, lon)
    ix, iy = np.unravel_index(int(np.nanargmin(dist)), dist.shape)
    return int(ix), int(iy)


def _stretch(channel, good, *, p_hi: float = 99.0, gamma: float = 0.8):
    """Scale a channel to [0, 1] by a high-percentile stretch + gamma."""
    channel = np.asarray(channel, dtype=float)
    finite = good & np.isfinite(channel)
    hi = np.percentile(channel[finite], p_hi) if finite.any() else np.nan
    if not np.isfinite(hi) or hi <= 0:
        hi = np.nanmax(channel) if np.isfinite(channel).any() else 1.0
    hi = hi if (np.isfinite(hi) and hi > 0) else 1.0
    return np.clip(np.nan_to_num(channel) / hi, 0.0, 1.0) ** gamma


def false_color_rgba(ds, *, rgb_waves=RGB_WAVES, mask_flags=_flags.STANDARD_OCEAN_MASK):
    """Build an ``(x, y, 4)`` RGBA composite from ``Rrs`` at three wavelengths.

    Each of ``rgb_waves`` (R, G, B) selects the nearest ``Rrs`` band; each channel
    is independently percentile-stretched to [0, 1]. Flagged / non-finite pixels
    are set to :data:`_FLAG_RGBA` (grey).

    Returns:
        ``(rgba, used_waves)`` — the RGBA array and the actual band wavelengths.
    """
    wave = np.asarray(ds["wavelength"].values, dtype=float)
    rrs = np.asarray(ds["Rrs"].values, dtype=float)  # (x, y, wl)
    bad = _flags.flagged_mask(np.asarray(ds["l2_flags"].values), mask_flags)
    good = ~bad
    nx, ny = rrs.shape[0], rrs.shape[1]
    rgba = np.ones((nx, ny, 4), dtype=float)
    used = []
    for c, w in enumerate(rgb_waves):
        b = int(np.argmin(np.abs(wave - w)))
        used.append(float(wave[b]))
        rgba[..., c] = _stretch(rrs[..., b], good)
    rgba[bad] = _FLAG_RGBA
    return rgba, tuple(used)


def scene_quicklook(
    ds,
    target_lat: float,
    target_lon: float,
    *,
    pixels=None,
    mode: str = "rgb",
    rgb_waves=RGB_WAVES,
    band: float = 442.0,
    mask_flags=_flags.STANDARD_OCEAN_MASK,
    outfile=None,
    dpi: int = 100,
    title: str | None = None,
):
    """Render the scene quick-look for a granule around a float.

    Args:
        ds: Canonical granule dataset (dims ``x, y, wl``).
        target_lat, target_lon: Float position (a red star).
        pixels: Iterable of analyzed-pixel dicts with ``ix``/``iy`` (white
            circles); if ``None``, the nearest pixel is highlighted.
        mode: ``"rgb"`` (default) for the false-color composite, or ``"band"``
            for a single-band ``Rrs`` map with a colorbar.
        rgb_waves: ``(R, G, B)`` wavelengths (nm) for the composite.
        band: Wavelength (nm) shown in ``mode="band"`` (nearest available).
        mask_flags: ``l2_flags`` names that grey out / mask a pixel.
        outfile: If given, the figure is saved here (PNG) and the path returned.
        dpi: Output DPI (kept low for the ~100 KB budget).
        title: Optional figure title.

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt

    lats = np.asarray(ds["latitude"].values, dtype=float)
    lons = np.asarray(ds["longitude"].values, dtype=float)
    fig, ax = plt.subplots(figsize=(5, 4.2))

    if mode == "rgb":
        rgba, used = false_color_rgba(ds, rgb_waves=rgb_waves, mask_flags=mask_flags)
        # RGB on the (curvilinear) lat/lon mesh: draw a QuadMesh, then override
        # its per-cell facecolors (set_array(None) disables scalar colormapping).
        pc = ax.pcolormesh(lons, lats, np.zeros(lats.shape), shading="nearest")
        pc.set_array(None)
        pc.set_facecolor(rgba.reshape(-1, 4))
        ax.set_facecolor("0.6")
        sub = "false-color R/G/B = " + "/".join(f"{w:.0f}" for w in used) + " nm"
    else:
        wave = np.asarray(ds["wavelength"].values, dtype=float)
        b = int(np.argmin(np.abs(wave - band)))
        rrs = np.asarray(ds["Rrs"].isel(wl=b).values, dtype=float)
        bad = _flags.flagged_mask(np.asarray(ds["l2_flags"].values), mask_flags)
        cmap = plt.get_cmap("viridis").copy()
        cmap.set_bad("0.6")
        pc = ax.pcolormesh(
            lons, lats, np.ma.array(rrs, mask=bad), shading="nearest", cmap=cmap
        )
        fig.colorbar(pc, ax=ax, label=f"Rrs({wave[b]:.0f} nm) [sr$^{{-1}}$]")
        sub = f"Rrs({wave[b]:.0f} nm)"

    if pixels is None:
        ix, iy = locate_float_pixel(ds, target_lat, target_lon)
        pixels = [{"ix": ix, "iy": iy}]
    ax.scatter(
        [float(lons[int(p["ix"]), int(p["iy"])]) for p in pixels],
        [float(lats[int(p["ix"]), int(p["iy"])]) for p in pixels],
        s=40,
        facecolors="none",
        edgecolors="w",
        linewidths=1.2,
        label="analyzed pixels",
    )
    ax.plot(target_lon, target_lat, "r*", ms=16, label="float")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title(f"{title}\n{sub}" if title else sub, fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return outfile
    return fig


def scene_from_store(store, matchup_id: str, *, opener=None, outfile=None, **kwargs):
    """Build the quick-look for a stored matchup (opens its granule).

    Reads the matchup's float position, its analyzed pixels, and the granule URL
    from the DB, opens the granule (mockable via ``opener``), and calls
    :func:`scene_quicklook`.
    """
    from pab.pace import cloud

    m = store.query(
        "SELECT mch.granule_id, g.data_url, p.latitude, p.longitude "
        "FROM matchups mch "
        "JOIN profiles p ON p.profile_id = mch.profile_id "
        "JOIN granules g ON g.granule_id = mch.granule_id "
        "WHERE mch.matchup_id = ?",
        (matchup_id,),
    )
    if not m:
        raise ValueError(f"no matchup {matchup_id!r}")
    m = m[0]
    pixels = store.query(
        "SELECT ix, iy FROM matchup_pixels WHERE matchup_id = ? ORDER BY rank",
        (matchup_id,),
    )
    source = m["data_url"] or m["granule_id"]
    ds = cloud.open_granule(source, opener=opener)
    return scene_quicklook(
        ds,
        m["latitude"],
        m["longitude"],
        pixels=pixels,
        outfile=outfile,
        title=kwargs.pop("title", matchup_id),
        **kwargs,
    )
