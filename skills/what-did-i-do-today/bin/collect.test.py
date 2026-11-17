#!/usr/bin/env python3
"""collect.py 시험. 가짜 전사(JSONL)를 임시 HOME 에 만들어 읽힌다 — 실제 ~/.claude/projects·~/.codex 는 읽지 않는다.

  python3 -I collect.test.py        exit 0 전부 기대대로, 1 아니면
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.dont_write_bytecode = True   # 저장소 안에 __pycache__ 를 만들지 않는다
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'collect.py')


def load_module():
    spec = importlib.util.spec_from_file_location('wdidt_collect', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load_module()
NOW = datetime.now(timezone.utc)


def iso(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).isoformat().replace('+00:00', 'Z')


def user(text, minutes_ago=10, sid='sess-aaaa1111', **fields):
    e = {'type': 'user', 'timestamp': iso(minutes_ago), 'sessionId': sid, 'cwd': '/w/proj',
         'gitBranch': 'main', 'message': {'role': 'user', 'content': text}}
    e.update(fields)
    return e


HUMAN = {'origin': {'kind': 'human'}, 'promptSource': 'typed'}

# 한 세션에 들어갈 줄들. (줄, 기대) — 기대는 사람이 읽기 위한 주석일 뿐이고 검사는 아래에서 한다.
SESSION_LINES = [
    '',                                                               # 빈 줄
    '{"type": "user", "timestamp": ',                                  # 잘린 줄
    json.dumps({'type': 'assistant', 'timestamp': iso(9), 'message': {'content': 'hi'}}),
    json.dumps(user('첫 요청', 50, **HUMAN)),
    json.dumps(user('큐에 넣은 요청', 40, origin={'kind': 'human'}, promptSource='queued')),
    json.dumps(user('추천 수락', 39, promptSource='suggestion_accepted')),
    json.dumps(user('첫 요청', 30, **HUMAN)),                           # 같은 문장 재기록 → 하나만
    json.dumps(user('기간 밖', 60 * 30, **HUMAN)),                      # 30시간 전
    json.dumps(user([{'type': 'tool_result', 'content': 'ok'}], 20)),
    json.dumps(user('주입', 20, isMeta=True)),
    json.dumps(user('<task-notification>done</task-notification>', 19,
                    origin={'kind': 'task-notification'}, promptSource='system')),
    json.dumps(user('peer says hi', 18, origin={'kind': 'peer'}, promptSource='system', isMeta=True)),
    json.dumps(user('sdk 입력', 17, promptSource='sdk')),
    json.dumps(user('서브에이전트', 16, isSidechain=True, **HUMAN)),
    json.dumps(user('<command-name>/clear</command-name>', 15, origin={'kind': 'human'})),
    json.dumps(user('<bash-input>ls -la</bash-input>', 14)),
    json.dumps(user('옛 전사의 무표시 입력', 13)),
    json.dumps(user([{'type': 'text', 'text': '블록 '}, {'type': 'text', 'text': '입력'}], 12, **HUMAN)),
    json.dumps(user('   ', 11, **HUMAN)),                                 # 공백뿐 → 버림
    json.dumps(user('시각 없음', 10, timestamp=None, **HUMAN)),
    json.dumps(user('시각 깨짐', 10, timestamp='어제', **HUMAN)),
]


class Fixture:
    """임시 HOME 아래 ~/.claude/projects 와 ~/.codex/sessions 를 만든다."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.projects = os.path.join(self.home, '.claude', 'projects')
        self.codex = os.path.join(self.home, '.codex', 'sessions')

    def jsonl(self, rel, lines, base=None, mtime=None):
        path = os.path.join(base or self.projects, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(l if isinstance(l, str) else json.dumps(l, ensure_ascii=False) for l in lines) + '\n')
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def cleanup(self):
        self.tmp.cleanup()


