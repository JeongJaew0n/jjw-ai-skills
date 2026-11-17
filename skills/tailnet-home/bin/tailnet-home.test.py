#!/usr/bin/env python3
"""tailnet-home.py 시험. 모든 쓰기는 임시 폴더 안에서만 한다.

TAILNET_HOME_DIR·HOME 을 임시 폴더로 돌리고, 네트워크·tailscale·lsof 를 부르는 함수(fetch, tailscale_json,
listening_beside_loopback6)는 가짜로 바꾼다. 실제 홈 서버·tailscaled·~/my/Dev/home 은 건드리지 않는다.
하위 프로세스로 돌리는 경우는 거부 경로(네트워크 전에 멈춤)와, 닿지 않는 포트(1)·가짜 tailscale 로만 돌린다.

  python3 -I tailnet-home.test.py        exit 0 전부 기대대로, 1 아니면
"""
import contextlib
import fcntl
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.realpath(__file__))
TOOL = os.path.join(HERE, 'tailnet-home.py')

APPS = {'apps': [
    {'id': 'old', 'title': 'Old', 'summary': '', 'url': 'https://example.com/', 'group': 'lab'},
    {'id': 'static', 'title': 'Static', 'summary': '', 'root': '/nowhere', 'group': 'work'},
]}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='tailnet-home-test-')
        self.tmp = os.path.realpath(self._tmp.name)
        self.home = os.path.join(self.tmp, 'user')            # 가짜 HOME (TOO_WIDE 의 ~ 가 여기)
        self.hdir = os.path.join(self.tmp, 'homesrv')         # 가짜 TAILNET_HOME_DIR
        os.makedirs(os.path.join(self.home, 'my', 'Dev'))
        os.makedirs(self.hdir)
        self.apps_path = os.path.join(self.hdir, 'apps.json')
        self.write_json(self.apps_path, APPS)
        self.write_json(os.path.join(self.hdir, 'state.json'), {'disabled': ['off']})
        self.env = {'HOME': self.home, 'TAILNET_HOME_DIR': self.hdir, 'TAILNET_HOME_PORT': '1',
                    'TAILSCALE_SOCKET': os.path.join(self.tmp, 'no.sock'), 'TAILSCALE_PROXY': '[::1]:1'}
        self._env = mock.patch.dict(os.environ, self.env)
        self._env.start()
        spec = importlib.util.spec_from_file_location('tailnet_home_under_test', TOOL)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        # 네트워크·외부 명령 차단: 부르면 기록만 하고 "연결 실패" 를 돌려준다
        self.fetched = []
        self.answers = {}                                     # url → (status, body)

        def fake_fetch(url, proxy=None, timeout=4):
            self.fetched.append((url, proxy))
            return self.answers.get(url, (None, 'refused (test)'))
        self.m.fetch = fake_fetch
        self.m.tailscale_json = lambda: (None, 'no tailscale (test)')
        self.m.listening_beside_loopback6 = lambda port: []

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    # -- helpers
    @staticmethod
    def write_json(path, data):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def apps(self):
        with open(self.apps_path, encoding='utf-8') as f:
            return json.load(f)

    def app(self, app_id):
        return next((a for a in self.apps()['apps'] if a['id'] == app_id), None)

    def backups(self):
        d = os.path.join(self.hdir, 'backups')
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, 'argv', ['tailnet-home', *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = self.m.main()
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def make_site(self, name='site', files=None):
        root = os.path.join(self.tmp, 'sites', name)
        os.makedirs(root, exist_ok=True)
        for rel, body in {'index.html': '<!doctype html><title>x</title>', **(files or {})}.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(body)
        return root

    def serve_ok(self, app_id, index='<!doctype html><title>x</title>'):
        """가짜 fetch 가 로컬·tailnet 양쪽에서 200 을 주게 한다."""
        self.answers[f'http://localhost:1/apps/{app_id}/'] = (200, index)
        self.answers['http://localhost:1/api/status'] = (200, json.dumps({'tailscale': {'self': {'dns': 'mac.ts.net'}}}))
        self.answers[f'http://mac.ts.net/apps/{app_id}/'] = (200, index)

    def assertUnchanged(self):
        self.assertEqual(self.apps(), APPS)
        self.assertEqual(self.backups(), [])


class AddValidation(Base):
    def test_bad_ids_refused(self):
        for bad in ('Upper', 'under_score', 'trail-', '-lead', 'a--b', 'sp ace', '../x'):
            code, _, err = self.run_main('add', f'--id={bad}', '--title', 't', '--url', 'https://x')
            self.assertEqual(code, 1, bad)
            self.assertIn('kebab-case', err)
        self.assertUnchanged()

    def test_exactly_one_source(self):
        site = self.make_site()
        for extra in ([], ['--root', site, '--url', 'https://x'], ['--url', 'https://x', '--proxy', 'http://[::1]:5000'],
                      ['--root', site, '--url', 'https://x', '--proxy', 'http://[::1]:5000']):
            code, _, err = self.run_main('add', '--id', 'n', '--title', 't', *extra)
            self.assertEqual(code, 1, extra)
            self.assertIn('하나만', err)
        self.assertUnchanged()

    def test_service_needs_proxy(self):
        code, _, err = self.run_main('add', '--id', 'n', '--title', 't', '--url', 'https://x', '--service', 'com.jjw.x')
        self.assertEqual(code, 1)
        self.assertIn('--proxy 앱에만', err)
        self.assertUnchanged()

    def test_existing_needs_replace_then_yes(self):
        code, _, err = self.run_main('add', '--id', 'old', '--title', 'N', '--url', 'https://n')
        self.assertEqual(code, 1)
        self.assertIn('--replace', err)
        code, _, err = self.run_main('add', '--id', 'old', '--title', 'N', '--url', 'https://n', '--replace')
        self.assertEqual(code, 2)
        self.assertIn('--yes', err)
        self.assertUnchanged()

    def test_replace_with_yes_keeps_group_and_backs_up(self):
        code, out, _ = self.run_main('add', '--id', 'old', '--title', 'N', '--url', 'https://n', '--replace', '--yes')
        self.assertEqual(code, 0)
        self.assertIn('바꿈: old', out)
        a = self.app('old')
        self.assertEqual((a['title'], a['url'], a['group']), ('N', 'https://n', 'lab'))
        self.assertEqual(len(self.apps()['apps']), 2)
        self.assertEqual(self.app('static'), APPS['apps'][1])   # 다른 앱은 그대로
        [b] = self.backups()
        with open(os.path.join(self.hdir, 'backups', b), encoding='utf-8') as f:
            self.assertEqual(json.load(f), APPS)                    # 백업은 바꾸기 전 내용

    def test_replace_with_new_group(self):
        code, _, _ = self.run_main('add', '--id', 'old', '--title', 'N', '--url', 'https://n', '--replace', '--yes',
                                   '--group', 'study')
        self.assertEqual(code, 0)
        self.assertEqual(self.app('old')['group'], 'study')

    def test_bad_group_choice_is_usage_error(self):
        code, _, _ = self.run_main('add', '--id', 'n', '--title', 't', '--url', 'https://x', '--group', 'garage')
        self.assertEqual(code, 2)
        self.assertUnchanged()

    def test_missing_required_args(self):
        self.assertEqual(self.run_main('add', '--title', 't', '--url', 'https://x')[0], 2)
        self.assertEqual(self.run_main('add', '--id', 'n', '--url', 'https://x')[0], 2)
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main('deploy')[0], 2)
        self.assertUnchanged()


