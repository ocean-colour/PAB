# Design PAB

## Goals

We wish to generate a document `docs/design/PAB_design.md` that describes the design of PAB and its requirements.

We expect the package to do at least the following:

- Use argopy to fetch BGC-Argo data and then
  - Perform Q&A on those data with plots
  - Calclate and record the mixed layer depth (if not provided by argopy)
  - Measure bbp and Chl-a values in the mixed layer and record + tabulate
  - Record average salinity and temperature in the mixed layer
- Match-up the Argo profiles to PACE granules
- Extract the ~10 spectra from the PACE granules for BING analysis
- Run BING on the spectra
  - Calculate the IOPs and their uncertainties
  - Generate figures and tables
  - Tabulate
- Provide summary reports on the matchup analysis
  - Include figures, tables, and text
  - Use .rst files to be published on readthedocs.io

## Claude

### Skills

Consider using the skills in .claude/skills/

## Context

Examine the following files that may help generating the design:

- The code and files in the BING Repository: https://github.com/ocean-colour/BING.  In particular all of the files in the papers/biomass folder.
- The BING paper: docs/PDFs/bing.pdf
- The Bisson et al. papers in docs/PDFs/
- The argopy documentation: https://argopy.readthedocs.io/en/stable/
- Documentation on the PACE website for:
  - the granules (Level 2 products) and
  - how to process their data in the cloud
  - any APIs to extract individual spectra instead of full granules (might also need to be done in the Cloud)
- The context.md file in this repository: docs/context.md

## Overview

Guidelines for the design document which will be named IOPtics_design.md and will be stored in docs/design/.  Keep in mind:

- You are encouraged to suggest your own design ideas 
- This document will be used to guide the development of the IOPtics package
- It will not include specific code recommendations; we will generate a separate doc for that

## Prompts

### Context

1. Read the Context section above.  Read the code, files and websites mentioned.  Generate a docs/context.md file that you can refer to which is a reduced form of the information in the files.  Add a version number and date to the file.  Log your work in the Logs section below.

### Prep

