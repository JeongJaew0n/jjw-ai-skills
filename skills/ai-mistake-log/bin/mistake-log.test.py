#!/usr/bin/env python3
"""mistake-log.py 시험. 모든 쓰기는 임시 HOME 안에서만 한다 — 실제 ~/.claude 는 읽지도 고치지도 않는다.

  python3 -I mistake-log.test.py        exit 0 전부 기대대로, 1 아니면
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True   # 저장소 안에 __pycache__ 를 만들지 않는다
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'mistake-log.py')
GUARD = os.path.join(HERE, 'bash-guard.py')
BEGIN = '<!-- ai-mistake-log:begin -->'
END = '<!-- ai-mistake-log:end -->'
ENV_KEYS = ('AI_MISTAKES_DIR', 'AI_MISTAKES_CLAUDE_MD', 'AI_MISTAKES_CODEX_MD', 'AI_MISTAKES_SETTINGS')


def load_module():
    spec = importlib.util.spec_from_file_location('mistake_log', TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # 가져오기는 경로 문자열만 만든다. 파일을 건드리지 않는다
    return mod


ML = load_module()


def real_guard_id():
    out = subprocess.run([sys.executable, GUARD, '--list'], capture_output=True, text=True, timeout=10)
    ids = out.stdout.split()
    return ids[0] if ids else None


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='mistake-log-test-')
        self.home = os.path.realpath(self._tmp.name)
        self.mistakes = os.path.join(self.home, '.claude', 'mistakes')
        self.claude_md = os.path.join(self.home, '.claude', 'CLAUDE.md')
        self.codex_md = os.path.join(self.home, '.codex', 'AGENTS.md')
        self.settings = os.path.join(self.home, '.claude', 'settings.json')
        self.installed_guard = os.path.join(self.home, '.claude', 'skills', 'ai-mistake-log', 'bin', 'bash-guard.py')

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, *args, extra_env=None):
        env = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
        env['HOME'] = self.home          # 기본 경로가 전부 임시 HOME 아래로 간다
        env.update(extra_env or {})
        return subprocess.run([sys.executable, '-I', TOOL, *args], capture_output=True, text=True,
                              env=env, cwd=self.home, timeout=30)

    def new(self, slug, rule='규칙 한 줄', title='제목', *more):
        return self.run_tool('new', slug, '--title', title, '--rule', rule, '--date', '2026-01-02', *more)

    def read(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    def backups(self):
        d = os.path.join(self.mistakes, '.backups')
        return sorted(os.listdir(d)) if os.path.isdir(d) else []


# ---------------------------------------------------------------- 인자 검사
class ArgsTest(Base):
    def test_no_subcommand_is_usage_error(self):
        self.assertEqual(self.run_tool().returncode, 2)

    def test_unknown_subcommand(self):
        self.assertEqual(self.run_tool('frobnicate').returncode, 2)

    def test_new_requires_title_and_rule(self):
        self.assertEqual(self.run_tool('new', 'a-b', '--title', 't').returncode, 2)
        self.assertEqual(self.run_tool('new', 'a-b', '--rule', 'r').returncode, 2)
        self.assertFalse(os.path.exists(self.mistakes))

    def test_bad_slugs_refused(self):
        for slug in ('Upper', 'with space', 'under_score', '-lead', 'trail-', 'a--b', '../escape', ''):
            r = self.new(slug)
            self.assertEqual(r.returncode, 2, slug)
            self.assertIn('slug', r.stderr)
        self.assertFalse(os.path.exists(self.mistakes) and os.listdir(self.mistakes))

    def test_multiline_title_or_rule_refused(self):
        self.assertEqual(self.new('ok-slug', '두\n줄').returncode, 2)
        self.assertEqual(self.new('ok-slug', '한 줄', '두\n줄').returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.mistakes, '2026-01-02-ok-slug.md')))

    def test_unknown_guard_refused(self):
        r = self.new('ok-slug', '규칙', '제목', '--guard', 'no-such-guard-id')
        self.assertEqual(r.returncode, 2)
        self.assertIn('guard id', r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.mistakes, '2026-01-02-ok-slug.md')))

    def test_new_date_is_validated(self):
        # BUG: --date 는 형식을 검사하지 않고 파일 이름에 그대로 들어간다. '../x' 를 주면
        # 기록이 ~/.claude/mistakes 밖(~/.claude/x-ok-slug.md)에 생긴다.
        r = self.new('ok-slug', '규칙', '제목', '--date', '../x')
        self.assertFalse(os.path.exists(os.path.join(self.home, '.claude', 'x-ok-slug.md')))
        self.assertEqual(r.returncode, 2)


# ---------------------------------------------------------------- new / list
class NewListTest(Base):
    def test_new_creates_record_with_frontmatter(self):
        r = self.new('bsd-thing', '옵션을 패턴 앞에 둔다', '제목: 콜론 포함')
        self.assertEqual(r.returncode, 0, r.stderr)
        path = os.path.join(self.mistakes, '2026-01-02-bsd-thing.md')
        self.assertEqual(r.stdout.strip(), path)
        meta = ML.parse_record(path)
        self.assertEqual(meta['date'], '2026-01-02')
        self.assertEqual(meta['title'], '제목: 콜론 포함')
        self.assertEqual(meta['rule'], '옵션을 패턴 앞에 둔다')
        self.assertEqual(meta['guard'], '')
        for section in ('## 무엇을 했나', '## 무엇이 망가졌나', '## 왜 (근본 원인)', '## 증거', '## 재발 방지'):
            self.assertIn(section, self.read(path))

    def test_new_with_real_guard(self):
        gid = real_guard_id()
        if not gid:
            self.skipTest('bash-guard.py --list 가 비어 있음')
        r = self.new('with-guard', '규칙', '제목', '--guard', gid)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.read(os.path.join(self.mistakes, '2026-01-02-with-guard.md'))
        self.assertIn(f'guard: {gid}', text)
        self.assertIn(f'훅 `{gid}`(install-hook)', text)

    def test_new_never_overwrites(self):
        self.assertEqual(self.new('dup', '처음').returncode, 0)
        path = os.path.join(self.mistakes, '2026-01-02-dup.md')
        self.write(path, self.read(path) + '\n손으로 채운 내용\n')
        before = self.read(path)
        r = self.new('dup', '두 번째')
        self.assertEqual(r.returncode, 2)
        self.assertIn('이미 있어', r.stderr)
        self.assertEqual(self.read(path), before)

    def test_new_default_date_is_today(self):
        import datetime
        r = self.run_tool('new', 'today', '--title', 't', '--rule', 'r')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip().endswith(f'{datetime.date.today().isoformat()}-today.md'))

    def test_list_empty_and_filled(self):
        r = self.run_tool('list')
        self.assertEqual(r.returncode, 0)
        self.assertIn('기록 없음', r.stdout)
        self.new('one', '규칙', '첫 제목')
        self.write(os.path.join(self.mistakes, 'README.md'), '# 무시돼야 함\n')
        self.write(os.path.join(self.mistakes, '.hidden.md'), '---\ntitle: 숨김\n---\n')
        r = self.run_tool('list')
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn('첫 제목', lines[0])
        self.assertTrue(lines[0].startswith('2026-01-02'))

    def test_env_overrides_dir(self):
        other = os.path.join(self.home, 'elsewhere')
        r = self.run_tool('new', 'env-dir', '--title', 't', '--rule', 'r', '--date', '2026-01-02',
                          extra_env={'AI_MISTAKES_DIR': other})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(other, '2026-01-02-env-dir.md')))
        self.assertFalse(os.path.exists(self.mistakes))


# ---------------------------------------------------------------- 블록 (순수 함수)
class BlockTest(unittest.TestCase):
    BLOCK = f'{BEGIN}\n새 블록\n{END}\n'

    def test_append_to_empty(self):
        self.assertEqual(ML.apply_block('', self.BLOCK), self.BLOCK)

    def test_append_adds_blank_line_and_missing_newline(self):
        self.assertEqual(ML.apply_block('사용자 글', self.BLOCK), '사용자 글\n\n' + self.BLOCK)

    def test_replace_keeps_outside_text(self):
        text = f'앞\n\n{BEGIN}\n옛 블록\n{END}\n뒤\n'
        self.assertEqual(ML.apply_block(text, self.BLOCK), f'앞\n\n{self.BLOCK}뒤\n')

    def test_idempotent(self):
        once = ML.apply_block('앞\n', self.BLOCK)
        self.assertEqual(ML.apply_block(once, self.BLOCK), once)

    def test_marker_mentioned_in_user_text_is_not_a_block(self):
        # BUG: 사용자 글이 시작 표시를 본문에 언급만 해도(예: "`<!-- ai-mistake-log:begin -->` 사이는 …")
        # 첫 sync 는 블록을 끝에 붙이고, 두 번째 sync 는 그 언급부터 블록 끝까지를 통째로 갈아 끼워
        # 블록 밖 사용자 글을 지운다. 표시는 줄 전체로만, 그리고 END 는 BEGIN 뒤에서 찾아야 한다.
        user = f'규칙: `{BEGIN}` 사이는 손대지 마.\n사이에 낀 사용자 글\n'
        once = ML.apply_block(user, self.BLOCK)
        twice = ML.apply_block(once, self.BLOCK)
        self.assertIn('사이에 낀 사용자 글', twice)


# ---------------------------------------------------------------- sync / check
class SyncCheckTest(Base):
    def test_sync_creates_both_targets_without_backup(self):
        self.new('first', '첫 규칙')
        r = self.run_tool('sync')
        self.assertEqual(r.returncode, 0, r.stderr)
        for path in (self.claude_md, self.codex_md):
            text = self.read(path)
            self.assertTrue(text.startswith(BEGIN))
            self.assertIn('- 첫 규칙 (기록: `~/.claude/mistakes/2026-01-02-first.md`)', text)
        self.assertEqual(self.backups(), [])
        self.assertIn('만듦', r.stdout)

    def test_sync_with_no_records_writes_placeholder(self):
        self.assertEqual(self.run_tool('sync').returncode, 0)
        self.assertIn('- (아직 없음)', self.read(self.claude_md))

    def test_sync_preserves_outside_text_and_backs_up(self):
        user = '# 내 전역 지침\n\n블록 밖 사용자 글\n'
        self.write(self.claude_md, user)
        self.new('first', '첫 규칙')
        r = self.run_tool('sync')
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.read(self.claude_md)
        self.assertTrue(text.startswith(user))
        self.assertIn('첫 규칙', text)
        self.assertIn('백업', r.stdout)
        baks = self.backups()
        self.assertEqual(len(baks), 1)          # codex 쪽은 새로 만들었으니 백업 없음
        self.assertTrue(baks[0].startswith('~_.claude_CLAUDE.md.'))
        self.assertEqual(self.read(os.path.join(self.mistakes, '.backups', baks[0])), user)

    def test_sync_is_idempotent(self):
        self.new('first', '첫 규칙')
        self.run_tool('sync')
        before = (self.read(self.claude_md), self.read(self.codex_md))
        r = self.run_tool('sync')
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.count('변경 없음'), 2)
        self.assertEqual((self.read(self.claude_md), self.read(self.codex_md)), before)
        self.assertEqual(self.backups(), [])

    def test_sync_updates_block_in_place(self):
        self.new('first', '첫 규칙')
        self.run_tool('sync')
        self.write(self.claude_md, '앞 글\n\n' + self.read(self.claude_md) + '\n뒤 글\n')
        self.new('second', '둘째 규칙')
        self.assertEqual(self.run_tool('sync').returncode, 0)
        text = self.read(self.claude_md)
        self.assertEqual(text.count(BEGIN), 1)
        self.assertTrue(text.startswith('앞 글\n\n' + BEGIN))
        self.assertTrue(text.endswith('\n뒤 글\n'))
        self.assertLess(text.index('첫 규칙'), text.index('둘째 규칙'))

    def test_sync_dry_run_writes_nothing(self):
        self.new('first', '첫 규칙')
        self.write(self.claude_md, '사용자 글\n')
        r = self.run_tool('sync', '--dry-run')
        self.assertEqual(r.returncode, 0)
        self.assertIn('갱신 예정', r.stdout)
        self.assertIn('만들 예정', r.stdout)
        self.assertEqual(self.read(self.claude_md), '사용자 글\n')
        self.assertFalse(os.path.exists(self.codex_md))
        self.assertEqual(self.backups(), [])

    def test_sync_uses_env_targets(self):
        c = os.path.join(self.home, 'x', 'C.md')
        x = os.path.join(self.home, 'y', 'A.md')
        r = self.run_tool('sync', extra_env={'AI_MISTAKES_CLAUDE_MD': c, 'AI_MISTAKES_CODEX_MD': x})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(c) and os.path.isfile(x))
        self.assertFalse(os.path.exists(self.claude_md))

    def test_check_reports_out_of_sync_then_clean(self):
        self.new('first', '첫 규칙')
        r = self.run_tool('check')
        self.assertEqual(r.returncode, 1)
        self.assertIn('2건', r.stdout)
        self.run_tool('sync')
        r = self.run_tool('check')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('문제 없음', r.stdout)

    def test_check_flags_empty_rule_and_unknown_guard(self):
        self.write(os.path.join(self.mistakes, '2026-01-01-hand.md'),
                   '---\ndate: 2026-01-01\ntitle: 손\nrule:\nguard: no-such-guard\n---\n')
        self.run_tool('sync')
        r = self.run_tool('check')
        self.assertEqual(r.returncode, 1)
        self.assertIn('rule 이 비어 있음', r.stdout)
        self.assertIn('없는 guard id: no-such-guard', r.stdout)
        self.assertIn('훅이 등록 안 됨', r.stdout)

    def test_check_is_read_only(self):
        self.new('first', '첫 규칙')
        self.run_tool('check')
        self.assertFalse(os.path.exists(self.claude_md))
        self.assertFalse(os.path.exists(self.settings))


# ---------------------------------------------------------------- install-hook
class InstallHookTest(Base):
    def install_guard_file(self):
        self.write(self.installed_guard, '#!/bin/sh\n')

    def test_refuses_when_guard_not_installed(self):
        r = self.run_tool('install-hook')
        self.assertEqual(r.returncode, 2)
        self.assertIn('install.sh', r.stderr)
        self.assertFalse(os.path.exists(self.settings))

    def test_refuses_even_dry_run_when_guard_not_installed(self):
        self.assertEqual(self.run_tool('install-hook', '--dry-run').returncode, 2)

    def test_creates_settings_when_missing(self):
        self.install_guard_file()
        r = self.run_tool('install-hook')
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(self.read(self.settings))
        hook = data['hooks']['PreToolUse'][0]
        self.assertEqual(hook['matcher'], 'Bash')
        self.assertEqual(hook['hooks'][0]['command'], self.installed_guard)
        self.assertEqual(hook['hooks'][0]['timeout'], 10)
        self.assertNotIn('백업', r.stdout)
        self.assertEqual([f for f in os.listdir(os.path.dirname(self.settings)) if 'tmp-ai-mistake-log' in f], [])

    def test_preserves_other_keys_and_backs_up(self):
        self.install_guard_file()
        original = {'model': 'x', 'permissions': {'allow': ['Bash(ls)']},
                    'hooks': {'PreToolUse': [{'matcher': 'Edit', 'hooks': [{'type': 'command', 'command': 'other'}]}],
                              'Stop': [{'hooks': []}]}}
        self.write(self.settings, json.dumps(original))
        raw = self.read(self.settings)
        r = self.run_tool('install-hook')
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(self.read(self.settings))
        self.assertEqual(data['model'], 'x')
        self.assertEqual(data['permissions'], original['permissions'])
        self.assertEqual(data['hooks']['Stop'], original['hooks']['Stop'])
        self.assertEqual(data['hooks']['PreToolUse'][0], original['hooks']['PreToolUse'][0])
        self.assertEqual(len(data['hooks']['PreToolUse']), 2)
        baks = [f for f in os.listdir(os.path.dirname(self.settings)) if f.startswith('settings.json.bak-ai-mistake-log-')]
        self.assertEqual(len(baks), 1)
        self.assertEqual(self.read(os.path.join(os.path.dirname(self.settings), baks[0])), raw)

    def test_idempotent(self):
        self.install_guard_file()
        self.run_tool('install-hook')
        before = self.read(self.settings)
        r = self.run_tool('install-hook')
        self.assertEqual(r.returncode, 0)
        self.assertIn('이미 등록돼 있어', r.stdout)
        self.assertEqual(self.read(self.settings), before)
        baks = [f for f in os.listdir(os.path.dirname(self.settings)) if '.bak-' in f]
        self.assertEqual(baks, [])

    def test_recognises_hook_registered_under_another_path(self):
        # 저장소 실물 경로로 등록된 것도 같은 훅으로 본다 (…/ai-mistake-log/bin/bash-guard.py 로 끝나면)
        self.write(self.settings, json.dumps({'hooks': {'PreToolUse': [
            {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': '/repo/skills/ai-mistake-log/bin/bash-guard.py'}]}]}}))
        before = self.read(self.settings)
        r = self.run_tool('install-hook')
        self.assertEqual(r.returncode, 0)
        self.assertIn('이미 등록돼 있어', r.stdout)
        self.assertEqual(self.read(self.settings), before)

    def test_dry_run_writes_nothing(self):
        self.install_guard_file()
        self.write(self.settings, '{"model": "x"}')
        r = self.run_tool('install-hook', '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['hooks']['PreToolUse'][0]['matcher'], 'Bash')
        self.assertEqual(self.read(self.settings), '{"model": "x"}')
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.settings))), ['settings.json', 'skills'])

    def test_broken_settings_is_left_alone(self):
        self.install_guard_file()
        self.write(self.settings, '{ not json')
        r = self.run_tool('install-hook')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.read(self.settings), '{ not json')

    def test_check_passes_after_hook_with_guard_record(self):
        gid = real_guard_id()
        if not gid:
            self.skipTest('bash-guard.py --list 가 비어 있음')
        self.install_guard_file()
        self.new('guarded', '규칙', '제목', '--guard', gid)
        self.run_tool('sync')
        self.assertEqual(self.run_tool('check').returncode, 1)
        self.run_tool('install-hook')
        r = self.run_tool('check')
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=1)