class AddUrl(Base):
    def test_url_must_be_http(self):
        for bad in ('ftp://x', 'javascript:alert(1)', 'example.com', '//x'):
            code, _, err = self.run_main('add', '--id', 'n', '--title', 't', '--url', bad)
            self.assertEqual(code, 1, bad)
            self.assertIn('http(s)://', err)
        self.assertUnchanged()

    def test_url_happy_path_no_network(self):
        code, out, _ = self.run_main('add', '--id', 'link', '--title', 'L', '--summary', 's', '--url', 'https://l',
                                     '--group', 'work')
        self.assertEqual(code, 0)
        self.assertIn('추가: link', out)
        self.assertEqual(self.app('link'), {'id': 'link', 'title': 'L', 'summary': 's', 'group': 'work', 'url': 'https://l'})
        self.assertEqual(self.fetched, [])                          # 링크형은 check 를 돌지 않는다
        self.assertEqual(len(self.backups()), 1)
        leftovers = [f for f in os.listdir(self.hdir) if f.startswith('.apps.') and f.endswith('.json')]
        self.assertEqual(leftovers, [])                             # 원자적 교체 임시 파일이 남지 않음

    def test_disabled_id_notice(self):
        code, out, _ = self.run_main('add', '--id', 'off', '--title', 'O', '--url', 'https://o')
        self.assertEqual(code, 0)
        self.assertIn('꺼진 기록', out)


