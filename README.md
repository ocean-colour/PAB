# PAB

[![CI](https://github.com/ocean-colour/PAB/actions/workflows/ci.yml/badge.svg)](https://github.com/ocean-colour/PAB/actions/workflows/ci.yml)
[![Documentation Status](https://readthedocs.org/projects/pab/badge/?version=latest)](https://pab.readthedocs.io/en/latest/)

PACE and BGC-Argo matchup analyses.

**PAB** produces matchup analyses between **PACE** (satellite ocean color) and
**BGC-Argo** (autonomous float) data, and shares the results with the community.

## Documentation

The developer and methods documentation is built with Sphinx and published on
Read the Docs: **https://pab.readthedocs.io**

To build it locally:

```bash
pip install -r requirements.txt
sphinx-build -b html docs docs/_build/html
```

See [`docs/dev_setup.rst`](docs/dev_setup.rst) for the full developer setup, and
the design docs under [`docs/design/`](docs/design/) (design, coding plan, and
implementation record).
