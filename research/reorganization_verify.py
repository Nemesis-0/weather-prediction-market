#!/usr/bin/env python3
"""Verify the 2026 migration ledger, explicit later public-documentation revisions, links and V3 freeze adapter.

The historical migration ledger is never overwritten to reflect newer prose.
A separate allowlisted publication manifest authenticates revised presentation
files while retaining the original 2026-11-12 post-migration hashes.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

PUBLICATION_ALLOWLIST = frozenset({
    'README.md',
    'DATA_POLICY.md',
    'research/README.md',
    'research/v1/README.md',
    'research/v2/README.md',
    'research/v3/README.md',
    'research/shared/README.md',
    'research/reorganization_verify.py',
})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(root: Path) -> None:
    d = json.loads((root / 'research/migration_ledger.json').read_text())
    if d['original_file_count'] != len(d['files']) or len(d['files']) != 215:
        raise RuntimeError('Invalid migration ledger inventory')

    originals = {rec['new_path']: rec for rec in d['files'].values()}
    extras = d['extra_files']
    known = set(originals) | set(extras)

    publication_path = root / 'research/public_documentation_manifest.json'
    overrides = {}
    if publication_path.is_file():
        publication = json.loads(publication_path.read_text(encoding='utf-8'))
        if publication.get('baseline_commit') != '74f672b':
            raise RuntimeError('Unexpected public-documentation baseline')
        overrides = publication.get('updated_files', {})
        if set(overrides) != PUBLICATION_ALLOWLIST:
            raise RuntimeError('Public documentation manifest not limited to approved files')
        if not set(overrides).issubset(known):
            raise RuntimeError('Publication manifest names an unknown migrated path')

    def check(path: str, historical_hash: str, historical_length: int):
        data = (root / path).read_bytes()
        x = overrides.get(path)
        if x:
            if x.get('migration_sha256') != historical_hash or x.get('migration_bytes') != historical_length:
                raise RuntimeError(f'Incorrect historical-migration identity: {path}')
            expected_hash, expected_length = x['current_sha256'], x['current_bytes']
        else:
            expected_hash, expected_length = historical_hash, historical_length
        if digest(data) != expected_hash or len(data) != expected_length:
            raise RuntimeError(f'File integrity mismatch: {path}')

    unchanged = 0
    for old, rec in d['files'].items():
        check(rec['new_path'], rec['new_sha256'], rec['new_bytes'])
        if rec['byte_identical']:
            unchanged += 1
            if rec['new_sha256'] != rec['original_sha256']:
                raise RuntimeError(f'False byte-identical claim: {old}')

    for path, rec in extras.items():
        check(path, rec['sha256'], rec['bytes'])

    if unchanged < 140:
        raise RuntimeError('Too few original files retained byte-for-byte')

    links = 0
    for p in root.rglob('*.md'):
        if 'research' not in p.parts and p.name not in ('README.md', 'DATA_POLICY.md'):
            continue
        for m in re.finditer(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
            s = m.group(1).split('#')[0].split('?')[0]
            if not s or s.startswith(('https://', 'http://', 'mailto:', '/', '#', 'data:')):
                continue
            links += 1
            if not (p.parent / s).exists():
                raise RuntimeError(f'BROKEN LINK: {p.relative_to(root)} -> {s}')

    sys.path.insert(0, str(root))
    from research.v3.code.study1.frozen import verify_freeze_manifest
    result = verify_freeze_manifest(root)
    if result['manifest_sha256'] != d['files']['configs/v3/study1_freeze_manifest.json']['original_sha256']:
        raise RuntimeError('V3 frozen-manifest identity changed')

    print(
        f'REPOSITORY VERIFY: PASS | original files: {len(d["files"])}'
        f' | originally unchanged bytes: {unchanged} | publication updates: {len(overrides)}'
        f' | verified links: {links} | V3 freeze adapter: PASS'
    )


if __name__ == '__main__':
    verify(Path(__file__).resolve().parents[1])
