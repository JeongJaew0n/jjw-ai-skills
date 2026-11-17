#!/usr/bin/env python3
"""scaffold.py 시험. 임시 디렉터리 안에서만 git init 하고, git global 설정은 임시 파일(GIT_CONFIG_GLOBAL)로
바꿔 둔다. gh 는 PATH 에서 빼거나 가짜로 바꿔 네트워크를 쓰지 않는다.

  python3 -I scaffold.test.py        exit 0 전부 기대대로, 1 아니면
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True   # 저장소 안에 __pycache__ 를 만들지 않는다
HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'scaffold.py')
GIT = shutil.which('git')

spec = importlib.util.spec_from_file_location('scaffold', TOOL)
SCAFFOLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SCAFFOLD)
DOC_TREE = SCAFFOLD.DOC_TREE


def snapshot(root):
    """root 아래 모든 파일의 (상대경로 → 바이트). .git 은 빼고 본다."""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != '.git']
        for f in files:
            p = os.path.join(dirpath, f)
            with open(p, 'rb') as fh:
                out[os.path.relpath(p, root)] = fh.read()
    return out


@unittest.skipIf(GIT is None, 'git 없음')
class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='scaffold-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, 'home')
        self.root = os.path.join(self.tmp, 'proj')
        self.bin = os.path.join(self.tmp, 'bin')
        for d in (self.home, self.root, self.bin):
            os.makedirs(d)
        os.symlink(GIT, os.path.join(self.bin, 'git'))
        self.gitconfig = os.path.join(self.home, 'gitconfig')
        with open(self.gitconfig, 'w') as f:
            f.write('[user]\n\tname = Global Person\n\temail = global@example.invalid\n')
        with open(self.gitconfig, 'rb') as f:
            self.gitconfig_before = f.read()

    def tearDown(self):
        # git global 설정은 어떤 명령으로도 바뀌면 안 된다
        with open(self.gitconfig, 'rb') as f:
            self.assertEqual(f.read(), self.gitconfig_before)
        self._tmp.cleanup()

    def env(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(HOME=self.home, GIT_CONFIG_GLOBAL=self.gitconfig, GIT_CONFIG_NOSYSTEM='1',
                   PATH=os.pathsep.join([self.bin, '/usr/bin', '/bin']))
        return env

    def run_tool(self, *args):
        return subprocess.run([sys.executable, '-I', TOOL, *args], capture_output=True, text=True,
                              env=self.env(), cwd=self.tmp, timeout=60)

    def apply(self, *args, root=None):
        return self.run_tool('apply', '--root', root or self.root, *args)

    def git(self, *args, root=None):
        return subprocess.run([GIT, '-C', root or self.root, *args], capture_output=True, text=True,
                              env=self.env(), timeout=60)

    def local(self, key, root=None):
        return self.git('config', '--local', key, root=root).stdout.strip()

    def fake_gh(self, stderr_lines, code=1):
        p = os.path.join(self.bin, 'gh')
        body = ''.join(f"echo '{line}' >&2\n" for line in stderr_lines)
        with open(p, 'w') as f:
            f.write(f'#!/bin/sh\n{body}exit {code}\n')
        os.chmod(p, 0o755)


# ---------------------------------------------------------------- 인자 검사
class ArgsTest(Base):
    def test_no_subcommand_is_usage_error(self):
        self.assertEqual(self.run_tool().returncode, 2)

    def test_unknown_flag_is_usage_error(self):
        self.assertEqual(self.run_tool('apply', '--force').returncode, 2)
        self.assertEqual(snapshot(self.root), {})

    def test_missing_root_dir(self):
        missing = os.path.join(self.tmp, 'nope')
        r = self.apply(root=missing)
        self.assertEqual(r.returncode, 1)
        self.assertIn('디렉터리가 없습니다', r.stderr)
        self.assertFalse(os.path.exists(missing))

    def test_name_without_email_refused(self):
        self.git('init')
        for args in (('--author-name', 'A'), ('--author-email', 'a@example.invalid')):
            r = self.apply(*args)
            self.assertEqual(r.returncode, 1)
            self.assertIn('함께 줘야', r.stderr)
        self.assertEqual(self.local('user.name'), '')

    def test_identity_without_repo_refused(self):
        r = self.apply('--author-name', 'A', '--author-email', 'a@example.invalid')
        self.assertEqual(r.returncode, 1)
        self.assertIn('--git-init', r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, '.git')))

    def test_invalid_args_write_nothing(self):
        # BUG: 신원 인자 검사(짝이 안 맞음, git 저장소 아님)가 docs 골격을 쓴 다음에 일어난다.
        # 종료 코드 1 로 실패했다고 알리면서 파일 다섯 개는 이미 만들어져 있다.
        # 인자 검사를 1) docs 골격 앞으로 옮기면 된다.
        r = self.apply('--author-name', 'A')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(snapshot(self.root), {})


# ---------------------------------------------------------------- apply
class ApplyTest(Base):
    def test_creates_doc_tree(self):
        r = self.apply()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.root), {k: v.encode() for k, v in DOC_TREE.items()})
        for rel in DOC_TREE:
            self.assertIn(f'생성 : {rel}', r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.root, '.git')))

    def test_idempotent(self):
        self.apply('--git-init', '--author-name', 'A', '--author-email', 'a@example.invalid')
        before = snapshot(self.root)
        r = self.apply('--git-init', '--author-name', 'A', '--author-email', 'a@example.invalid')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.root), before)
        self.assertNotIn('생성 :', r.stdout)
        self.assertEqual(r.stdout.count('이미 있음 — 덮어쓰지 않음'), len(DOC_TREE))
        self.assertEqual(self.local('user.email'), 'a@example.invalid')

    def test_never_overwrites_existing_files(self):
        mine = os.path.join(self.root, 'docs', 'plans', 'README.md')
        os.makedirs(os.path.dirname(mine))
        with open(mine, 'w') as f:
            f.write('내 계획 문서\n')
        r = self.apply()
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(mine) as f:
            self.assertEqual(f.read(), '내 계획 문서\n')
        self.assertIn('유지 : docs/plans/README.md', r.stdout)
        snap = snapshot(self.root)
        for rel, body in DOC_TREE.items():
            if rel != 'docs/plans/README.md':
                self.assertEqual(snap[rel], body.encode())

    def test_dangling_symlink_is_not_written_through(self):
        # BUG: 존재 확인이 os.path.exists 라서 끊어진 심볼릭 링크를 '없음' 으로 본다. 그다음 open(…, 'w')
        # 가 링크를 따라가 프로젝트 밖(링크 대상)에 파일을 만든다. os.path.lexists 로 보면 된다.
        outside = os.path.join(self.tmp, 'outside', 'target.md')
        os.makedirs(os.path.dirname(outside))
        link = os.path.join(self.root, 'docs', 'plans', 'README.md')
        os.makedirs(os.path.dirname(link))
        os.symlink(outside, link)
        self.apply()
        self.assertFalse(os.path.exists(outside))

    def test_dry_run_writes_nothing(self):
        r = self.apply('--dry-run', '--git-init', '--author-name', 'A', '--author-email', 'a@example.invalid')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('--dry-run', r.stdout)
        self.assertIn('생성 : .git/', r.stdout)
        self.assertIn('신원 : A <a@example.invalid>', r.stdout)
        self.assertNotIn('확인 :', r.stdout)
        self.assertEqual(os.listdir(self.root), [])

    def test_git_init_and_local_identity(self):
        r = self.apply('--git-init', '--author-name', 'Proj Person', '--author-email', 'proj@example.invalid')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(self.root, '.git')))
        self.assertEqual(self.local('user.name'), 'Proj Person')
        self.assertEqual(self.local('user.email'), 'proj@example.invalid')
        self.assertIn('확인 : Proj Person <proj@example.invalid>', r.stdout)
        # 실효 값(로컬이 global 을 이김)
        self.assertEqual(self.git('config', 'user.email').stdout.strip(), 'proj@example.invalid')

    def test_git_init_skipped_for_existing_repo(self):
        self.git('init')
        marker = os.path.join(self.root, '.git', 'marker')
        with open(marker, 'w') as f:
            f.write('x')
        r = self.apply('--git-init')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('.git/', r.stdout)
        self.assertTrue(os.path.exists(marker))

    def test_identity_in_existing_repo_without_git_init(self):
        self.git('init')
        r = self.apply('--author-name', 'A', '--author-email', 'a@example.invalid')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.local('user.name'), 'A')

    def test_identity_change_replaces_local_value(self):
        self.apply('--git-init', '--author-name', 'Old', '--author-email', 'old@example.invalid')
        self.apply('--author-name', 'New', '--author-email', 'new@example.invalid')
        self.assertEqual(self.local('user.email'), 'new@example.invalid')
        self.assertEqual(self.git('config', '--local', '--get-all', 'user.email').stdout.split(),
                         ['new@example.invalid'])

    def test_identity_in_git_worktree(self):
        # BUG: 저장소 판정이 os.path.isdir(root/.git) 이라 .git 이 '파일'인 곳(git worktree, 서브모듈)을
        # 저장소가 아니라고 본다. 신원 설정이 "git 저장소가 아니라" 로 거부된다(detect 도 local 설정을
        # 안 보여 준다). `git -C root rev-parse --git-dir` 로 판정하면 된다.
        self.git('init')
        self.git('-c', 'user.name=t', '-c', 'user.email=t@example.invalid', 'commit', '--allow-empty', '-m', 'init')
        wt = os.path.join(self.tmp, 'wt')
        self.git('worktree', 'add', '-q', wt)
        r = self.apply('--author-name', 'A', '--author-email', 'a@example.invalid', root=wt)
        self.assertEqual(r.returncode, 0, r.stderr)


# ---------------------------------------------------------------- detect
class DetectTest(Base):
    def test_global_identity_and_no_gh(self):
        r = self.run_tool('detect', '--root', self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Global Person <global@example.invalid>', r.stdout)
        self.assertIn('(gh 설치 안 됨)', r.stdout)
        self.assertNotIn('local 설정', r.stdout)

    def test_gh_accounts_read_from_stderr_despite_nonzero_exit(self):
        self.fake_gh(['github.com', '  ✓ Logged in to github.com account alice (keyring)',
                      '  X Timeout trying to log in to github.com account bob (keyring)', '  - Token: gho_***'])
        r = self.run_tool('detect', '--root', self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('account alice', r.stdout)
        self.assertIn('account bob', r.stdout)
        self.assertNotIn('Token', r.stdout)

    def test_gh_not_logged_in(self):
        self.fake_gh(['You are not logged into any GitHub hosts.'])
        r = self.run_tool('detect', '--root', self.root)
        self.assertIn('(미로그인)', r.stdout)

    def test_local_identity_shown_and_nothing_changed(self):
        self.git('init')
        self.git('config', '--local', 'user.name', 'Local One')
        before = snapshot(self.root)
        with open(os.path.join(self.root, '.git', 'config'), 'rb') as f:
            cfg = f.read()
        r = self.run_tool('detect', '--root', self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Local One <(미설정)>', r.stdout)
        self.assertEqual(snapshot(self.root), before)
        with open(os.path.join(self.root, '.git', 'config'), 'rb') as f:
            self.assertEqual(f.read(), cfg)

    def test_unset_global(self):
        with open(self.gitconfig, 'w') as f:
            f.write('')
        self.gitconfig_before = b''
        r = self.run_tool('detect', '--root', self.root)
        self.assertIn('(없음) <(없음)>', r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=1)