1. Start the design document by including a preamble of what it is for.  Title that section "Preamble".

   - Add any other information you think is relevant
   - Add a version number to the document (0.1)
   - Add a date to the document (today's date)
   - Add a author to the document (JXP and Claude)


### Data

1. Read this doc.  Execute the 1st task in the Data section below

## Data

We will be using two primary datasets in this Repository: BGC-Argo and PACE (Ocean Color Imager) data.  Do also provide hooks to include other in-situ datasets and satellite data in the future.

### PACE dataset

The PACE dataset is available from the Ocean Color Imager (OCI) on the NASA Earth Observing System Data and Information System (EOSDIS) Earthdata Cloud.  See the context.md file for additional information.

### BGC-Argo dataset

The BGC-Argo dataset is available from the BGC-Argo project.  See the context.md file for additional information.

### Tasks

1. Let's begin writing the data section of the design document.  Write a section called "Data" and include the following:

- A table of the datasets to be used
- A description of each dataset
- A description of how to load the datasets
- A description of how to process the datasets
- A description of how to use the datasets
- A description of how to store the datasets
- A description of how to retrieve the datasets
- A description of how to analyze the datasets

You should examine the new code in the `ocpy` Repository (on this computer) and the code in the `argopy` Repository (on this computer) to help you write the data section (name it "Data").  Log your work in the Logs section below.  If you have any questions, write them in the Q&A section below.  

### Q&A

## Analysis

We will develop a set of analysis methods that can be applied uniformly to all algorithms.  These will include:
- Calculating the IOPs from the spectra
- Calculating the uncertainties in the IOPs
- Calculating the metrics and diagnostics
- Generating figures and tables
- Generating reports and publications

For this, we will primarily use the BING package.

### Tasks

1. Please examine the BING package and generate a plan for the analysis methods.  Write the plan in the Planning document.  If you have any questions, write them in the Q&A section below. Log your work.

### Q&A

## Validation

We will develop a set of validation methods that can be applied uniformly to all algorithms.  These will include:

## Metrics

## Reporting

We will generate reports and publications on the main findings.  This will include figures, tables, and text.  These will be shared via readthedocs.io which will neccesitate .rst files.

## Logging

The "Logs" section will record Claude's work.  Please use the following format:

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

...

## Logs


### 2026-06-17 (Context #1: generated docs/context.md)

Per Context prompt #1, read the sources in the *Context* section and produced
`docs/context.md` (v1.0, 2026-06-17, authors JXP and Claude) — a distilled,
single-page reference for writing the design doc. Coverage:

- **BING** (`docs/PDFs/bing.pdf`, Prochaska & Frouin 2025): the IOP retrieval
  engine. Captured the Gordon forward model (G1=0.0949, G2=0.0794), the central
  `bb/a` physical degeneracy, the `k`=2–5 IOP model ladder (the `expb_pow`
  workhorse, GIOP/GSM as constrained variants), `emcee` MCMC + LM fitting,
  AIC/BIC model selection, posterior-percentile uncertainties, and the key
  finding that multispectral sensors recover ≤3 params while PACE/OCI can reach
  ~4–5 (bbp the most robust observable). Also summarized the BING repo layout
  and flagged `papers/biomass/` as the closest existing PACE↔BGC-Argo matchup
  template (`fitting.py::closest_Rrs`, Stoer-2024 carbon pipeline).
- **Bisson 2019/2021** (`docs/PDFs/`): the matchup methodology — MLD via the
  0.03 kg m⁻³ density threshold, 3-point moving-median de-spiking, averaging
  float bbp within the MLD, 5×5 unflagged pixel box, tight time window — and
  the warning that satellite Rrs carries a season/region-dependent bias
  (strongest in oligotrophic gyres).
- **argopy** (docs + local `../argopy`): `DataFetcher` with `ds='bgc'`,
  `src='erddap'`, `.region(...)`; `params`/`measured` kwargs; CHLA/BBP700/PSAL/
  TEMP/PRES; no public MLD accessor (use `teos10`→`SIG0` + `gsw`, or
  `reduce_profile`); `ArgoIndex` for index-first matchup pre-selection.
- **PACE/OCI**: product `PACE_OCI_L2_AOP` (v3.1, OB.DAAC), NetCDF groups
  (`geophysical_data`→Rrs/Rrs_unc/l2_flags, `navigation_data`,
  `sensor_band_parameters`→`wavelength_3d`≈172), earthaccess access pattern,
  cloud (us-west-2 S3) vs HTTPS, nearest-unflagged-pixel spectrum extraction,
  and the standard `l2_flags` ocean mask.
- A candidate-datasets table (L23, PANGAEA, GLORIA/G13, BGC-Argo, SeaBASS/NOMAD,
  MOBY, CALIOP) and a source index.

What I learned: BING's degeneracy result directly shapes PAB's validation
expectations — bbp (amplitude + slope) is the robust matchup observable, while
phytoplankton absorption is only marginally retrievable even with PACE; and the
Bisson papers already define the float-side processing recipe PAB should adopt.

Side note: the web-research sub-agents added WebFetch allow-rules to
`.claude/settings.json` (github/raw.githubusercontent/api.github) and created
`.claude/settings.local.json` (pace/nasa domains). These are benign permission
allowlists; left in place — revert if undesired.

### 2026-06-17 (Prep #1 redo: recreated the design document with a Preamble)

The design document was missing from `docs/design/` (the file logged earlier
under Prep #1/#2 was not present on disk — most likely lost since it was never
committed). Per Prep prompt #1, recreated it directly as
`docs/design/IOPtics_design.md` (v0.1, 2026-06-17, authors JXP and Claude) with
a titled **Preamble** section covering: the document's purpose (guiding,
code-free, living design reference for IOPtics/PAB), the package scope and goals
(argopy BGC-Argo fetch/Q&A/MLD/mixed-layer bbp+Chl-a+T+S, PACE matchup, ~10-Rrs
extraction, BING IOP retrieval + uncertainties, .rst reports for readthedocs,
plus hooks for future datasets/satellites), its relationship to `docs/context.md`
and the BING/ocpy/argopy packages, and basic conventions. Included the requested
version (0.1), date, and authors.