class AddRoot(Base):
    def add_root(self, root, *extra, app_id='n'):
        return self.run_main('add', '--id', app_id, '--title', 't', '--root', root, *extra)

    def test_missing_folder(self):
        code, _, err = self.add_root(os.path.join(self.tmp, 'nope'))
        self.assertEqual(code, 1)
        self.assertIn('폴더가 없어', err)
        self.assertUnchanged()

    def test_too_wide_refused(self):
        for wide in ('/', self.home, os.path.join(self.home, 'my'), os.path.join(self.home, 'my', 'Dev'),
                     self.tmp, os.path.dirname(self.tmp)):
            # index.html 이 있어도 넓은 곳은 거부 (검사 순서: 넓이 → index.html)
            code, _, err = self.add_root(wide)
            self.assertEqual(code, 1, wide)
            self.assertIn('너무 넓어', err, wide)
        self.assertUnchanged()

    def test_too_wide_via_symlink_and_tilde(self):
        link = os.path.join(self.tmp, 'link-to-home')
        os.symlink(self.home, link)
        code, _, err = self.add_root(link)
        self.assertEqual(code, 1)
        self.assertIn('너무 넓어', err)
        code, _, err = self.add_root('~/my')
        self.assertEqual(code, 1)
        self.assertIn('너무 넓어', err)
        self.assertUnchanged()

    def test_project_under_dev_is_not_too_wide(self):
        root = os.path.join(self.home, 'my', 'Dev', 'proj', 'dist')
        os.makedirs(root)
        with open(os.path.join(root, 'index.html'), 'w') as f:
            f.write('x')
        self.serve_ok('n', 'x')
        code, _, err = self.add_root(root)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.app('n')['root'], root)

    def test_needs_index_html(self):
        root = os.path.join(self.tmp, 'empty')
        os.makedirs(root)
        code, _, err = self.add_root(root)
        self.assertEqual(code, 1)
        self.assertIn('index.html', err)
        self.assertUnchanged()

    def test_repo_root_refused_unless_allowed(self):
        root = self.make_site('repo')
        os.makedirs(os.path.join(root, '.git'))
        code, _, err = self.add_root(root)
        self.assertEqual(code, 1)
        self.assertIn('저장소 최상위', err)
        self.assertUnchanged()
        self.serve_ok('n')
        code, _, err = self.add_root(root, '--allow-repo-root')
        self.assertEqual(code, 0, err)

    def test_repo_root_refused_for_git_file(self):
        root = self.make_site('worktree', {'.git': 'gitdir: /elsewhere'})   # worktree·submodule 의 .git 파일
        code, _, err = self.add_root(root)
        self.assertEqual(code, 1)
        self.assertIn('저장소 최상위', err)

    def test_secret_files_refused(self):
        for rel in ('server.key', 'cert.PEM', 'sub/id_rsa', 'deep/a/id_ed25519.pub', 'secrets.yaml', 'Secrets.txt',
                    'client_secret_123.json', 'token.json', 'local.properties', 'GoogleService-Info.plist',
                    'google-services.json', 'credentials.csv', 'service-account-x.json', 'vault.kdbx'):
            root = self.make_site('s-' + rel.replace('/', '_'), {rel: 'secret'})
            code, _, err = self.add_root(root)
            self.assertEqual(code, 1, rel)
            self.assertIn('비밀일 수 있는 파일', err, rel)
            self.assertIn(rel, err, rel)
        self.assertUnchanged()

    def test_hidden_and_node_modules_not_scanned(self):
        # 서버가 숨기는 곳(점 폴더·node_modules)의 파일은 공개되지 않으니 거부 사유가 아니다
        root = self.make_site('hidden', {'.hide/server.key': 'k', 'node_modules/pkg/x.pem': 'k', '.npmrc': 'x',
                                          'app.js': 'x'})
        self.serve_ok('n')
        code, out, err = self.add_root(root)
        self.assertEqual(code, 0, err)
        self.assertIn('공개될 파일: 2개', out)                      # index.html, app.js

    def test_env_file_warns_but_allowed(self):
        root = self.make_site('envy', {'.env.local': 'A=1'})
        self.serve_ok('n')
        code, out, err = self.add_root(root)
        self.assertEqual(code, 0, err)
        self.assertIn('! .env.local', out)

    def test_scan_cap_refused(self):
        self.m.SCAN_LIMIT = 5
        root = self.make_site('big', {f'f{i}.txt': 'x' for i in range(5)})
        code, _, err = self.add_root(root)
        self.assertEqual(code, 1)
        self.assertIn('5개를 넘어', err)
        self.assertUnchanged()

    def test_scan_cap_real_limit_fast_path(self):
        count, _, _, _, capped = self.m.scan(self.make_site('small', {f'f{i}': 'x' for i in range(3)}))
        self.assertEqual((count, capped), (4, False))

    def test_happy_path_runs_check(self):
        root = self.make_site('ok', {'a.js': 'x'})
        self.serve_ok('n')
        code, out, err = self.add_root(root, '--group', 'study')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.app('n'), {'id': 'n', 'title': 't', 'summary': '', 'group': 'study', 'root': root})
        self.assertIn('추가: n', out)
        self.assertIn('결과: 열림', out)
        self.assertIn(('http://mac.ts.net/apps/n/', '[::1]:1'), self.fetched)   # tailnet 은 프록시 경유
        self.assertEqual(len(self.backups()), 1)

    def test_written_but_check_fails_exit_1(self):
        root = self.make_site('down')
        code, out, _ = self.add_root(root)                          # 가짜 fetch: 다 연결 실패
        self.assertEqual(code, 1)
        self.assertIsNotNone(self.app('n'))                         # 등록은 됐다
        self.assertIn('결과: 문제 있음', out)

    def test_check_warns_on_absolute_refs(self):
        root = self.make_site('abs')
        self.serve_ok('n', '<script src="/assets/a.js"></script><a href="//cdn/x">x</a><img src="./ok.png">')
        code, out, _ = self.add_root(root)
        self.assertEqual(code, 0)
        self.assertIn('/assets/a.js', out)
        self.assertNotIn('//cdn', out)
        self.assertNotIn('./ok.png', out)

    def test_thumb(self):
        root = self.make_site('thumb', {'img/t.png': 'png', '../outside.png': 'png'})
        self.serve_ok('n')
        code, _, err = self.add_root(root, '--thumb', 'img/t.png:1,2,30,40')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.app('n')['thumb'], {'image': 'img/t.png', 'x': 1, 'y': 2, 'w': 30, 'h': 40})
        for bad, msg in (('img/t.png', '형식'), ('img/t.png:1,2,3', '형식'), ('img/t.png:a,b,c,d', '형식'),
                         ('../outside.png:0,0,1,1', 'root 안에 없어'), ('nope.png:0,0,1,1', 'root 안에 없어'),
                         ('img:0,0,1,1', 'root 안에 없어')):
            code, _, err = self.add_root(root, '--thumb', bad, app_id='m')
            self.assertEqual(code, 1, bad)
            self.assertIn(msg, err, bad)
            self.assertIsNone(self.app('m'))


