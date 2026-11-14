"""CDOM qualitative/correlative comparison (chl_cdom_prompt_2.md Task 2, per C1-C4).

Standalone analysis scripts over ``pab.db`` — not part of the ``pab`` package's
report pipeline, not published to Read the Docs. Reuses
:func:`pab.matchup.chl.data.load_chl_matchups` (the CDOM population is a
subset of the same joined matchup table); see :mod:`pab.matchup.cdom.data` for
the CDOM-specific validity filter and the C3 quantity caveat every figure
carries. See :mod:`pab.matchup.cdom.run_all` to reproduce the full set.
"""
