# Coding up PAB - First Major Pass

## Goals

We will now perform the first major pass of coding up PAB.  We will use the design document `docs/design/PAB_design.md` and the coding plan `docs/design/PAB_coding_plan.md` to guide our work.

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
- The coding plan document: docs/design/PAB_coding_plan.md
- The design document: docs/design/PAB_design.md

## Prompts

### Stage 0

1. Read this doc. Execute the 1st task in the Stage 0 section below.

## Stage 0

### Tasks

1.  Read the context files. Proceed with the coding.  Begin with Stage 0.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

### Q&A

## Logging

The "Logs" section will record Claude's work.  Please use the following format:

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

...

## Logs

### 2026-06-19 (Stage 0 — scaffolding & infrastructure)

Read the context files (`docs/design/PAB_design.md` v0.3.1,
`docs/design/PAB_coding_plan.md` v0.1.1, `docs/context.md`) and executed
**Stage 0** of the coding plan: package skeleton, config + `pab_version`, test
harness, Sphinx docs skeleton, dependency pinning, and CI.

Delivered:

- **Package skeleton** matching the §2 module map — importable subpackage
  stubs `pab.{db,argo,pace,matchup,fit,metrics,plotting,report}` (each an
  `__init__.py` docstring naming its future role and the stage that fills it in)
  plus `pab/pipeline.py`. `find_packages()` now discovers all 10 subpackages.
- **`pab/config.py`** exposing `pab_version = "0.0.dev0"` (distinct from the
  packaging version in `setup.py`), `ROOT`/`DATA_DIR` paths (env-overridable
  via `PAB_ROOT`/`PAB_DATA_DIR`), and `package_versions()` for provenance — it
  reports versions for pab/bing/ocpy/argopy/remote_sensing/earthaccess/
  numpy/scipy/xarray and degrades to `"not installed"` rather than raising.
  `pab/__init__.py` re-exports `pab_version` as `__version__`.
- **Tests** (`pab/tests/test_smoke.py`): parametrized import smoke test over all
  subpackages, `pab_version` presence/type, and `package_versions()` shape.
  `pytest.ini` collects from `pab/tests`. 13 tests pass.
- **Docs** (`docs/conf.py`, `index.rst`, `dev_setup.rst`): Sphinx site reusing
  the existing `docs/` tree, with napoleon (Google docstrings), myst-parser
  (renders the Markdown design/context docs), and sphinxcontrib-mermaid (the
  design's mermaid diagrams). `autodoc_mock_imports` and `suppress_warnings`
  keep the build green without the heavy optional deps. Builds clean under
  `sphinx-build -W`.
- **Dependency pinning**: added sphinx/sphinx-rtd-theme/myst-parser/
  sphinxcontrib-mermaid and ruff to `requirements.txt` (still the single source
  of deps; the special-source packages bing/ocpy/remote_sensing stay as
  comments). Added `ruff.toml`.
- **CI**: `.github/workflows/ci.yml` runs pytest and a `-W` docs build on every
  push/PR; `.readthedocs.yaml` for the RTD build.

Verification: `pytest` → 13 passed; `sphinx-build -W` → build succeeded;
`ruff check pab` and `ruff format --check pab` → clean.

What I learned: the workstation already has bing/ocpy/remote_sensing/argopy/
earthaccess installed, so later stages can import them directly — but CI and the
Stage 0 smoke test deliberately do **not** require them (CI installs only the
package + pytest; the docs build mocks them). Python here is 3.14.5 (plan
floor is 3.12). No questions for the Q&A section — Stage 0 scope was
unambiguous.
