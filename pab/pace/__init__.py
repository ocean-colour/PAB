"""PACE discovery, cloud access, and spectrum extraction.

earthaccess/CMR granule discovery, lazy in-region S3 access behind an
abstraction, nearest-unflagged-pixel Rrs extraction, and l2_flags masking.

Public API::

    from pab.pace import discover, cloud, extract, flags, iop, l1b

Implemented in Stage 3 (``l1b`` is a documented future hook); ``iop`` (the
NASA-GIOP baseline comparison access) added in Stage 10b.
"""

from pab.pace import cloud, discover, extract, flags, iop, l1b

__all__ = ["cloud", "discover", "extract", "flags", "iop", "l1b"]
