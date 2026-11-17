#!/usr/bin/env python3
"""scan-sources.py 시험. 스크립트를 임시 폴더의 가짜 스킬(bin/ + references/)에 복사해 돌리고, HOME 도 임시 폴더로
돌려 가짜 ~/my/Dev 프로젝트를 훑게 한다. 실제 references/ 와 ~/my/Dev 는 보지 않는다.

  python3 -I scan-sources.test.py        exit 0 전부 기대대로, 1 아니면
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'scan-sources.py')
PLUGIN = {'id': 'p', 'name': 'P', 'version': '1.0.0', 'minAppVersion': '1.0.0'}


class Scan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='scan-sources-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, 'home')
        self.dev = os.path.join(self.home, 'my', 'Dev')
        self.refs = os.path.join(self.tmp, 'skill', 'references')
        self.tool = os.path.join(self.tmp, 'skill', 'bin', 'scan-sources.py')
        os.makedirs(self.refs)
        os.makedirs(os.path.dirname(self.tool))
        shutil.copy(TOOL, self.tool)

    def tearDown(self):
        self._tmp.cleanup()

    @staticmethod
    def write(path, body):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body if isinstance(body, str) else json.dumps(body))

    def project(self, name, manifest=PLUGIN, reusable=None, specific=None, troubleshootings=True):
        root = os.path.join(self.dev, name)
        os.makedirs(root)
        if manifest is not None:
            self.write(os.path.join(root, 'manifest.json'), manifest)
        if troubleshootings:
            base = os.path.join(root, 'docs', 'troubleshootings')
            os.makedirs(os.path.join(base, 'reusable'))
            for f, body in (reusable or {}).items():
                self.write(os.path.join(base, 'reusable', f), body)
            for f, body in (specific or {}).items():
                self.write(os.path.join(base, 'project-specific', f), body)
        return root

    def run_tool(self, tool=None):
        env = {'HOME': self.home, 'PATH': '/usr/bin:/bin'}
        return subprocess.run([sys.executable, '-I', tool or self.tool], capture_output=True, text=True, env=env,
                              cwd=self.tmp, timeout=30)

    def test_no_dev_dir(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 3)
        self.assertIn('가 없습니다', r.stderr)

    def test_real_script_without_dev_dir(self):
        r = self.run_tool(TOOL)                                  # 실제 위치 그대로: ~/my/Dev 가 없으면 바로 3
        self.assertEqual(r.returncode, 3)

    def test_no_plugin_projects(self):
        os.makedirs(self.dev)
        self.project('chrome-ext', manifest={'manifest_version': 3, 'minAppVersion': 'x'})
        self.project('no-manifest', manifest=None)
        r = self.run_tool()
        self.assertEqual(r.returncode, 0)
        self.assertIn('Obsidian 플러그인 프로젝트를 찾지 못했습니다', r.stdout)

    def test_classifies_documents(self):
        self.write(os.path.join(self.refs, 'same.md'), '> 출처: a/same.md\n> 원본이 정본이다\n\n# Same\nbody\n')
        self.write(os.path.join(self.refs, 'old.md'), '# Old\nold body\n')
        self.write(os.path.join(self.refs, 'README.md'), 'index')
        self.project('plugin-a', reusable={'same.md': '# Same\nbody\n', 'old.md': '# Old\nnew body\n',
                                           'fresh.md': 'intro\n# Fresh doc\n', 'README.md': 'ignored'},
                     specific={'local.md': '# Local only\n', 'README.md': 'ignored'})
        self.project('plugin-b', reusable={'untitled.md': 'no heading'})
        self.project('chrome-ext', manifest={'manifest_version': 3})
        self.project('broken', manifest='{not json')
        self.project('no-docs', troubleshootings=False)            # docs/troubleshootings 없으면 후보도 아님
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn('Obsidian 플러그인 프로젝트 2개: plugin-a, plugin-b', out)
        self.assertIn('제외 2개 (Obsidian 플러그인 아님): broken, chrome-ext', out)
        self.assertNotIn('no-docs', out)
        self.assertIn('references/ 에 없는 reusable 문서 2개', out)
        self.assertIn('plugin-a/fresh.md\n    Fresh doc', out)
        self.assertIn('plugin-b/untitled.md\n    (제목 없음)', out)
        self.assertIn('원본이 바뀐 문서 1개', out)
        self.assertIn('plugin-a/old.md', out)
        self.assertIn('일치 1개', out)
        self.assertIn('project-specific 1개', out)
        self.assertIn('plugin-a/local.md  — Local only', out)
        self.assertNotIn('README', out)

    def test_all_up_to_date_and_read_only(self):
        self.write(os.path.join(self.refs, 'a.md'), '# A\nx\n')
        self.project('plugin', reusable={'a.md': '# A\nx\n'})
        before = {f: os.stat(os.path.join(self.refs, f)).st_mtime_ns for f in os.listdir(self.refs)}
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('reusable 문서는 모두 최신', r.stdout)
        self.assertIn('일치 1개', r.stdout)
        self.assertEqual({f: os.stat(os.path.join(self.refs, f)).st_mtime_ns for f in os.listdir(self.refs)}, before)
        self.assertEqual(sorted(os.listdir(os.path.join(self.dev, 'plugin', 'docs', 'troubleshootings', 'reusable'))),
                         ['a.md'])

    def test_idempotent(self):
        self.project('plugin', reusable={'n.md': '# N\n'})
        self.assertEqual(self.run_tool().stdout, self.run_tool().stdout)

    def test_non_object_manifest_is_skipped(self):
        # BUG: scan-sources.py:46 `"minAppVersion" in j` — manifest.json 이 숫자·null 이면 TypeError 로 전체 스캔이
        # 죽는다(파싱 실패만 except 로 잡는다). 문자열이면 부분 문자열 검사가 된다. 고치려면
        # `return isinstance(j, dict) and "minAppVersion" in j and "manifest_version" not in j`.
        self.project('plugin', reusable={'n.md': '# N\n'})
        self.project('weird', manifest='null')
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('제외 1개', r.stdout)


if __name__ == '__main__':
    unittest.main()
