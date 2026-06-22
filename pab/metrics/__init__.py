"""Comparison metrics.

Satellite/in-situ ratio, Spearman rank correlation, log-space bias and
scatter, per-fit reduced chi-squared, and BING vs NASA-L2-IOP comparison.

Public API::

    from pab.metrics import compare
    from pab.metrics import log_comparison, gather_matchups

Implemented in Stage 6.
"""

from pab.metrics import compare
from pab.metrics.compare import (
    add_oc_chl,
    add_strata,
    gather_matchups,
    log_comparison,
)
from pab.metrics.compare import (
    compare as compare_columns,
)

__all__ = [
    "compare",
    "add_oc_chl",
    "add_strata",
    "compare_columns",
    "gather_matchups",
    "log_comparison",
]