class AddProxy(Base):
    def test_check_proxy_accepts(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.m.check_proxy('http://[::1]:5173'), 'http://[::1]:5173')
            self.assertEqual(self.m.check_proxy('http://[::1]:5173/'), 'http://[::1]:5173')
        self.assertEqual(out.getvalue(), '')                        # ::1 은 경고 없음
        for url, want in (('http://127.0.0.1:5173/', 'http://127.0.0.1:5173'), ('http://localhost:80', 'http://localhost:80')):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(self.m.check_proxy(url), want)
            self.assertIn('127.0.0.1 에서 들으면', out.getvalue())

    def test_check_proxy_refuses(self):
        for bad in ('https://[::1]:5173', 'http://example.com:5173', 'http://192.168.0.2:5173', 'http://[::1]',
                    'http://[::1]:1', 'http://[::1]:1055', 'http://[::1]:5173/app', 'http://[::1]:5173/?a=1',
                    'http://[::1]:99999', 'http://[::1]:x', '[::1]:5173', 'http://0.0.0.0:5173'):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                self.m.check_proxy(bad)
            self.assertEqual(cm.exception.code, 1, bad)
            self.assertIn('--proxy 는', err.getvalue(), bad)

    def test_check_proxy_refuses_home_port(self):
        self.m.PORT = 8700
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.m.check_proxy('http://[::1]:8700')

    def test_proxy_add_and_service(self):
        plist_dir = os.path.join(self.home, 'Library', 'LaunchAgents')
        os.makedirs(plist_dir)
        open(os.path.join(plist_dir, 'com.jjw.my-app.plist'), 'w').close()
        self.serve_ok('p')
        code, out, err = self.run_main('add', '--id', 'p', '--title', 'P', '--proxy', 'http://[::1]:5173/',
                                       '--service', 'com.jjw.my-app')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.app('p')['proxy'], 'http://[::1]:5173')
        self.assertEqual(self.app('p')['service'], 'com.jjw.my-app')
        self.assertIn('앱 서버가 안 떠 있어', out)                  # 앱 서버 응답 없음 경고 (등록은 함)
        self.assertIn(('http://[::1]:5173/', None), self.fetched)

    def test_service_refusals(self):
        plist_dir = os.path.join(self.home, 'Library', 'LaunchAgents')
        os.makedirs(plist_dir)
        for label in ('com.jjw.home', 'com.jjw.tailscaled-userspace', 'com.jjw.taildrop-inbox'):
            open(os.path.join(plist_dir, label + '.plist'), 'w').close()
        for label, msg in (('com.jjw.home', '안 돼'), ('com.jjw.tailscaled-userspace', '안 돼'),
                           ('com.jjw.taildrop-inbox', '안 돼'), ('com.apple.x', '안 돼'), ('com.jjw.', '안 돼'),
                           ('com.jjw.UP', '안 돼'), ('com.jjw.a/../b', '안 돼'), ('com.jjw.missing', '가 없어')):
            code, _, err = self.run_main('add', '--id', 'p', '--title', 'P', '--proxy', 'http://[::1]:5173',
                                         '--service', label)
            self.assertEqual(code, 1, label)
            self.assertIn(msg, err, label)
        self.assertUnchanged()

    def test_proxy_check_flags_wide_listener(self):
        self.m.listening_beside_loopback6 = lambda port: ['127.0.0.1:5173'] if port == 5173 else []
        self.serve_ok('p')
        self.answers['http://[::1]:5173/'] = (200, 'ok')
        code, out, _ = self.run_main('add', '--id', 'p', '--title', 'P', '--proxy', 'http://[::1]:5173')
        self.assertEqual(code, 1)
        self.assertIn('127.0.0.1:5173 에서도 들어', out)
        self.assertIn('결과: 문제 있음', out)


