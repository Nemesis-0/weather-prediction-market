# V1–V3 directory reorganization — 2026-11-12

**Scope:** one physical repository-layout upgrade. No new model, V4 execution, broker order, alpha result, or scientific hypothesis was added.

## Source and immutability

- Source: 215 tracked-file snapshot from `WEATHER_PM_REVIEW_20261112-135412` (its two `_review_meta` files were review-only and are not part of the repository).
- A complete [old-path → new-path, old/new SHA256 and byte-count ledger](migration_ledger.json) accompanies this commit.
- Every original file is accounted for. Most scientific result tables, protocols, and old freeze manifests retain **exact original bytes**.
- Where imports, runtime roots, path references, or Markdown links needed updating, the ledger transparently records changed bytes. These changes do not retroactively replace the original historical freeze.
- The original V3 Study 1 SHA256 manifest still refers to the **pre-reorganization snapshot**. It remains unedited; [a separate runtime integrity ledger](v3/configs/study1_reorg_runtime_manifest.json) checks the relocated/adapted files. Original file identity can be tested using the previous Git commit/tag.

## Runtime and data

- Current V3 CLI: `python research/v3/code/cli/run_ibkr_capability_audit.py --help`.
- Current deterministic suite: `python -m pytest -q research/v3/tests`.
- Historical V1/V2 scripts still read untracked `data/` from repo root. No private dataset is moved or deleted.
- Old local `results/`, `configs/v3/local/`, `local_artifacts/`, `runtime/` and similar ignored folders are not deleted. They remain local if present; old script paths and third-party links outside the repository may require updating.
- Do not interpret a passing moved-code runtime check as re-execution of unavailable historical V1/V2 data or validation against the old freeze digests.

## Installation safeguards

The ZIP installer checks the original file digests and a clean original Git working tree, archives the original tracked files, performs file-by-file moves, checks final file digests and tests, and rolls back to the original branch on install failure. It **never** pushes to GitHub; publishing is a separate human-confirmed operation.
