"""SQLite storage layer (the storage seam).

Holds the schema and a thin access API for the extracted-value tables:
mixed-layer summaries, the matchup index, and namespaced fit results. Bulky
artifacts (MCMC chains, figures) live in files keyed by ID, not here.

Implemented in Stage 1.
"""
