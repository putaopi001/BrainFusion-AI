"""Read official package metadata only; never install or execute remote content."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

SOURCES = {
    'pypi': 'https://pypi.org/pypi/pyradiomics/3.1.0/json',
    'conda_forge': 'https://api.anaconda.org/package/conda-forge/pyradiomics',
    'radiomics_channel': 'https://api.anaconda.org/package/radiomics/pyradiomics',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve());output.mkdir(exist_ok=False)
    def fetch(item):
        name,url=item
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'BrainFusion-local-environment-audit'})
            with urllib.request.urlopen(request,timeout=15) as response: raw=response.read(8*1024**2)
            data=json.loads(raw);(output/(name+'.json')).write_bytes(raw)
            files=data['urls'] if name=='pypi' else data.get('files',[])
            names=[f.get('filename',f.get('basename','')) for f in files]
            windows=[n for n in names if 'win_amd64' in n or 'win-64/' in n]
            compatible=[n for n in windows if any(tag in n for tag in ('cp311','cp312','cp313','py311','py312','py313'))]
            return name,{'status':'fetched','url':url,'metadata_sha256':hashlib.sha256(raw).hexdigest(),
                         'bytes':len(raw),'windows_builds':windows,'python311plus_windows_builds':compatible}
        except (urllib.error.URLError,ValueError) as error:return name,{'status':'unavailable','url':url,'error':str(error)}
    with ThreadPoolExecutor(max_workers=3) as pool: result=dict(pool.map(fetch,SOURCES.items()))
    (output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