class PureTest(unittest.TestCase):
    def test_parse_ts(self):
        self.assertEqual(C.parse_ts('2026-11-18T01:02:03.456Z'),
                         datetime(2026, 11, 18, 1, 2, 3, 456000, tzinfo=timezone.utc))
        self.assertEqual(C.parse_ts('2026-11-18T10:00:00+09:00').utcoffset(), timedelta(hours=9))
        for bad in (None, '', '어제', 12345, 'Z'):
            self.assertIsNone(C.parse_ts(bad), bad)

    def test_text_of(self):
        self.assertEqual(C.text_of('그냥 문자열'), '그냥 문자열')
        self.assertEqual(C.text_of([{'type': 'text', 'text': 'a'}, 'junk', {'type': 'image'},
                                    {'type': 'text', 'text': 'b'}]), 'ab')
        self.assertIsNone(C.text_of([{'type': 'text', 'text': 'a'}, {'type': 'tool_result'}]))
        self.assertIsNone(C.text_of([{'type': 'image'}]))
        self.assertIsNone(C.text_of([]))
        self.assertIsNone(C.text_of({'type': 'text', 'text': 'dict'}))
        self.assertIsNone(C.text_of(None))

    def test_classify_table(self):
        cases = [
            ({'isSidechain': True, **HUMAN}, 'x', ('machine', '서브에이전트')),
            ({'isMeta': True}, 'x', ('machine', '주입된 내용')),
            ({'origin': {'kind': 'task-notification'}}, 'x', ('machine', 'task-notification')),
            ({'origin': {'kind': 'peer'}, 'promptSource': 'typed'}, 'x', ('machine', 'peer')),
            ({'promptSource': 'system'}, 'x', ('machine', 'system')),
            ({'promptSource': 'sdk'}, 'x', ('machine', 'sdk')),
            (HUMAN, '<system-reminder>x</system-reminder>', ('machine', 'system-reminder')),
            ({'origin': {'kind': 'human'}}, '<command-name>/x</command-name>', ('machine', 'command-name')),
            ({}, '<cross-session-message from="a">', ('machine', 'cross-session-message')),
            ({}, 'Caveat: The messages below were generated by the user', ('machine', 'Caveat: The messages below were generated')),
            ({}, '[Request interrupted by user for tool use]', ('machine', 'Request interrupted by user')),
            ({}, '<bash-stdout>x</bash-stdout>', ('machine', 'bash-stdout')),
            (HUMAN, '안녕', ('human', 'typed')),
            ({'origin': {'kind': 'human'}}, '안녕', ('human', 'human')),
            ({'promptSource': 'queued'}, '안녕', ('human', 'queued')),
            ({'promptSource': 'suggestion_accepted'}, '안녕', ('human', 'suggestion_accepted')),
            ({}, '<bash-input>ls</bash-input>', ('human', 'bash-input')),
            ({}, '그냥 글', ('unknown', '판별 정보 없음')),
            ({'origin': 'human'}, '문자열 origin', ('unknown', '판별 정보 없음')),   # dict 아닌 origin
            ({'promptSource': 'weird'}, '모르는 경로', ('unknown', '판별 정보 없음')),
        ]
        for entry, body, want in cases:
            self.assertEqual(C.classify(entry, body), want, (entry, body))

    def test_dedupe_keeps_earliest(self):
        t = lambda m: NOW - timedelta(minutes=m)
        items = [{'at': t(1), 'text': 'a'}, {'at': t(5), 'text': 'a'}, {'at': t(3), 'text': 'b'}]
        out = C.dedupe(items)
        self.assertEqual([(i['text'], i['at']) for i in out], [('a', t(5)), ('b', t(3))])

    def test_one_line(self):
        self.assertEqual(C.one_line('a\n  b\tc'), 'a b c')
        self.assertEqual(C.one_line('abcdef', 3), 'abc…')
        self.assertEqual(C.one_line('abc', 3), 'abc')
        self.assertEqual(C.one_line('abcdef', 0), 'abcdef')


