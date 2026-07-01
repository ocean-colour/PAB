"""Q&A plots for BGC-Argo profiles.

Quick diagnostic figures: the ``BBP700`` and ``CHLA`` profiles versus pressure
with the mixed-layer depth marked, so an analyst can eyeball the MLD and the
de-spiking before trusting a summary. Uses a non-interactive Matplotlib backend
so it runs headless (CI, batch).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

from pab.argo import summary as _summary

# Force the non-interactive backend before importing pyplot — these figures are
# rendered headless and, in `ingest`, alongside argopy's worker threads, where an
# interactive (Tk) backend aborts the process at teardown. Belt-and-suspenders
# with the MPLBACKEND default in ``pab/__init__.py`` (import-order independent).
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)


def plot_profile(
    pres,
    *,
    bbp700=None,
    chla=None,
    mld: float | None = None,
    despike_bbp: bool = True,
    title: str | None = None,
):
    """Plot ``BBP700`` / ``CHLA`` vs pressure with the MLD marked.

    Args:
        pres: Pressure (dbar ≈ m); the y-axis (depth, inverted).
        bbp700: Particulate backscatter profile (optional).
        chla: Chlorophyll-a profile (optional).
        mld: Mixed-layer depth to mark with a horizontal line (optional).
        despike_bbp: Overlay the 3-point moving-median de-spiked ``BBP700``.
        title: Figure title (e.g. ``"WMO 6903823 / cycle 387"``).

    Returns:
        The Matplotlib ``Figure``.
    """
    pres = np.asarray(pres, dtype=float)
    panels = [p for p in (("BBP700", bbp700), ("CHLA", chla)) if p[1] is not None]
    if not panels:
        raise ValueError("provide at least one of bbp700 / chla")

    fig, axes = plt.subplots(
        1, len(panels), figsize=(3.2 * len(panels), 4.2), sharey=True
    )
    if len(panels) == 1:
        axes = [axes]

    for ax, (name, values) in zip(axes, panels, strict=True):
        values = np.asarray(values, dtype=float)
        ax.plot(values, pres, ".-", color="0.5", label=name)
        if name == "BBP700" and despike_bbp:
            ax.plot(
                _summary.moving_median(values),
                pres,
                "-",
                color="C0",
                label="de-spiked",
            )
        if mld is not None and np.isfinite(mld):
            ax.axhline(mld, color="C3", ls="--", lw=1, label=f"MLD = {mld:.0f}")
        ax.set_xlabel(name)
        ax.legend(fontsize=7, loc="best")
        ax.grid(alpha=0.3)

    axes[0].set_ylabel("Pressure (dbar)")
    axes[0].invert_yaxis()
    if title:
        fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    return fig


def save_profile_qa(path: str | Path, pres, *, dpi: int = 100, **kwargs: Any) -> Path:
    """Render :func:`plot_profile` to ``path`` and close the figure.

    Returns:
        The written path.
    """
    fig = plot_profile(pres, **kwargs)
    path = Path(path)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
