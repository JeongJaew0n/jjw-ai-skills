#!/usr/bin/env python3
"""skill-sync.py 시험. HOME 을 임시 디렉터리로 바꿔 ~/.claude/skills · ~/.codex/skills · 백업 · 저장소 경로가
전부 그 안에 생기게 한다. 실제 홈 디렉터리는 읽지도 고치지도 않는다.

  python3 -I skill-sync.test.py        exit 0 전부 기대대로, 1 아니면
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'skill-sync.py')
OLD, NEW = 1_600_000_000, 1_700_000_000


def snapshot(root):
    """root 아래 (상대경로 → 링크면 'link:대상', 파일이면 바이트)."""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                out[rel] = 'link:' + os.readlink(p)
            elif os.path.isfile(p):
                with open(p, 'rb') as f:
                    out[rel] = f.read()
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='skill-sync-test-')
        self.home = os.path.realpath(self._tmp.name)
        self.claude = os.path.join(self.home, '.claude', 'skills')
        self.codex = os.path.join(self.home, '.codex', 'skills')
        self.repo = os.path.join(self.home, 'my', 'Dev', 'jjw-ai-skills', 'skills')
        self.backups = os.path.join(self.home, '.claude', 'backups')
        os.makedirs(self.claude)
        os.makedirs(self.codex)

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, *args):
        env = dict(os.environ, HOME=self.home)
        return subprocess.run([sys.executable, '-I', TOOL, *args], capture_output=True, text=True,
                              env=env, cwd=self.home, timeout=60)

    def skill(self, side, name, files=None, desc='평범한 스킬', mtime=None):
        """side 쪽(claude/codex/repo 경로)에 스킬 하나를 만든다. files: {상대경로: 내용}."""
        d = os.path.join(side, name)
        files = dict(files or {})
        files.setdefault('SKILL.md', f'---\nname: {name}\ndescription: {desc}\n---\n본문\n')
        for rel, body in files.items():
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(body)
            if mtime:
                os.utime(p, (mtime, mtime))
        return d

    def analyze(self):
        r = self.run_tool('analyze', '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        return {row['name']: row for row in json.loads(r.stdout)}

    def backup_dirs(self):
        return sorted(os.listdir(self.backups)) if os.path.isdir(self.backups) else []


# ---------------------------------------------------------------- 인자 검사
class ArgsTest(Base):
    def test_usage_errors(self):
        self.assertEqual(self.run_tool().returncode, 2)
        self.assertEqual(self.run_tool('apply').returncode, 2)                       # --direction 필수
        self.assertEqual(self.run_tool('apply', '--direction', 'both').returncode, 2)
        self.assertEqual(self.run_tool('sync').returncode, 2)

    def test_bad_direction_changes_nothing(self):
        self.skill(self.claude, 'a')
        before = snapshot(self.home)
        self.run_tool('apply', '--direction', 'claude2codex')
        self.assertEqual(snapshot(self.home), before)


# ---------------------------------------------------------------- analyze
class AnalyzeTest(Base):
    def test_empty(self):
        r = self.run_tool('analyze')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('동기화가 필요한 스킬 없음', r.stdout)
        self.assertEqual(self.analyze(), {})

    def test_missing_roots_are_empty(self):
        os.rmdir(self.claude)
        os.rmdir(self.codex)
        self.assertEqual(self.run_tool('analyze').returncode, 0)
        self.assertFalse(os.path.exists(self.claude))

    def test_classification(self):
        self.skill(self.claude, 'only-claude')
        self.skill(self.codex, 'only-codex')
        for side in (self.claude, self.codex):
            self.skill(side, 'same', {'a.py': 'x'})
        self.skill(self.claude, 'differ', {'a.py': 'claude 판 내용'}, mtime=NEW)
        self.skill(self.codex, 'differ', {'a.py': 'codex 판 내용!'}, mtime=OLD)
        shared = self.skill(os.path.join(self.home, 'src'), 'shared')
        os.symlink(shared, os.path.join(self.claude, 'shared'))
        os.symlink(shared, os.path.join(self.codex, 'shared'))
        rows = self.analyze()
        self.assertEqual(rows['only-claude']['state'], 'claude 에만')
        self.assertEqual(rows['only-claude']['newer'], 'claude')
        self.assertEqual(rows['only-codex']['state'], 'codex 에만')
        self.assertEqual(rows['same']['state'], '동일(내용 일치)')
        self.assertEqual(rows['shared']['state'], '동일(같은 원본 공유)')
        self.assertEqual(rows['differ']['state'], '다름')
        self.assertEqual(rows['differ']['newer'], 'claude')
        self.assertIsNone(rows['differ']['suspect'])
        for row in rows.values():
            self.assertIsNone(row['excluded'])

    def test_equal_mtime_is_reported_as_simultaneous(self):
        self.skill(self.claude, 'tie', {'a': '1'}, mtime=OLD)
        self.skill(self.codex, 'tie', {'a': '2'}, mtime=OLD)
        self.assertEqual(self.analyze()['tie']['newer'], '동시')

    def test_ignored_entries(self):
        self.skill(self.claude, 'x', {'a': '1'})
        self.skill(self.codex, 'x', {'a': '1', '.DS_Store': 'junk', '__pycache__/m.pyc': 'b', '.git/HEAD': 'h'})
        os.makedirs(os.path.join(self.claude, '.hidden-skill'))
        with open(os.path.join(self.codex, 'loose-file.md'), 'w') as f:
            f.write('스킬 아님')
        rows = self.analyze()
        self.assertEqual(set(rows), {'x'})
        self.assertEqual(rows['x']['state'], '동일(내용 일치)')

    def test_layout_counts_in_digest(self):
        self.skill(self.claude, 'moved', {'a/f.md': 'same'})
        self.skill(self.codex, 'moved', {'b/f.md': 'same'})
        self.assertEqual(self.analyze()['moved']['state'], '다름')

    def test_suspect_when_newer_side_much_smaller(self):
        self.skill(self.claude, 'body', {'big.md': 'x' * 2000}, mtime=OLD)
        self.skill(self.codex, 'body', {'wrapper.md': 'w'}, mtime=NEW)
        row = self.analyze()['body']
        self.assertEqual(row['newer'], 'codex')
        self.assertIn('codex 가 최신인데', row['suspect'])
        self.assertEqual(row['claude_files'], 2)
        r = self.run_tool('analyze')
        self.assertIn('최신 판정이 의심스러운 1개', r.stdout)
        self.assertIn('body', r.stdout)

    def test_no_suspect_when_newer_side_bigger(self):
        self.skill(self.claude, 'grow', {'a.md': 'x' * 2000}, mtime=NEW)
        self.skill(self.codex, 'grow', {'a.md': 'x'}, mtime=OLD)
        self.assertIsNone(self.analyze()['grow']['suspect'])

    def test_exclusions(self):
        self.skill(self.repo, 'repo-skill')
        self.skill(self.claude, 'repo-skill', {'a': '1'})
        self.skill(self.codex, 'repo-skill', {'a': '2'})
        for side in (self.claude, self.codex):
            self.skill(side, 'omx-both', {'a': side}, desc='[OMX] 패키지 것')
        self.skill(self.codex, 'omx-only', desc='[OMX] 한쪽에만')
        self.skill(self.claude, 'clash', desc='개인 스킬')
        self.skill(self.codex, 'clash', desc='[OMX] 다른 스킬')
        rows = self.analyze()
        self.assertEqual(rows['repo-skill']['excluded'], '저장소 관리 (bin/install.sh)')
        self.assertEqual(rows['omx-both']['excluded'], '다른 패키지 (oh-my-codex)')
        self.assertEqual(rows['omx-only']['excluded'], '다른 패키지 (oh-my-codex)')
        self.assertEqual(rows['clash']['excluded'], '계보 충돌 — 같은 이름, 다른 출처')
        r = self.run_tool('analyze')
        self.assertIn('== 제외 4개 (건드리지 않음) ==', r.stdout)
        self.assertIn('계보 충돌은 자동으로 처리하지 않는다', r.stdout)
        self.assertIn('동기화가 필요한 스킬 없음', r.stdout)

    def test_omx_in_block_scalar_description(self):
        # BUG: description() 은 'description:' 줄의 나머지만 본다. `description: |` 처럼 여러 줄로 쓴
        # description 은 '|' 로 읽혀 [OMX] 표시를 못 찾는다 → 계보 충돌이 일반 '다름' 으로 분류되고
        # apply 가 한쪽을 덮어쓴다. 블록 스칼라면 이어지는 들여쓴 줄까지 읽어야 한다.
        self.skill(self.claude, 'clash', desc='개인 스킬')
        self.skill(self.codex, 'clash', desc='|\n  [OMX] 다른 스킬')
        self.assertEqual(self.analyze()['clash']['excluded'], '계보 충돌 — 같은 이름, 다른 출처')

    def test_digest_separates_path_from_content(self):
        # BUG: digest() 가 경로와 내용을 구분자 없이 이어 해시한다. 'a' 파일에 'bX' 와 'ab' 파일에 'X' 는
        # 같은 바이트열 'abX' 가 돼 '동일(내용 일치)' 로 판정된다. 경로·길이를 구분해 넣으면 된다.
        self.skill(self.claude, 'collide', {'a': 'bX'})
        self.skill(self.codex, 'collide', {'ab': 'X'})
        self.assertEqual(self.analyze()['collide']['state'], '다름')

    def test_analyze_is_read_only(self):
        self.skill(self.claude, 'a', {'x': '1'}, mtime=NEW)
        self.skill(self.codex, 'a', {'x': '2'}, mtime=OLD)
        self.skill(self.codex, 'b')
        before = snapshot(self.home)
        self.run_tool('analyze')
        self.run_tool('analyze', '--json')
        self.assertEqual(snapshot(self.home), before)

    def test_mixed_newest_warning(self):
        self.skill(self.claude, 'c-new', {'a': '1'}, mtime=NEW)
        self.skill(self.codex, 'c-new', {'a': '2'}, mtime=OLD)
        self.skill(self.claude, 'x-new', {'a': '1'}, mtime=OLD)
        self.skill(self.codex, 'x-new', {'a': '2'}, mtime=NEW)
        r = self.run_tool('analyze')
        self.assertIn('claude 가 최신: 1개    codex 가 최신: 1개', r.stdout)
        self.assertIn('양쪽에 최신이 섞여 있다', r.stdout)


# ---------------------------------------------------------------- apply
class ApplyTest(Base):
    def apply(self, direction='claude-to-codex', *more):
        r = self.run_tool('apply', '--direction', direction, *more)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_fill_overwrite_skip(self):
        self.skill(self.claude, 'fill', {'a': 'claude'})
        self.skill(self.claude, 'over', {'a': 'claude 새 판'}, mtime=NEW)
        self.skill(self.codex, 'over', {'a': 'codex 옛 판', 'codex-only-file': 'z'}, mtime=OLD)
        self.skill(self.codex, 'codex-only', {'a': 'c'})
        r = self.apply()
        self.assertIn('채움   fill', r.stdout)
        self.assertIn('덮어씀 over', r.stdout)
        self.assertIn('건너뜀 codex-only', r.stdout)
        self.assertIn('적용 2개, 건너뜀 1개', r.stdout)
        self.assertEqual(snapshot(os.path.join(self.codex, 'fill')), snapshot(os.path.join(self.claude, 'fill')))
        self.assertEqual(snapshot(os.path.join(self.codex, 'over')), snapshot(os.path.join(self.claude, 'over')))
        # 지우지 않는다: 원본 쪽에 없는 스킬은 그대로
        self.assertTrue(os.path.isfile(os.path.join(self.codex, 'codex-only', 'a')))
        self.assertFalse(os.path.exists(os.path.join(self.claude, 'codex-only')))

    def test_backup_before_overwrite(self):
        self.skill(self.claude, 'over', {'a': 'new'}, mtime=NEW)
        old = self.skill(self.codex, 'over', {'a': 'old', 'extra': 'e'}, mtime=OLD)
        before = snapshot(old)
        r = self.apply()
        dirs = self.backup_dirs()
        self.assertEqual(len(dirs), 1)
        self.assertTrue(dirs[0].startswith('skill-sync-'))
        backup = os.path.join(self.backups, dirs[0])
        self.assertIn(f'덮어쓴 것 백업: {backup}', r.stdout)
        self.assertEqual(snapshot(os.path.join(backup, 'over')), before)

    def test_no_backup_when_only_filling(self):
        self.skill(self.claude, 'fill')
        r = self.apply()
        self.assertEqual(self.backup_dirs(), [])
        self.assertNotIn('덮어쓴 것 백업', r.stdout)

    def test_idempotent(self):
        self.skill(self.claude, 'fill')
        self.skill(self.claude, 'over', {'a': 'new'}, mtime=NEW)
        self.skill(self.codex, 'over', {'a': 'old'}, mtime=OLD)
        self.apply()
        after_first = snapshot(self.home)
        r = self.apply()
        self.assertIn('적용할 대상이 없습니다', r.stdout)
        self.assertEqual(snapshot(self.home), after_first)
        rows = self.analyze()
        self.assertTrue(all(row['state'].startswith('동일') for row in rows.values()), rows)

    def test_reverse_direction(self):
        self.skill(self.codex, 'from-codex', {'a': 'c'})
        self.skill(self.claude, 'claude-only', {'a': 'k'})
        r = self.apply('codex-to-claude')
        self.assertIn('채움   from-codex', r.stdout)
        self.assertIn('건너뜀 claude-only', r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.claude, 'from-codex', 'a')))
        self.assertFalse(os.path.exists(os.path.join(self.codex, 'claude-only')))

    def test_only_filter(self):
        self.skill(self.claude, 'a')
        self.skill(self.claude, 'b')
        self.skill(self.claude, 'c')
        r = self.apply('claude-to-codex', '--only', ' a , c')
        self.assertIn('적용 2개', r.stdout)
        self.assertEqual(sorted(os.listdir(self.codex)), ['a', 'c'])
        r = self.apply('claude-to-codex', '--only', 'nope')
        self.assertIn('적용할 대상이 없습니다', r.stdout)

    def test_excluded_and_identical_untouched(self):
        self.skill(self.repo, 'repo-skill')
        self.skill(self.claude, 'repo-skill', {'a': 'claude'})
        self.skill(self.codex, 'repo-skill', {'a': 'codex'})
        self.skill(self.claude, 'clash', {'a': 'mine'}, desc='개인 스킬')
        self.skill(self.codex, 'clash', {'a': 'omx'}, desc='[OMX] 다른 스킬')
        self.skill(self.claude, 'omx-new', desc='[OMX] 패키지')
        for side in (self.claude, self.codex):
            self.skill(side, 'same', {'a': '1'})
        before = snapshot(self.codex)
        r = self.apply()
        self.assertIn('적용할 대상이 없습니다', r.stdout)
        r = self.apply('claude-to-codex', '--only', 'repo-skill,clash,omx-new,same')
        self.assertIn('적용할 대상이 없습니다', r.stdout)
        self.assertEqual(snapshot(self.codex), before)
        self.assertEqual(self.backup_dirs(), [])

    def test_symlinks_are_copied_as_real_files(self):
        real = os.path.join(self.home, 'shared-data')
        os.makedirs(real)
        with open(os.path.join(real, 'ref.md'), 'w') as f:
            f.write('참고')
        d = self.skill(self.claude, 'linky')
        os.symlink(os.path.join(real, 'ref.md'), os.path.join(d, 'ref.md'))
        os.symlink(real, os.path.join(d, 'refs'))
        self.apply()
        for rel in ('ref.md', 'refs'):
            self.assertFalse(os.path.islink(os.path.join(self.codex, 'linky', rel)))
        with open(os.path.join(self.codex, 'linky', 'refs', 'ref.md')) as f:
            self.assertEqual(f.read(), '참고')

    def test_symlinked_destination_is_unlinked_not_emptied(self):
        self.skill(self.claude, 'l', {'a': 'new'}, mtime=NEW)
        target = self.skill(os.path.join(self.home, 'elsewhere'), 'l', {'a': 'old'}, mtime=OLD)
        os.symlink(target, os.path.join(self.codex, 'l'))
        target_before = snapshot(target)
        self.apply()
        dst = os.path.join(self.codex, 'l')
        self.assertFalse(os.path.islink(dst))
        self.assertEqual(snapshot(dst), snapshot(os.path.join(self.claude, 'l')))
        self.assertEqual(snapshot(target), target_before)   # 링크가 가리키던 원본은 그대로
        backup = os.path.join(self.backups, self.backup_dirs()[0], 'l')
        self.assertEqual(snapshot(backup), target_before)

    def test_suspect_warning_only_toward_smaller_side(self):
        self.skill(self.claude, 'body', {'big.md': 'x' * 2000}, mtime=OLD)
        self.skill(self.codex, 'body', {'wrapper.md': 'w'}, mtime=NEW)
        r = self.run_tool('apply', '--direction', 'claude-to-codex')
        self.assertNotIn('! 주의', r.stdout)
        # 되돌려 놓고 반대 방향(작은 쪽을 원본으로)으로 밀면 경고한다. 막지는 않는다.
        self.skill(self.codex, 'body2', {'wrapper.md': 'w'}, mtime=NEW)
        self.skill(self.claude, 'body2', {'big.md': 'x' * 2000}, mtime=OLD)
        r = self.apply('codex-to-claude', '--only', 'body2')
        self.assertIn('! 주의 body2', r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.claude, 'body2', 'wrapper.md')))

    def test_refuses_when_destination_root_missing(self):
        # BUG(가드레일 빈틈): SKILL.md 동작 원칙은 "~/.codex/skills 가 없으면 Codex 를 안 쓰는 머신이니
        # 만들지 말고 멈춰" 인데, 스크립트는 그대로 진행해 copytree 가 ~/.codex/skills 를 새로 만든다.
        # apply 시작 때 dst_root 가 없으면 종료 코드를 내고 멈추면 된다.
        os.rmdir(self.codex)
        self.skill(self.claude, 'a')
        r = self.run_tool('apply', '--direction', 'claude-to-codex')
        self.assertFalse(os.path.exists(self.codex))
        self.assertNotEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=1)
