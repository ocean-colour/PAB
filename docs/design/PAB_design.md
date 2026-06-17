# IOPtics Design Document

**Version:** 0.1
**Date:** 2026-06-17
**Authors:** JXP and Claude

---

## Preamble

This document describes the design and requirements of **IOPtics** (developed in
the **PAB** repository), a Python package for **matchup analyses between PACE
satellite ocean-color observations and BGC-Argo autonomous-float data**.

### Purpose

This is the guiding reference for the development of the IOPtics package. It
captures *what* the package must do and *how* its pieces fit together, so that
implementation can proceed against a shared, agreed design.

- It is a **design document**, not a code specification: it deliberately avoids
  specific code recommendations (function signatures, class hierarchies, etc.).
  A separate document will cover implementation details.
- It is a **living document**. Sections will be added and revised as the design
  matures; the version number at the top will be incremented accordingly.

### Scope and goals

IOPtics is intended to, at minimum:

- **Fetch and process BGC-Argo data** (via `argopy`): perform Q&A with plots,
  compute and record the mixed-layer depth (MLD) when not supplied, measure and
  tabulate `bbp` and Chl-a within the mixed layer, and record average salinity
  and temperature in the mixed layer.
- **Match BGC-Argo profiles to PACE granules** in space and time.
- **Extract the ~10 Rrs spectra** nearest each float from the PACE granules for
  IOP analysis.
- **Run BING** on the extracted spectra to retrieve the inherent optical
  properties (IOPs: non-water absorption and particulate backscattering) and
  their uncertainties, and generate the associated figures and tables.
- **Produce summary reports** of the matchup analysis — figures, tables, and
  text — published to readthedocs.io via `.rst` files.

The package should also provide **hooks to incorporate additional in-situ
datasets and other satellites** in the future, rather than hard-coding the
PACE/BGC-Argo pair.

### Relationship to other documents and packages

- A distilled reference of the source material (the BING paper, the Bisson et
  al. matchup papers, and the argopy / PACE / earthaccess documentation) is
  maintained in [`docs/context.md`](../context.md). The design draws on it
  throughout.
- Core scientific machinery is reused from existing packages: **BING**
  (Bayesian IOP retrieval), **ocpy** (ocean-color utilities, dataset loaders),
  and **argopy** (BGC-Argo access).

### Conventions

- Wavelengths in nanometres (nm); IOPs in m⁻¹; `Rrs` in sr⁻¹.
- Argo variables referred to by their standard uppercase names (e.g. `CHLA`,
  `BBP700`, `PSAL`, `TEMP`, `PRES`).
- Dates in ISO format (YYYY-MM-DD).

---

*This document is under active development; sections beyond the Preamble will be
added in subsequent revisions.*
