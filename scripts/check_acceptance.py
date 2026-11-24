"""Fail closed until E supplies complete, versioned final AC evidence."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate_report(report: dict, root: Path = ROOT):
    expected = {f'AC-{owner}{number:02d}' for owner, count in [('A', 8), ('B', 4), ('C', 4), ('D', 3), ('E', 3), ('F', 2)]
                for number in range(1, count + 1)}
    version = json.loads((root / 'contracts/version.json').read_text(encoding='utf-8'))['contract_version']
    if report.get('contract_version') != version:
        raise ValueError('Final report contract_version is missing or stale')
    if not re.fullmatch(r'[0-9a-f]{40}', report.get('commit', '')):
        raise ValueError('Final report must identify the full tested commit SHA')
    items = report.get('items', [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError('Final report items must be a list of AC records')
    ids = [item.get('id') for item in items]
    if len(ids) != len(expected) or set(ids) != expected:
        raise ValueError('Final report must contain exactly the 24 unique AC identifiers')
    for item in items:
        if item.get('status') != 'passed':
            raise ValueError(f'{item["id"]} is not passed')
        if not item.get('reviewer') or not item.get('actual_result', '').strip():
            raise ValueError(f'{item["id"]} lacks reviewer or actual result')
        evidence = item.get('evidence', [])
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f'{item["id"]} lacks evidence')
        for entry in evidence:
            if not isinstance(entry, str):
                raise ValueError(f'{item["id"]} evidence must use repository paths')
            path = (root / entry).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                raise ValueError(f'{item["id"]} evidence file is missing or outside repository: {entry}')


def main():
    report_path = ROOT / 'docs/integration/results/acceptance.json'
    if not report_path.is_file():
        raise ValueError('Final acceptance report is not ready: create acceptance.json only after real verification')
    validate_report(json.loads(report_path.read_text(encoding='utf-8')))
    print('24 final AC records and evidence paths are complete; human evidence still requires E review')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError) as exc:
        print(f'Acceptance NOT complete: {exc}', file=sys.stderr)
        raise SystemExit(1)