class CollectClaudeTest(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)
        self.fx.jsonl('-w-proj/sess-aaaa1111.jsonl', SESSION_LINES)
        # sessionId 가 없는 전사 → 파일명 앞 8자
        self.fx.jsonl('-w-other/bbbbbbbb-rest.jsonl', [
            {k: v for k, v in user('세션 id 없음', 5, cwd='/w/other', **HUMAN).items() if k != 'sessionId'}])
        # 수정 시각이 기간 밖인 파일은 열지도 않는다 (안의 시각이 기간 안이어도)
        self.fx.jsonl('-w-old/old.jsonl', [user('파일이 오래됨', 5, sid='old', **HUMAN)],
                      mtime=time.time() - 3 * 86400)
        p = mock.patch.object(C, 'CLAUDE_PROJECTS', self.fx.projects)
        p.start()
        self.addCleanup(p.stop)
        self.cutoff = NOW - timedelta(hours=24)

    def test_classification_counts(self):
        sessions = C.collect_claude(self.cutoff)
        self.assertEqual(set(sessions), {'sess-aaaa1111', 'bbbbbbbb'})
        s = sessions['sess-aaaa1111']
        human = [i['text'] for i in C.dedupe(s['human'])]
        self.assertEqual(human, ['첫 요청', '큐에 넣은 요청', '추천 수락', '<bash-input>ls -la</bash-input>', '블록 입력'])
        self.assertEqual([i['text'] for i in s['unknown']], ['옛 전사의 무표시 입력'])
        self.assertEqual(s['machine'], 6)
        # peer 는 isMeta 도 달고 와서 '주입된 내용' 으로 먼저 잡힌다. 도구 결과는 세지 않는다.
        self.assertEqual(s['machine_reasons'], {
            '주입된 내용': 2, 'task-notification': 1, 'sdk': 1, '서브에이전트': 1, 'command-name': 1})
        self.assertEqual(s['cwd'], '/w/proj')
        self.assertEqual(s['git_branch'], 'main')
        self.assertEqual(s['first'], C.parse_ts(iso(50)))
        self.assertEqual(s['last'], C.parse_ts(iso(12)))
        self.assertEqual(sessions['bbbbbbbb']['cwd'], '/w/other')

    def test_cutoff_window(self):
        sessions = C.collect_claude(NOW - timedelta(minutes=35))
        human = [i['text'] for i in sessions['sess-aaaa1111']['human']]
        self.assertNotIn('큐에 넣은 요청', human)   # 40분 전
        self.assertIn('첫 요청', human)             # 30분 전 재기록분
        sessions = C.collect_claude(NOW - timedelta(days=3, hours=1))
        self.assertIn('old', sessions)                # 기간을 넓히면 오래된 파일도 읽는다
        self.assertIn('기간 밖', [i['text'] for i in sessions['sess-aaaa1111']['human']])

    @unittest.expectedFailure
    def test_compaction_summary_is_not_unknown(self):
        # BUG: 대화 압축 요약(isCompactSummary: true)은 origin·promptSource 가 없어 [판별불가] 로 떨어진다.
        # 프로그램이 넣은 것이므로 machine 이어야 한다. 실제 전사에서 확인(2026-11-18).
        entry = user('This session is being continued from a previous conversation that ran out of context.',
                     isCompactSummary=True)
        self.assertEqual(C.classify(entry, entry['message']['content'])[0], 'machine')

    @unittest.expectedFailure
    def test_teammate_message_is_not_unknown(self):
        # BUG: 팀원 에이전트가 보낸 메시지는 판별 필드 없이 본문에 <teammate-message 표식만 있어
        # [판별불가] 로 떨어진다. INJECTED_MARKERS 에 "<teammate-message" 가 없다.
        body = ('Another Claude session sent a message:\n'
                '<teammate-message teammate_id="review-x" color="yellow">\n{"type":"idle_notification"}')
        self.assertEqual(C.classify(user(body), body)[0], 'machine')

    def test_valid_json_that_is_not_an_object_is_skipped(self):
        # BUG: 줄이 JSON 이긴 한데 객체가 아니거나(`[]`, `"x"`, `null`) message 가 객체가 아니면
        # entry.get / .get("content") 에서 AttributeError 로 전체가 죽는다. 깨진 줄처럼 건너뛰어야 한다.
        self.fx.jsonl('-w-bad/bad.jsonl', ['[]', '"x"', 'null', json.dumps(user('m', message=None))])
        C.collect_claude(self.cutoff)

    def test_timestamp_without_zone_is_skipped(self):
        # BUG: 시간대 없는 timestamp 는 naive datetime 이 되어 `ts < cutoff` 에서 TypeError 로 죽는다.
        self.fx.jsonl('-w-naive/n.jsonl', [user('x', timestamp='2099-01-01T00:00:00', **HUMAN)])
        C.collect_claude(self.cutoff)


class CollectCodexTest(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)
        p = mock.patch.object(C, 'CODEX_SESSIONS', self.fx.codex)
        p.start()
        self.addCleanup(p.stop)
        self.cutoff = NOW - timedelta(hours=24)

    def test_legacy_event_msg_user_message(self):
        self.fx.jsonl('2026/11/18/rollout-a.jsonl', [
            {'type': 'event_msg', 'timestamp': iso(5), 'payload': {'type': 'user_message', 'message': '  codex 요청 '}},
            {'type': 'event_msg', 'timestamp': iso(4), 'payload': {'type': 'user_message', 'message': ''}},
            {'type': 'event_msg', 'timestamp': iso(60 * 30), 'payload': {'type': 'user_message', 'message': '오래됨'}},
            {'type': 'event_msg', 'timestamp': iso(3), 'payload': {'type': 'agent_message', 'message': 'AI'}},
            {'type': 'event_msg', 'timestamp': iso(3), 'payload': None},
            'not json',
        ], base=self.fx.codex)
        rows = C.collect_codex(self.cutoff)
        self.assertEqual([(r['text'], r['file']) for r in rows], [('codex 요청', 'rollout-a.jsonl')])

    @unittest.expectedFailure
    def test_current_rollout_format(self):
        # BUG: 지금 Codex 전사(2026-11 확인)에는 event_msg/user_message 가 없다. 사용자 입력은
        # event_msg/item_completed 의 item.type == "UserMessage" (content: [{type: text, text}]) 와
        # response_item 의 payload {type: message, role: user, content: [{type: input_text}]} 로 남는다.
        # 그래서 --codex 가 늘 0건이다.
        self.fx.jsonl('2026/11/18/rollout-b.jsonl', [
            {'type': 'session_meta', 'timestamp': iso(6), 'payload': {'cwd': '/w/x'}},
            {'type': 'response_item', 'timestamp': iso(5), 'payload': {
                'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': '구현 진행.'}]}},
            {'type': 'event_msg', 'timestamp': iso(5), 'payload': {
                'type': 'item_completed', 'item': {'type': 'UserMessage', 'id': 'u1',
                                                   'content': [{'type': 'text', 'text': '구현 진행.'}]}}},
        ], base=self.fx.codex)
        self.assertEqual([r['text'] for r in C.collect_codex(self.cutoff)][:1], ['구현 진행.'])


