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
2. Read this doc.  Execute the 2nd task in the Data section below
3. Read this doc.  Execute the 3rd task in the Data section below

### Analysis

1. Read this doc.  Execute the 1st task in the Analysis section below
2. Read this doc.  Execute the 2nd task in the Analysis section below

### Reporting

1. Read this doc.  Execute the 1st task in the Reporting section below
2. Read this doc.  Execute the 2nd task in the Reporting section below
3. Read this doc.  Execute the 3rd task in the Reporting section below

### Cleaning up

1. Read this doc.  Execute the 1st task in the Cleaning up section below
2. Read this doc.  Execute the 2nd task in the Cleaning up section below
3. Read this doc.  Execute the 3rd task in the Cleaning up section below

### Coding Plan

1. Read this doc.  Execute the 1st task in the Coding Plan section below
2. Read this doc.  Execute the 2nd task in the Coding Plan section below

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

2. Please make several edits to the Data section of the design doc:

   - Modify the PACE data section to recognize:
     - While `ocpy` has methods for loading data from L2 granules on a hard drive, the primary intention is to load the data from the Earthdata Cloud.
     - Similarly, we will tend to avoid downloading full L2 granules except for debugging and development purposes.
   - We should rethink the CSV look-up tables.  While these are conveient for user inspection and easy I/O, they are not ideal for programmatic use.  We should consider using a database instead.  Make this a point of discussion
 
Now, I insist you ask questions to me before you continue.  And Log your work

3. Read my answers to the questions in the Q&A section below and make any necessary edits to the Data section of the design doc.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

### Q&A

Open questions for JXP, raised by Claude while drafting the Data section
(2026-06-18). Answers will be folded into `docs/design/PAB_design.md`.

**On PACE cloud access:**

1. **Compute environment.** Where will PAB's PACE processing primarily run —
   in-region AWS (`us-west-2`, e.g. a PACE Hackweek / 2i2c JupyterHub, which
   enables fast direct S3 streaming), local/out-of-region (HTTPS/OPeNDAP
   fallback), or should the design be agnostic and run in both?

   _A:_It will primarily run on my workstation in the AWS us-west-2 region.

2. **Spectrum extraction mechanism.** To read only the pixels we need without
   downloading whole granules, which approach do you prefer: (a) lazy `xarray`
   open over S3/HTTPS with nearest-pixel indexing (mirrors `ocpy`'s existing
   extraction, repointed at cloud URLs); (b) OPeNDAP server-side subsetting from
   OB.DAAC; (c) the Harmony subsetting service; or (d) document all three and
   decide later?

   _A:_Please provide more information on the first two options.  We will decide later.  I should add that you should also explore the `remote_sensing` package that I have built and which is on this computer.

3. **Earthdata authentication.** Is an Earthdata Login (`~/.netrc` /
   `earthaccess.login()`) already set up for this work, and is there a target
   compute account/region we should assume?

   _A:_Yes, I have set up the Earthdata Login on my workstation.

**On storage / lookup tables:**

4. **CSV vs. database direction.** Do you want the design to recommend a
   specific backend now — SQLite (embedded, single file), DuckDB+Parquet
   (embedded, analytical), or PostgreSQL (client/server, multi-user) — or keep
   it as an open discussion until the scale/sharing model is settled?

   _A:_ Let's choose SQLite as the preferred backend for now.

5. **Scale and sharing.** What scale should we design for (rough order of
   matchups/profiles), and is the matchup store intended to be single-user/
   collaborator-shared files, or a shared/community archive with concurrent
   updates? This is the main driver of the backend choice.

   _A:_The database may grow to 10,000 Argo profiles and 10x as many PACE spectra analyzed.

6. **Relationship to BING outputs.** Should the BING fit outputs (chains,
   posterior summaries, derived IOPs) live in the same store as the matchup
   tables, or remain separate NPZ/JSON keyed by a matchup ID?

   _A:_The extracted values should be stored in the database.  The fit outputs (chains, figures) should be stored in separate files.

**On scope:**

7. **Reference datasets in the data layer.** Should L23 / GLORIA / PANGAEA be
   first-class citizens of the same loader/storage machinery now, or kept to the
   later Analysis/Validation sections so the data layer focuses on the
   PACE↔BGC-Argo matchup?

   _A:_Sorry, ignore the L23, GLORIA and PANGAEA datasets for now. That was a mistake.

## Analysis

Analysis will primarily proceed following the approach currently in the bing/papers/biomass/Analysis folder.  The primary differences are:

1. We wish to semi-automate the process.  
2. We wish to enhance and better record the provenance of the effort, ie. the input parameters and the output results.  We may want a versioning schema
3. We may wish to expose the fit outputs for the community to inspect.  At the very least we want the BING figures to be viewable.  Each is ~1Mb.  Will this be a problem on GitHub?

### Tasks

1. Please examine the context files and especially the code in the bing/papers/biomass/Analysis folder.  Generate a plan for the analysis methods.  Write the plan in the Analysis section of the design document.  If you have any questions, write them in the Q&A section below. Log your work.

2. I have answered the questions in the Q&A section below.  I have the following additional items to include:

    - We may choose to process PACE Level 1B data with our own algorithms to estiamte Rrs and its uncertainties.  The code will need to allow for this.
    - The design doc should note that we will not use any of the code in the bing/papers/biomass/Analysis folder.  We will take what we need from those modules and generate entirely new ones in the PAB package.

Please make any necessary edits to the Analysis section of the design document.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

### Q&A

Open questions for JXP, raised by Claude while drafting the Analysis section
(2026-06-18). Answers will be folded into `docs/design/PAB_design.md`.

