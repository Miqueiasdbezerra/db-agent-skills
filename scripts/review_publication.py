"""Check the exact public file set offline; never publish or modify Git."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'skills/webops-secretary'
spec=importlib.util.spec_from_file_location('reviewed_webops_package',PACKAGE/'scripts/package_skill.py')
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

COPYRIGHT = 'Copyright (c) 2026 Miqueias Durans Bezerra'
LICENSE_SHA256 = '6702e4cac71885c0666bba416ef258ef3473cac7cabc71a474b756a272434a1a'


def verify_licenses(root):
    root = Path(root)
    license_text = (root/'LICENSE').read_text(encoding='utf-8')
    standalone = (root/'skills/webops-secretary/LICENSE').read_text(encoding='utf-8')
    if license_text != standalone:
        raise ValueError('Repository and standalone skill licenses differ')
    if COPYRIGHT not in license_text or hashlib.sha256(license_text.encode('utf-8')).hexdigest() != LICENSE_SHA256:
        raise ValueError('License differs from the owner-approved MIT text and copyright')
    metadata = json.loads((root/'catalog.json').read_text(encoding='utf-8'))['license']
    if metadata.get('effective_license') != 'MIT' or metadata.get('copyright') != COPYRIGHT or metadata.get('normalized_sha256') != LICENSE_SHA256:
        raise ValueError('Catalog license metadata differs from the approved license')


def check():
    verify_licenses(ROOT)
    guard.validate(PACKAGE)
    manifest=json.loads((ROOT/'release-files.json').read_text(encoding='utf-8'))
    names=manifest['files']
    if len(names)!=len(set(names)) or any(not guard._safe_name(n) for n in names):
        raise ValueError('Unsafe or duplicate publication manifest paths')
    seen=set()
    for directory,dirs,files in os.walk(ROOT,followlinks=False):
        path=Path(directory)
        dirs[:]=[d for d in dirs if d!='.git']
        for name in dirs:
            if guard._is_link(path/name): raise ValueError('Linked publication directory is not permitted')
        for name in files:
            p=path/name
            if p.suffix=='.pyc' and '__pycache__' in p.parts: continue
            rel=p.relative_to(ROOT).as_posix()
            if guard._is_link(p): raise ValueError('Linked publication file is not permitted')
            seen.add(rel)
    if seen!=set(names): raise ValueError('Publication file set differs from release-files.json; review missing/unlisted files')
    for name in names:
        if guard._sensitive_name(name): raise ValueError('Sensitive filename in publication manifest')
        data=(ROOT/name).read_text(encoding='utf-8')
        issues=guard._scan_content(name,data)
        if name.endswith('.md'): issues+=guard._check_links(ROOT,name,data)
        if issues: raise ValueError('\n'.join(issues))
        if name.endswith('.py'): ast.parse(data,filename=name)
    return {'files':len(names),'skill_files':len(guard.validate(PACKAGE)),'content_checks':'passed','license':'MIT','copyright':COPYRIGHT,'license_copies':'identical; approved normalized hash verified','publication':'This offline checker performs no public action; publication requires owner authorization','limitation':'Heuristic scan and manual provenance audit are not independent proof of all secrets or legal ownership'}


if __name__=='__main__':
    try: print(json.dumps(check(),indent=2))
    except (ValueError,OSError,KeyError) as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(1)
