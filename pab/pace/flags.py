"""``l2_flags`` bitmask decoding and quality masking for PACE/OCI L2.

Self-contained (NumPy only) so it unit-tests offline. The bit positions match
the canonical SeaDAS/OB.DAAC ``l2_flags`` definition (and
``remote_sensing.netcdf.oc.L2_FLAGS``); PAB's default screen is the standard
ocean mask named in the design (``docs/design/PAB_design.md`` → *Processing*).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike

#: Canonical ``l2_flags`` bit positions (SeaDAS/OB.DAAC; matches
#: ``remote_sensing.netcdf.oc.L2_FLAGS``).
L2_FLAG_BITS: dict[str, int] = {
    "ATMFAIL": 0,
    "LAND": 1,
    "PRODWARN": 2,
    "HIGLINT": 3,
    "HILT": 4,
    "HISATZEN": 5,
    "COASTZ": 6,
    "STRAYLIGHT": 8,
    "CLDICE": 9,
    "COCCOLITH": 10,
    "TURBIDW": 11,
    "HISOLZEN": 12,
    "LOWLW": 14,
    "CHLFAIL": 15,
    "NAVWARN": 16,
    "ABSAER": 17,
    "MAXAERITER": 19,
    "MODGLINT": 20,
    "CHLWARN": 21,
    "ATMWARN": 22,
    "SEAICE": 24,
    "NAVFAIL": 25,
    "FILTER": 26,
    "BOWTIEDEL": 28,
    "HIPOL": 29,
    "PRODFAIL": 30,
    "SPARE": 31,
}

#: PAB's standard ocean screen (design *Processing* section). A pixel is
#: rejected if *any* of these bits is set.
STANDARD_OCEAN_MASK: tuple[str, ...] = (
    "ATMFAIL",
    "LAND",
    "HIGLINT",
    "HILT",
    "STRAYLIGHT",
    "CLDICE",
    "COCCOLITH",
    "HISATZEN",
    "HISOLZEN",
    "LOWLW",
    "CHLFAIL",
    "NAVFAIL",
    "MAXAERITER",
)


def flag_value(names: Iterable[str]) -> int:
    """Combine flag names into a single integer bitmask.

    Args:
        names: Flag names from :data:`L2_FLAG_BITS`.

    Returns:
        The OR of the named bits.

    Raises:
        KeyError: on an unknown flag name.
    """
    value = 0
    for name in names:
        value |= 1 << L2_FLAG_BITS[name]
    return value


def decode(value: int) -> tuple[str, ...]:
    """Return the flag names set in a scalar ``l2_flags`` value (sorted by bit)."""
    return tuple(
        name
        for name, bit in sorted(L2_FLAG_BITS.items(), key=lambda kv: kv[1])
        if value & (1 << bit)
    )


def is_set(l2_flags: ArrayLike, name: str) -> np.ndarray:
    """Boolean array: is flag ``name`` set in each element of ``l2_flags``?"""
    if name not in L2_FLAG_BITS:
        raise KeyError(f"Unknown flag {name!r}; valid: {list(L2_FLAG_BITS)}")
    flags = np.asarray(l2_flags)
    return (flags & (1 << L2_FLAG_BITS[name])) != 0


def flagged_mask(
    l2_flags: ArrayLike, mask_flags: Sequence[str] = STANDARD_OCEAN_MASK
) -> np.ndarray:
    """Boolean mask, ``True`` where a pixel is rejected (any masked bit set).

    Args:
        l2_flags: Integer ``l2_flags`` array.
        mask_flags: Flag names that reject a pixel (default the standard ocean
            mask).

    Returns:
        Boolean array, ``True`` = bad / masked.
    """
    flags = np.asarray(l2_flags)
    reject = flag_value(mask_flags)
    return (flags & reject) != 0


def good_mask(
    l2_flags: ArrayLike, mask_flags: Sequence[str] = STANDARD_OCEAN_MASK
) -> np.ndarray:
    """Boolean mask, ``True`` where a pixel is **unflagged** (passes the screen)."""
    return ~flagged_mask(l2_flags, mask_flags)
