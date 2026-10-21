"""Recover headers omitted by the upstream sdist from its exact Git commit.

Cross-check all four sdist C files against Git blobs before using any header.
Only source text is downloaded; no setup or dataset scripts are executed.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import urllib.request

REVISION = '6a761c4eb01905cfcb1139b0b158547c55edd4df'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent':'BrainFusion-verified-source-build'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(8 * 1024**2)
    return raw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    version_ast=ast.parse((args.source_root/'radiomics/_version.py').read_text(encoding='utf-8'))
    encoded=next(node.value.value for node in version_ast.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='version_json' for t in node.targets))
    version=json.loads(encoded)
    assert version['full-revisionid']==REVISION and version['version']=='v3.1.0'
    tree_url='https://api.github.com/repos/AIM-Harvard/pyradiomics/git/trees/'+REVISION+'?recursive=1'
    raw_tree=fetch(tree_url)
    (output/'git-tree.json').write_bytes(raw_tree)
    tree=json.loads(raw_tree)
    assert not tree.get('truncated')
    entries={item['path']:item for item in tree['tree']}
    records=[]
    for name in ('_cmatrices.c','cmatrices.c','_cshape.c','cshape.c','cmatrices.h','cshape.h'):
        path='radiomics/src/'+name
        url='https://raw.githubusercontent.com/AIM-Harvard/pyradiomics/'+REVISION+'/'+path
        raw=fetch(url)
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert blob==entries[path]['sha'] and len(raw)==entries[path]['size'], 'Git blob mismatch'
        record={'path':path,'url':url,'git_blob_sha1':blob,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        if name.endswith('.c'):
            assert (args.source_root/path).read_bytes()==raw, 'sdist C source differs from recorded upstream commit'
            record['sdist_identical']=True
        else:
            directory=output/'include';directory.mkdir(exist_ok=True)
            (directory/name).write_bytes(raw)
        records.append(record)
    (output/'headers.json').write_text(json.dumps({'status':'passed','upstream_revision':REVISION,'source_c_files_identical':4,'sources':records,'tree_url':tree_url,'tree_sha256':hashlib.sha256(raw_tree).hexdigest(),'license':'BSD-3-Clause','source_archive_unchanged':True},indent=2),encoding='utf-8')
    print('Four sdist C files match exact upstream commit; both missing headers verified')


if __name__=='__main__':main()
