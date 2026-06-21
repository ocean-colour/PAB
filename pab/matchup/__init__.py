"""Space + time matchup engine.

Match BGC-Argo profiles to PACE granules, select the ~10 nearest valid
spectra per qualifying profile, and write matchup records linking
float <-> granule <-> pixels.

Public API::

    from pab.matchup import engine
    from pab.matchup import build_matchups, find_matchup, MatchupConfig

Implemented in Stage 4.
"""

from pab.matchup import engine
from pab.matchup.engine import (
    Matchup,
    MatchupConfig,
    build_matchups,
    candidate_granules,
    find_matchup,
    make_matchup_id,
    qualifying_profiles,
    time_offset_hours,
    write_matchup,
)

__all__ = [
    "engine",
    "Matchup",
    "MatchupConfig",
    "build_matchups",
    "candidate_granules",
    "find_matchup",
    "make_matchup_id",
    "qualifying_profiles",
    "time_offset_hours",
    "write_matchup",
]
