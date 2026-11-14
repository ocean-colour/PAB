# BGC Argo Float Coverage Verification Report

**Date:** July 24, 2026  
**Author:** Allie James  
**Purpose:** Verify that argopy (via GDAC) retrieves the complete BGC Argo float dataset,
and characterize the relationship between the SOCCOM/GO-BGC quality-controlled subset
and the full GDAC BGC float fleet.

---

## 1. Data Sources

| Source | Description |
|---|---|
| **Argo GDAC** | Raw BGC profile index downloaded directly from `data-argo.ifremer.fr/argo_bio-profile_index.txt.gz` |
| **argopy** | Python library (v1.4.0) configured with `src='gdac', mode='expert'`, using `ArgoIndex(index_file='bio')` |
| **SOCCOM/GO-BGC** | High-resolution QC dataset (`SOCCOM_GO-BGC_HiResQC_LIAR_26Jun2025_netcdf`) stored at `/mnt/tank/Oceanography/data/Argo/` on profx |
| **MBARI/UCSD matched CSV** | `matched_argo_bgc_profiles_bbp_v3.csv` — PACE-matched subset of BGC profiles with BING fit results |

---

## 2. Methods

### 2.1 GDAC Direct Download (`check_gdac.py`)
The Argo GDAC BGC profile index was downloaded directly using Python's `urllib` and
parsed without any intermediary library. WMO numbers were extracted from the `file`
column (format: `dac/WMO/profiles/filename.nc`). Floats with BBP700 were identified
by filtering the `parameters` column. This script can be run anywhere with standard
Python — no extra installs needed.

```python
# check_gdac.py
import urllib.request, gzip, io, pandas as pd

url = 'https://data-argo.ifremer.fr/argo_bio-profile_index.txt.gz'
print('Downloading BGC index from GDAC...')
with urllib.request.urlopen(url) as r:
    data = r.read()
with gzip.open(io.BytesIO(data)) as f:
    lines = f.read().decode('utf-8').splitlines()
header = next(i for i, l in enumerate(lines) if not l.startswith('#'))
df = pd.read_csv(io.StringIO('\n'.join(lines[header:])))
df['wmo'] = df['file'].apply(lambda x: int(x.split('/')[1]))

print(f'Total BGC profiles: {len(df):,}')
print(f'Unique floats: {df["wmo"].nunique():,}')

bbp = df[df['parameters'].str.contains('BBP700', na=False)]
print(f'Floats with BBP700: {bbp["wmo"].nunique():,}')
```

Run with:
```bash
python3 check_gdac.py
```

### 2.2 argopy vs. GDAC Comparison (`check_argo_coverage.py`)
argopy was installed locally (v1.4.0) with erddapy pinned to `<3.0` to resolve an
import incompatibility (`_quote_string_constraints` was removed in erddapy 3.x).
The script compares the live argopy index against the raw GDAC download at runtime
and reports any discrepancies.

```python
# check_argo_coverage.py
import urllib.request, gzip, io, pandas as pd
import argopy
from argopy import ArgoIndex


def get_gdac_direct(param='BBP700'):
    """Download and parse the raw GDAC BGC index directly."""
    url = 'https://data-argo.ifremer.fr/argo_bio-profile_index.txt.gz'
    print('Downloading raw GDAC index...')
    with urllib.request.urlopen(url) as r:
        data = r.read()
    with gzip.open(io.BytesIO(data)) as f:
        lines = f.read().decode('utf-8').splitlines()
    header = next(i for i, l in enumerate(lines) if not l.startswith('#'))
    df = pd.read_csv(io.StringIO('\n'.join(lines[header:])))
    df['wmo'] = df['file'].apply(lambda x: int(x.split('/')[1]))
    return df


def get_argopy_index(param='BBP700'):
    """Fetch the BGC index via argopy using GDAC source."""
    print('Fetching argopy BGC index...')
    argopy.set_options(src='gdac', mode='expert')
    idx = ArgoIndex(index_file='bio')
    idx.load()
    df = idx.to_dataframe()
    df['wmo'] = df['file'].apply(lambda x: int(x.split('/')[1]))
    return df


def compare(param='BBP700'):
    df_gdac = get_gdac_direct()
    df_argopy = get_argopy_index()

    gdac_all   = df_gdac['wmo'].nunique()
    gdac_param = df_gdac[df_gdac['parameters'].str.contains(param, na=False)]['wmo'].nunique()
    argo_all   = df_argopy['wmo'].nunique()
    argo_param = df_argopy[df_argopy['parameters'].str.contains(param, na=False)]['wmo'].nunique()

    print(f'\n=== Coverage Check (param={param}) ===')
    print(f'{"":30s} {"GDAC direct":>12} {"Argopy":>12} {"Match":>8}')
    print(f'{"All BGC floats":30s} {gdac_all:>12} {argo_all:>12} {str(gdac_all == argo_all):>8}')
    print(f'{param + " floats":30s} {gdac_param:>12} {argo_param:>12} {str(gdac_param == argo_param):>8}')

    if gdac_all == argo_all and gdac_param == argo_param:
        print('\nResult: CONFIRMED — argopy returns the complete GDAC BGC index.')
    else:
        missing = set(df_gdac['wmo'].unique()) - set(df_argopy['wmo'].unique())
        print(f'\nResult: MISMATCH — {len(missing)} floats missing from argopy.')
        print('Missing WMOs:', sorted(missing))


if __name__ == '__main__':
    compare(param='BBP700')
```

