#!/usr/bin/env python3
"""cmux-where.py 시험. 진짜 cmux 는 부르지 않는다.

- 모듈을 직접 부르는 시험은 subprocess.run 을 가짜로 바꿔 identify·rpc *.list 에 미리 만든 답을 준다.
  그 밖의 cmux 명령(send 등)이 불리면 시험이 실패한다.
- 자식 프로세스 시험은 PATH 를 임시 폴더 하나로 좁히고 거기에 가짜 `cmux` 를 둔다. 가짜는
  받은 인자를 기록하고, 읽기 명령이 아니면 99 로 끝난다.

  python3 -I cmux-where.test.py        exit 0 전부 기대대로, 1 아니면
"""
import contextlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True   # 저장소 안에 __pycache__ 를 만들지 않는다
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'cmux-where.py')
READ_ONLY_RPC = {'pane.list', 'surface.list', 'workspace.list'}


def load_module():
    spec = importlib.util.spec_from_file_location('cmux_where', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CW = load_module()


def frame(x, y, w=480.0, h=460.0):
    return {'x': x, 'y': y, 'width': w, 'height': h}


# 2x2 격자. pane.list 는 index(열 우선) 순으로 준다: 좌상 → 좌하 → 우상 → 우하.
# 두 번째 항목(pane:9)이 화면에서는 좌하단이라는 것이 SKILL.md 함정 1 이다.
WS3 = {
    'panes': [
        {'ref': 'pane:8', 'index': 0, 'pixel_frame': frame(216, 0)},
        {'ref': 'pane:9', 'index': 1, 'pixel_frame': frame(216.0, 460.5)},
        {'ref': 'pane:10', 'index': 2, 'pixel_frame': frame(698.5, 1.5)},   # 허용 오차 안의 어긋남
        {'ref': 'pane:11', 'index': 3, 'pixel_frame': frame(700.0, 462.0)},
    ],
    'surfaces': [
        {'ref': 'surface:8', 'id': 'S8', 'pane_ref': 'pane:8', 'title': '나', 'type': 'terminal',
         'selected_in_pane': True, 'resume_binding': {'checkpoint_id': 'me-session-uuid'}},
        {'ref': 'surface:9', 'id': 'S9', 'pane_ref': 'pane:9', 'title': '✳ claude', 'type': 'terminal',
         'selected_in_pane': True, 'resume_binding': {'checkpoint_id': 'abcdef0123456789'}},
        {'ref': 'surface:12', 'id': 'S12', 'pane_ref': 'pane:10', 'title': 'bg', 'type': 'terminal',
         'selected_in_pane': False},
        {'ref': 'surface:10', 'id': 'S10', 'pane_ref': 'pane:10', 'title': 'zsh', 'type': 'terminal',
         'selected_in_pane': True, 'resume_binding': None},
        {'ref': 'surface:11', 'id': 'S11', 'pane_ref': 'pane:11', 'title': 'x' * 60, 'type': 'terminal',
         'selected_in_pane': True},
    ],
}
WS2 = {
    'panes': [
        {'ref': 'pane:3', 'pixel_frame': frame(700, 0)},
        {'ref': 'pane:2', 'pixel_frame': frame(216, 0)},
    ],
    'surfaces': [
        {'ref': 'surface:2', 'pane_ref': 'pane:2', 'title': 'left', 'selected_in_pane': True},
        {'ref': 'surface:3', 'pane_ref': 'pane:3', 'title': 'right', 'selected_in_pane': True,
         'resume_binding': {'checkpoint_id': 'feedbeef00'}},
    ],
}
FIXTURE = {
    'identify': {
        'caller': {'window_ref': 'window:1', 'workspace_ref': 'workspace:3', 'pane_ref': 'pane:8',
                   'surface_ref': 'surface:8'},
        'focused': {'window_ref': 'window:1', 'workspace_ref': 'workspace:3', 'pane_ref': 'pane:8',
                    'surface_ref': 'surface:8'},
    },
    'workspace.list': {'workspaces': [
        {'ref': 'workspace:2', 'id': 'UUID-2', 'title': 'other', 'selected': False},
        {'ref': 'workspace:3', 'id': 'UUID-3', 'title': 'ai skills', 'selected': True},
        {'ref': 'workspace:5', 'id': 'UUID-5', 'title': 'empty', 'selected': False},
    ]},
    'by_workspace': {'UUID-3': WS3, 'UUID-2': WS2},
}


class FakeCmux:
    """subprocess.run 대역. 읽기 명령에만 답하고 나머지는 시험 실패로 만든다."""

    def __init__(self, fixture):
        self.fx = json.loads(json.dumps(fixture))
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] != 'cmux':
            raise AssertionError(f'cmux 가 아닌 명령: {cmd}')
        if cmd[1:] == ['identify']:
            return self.ok(self.fx['identify'])
        if cmd[1] == 'rpc' and cmd[2] in READ_ONLY_RPC:
            method = cmd[2]
            if method == 'workspace.list':
                return self.ok(self.fx['workspace.list'])
            params = json.loads(cmd[3]) if len(cmd) > 3 else {}
            ws = self.fx['by_workspace'].get(params.get('workspace_id'))
            key = 'panes' if method == 'pane.list' else 'surfaces'
            return self.ok({key: ws[key]} if ws else {key: []})
        raise AssertionError(f'읽기 전용이 아닌 cmux 호출: {cmd}')

    @staticmethod
    def ok(obj):
        return SimpleNamespace(returncode=0, stdout=json.dumps(obj), stderr='')


