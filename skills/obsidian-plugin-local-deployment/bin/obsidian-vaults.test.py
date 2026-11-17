#!/usr/bin/env python3
"""obsidian-vaults.sh 시험. HOME·APPDATA 를 임시 폴더로 돌리고 그 안에 가짜 obsidian.json 과 vault 를 만든다.
스크립트는 읽기만 하고, 실제 Obsidian 설정·vault 는 보지 않는다.

  python3 -I obsidian-vaults.test.py        exit 0 전부 기대대로, 1 아니면
"""
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'obsidian-vaults.sh')
MAC = ('Library', 'Application Support', 'obsidian', 'obsidian.json')
LINUX = ('.config', 'obsidian', 'obsidian.json')
FLATPAK = ('.var', 'app', 'md.obsidian.Obsidian', 'config', 'obsidian.json')


class Vaults(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='obsidian-vaults-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, 'home')
        os.makedirs(self.home)

    def tearDown(self):
        self._tmp.cleanup()

    def config(self, parts, data, root=None):
        path = os.path.join(root or self.home, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def vault(self, name, plugins=True):
        v = os.path.join(self.tmp, 'vaults', name)
        os.makedirs(os.path.join(v, '.obsidian', 'plugins') if plugins else v, exist_ok=True)
        return v

    def run_tool(self, **env):
        e = {'HOME': self.home, 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', **env}
        return subprocess.run(['/bin/sh', TOOL], capture_output=True, text=True, env=e, cwd=self.tmp, timeout=30)

    @staticmethod
    def read(path):
        with open(path, encoding='utf-8') as f:
            return f.read()

    def rows(self, r):
        return [line.split('\t') for line in r.stdout.splitlines()]

    def test_no_config(self):
        r = self.run_tool()
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, '')
        self.assertIn('obsidian.json 을 찾지 못했습니다', r.stderr)

    def test_lists_existing_vaults_sorted(self):
        b = self.vault('b vault', plugins=False)
        a = self.vault('a')
        self.config(MAC, {'vaults': {
            '1': {'path': b, 'ts': 1, 'open': True},
            '2': {'path': a},
            '3': {'path': os.path.join(self.tmp, 'vaults', 'gone')},   # 지운 vault 는 빠짐
            '4': 'not a dict', '5': {}, '6': {'path': ''},
        }})
        r = self.run_tool()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows(r), [
            [a, os.path.join(a, '.obsidian', 'plugins'), 'yes'],
            [b, os.path.join(b, '.obsidian', 'plugins'), 'no'],
        ])

    def test_mac_config_wins_over_linux(self):
        mac_v, linux_v = self.vault('mac'), self.vault('linux')
        self.config(LINUX, {'vaults': {'x': {'path': linux_v}}})
        self.config(MAC, {'vaults': {'x': {'path': mac_v}}})
        r = self.run_tool()
        self.assertEqual([row[0] for row in self.rows(r)], [mac_v])

    def test_other_locations(self):
        v = self.vault('v')
        for parts in (LINUX, FLATPAK):
            path = self.config(parts, {'vaults': {'x': {'path': v}}})
            r = self.run_tool()
            self.assertEqual(r.returncode, 0, (parts, r.stderr))
            self.assertEqual(self.rows(r)[0][0], v, parts)
            os.remove(path)
        appdata = os.path.join(self.tmp, 'appdata')
        self.config(('obsidian', 'obsidian.json'), {'vaults': {'x': {'path': v}}}, root=appdata)
        r = self.run_tool(APPDATA=appdata)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.rows(r)[0][0], v)

    def test_broken_or_empty_config(self):
        for data, msg in (('{broken', '읽지 못했습니다'), ({'other': 1}, 'vaults 항목이 없습니다'),
                          ({'vaults': []}, 'vaults 항목이 없습니다'),
                          ({'vaults': {'x': {'path': '/definitely/not/here'}}}, '실제로 존재하는 것이 없습니다'),
                          ({'vaults': {}}, '실제로 존재하는 것이 없습니다')):
            self.config(MAC, data)
            r = self.run_tool()
            self.assertEqual(r.returncode, 1, data)
            self.assertEqual(r.stdout, '', data)
            self.assertIn(msg, r.stderr, data)

    def test_top_level_not_object(self):
        # BUG: obsidian-vaults.sh:59 `data.get("vaults")` — obsidian.json 최상위가 객체가 아니면(예: [] 나 null)
        # AttributeError 트레이스백으로 죽는다. 종료 코드는 1 이라 동작은 맞지만 메시지가 "vaults 항목이 없습니다" 가
        # 아니다. 고치려면 `vaults = data.get("vaults") if isinstance(data, dict) else None`.
        self.config(MAC, [])
        r = self.run_tool()
        self.assertEqual(r.returncode, 1)
        self.assertNotIn('Traceback', r.stderr)

    def test_read_only(self):
        v = self.vault('v', plugins=False)
        path = self.config(MAC, {'vaults': {'x': {'path': v}}})
        before = os.stat(path).st_mtime_ns, self.read(path)
        self.run_tool()
        self.assertEqual((os.stat(path).st_mtime_ns, self.read(path)), before)
        self.assertFalse(os.path.exists(os.path.join(v, '.obsidian')))   # plugins 폴더를 만들지 않음


if __name__ == '__main__':
    unittest.main()
