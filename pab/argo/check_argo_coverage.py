"""
check_argo_coverage.py
Verify that argopy (via GDAC) retrieves the complete BGC Argo float index.
Compares argopy output against the raw GDAC bio-profile index file.

Usage:
    python3 check_argo_coverage.py
"""

import urllib.request
import gzip
import io
import pandas as pd
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
