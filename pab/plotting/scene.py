"""Per-matchup scene quick-look (Stage 6).

A small PNG of the PACE scene around the float for visual QC: a single-band
``Rrs`` thumbnail of the granule neighbourhood with the **Argo location marked**,
the **analyzed (matchup) pixels highlighted**, and the ``l2_flags`` mask shown
(flagged pixels greyed). It makes the granule-quality assessment checkable at a
glance — was the float under cloud/glint, and which pixels fed the fit.

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


def locate_float_pixel(ds, lat: float, lon: float) -> tuple[int, int]:
    """Return the ``(ix, iy)`` of the granule pixel nearest ``(lat, lon)``."""
    from pab.pace.extract import haversine_km

    lats = np.asarray(ds["latitude"].values, dtype=float)
    lons = np.asarray(ds["longitude"].values, dtype=float)
    dist = haversine_km(lats, lons, lat, lon)
    ix, iy = np.unravel_index(int(np.nanargmin(dist)), dist.shape)
    return int(ix), int(iy)


def scene_quicklook(
    ds,
    target_lat: float,
    target_lon: float,
    *,
    pixels=None,
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
        band: Wavelength (nm) to display (nearest available is used).
        mask_flags: ``l2_flags`` names that grey out a pixel.
        outfile: If given, the figure is saved here (PNG) and the path returned.
        dpi: Output DPI (kept low for the ~100 KB budget).
        title: Optional figure title.

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt

    lats = np.asarray(ds["latitude"].values, dtype=float)
    lons = np.asarray(ds["longitude"].values, dtype=float)
    wave = np.asarray(ds["wavelength"].values, dtype=float)
    b = int(np.argmin(np.abs(wave - band)))
    rrs = np.asarray(ds["Rrs"].isel(wl=b).values, dtype=float)
    bad = _flags.flagged_mask(np.asarray(ds["l2_flags"].values), mask_flags)
    masked = np.ma.array(rrs, mask=bad)

    fig, ax = plt.subplots(figsize=(5, 4.2))
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("0.6")  # flagged pixels greyed
    pc = ax.pcolormesh(lons, lats, masked, shading="nearest", cmap=cmap)
    fig.colorbar(pc, ax=ax, label=f"Rrs({wave[b]:.0f} nm) [sr$^{{-1}}$]")

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
    if title:
        ax.set_title(title, fontsize=9)
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
