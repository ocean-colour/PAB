"""BING fitting wrapper.

Configure the model pair (ExpBricaud + Pow) and priors, run the
LM warm-start -> MCMC pipeline, extract scalar IOPs + uncertainties into
namespaced columns, and write chains/provenance keyed by ID.

Implemented in Stage 5.
"""