class Base(unittest.TestCase):
    def use(self, fixture=FIXTURE):
        self.cmux = FakeCmux(fixture)
        p = mock.patch.object(CW.subprocess, 'run', self.cmux)
        p.start()
        self.addCleanup(p.stop)
        return self.cmux

    def exits(self, func, *a):
        err = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(err):
            func(*a)
        return cm.exception.code, err.getvalue()


class GeometryTest(unittest.TestCase):
    def test_group_axis_tolerance(self):
        self.assertEqual(CW.group_axis([700.0, 216, 698.5, 216.0]), [216, 698.5])
        self.assertEqual(CW.group_axis([0, 3.9, 8.0]), [0, 8.0])      # 오차는 첫 대표값 기준
        self.assertEqual(CW.group_axis([0, 4.0]), [0])                 # 경계 포함
        self.assertEqual(CW.group_axis([0, 4.01]), [0, 4.01])
        self.assertEqual(CW.group_axis([]), [])

    def test_axis_index(self):
        b = [216, 698.5]
        self.assertEqual(CW.axis_index(219.9, b), 0)
        self.assertEqual(CW.axis_index(702, b), 1)
        self.assertEqual(CW.axis_index(5000, b), 2)    # 어디에도 안 맞으면 끝 다음

    def test_ordinal(self):
        self.assertEqual(CW.ordinal(0), '첫번째')
        self.assertEqual(CW.ordinal(7), '여덟번째')
        self.assertEqual(CW.ordinal(8), '9번째')

    def test_describe_position(self):
        d = CW.describe_position
        self.assertEqual(d(0, 0, 1, 1)[0], '단독')
        self.assertEqual([d(0, c, 1, 2)[0] for c in range(2)], ['좌측', '우측'])
        self.assertEqual(d(0, 1, 1, 2)[1], '좌우 2분할 중 두번째 (왼쪽부터)')
        self.assertEqual([d(0, c, 1, 3)[0] for c in range(3)], ['좌→우 첫번째', '좌→우 두번째', '좌→우 세번째'])
        self.assertEqual([d(r, 0, 2, 1)[0] for r in range(2)], ['상단', '하단'])
        self.assertEqual(d(2, 0, 3, 1), ('위→아래 세번째', '상하 3분할 중 세번째 (위부터)'))
        self.assertEqual([d(r, c, 2, 2)[0] for r in range(2) for c in range(2)], ['좌상', '우상', '좌하', '우하'])
        self.assertEqual(d(1, 1, 3, 3), ('중중', '3행 x 3열 격자의 2행 2열'))
        self.assertEqual(d(0, 1, 2, 3)[0], '중상')


