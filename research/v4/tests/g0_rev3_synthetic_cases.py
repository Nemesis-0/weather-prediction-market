#!/usr/bin/env python3
"""G0 REV2 DESIGN-LEVEL synthetic counterexamples ONLY.

No network, no IBKR, no V4 implementation imported. This demonstrates the
acceptance semantics the next implementation must satisfy, NOT runtime proof.
"""
from datetime import datetime, timezone
from decimal import Decimal
import math


def utc(s):
    return datetime.fromisoformat('2026-11-12T' + s + '+00:00')


def paired_score(enrolled, paired):
    assert set(paired).issubset(enrolled)
    return None if not paired else sum(paired.values()) / len(paired)


def issue_ok(snapshot, anchor, issued, deadline, determined_at=None):
    return snapshot <= anchor and issued <= deadline and (
        determined_at is None or issued < determined_at
    )


def binding_observed_ready_by(effective, receipt, ready, cutoff):
    return effective <= cutoff and receipt <= cutoff and ready <= cutoff


def score_label_status(effective, receipt, ready, score_cutoff):
    return 'SCOREABLE' if binding_observed_ready_by(effective, receipt, ready, score_cutoff) else 'LATE_LABEL'


def training_label_available(effective, receipt, ready, update_cutoff, other_guards_pass=True):
    # Scoring maturity is intentionally absent: U governs later scheduled training.
    return other_guards_pass and binding_observed_ready_by(effective, receipt, ready, update_cutoff)


def edge_passes_at_limit(edge, positive_margin):
    # Never accept equality; both inputs in consistent per-unit cash units.
    return edge > positive_margin


def conservative_edge(p_lower, payout, authorized_ceiling, fee_upper, reserve):
    return p_lower * payout - authorized_ceiling - fee_upper - reserve


def forecast_score_allowed(paired, binary_label_mature, fee_known, budget_ok):
    # Account fee and budget intentionally do not determine score eligibility.
    return paired and binary_label_mature


def eligible_record(scope, scope_ref, event_id, reason, forecast_id=None, m0_issued_id=None, evidence_ref='evidence'):
    assert scope in {'scan','scan_item','event','model','global_health'}
    assert scope_ref and evidence_ref
    if scope == 'event':
        assert event_id
    if reason == 'ELIGIBLE_NO_TRADE':
        assert forecast_id
    if reason == 'NO_RULE':
        assert scope == 'scan_item' and forecast_id is None
    if reason == 'MISSING_M2':
        assert forecast_id is None
    return True


def run():
    checks = 0
    def verify(cond, name):
        nonlocal checks
        assert cond, name
        checks += 1

    verify(issue_ok(utc('11:54:50'), utc('11:55:00'), utc('11:55:30'), utc('11:56:00')), 'I08 allow post-anchor issued by deadline')
    verify(not issue_ok(utc('11:54:50'), utc('11:55:00'), utc('11:55:30'), utc('11:55:00')), 'I08 reject late issuance')
    verify(not issue_ok(utc('11:54:50'), utc('11:55:00'), utc('11:55:30'), utc('11:56:00'), utc('11:55:10')), 'I08 reject known outcome')
    verify(math.isclose(paired_score({'a','b'}, {'a':.12}), .12), 'I09 paired denominator')
    verify(paired_score({'a','b'}, {}) is None, 'I09 none paired')
    verify(forecast_score_allowed(True, True, False, False), 'I10 fee budget trade-only')
    verify(score_label_status(utc('12:00:00'), utc('12:08:00'), utc('12:08:00'), utc('12:06:00')) == 'LATE_LABEL', 'S04 scoring cutoff 12:06 late')
    verify(not training_label_available(utc('12:00:00'), utc('12:08:00'), utc('12:08:00'), utc('12:05:00')), 'S04 training cutoff 12:05 reject')
    verify(training_label_available(utc('12:00:00'), utc('12:08:00'), utc('12:08:00'), utc('12:10:00')), 'S04 later training 12:10 admissible despite late score')
    verify(not training_label_available(utc('12:00:00'), utc('12:08:00'), utc('12:08:00'), utc('12:10:00'), other_guards_pass=False), 'S04 other training guard still binding')
    verify(math.isclose(conservative_edge(.60,1,.40,.01,.02), .17), 'Q05 ask view')
    verify(math.isclose(conservative_edge(.60,1,.58,.01,.02), -.01), 'Q05 max limit view')
    verify(conservative_edge(.60,1,.58,.01,.02) < .05 and .58+.01<=1, 'Q05 reject even under $1')
    # Decimal exact-equality sentinel: .60 - .52 - .01 - .02 = exactly .05.
    eq_edge = conservative_edge(Decimal('0.60'), Decimal('1.00'), Decimal('0.52'), Decimal('0.01'), Decimal('0.02'))
    verify(eq_edge == Decimal('0.05'), 'Q05 exact equality vector')
    verify(not edge_passes_at_limit(eq_edge, Decimal('0.05')), 'Q05 equality must reject strictly')
    verify(edge_passes_at_limit(Decimal('0.06'), Decimal('0.05')), 'Q05 strictly above passes edge predicate only')
    verify(not edge_passes_at_limit(Decimal('0.04'), Decimal('0.05')), 'Q05 below fails')
    # U05/U06/U07 policy predicates: legality is temporal, distinct-block and schedule-based.
    scored_a=True; binding_ready_a=True; scheduled=True; different_block=True; embargo_ok=True
    verify(all([scored_a,binding_ready_a,scheduled,different_block,embargo_ok]), 'U05 prior score can later train')
    verify(not all([scored_a,binding_ready_a,scheduled,False,embargo_ok]), 'U05 same block cannot train')
    shadow=True; registered_primary_changed=False
    verify(shadow and not registered_primary_changed, 'U06 shadow no primary change')
    final_observed_ready=True; checkpoint=True; fills=0
    verify(final_observed_ready and checkpoint and fills==0, 'U07 zero fill G4')
    verify(eligible_record('scan_item','scan1:item2',None,'NO_RULE'), 'X01 scoped no-rule')
    verify(eligible_record('scan','scan1',None,'SCAN_COMPLETE'), 'X06 no event scan')
    verify(eligible_record('model','model1',None,'UPDATE'), 'X06 multi-event model')
    verify(eligible_record('global_health','incident1',None,'OUTAGE'), 'X06 health')
    verify(eligible_record('scan_item','scan1:item3',None,'MISSING_M2',m0_issued_id='m0:1'), 'X06 no fake forecast')
    verify(eligible_record('scan_item','scan1:item4','event1','ELIGIBLE_NO_TRADE',forecast_id='forecast1'), 'X01 scored ref')
    try:
        eligible_record('scan_item','scan1:item5',None,'ELIGIBLE_NO_TRADE')
    except AssertionError:
        verify(True,'X01 missing forecast rejected')
    else:
        raise AssertionError('X01 failed to reject missing forecast')
    print(f'G0 REV2 SYNTHETIC DESIGN FIXTURES: {checks}/{checks} PASS (NOT V4 runtime tests)')

if __name__ == '__main__':
    run()
