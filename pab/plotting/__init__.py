"""Figures.

Per-matchup fit figures and scene quick-looks (~100 KB target) and population
figures (scatter / map / metric distributions).

Public API::

    from pab.plotting import fit_fig, scene, population

Implemented in Stage 6.
"""

from pab.plotting import fit_fig, population, scene
from pab.plotting.fit_fig import fit_figure
from pab.plotting.population import comparison_scatter, matchup_map
from pab.plotting.scene import scene_from_store, scene_quicklook

__all__ = [
    "fit_fig",
    "population",
    "scene",
    "fit_figure",
    "comparison_scatter",
    "matchup_map",
    "scene_from_store",
    "scene_quicklook",
]
