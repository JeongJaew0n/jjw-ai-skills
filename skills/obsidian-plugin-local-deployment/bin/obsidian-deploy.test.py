#!/usr/bin/env python3
"""obsidian-deploy.sh 시험. 플러그인 레포와 vault 는 전부 임시 폴더에 만든다 — 실제 vault·Obsidian 은 건드리지 않는다.

스크립트는 --plugins-dir 로 받은 곳에만 쓰고 obsidian 명령을 부르지 않는다. 그래도 PATH 맨 앞에 인자만 기록하는
가짜 obsidian·open 을 두고, 불리지 않았는지 확인한다.

  python3 -I obsidian-deploy.test.py        exit 0 전부 기대대로, 1 아니면
"""
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'obsidian-deploy.sh')
MANIFEST = {'id': 'my-plugin', 'name': 'My Plugin', 'version': '1.2.3', 'minAppVersion': '1.0.0'}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='obsidian-deploy-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, 'home')
        self.src = os.path.join(self.tmp, 'repo')
        self.vault = os.path.join(self.home, 'vault')
        self.plugins = os.path.join(self.vault, '.obsidian', 'plugins')
        self.fakebin = os.path.join(self.tmp, 'fakebin')
        self.calls = os.path.join(self.tmp, 'calls.log')
        for d in (self.home, self.src, self.plugins, self.fakebin):
            os.makedirs(d, exist_ok=True)
        for name in ('obsidian', 'open'):
            p = os.path.join(self.fakebin, name)
            with open(p, 'w') as f:
                f.write(f'#!/bin/sh\necho "{name} $*" >> "{self.calls}"\n')
            os.chmod(p, 0o755)
        self.write(os.path.join(self.src, 'manifest.json'), json.dumps(MANIFEST))
        self.write(os.path.join(self.src, 'main.js'), 'console.log("v2")')
        self.write(os.path.join(self.src, 'styles.css'), '.a{}')

    def tearDown(self):
        self.assertFalse(os.path.exists(self.calls), 'obsidian/open 이 불렸다')
        self._tmp.cleanup()

    @staticmethod
    def write(path, body):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)

    @staticmethod
    def read(path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def run_tool(self, *argv, cwd=None):
        # PYTHONDONTWRITEBYTECODE: macOS 의 /usr/bin/python3 가 임시 HOME/Library/Caches 에 .pyc 를 쓰지 않게
        env = {'HOME': self.home, 'PATH': f'{self.fakebin}:/usr/bin:/bin', 'LANG': 'en_US.UTF-8',
               'PYTHONDONTWRITEBYTECODE': '1'}
        return subprocess.run(['/bin/sh', TOOL, *argv], capture_output=True, text=True, env=env,
                              cwd=cwd or self.tmp, timeout=30)

    def deploy(self, *extra):
        return self.run_tool('--src', self.src, '--plugins-dir', self.plugins, *extra)

    def tree(self, root=None):
        root = root or self.tmp
        out = set()
        for d, _, files in os.walk(root):
            for f in files:
                rel = os.path.relpath(os.path.join(d, f), root)
                if '/Library/Caches/' not in '/' + rel:                # 파이썬이 남기는 캐시는 세지 않는다
                    out.add(rel)
        return out


class Refusals(Base):
    def test_unknown_argument(self):
        r = self.run_tool('--vault', 'x')
        self.assertEqual(r.returncode, 1)
        self.assertIn('알 수 없는 인자: --vault', r.stderr)

    def test_missing_option_value_exits_nonzero(self):
        for argv in (['--src', self.src, '--plugins-dir'], ['--plugins-dir', self.plugins, '--src'],
                     ['--src', self.src, '--plugins-dir', self.plugins, '--id']):
            r = self.run_tool(*argv)
            self.assertNotEqual(r.returncode, 0, argv)
            self.assertEqual(os.listdir(self.plugins), [], argv)

    def test_missing_option_value_says_why(self):
        # BUG: obsidian-deploy.sh:29-31 `shift 2` 로 값 없는 마지막 옵션을 넘기면 shift 가 실패하고 set -e 로
        # 아무 메시지 없이 종료 1 한다. 사용자는 이유를 못 본다. 고치려면 각 값 옵션에서
        # `[ $# -ge 2 ] || die "$1 값이 필요합니다."` 를 먼저 검사한다 (vsix-install.sh --cli 처럼).
        r = self.run_tool('--src', self.src, '--plugins-dir')
        self.assertIn('오류', r.stderr)

    def test_plugins_dir_required(self):
        r = self.run_tool('--src', self.src)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--plugins-dir 이 필요합니다', r.stderr)

    def test_src_must_exist(self):
        r = self.run_tool('--src', os.path.join(self.tmp, 'nope'), '--plugins-dir', self.plugins)
        self.assertEqual(r.returncode, 1)
        self.assertIn('--src 경로가 없습니다', r.stderr)

    def test_missing_plugins_dir_is_not_created(self):
        wrong = os.path.join(self.home, 'other-vault', '.obsidian', 'plugins')
        r = self.run_tool('--src', self.src, '--plugins-dir', wrong)
        self.assertEqual(r.returncode, 1)
        self.assertIn('플러그인 디렉터리가 없습니다', r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, 'other-vault')))

    def test_manifest_and_main_required(self):
        os.remove(os.path.join(self.src, 'main.js'))
        r = self.deploy()
        self.assertEqual(r.returncode, 1)
        self.assertIn('main.js 가 없습니다', r.stderr)
        os.remove(os.path.join(self.src, 'manifest.json'))
        r = self.deploy()
        self.assertEqual(r.returncode, 1)
        self.assertIn('manifest.json 이 없습니다', r.stderr)
        self.assertEqual(os.listdir(self.plugins), [])

    def test_manifest_without_id(self):
        for manifest in ({'name': 'x'}, {'id': 5}, {'id': ''}, []):
            self.write(os.path.join(self.src, 'manifest.json'), json.dumps(manifest))
            r = self.deploy()
            self.assertNotEqual(r.returncode, 0, manifest)
            self.assertEqual(os.listdir(self.plugins), [], manifest)

    def test_broken_manifest_json(self):
        self.write(os.path.join(self.src, 'manifest.json'), '{broken')
        r = self.deploy()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('manifest.json 파싱 실패', r.stderr)
        r = self.deploy('--id', 'given')                           # --id 가 있어도 name 을 읽다가 멈춤
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(os.listdir(self.plugins), [])

    def test_unsafe_ids_refused(self):
        before = self.tree()
        for bad in ('../evil', 'a/b', '..', '.', 'a\\b', '/abs', '../../../../escape'):
            self.write(os.path.join(self.src, 'manifest.json'), json.dumps({**MANIFEST, 'id': bad}))
            r = self.deploy()
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn('폴더명으로 쓸 수 없는 값', r.stderr, bad)
            self.write(os.path.join(self.src, 'manifest.json'), json.dumps(MANIFEST))
            r = self.deploy('--id', bad)
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn('폴더명으로 쓸 수 없는 값', r.stderr, bad)
        self.assertEqual(self.tree(), before)                      # 아무 데도 안 썼다