class CollectTest(Base):
    def test_grid_positions_from_pixels_not_index(self):
        self.use()
        rows, grid = CW.collect('UUID-3')
        self.assertEqual(grid, (2, 2))
        pos = {r['surface_ref']: r['position'] for r in rows}
        self.assertEqual(pos, {'surface:8': '좌상', 'surface:9': '좌하', 'surface:10': '우상',
                               'surface:12': '우상', 'surface:11': '우하'})
        # 화면 읽기 순서: 위 행 왼→오, 같은 pane 은 보이는 탭 먼저
        self.assertEqual([r['surface_ref'] for r in rows],
                         ['surface:8', 'surface:10', 'surface:12', 'surface:9', 'surface:11'])
        by = {r['surface_ref']: r for r in rows}
        self.assertFalse(by['surface:12']['selected_in_pane'])
        self.assertEqual(by['surface:9']['claude_session_id'], 'abcdef0123456789')
        self.assertIsNone(by['surface:10']['claude_session_id'])   # resume_binding: null 도 견딘다
        self.assertEqual(by['surface:9']['position_detail'], '2행 x 2열 격자의 2행 1열')

    def test_rpc_uses_workspace_id_uuid(self):
        cmux = self.use()
        CW.collect('UUID-3')
        rpc_calls = [c for c in cmux.calls if c[1] == 'rpc']
        self.assertEqual([c[2] for c in rpc_calls], ['pane.list', 'surface.list'])
        for c in rpc_calls:
            self.assertEqual(json.loads(c[3]), {'workspace_id': 'UUID-3'})   # 함정 3: 키 이름·UUID

    def test_no_panes(self):
        self.use()
        self.assertEqual(CW.collect('UUID-404'), ([], (0, 0)))

    def test_missing_frame_and_unknown_pane(self):
        fx = json.loads(json.dumps(FIXTURE))
        fx['by_workspace']['UUID-3'] = {
            'panes': [{'ref': 'pane:1'}, {'ref': 'pane:2', 'pixel_frame': frame(500, 0)}],
            'surfaces': [{'ref': 'surface:1', 'pane_ref': 'pane:1'},
                         {'ref': 'surface:2', 'pane_ref': 'pane:2', 'selected_in_pane': True},
                         {'ref': 'surface:3', 'pane_ref': 'pane:gone'}]}
        self.use(fx)
        rows, grid = CW.collect('UUID-3')
        self.assertEqual(grid, (1, 2))
        pos = {r['surface_ref']: (r['position'], r['title'], r['selected_in_pane']) for r in rows}
        self.assertEqual(pos['surface:1'], ('좌측', '', False))
        self.assertEqual(pos['surface:2'][0], '우측')
        self.assertEqual(pos['surface:3'][0], '좌측')   # 기하가 없으면 (0,0) 으로 본다

    def test_full_height_pane_in_l_layout(self):
        # BUG: 행·열을 x·y 시작점만으로 매기고 pane 의 높이·너비는 보지 않는다. 왼쪽 전체 높이
        # pane + 오른쪽 상하 2분할(L 자) 배치에서 왼쪽 pane 이 '좌상'(2행 x 2열 격자의 1행 1열)으로
        # 나온다. 실제로는 왼쪽 열 전체라 '좌측' 이어야 사용자의 "좌측 세션" 과 맞는다.
        fx = json.loads(json.dumps(FIXTURE))
        fx['by_workspace']['UUID-3'] = {
            'panes': [{'ref': 'pane:1', 'pixel_frame': frame(216, 0, h=920)},
                      {'ref': 'pane:2', 'pixel_frame': frame(700, 0)},
                      {'ref': 'pane:3', 'pixel_frame': frame(700, 460)}],
            'surfaces': [{'ref': f'surface:{i}', 'pane_ref': f'pane:{i}', 'selected_in_pane': True}
                         for i in (1, 2, 3)]}
        self.use(fx)
        rows, _ = CW.collect('UUID-3')
        self.assertEqual({r['surface_ref']: r['position'] for r in rows}['surface:1'], '좌측')