class CliTest(unittest.TestCase):
    """스크립트를 자식 프로세스로 돌린다. HOME 을 임시 폴더로 바꿔 실제 전사를 못 보게 한다."""

    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)

    def run_tool(self, *args):
        env = {'HOME': self.fx.home, 'PATH': '/usr/bin:/bin', 'TZ': 'UTC', 'LANG': 'C.UTF-8'}
        return subprocess.run([sys.executable, '-I', TOOL, *args], capture_output=True, text=True,
                              env=env, timeout=30)

    def test_missing_projects_dir_exits_1(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 1)
        self.assertIn('전사 디렉터리가 없습니다', r.stderr)

    def test_bad_arguments_exit_2(self):
        for args in (['--hours', 'abc'], ['--days'], ['--max-chars', '1.5'], ['--nope']):
            self.assertEqual(self.run_tool(*args).returncode, 2, args)

    def test_json_output(self):
        self.fx.jsonl('-w-proj/sess-aaaa1111.jsonl', SESSION_LINES)
        r = self.run_tool('--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data['hours'], 24.0)
        self.assertEqual(data['codex'], [])
        [s] = data['sessions']
        self.assertEqual(len(s['human']), 5)
        self.assertEqual(s['unknown'][0]['source'], '판별 정보 없음')
        self.assertEqual(s['machine'], 6)
        self.assertTrue(s['first'] < s['last'])

    def test_days_overrides_hours(self):
        self.fx.jsonl('-w-proj/sess-aaaa1111.jsonl', SESSION_LINES)
        data = json.loads(self.run_tool('--hours', '1', '--days', '7', '--json').stdout)
        self.assertEqual(data['hours'], 168.0)
        self.assertIn('기간 밖', [i['text'] for i in data['sessions'][0]['human']])
        data = json.loads(self.run_tool('--hours', '0.55', '--json').stdout)
        self.assertEqual([i['text'] for i in data['sessions'][0]['human']], ['첫 요청', '<bash-input>ls -la</bash-input>', '블록 입력'])

    def test_text_output(self):
        self.fx.jsonl('-w-proj/sess-aaaa1111.jsonl', SESSION_LINES)
        self.fx.jsonl('-w-proj/sess-bbbb.jsonl', [user('줄\n바꿈이 있는 아주 긴 입력입니다', 3, sid='sess-bbbb2222', **HUMAN)])
        r = self.run_tool('--max-chars', '8')
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith('기간: '))
        self.assertEqual(lines[1], '세션 2개 · 직접 입력 6건 · AI/시스템 6건 · 판별불가 1건')
        self.assertIn('━━ /w/proj', r.stdout)
        self.assertIn('[판별불가] 옛 전사의 무표…', r.stdout)
        self.assertIn('  줄 바꿈이 있는…\n', r.stdout)            # 한 줄로 접고 8자에서 자름
        heads = [l for l in lines if l.startswith('  [')]
        self.assertTrue(heads[0].startswith('  [sess-bbb'))       # 최근 세션 먼저
        self.assertIn('· main', heads[0])

    def test_empty_period(self):
        os.makedirs(self.fx.projects)
        r = self.run_tool()
        self.assertEqual(r.returncode, 0)
        self.assertIn('세션 0개 · 직접 입력 0건 · AI/시스템 0건', r.stdout)
        self.assertIn('이 기간에 입력한 내용이 없습니다.', r.stdout)

    def test_codex_section(self):
        self.fx.jsonl('-w-proj/sess-aaaa1111.jsonl', SESSION_LINES)
        self.fx.jsonl('2026/11/18/rollout-a.jsonl', [
            {'type': 'event_msg', 'timestamp': iso(5), 'payload': {'type': 'user_message', 'message': 'codex 요청'}}],
            base=self.fx.codex)
        r = self.run_tool('--codex')
        self.assertIn('━━ Codex 세션 (1건) — 사람 입력 표시가 없어 확정 불가', r.stdout)
        self.assertIn('codex 요청', r.stdout)
        self.assertIn('직접 입력 5건', r.stdout)                   # Codex 는 사람 입력 건수에 합치지 않는다
        self.assertNotIn('Codex', self.run_tool().stdout)


if __name__ == '__main__':
    unittest.main()
