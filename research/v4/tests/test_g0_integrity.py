"""Regression fences for G0 design semantics; no live code or network."""
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import hashlib
import json
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]


def _synth():
    path = ROOT / 'tests/g0_rev3_synthetic_cases.py'
    spec = spec_from_file_location('g0_frozen_semantics', path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_frozen_reviewed_documents_match_manifest():
    manifest = json.loads((ROOT/'g0_manifest.json').read_text())
    assert len(manifest['reviewed_bytes']) == 6
    for rel, meta in manifest['reviewed_bytes'].items():
        data = (ROOT/rel).read_bytes()
        assert len(data) == meta['bytes']
        assert hashlib.sha256(data).hexdigest() == meta['sha256']


def test_s04_scoring_and_training_clocks_separate():
    f = _synth()
    t = f.utc
    assert f.score_label_status(t('12:00:00'),t('12:08:00'),t('12:08:00'),t('12:06:00')) == 'LATE_LABEL'
    assert not f.training_label_available(t('12:00:00'),t('12:08:00'),t('12:08:00'),t('12:05:00'))
    assert f.training_label_available(t('12:00:00'),t('12:08:00'),t('12:08:00'),t('12:10:00'))


def test_q05_strict_limit_edge_and_one_dollar_cap():
    f = _synth()
    e = f.conservative_edge(Decimal('.60'), Decimal('1'), Decimal('.52'), Decimal('.01'), Decimal('.02'))
    assert e == Decimal('.05')
    assert not f.edge_passes_at_limit(e, Decimal('.05'))
    assert f.conservative_edge(Decimal('.60'), Decimal('1'), Decimal('.58'), Decimal('.01'), Decimal('.02')) < Decimal('.05')
    assert Decimal('.58') + Decimal('.01') <= Decimal('1')