class RpcTest(Base):
    def run_with(self, result):
        def run(cmd, **kw):
            if isinstance(result, BaseException):
                raise result
            return result
        return mock.patch.object(CW.subprocess, 'run', run)

    def test_rpc_failures_return_none(self):
        for res in (SimpleNamespace(returncode=1, stdout='{}', stderr='x'),
                    SimpleNamespace(returncode=0, stdout='  \n', stderr=''),
                    SimpleNamespace(returncode=0, stdout='not json', stderr='')):
            with self.run_with(res):
                self.assertIsNone(CW.rpc('pane.list', {'workspace_id': 'U'}))

    def test_rpc_cannot_run_cmux_exits_1(self):
        for exc in (OSError('no cmux'), subprocess.TimeoutExpired('cmux', 15)):
            with self.run_with(exc):
                self.assertEqual(self.exits(CW.rpc, 'workspace.list')[0], 1)

    def test_rpc_without_params(self):
        cmux = self.use()
        CW.rpc('workspace.list')
        self.assertEqual(cmux.calls, [['cmux', 'rpc', 'workspace.list']])

    def test_identify_failures_exit_1(self):
        for res in (OSError('x'), SimpleNamespace(returncode=2, stdout='', stderr='not in cmux'),
                    SimpleNamespace(returncode=0, stdout='<html>', stderr='')):
            with self.run_with(res):
                code, err = self.exits(CW.identify)
                self.assertEqual(code, 1, res)
                self.assertTrue(err)

    def test_workspaces_shapes(self):
        fx = json.loads(json.dumps(FIXTURE))
        fx['workspace.list'] = [{'ref': 'workspace:1', 'id': 'U1'}]   # 배열로 와도 받는다
        self.use(fx)
        self.assertEqual(CW.workspaces(), [{'ref': 'workspace:1', 'id': 'U1'}])
        with self.run_with(SimpleNamespace(returncode=1, stdout='', stderr='')):
            self.assertEqual(self.exits(CW.workspaces)[0], 1)


class BuildRenderTest(Base):
    def test_build_mine_only(self):
        self.use()
        data = CW.build(False)
        self.assertTrue(data['caller_is_focused'])
        self.assertEqual(data['my_workspace_ref'], 'workspace:3')
        [ws] = data['workspaces']
        self.assertTrue(ws['is_mine'])
        self.assertEqual(ws['grid'], {'rows': 2, 'cols': 2})
        self.assertEqual([t['surface_ref'] for t in ws['terminals'] if t['is_me']], ['surface:8'])

    def test_build_all(self):
        self.use()
        data = CW.build(True)
        self.assertEqual([w['ref'] for w in data['workspaces']], ['workspace:2', 'workspace:3', 'workspace:5'])
        ws2 = data['workspaces'][0]
        self.assertFalse(ws2['is_mine'])
        self.assertEqual([(t['surface_ref'], t['position']) for t in ws2['terminals']],
                         [('surface:2', '좌측'), ('surface:3', '우측')])
        self.assertEqual(data['workspaces'][2]['terminals'], [])

    def test_my_workspace_missing_exits_1(self):
        fx = json.loads(json.dumps(FIXTURE))
        fx['identify']['caller']['workspace_ref'] = 'workspace:99'
        self.use(fx)
        code, err = self.exits(CW.build, False)
        self.assertEqual(code, 1)
        self.assertIn('workspace:99', err)

    def test_render_focused(self):
        self.use()
        text = CW.render(CW.build(False))
        self.assertIn('경로   : window:1 > workspace:3 "ai skills" > pane:8 > surface:8', text)
        self.assertIn('위치   : 좌상 — 2행 x 2열 격자의 1행 1열', text)
        self.assertNotIn('주의', text)
        self.assertIn('[내 workspace]  [화면에 보이는 중]  (2행 x 2열)', text)
        self.assertIn('claude=abcdef01', text)
        self.assertIn('[배경 탭]', text)
        self.assertIn('x' * 38, text)
        self.assertNotIn('x' * 39, text)
        sends = [l for l in text.splitlines() if 'cmux send' in l]
        self.assertEqual(len(sends), 4)                        # 형제 4개 각각 한 줄
        self.assertTrue(all('--workspace' not in l for l in sends))   # 내 workspace 는 생략
        self.assertIn('    우상 → cmux send --surface surface:10 "<text>" && cmux send-key --surface surface:10 enter',
                      sends)

    def test_render_other_workspace_adds_workspace_flag(self):
        self.use()
        text = CW.render(CW.build(True))
        self.assertIn('cmux send --workspace workspace:2 --surface surface:3 "<text>" '
                      '&& cmux send-key --workspace workspace:2 --surface surface:3 enter', text)
        self.assertIn('== workspace:5 "empty"  (0행 x 0열) ==\n  (터미널 없음)', text)

    def test_render_warns_when_not_focused(self):
        fx = json.loads(json.dumps(FIXTURE))
        fx['identify']['focused'] = {'workspace_ref': 'workspace:2', 'pane_ref': 'pane:2', 'surface_ref': 'surface:2'}
        self.use(fx)
        data = CW.build(False)
        self.assertFalse(data['caller_is_focused'])
        text = CW.render(data)
        self.assertIn('== 주의: 내가 보이는 화면이 아니다 ==', text)
        self.assertIn('지금 화면에 보이는 곳 : workspace:2 > pane:2 > surface:2', text)

    def test_render_when_me_not_found(self):
        fx = json.loads(json.dumps(FIXTURE))
        fx['identify']['caller']['surface_ref'] = 'surface:404'
        self.use(fx)
        text = CW.render(CW.build(False))
        self.assertIn('위치   : 판정 실패', text)
        self.assertIn('workspace:3 > pane:8 > surface:404', text)

    def test_session_env_shown(self):
        self.use()
        with mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'sid-123'}):
            data = CW.build(False)
        self.assertEqual(data['my_claude_session_id'], 'sid-123')
        self.assertIn('세션   : sid-123', CW.render(data))


