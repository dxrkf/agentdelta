#!/usr/bin/env python3
"""Compare explicit agent capability inventories without invoking any tools."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

FIELDS = {'name', 'actions', 'resources', 'approval'}
ACTIONS = {'read', 'write', 'delete', 'execute', 'send'}
APPROVAL = {'always': 0, 'writes': 1, 'never': 2}


def load(path):
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'tools'} or not isinstance(data['tools'], list):
        raise ValueError('expected an object containing only a tools array')
    tools = {}
    for item in data['tools']:
        if not isinstance(item, dict) or set(item) != FIELDS:
            raise ValueError('each tool needs exactly name, actions, resources, approval')
        name = item['name']
        if not isinstance(name, str) or not name.strip() or name != name.strip() or name in tools:
            raise ValueError('tool names must be unique nonempty strings without outer spaces')
        for field in ('actions', 'resources'):
            values = item[field]
            if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x or x != x.strip() for x in values):
                raise ValueError(f'{name}: {field} must be nonempty string arrays')
            if len(values) != len(set(values)):
                raise ValueError(f'{name}: duplicate {field}')
        if not set(item['actions']) <= ACTIONS:
            raise ValueError(f'{name}: unsupported action')
        if not isinstance(item['approval'], str) or item['approval'] not in APPROVAL:
            raise ValueError(f'{name}: approval must be always, writes, or never')
        tools[name] = item
    return tools, hashlib.sha256(raw).hexdigest()


def compare(before, after):
    findings = []
    def add(tool, level, rule, detail):
        findings.append(dict(tool=tool, severity=level, rule=rule, detail=detail))
    for name in sorted(after):
        new = after[name]
        old = before.get(name)
        if old is None:
            add(name, 'review', 'TOOL_ADDED', 'New tool identity; review its full capability set')
        old_actions = set(old['actions']) if old else set()
        added = set(new['actions']) - old_actions
        if added:
            level = 'high' if added & {'delete', 'execute', 'send'} else 'review'
            add(name, level, 'ACTIONS_ADDED', ', '.join(sorted(added)))
        old_resources = set(old['resources']) if old else set()
        resources = set(new['resources']) - old_resources
        # Resource strings are opaque policy labels. Only literal * is universal.
        if resources and '*' not in old_resources:
            add(name, 'high' if '*' in resources else 'review', 'RESOURCES_ADDED', ', '.join(sorted(resources)))
        if old and APPROVAL[new['approval']] > APPROVAL[old['approval']]:
            add(name, 'high', 'APPROVAL_RELAXED', old['approval'] + ' -> ' + new['approval'])
        if (old is None or added) and new['approval'] == 'never' and set(new['actions']) & {'write', 'delete', 'execute', 'send'}:
            add(name, 'high', 'UNATTENDED_MUTATION', 'New mutation capability has no required approval')
    for name in sorted(set(before) - set(after)):
        add(name, 'info', 'TOOL_REMOVED', 'Tool identity removed')
    return findings


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before')
    p.add_argument('after')
    p.add_argument('--json', action='store_true')
    p.add_argument('--fail-on', choices=['high', 'review', 'never'], default='high')
    args = p.parse_args()
    try:
        before, bh = load(args.before)
        after, ah = load(args.after)
        findings = compare(before, after)
    except (OSError, ValueError, UnicodeError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    report = dict(before_sha256=bh, after_sha256=ah, findings=findings)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        for f in findings:
            print(f"{f['severity'].upper():6} {f['tool']} | {f['rule']} | {f['detail']}")
        print(f'{len(findings)} finding(s). No tools invoked.')
    levels = {'never': set(), 'high': {'high'}, 'review': {'review', 'high'}}
    return int(any(f['severity'] in levels[args.fail_on] for f in findings))


if __name__ == '__main__':
    sys.exit(main())
