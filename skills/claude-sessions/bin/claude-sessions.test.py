#!/usr/bin/env python3
"""claude-sessions.py 시험. 가짜 레지스트리(임시 폴더)와 가짜 ps·lsof 출력만 쓴다.

실제 ~/.claude/sessions 는 읽지 않고, ps·lsof 를 부르지 않고, os.kill(pid, 0) 도 보내지 않는다
(subprocess.run·alive 를 바꿔 끼운다).

  python3 -I claude-sessions.test.py        exit 0 전부 기대대로, 1 아니면
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True   # 저장소 안에 __pycache__ 를 만들지 않는다
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'claude-sessions.py')


def load_module():
    spec = importlib.util.spec_from_file_location('claude_sessions', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # 가져오기는 경로만 만든다. 아무것도 실행하지 않는다
    return mod


CS = load_module()

FAKE_PS = """\
    1     0 /sbin/launchd
  100     1 /Users/u/.local/bin/claude --resume
  200     1 /Users/u/.local/bin/claude
  300   200 /bin/zsh -c python3 claude-sessions.py
  400   300 /usr/bin/python3 claude-sessions.py
  500     1 node /opt/lib/claude-helper.js
  600     1 /Applications/Claude.app/Contents/MacOS/Claude
  700   100 /Users/u/.local/bin/claude mcp serve
garbage-line
  800
