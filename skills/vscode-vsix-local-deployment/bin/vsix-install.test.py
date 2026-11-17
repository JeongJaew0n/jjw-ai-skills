#!/usr/bin/env python3
"""vsix-install.sh 시험. VS Code CLI 는 PATH 맨 앞의 가짜 `code`(인자를 기록하고 정해 둔 버전·설치 목록을 돌려줌)로
바꾸고, 확장 저장소·VSIX·HOME·TMPDIR 은 전부 임시 폴더에 만든다. 실제 VS Code 는 부르지 않는다.

/Applications 의 실제 VS Code 로 넘어가는 경로(PATH 에 code 가 없고 --cli 도 없음)는 그 앱이 없을 때만 시험한다.

  python3 -I vsix-install.test.py        exit 0 전부 기대대로, 1 아니면
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'vsix-install.sh')
NODE = shutil.which('node')
REAL_APP_CLI = '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
PKG = {'publisher': 'Pub', 'name': 'ext', 'version': '1.2.3', 'engines': {'vscode': '^1.90.0'}}
FAKE_CODE = r'''#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_LOG"
case "$1" in
  --version) printf '%s\nabc123\narm64\n' "$FAKE_VERSION" ;;
  --install-extension) [ -z "${FAKE_INSTALL_FAIL:-}" ] || exit 7; printf '%s\n' "$FAKE_LIST_AFTER" > "$FAKE_STATE" ;;
  --list-extensions) cat "$FAKE_STATE" 2>/dev/null ;;
esac
'''


@unittest.skipUnless(NODE, 'node 가 없음')
class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='vsix-install-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, 'home')
        self.repo = os.path.join(self.tmp, 'repo')
        self.fakebin = os.path.join(self.tmp, 'fakebin')
        self.tmpdir = os.path.join(self.tmp, 't')
        self.log = os.path.join(self.tmp, 'code.log')
        for d in (self.home, self.repo, self.fakebin, self.tmpdir):
            os.makedirs(d)
        self.code = os.path.join(self.fakebin, 'code')
        with open(self.code, 'w') as f:
            f.write(FAKE_CODE)
        os.chmod(self.code, 0o755)
        self.write_json(os.path.join(self.repo, 'package.json'), PKG)
        self.env = {
            'HOME': self.home, 'TMPDIR': self.tmpdir, 'LANG': 'en_US.UTF-8',
            'PATH': f'{self.fakebin}:{os.path.dirname(NODE)}:/usr/bin:/bin',
            'FAKE_LOG': self.log, 'FAKE_STATE': os.path.join(self.tmp, 'installed.txt'),
            'FAKE_VERSION': '1.95.0', 'FAKE_LIST_AFTER': 'other.thing@0.1.0\nPub.ext@1.2.3',
        }

    def tearDown(self):
        self.assertEqual(os.listdir(self.tmpdir), [], 'mktemp 파일이 남았다')
        self._tmp.cleanup()

    @staticmethod
    def write_json(path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def vsix(self, path, manifest=PKG):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with zipfile.ZipFile(path, 'w') as z:
            if manifest is not None:
                z.writestr('extension/package.json', manifest if isinstance(manifest, str) else json.dumps(manifest))
            z.writestr('extension.vsixmanifest', '<x/>')
        return path

    def run_tool(self, *argv, cwd=None, **env):
        e = {**self.env, **env}
        e = {k: v for k, v in e.items() if v is not None}
        return subprocess.run(['/bin/sh', TOOL, *argv], capture_output=True, text=True, errors='replace', env=e,
                              cwd=cwd or self.tmp, timeout=60)

    def calls(self):
        try:
            with open(self.log) as f:
                return f.read().splitlines()
        except FileNotFoundError:
            return []

    def installs(self):
        return [c for c in self.calls() if c.startswith('--install-extension')]


class Arguments(Base):
    def test_help(self):
        r = self.run_tool('--help')
        self.assertEqual(r.returncode, 0)
        self.assertIn('Usage: vsix-install.sh', r.stdout)
        self.assertEqual(self.run_tool('-h').returncode, 0)

    def test_usage_errors_exit_2(self):
        for argv, msg in ((['--bogus'], '알 수 없는 옵션'), (['--cli'], '--cli 값이 필요'), (['a', 'b'], '하나만'),
                          (['--build'], '알 수 없는 옵션')):
            r = self.run_tool(*argv)
            self.assertEqual(r.returncode, 2, argv)
            self.assertIn(msg, r.stderr, argv)
        self.assertEqual(self.calls(), [])

    def test_cli_not_found(self):
        r = self.run_tool(self.repo, '--cli', 'no-such-code-cli')
        self.assertEqual(r.returncode, 1)
        self.assertIn('PATH에서 찾지 못했습니다', r.stderr)
        notexec = os.path.join(self.tmp, 'notexec')
        open(notexec, 'w').close()
        r = self.run_tool(self.repo, '--cli', notexec)
        self.assertEqual(r.returncode, 1)
        self.assertIn('실행할 수 없는 VS Code CLI', r.stderr)
        self.assertEqual(self.calls(), [])

    @unittest.skipIf(os.path.exists(REAL_APP_CLI), '실제 VS Code 앱이 있어 기본 탐색이 그 앱으로 간다')
    def test_no_cli_anywhere(self):
        os.remove(self.code)
        r = self.run_tool(self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn('CLI를 찾지 못했습니다', r.stderr)

    def test_cli_by_name_and_path(self):
        self.vsix(os.path.join(self.repo, 'artifacts', 'ext-1.2.3.vsix'))
        alt = os.path.join(self.fakebin, 'code-insiders')
        shutil.copy(self.code, alt)
        r = self.run_tool(self.repo, '--cli', 'code-insiders', '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'CLI:   {alt} (VS Code 1.95.0)', r.stdout)
        r = self.run_tool(self.repo, '--cli', alt, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)


class Targets(Base):
    def test_missing_target(self):
        r = self.run_tool(os.path.join(self.tmp, 'nope'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('대상을 찾을 수 없습니다', r.stderr)

    def test_file_must_be_vsix(self):
        zip_path = self.vsix(os.path.join(self.tmp, 'ext.zip'))
        r = self.run_tool(zip_path)
        self.assertEqual(r.returncode, 1)
        self.assertIn('VSIX 파일이 아닙니다', r.stderr)

    def test_repo_needs_extension_package_json(self):
        empty = os.path.join(self.tmp, 'empty')
        os.makedirs(empty)
        r = self.run_tool(empty)
        self.assertEqual(r.returncode, 1)
        self.assertIn('package.json을 찾지 못했습니다', r.stderr)
        for pkg in ({'name': 'ext', 'version': '1.0.0', 'engines': {'vscode': '^1.0.0'}},      # publisher 없음
                    {'publisher': 'p', 'name': 'ext', 'version': '1.0.0'},                      # engines 없음
                    {'publisher': 'p', 'name': 'ext', 'version': '1.0.0', 'engines': {'node': '20'}},
                    '{broken'):
            self.write_json(os.path.join(self.repo, 'package.json'), pkg)
            r = self.run_tool(self.repo)
            self.assertEqual(r.returncode, 1, pkg)
            self.assertIn('VS Code 확장 package.json이 필요합니다', r.stderr, pkg)
        self.assertEqual(self.installs(), [])

    def test_repo_without_vsix(self):
        r = self.run_tool(self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn('설치할 VSIX가 없습니다', r.stderr)

    def test_expected_artifact_wins_over_others(self):
        want = self.vsix(os.path.join(self.repo, 'artifacts', 'ext-1.2.3.vsix'))
        self.vsix(os.path.join(self.repo, 'artifacts', 'ext-1.2.2.vsix'))
        self.vsix(os.path.join(self.repo, 'ext-0.1.0.vsix'))
        r = self.run_tool(self.repo, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'VSIX:  {want}', r.stdout)

    def test_several_candidates_refused(self):
        self.vsix(os.path.join(self.repo, 'artifacts', 'ext-1.2.2.vsix'))
        self.vsix(os.path.join(self.repo, 'ext-0.1.0.vsix'))
        r = self.run_tool(self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn('VSIX가 여러 개입니다', r.stderr)
        self.assertEqual(self.installs(), [])

    def test_single_other_candidate_used(self):
        only = self.vsix(os.path.join(self.repo, 'ext-0.9.0.vsix'))
        r = self.run_tool(self.repo, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f'VSIX:  {only}', r.stdout)

    def test_repo_defaults_to_cwd(self):
        self.vsix(os.path.join(self.repo, 'artifacts', 'ext-1.2.3.vsix'))
        r = self.run_tool('--dry-run', cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_relative_vsix_path_made_absolute(self):
        path = self.vsix(os.path.join(self.tmp, 'dl', 'ext.vsix'))
        r = self.run_tool('dl/ext.vsix')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.installs(), [f'--install-extension {path} --force'])


class Manifest(Base):
    def test_vsix_without_manifest(self):
        path = self.vsix(os.path.join(self.tmp, 'bad.vsix'), manifest=None)
        r = self.run_tool(path)
        self.assertEqual(r.returncode, 1)
        self.assertIn('extension/package.json을 읽지 못했습니다', r.stderr)
        notzip = os.path.join(self.tmp, 'notzip.vsix')
        with open(notzip, 'w') as f:
            f.write('not a zip')
        r = self.run_tool(notzip)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.installs(), [])

    def test_vsix_manifest_fields(self):
        for m in ({'name': 'x', 'version': '1', 'engines': {'vscode': '^1.0.0'}}, '{broken', '[]'):
            path = self.vsix(os.path.join(self.tmp, 'm.vsix'), manifest=m)
            r = self.run_tool(path)
            self.assertEqual(r.returncode, 1, m)
            self.assertIn('VSIX manifest에 publisher', r.stderr, m)
        self.assertEqual(self.installs(), [])

    def test_unreadable_cli_version(self):
        path = self.vsix(os.path.join(self.tmp, 'e.vsix'))
        r = self.run_tool(path, FAKE_VERSION='insiders')
        self.assertEqual(r.returncode, 1)
        self.assertIn('VS Code CLI 버전을 확인하지 못했습니다', r.stderr)
        self.assertEqual(self.installs(), [])

    def test_engine_compatibility(self):
        cases = (('^1.90.0', '1.95.0', 0), ('^1.95.0', '1.95.0', 0), ('^1.96.0', '1.95.0', 1), ('^2.0.0', '3.0.0', 1),
                 ('>=1.80.0', '1.95.0', 0), ('>= 1.99.0', '1.95.0', 1), ('>=1.0.0', '2.0.0', 0), ('*', '1.0.0', 0),
                 ('~1.99.0', '1.95.0', 0), ('1.96.0', '1.95.0', 1), ('1.95.1', '1.95.10', 0))
        for rng, have, want in cases:
            path = self.vsix(os.path.join(self.tmp, 'e.vsix'), {**PKG, 'engines': {'vscode': rng}})
            r = self.run_tool(path, '--dry-run', FAKE_VERSION=have)
            self.assertEqual(r.returncode, want, (rng, have, r.stderr))
            if want:
                self.assertIn('낮거나 호환되지 않습니다', r.stderr)
        self.assertEqual(self.installs(), [])


class Install(Base):
    def setUp(self):
        super().setUp()
        self.path = self.vsix(os.path.join(self.repo, 'artifacts', 'ext-1.2.3.vsix'))

    def test_dry_run_does_not_install(self):
        r = self.run_tool(self.repo, '--dry-run')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('확장:  Pub.ext@1.2.3', r.stdout)
        self.assertIn('요구:  VS Code ^1.90.0', r.stdout)
        self.assertIn('dry-run: 설치하지 않았습니다.', r.stdout)
        self.assertEqual(self.calls(), ['--version'])

    def test_install_and_verify(self):
        r = self.run_tool(self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), ['--version', f'--install-extension {self.path} --force',
                                        '--list-extensions --show-versions'])
        self.assertIn('설치 검증 완료: Pub.ext@1.2.3', r.stdout)

    def test_verify_is_case_insensitive_and_idempotent(self):
        for _ in range(2):
            r = self.run_tool(self.repo, FAKE_LIST_AFTER='pub.ext@1.2.3')
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.installs()), 2)

    def test_verify_fails_when_not_listed(self):
        for listed in ('Pub.ext@1.2.2', 'Pub.ext', 'Pub.ext@1.2.3.4', 'x.Pub.ext@1.2.3', ''):
            r = self.run_tool(self.repo, FAKE_LIST_AFTER=listed)
            self.assertEqual(r.returncode, 1, listed)
            self.assertNotIn('설치 검증 완료', r.stdout, listed)

    def test_not_listed_message_names_version(self):
        # BUG: vsix-install.sh:197 `$EXTENSION_VERSION을` — macOS /bin/sh(bash 3.2)는 UTF-8 로캘에서 '을' 의 첫 바이트를
        # 변수 이름에 붙여 읽는다. set -u 라 안내문 대신 "line 197: EXTENSION_VERSION\xec: unbound variable" 로 죽는다
        # (종료 1 은 맞지만 이유가 안 보인다. C 로캘이면 멀쩡하다). 고치려면 `${EXTENSION_VERSION}을`.
        r = self.run_tool(self.repo, FAKE_LIST_AFTER='', LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8')
        self.assertEqual(r.returncode, 1)
        self.assertIn('설치 목록에서 Pub.ext@1.2.3을 확인하지 못했습니다', r.stderr)

    def test_install_failure_stops(self):
        r = self.run_tool(self.repo, FAKE_INSTALL_FAIL='1')
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn('--list-extensions --show-versions', self.calls())
        self.assertNotIn('설치 검증 완료', r.stdout)

    def test_vsix_target_without_node(self):
        r = self.run_tool(self.path, PATH=f'{self.fakebin}:/usr/bin:/bin')
        self.assertEqual(r.returncode, 1)
        self.assertIn('Node.js가 필요합니다', r.stderr)
        self.assertEqual(self.installs(), [])

    def test_repo_target_without_node_says_node(self):
        # BUG: vsix-install.sh:93 이 저장소 대상의 package.json 을 `node -e` 로 읽는데, node 가 있는지는 그 뒤
        # 129행에서야 본다. node 가 없으면 "publisher, name, version, engines.vscode가 있는 ... package.json이
        # 필요합니다" 라는 엉뚱한 이유로 멈춘다. 고치려면 129행의 node 검사를 resolve_cli 직후(83행 앞)로 올린다.
        r = self.run_tool(self.repo, '--dry-run', PATH=f'{self.fakebin}:/usr/bin:/bin')
        self.assertIn('Node.js가 필요합니다', r.stderr)

    @unittest.expectedFailure
    def test_broken_node_options(self):
        # BUG: vsix-install.sh:93,139,159 가 `node -e` 를 NODE_OPTIONS 를 물려받은 채 부른다. NODE_OPTIONS 가 깨져 있으면
        # (예: --require 대상이 tmp 청소로 사라짐 — 이 맥에서 실제로 있는 일) 첫 node 가 MODULE_NOT_FOUND 로 죽고,
        # 스크립트는 "package.json이 필요합니다" 라는 엉뚱한 이유로 멈춘다. hud 런처가 이미 같은 이유로
        # `env -u NODE_OPTIONS node` 를 쓴다. 고치려면 스크립트 앞쪽에서 `unset NODE_OPTIONS`.
        r = self.run_tool(self.repo, '--dry-run', NODE_OPTIONS=f'--require {self.tmp}/gone.cjs')
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main()