1. **Default model pair.** Is `ExpBricaud` + `Pow` (the biomass workhorse) the
   right default for PAB, and do you want the GIOP and/or GSM baselines run
   automatically alongside it for every matchup, or only on request?

   _A: Yes, the ExpBricaud + Pow model is the right default for PAB.  We will only run that model for now, but the code base should be prepared for additional ones.  We will need a naming schema for their outputs, e.g. BING_ExpBPow_bbp, ...

2. **Automated model selection.** Should PAB *automatically* choose the model
   complexity per spectrum via AIC/BIC (fitting a ladder of models and picking
   the favored one), or always fit a single fixed model pair and just *report*
   the IC values?

   _A: N/A for now

3. **Versioning scheme.** For the provenance/versioning requirement, which do
   you prefer to stamp on each fit: (a) a semantic `pab_version` string, (b) a
   hash of the full pipeline configuration (models+priors+MCMC+RT options), or
   (c) a monotonic run/batch ID — or some combination?

   _A: I like a `pab_version` string.

4. **MCMC settings.** Keep the biomass defaults (`nsteps≈10000`, `nburn≈1000`,
   16 walkers) as PAB's standard, or expose them per-run and record per fit?
   (They are recorded as provenance regardless.)

   _A: Keep the biomass defaults.

5. **Figure storage / exposure.** Given ~1 MB/figure and ~10⁵ spectra, do you
   agree with: don't commit per-fit figures to git, store/regenerate them
   externally, and publish only a curated subset + population figures via
   readthedocs? If you want versioned figure storage, should we plan on Git LFS,
   release assets, or an S3 bucket in your us-west-2 account?

   _A: Well, we would likely only expose one fit per matchup, so the figure size is not a major problem for now.  And we should find a way to reduce the figure size from 1MB to 100KB

6. **What to expose to the community.** Beyond viewable BING figures, should the
   exposed products include the extracted-value tables (CSV/SQLite export), the
   raw MCMC chains (NPZ), and/or an interactive way to query matchups — and is
   readthedocs the only intended channel, or also a data release (e.g. Zenodo)?

   _A: Good questions.  Ask again when we work on the Reporting section below.

## Reporting

A major component -- possibly the most important --  of PBA will be to provide the community quick-look yet comprehensive views of the matchup results.  These should be accessible via a web interface.  We should also provide a way to download the data for further analysis.  Both the summary statistics and the fits.

Here are a few items to scope out:

- Exposing the results via readthedocs.io
- Interactive figures using Bokeh
- Tables of the summary statistics
- Reports that describe the matchup results in detail

If you think there are additional items the community would like to see and/or access, please add them to the Reporting section of the design document.

### Tasks

1. Please examine the context files.  Generate a plan for the Reporting methods.  Write the plan in the Reporting section of the design document.  If you have any questions, write them in the Q&A section below. Log your work.

2. Read my answers to the questions in the Q&A section below and make any necessary edits to the Reporting section of the design document.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

3. Read this doc.  Read my answers to the questions in the Q&A section below and make any necessary edits to the Reporting section of the design document.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

### Q&A

Open questions for JXP, raised by Claude while drafting the Reporting section
(2026-06-19). Answers will be folded into `docs/design/PAB_design.md`.

1. **Static vs. server-backed interactivity.** Is a fully **static** site
   (standalone Bokeh embedded in readthedocs, no running server) sufficient, or
   do you want richer server-driven interactivity (a Bokeh-server / Panel app,
   live DB queries) — which would need a hosted service beyond readthedocs?

   _A: Static is sufficient for now.  If it becomes very popular, we can consider a server-driven interactivity.

2. **Downloadable products (carried over from Analysis Q6).** Which should PAB
   expose for download: (a) summary-statistics tables (CSV/Parquet) — assumed
   yes; (b) the SQLite database file itself; (c) the raw per-matchup MCMC chains
   (NPZ); (d) the per-matchup figures? Any you'd exclude?

   _A:_ We will provide (a), (c) and (d)

3. **Citable data release.** Do you want periodic **Zenodo** snapshots (DOI,
   pinned to a `pab_version`) in addition to the living readthedocs site, or is
   readthedocs the only intended channel for now?

   _A:_ Yes, we will provide a Zenodo snapshot.

4. **Hosting for bulk fit artifacts.** For the downloadable chains/figures (too
   large for git), is an **`us-west-2` S3 bucket** the intended store, or do you
   prefer another host (Zenodo-only, institutional server, etc.)?

   _A:_ Yes, but we will use the Nautilus `s3` storage maintained by NSF.  Add this to the report.

5. **Build cadence / audience.** Should the readthedocs site rebuild
   automatically on each pipeline run (always-current), or as curated, tagged
   releases? And who is the primary audience — collaborators, or the broader
   public ocean-color community (affects how much explanatory framing to include)?

   _A:_ For now we will build it as a manual pipeline run.  We may then migrate to a more automated build.  The primary audience is the ocean color community, i.e. scientists.

6. **Per-matchup pages at scale.** At ~10⁴ matchups, generating one `.rst` page
   per matchup is a lot of pages. Do you want a page **per matchup**, or
   per-float/per-region aggregate pages with the individual fits shown inline /
   on demand?

   _A:_ We do not want one `.rst` page per matchup.  And the per-float would be nearly as "expensive".  We will need to find a way to aggregate the results.

---

Follow-up questions from Claude (2026-06-19), after folding the above answers:

7. **Aggregation approach (re: Q6).** My proposed scheme is: a *small fixed set*
   of aggregate `.rst` pages (landing + binned-by-region/season/`bbp`/`Rrs`-
   variability) plus **one interactive, searchable/filterable matchup table and
   the interactive scatter/map**, where per-matchup detail (figure + values) is
   fetched **on demand** by ID from the object store via hover/click — so no
   per-matchup or per-float pages are rendered. Does this match what you have in
   mind, or do you have a preferred aggregation scheme (e.g. specific bins,
   gridded/HEALPix spatial cells, or a different granularity)?

   _A:_ Yes, let's try your idea for now, although I am tempted to try the HEALPix option too.  Add this to the report.

