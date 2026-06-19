"""Figure 3 for the PAB design document: storage & reporting architecture.

Draws the flow of PAB outputs from the analysis layer through storage to the
community-facing reporting channels:

    BING fits  ->  SQLite DB (extracted values)        ->  Reporting
               ->  Nautilus/NSF S3 (chains + figures)  ->  Reporting + downloads
               ->  Zenodo snapshot (DOI, pab_version)

Usage:
    python docs/scripts/fig_architecture.py [out.png]

Writes docs/figures/fig_architecture.png by default.
"""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "figures",
                           "fig_architecture.png")

# palette
GREY = "#ededed"
BLUE = "#d9ebff"
GREEN = "#d9f7dc"
ORANGE = "#ffedcc"
EDGE = "#333333"


def _box(ax, x, y, w, h, label, face):
    """Draw a centered, rounded box (x,y = lower-left, data coords 0..100)."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2.0",
        linewidth=1.3, edgecolor=EDGE, facecolor=face, zorder=2))
    ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
            fontsize=10.5, zorder=3)
    return (x, y, w, h)


def _arrow(ax, xy_from, xy_to):
    ax.add_patch(FancyArrowPatch(
        xy_from, xy_to, arrowstyle="-|>", mutation_scale=14,
        linewidth=1.3, color="#555555", zorder=1,
        shrinkA=2, shrinkB=2))


def main(out_path=DEFAULT_OUT):
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Source
    src = _box(ax, 3, 58, 22, 18, "BING fits\n(per matchup)", GREY)

    # Storage tier
    db = _box(ax, 37, 74, 27, 16, "SQLite DB\nextracted values", BLUE)
    s3 = _box(ax, 37, 50, 27, 16, "Nautilus / NSF S3\nchains + figures", GREEN)
    zen = _box(ax, 37, 26, 27, 16, "Zenodo snapshot\nDOI · pab_version", ORANGE)

    # Reporting tier
    rep = _box(ax, 74, 50, 23, 26,
               "Reporting\nreadthedocs\n+ Bokeh\n+ downloads", GREY)

    # arrows: source -> storage
    _arrow(ax, (src[0] + src[2], 69), (db[0], 83))
    _arrow(ax, (src[0] + src[2], 65), (s3[0], 58))
    # storage -> Zenodo (DB and S3 feed the citable snapshot)
    _arrow(ax, (db[0] + 6, db[1]), (zen[0] + 8, zen[1] + zen[3]))
    _arrow(ax, (s3[0] + 6, s3[1]), (zen[0] + 16, zen[1] + zen[3]))
    # storage -> reporting
    _arrow(ax, (db[0] + db[2], 82), (rep[0], 70))
    _arrow(ax, (s3[0] + s3[2], 58), (rep[0], 60))

    ax.set_title("PAB storage & reporting architecture", fontsize=13)

    fig.tight_layout()
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=110)
    print(f"Wrote {out_path} ({os.path.getsize(out_path)/1024:.0f} KB)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    main(out)
