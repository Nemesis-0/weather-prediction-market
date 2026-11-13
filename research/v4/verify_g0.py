#!/usr/bin/env python3
"""Self-contained byte-integrity and synthetic-contract verifier for V4 G0.

Requires only the repository copy: no delivery archive, machine paths, network or broker.
"""
from pathlib import Path
import hashlib
import json
import runpy


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "g0_manifest.json").read_text(encoding="utf-8"))
    for rel, info in manifest["reviewed_bytes"].items():
        path = root / rel
        data = path.read_bytes()
        if len(data) != info["bytes"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise SystemExit(f"G0 reviewed bytes mismatch: {rel}")
    runpy.run_path(str(root / 'tests/g0_rev3_synthetic_cases.py'), run_name='__main__')
    print(f"V4 G0 REPOSITORY VERIFY: PASS | exact reviewed inputs: {len(manifest['reviewed_bytes'])}")


if __name__ == "__main__":
    main()
