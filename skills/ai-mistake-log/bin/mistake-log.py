#!/usr/bin/env python3
"""mistake-log — AI 실수 기록을 관리하고, 거기서 나온 규칙을 실제로 적용되는 곳에 넣는다.

기록(정본)은 저장소 밖 ~/.claude/mistakes/<날짜>-<slug>.md 에 둔다. 전역 지침의 블록은 기록에서 다시 만든다.

  mistake-log.py new <slug> --title T --rule R [--guard ID] [--date YYYY-MM-DD]
  mistake-log.py list
  mistake-log.py sync [--dry-run]          전역 지침(~/.claude/CLAUDE.md, ~/.codex/AGENTS.md)의 블록 갱신
  mistake-log.py check                     어긋난 곳 보고 (있으면 종료 코드 1)
  mistake-log.py install-hook [--dry-run]  settings.json 에 bash-guard 훅 등록

경로는 환경변수로 바꿀 수 있다 (시험용): AI_MISTAKES_DIR, AI_MISTAKES_CLAUDE_MD, AI_MISTAKES_CODEX_MD,
AI_MISTAKES_SETTINGS.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser('~')
DIR = os.environ.get('AI_MISTAKES_DIR', os.path.join(HOME, '.claude', 'mistakes'))
TARGETS = [
    ('Claude', os.environ.get('AI_MISTAKES_CLAUDE_MD', os.path.join(HOME, '.claude', 'CLAUDE.md'))),
    ('Codex', os.environ.get('AI_MISTAKES_CODEX_MD', os.path.join(HOME, '.codex', 'AGENTS.md'))),
]
SETTINGS = os.environ.get('AI_MISTAKES_SETTINGS', os.path.join(HOME, '.claude', 'settings.json'))
GUARD = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'bash-guard.py')
# 훅은 저장소 실물이 아니라 설치 경로(심볼릭 링크)로 등록한다. 저장소를 옮겨도 install.sh 만 다시 돌리면 된다.
GUARD_INSTALLED = os.path.join(HOME, '.claude', 'skills', 'ai-mistake-log', 'bin', 'bash-guard.py')

BEGIN = '<!-- ai-mistake-log:begin -->'
END = '<!-- ai-mistake-log:end -->'
SLUG = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')

TEMPLATE = """---
date: {date}
title: {title}
rule: {rule}
guard: {guard}
---

## 무엇을 했나

<실행한 명령·한 일을 그대로. 어느 세션, 무엇을 하려던 중이었는지>

## 무엇이 망가졌나

<피해 범위. 숫자로 셀 수 있으면 숫자로>

## 왜 (근본 원인)

<"부주의" 가 아니라 메커니즘. 무엇을 잘못 알고 있었나>

## 증거

<로그·재현 명령과 그 출력. 재현은 해가 없는 방법으로>

## 재발 방지