## Cleaning up

1.  Here are a few additional items:

    - Bump the version of the design document to 0.2
    - If you touch the document from here on, bump the version.  Small changes should add and additional decimal, e.g. 0.2.1
    - Read it end to end.  If you have any additional questions or suggestions, write them in the Q&A section below.
    - If you have a figure or two to suggest including, please do so.
    - We will proceed to write a coding plan next
    - Log your work

2. Read my responses in the Q&A section below and make any necessary edits to the design document.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

3. Read my comments on Figure 3.  Create it with Python and add it to the design document.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

### Q&A

Suggestions & questions from Claude after an end-to-end read (2026-06-19), having
bumped the design doc to v0.2:

**Suggestions / observations**

- **Missing Validation & Metrics sections.** The `Prompts` list and the original
  section skeleton include **Validation** and **Metrics**, but no tasks were run
  for them and the design doc has no such sections. The Analysis section already
  *forward-references* them ("Metrics (defined fully in the later *Metrics*
  section)"). Recommend either writing brief Validation and Metrics sections or
  removing/relaxing the forward references before the coding plan. **Q: do you
  want these two sections written, or deferred (and the forward refs softened)?**

I don't remember what I had in mind for the Validation section.  Please remove mention of it.  As for Metrics, please write that based on what exists in the papers/biomass/Analysis folder.

- **Metrics content is currently split across Analysis.** The satellite/in-situ
  ratio, rank correlation, log-space bias/scatter, χ², and the
  region/season/`Rrs`-variability stratification live in the Analysis
  "Comparison & metrics" subsection. If a Metrics section is added, consider
  moving the definitions there and leaving Analysis to point at it.

I think we can remove the notion of a separate Metrics section.  We can just include the metrics in the Analysis section.

- **Minor copyedit (Preamble).** Line 11 reads "design and requirements of
  **PAB** a Python package…"; suggest "**PAB**, a Python package…".

Make that edit

**Figures**

- **Figure 1 (added in v0.2):** an end-to-end dataflow diagram (Mermaid) in the
  Preamble's new *Architecture overview* — Argo + PACE → matchup → BING → SQLite
  / artifacts → reporting.
- **Suggested Figure 2 (not yet added):** a *single-matchup* science schematic —
  the float `bbp(z)` profile with the MLD marked, the PACE pixel neighborhood
  around the float, and the extracted `Rrs(λ)` spectrum with its BING fit +
  uncertainty envelope — to illustrate the core science in one glance. **Q: want
  me to add a placeholder for this (it needs a real example fit to render)?**

Please generate this figure.  Use one of the fits from the papers/biomass/Analysis work.  Ask me if you need help.

- **Possible Figure 3:** a storage/architecture diagram (SQLite DB ↔ object
  store ↔ readthedocs/Zenodo) if the Reporting section warrants more detail.

Yes, please generate this too.  Use Matlab and make a script in docs/scripts folder.

**Question**

- **Scope of the upcoming coding plan.** You noted a coding plan is next. **Q:
  should it be a separate document (e.g. `docs/design/PAB_coding_plan.md`) per
  the Overview's "separate doc" for code-level recommendations, and should it
  cover the whole package or proceed section-by-section (Data → Analysis →
  Reporting)?**

Yes, a separate doc.  It will cover the whole package and will have a recommended staging for development.

---