class Remove(Base):
    def test_needs_yes(self):
        code, _, err = self.run_main('remove', 'old')
        self.assertEqual(code, 2)
        self.assertIn('--yes', err)
        self.assertUnchanged()

    def test_missing_id(self):
        code, _, err = self.run_main('remove', 'ghost', '--yes')
        self.assertEqual(code, 1)
        self.assertIn('ghost 가 없어', err)
        self.assertUnchanged()

    def test_remove(self):
        code, out, _ = self.run_main('remove', 'old', '--yes')
        self.assertEqual(code, 0)
        self.assertIn('제거: old', out)
        self.assertIsNone(self.app('old'))
        self.assertIsNotNone(self.app('static'))
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.run_main('remove', 'old', '--yes')[0], 1)   # 두 번째는 없음


class Group(Base):
    def test_set_and_idempotent(self):
        code, out, _ = self.run_main('group', 'old', 'study')
        self.assertEqual(code, 0)
        self.assertIn('연구실 → 학습실', out)
        self.assertEqual(self.app('old')['group'], 'study')
        self.assertEqual(len(self.backups()), 1)
        code, out, _ = self.run_main('group', 'old', 'study')
        self.assertEqual(code, 0)
        self.assertIn('바꾼 것 없음', out)
        self.assertEqual(len(self.backups()), 1)                    # 바뀐 게 없으면 백업도 쓰지 않음

    def test_none_removes_group(self):
        code, _, _ = self.run_main('group', 'old', 'none')
        self.assertEqual(code, 0)
        self.assertNotIn('group', self.app('old'))
        code, out, _ = self.run_main('group', 'old', 'none')
        self.assertIn('바꾼 것 없음', out)

    def test_missing_and_bad_choice(self):
        self.assertEqual(self.run_main('group', 'ghost', 'work')[0], 1)
        self.assertEqual(self.run_main('group', 'old', 'garage')[0], 2)
        self.assertUnchanged()

    def test_backups_pruned_to_keep(self):
        for i in range(self.m.KEEP_BACKUPS + 3):
            self.assertEqual(self.run_main('group', 'old', 'work' if i % 2 else 'study')[0], 0)
        self.assertEqual(len(self.backups()), self.m.KEEP_BACKUPS)


