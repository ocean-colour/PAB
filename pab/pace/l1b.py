"""PAB-derived ``Rrs`` from PACE Level-1B — documented hook (future).

The design treats the ``Rrs`` source as a **pluggable upstream stage**: the BING
fit consumes an ``Rrs(λ)`` spectrum and its per-band uncertainty regardless of
whether they arrive from the **PACE L2 AOP** product (the default; see
:mod:`pab.pace.cloud` / :mod:`pab.pace.extract`) or from a PAB in-house
**L1B → Rrs** algorithm (custom atmospheric correction / uncertainty model).

This module is the placeholder for that second path. Implementing it (Stage 9)
means producing, from L1B radiances, the same ``(wavelength, Rrs, Rrs_unc)``
triple the L2 path yields, and recording the provenance source
``PAB_L1B:<algorithm/version>`` (vs ``L2_AOP``) with the fit so downstream
analysis is unchanged.
"""

from __future__ import annotations

#: Provenance tag prefix for fits whose Rrs came from a PAB L1B algorithm.
RRS_SOURCE_PREFIX = "PAB_L1B"

#: Provenance tag for the default NASA L2 AOP Rrs source.
RRS_SOURCE_L2 = "L2_AOP"


def rrs_from_l1b(*args, **kwargs):
    """Derive ``Rrs``/``Rrs_unc`` from PACE L1B radiances (not yet implemented).

    Raises:
        NotImplementedError: always — this is a Stage 9 hook. See the module
            docstring for the intended contract.
    """
    raise NotImplementedError(
        "PAB L1B -> Rrs is a future capability (design 'Rrs source' section). "
        "The L2 AOP path (pab.pace.cloud/extract) is the current default."
    )