Follow-up from Claude (Cleaning up #2, 2026-06-19):

- **Figure 2 — done, but partial.** Generated a real, data-backed Figure 2 from
  a `papers/biomass` fit (NPZ): the extracted PACE `Rrs(λ)` + BING fit +
  uncertainty, and the retrieved `a_nw`/`b_b,nw` with 5–95% envelopes
  (`docs/scripts/fig_example_fit.py` → `docs/figures/fig_example_fit.png`, 58 KB).
  The two extra panels you'd described — the **float `bbp(z)` profile with MLD**
  and the **PACE pixel neighborhood** — were *not* added because they need the
  raw Argo profile NetCDF and the PACE granule, which I don't have offline. **Q:
  add those panels (and point me to the raw Argo file + granule for this float),
  or is the current Rrs+IOP figure sufficient?**

- **Figure 3 — MATLAB not installed here.** Wrote the MATLAB script
  `docs/scripts/fig_architecture.m` as requested, but **MATLAB/Octave is not
  available in this environment**, so I could not run it — `fig_architecture.png`
  is not yet rendered (the design doc references it and notes this). **Please run
  the script in MATLAB on your workstation to produce the PNG**, or say the word
  and I can generate the same diagram in Python (matplotlib) instead.

I am only using Python.  Generate tihs with Python not MATLAB.

## Coding Plan

Let us now use the design document to generate a coding plan.  Please do this in a separate document called `docs/design/PAB_coding_plan.md`.  The coding plan will be a living document that will be updated as we develop the package.  It will be used to guide the development of the package.  Add version number and date to the file. The coding plan is a living document that will be updated as we develop the package.  It will be used to guide the development of the package.

### Tasks

1.  Proceed with a first draft of the coding plan.  Be sure:
    - Have the development occur in well defined stages.
    - Include tests and doc development in each stage.
    - If you have any additional questions, write them in the Q&A section below.  
    - Log your work in the Logs section below.  

2. I have read the answers to the questions in the Q&A section below.  Make edits to the coding plan accordingly.  Log your work in the Logs section below.  If you have any additional questions, write them in the Q&A section below.  

### Q&A

Open questions for JXP on the coding plan (2026-06-19), from Claude:

1. **Test fixtures vs. mocking.** For offline/CI tests I'd like to commit small
   fixtures — a trimmed BGC-Argo profile, a tiny synthetic/cropped PACE granule,
   and one stored example BING fit. Is committing a small (~MB) PACE granule
   subset acceptable (size/licensing), or should PACE cloud access always be
   mocked in tests?

   _A:_ These are good suggestions.  A small PACE granule subset is acceptable.  We will mock the PACE cloud access in tests.

2. **Database access layer.** For the SQLite layer, do you prefer raw `sqlite3`
   (lightweight, no deps), `SQLAlchemy` (ORM/migrations, heavier), or pandas
   `to_sql`/`read_sql` (simplest, less control)?

   _A:_ We will use the SQLite database.

3. **CI.** Should the plan assume **GitHub Actions** for running tests + a docs
   build on each push, or do you use another CI / none for now?

   _A:_ Yes, it should assume GitHub Actions.

4. **Credentials & external services in scope.** When should the plan schedule
   the **Nautilus/NSF S3** upload and **Zenodo** publishing (Stage 7) — are
   credentials/endpoints available now, or should those be stubbed until later?

   _A:_ They are available now, but let us stub them until later.

5. **Python / packaging.** Confirm the target is **Python ≥ 3.12** (per
   `setup.py`) and that `requirements.txt` stays the single dependency source
   (I'll add `bing`, `ocpy`, `remote_sensing`, `gsw`, `bokeh`, HEALPix tooling as
   stages need them). Any constraint on adding dependencies?

   _A:_ Yes, the target is Python ≥ 3.12 and the requirements.txt file should stay the single dependency source.  We will add the dependencies as we need them.  You can add those for now.  I will be turning `bing` into a pip package.  `remote_sensing` will have to be accessed via GitHub.

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

### 2026-06-17 (Data #1: wrote the Data section of the design document)

Per the Data task #1, added a **Data** section to the design doc. First resolved
a naming conflict — the Goals now name the doc `docs/design/PAB_design.md` while
the Overview still says `IOPtics_design.md`; per the user's choice the doc is
now `docs/design/PAB_design.md`.

Examined the relevant local code to ground the section: in **ocpy** —
`pace/io.py` (`load_oci_l2`, `load_oci_l2_spectrum` (nearest-pixel, reads a
single spectrum off disk), `load_oci_l2_spectrum_pixel`, `load_iop_l2` exposing
NASA's `a`/`bb`/`aph`/`bbp_442`/`adg_*`), `satellites/pace.py`
(`wave`, `gen_noise_vector` from `PACE_error.csv`),
`hydrolight/loisel23.py` (`load_ds(X,Y,profile)`, `calc_Chl`),
`insitu/gloria.py` (`load_gloria`), `insitu/panagea.py` (`load`, `spectrum`,
`to_long`); and in **argopy** the `DataFetcher(ds='bgc', src='erddap')` /
`ArgoIndex(index_file='bgc-s')` access patterns plus the `argo` accessor
(`point2profile`, `filter_qc`, `teos10`→`SIG0` for MLD).

The Data section covers: a datasets-at-a-glance table (BGC-Argo + PACE AOP as
primary; PACE IOP, L23, GLORIA, PANGAEA as secondary/reference; future hooks);
per-dataset descriptions; loading (the existing ocpy/argopy entry points);
processing (Argo MLD via the 0.03 kg m⁻³ density threshold, 3-pt de-spike,
mixed-layer averaging; PACE scaling, `l2_flags` ocean mask, nearest-unflagged
pixel, noise vector); matchup/use/analysis (5×5 box + tight time window → ~10
Rrs → BING → compare bbp vs float + NASA L2 IOP); storage/retrieval (raw cache
via earthaccess + argopy cache and the BGC index for index-first pre-selection,
intermediate matchup tables as CSV/Parquet à la `papers/biomass`, NPZ/JSON fit
outputs); and extensibility hooks (common matchup-record schema, loader
registry, satellite abstraction). No open questions for the Q&A section.

What I learned: ocpy already provides the exact PACE single-spectrum extraction
PAB needs (`load_oci_l2_spectrum` does nearest-pixel-by-distance and reads only
that spectrum), and a NASA L2 IOP loader for a ready baseline comparison — so
the data layer is largely an orchestration/caching effort over existing loaders
rather than new I/O.

### 2026-06-18 (Data #2: edited the Data section; raised Q&A in the design doc)

Per Data task #2, made two edits to the Data section of `docs/design/PAB_design.md`:

- **PACE cloud-first.** Reworked the PACE-AOP loading bullet and the
  Storage/retrieval subsection to state that the *primary* intention is to read
  PACE data directly from the NASA Earthdata Cloud (via `earthaccess`), with the
  `ocpy` hard-drive granule readers (`load_oci_l2`, `load_oci_l2_spectrum`,
  `load_oci_l2_spectrum_pixel`) used mainly for **debugging/development**, and
  that PAB **avoids downloading full L2 granules** except for dev/offline work
  (reads only the needed pixels).
- **CSV → database.** Reframed the "intermediate matchup tables" bullet to note
  CSV's limits for programmatic use, and added a **"Discussion: lookup tables —
  CSV vs. a database"** subsection laying out the trade-offs and candidate
  backends (SQLite / DuckDB+Parquet / PostgreSQL), with a default of defining a
  schema now behind a thin storage interface so CSV can migrate to a DB later.

Then — per the explicit instruction to ask questions before continuing — I added
a **Q&A** subsection to the design doc (the user redirected my interactive
questions into the doc) with 7 open questions for JXP: PACE compute environment
(in-region vs local), cloud spectrum-extraction mechanism (lazy xarray/S3 vs
OPeNDAP vs Harmony), Earthdata auth, CSV-vs-DB backend direction, scale/sharing
model, whether BING fit outputs share the matchup store, and whether the
reference datasets (L23/GLORIA/PANGAEA) belong in the data layer now. Awaiting
answers before finalizing these parts of the design.

Note: the earlier (Data #1) log line "No open questions for the Q&A section" is
now superseded — the Q&A above lists open questions.

### 2026-06-18 (Data #3: folded JXP's Q&A answers into the Data section)

Per Data task #3, read JXP's answers in the Q&A and revised the Data section of
`docs/design/PAB_design.md` accordingly. Also explored the **remote_sensing**
package on this workstation (per JXP's note in Q2). Key changes:

- **Cloud-first + in-region (Q1, Q3).** Stated that PAB runs on a workstation in
  AWS `us-west-2` with Earthdata Login configured, so in-region direct cloud
  access is the design target.
- **New "Cloud access (PACE)" subsection (Q2).** Detailed the two extraction
  mechanisms with pros/cons, decision deferred: (a) lazy `xarray` open over S3
  (nearest-pixel read transfers one spectrum; reuses `ocpy`/`remote_sensing`
  readers with only the file handle becoming a remote object) and (b) OPeNDAP
  server-side subsetting (minimal transfer, works out-of-region, per-request
  latency). Grounded in the actual `remote_sensing` code I found:
  `process.swot_ssh_utils` already implements the in-region `s3fs` +
  `xr.open_dataset(s3sys.open(...))` pattern (notes us-west-2 requirement);
  `download.earthaccess` wraps CMR search + a granule→DataFrame table
  (`query_modis_oc`, `build_granule_table` with footprint polygons/time/CC/URL);
  `download.podaac` already distinguishes the `OPENDAP DATA` URL subtype;
  `netcdf/oc.py` has sensor-agnostic OC L2 helpers (`create_quality_mask`,
  `quality_control`, `extract_rrs_spectrum`, `find_rrs_variables`). Recommended
  starting with (a) while keeping discovery/pixel-selection factored so (b) can
  slot in.
- **SQLite chosen (Q4, Q5).** Replaced the open CSV-vs-DB discussion with a
  decision: extracted/tabular values (mixed-layer summaries, matchup index,
  scalar IOP results) go in a single-file **SQLite** DB; CSV/Parquet kept as
  exports only. Noted the scale (~10⁴ Argo profiles, ~10⁵ PACE spectra) sits
  well within SQLite's single-user range; DuckDB+Parquet and PostgreSQL recorded
  as deferred alternatives behind a thin storage interface.
- **Fit outputs split (Q6).** Bulky BING outputs (MCMC chains, figures) stored
  as separate files (NPZ/JSON, PNG/PDF) keyed by matchup/fit ID, not in the DB.
- **Dropped reference datasets (Q7).** Removed L23 / GLORIA / PANGAEA from the
  datasets table, descriptions, loading, and processing; the data layer now
  focuses on the PACE↔BGC-Argo matchup (PACE L2 IOP retained as the NASA
  baseline). Generalized the extensibility hooks accordingly and added
  `remote_sensing` to the reused-packages list (Preamble + intro).

No additional open questions. What I learned: `remote_sensing` already supplies
both halves of the cloud path PAB needs — Earthdata/CMR granule discovery with a
footprint table for spatial matchup, and a proven in-region S3 lazy-open pattern
— so PAB's PACE access can be assembled largely from existing code.

### 2026-06-18 (Analysis #1: wrote the Analysis section of the design document)

Per Analysis task #1, examined the local **BING** package
(`/home/xavier/Oceanography/python/bing`) and its `papers/biomass/Analysis`
folder, then wrote an **Analysis** section into `docs/design/PAB_design.md`.

Examined: `bing/papers/biomass/Analysis/py/end_to_end_workflow.py` (the staged
slurp→match→find-closest→fit→slurp pipeline), `fitting.py`
(`fit_em_all`/`fit_one`/`fit_me`, two-stage LM→MCMC with `ExpBricaud`+`Pow`),
`bing/scripts/fit_Rrs.py` (the public fit recipe), and the core API:
`models/utils.init`, `models/anw.py` + `bbnw.py` (model libraries),
`fitting/inference.py` (`init_mcmc`, `fit_one`, `fit_batch`, `run_emcee`),
`fitting/chisq_fit.py` (LM), `evaluate.py` (`calc_stats`,
`reconstruct_from_chains`, `thin_burn_chains`), `stats.py` (`calc_chisq`,
`calc_ICs` → AIC/BIC), `rt/rrs.py` (Gordon forward model), `plotting.py`.

The Analysis section covers: the biomass reference workflow; the per-spectrum
BING fit (init models → priors → LM warm-start → MCMC → reconstruct/summarize),
defaulting to `ExpBricaud`+`Pow` with `bbp` as the key observable; model
selection & diagnostics (χ², AIC/BIC, convergence QC); comparison of BING vs
NASA-L2-IOP vs in-situ Argo `bbp` and the metrics that follow; per-fit and
population figures + tables (extracted scalars → SQLite, exportable to
CSV/.rst); semi-automation (idempotent, resumable stage runner); and provenance
& versioning (record inputs, config, and package/git versions; proposed stamping
a version/config-hash per fit).

Addressed JXP's embedded question (Analysis intro #3) on ~1 MB BING figures on
GitHub: a single 1 MB file is fine, but ~10⁵ figures (~100 GB) must NOT be
committed — recommended generating on demand / external object store +
publishing a curated subset and population figures via readthedocs, with Git
LFS / release assets / S3 as options if versioned figure storage is wanted.

Per JXP's standing preference (now saved to memory), I did NOT use interactive
prompts; I recorded 6 open questions in the **Analysis → Q&A** section of
`design_prompts.md` (default model pair + GIOP/GSM baselines; automated AIC/BIC
model selection vs fixed model; versioning scheme; MCMC defaults; figure
storage/exposure; what else to expose to the community + channel) and await
JXP's answers before finalizing those parts.

### 2026-06-18 (Analysis #2: folded answers + new items into the Analysis section)

Per Analysis task #2, read JXP's Q&A answers and the two additional items, then
revised the Analysis section of `docs/design/PAB_design.md`:

From the answers:
- **Single default model.** PAB runs only `ExpBricaud`+`Pow` for now, but the
  code must be prepared for more pairs. Added an **output naming schema** —
  results namespaced as `BING_ExpBPow_bbp`, `…_beta`, `…_aph`, `…_unc`, with the
  NASA baseline as `NASA_L2IOP_bbp` — so additional pairs write parallel columns
  without collision.
- **No automated model selection** (N/A for now): renamed "Model selection &
  diagnostics" → "Diagnostics"; χ² and AIC/BIC are *reported* per fit, not used
  to select a model; ladder/ΔBIC selection noted as a future capability only.
- **Versioning = `pab_version` string** (decided): removed the config-hash/run-ID
  hedge; every fit stamped with `pab_version` + timestamp, new version instead of
  overwrite.
- **MCMC defaults kept** (`nsteps≈10000`, `nburn≈1000`, 16 walkers) as PAB's
  standard, recorded as provenance.
- **Figures**: one figure per matchup (~10⁴, not the ~10⁵ spectra), with an
  explicit **~100 KB target** (down from ~1 MB; via lower DPI / rasterization /
  PNG optimization). Revised the GitHub discussion accordingly (the full set is
  ~1 GB, "not a major concern for now"; still prefer readthedocs/external store
  over git history).
- **Community products** deferred to the **Reporting** section per JXP.

From the two new items:
- **PACE L1B option.** Added an "Rrs source" subsection: PAB must allow deriving
  `Rrs`/σ_Rrs from PACE **Level-1B** with our own algorithms; the Rrs source is a
  pluggable upstream stage (L2_AOP vs PAB_L1B:<algo/version>) feeding the same
  fit pipeline, with the source recorded as provenance.
- **No biomass code reuse.** Added a prominent **Code-reuse principle**: PAB will
  NOT use any code in `bing/papers/biomass/Analysis` — those scripts are a
  scientific *reference* only; PAB reimplements all orchestration anew while
  still depending on the installable **BING package** API (plus ocpy/argopy/
  remote_sensing). Reframed every biomass-script reference (`fit_em_all`,
  `plot_fit`, `figs_biomass`, etc.) as conceptual templates, and the
  semi-automation pipeline as new PAB code.

No new open questions (the one remaining topic — full community-facing product
set — is carried to the Reporting section).

### 2026-06-19 (Reporting #1: wrote the Reporting section of the design document)

Per Reporting task #1, wrote a **Reporting** section into
`docs/design/PAB_design.md`, drawing on the Reporting scope (web interface;
downloadable summary stats + fits; readthedocs.io; Bokeh interactive figures;
summary tables; detailed reports) and the materials produced by the Analysis
layer (SQLite store + per-matchup fit artifacts, `pab_version`-stamped).

The section defines four product tiers: (1) a **static readthedocs site** with
`.rst` generated programmatically from the SQLite DB + fit artifacts (landing/
summary page, per-matchup quick-look pages, sortable stat tables, methods pages);
(2) **interactive Bokeh figures** embedded as *standalone* HTML/JSON so they work
on static hosting (matchup map, satellite-vs-float and BING-vs-NASA `bbp`
scatter, linked filtering; WebGL/Datashader for ~10⁴–10⁵ points; a server/Panel
app flagged as an optional separate deployment); (3) **downloads** in two tiers —
summary stats as CSV/Parquet + the SQLite file, and fits (NPZ chains + figures)
from an external us-west-2 S3 store with a download manifest; (4) a **Zenodo**
citable release pinned to `pab_version`. Also suggested extra community items: a
searchable matchup index, per-float/per-region pages linking out to PACE/Argo
dashboards, reproducibility hooks, a coverage/QC dashboard, and a STAC-like
metadata/API. Added an architecture/build note (reporting module reads DB +
artifact store, renders via Sphinx, incremental, driven off `pab_version`,
static-first).

Key design point captured: **readthedocs serves static content**, so Bokeh must
be embedded standalone (server-driven interactivity = a separate hosted app).

Per JXP's standing preference (memory), used no interactive prompts; recorded **6
open questions** in the **Reporting → Q&A** of `design_prompts.md` — static vs
server-backed interactivity; which products to expose for download (the
carried-over Analysis Q6); Zenodo release y/n; hosting for bulk artifacts (S3?);
build cadence + audience; and per-matchup vs aggregate pages at ~10⁴ scale —
each with an `_A:_` placeholder, awaiting answers.

### 2026-06-19 (Reporting #2: folded answers into the Reporting section)

Per Reporting task #2, read JXP's six answers and revised the Reporting section
of `docs/design/PAB_design.md`:

- **Static-first (Q1).** Firmed the site as fully static (standalone Bokeh on
  readthedocs); a server-backed Bokeh/Panel app is deferred unless usage grows.
- **Downloads (Q2).** Exposed products are (a) summary-stat tables (CSV/Parquet),
  (c) per-matchup MCMC chains (NPZ), and (d) per-matchup figures — **not** the
  raw SQLite DB file. Updated the downloads tier accordingly.
- **Zenodo (Q3).** Kept the citable-release tier; snapshot = summary-table export
  + fit-artifact manifest, pinned to `pab_version`.
- **Object store (Q4).** Bulk chains/figures hosted on **NSF/Nautilus
  S3-compatible storage** (National Research Platform), not AWS; noted compute is
  AWS us-west-2 while distribution artifacts go to Nautilus S3, with URLs in the
  manifest.
- **Cadence/audience (Q5).** Manual pipeline-run build for now (may automate
  later); audience = ocean-color scientists, so framing emphasizes methods and
  quantitative comparison.
- **No page explosion (Q6).** Removed all per-matchup pages and per-float pages.
  The site is now a small fixed set of **aggregate** pages (landing + binned
  views + methods); **per-matchup detail is reached on demand** via the
  interactive Bokeh map/scatter and a searchable matchup table (hover shows
  values, click links to the figure/artifacts by ID in the object store). The
  per-matchup metadata is exported once from the DB into a compact table the
  figures load.

Posed one follow-up question (Q7) in the **Reporting → Q&A** to confirm the
aggregation scheme (small fixed aggregate pages + interactive table/figures +
on-demand detail; possible region/season/HEALPix binning). Awaiting JXP's answer.

What I learned: JXP's "no per-matchup/per-float pages" constraint reshapes the
reporting design from a page-per-object site to an **aggregate + interactive +
on-demand-artifact** model — the database feeds compact tables that drive
client-side Bokeh, and the heavy artifacts live on Nautilus S3, keeping the
static readthedocs build small regardless of matchup count.

### 2026-06-19 (Reporting #3: confirmed aggregation scheme; added HEALPix option)

Per Reporting task #3, read JXP's answer to the follow-up Q7. He confirmed the
proposed aggregation scheme (small fixed set of aggregate pages + interactive
searchable table/scatter/map + on-demand per-matchup detail by ID) and asked to
also add the **HEALPix** option. Edits to the Reporting section of
`docs/design/PAB_design.md`:

- Added a **spatial aggregation via HEALPix (to try)** bullet under the aggregate
  result pages: matchups binned into HEALPix equal-area cells, per-cell stats
  (median `bbp`, float ratio, counts) driving a map + compact per-cell table;
  resolution-tunable and scales independently of matchup count. Noted it can
  reuse the existing **`remote_sensing.healpix`** tooling (`rs_healpix`,
  `combine`, `utils`). Flat region/season binning stays the default; HEALPix is
  an alternative to evaluate alongside it.
- Updated the Reporting Q&A note to record that all Reporting questions
  (including Q7) are answered and folded in; no open Reporting questions remain.

What I learned: JXP's own `remote_sensing` package already ships a HEALPix
module, so the equal-area spatial aggregation he's tempted by is readily
buildable from existing code rather than from scratch.

### 2026-06-19 (Cleaning up #1: bumped to v0.2, added a figure, end-to-end review)

Per Cleaning-up task #1:
- **Version → 0.2.** Bumped the design doc from 0.1 to 0.2, updated the Date to
  2026-06-19, and recorded the **versioning convention** in the header (minor
  bump for substantive changes, e.g. 0.2→0.3; extra decimal for small edits,
  e.g. 0.2.1; update Date on every bump).
- **Figure added.** Added **Figure 1** — an end-to-end dataflow **Mermaid**
  diagram — in a new *Architecture overview* subsection of the Preamble
  (Argo + PACE → matchup → BING fit → SQLite/artifacts → reporting). Renders on
  GitHub and on readthedocs via the mermaid extension.
- **End-to-end read.** Read the whole doc. It is internally consistent except for
  one dangling forward reference: the Analysis "Comparison & metrics" subsection
  cites "the later *Metrics* section," but **no Validation or Metrics sections
  exist** (no tasks were run for them). Recorded this, plus a minor Preamble
  copyedit and two further figure suggestions (a single-matchup science
  schematic; a storage/architecture diagram), in the **Cleaning up → Q&A**
  section of `design_prompts.md`.
- **Questions for JXP** (in Cleaning-up Q&A): whether to write the Validation &
  Metrics sections or defer them (and soften the forward refs); whether to add
  the suggested Figure 2 placeholder; and the scope/location of the upcoming
  coding plan (separate `docs/design/PAB_coding_plan.md`? whole-package vs
  section-by-section?).

Noted for next step: JXP says a **coding plan** is next.

### 2026-06-19 (Cleaning up #2: folded responses, wrote Metrics into Analysis, added Figures 2 & 3)

Per Cleaning-up task #2, read JXP's Q&A responses and edited the design doc
(bumped 0.2 → **0.3**, date 2026-06-19):

- **Validation removed.** Per JXP, dropped the notion of a Validation section.
  (There was in fact no Validation mention in the doc to remove — only the
  prompts skeleton had it.)
- **Metrics folded into Analysis (no separate section).** Per JXP, kept metrics
  in the Analysis layer and rewrote the "Comparison & metrics" subsection to
  *define* them inline — median satellite/float `bbp` ratio (Bisson's 0.77–1.66),
  Spearman rank correlation, log-space bias & RMS/MAD scatter (with 1:1 and
  median-ratio lines à la `figs_biomass.fig_giop_vs_bnw_colored`), per-fit
  reduced χ², and BING-vs-NASA-L2-IOP stats; all stratified by region/season/
  `Rrs`-variability. Removed the dangling "later *Metrics* section" forward ref.
- **Preamble copyedit.** "PAB a Python package" → "PAB, a Python package".
- **Figure 2 (real, data-backed).** Wrote `docs/scripts/fig_example_fit.py`,
  which loads a real `papers/biomass` fit NPZ (float 6903823/profile 387) and
  renders `docs/figures/fig_example_fit.png` (58 KB): PACE `Rrs`+BING fit+σ and
  retrieved `a_nw`/`b_b,nw` with 5–95% envelopes. Ran it and verified the output.
  Embedded as Figure 2 in the Analysis section. The float `bbp(z)`/MLD and PACE
  pixel-neighborhood panels were not added (need raw Argo NetCDF + granule) —
  flagged in Q&A.
- **Figure 3 (MATLAB script).** Wrote `docs/scripts/fig_architecture.m` (storage
  & reporting architecture) as requested. **MATLAB/Octave is not installed in
  this environment**, so I could not render `fig_architecture.png`; the doc
  references it (Figure 3) with a note, and I asked JXP to run the script (or
  approve a Python version) in the Q&A.

Coding-plan direction recorded for next step: a **separate document** covering
the **whole package** with a **recommended development staging**.

What I learned: the biomass fit NPZs are self-contained (wave, Rrs, varRrs,
chains, reconstructed Rrs±σ, and a/bb with lo/hi envelopes), so a real example
fit figure can be produced with no extra data; the depth profile and pixel
neighborhood are the only parts that need the raw Argo/PACE sources.

### 2026-06-19 (Cleaning up #3: generated Figure 3 in Python)

Per Cleaning-up task #3 and JXP's Q&A comment ("I am only using Python. Generate
this with Python not MATLAB"):

- Wrote `docs/scripts/fig_architecture.py` (matplotlib) and ran it to produce
  `docs/figures/fig_architecture.png` (46 KB) — the storage & reporting
  architecture diagram (BING fits → SQLite DB + Nautilus/NSF S3 → Zenodo
  snapshot; reporting layer reads both). Verified the rendered output.
- **Deleted** the earlier MATLAB script `docs/scripts/fig_architecture.m`.
- Updated the Figure 3 caption in the design doc to point at the Python script
  and removed the "MATLAB not available / not rendered" note.
- Bumped the design doc **0.3 → 0.3.1** (small change).
- Saved a memory: **JXP uses Python only — never MATLAB for PAB.**

Both design-doc figures (Fig 2 example fit, Fig 3 architecture) are now real,
Python-generated PNGs under `docs/figures/`, scripted under `docs/scripts/`.

### 2026-06-19 (Coding Plan #1: first draft of PAB_coding_plan.md)

Per Coding-Plan task #1, wrote a first draft of `docs/design/PAB_coding_plan.md`
(v0.1, 2026-06-19, JXP and Claude) — a separate living document implementing
`PAB_design.md` (v0.3.1). Contents:

- **Guiding principles** (reuse BING/ocpy/argopy/remote_sensing; Python only; no
  biomass-script reuse; cloud-first PACE; SQLite as the single source of truth
  behind a swappable storage seam; provenance + `pab_version`; code+tests+docs
  every stage; idempotent/resumable pipeline).
- **Proposed `pab/` package layout** (config, db, argo, pace, matchup, fit,
  metrics, plotting, report, pipeline, tests).
- **Cross-cutting concerns** (testing with small offline fixtures + mocked cloud;
  Sphinx docs; provenance; tooling; CI).
- **Ten development stages (0–9)**, each with scope / deliverables / tests / docs:
  0 scaffolding, 1 SQLite layer, 2 Argo ingest + MLD/summary, 3 PACE access +
  extraction, 4 matchup engine, 5 BING fitting wrapper, 6 metrics + figures, 7
  reporting (rst + Bokeh + HEALPix + S3/Zenodo), 8 end-to-end pipeline/CLI, 9
  extensibility (loader registry, more models, L1B→Rrs, server interactivity).
- **Suggested order/dependency graph** (DB first; Argo ∥ PACE; recommend a thin
  end-to-end "walking skeleton" early) and **milestones M1–M4**.

Per JXP's standing preferences, used Python throughout and posed **5 questions**
in the Coding-Plan Q&A (test fixtures vs mocking + committing a small PACE
granule; sqlite3 vs SQLAlchemy vs pandas; CI = GitHub Actions?; when to schedule
Nautilus S3 / Zenodo; confirm Python ≥3.12 + dependency policy) with `_A:_`
placeholders, awaiting answers before refining the plan.

### 2026-06-19 (Coding Plan #2: folded Q&A answers into the coding plan)

Per Coding-Plan task #2, read JXP's five answers and edited
`docs/design/PAB_coding_plan.md` (bumped 0.1 → **0.1.1**):

- **Testing.** Commit a **small real PACE granule subset** as a fixture and
  **mock the PACE cloud-access layer** in tests (granule read locally; no
  network/S3 in the suite).
- **Database access.** Added a Database bullet: SQLite via the stdlib **`sqlite3`**
  module as the default access layer (no extra dep); ORM deferred but the thin
  `pab.db.store` API keeps it optional.
- **CI.** Stated **GitHub Actions** runs pytest + a docs build on every push.
- **Stage 7 external services.** Noted Nautilus/NSF S3 and Zenodo credentials are
  available but the publish interfaces are **implemented against stubs/local
  mocks** now, with real uploads deferred behind a config-gated switch.
- **Dependencies.** Confirmed Python **≥ 3.12** and `requirements.txt` as the
  single source; recorded install sources — most deps PyPI; **`bing`** being
  packaged for PyPI; **`remote_sensing`** and **`ocpy`** from GitHub/local. Per
  JXP's "you can add those for now," updated `requirements.txt`: added `gsw`,
  `bokeh`, `healpy`, and a commented block documenting the three special-source
  packages (so `pip install -r` doesn't fail on not-yet-published/GitHub-only
  packages).

No new open questions. What I learned: `bing` will be pip-installable soon while
`remote_sensing`/`ocpy` remain GitHub installs, so PAB's dependency story is
mixed-source — captured in both the plan and `requirements.txt`.