#!/usr/bin/env python3
"""install.sh 시험. install.sh 는 저장소의 skills/*/agents/openai.yaml 을 고쳐 쓰므로 실제 저장소에서는
돌리지 않는다. 스크립트를 임시 디렉터리의 가짜 저장소(<tmp>/repo/bin/install.sh)로 복사해 돌리고,
HOME 도 임시 디렉터리로 바꾼다. 실제 저장소에는 --check · --dry-run(쓰기 없음)만 돌린다.

  python3 -I install.test.py        exit 0 전부 기대대로, 1 아니면
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT = os.path.join(HERE, 'install.sh')
REAL_REPO = os.path.dirname(HERE)


def snapshot(root):
    out = {}
    for dirpath, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                out[rel] = 'link:' + os.readlink(p)
                if n in dirs:
                    dirs.remove(n)          # 링크 안으로 들어가지 않는다
            elif os.path.isfile(p):
                with open(p, 'rb') as f:
                    out[rel] = f.read()
            else:
                out[rel] = 'dir'
    return out


def skill_md(name, dmi='true'):
    return f'---\nname: {name}\ndescription: "시험용"\nuser-invocable: true\ndisable-model-invocation: {dmi}\n---\n본문\n'


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='install-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.repo = os.path.join(self.tmp, 'repo')
        self.src = os.path.join(self.repo, 'skills')
        self.home = os.path.join(self.tmp, 'home')
        self.claude = os.path.join(self.home, '.claude', 'skills')
        self.codex = os.path.join(self.home, '.codex', 'skills')
        os.makedirs(os.path.join(self.repo, 'bin'))
        shutil.copy2(SCRIPT, os.path.join(self.repo, 'bin', 'install.sh'))
        os.makedirs(self.claude)
        os.makedirs(self.codex)
        self.write(os.path.join(self.src, 'manual', 'SKILL.md'), skill_md('manual', 'true'))
        self.write(os.path.join(self.src, 'auto', 'SKILL.md'), skill_md('auto', 'false'))
        self.write(os.path.join(self.src, 'nested', 'inner', 'SKILL.md'), skill_md('inner'))

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)

    def read(self, path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def run_install(self, *args, script=None):
        env = dict(os.environ, HOME=self.home)
        return subprocess.run(['/bin/sh', script or os.path.join(self.repo, 'bin', 'install.sh'), *args],
                              capture_output=True, text=True, env=env, cwd=self.tmp, timeout=60)

    def everything(self):
        return snapshot(self.tmp)

    def policy(self, name):
        return self.read(os.path.join(self.src, name, 'agents', 'openai.yaml'))

    def backups(self):
        d = os.path.join(self.home, '.claude', 'backups')
        return sorted(os.listdir(d)) if os.path.isdir(d) else []


class ArgsTest(Base):
    def test_unknown_argument(self):
        before = self.everything()
        r = self.run_install('--force')
        self.assertEqual(r.returncode, 1)
        self.assertIn('알 수 없는 인자: --force', r.stderr)
        self.assertEqual(self.everything(), before)

    def test_missing_skills_dir(self):
        shutil.rmtree(self.src)
        r = self.run_install()
        self.assertEqual(r.returncode, 1)
        self.assertIn('skills/ 를 찾을 수 없습니다', r.stderr)


class InstallTest(Base):
    def test_links_and_policies(self):
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        for tdir in (self.claude, self.codex):
            for name in ('manual', 'auto', 'nested'):
                link = os.path.join(tdir, name)
                self.assertTrue(os.path.islink(link), link)
                self.assertEqual(os.readlink(link), os.path.join(self.src, name))
        self.assertEqual(self.policy('manual'),
                         '# bin/install.sh 가 SKILL.md frontmatter 에서 생성한다. 직접 고치지 말 것.\n'
                         'interface:\n  display_name: "manual"\n  default_prompt: "Use $manual."\n\n'
                         'policy:\n  allow_implicit_invocation: false\n')
        self.assertIn('allow_implicit_invocation: true\n', self.policy('auto'))
        self.assertFalse(os.path.exists(os.path.join(self.src, 'nested', 'agents')))
        self.assertIn('중첩 스킬', r.stdout)
        self.assertEqual(self.backups(), [])

    def test_missing_key_defaults_to_manual(self):
        # 키가 없으면 닫힌 쪽(수동). 이 저장소는 새 스킬을 수동으로 시작하고(AGENTS.md), 키를 빼먹은 실수가
        # Codex 쪽 자동 호출을 여는 쪽으로 새면 안 된다.
        self.write(os.path.join(self.src, 'nokey', 'SKILL.md'), '---\nname: nokey\n---\n')
        self.run_install()
        self.assertIn('allow_implicit_invocation: false\n', self.policy('nokey'))

    def test_idempotent(self):
        self.run_install()
        before = self.everything()
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count('이미 연결됨'), 6)
        self.assertNotIn('연결\n', r.stdout.replace('이미 연결됨', ''))
        self.assertEqual(self.everything(), before)

    def test_dry_run_and_check_change_nothing(self):
        stale = os.path.join(self.home, 'stale')
        os.makedirs(stale)
        os.symlink(stale, os.path.join(self.claude, 'manual'))
        self.write(os.path.join(self.codex, 'auto', 'config.json'), '{}')
        before = self.everything()
        for flag, banner in (('--dry-run', '(dry-run — 변경하지 않음)'), ('--check', '(점검 모드 — 변경하지 않음)')):
            r = self.run_install(flag)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(banner, r.stdout)
            self.assertIn('연결 예정', r.stdout)
            self.assertIn('다른 곳을 가리킴 → 교체', r.stdout)
            self.assertIn('복사본 발견 → 백업 후 링크로 교체', r.stdout)
            self.assertNotIn('교체된 복사본 백업', r.stdout)
            self.assertEqual(self.everything(), before)

    def test_missing_target_dir_is_skipped_not_created(self):
        shutil.rmtree(os.path.join(self.home, '.codex'))
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('대상 디렉터리 없음 — 건너뜀', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.home, '.codex')))
        self.assertTrue(os.path.islink(os.path.join(self.claude, 'manual')))

    def test_link_elsewhere_is_replaced_target_kept(self):
        other = os.path.join(self.tmp, 'old-checkout', 'manual')
        self.write(os.path.join(other, 'SKILL.md'), '옛 저장소')
        os.symlink(other, os.path.join(self.claude, 'manual'))
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'다른 곳을 가리킴 → 교체 ({other})', r.stdout)
        self.assertEqual(os.readlink(os.path.join(self.claude, 'manual')), os.path.join(self.src, 'manual'))
        self.assertEqual(self.read(os.path.join(other, 'SKILL.md')), '옛 저장소')

    def test_dangling_link_is_replaced(self):
        os.symlink(os.path.join(self.tmp, 'gone'), os.path.join(self.codex, 'auto'))
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(os.readlink(os.path.join(self.codex, 'auto')), os.path.join(self.src, 'auto'))

    def test_copy_is_backed_up_then_linked(self):
        copy = os.path.join(self.codex, 'manual')
        self.write(os.path.join(copy, 'SKILL.md'), '옛 복사본')
        self.write(os.path.join(copy, 'config.json'), '{"keep": 1}')
        self.write(os.path.join(copy, 'sub', 'f.txt'), 'f')
        before = snapshot(copy)
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.islink(copy))
        baks = self.backups()
        self.assertEqual(len(baks), 1)
        self.assertTrue(baks[0].startswith('skill-install-'))
        backup = os.path.join(self.home, '.claude', 'backups', baks[0], '.codex', 'manual')
        self.assertEqual(snapshot(backup), before)
        self.assertIn(f'교체된 복사본 백업: {os.path.dirname(os.path.dirname(backup))}', r.stdout)
        # 런타임 파일은 저장소 쪽에 없으면 옮겨 살린다
        self.assertEqual(self.read(os.path.join(self.src, 'manual', 'config.json')), '{"keep": 1}')
        self.assertIn('런타임 파일 보존: config.json', r.stdout)

    def test_runtime_file_never_overwrites_repo_copy(self):
        self.write(os.path.join(self.src, 'auto', 'config.json'), '{"repo": 1}')
        self.write(os.path.join(self.claude, 'auto', 'config.json'), '{"global": 1}')
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(os.path.join(self.src, 'auto', 'config.json')), '{"repo": 1}')
        self.assertNotIn('런타임 파일 보존', r.stdout)

    def test_unmanaged_skills_untouched_and_listed(self):
        self.write(os.path.join(self.claude, 'mine-only', 'SKILL.md'), '내 것')
        os.symlink(os.path.join(self.tmp, 'gone'), os.path.join(self.codex, 'broken-mine'))
        self.write(os.path.join(self.codex, '.system', 'x'), 'x')
        r = self.run_install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read(os.path.join(self.claude, 'mine-only', 'SKILL.md')), '내 것')
        self.assertTrue(os.path.islink(os.path.join(self.codex, 'broken-mine')))
        self.assertTrue(os.path.isfile(os.path.join(self.codex, '.system', 'x')))
        listed = r.stdout.split('=== 저장소에 없는 전역 스킬 (건드리지 않음) ===')[1]
        self.assertIn('mine-only', listed)
        self.assertNotIn('.system', listed)
        self.assertNotIn('manual', listed)

    def test_regular_file_in_the_way_is_not_overwritten(self):
        blocker = os.path.join(self.claude, 'manual')
        self.write(blocker, '스킬 자리에 놓인 파일')
        r = self.run_install()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.read(blocker), '스킬 자리에 놓인 파일')

    def test_manual_policy_survives_comment_or_crlf(self):
        # BUG: install.sh:37,55 — frontmatter 값을 줄 끝까지 통째로 읽고 정확히 "true" 일 때만 막는다.
        # `disable-model-invocation: true    # 메모` (AGENTS.md 의 예시 그대로)나 CRLF 줄 끝이면 값이
        # "true    # 메모"/"true\r" 가 돼 Codex 쪽이 allow_implicit_invocation: true 로 열린다(가드레일이
        # 반대로 풀림). 값의 주석·공백·\r 을 잘라 내거나, "false" 일 때만 true 로 여는 쪽으로 바꾸면 된다.
        self.write(os.path.join(self.src, 'commented', 'SKILL.md'),
                   '---\nname: commented\ndisable-model-invocation: true    # 자동 스킬만 false\n---\n')
        self.write(os.path.join(self.src, 'crlf', 'SKILL.md'),
                   '---\r\nname: crlf\r\ndisable-model-invocation: true\r\n---\r\n')
        self.run_install()
        self.assertIn('allow_implicit_invocation: false\n', self.policy('commented'))
        self.assertIn('allow_implicit_invocation: false\n', self.policy('crlf'))


class RealRepoReadOnlyTest(Base):
    """실제 저장소 스크립트는 쓰기 없는 모드로만 돌린다. 임시 HOME 이 바뀌지 않아야 한다."""

    def test_check_and_dry_run_write_nothing(self):
        before = snapshot(self.home)
        for flag in ('--check', '--dry-run'):
            r = self.run_install(flag, script=SCRIPT)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f'저장소: {REAL_REPO}', r.stdout)
            self.assertIn('ai-mistake-log', r.stdout)
            self.assertEqual(snapshot(self.home), before)


if __name__ == '__main__':
    unittest.main(verbosity=1)