Run with:
```bash
pip install "erddapy<3.0"  # one-time fix if needed
python3 check_argo_coverage.py
```

### 2.3 SOCCOM/GO-BGC Dataset
WMO numbers were extracted from filenames in the SOCCOM/GO-BGC directory on profx.
Files follow the naming convention `<WMO>QC.nc` or `<WMO>_HRQC.nc`. Four files with
no WMO (`NO_WMO_*`) were excluded from the comparison.

```bash
ls /mnt/tank/Oceanography/data/Argo/SOCCOM_GO-BGC_HiResQC_LIAR_26Jun2025_netcdf/*.nc | wc -l
# → 685 .nc files total (681 valid WMOs + 4 no-WMO files)
```

### 2.4 MBARI/UCSD Matched CSV
WMO numbers were read from the `cruise` column of `matched_argo_bgc_profiles_bbp_v3.csv`.

---

## 3. Results

### 3.1 GDAC vs. argopy Comparison

| | GDAC direct | argopy | Match |
|---|---|---|---|
| All BGC floats | 2,924 | 2,924 | ✓ |
| BBP700 floats | 1,473 | 1,473 | ✓ |

**Conclusion:** argopy with `src='gdac', mode='expert'` retrieves the complete GDAC
BGC index with no floats dropped or filtered.

### 3.2 SOCCOM/GO-BGC vs. GDAC BBP700

| | Count |
|---|---|
| SOCCOM/GO-BGC valid WMOs | 681 |
| SOCCOM/GO-BGC no-WMO files | 4 |
| GDAC total BGC floats | 2,924 |
| GDAC BBP700 floats | 1,473 |
| In both SOCCOM and GDAC BBP700 | 611 |
| In SOCCOM but not in GDAC | 0 |
| In GDAC BBP700 but not in SOCCOM | 862 |

**Conclusion:** SOCCOM/GO-BGC is a curated subset covering 611 of 1,473 BBP700
floats (~41% of the GDAC BBP700 fleet). All 681 SOCCOM WMOs are present in GDAC —
no orphaned floats. The remaining 862 BBP700 floats in GDAC have not undergone the
SOCCOM/GO-BGC QC process.

### 3.3 MBARI/UCSD Matched CSV vs. GDAC BBP700

| | Count |
|---|---|
| MBARI/UCSD matched CSV floats | 146 |
| In both MBARI CSV and GDAC BBP700 | 146 |
| In MBARI CSV but not in GDAC | 0 |

**Conclusion:** The MBARI/UCSD matched CSV is a PACE-matched subset of 146 floats,
all confirmed present in the GDAC BBP700 index.

---

## 4. BGC Parameter Coverage (GDAC)

| Parameter | Floats |
|---|---|
| DOXY | ~2,400+ |
| CHLA | 1,490 |
| BBP700 | 1,473 |
| CDOM | 687 |
| DOWNWELLING_PAR | 399 |
| DOWN_IRRADIANCE412 | 388 |
| BBP532 | 45 |

---

## 5. Summary

- argopy configured with `src='gdac', mode='expert'` is confirmed to retrieve the
  complete GDAC BGC Argo index (2,924 floats, 1,473 with BBP700).
- The SOCCOM/GO-BGC dataset on profx covers ~41% of GDAC BBP700 floats and represents
  a high-quality curated subset, not the full fleet.
- The PAB pipeline, if expanded beyond the SOCCOM/GO-BGC files to use argopy/GDAC
  directly, would have access to 862 additional BBP700 floats not currently in the
  SOCCOM dataset.

---

## 6. Verification Scripts

Two scripts were written during this analysis and should be added to the PAB repo:

| Script | Purpose | Requires argopy? |
|---|---|---|
| `check_gdac.py` | Download and parse the raw GDAC BGC index; report float/parameter counts | No — stdlib + pandas only |
| `check_argo_coverage.py` | Compare argopy output against the raw GDAC index; flag any discrepancies | Yes — argopy + erddapy<3.0 |

Both scripts re-download the live GDAC index at runtime, so float counts will update
automatically as the fleet grows.

---

## 7. Notes

- erddapy must be pinned to `<3.0` for argopy 1.4.0 compatibility
  (`pip install "erddapy<3.0"`). erddapy 3.3.0 removed the
  `_quote_string_constraints` function that argopy imports.
- The argopy `FutureWarning` about `institution` vs. `institution_name` is harmless
  and will be resolved in a future argopy release.
- GDAC index files update daily; float counts will increase as new floats are deployed.