"""


def fake_run(stdout):
    def run(cmd, **kw):
        assert cmd[0] in ('ps', 'lsof'), f'예상하지 않은 명령: {cmd}'
        return SimpleNamespace(stdout=stdout, returncode=0)
    return run


class ParseTest(unittest.TestCase):
    def test_ps_table_parses_and_skips_short_lines(self):
        with mock.patch.object(CS.subprocess, 'run', fake_run(FAKE_PS)):
            t = CS.ps_table()
        self.assertEqual(t[100], (1, '/Users/u/.local/bin/claude --resume'))
        self.assertEqual(t[300], (200, '/bin/zsh -c python3 claude-sessions.py'))
        self.assertNotIn(800, t)      # 필드가 모자란 줄은 버린다
        self.assertEqual(len(t), 8)

    def test_is_claude(self):
        self.assertTrue(CS.is_claude('/Users/u/.local/bin/claude --resume'))
        self.assertTrue(CS.is_claude('claude'))
        self.assertTrue(CS.is_claude('/Users/u/.local/bin/claude mcp serve'))
        self.assertFalse(CS.is_claude('node /opt/lib/claude-helper.js'))
        self.assertFalse(CS.is_claude('/Applications/Claude.app/Contents/MacOS/Claude'))
        self.assertFalse(CS.is_claude('/usr/bin/claude-code'))

    def test_lsof_cwd(self):
        with mock.patch.object(CS.subprocess, 'run', fake_run('p123\nfcwd\nn/Users/u/proj\n')):
            self.assertEqual(CS.lsof_cwd(123), '/Users/u/proj')
        with mock.patch.object(CS.subprocess, 'run', fake_run('p123\n')):
            self.assertIsNone(CS.lsof_cwd(123))

        def boom(*a, **k):
            raise OSError('no lsof')
        with mock.patch.object(CS.subprocess, 'run', boom):
            self.assertIsNone(CS.lsof_cwd(123))


class FindSelfTest(unittest.TestCase):
    def table(self):
        with mock.patch.object(CS.subprocess, 'run', fake_run(FAKE_PS)):
            return CS.ps_table()

    def test_walks_up_to_nearest_claude(self):
        with mock.patch.object(CS.os, 'getpid', return_value=400):
            self.assertEqual(CS.find_self(self.table()), 200)

    def test_no_claude_ancestor(self):
        t = {10: (1, '/bin/zsh'), 11: (10, 'python3 x')}
        with mock.patch.object(CS.os, 'getpid', return_value=11):
            self.assertIsNone(CS.find_self(t))

    def test_self_not_in_table(self):
        with mock.patch.object(CS.os, 'getpid', return_value=99999):
            self.assertIsNone(CS.find_self({}))

    def test_own_command_named_claude_is_skipped(self):
        # 스크립트 자신이 claude 라는 이름이어도 자기를 고르지 않는다
        t = {50: (40, '/x/claude'), 40: (1, '/x/claude')}
        with mock.patch.object(CS.os, 'getpid', return_value=50):
            self.assertEqual(CS.find_self(t), 40)

    def test_parent_cycle_terminates(self):
        t = {10: (11, 'sh'), 11: (10, 'sh')}
        with mock.patch.object(CS.os, 'getpid', return_value=10):
            self.assertIsNone(CS.find_self(t))


class FormatTest(unittest.TestCase):
    def test_short(self):
        with mock.patch.dict(os.environ, {'HOME': '/Users/u'}):
            self.assertEqual(CS.short('/Users/u'), '~')
            self.assertEqual(CS.short('/Users/u/proj'), '~/proj')
            self.assertEqual(CS.short('/Users/uother/proj'), '/Users/uother/proj')
            self.assertEqual(CS.short('/tmp/x'), '/tmp/x')
            self.assertEqual(CS.short(None), '?')
            self.assertEqual(CS.short(''), '?')

    def test_ago_buckets(self):
        now = 1_800_000_000.0
        with mock.patch.object(CS.time, 'time', return_value=now):
            ms = lambda sec_ago: (now - sec_ago) * 1000
            self.assertEqual(CS.ago(None), '?')
            self.assertEqual(CS.ago(0), '?')
            self.assertEqual(CS.ago(ms(5)), '방금')
            self.assertEqual(CS.ago(ms(-120)), '방금')        # 미래 시각은 0 으로 자른다
            self.assertEqual(CS.ago(ms(125)), '2분 전')
            self.assertEqual(CS.ago(ms(3 * 3600 + 5)), '3시간 전')
            self.assertEqual(CS.ago(ms(2 * 86400 + 5)), '2일 전')

    def test_width_counts_hangul_as_two(self):
        self.assertEqual(CS._w('ab'), 2)
        self.assertEqual(CS._w('작업'), 4)
        self.assertEqual(CS._pad('대기', 6), '대기  ')


class CollectTest(unittest.TestCase):
    """레지스트리 × 프로세스 대조. SKILL.md '어떻게 알아내나' 표의 세 경우."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = Path(self.tmp.name) / 'sessions'
        self.reg.mkdir()
        self.write(100, {'pid': 100, 'name': 'me', 'cwd': '/w/a', 'status': 'busy', 'updatedAt': 3000})
        self.write(200, {'pid': 200, 'name': 'peer', 'cwd': '/w/b', 'status': 'idle', 'updatedAt': 2000})
        self.write(900, {'pid': 900, 'name': 'gone', 'cwd': '/w/c', 'status': 'busy', 'updatedAt': 1000})
        (self.reg / '901.json').write_text('{not json')                        # 깨진 파일
        (self.reg / 'abc.json').write_text(json.dumps({'name': 'no pid'}))      # pid 도 숫자 이름도 없음
        (self.reg / '902.json').write_text(json.dumps({'name': 'stem pid', 'status': 'idle'}))  # 파일명으로 pid
        (self.reg / 'notes.txt').write_text('ignored')
        self.ps = {
            1: (0, '/sbin/launchd'),
            100: (1, '/Users/u/.local/bin/claude'),
            200: (1, '/Users/u/.local/bin/claude'),
            300: (1, '/Users/u/.local/bin/claude'),   # 레지스트리 없음
            400: (100, '/usr/bin/python3 claude-sessions.py'),
        }
        self.alive_calls = []
        patches = [
            mock.patch.object(CS, 'REGISTRY', self.reg),
            mock.patch.object(CS, 'ps_table', lambda: dict(self.ps)),
            mock.patch.object(CS, 'alive', self.fake_alive),
            mock.patch.object(CS, 'lsof_cwd', lambda pid: f'/cwd/of/{pid}'),
            mock.patch.object(CS.os, 'getpid', return_value=400),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def write(self, pid, data):
        (self.reg / f'{pid}.json').write_text(json.dumps(data))

    def fake_alive(self, pid):
        self.alive_calls.append(pid)
        return False

    def by_pid(self, sessions):
        return {s['pid']: s for s in sessions}

    def test_live_sessions_default(self):
        s = self.by_pid(CS.collect(False))
        self.assertEqual(set(s), {100, 200, 300})
        self.assertEqual(s[100]['source'], 'registry')
        self.assertTrue(s[100]['self'])
        self.assertFalse(s[200]['self'])
        self.assertEqual(s[200]['status'], 'idle')
        self.assertEqual(s[300]['source'], 'unregistered')
        self.assertEqual(s[300]['cwd'], '/cwd/of/300')
        self.assertIsNone(s[300]['status'])
        self.assertIn(900, self.alive_calls)   # ps 에 없으면 alive() 로 한 번 더 확인한다

    def test_all_includes_stale_with_status_cleared(self):
        s = self.by_pid(CS.collect(True))
        self.assertEqual(set(s), {100, 200, 300, 900, 902})
        self.assertEqual(s[900]['source'], 'stale')
        self.assertIsNone(s[900]['status'])           # 죽은 세션의 busy 를 믿지 않는다
        self.assertEqual(s[902]['name'], 'stem pid')  # pid 키가 없으면 파일명

    def test_registry_dir_missing(self):
        with mock.patch.object(CS, 'REGISTRY', Path(self.tmp.name) / 'nope'):
            s = self.by_pid(CS.collect(False))
        self.assertEqual({p: v['source'] for p, v in s.items()},
                         {100: 'unregistered', 200: 'unregistered', 300: 'unregistered'})

    def test_render_summary_and_notes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            CS.render(CS.collect(True))
        text = out.getvalue()
        lines = text.splitlines()
        self.assertEqual(lines[0], '이 세션 말고 2개가 돌고 있습니다 (대기 1, 상태 모름 1).')
        self.assertIn('← 지금 이 세션', text)
        self.assertIn('종료됨', text)
        self.assertIn('(레지스트리 없음)', text)
        self.assertIn('~/.claude/sessions 에 파일이 없는 세션입니다', text)
        body = lines[3:]
        # 정렬: 살아 있는 것 먼저(작업 중 → 대기 → 모름), 종료된 것은 맨 뒤
        self.assertTrue(body[0].startswith('작업 중'))
        self.assertTrue(body[1].startswith('대기'))
        self.assertTrue([l for l in body if l.startswith('종료됨')])
        self.assertTrue(all(not l.startswith('종료됨') for l in body[:3]))

    def test_render_alone(self):
        self.ps = {100: (1, '/Users/u/.local/bin/claude'), 400: (100, 'python3')}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            CS.render(CS.collect(False))
        self.assertTrue(out.getvalue().startswith('이 세션 말고 돌고 있는 Claude Code 세션은 없습니다.'))
        self.assertNotIn('(레지스트리 없음) —', out.getvalue())

    def test_main_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            CS.main(['--json'])
        data = json.loads(out.getvalue())
        self.assertEqual(sorted(d['pid'] for d in data), [100, 200, 300])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            CS.main(['--json', '--all'])
        self.assertIn(900, [d['pid'] for d in json.loads(out.getvalue())])

    def test_reused_pid_is_not_a_live_session(self):
        # BUG: collect() 는 pid 가 claude 프로세스가 아니어도 alive(pid) 만 참이면 살아 있다고 본다.
        # 죽은 세션의 레지스트리 파일이 남은 상태에서 그 pid 를 다른 프로그램이 재사용하면,
        # 그 파일의 마지막 status(예: busy)가 '작업 중' 세션으로 표시된다.
        self.ps[900] = (1, '/usr/bin/vim notes.txt')
        with mock.patch.object(CS, 'alive', lambda pid: pid in self.ps):
            s = self.by_pid(CS.collect(False))
        self.assertNotIn(900, s)


if __name__ == '__main__':
    unittest.main()
