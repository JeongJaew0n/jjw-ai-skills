#!/usr/bin/env python3
"""rc-session.py 시험. 서버를 띄우지 않고 프로세스도 죽이지 않는다.

- 모든 파일 작업은 임시 HOME 안의 가짜 ~/.claude.json·~/.claude/sessions 에만 한다.
- 모듈을 직접 부르는 시험은 subprocess.Popen 과 os.kill 을 '불리면 실패' 로 바꿔 끼운 채 돈다.
  start 의 로그 폴링은 가짜 Popen 이 로그에 미리 쓴 내용으로 시험한다.
- 자식 프로세스로 부르는 시험은 audit·trust·list·start --dry-run 과 인자 오류뿐이다.
  가짜 claude 바이너리는 실행 권한이 없는 빈 파일이다.

  python3 -I rc-session.test.py        exit 0 전부 기대대로, 1 아니면
"""
import contextlib
import glob
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True   # 저장소 안에 __pycache__ 를 만들지 않는다
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'rc-session.py')


def load_module():
    spec = importlib.util.spec_from_file_location('rc_session', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RC = load_module()


def slurp(path):
    with open(path, 'rb') as f:
        return f.read()


def forbidden(name):
    def f(*a, **k):
        raise AssertionError(f'시험 중 {name} 가 불렸습니다: {a}')
    return f


class Home:
    """임시 HOME. ~/.claude.json, ~/.claude/sessions, ~/.local/bin/claude(가짜) 를 만든다."""

    def __init__(self, projects=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)
        self.claude_json = os.path.join(self.home, '.claude.json')
        self.sessions = os.path.join(self.home, '.claude', 'sessions')
        self.bin = os.path.join(self.home, '.local', 'bin', 'claude')
        os.makedirs(self.sessions)
        os.makedirs(os.path.dirname(self.bin))
        open(self.bin, 'w').close()            # 실행 권한 없음 — 실수로 실행돼도 아무것도 안 뜬다
        self.write_json({'numStartups': 3, 'userID': '한글값', 'projects': projects or {}})

    def write_json(self, data):
        with open(self.claude_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def read_json(self):
        with open(self.claude_json, encoding='utf-8') as f:
            return json.load(f)

    def dir(self, name, *entries):
        d = os.path.join(self.home, name)
        os.makedirs(d, exist_ok=True)
        for e in entries:
            p = os.path.join(d, e)
            if e.endswith('/'):
                os.makedirs(p, exist_ok=True)
            else:
                open(p, 'w').close()
        return d

    def session(self, pid, **fields):
        with open(os.path.join(self.sessions, f'{pid}.json'), 'w') as f:
            json.dump({'pid': pid, **fields}, f)

    def backups(self):
        return glob.glob(self.claude_json + '.bak-*')

    def cleanup(self):
        self.tmp.cleanup()


class ModuleTest(unittest.TestCase):
    """모듈 상수를 임시 HOME 으로 돌리고, 서버 기동·kill 은 막아 둔다."""

    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.cleanup)
        for name, value in (('CLAUDE_JSON', self.h.claude_json), ('SESSIONS_DIR', self.h.sessions),
                            ('CLAUDE_BIN', self.h.bin)):
            p = mock.patch.object(RC, name, value)
            p.start()
            self.addCleanup(p.stop)
        for target, name in ((RC.subprocess, 'Popen'), (RC.os, 'kill')):
            p = mock.patch.object(target, name, forbidden(name))
            p.start()
            self.addCleanup(p.stop)

    def call(self, func, **args):
        """(종료 코드, stdout, stderr). die 는 SystemExit 이 된다."""
        out, err = io.StringIO(), io.StringIO()
        code = None
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = func(SimpleNamespace(**args))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()


class AuditDirTest(ModuleTest):
    def test_verdicts(self):
        self.assertEqual(RC.audit_dir(os.path.join(self.h.home, 'missing')), ('MISSING', [], []))
        self.assertEqual(RC.audit_dir(self.h.dir('empty')), ('INERT', [], []))
        self.assertEqual(RC.audit_dir(self.h.dir('gitonly', '.git/', '.gitignore', '.DS_Store')), ('INERT', [], []))
        self.assertEqual(RC.audit_dir(self.h.dir('content', '.git/', 'src/', 'README.md')),
                         ('HAS_CONTENT', [], ['README.md', 'src']))
        for cfg in RC.EXECUTABLE_CONFIG:
            d = self.h.dir('cfg-' + cfg.strip('.'), cfg + ('/' if cfg == '.claude' else ''), 'main.py')
            self.assertEqual(RC.audit_dir(d), ('HAS_CONFIG', [cfg], ['main.py']), cfg)

    def test_file_path_is_missing(self):
        f = os.path.join(self.h.dir('x'), 'file')
        open(f, 'w').close()
        self.assertEqual(RC.audit_dir(f)[0], 'MISSING')

    def test_case_variant_config_on_case_insensitive_fs(self):
        # BUG: EXECUTABLE_CONFIG 비교가 대소문자를 가린다. macOS 기본(APFS, 대소문자 무시)에서는
        # `claude.md`·`.Claude/` 도 Claude Code 가 CLAUDE.md·.claude/ 로 열어 읽는데, audit 은
        # 이를 HAS_CONTENT 로 판정해 trust 우회를 허용한다. HAS_CONFIG 여야 한다.
        d = self.h.dir('case', 'claude.md')
        if not os.path.exists(os.path.join(d, 'CLAUDE.md')):
            self.skipTest('대소문자를 가리는 파일 시스템')
        self.assertEqual(RC.audit_dir(d)[0], 'HAS_CONFIG')


class TrustStateTest(ModuleTest):
    def test_states(self):
        self.h.write_json({'projects': {'/a': {}, '/b': {'hasTrustDialogAccepted': True},
                                        '/c': {'hasTrustDialogAccepted': 'true'},
                                        '/d': {'hasTrustDialogAccepted': False}}})
        self.assertEqual(RC.trust_state('/a'), (True, False))
        self.assertEqual(RC.trust_state('/b'), (True, True))
        self.assertEqual(RC.trust_state('/c'), (True, False))   # 문자열 "true" 는 신뢰가 아니다
        self.assertEqual(RC.trust_state('/d'), (True, False))
        self.assertEqual(RC.trust_state('/zzz'), (False, False))
        self.h.write_json({})
        self.assertEqual(RC.trust_state('/a'), (False, False))

    def test_missing_or_broken_claude_json_stops(self):
        os.remove(self.h.claude_json)
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            RC.load_claude_json()
        self.assertEqual(cm.exception.code, 1)
        with open(self.h.claude_json, 'w') as f:
            f.write('{"projects": ')
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            RC.load_claude_json()
        self.assertEqual(cm.exception.code, 1)


class TrustTest(ModuleTest):
    def trust(self, d, flag=True):
        return self.call(RC.cmd_trust, dir=d, i_understand_trust_bypass=flag)

    def test_requires_confirmation_flag(self):
        d = self.h.dir('empty')
        before = slurp(self.h.claude_json)
        code, _, err = self.trust(d, flag=False)
        self.assertEqual(code, 1)
        self.assertIn('--i-understand-trust-bypass', err)
        self.assertEqual(slurp(self.h.claude_json), before)
        self.assertEqual(self.h.backups(), [])

    def test_missing_dir(self):
        code, _, err = self.trust(os.path.join(self.h.home, 'nope'))
        self.assertEqual(code, 1)
        self.assertIn('디렉터리가 없습니다', err)

    def test_has_config_is_refused_even_with_flag(self):
        for cfg in RC.EXECUTABLE_CONFIG:
            d = self.h.dir('cfg-' + cfg.strip('.'), cfg)
            before = slurp(self.h.claude_json)
            code, _, err = self.trust(d)
            self.assertEqual(code, 1, cfg)
            self.assertIn('거부', err)
            self.assertEqual(slurp(self.h.claude_json), before)
        self.assertEqual(self.h.backups(), [])

    def test_writes_flag_with_backup_and_preserves_other_keys(self):
        d = self.h.dir('proj', 'src/')
        self.h.write_json({'numStartups': 3, 'userID': '한글값', 'projects': {
            d: {'allowedTools': ['Bash'], 'custom': 1},
            '/other': {'hasTrustDialogAccepted': True}}})
        original = slurp(self.h.claude_json)
        code, out, _ = self.trust(d)
        self.assertEqual(code, 0)
        data = self.h.read_json()
        entry = data['projects'][d]
        self.assertIs(entry['hasTrustDialogAccepted'], True)
        self.assertEqual(entry['allowedTools'], ['Bash'])        # 기존 값은 그대로
        self.assertEqual(entry['custom'], 1)
        self.assertEqual(entry['mcpServers'], {})                # 빠진 기본 키만 채운다
        self.assertEqual(data['projects']['/other'], {'hasTrustDialogAccepted': True})
        self.assertEqual(data['userID'], '한글값')
        self.assertIn('한글값', slurp(self.h.claude_json).decode())   # ensure_ascii=False
        [backup] = self.h.backups()
        self.assertEqual(slurp(backup), original)
        self.assertIn(f'백업       : {backup}', out)
        self.assertIn('HAS_CONTENT (내용 1개)', out)
        self.assertEqual(glob.glob(self.h.claude_json + '.tmp-*'), [])   # 임시 파일이 남지 않는다

    def test_already_trusted_is_noop(self):
        d = self.h.dir('proj', 'CLAUDE.md')    # 설정이 있어도 이미 신뢰됐으면 건드리지 않는다
        self.h.write_json({'projects': {d: {'hasTrustDialogAccepted': True}}})
        before = slurp(self.h.claude_json)
        code, out, _ = self.trust(d)
        self.assertEqual(code, 0)
        self.assertIn('이미 신뢰됨', out)
        self.assertEqual(slurp(self.h.claude_json), before)
        self.assertEqual(self.h.backups(), [])


class FakeProc:
    def __init__(self, pid=4242, code=None):
        self.pid, self.returncode, self._code = pid, None, code

    def poll(self):
        self.returncode = self._code
        return self._code


class StartTest(ModuleTest):
    def setUp(self):
        super().setUp()
        self.target = self.h.dir('proj', 'src/')
        self.h.write_json({'projects': {self.target: {'hasTrustDialogAccepted': True}}})
        p = mock.patch.object(RC.time, 'sleep', lambda s: None)
        p.start()
        self.addCleanup(p.stop)
        self.launched = []

    def args(self, **kw):
        base = dict(dir=self.target, name=None, create=False, log=None, wait=25, dry_run=False, extra=None)
        base.update(kw)
        return base

    def fake_popen(self, log_text, code=None):
        def popen(cmd, **kw):
            self.launched.append((cmd, kw))
            kw['stdout'].write(log_text.encode())
            return FakeProc(code=code)
        return popen

    def test_build_start_cmd(self):
        self.assertEqual(RC.build_start_cmd(None, []),
                         [self.h.bin, 'remote-control', '--create-session-in-dir', '--spawn', 'same-dir'])
        self.assertEqual(RC.build_start_cmd('m3·이름', ['--capacity', '4'])[-4:],
                         ['--name', 'm3·이름', '--capacity', '4'])

    def test_refuses_untrusted_dir(self):
        d = self.h.dir('untrusted')
        code, _, err = self.call(RC.cmd_start, **self.args(dir=d))
        self.assertEqual(code, 1)
        self.assertIn('신뢰되지 않은 디렉터리', err)

    def test_refuses_missing_dir_and_binary(self):
        code, _, err = self.call(RC.cmd_start, **self.args(dir=os.path.join(self.h.home, 'nope')))
        self.assertEqual(code, 1)
        self.assertIn('--create', err)
        os.remove(self.h.bin)
        code, _, err = self.call(RC.cmd_start, **self.args())
        self.assertEqual(code, 1)
        self.assertIn('바이너리를 찾지 못했습니다', err)

    def test_dry_run_launches_nothing(self):
        code, out, _ = self.call(RC.cmd_start, **self.args(dry_run=True, name='n'))
        self.assertEqual(code, 0)
        self.assertIn('--dry-run: 서버를 띄우지 않았습니다.', out)
        self.assertIn(f'로그       : {self.target}/.rc-session.log', out)
        self.assertFalse(os.path.exists(os.path.join(self.target, '.rc-session.log')))

    def test_extracts_both_links_from_log(self):
        log = ('·✔︎· Connected · n · main\n'
               '\x1b]8;;https://claude.ai/code/session_01AbC9\x07n\x1b]8;;\x07\n'
               'Continue coding in the Claude mobile app or https://claude.ai/code?environment=env_Xy12\n')
        custom_log = os.path.join(self.h.home, 'logs', 'rc.log')
        os.makedirs(os.path.dirname(custom_log))
        with mock.patch.object(RC.subprocess, 'Popen', self.fake_popen(log)):
            code, out, _ = self.call(RC.cmd_start, **self.args(name='n', log=custom_log, extra=['--capacity', '2']))
        self.assertEqual(code, 0)
        [(cmd, kw)] = self.launched
        self.assertEqual(cmd, [self.h.bin, 'remote-control', '--create-session-in-dir', '--spawn', 'same-dir',
                               '--name', 'n', '--capacity', '2'])
        self.assertEqual(kw['cwd'], self.target)
        self.assertTrue(kw['start_new_session'])
        self.assertIs(kw['stdin'], subprocess.DEVNULL)
        self.assertIn('환경 링크  : https://claude.ai/code?environment=env_Xy12', out)
        self.assertIn('세션 직링크: https://claude.ai/code/session_01AbC9', out)
        self.assertIn('PID        : 4242', out)
        self.assertIn('stop --pid 4242', out)

    def test_untrusted_error_in_log(self):
        log = 'Error: Workspace not trusted. Please run `claude` in x first\n'
        with mock.patch.object(RC.subprocess, 'Popen', self.fake_popen(log)):
            code, _, err = self.call(RC.cmd_start, **self.args())
        self.assertEqual(code, 1)
        self.assertIn('신뢰 오류', err)

    def test_early_exit(self):
        with mock.patch.object(RC.subprocess, 'Popen', self.fake_popen('boom\n', code=2)):
            code, _, err = self.call(RC.cmd_start, **self.args())
        self.assertEqual(code, 1)
        self.assertIn('조기 종료', err)
        self.assertIn('exit=2', err)

    def test_no_url_within_wait(self):
        with mock.patch.object(RC.subprocess, 'Popen', self.fake_popen('connecting…\n')):
            code, out, _ = self.call(RC.cmd_start, **self.args(wait=0))
        self.assertEqual(code, 0)
        self.assertIn('URL 을 아직 못 뽑았습니다', out)

    def test_create_makes_dir(self):
        d = os.path.join(self.h.home, 'new', 'deep')
        self.h.write_json({'projects': {d: {'hasTrustDialogAccepted': True}}})
        with mock.patch.object(RC.subprocess, 'Popen', self.fake_popen('')):
            code, out, _ = self.call(RC.cmd_start, **self.args(dir=d, create=True, wait=0))
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isdir(d))
        self.assertIn(f'생성       : {d}', out)

    def test_dry_run_with_create_does_not_create(self):
        # BUG: cmd_start 는 --create 를 다른 검사와 --dry-run 보다 먼저 처리한다. 그래서
        # `start --create --dry-run` 이 디렉터리를 실제로 만든다. 신뢰되지 않은 새 경로면
        # 만든 직후 신뢰 검사에서 거부되어, 실패한 명령이 빈 디렉터리를 남긴다.
        d = os.path.join(self.h.home, 'should-not-exist')
        self.h.write_json({'projects': {d: {'hasTrustDialogAccepted': True}}})
        code, _, _ = self.call(RC.cmd_start, **self.args(dir=d, create=True, dry_run=True))
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(d))