- 규칙: 위 rule
- 적용한 곳: 전역 지침(sync){guard_line}
"""


def fail(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def read_text(path, default=None):
    """파일 내용. default 를 주면 파일이 없을 때 그 값을 돌려준다."""
    if default is not None and not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return f.read()


def load_settings():
    return json.loads(read_text(SETTINGS)) if os.path.exists(SETTINGS) else {}


# ---------------------------------------------------------------- records
def parse_record(path):
    text = read_text(path)
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
    meta['file'] = os.path.basename(path)
    meta['path'] = path
    return meta


def records():
    if not os.path.isdir(DIR):
        return []
    return [parse_record(os.path.join(DIR, f)) for f in sorted(os.listdir(DIR))
            if f.endswith('.md') and not f.startswith('.') and f != 'README.md']


def guard_ids():
    try:
        out = subprocess.run([sys.executable, GUARD, '--list'], capture_output=True, text=True, timeout=10)
        return set(out.stdout.split())
    except Exception:
        return set()


# ---------------------------------------------------------------- block
def render_block():
    lines = [BEGIN,
             '## 지난 실수에서 나온 규칙',
             '',
             '`ai-mistake-log` 스킬이 `~/.claude/mistakes/` 의 기록으로 만든 블록이야. 여기를 직접 고치지 말고 '
             '기록을 고친 뒤 `mistake-log.py sync` 를 돌려. 규칙마다 자세한 경위는 그 기록에 있어.',
             '']
    rs = [r for r in records() if r.get('rule')]
    if not rs:
        lines.append('- (아직 없음)')
    for r in rs:
        guard = f" · 훅이 막음: `{r['guard']}`" if r.get('guard') else ''
        lines.append(f"- {r['rule']} (기록: `~/.claude/mistakes/{r['file']}`{guard})")
    lines.append(END)
    return '\n'.join(lines) + '\n'


def find_block(text):
    """블록의 (시작, 끝) 위치. 표시는 줄 전체로만 인정하고 END 는 BEGIN 뒤에서 찾는다.
    사용자 글이 표시를 본문에 언급만 한 경우를 블록으로 착각해 그 사이를 지우지 않게."""
    m = re.search(rf'^{re.escape(BEGIN)}[ \t]*$', text, re.M)
    if not m:
        return None
    e = re.compile(rf'^{re.escape(END)}[ \t]*(\n|$)', re.M).search(text, m.end())
    if not e:
        return None
    return m.start(), e.end()


def apply_block(text, block):
    span = find_block(text)
    if span:
        a, b = span
        return text[:a] + block + text[b:]
    if text and not text.endswith('\n'):
        text += '\n'
    return text + ('\n' if text else '') + block


def backup(path):
    bdir = os.path.join(DIR, '.backups')
    os.makedirs(bdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    name = path.replace(HOME, '~').strip('/').replace('/', '_')
    dst = os.path.join(bdir, f'{name}.{stamp}')
    shutil.copy2(path, dst)
    return dst


def valid_date(s):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return False
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- commands
def cmd_new(a):
    if not SLUG.match(a.slug):
        fail('slug 는 소문자·숫자·하이픈만 돼 (예: bsd-pkill-trailing-options)', 2)
    if a.guard and a.guard not in guard_ids():
        fail(f'bash-guard 에 없는 guard id 야: {a.guard} (bash-guard.py --list)', 2)
    for field in (a.title, a.rule):
        if '\n' in field:
            fail('title·rule 은 한 줄로 써', 2)
    date = a.date or datetime.date.today().isoformat()
    if not valid_date(date):   # 파일 이름에 들어가니 '../x' 같은 값으로 기록 폴더 밖에 쓰지 않게
        fail(f'--date 는 YYYY-MM-DD 형식이어야 해: {date}', 2)
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, f'{date}-{a.slug}.md')
    if os.path.exists(path):
        fail(f'이미 있어: {path}', 2)
    guard_line = f', 훅 `{a.guard}`(install-hook)' if a.guard else ''
    with open(path, 'w', encoding='utf-8') as f:
        f.write(TEMPLATE.format(date=date, title=a.title, rule=a.rule, guard=a.guard or '', guard_line=guard_line))
    print(path)


def cmd_list(a):
    rs = records()
    if not rs:
        print(f'기록 없음 ({DIR})')
        return
    for r in rs:
        print(f"{r.get('date', '?'):10}  {r.get('guard') or '-':28}  {r.get('title', r['file'])}")


def cmd_sync(a):
    block = render_block()
    for label, path in TARGETS:
        old = read_text(path, '')
        new = apply_block(old, block)
        if new == old:
            print(f'{label:7} 변경 없음  {path}')
            continue
        if a.dry_run:
            print(f"{label:7} {'만들 예정' if not old else '갱신 예정'}  {path}")
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        saved = backup(path) if os.path.exists(path) else None
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)
        print(f"{label:7} {'만듦' if not old else '갱신'}  {path}" + (f'  (백업 {saved})' if saved else ''))


def hook_entry():
    return {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': GUARD_INSTALLED, 'timeout': 10}]}


def hook_installed(settings):
    for group in (settings.get('hooks') or {}).get('PreToolUse') or []:
        for h in group.get('hooks') or []:
            if h.get('command', '').endswith('ai-mistake-log/bin/bash-guard.py'):
                return True
    return False


def cmd_install_hook(a):
    settings = load_settings()
    if hook_installed(settings):
        print(f'이미 등록돼 있어: {SETTINGS}')
        return
    if not os.path.exists(GUARD_INSTALLED):
        fail(f'훅 스크립트가 설치 경로에 없어: {GUARD_INSTALLED}\n저장소에서 ./bin/install.sh 를 먼저 돌려', 2)
    settings.setdefault('hooks', {}).setdefault('PreToolUse', []).append(hook_entry())
    if a.dry_run:
        print(json.dumps({'hooks': {'PreToolUse': settings['hooks']['PreToolUse']}}, ensure_ascii=False, indent=2))
        return
    saved = None
    if os.path.exists(SETTINGS):
        stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        saved = f'{SETTINGS}.bak-ai-mistake-log-{stamp}'
        shutil.copy2(SETTINGS, saved)
    tmp = SETTINGS + '.tmp-ai-mistake-log'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        f.write('\n')
    json.loads(read_text(tmp))   # 다시 읽어 확인
    os.replace(tmp, SETTINGS)
    print(f'등록함: {SETTINGS}' + (f'  (백업 {saved})' if saved else ''))


def cmd_check(a):
    problems = []
    ids = guard_ids()
    for r in records():
        if not r.get('rule'):
            problems.append(f"rule 이 비어 있음: {r['file']}")
        if r.get('guard') and r['guard'] not in ids:
            problems.append(f"없는 guard id: {r['guard']} ({r['file']})")
    block = render_block()
    for label, path in TARGETS:
        text = read_text(path, '')
        if apply_block(text, block) != text:
            problems.append(f'{label} 전역 지침의 블록이 기록과 다름 → sync: {path}')
    if any(r.get('guard') for r in records()):
        settings = load_settings()
        if not hook_installed(settings):
            problems.append(f'guard 가 있는 기록이 있는데 훅이 등록 안 됨 → install-hook: {SETTINGS}')
    for p in problems:
        print('- ' + p)
    print('문제 없음' if not problems else f'{len(problems)}건')
    return 1 if problems else 0


def main():
    p = argparse.ArgumentParser(description='AI 실수 기록과 규칙 적용')
    sub = p.add_subparsers(dest='cmd', required=True)
    n = sub.add_parser('new', help='빈 기록 만들기')
    n.add_argument('slug')
    n.add_argument('--title', required=True)
    n.add_argument('--rule', required=True, help='전역 지침에 들어갈 한 줄. 상황이 아니라 행동으로')
    n.add_argument('--guard', default='', help='기계적으로 막는 bash-guard 검사기 id')
    n.add_argument('--date')
    sub.add_parser('list')
    s = sub.add_parser('sync')
    s.add_argument('--dry-run', action='store_true')
    sub.add_parser('check')
    h = sub.add_parser('install-hook')
    h.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    fn = {'new': cmd_new, 'list': cmd_list, 'sync': cmd_sync, 'check': cmd_check,
          'install-hook': cmd_install_hook}[a.cmd]
    sys.exit(fn(a) or 0)


if __name__ == '__main__':
    main()
