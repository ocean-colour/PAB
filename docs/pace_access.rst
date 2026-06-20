PACE access & spectrum extraction
=================================

PAB reads PACE/OCI Level-2 AOP granules **cloud-first** — located and read from
the NASA Earthdata Cloud (in-region AWS ``us-west-2``) without bulk-downloading
— and extracts the ~10 nearest **unflagged** ``Rrs`` spectra around each float.
Implemented in the :mod:`pab.pace` subpackage.

Pipeline
--------

#. **Discover** (:mod:`pab.pace.discover`) — a CMR query by short name, bounding
   box, time window, and cloud-cover range
   (``earthaccess.search_data``), turned into a granule ``DataFrame``
   (id / footprint / time / cloud-cover / URL) via
   ``remote_sensing.download.earthaccess.build_granule_table`` and persisted to
   the ``granules`` table.
#. **Open** (:mod:`pab.pace.cloud`) — :func:`~pab.pace.cloud.open_granule`
   returns a **canonical granule dataset** regardless of source, so extraction
   is source-agnostic.
#. **Screen & extract** (:mod:`pab.pace.flags`, :mod:`pab.pace.extract`) —
   decode ``l2_flags``, build the standard ocean mask, select the nearest
   unflagged pixels, and read their ``Rrs(λ)`` / ``Rrs_unc(λ)`` spectra.
#. **Noise** — :func:`pab.pace.extract.pace_noise_vector` wraps
   ``ocpy.satellites.pace.gen_noise_vector`` for the fit's measurement noise.

Canonical granule dataset
--------------------------

Both the cloud and local readers produce the same in-memory layout, so the
nearest-pixel logic differs only in its data source:

* dims ``(x, y, wl)``: ``Rrs``, ``Rrs_unc``;
* 2-D coordinates ``latitude`` / ``longitude`` (``x, y``);
* ``wavelength`` (``wl``);
* a ``l2_flags`` (``x, y``) data variable.

This reuses ``ocpy.pace.io.load_oci_l2`` (which returns the dataset plus the
``l2_flags`` array); :func:`pab.pace.cloud.to_granule_ds` attaches the flags.

Cloud read: lazy S3 (a) vs OPeNDAP (b)
--------------------------------------

The design keeps two read mechanisms open; ``open_granule(..., backend=...)``
selects between them.

**(a) Lazy ``xarray`` over S3** *(default)*. In-region, the granule is opened as
a remote object and only the requested bytes are fetched, so a nearest-pixel
read transfers a single spectrum rather than the full cube. PAB obtains
temporary DAAC credentials and a file-like S3 object via ``earthaccess.open``
and reads the netCDF groups into the canonical layout.

* *Pros:* reuses the existing ``ocpy`` / ``remote_sensing`` readers unchanged
  (only the file handle is remote); full control over pixel selection and QC;
  fastest in-region.
* *Cons:* still opens the granule's coordinate/variable metadata; efficiency
  depends on the file's internal chunking; needs S3 credential handling.

**(b) OPeNDAP server-side subsetting** *(future)*. OB.DAAC exposes a Hyrax
OPeNDAP endpoint that returns only the requested variable and index slice.

* *Pros:* minimal transfer; works in- or out-of-region; no S3 credential
  plumbing.
* *Cons:* per-request server-side latency / reliability; index-based subsetting
  still needs the lat/lon arrays first to locate the nearest pixel.

PAB starts with **(a)** (maximizing reuse of the in-region readers) while
keeping discovery and pixel-selection factored so **(b)** can slot in as an
alternative backend (``backend="opendap"`` is currently a documented
``NotImplementedError``).

Quality screening (``l2_flags``)
--------------------------------

:mod:`pab.pace.flags` decodes the SeaDAS/OB.DAAC ``l2_flags`` bitmask (bit
positions in :data:`~pab.pace.flags.L2_FLAG_BITS`, matching
``remote_sensing.netcdf.oc``). PAB's default screen,
:data:`~pab.pace.flags.STANDARD_OCEAN_MASK`, rejects a pixel if any of
``ATMFAIL, LAND, HIGLINT, HILT, STRAYLIGHT, CLDICE, COCCOLITH, HISATZEN,
HISOLZEN, LOWLW, CHLFAIL, NAVFAIL, MAXAERITER`` is set. Nearest-pixel selection
considers only pixels that pass this screen.

Rrs source: L2 AOP vs PAB-derived L1B
-------------------------------------

By default the fit consumes the **PACE L2 AOP** ``Rrs`` / ``Rrs_unc``. The
design also allows **deriving ``Rrs`` from PACE L1B** with an in-house algorithm;
that path is a documented hook (:mod:`pab.pace.l1b`, raising
``NotImplementedError`` for now) whose provenance tag is
``PAB_L1B:<algorithm/version>`` vs ``L2_AOP``. Either source feeds the *same*
downstream fitting pipeline.

API reference
-------------

.. automodule:: pab.pace.discover
   :members:

.. automodule:: pab.pace.cloud
   :members:

.. automodule:: pab.pace.extract
   :members:

.. automodule:: pab.pace.flags
   :members:

.. automodule:: pab.pace.l1b
   :members:
