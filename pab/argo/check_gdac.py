import urllib.request, gzip, io, pandas as pd

url = 'https://data-argo.ifremer.fr/argo_bio-profile_index.txt.gz'
print('Downloading BGC index from GDAC...')
with urllib.request.urlopen(url) as r:
    data = r.read()

with gzip.open(io.BytesIO(data)) as f:
    lines = f.read().decode('utf-8').splitlines()

header = next(i for i,l in enumerate(lines) if not l.startswith('#'))
df = pd.read_csv(io.StringIO('\n'.join(lines[header:])))
df['wmo'] = df['file'].apply(lambda x: int(x.split('/')[1]))

print(f'Total BGC profiles: {len(df):,}')
print(f'Unique floats: {df["wmo"].nunique():,}')

bbp = df[df['parameters'].str.contains('BBP700', na=False)]
print(f'Floats with BBP700: {bbp["wmo"].nunique():,}')