class ListStopTest(ModuleTest):
    def setUp(self):
        super().setUp()
        self.h.session(300, kind='interactive', name='b-proj', cwd='/w/b', bridgeSessionId='session_x')
        self.h.session(200, kind='interactive', name='a-proj', cwd='/w/a')
        with open(os.path.join(self.h.sessions, 'broken.json'), 'w') as f:
            f.write('{')

    def test_list(self):
        code, out, _ = self.call(RC.cmd_list, rc_only=False)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertTrue(lines[0].strip().startswith('PID'))
        self.assertEqual([l.split()[0] for l in lines[1:]], ['200', '300'])   # cwd 순
        self.assertIn('예', lines[2])
        code, out, _ = self.call(RC.cmd_list, rc_only=True)
        self.assertEqual([l.split()[0] for l in out.splitlines()[1:]], ['300'])

    def test_list_empty(self):
        for f in glob.glob(os.path.join(self.h.sessions, '*')):
            os.remove(f)
        self.assertEqual(self.call(RC.cmd_list, rc_only=False)[1], '세션 기록이 없습니다.\n')

    def test_stop_refuses_unknown_pid(self):
        code, _, err = self.call(RC.cmd_stop, pid=999999, force=False)   # os.kill 은 forbidden 이다
        self.assertEqual(code, 1)
        self.assertIn('기록에 없습니다', err)

    def test_stop_known_pid_sends_sigterm(self):
        sent = []
        with mock.patch.object(RC.os, 'kill', lambda pid, sig: sent.append((pid, sig))):
            code, out, _ = self.call(RC.cmd_stop, pid=300, force=False)
            self.assertEqual(code, 0)
            code, _, _ = self.call(RC.cmd_stop, pid=999999, force=True)
            self.assertEqual(code, 0)
        self.assertEqual(sent, [(300, signal.SIGTERM), (999999, signal.SIGTERM)])

    def test_stop_errors(self):
        for exc, msg in ((ProcessLookupError, '이미 없습니다'), (PermissionError, '권한이 없습니다')):
            def kill(pid, sig, exc=exc):
                raise exc()
            with mock.patch.object(RC.os, 'kill', kill):
                code, _, err = self.call(RC.cmd_stop, pid=300, force=False)
            self.assertEqual(code, 1)
            self.assertIn(msg, err)


