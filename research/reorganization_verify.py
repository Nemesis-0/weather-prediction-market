#!/usr/bin/env python3
"""Verify the exact archive migration ledger, documentation links and V3 freeze adapter."""
from pathlib import Path
import hashlib, json, re, sys

def verify(root: Path) -> None:
    d = json.loads((root/'research/migration_ledger.json').read_text())
    assert d['original_file_count'] == len(d['files']) == 215
    unchanged = 0
    for old, rec in d['files'].items():
        target = root / rec['new_path']
        if not target.is_file():
            raise RuntimeError(f'MISSING migrated file: {rec["new_path"]}')
        actual = target.read_bytes()
        if len(actual) != rec['new_bytes'] or hashlib.sha256(actual).hexdigest() != rec['new_sha256']:
            raise RuntimeError(f'MIGRATION DIGEST mismatch: {rec["new_path"]}')
        if rec['byte_identical']:
            unchanged += 1
            if rec['new_sha256'] != rec['original_sha256']:
                raise RuntimeError(f'false byte-identical claim: {old}')
    for path, rec in d['extra_files'].items():
        actual = (root/path).read_bytes()
        if hashlib.sha256(actual).hexdigest() != rec['sha256'] or len(actual) != rec['bytes']:
            raise RuntimeError(f'ADDED FILE mismatch: {path}')
    if unchanged < 140:
        raise RuntimeError('too few original files retained byte-for-byte')
    links = 0
    for p in root.rglob('*.md'):
        # Do not scan hidden/local ignored workspaces or private raw data.
        if 'research' not in p.parts and p.name not in ('README.md', 'DATA_POLICY.md'):
            continue
        for m in re.finditer(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            s = m.group(1).split('#')[0].split('?')[0]
            if not s or s.startswith(('https://','http://','mailto:','/','#','data:')):
                continue
            links += 1
            if not (p.parent/s).exists():
                raise RuntimeError(f'BROKEN LINK: {p.relative_to(root)} -> {s}')
    sys.path.insert(0,str(root))
    from research.v3.code.study1.frozen import verify_freeze_manifest
    res = verify_freeze_manifest(root)
    assert res['manifest_sha256'] == d['files']['configs/v3/study1_freeze_manifest.json']['original_sha256']
    print(f'REORGANIZATION VERIFY: PASS | original files: {len(d["files"])} | unchanged bytes: {unchanged} | added files: {len(d["extra_files"])} | verified links: {links} | V3 freeze adapter: PASS')

if __name__ == '__main__':
    verify(Path(__file__).resolve().parents[1])