class Deploy(Base):
    def test_dry_run_writes_nothing(self):
        r = self.deploy('--dry-run', '--hotreload')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('기존     : 없음 (새로 만듦)', r.stdout)
        for line in ('복사 예정: main.js', '복사 예정: manifest.json', '복사 예정: styles.css', '생성 예정: .hotreload'):
            self.assertIn(line, r.stdout)
        self.assertEqual(os.listdir(self.plugins), [])

    def test_first_deploy(self):
        r = self.deploy()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('플러그인 : My Plugin (my-plugin) v1.2.3', r.stdout)
        target = os.path.join(self.plugins, 'my-plugin')
        self.assertIn(f'완료: {target}', r.stdout)
        self.assertEqual(self.tree(target), {'main.js', 'manifest.json', 'styles.css'})
        self.assertEqual(self.read(os.path.join(target, 'main.js')), 'console.log("v2")')

    def test_styles_optional(self):
        os.remove(os.path.join(self.src, 'styles.css'))
        r = self.deploy()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.tree(os.path.join(self.plugins, 'my-plugin')), {'main.js', 'manifest.json'})

    def test_redeploy_preserves_data_and_unknown_files(self):
        target = os.path.join(self.plugins, 'my-plugin')
        self.write(os.path.join(target, 'manifest.json'), json.dumps({**MANIFEST, 'version': '1.0.0'}))
        self.write(os.path.join(target, 'main.js'), 'old')
        self.write(os.path.join(target, 'data.json'), '{"setting": 1}')
        self.write(os.path.join(target, 'extra.txt'), 'keep')
        r = self.deploy()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('기존     : My Plugin v1.0.0 (덮어씀)', r.stdout)
        self.assertIn('보존     : data.json', r.stdout)
        self.assertEqual(self.read(os.path.join(target, 'data.json')), '{"setting": 1}')
        self.assertEqual(self.read(os.path.join(target, 'extra.txt')), 'keep')
        self.assertEqual(self.read(os.path.join(target, 'main.js')), 'console.log("v2")')
        self.assertNotIn('경고', r.stderr)

    def test_idempotent(self):
        target = os.path.join(self.plugins, 'my-plugin')
        snapshot = lambda: {f: self.read(os.path.join(target, f)) for f in self.tree(target)}  # noqa: E731
        self.assertEqual(self.deploy().returncode, 0)
        first = snapshot()
        r = self.deploy()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('기존     : My Plugin v1.2.3 (덮어씀)', r.stdout)
        self.assertEqual(snapshot(), first)

    def test_name_mismatch_warns(self):
        target = os.path.join(self.plugins, 'my-plugin')
        self.write(os.path.join(target, 'manifest.json'), json.dumps({'id': 'my-plugin', 'name': 'Someone Else'}))
        r = self.deploy()
        self.assertEqual(r.returncode, 0)
        self.assertIn('플러그인 이름이 다릅니다 (Someone Else → My Plugin)', r.stderr)

    def test_existing_folder_without_manifest(self):
        os.makedirs(os.path.join(self.plugins, 'my-plugin'))
        r = self.deploy()
        self.assertEqual(r.returncode, 0)
        self.assertIn('폴더는 있으나 manifest.json 없음', r.stdout)

    def test_hotreload_and_id_override(self):
        r = self.deploy('--hotreload', '--id', 'dev-copy')
        self.assertEqual(r.returncode, 0, r.stderr)
        target = os.path.join(self.plugins, 'dev-copy')
        self.assertEqual(self.tree(target), {'main.js', 'manifest.json', 'styles.css', '.hotreload'})
        self.assertEqual(os.path.getsize(os.path.join(target, '.hotreload')), 0)
        self.assertFalse(os.path.exists(os.path.join(self.plugins, 'my-plugin')))

    def test_src_defaults_to_cwd(self):
        r = self.run_tool('--plugins-dir', self.plugins, cwd=self.src)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'소스     : {self.src}', r.stdout)

    def test_paths_with_spaces(self):
        vault = os.path.join(self.home, 'My Vault', '.obsidian', 'plugins')
        src = os.path.join(self.tmp, 'my repo')
        os.makedirs(vault)
        os.rename(self.src, src)
        r = self.run_tool('--src', src, '--plugins-dir', vault)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.tree(os.path.join(vault, 'my-plugin')), {'main.js', 'manifest.json', 'styles.css'})


if __name__ == '__main__':
    unittest.main()