class CliTest(unittest.TestCase):
    """자식 프로세스. HOME 을 임시 폴더로 바꾼다. 서버를 띄우거나 kill 하는 경로는 부르지 않는다."""

    def setUp(self):
        self.h = Home()
        self.addCleanup(self.h.cleanup)

    def run_tool(self, *args):
        env = {'HOME': self.h.home, 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
        return subprocess.run([sys.executable, '-I', TOOL, *args], capture_output=True, text=True,
                              env=env, timeout=30)

    def test_argument_errors_exit_2(self):
        for args in ([], ['bogus'], ['audit'], ['trust'], ['start'], ['stop'], ['stop', '--pid', 'abc'],
                     ['start', '--dir', '.', '--wait', 'x']):
            self.assertEqual(self.run_tool(*args).returncode, 2, args)

    def test_audit_verdicts(self):
        cases = {
            self.h.dir('empty'): ('INERT', '비어 있습니다'),
            self.h.dir('content', 'a.txt'): ('HAS_CONTENT', '내용물이 있는 디렉터리'),
            self.h.dir('config', '.mcp.json'): ('HAS_CONFIG', '신뢰 우회 불가'),
            os.path.join(self.h.home, 'missing'): ('MISSING', '디렉터리가 없습니다'),
        }
        for d, (verdict, advice) in cases.items():
            r = self.run_tool('audit', '--dir', d)
            self.assertEqual(r.returncode, 0, d)
            self.assertIn(f'내용 판정  : {verdict}', r.stdout)
            self.assertIn(advice, r.stdout)
        self.assertEqual(self.h.backups(), [])   # audit 은 아무것도 쓰지 않는다

    def test_audit_lists_at_most_12_entries(self):
        d = self.h.dir('many', *[f'f{i:02}' for i in range(15)])
        r = self.run_tool('audit', '--dir', d)
        self.assertIn('기타 항목(15): f00, f01', r.stdout)
        self.assertIn('f11 …', r.stdout)
        self.assertNotIn('f12', r.stdout)

    def test_audit_then_trust_then_audit(self):
        d = self.h.dir('proj', '.gitignore')
        self.assertEqual(self.run_tool('trust', '--dir', d).returncode, 1)
        r = self.run_tool('trust', '--dir', d, '--i-understand-trust-bypass')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('보안 다이얼로그 우회', r.stdout)
        r = self.run_tool('audit', '--dir', d)
        self.assertIn('신뢰됨     : 예', r.stdout)
        self.assertIn('이미 신뢰된 디렉터리', r.stdout)

    def test_tilde_path_is_expanded(self):
        self.h.dir('proj')
        self.run_tool('trust', '--dir', '~/proj', '--i-understand-trust-bypass')
        self.assertIn(os.path.join(self.h.home, 'proj'), self.h.read_json()['projects'])

    def test_start_dry_run(self):
        d = self.h.dir('proj')
        self.h.write_json({'projects': {d: {'hasTrustDialogAccepted': True}}})
        r = self.run_tool('start', '--dir', d, '--name', 'm3·x', '--dry-run', '--extra', '--capacity', '2')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'명령       : {self.h.bin} remote-control --create-session-in-dir --spawn same-dir '
                      '--name m3·x --capacity 2', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(d, '.rc-session.log')))

    def test_list(self):
        self.h.session(11, kind='interactive', name='x', cwd='/w', bridgeSessionId='session_1')
        r = self.run_tool('list', '--rc-only')
        self.assertEqual(r.returncode, 0)
        self.assertIn('x', r.stdout)


if __name__ == '__main__':
    unittest.main()
