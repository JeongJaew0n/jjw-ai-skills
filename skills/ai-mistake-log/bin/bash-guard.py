#!/usr/bin/env python3
"""bash-guard — 지난 실수에서 나온 규칙으로 Bash 명령을 실행 전에 검사하는 Claude Code PreToolUse 훅.

settings.json 의 hooks.PreToolUse (matcher "Bash") 에 등록해서 쓴다 (mistake-log.py install-hook).
막아야 할 때만 permissionDecision "deny" 를 출력하고, 나머지는 아무것도 출력하지 않고 0 으로 끝난다.

고장 나면 통과시킨다(fail-open). 파싱 오류로 모든 Bash 가 막히면 그게 더 큰 사고다.

  bash-guard.py              훅으로 실행 (stdin 에 훅 JSON)
  bash-guard.py --list       검사기 id 목록
  bash-guard.py --self-test  막을 명령·통과시킬 명령 표 검사
  bash-guard.py --check CMD  명령 하나를 검사해 결과만 출력
"""

import json
import os
import re
import shlex
import sys

SEP = {';', '&', '&&', '|', '||', '|&', ';;', '(', ')', '\n'}
SUBST = '__SUBST__'


# ---------------------------------------------------------------- shell parsing
def split_substitutions(cmd):
    """$(...) 와 `...` 를 한 단어로 바꾸고, 안쪽 명령들을 따로 돌려준다. 작은따옴표 안은 건드리지 않는다."""
    out, inner, i, n = [], [], 0, len(cmd)
    quote = None
    while i < n:
        c = cmd[i]
        if quote == "'":
            out.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if c == '\\' and i + 1 < n:
            out.append(cmd[i:i + 2])
            i += 2
            continue
        if c in ('"', "'") and quote is None:
            quote = c
        elif c == '"' and quote == '"':
            quote = None
        if c == '$' and cmd.startswith('$(', i):
            depth, j = 0, i + 1
            while j < n:
                if cmd[j] == '(':
                    depth += 1
                elif cmd[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner.append(cmd[i + 2:j])
            out.append(SUBST)
            i = j + 1
            continue
        if c == '`':
            j = cmd.find('`', i + 1)
            if j < 0:
                j = n
            inner.append(cmd[i + 1:j])
            out.append(SUBST)
            i = j + 1
            continue
        out.append(c)
        i += 1
    return ''.join(out), inner


def tokens(cmd):
    lx = shlex.shlex(cmd, posix=True, punctuation_chars='();<>|&\n')
    lx.whitespace = ' \t\r'
    lx.whitespace_split = True
    lx.commenters = ''
    return list(lx)


def segments(cmd):
    """명령 문자열을 단순 명령 단위의 토큰 목록들로 나눈다. 명령 치환 안쪽도 따로 포함한다."""
    flat, inner = split_substitutions(cmd)
    segs, cur = [], []
    for t in tokens(flat):
        if t in SEP:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    for sub in inner:
        segs.extend(segments(sub))
    return segs


ASSIGN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
# 앞에 붙어 실제 명령을 뒤로 미루는 것들. 값: 값을 받는 옵션 집합 (None 이면 옵션을 따로 해석하지 않음)
WRAPPERS = {
    'sudo': {'-u', '-g', '-h', '-p', '-C', '-D', '-r', '-t', '-U'},
    'env': {'-u', '-C', '-S'},
    'command': set(), 'exec': {'-a'}, 'nohup': set(), 'time': set(), 'builtin': set(),
    'timeout': {'-s', '-k', '--signal', '--kill-after'},
    'nice': {'-n'},
    'xargs': {'-n', '-I', '-L', '-P', '-s', '-E', '-J', '-R', '-S', '-d', '-a'},
}
# timeout 은 옵션 뒤에 DURATION 인자가 하나 더 있다
WRAPPER_EXTRA_ARGS = {'timeout': 1}


def real_command(seg):
    """접두(VAR=, sudo, env, xargs …)를 벗겨 (명령 이름, 인자 목록) 을 돌려준다."""
    i = 0
    while i < len(seg):
        t = seg[i]
        if ASSIGN.match(t):
            i += 1
            continue
        name = os.path.basename(t)
        if name in WRAPPERS:
            takes = WRAPPERS[name]
            i += 1
            while i < len(seg) and seg[i].startswith('-') and seg[i] != '--':
                opt = seg[i]
                i += 1
                if opt in takes and i < len(seg):
                    i += 1
            if i < len(seg) and seg[i] == '--':
                i += 1
            while i < len(seg) and ASSIGN.match(seg[i]):   # env A=1 cmd
                i += 1
            i += WRAPPER_EXTRA_ARGS.get(name, 0)
            continue
        return name, seg[i + 1:]
    return None, []


# ---------------------------------------------------------------- checkers
PKILL_VALUE_OPTS = {'-F', '-G', '-P', '-U', '-d', '-g', '-t', '-u'}


def check_bsd_pkill_trailing_options(cmd):
    for seg in segments(cmd):
        name, args = real_command(seg)
        if name not in ('pkill', 'pgrep'):
            continue
        i, pattern = 0, None
        while i < len(args):
            a = args[i]
            if pattern is None:
                if a == '--':
                    if i + 1 < len(args):
                        pattern = args[i + 1]
                        i += 2
                        continue
                    break
                if a.startswith('-') and len(a) > 1:
                    i += 2 if a in PKILL_VALUE_OPTS else 1
                    continue
                pattern = a
            elif a.startswith('-') and len(a) > 1:
                return (
                    f'`{name}` 의 패턴({pattern!r}) 뒤에 `{a}` 옵션이 있어요. macOS(BSD) 의 {name} 명령은 첫 패턴에서 옵션 해석을 '
                    f'멈추고, `{a}` 와 그 뒤 인자를 모두 **추가 패턴**으로 읽어요. -f 와 같이 쓰면 명령줄에 그 문자열이 든 '
                    f'무관한 프로세스(터미널 셸, 다른 Claude 세션 등)까지 잡혀요. 옵션을 모두 패턴 앞에 두세요. '
                    f"예: {name} -f -U \"$(id -u)\" -n '<패턴>'"
                )
            i += 1
    return None


CHECKERS = {
    'bsd-pkill-trailing-options': check_bsd_pkill_trailing_options,
}


def evaluate(cmd):
    """(검사기 id, 이유) 또는 None."""
    for cid, fn in CHECKERS.items():
        reason = fn(cmd)
        if reason:
            return cid, reason
    return None


# ---------------------------------------------------------------- self test
BLOCK = [
    'pkill -f "my test server" -U $(id -u) -n',
    "pkill -f 'server.py' -n",
    'pgrep -f zzz -n',
    'sudo pkill -9 -f foo -U 0',
    'cd /tmp && pkill -f foo -n',
    'pkill -U $(id -u) foo -n',
    'pgrep -f foo | xargs pkill -f bar -n',
    'env A=1 pkill -f foo -x',
    'timeout 5 pkill -f foo -n',
    'kill $(pgrep -f foo -n)',
    'pkill -- foo -n',
]
ALLOW = [
    'pkill -f -U "$(id -u)" -n "my test server"',
    'pgrep -f -n zzz',
    'pkill -9 -f foo',
    'pkill -TERM -x node',
    'echo "pkill -f foo -n"',
    'grep -n pkill notes.md',
    'pkill -f foo\necho -n done',
    'pgrep -f foo | head -n 1',
    'pgrep -lf foo; ls -la',
    'pkill -f foo 2>/dev/null || true',
    'pgrep -u "$USER" -f "a b" > /dev/null',
    'npm run build -- --watch',
    'git log -n 3',
]


def self_test():
    bad = 0
    for c in BLOCK:
        r = evaluate(c)
        ok = r is not None
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} block  {c!r}")
    for c in ALLOW:
        r = evaluate(c)
        ok = r is None
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} allow  {c!r}" + ('' if ok else f'  ← {r[0]}'))
    print(f'\n{len(BLOCK) + len(ALLOW) - bad}/{len(BLOCK) + len(ALLOW)} 통과')
    return 1 if bad else 0


# ---------------------------------------------------------------- main
def main(argv):
    if '--list' in argv:
        print('\n'.join(CHECKERS))
        return 0
    if '--self-test' in argv:
        return self_test()
    if '--check' in argv:
        cmd = argv[argv.index('--check') + 1]
        r = evaluate(cmd)
        print(f'deny [{r[0]}] {r[1]}' if r else 'allow')
        return 2 if r else 0
    try:
        data = json.load(sys.stdin)
        if data.get('tool_name') != 'Bash':
            return 0
        cmd = (data.get('tool_input') or {}).get('command') or ''
        r = evaluate(cmd)
    except Exception as e:  # fail-open
        print(f'bash-guard: 검사 실패, 통과시킴: {e}', file=sys.stderr)
        return 0
    if r:
        cid, reason = r
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': f'[ai-mistake-log:{cid}] {reason}',
        }}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