class Check(Base):
    def test_unknown_id(self):
        code, _, err = self.run_main('check', 'ghost')
        self.assertEqual(code, 1)
        self.assertIn('ghost 가 없어', err)

    def test_link_app_no_network(self):
        code, out, _ = self.run_main('check', 'old')
        self.assertEqual(code, 0)
        self.assertIn('링크형', out)
        self.assertEqual(self.fetched, [])

    def test_disabled_app_reported(self):
        apps = self.apps()
        apps['apps'].append({'id': 'off', 'title': 'Off', 'root': '/x'})
        self.write_json(self.apps_path, apps)
        self.serve_ok('off')
        code, out, _ = self.run_main('check', 'off')
        self.assertEqual(code, 1)
        self.assertIn('꺼져 있어', out)

    def test_broken_apps_json(self):
        with open(self.apps_path, 'w') as f:
            f.write('{not json')
        code, _, err = self.run_main('check', 'old')
        self.assertEqual(code, 1)
        self.assertIn('못 읽었어', err)


class Cli(Base):
    """실제 프로세스로 돌린다. 네트워크 전에 멈추는 경로, 또는 닿지 않는 포트 1 과 가짜 tailscale 만 쓴다."""
    def setUp(self):
        super().setUp()
        fake_bin = os.path.join(self.tmp, 'fakebin')
        os.makedirs(fake_bin)
        ts = os.path.join(fake_bin, 'tailscale')
        with open(ts, 'w') as f:
            f.write('#!/bin/sh\necho "fake tailscale: not running" >&2\nexit 1\n')
        os.chmod(ts, 0o755)
        self.penv = {**os.environ, **self.env, 'PATH': fake_bin + ':/usr/bin:/bin'}

    def cli(self, *argv, **kw):
        return subprocess.run([sys.executable, '-I', TOOL, *argv], capture_output=True, text=True, env=self.penv,
                              timeout=30, **kw)

    def test_missing_apps_json(self):
        os.remove(self.apps_path)
        r = self.cli('remove', 'old', '--yes')
        self.assertEqual(r.returncode, 1)
        self.assertIn('apps.json 이 없어', r.stderr)

    def test_exit_codes(self):
        self.assertEqual(self.cli('remove', 'old').returncode, 2)
        self.assertEqual(self.cli('add', '--id', 'X', '--title', 't', '--url', 'https://x').returncode, 1)
        self.assertEqual(self.cli('add', '--id', 'old', '--title', 't', '--url', 'https://x', '--replace').returncode, 2)
        self.assertEqual(self.cli('--help').returncode, 0)
        self.assertUnchanged()

    def test_status_unreachable_is_clean_error(self):
        r = self.cli('status')
        self.assertEqual(r.returncode, 1)
        self.assertIn('홈 서버: 응답 없음', r.stdout)
        self.assertIn('Tailscale: 연결 실패', r.stdout)
        self.assertNotIn('Traceback', r.stderr)

    def test_lock_serialises_writers(self):
        lock = open(os.path.join(self.hdir, '.apps.json.lock'), 'w')
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            p = subprocess.Popen([sys.executable, '-I', TOOL, 'remove', 'old', '--yes'], env=self.penv,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.8)
            self.assertIsNone(p.poll(), '잠금을 쥐고 있는 동안 remove 가 끝나 버렸다')
            self.assertIsNotNone(self.app('old'))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        out, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertIsNone(self.app('old'))


if __name__ == '__main__':
    unittest.main()