FAKE_CMUX = r'''#!{python}
import json, os, sys
with open(os.environ['FAKE_CMUX_LOG'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\n')
fx = json.load(open(os.environ['FAKE_CMUX_FIXTURE']))
a = sys.argv[1:]
if a == ['identify']:
    print(json.dumps(fx['identify'])); sys.exit(0)
if len(a) >= 2 and a[0] == 'rpc' and a[1] in ('pane.list', 'surface.list', 'workspace.list'):
    if a[1] == 'workspace.list':
        print(json.dumps(fx['workspace.list'])); sys.exit(0)
    ws = fx['by_workspace'].get(json.loads(a[2]).get('workspace_id')) or {{}}
    key = 'panes' if a[1] == 'pane.list' else 'surfaces'
    print(json.dumps({{key: ws.get(key, [])}})); sys.exit(0)
sys.exit(99)
'''


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.tmp.name
        self.bin = os.path.join(d, 'bin')
        os.mkdir(self.bin)
        cmux = os.path.join(self.bin, 'cmux')
        with open(cmux, 'w') as f:
            f.write(FAKE_CMUX.format(python=sys.executable))
        os.chmod(cmux, os.stat(cmux).st_mode | stat.S_IXUSR)
        self.log = os.path.join(d, 'calls.log')
        open(self.log, 'w').close()
        self.fixture = os.path.join(d, 'fixture.json')
        with open(self.fixture, 'w') as f:
            json.dump(FIXTURE, f)

    def run_tool(self, *args, in_cmux=True):
        env = {'PATH': self.bin, 'HOME': self.tmp.name, 'LANG': 'C.UTF-8',
               'FAKE_CMUX_LOG': self.log, 'FAKE_CMUX_FIXTURE': self.fixture}
        if in_cmux:
            env.update(CMUX_SURFACE_ID='S8', CMUX_WORKSPACE_ID='UUID-3', CLAUDE_CODE_SESSION_ID='me-session-uuid')
        return subprocess.run([sys.executable, '-I', TOOL, *args], capture_output=True, text=True,
                              env=env, timeout=30)

    def calls(self):
        with open(self.log) as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_outside_cmux_exits_3_without_calling_cmux(self):
        for args in ([], ['--all'], ['--json']):
            r = self.run_tool(*args, in_cmux=False)
            self.assertEqual(r.returncode, 3, args)
            self.assertIn('CMUX_SURFACE_ID 없음', r.stderr)
            self.assertEqual(r.stdout, '')
        self.assertEqual(self.calls(), [])

    def test_unknown_argument_exits_1(self):
        for args in (['--bogus'], ['--all', 'x'], ['-a']):
            r = self.run_tool(*args)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn('알 수 없는 인자', r.stderr)
        self.assertEqual(self.calls(), [])

    def test_json_end_to_end_reads_only(self):
        r = self.run_tool('--json', '--all')
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data['my_claude_session_id'], 'me-session-uuid')
        self.assertEqual(len(data['workspaces']), 3)
        for c in self.calls():
            self.assertTrue(c == ['identify'] or (c[0] == 'rpc' and c[1] in READ_ONLY_RPC), c)

    def test_text_end_to_end(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith('== 나 ==\n'))
        self.assertIn('위치   : 좌상', r.stdout)


if __name__ == '__main__':
    unittest.main()
