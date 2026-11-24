"""The final gate must reject partial, stale, or unverifiable AC reports."""
from copy import deepcopy
import json

import pytest

from scripts.check_acceptance import validate_report
from scripts.check_baseline import load


@pytest.fixture
def report_environment(tmp_path):
    (tmp_path / 'contracts').mkdir()
    (tmp_path / 'contracts/version.json').write_text(json.dumps({'contract_version': '1.1.0'}), encoding='utf-8')
    (tmp_path / 'proof.txt').write_text('Synthetic gate test evidence only', encoding='utf-8')
    report = load('docs/integration/results/acceptance-template.json')
    report['commit'] = 'a' * 40
    for item in report['items']:
        item.update(status='passed', reviewer='test-only', actual_result='synthetic structural test', evidence=['proof.txt'])
    return report, tmp_path


def test_complete_report_structure_is_accepted(report_environment):
    report, root = report_environment
    validate_report(report, root)


@pytest.mark.parametrize('corruption', ['missing_ac', 'duplicate_ac', 'pending', 'stale', 'missing_evidence', 'outside_evidence', 'missing_commit'])
def test_incomplete_or_unverifiable_report_is_rejected(report_environment, corruption):
    report, root = report_environment
    if corruption == 'missing_ac':
        report['items'].pop()
    elif corruption == 'duplicate_ac':
        report['items'][-1] = deepcopy(report['items'][0])
    elif corruption == 'pending':
        report['items'][0]['status'] = 'pending'
    elif corruption == 'stale':
        report['contract_version'] = '1.0.0'
    elif corruption == 'missing_evidence':
        report['items'][0]['evidence'] = ['absent.txt']
    elif corruption == 'outside_evidence':
        report['items'][0]['evidence'] = ['../proof.txt']
    else:
        report['commit'] = ''
    with pytest.raises(ValueError):
        validate_report(report, root)
