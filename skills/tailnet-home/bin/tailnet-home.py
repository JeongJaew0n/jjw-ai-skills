#!/usr/bin/env python3
"""tailnet-home — 이 맥의 Tailscale·홈 서버 상태를 보고, 정적 웹앱을 홈 서버에 올린다.

전제: tailscaled 가 sudo 없이 userspace 로 돌고, 홈 서버가 tailscale serve 뒤에서
`/apps/<id>/` 로 정적 폴더를 나눠 준다. 홈 서버는 요청마다 apps.json 을 읽는다.

  status   Tailscale·serve·앱 상태 (변경 없음)
  check    앱 하나가 로컬과 tailnet 양쪽에서 열리는지 (변경 없음)
  add      apps.json 에 앱 추가 (백업 → 원자적 교체 → JSON 검증 → check)
  remove   apps.json 에서 앱 제거 (백업 → 원자적 교체 → JSON 검증)

tailscale 명령 중계는 일부러 두지 않았다. 필요한 상태는 status 가 다 보여 준다.
"""

import argparse
import datetime
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# 이 맥의 구성. 바뀌면 환경변수로 덮어쓴다.
HOME_DIR = os.path.expanduser(os.environ.get('TAILNET_HOME_DIR', '~/my/Dev/home'))
PORT = int(os.environ.get('TAILNET_HOME_PORT', '8700'))
SOCKET = os.path.expanduser(os.environ.get('TAILSCALE_SOCKET', '~/.local/share/tailscale/tailscaled.sock'))
PROXY = os.environ.get('TAILSCALE_PROXY', '127.0.0.1:1055')

APPS = os.path.join(HOME_DIR, 'apps.json')
STATE = os.path.join(HOME_DIR, 'state.json')
BACKUPS = os.path.join(HOME_DIR, 'backups')
KEEP_BACKUPS = 10
LOCAL = f'http://127.0.0.1:{PORT}'

# root 로 등록하면 너무 넓게 공개되는 곳 (같거나 그 조상이면 거부)
TOO_WIDE = ['/', '~', '~/my', '~/my/Dev']
DENY_FILES = ['*.key', '*.pem', '*.p12', 'id_rsa*', 'id_ed25519*', 'secrets*', 'credentials*']
WARN_FILES = ['.env*']
SCAN_LIMIT = 20000


def fail(msg, code=1):
    print(f'오류: {msg}', file=sys.stderr)
    sys.exit(code)


def fetch(url, proxy=None, timeout=4):
    """(status, body). 연결 실패면 (None, 이유)."""
    handlers = [urllib.request.ProxyHandler({'http': f'http://{proxy}'} if proxy else {})]
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(url, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception as e:  # noqa: BLE001 — 연결 실패 이유를 그대로 보여 준다
        return None, str(e)


def tailscale_json():
    exe = shutil.which('tailscale') or '/opt/homebrew/bin/tailscale'
    try:
        out = subprocess.run([exe, f'--socket={SOCKET}', 'status', '--json'],
                             capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if out.returncode != 0:
        return None, out.stderr.strip()
    return json.loads(out.stdout), None


def self_dns():
    """이 맥의 tailnet DNS 이름. 홈 서버 → tailscale CLI 순으로 묻는다."""
    code, body = fetch(f'{LOCAL}/api/status')
    if code == 200:
        dns = json.loads(body).get('tailscale', {}).get('self', {}).get('dns')
        if dns:
            return dns
    data, _ = tailscale_json()
    if data:
        return data.get('Self', {}).get('DNSName', '').rstrip('.') or None
    return None


def load_apps():
    with open(APPS, encoding='utf-8') as f:
        return json.load(f)


def disabled_ids():
    try:
        with open(STATE, encoding='utf-8') as f:
            return set(json.load(f).get('disabled', []))
    except (OSError, ValueError):
        return set()


def days_left(iso):
    try:
        t = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
    if t.year < 2000:
        return None
    return (t - datetime.datetime.now(datetime.timezone.utc)).days


# ---------------------------------------------------------------- status

def cmd_status(args):
    code, body = fetch(f'{LOCAL}/api/status')
    if code != 200:
        print(f'홈 서버: 응답 없음 ({LOCAL}, {code or body})')
        print('  방금 로그인했으면 몇 초 뒤 다시 해 봐. 계속이면: launchctl print gui/$(id -u)/com.jjw.home')
        data, err = tailscale_json()
        if not data:
            print(f'Tailscale: 연결 실패 ({err})')
            print('  확인: launchctl print gui/$(id -u)/com.jjw.tailscaled-userspace')
            return 1
        s = data.get('Self', {})
        print(f"Tailscale: {data.get('BackendState')}  이 맥 {s.get('DNSName', '').rstrip('.')}  "
              f"{', '.join(s.get('TailscaleIPs', []))}")
        for p in (data.get('Peer') or {}).values():
            print(f"  {'●' if p.get('Online') else '○'} {p.get('HostName')} ({p.get('OS')})")
        return 1

    d = json.loads(body)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0
    t = d.get('tailscale') or {}
    s = t.get('self') or {}
    left = days_left(s.get('keyExpiry'))
    print(f"Tailscale: {t.get('state')}  tailnet {t.get('suffix')}")
    print(f"이 맥: {s.get('dns')}  {', '.join(s.get('ips', []))}"
          + (f'  키 만료 {left}일 남음' if left is not None else '  키 만료 없음'))
    if left is not None and left < 30:
        print('  ! 키 만료가 30일 안 남았어. 관리 콘솔에서 키 만료를 끄거나 다시 로그인해야 해.')
    print('기기:')
    for p in t.get('peers', []):
        print(f"  {'●' if p.get('online') else '○'} {p.get('host')} ({p.get('os')})")
    print('serve:')
    for r in d.get('serve') or []:
        print(f"  {r['url']} → {r['target']}")
    if not d.get('serve'):
        print('  (없음) — 폰에서 홈에 못 들어와. serve 설정은 이 스킬이 바꾸지 않아.')
    base = f"http://{s.get('dns')}" if s.get('dns') else ''
    print('앱:')
    for a in d.get('apps', []):
        state = '켜짐' if a.get('enabled') else '꺼짐'
        where = a.get('root') or a.get('url')
        print(f"  [{state}] {a['id']}  {a.get('title')}  {base}{a.get('href')}  ← {where}")
    print(f'홈: {base}/  (맥에서는 {LOCAL}/)')
    return 0


# ---------------------------------------------------------------- check

ABS_REF = re.compile(r'''(?:src|href)\s*=\s*["'](/(?!/)[^"']+)["']''', re.I)


def cmd_check(args):
    try:
        apps = {a['id']: a for a in load_apps().get('apps', [])}
    except (OSError, ValueError) as e:
        fail(f'apps.json 을 못 읽었어: {e}')
    if args.id not in apps:
        fail(f'apps.json 에 {args.id} 가 없어')
    a = apps[args.id]
    ok = True
    if args.id in disabled_ids():
        print(f'! {args.id} 는 홈에서 꺼져 있어 (403). 홈 화면 스위치로 켜야 열려.')
        ok = False
    if a.get('url') and not a.get('root'):
        print(f"링크형 앱이라 홈 서버가 서빙하지 않아: {a['url']}")
        return 0

    path = f'/apps/{args.id}/'
    code, body = fetch(LOCAL + path)
    print(f"로컬   {LOCAL}{path}  → {code or body}")
    ok &= code == 200

    dns = self_dns()
    if not dns:
        print('tailnet 주소를 못 알아냈어 (Tailscale 꺼짐?)')
        ok = False
    else:
        tcode, tbody = fetch(f'http://{dns}{path}', proxy=PROXY, timeout=8)
        print(f"tailnet http://{dns}{path}  → {tcode or tbody}  (프록시 {PROXY} 경유)")
        ok &= tcode == 200

    if code == 200:
        refs = sorted(set(ABS_REF.findall(body)))
        if refs:
            print('! index.html 에 / 로 시작하는 경로가 있어. /apps/<id>/ 아래에서는 깨져:')
            for r in refs[:10]:
                print(f'    {r}')
            print('  상대경로(./)로 바꾸거나 빌드 설정을 고쳐 (Vite 는 base: "./").')
        print('  (index.html 만 봤어. JS 가 만드는 경로는 브라우저에서 확인해야 해.)')
    print('결과: ' + ('열림' if ok else '문제 있음'))
    return 0 if ok else 1


# ---------------------------------------------------------------- add / remove

def is_same_or_ancestor(path, of):
    of = os.path.realpath(os.path.expanduser(of))
    return path == of or of.startswith(path.rstrip('/') + '/')


def scan(root):
    """(파일 수, 총 바이트, 거부 목록, 경고 목록, 상한 도달)."""
    count = size = 0
    deny, warn = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != 'node_modules' and not d.startswith('.')]
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            if any(fnmatch.fnmatch(name, p) for p in WARN_FILES):
                warn.append(rel)
                continue
            if name.startswith('.'):
                continue  # 서버가 숨긴다
            if any(fnmatch.fnmatch(name.lower(), p) for p in DENY_FILES):
                deny.append(rel)
            count += 1
            try:
                size += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
            if count >= SCAN_LIMIT:
                return count, size, deny, warn, True
    return count, size, deny, warn, False


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f}{unit}' if unit == 'B' else f'{n:.1f}{unit}'
        n /= 1024


def backup():
    os.makedirs(BACKUPS, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    dest = os.path.join(BACKUPS, f'apps.json.{stamp}')
    shutil.copy2(APPS, dest)
    olds = sorted(f for f in os.listdir(BACKUPS) if f.startswith('apps.json.'))
    for f in olds[:-KEEP_BACKUPS]:
        os.remove(os.path.join(BACKUPS, f))
    return dest


def write_apps(data):
    fd, tmp = tempfile.mkstemp(dir=HOME_DIR, prefix='.apps.', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, APPS)
    load_apps()  # 다시 읽어 JSON 이 깨지지 않았는지 확인


def parse_thumb(spec, root):
    m = re.fullmatch(r'(.+):(\d+),(\d+),(\d+),(\d+)', spec)
    if not m:
        fail('--thumb 은 이미지:x,y,w,h 형식이야 (이미지는 root 기준 상대경로)')
    image = m.group(1)
    full = os.path.realpath(os.path.join(root, image))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        fail(f'썸네일 이미지가 root 안에 없어: {image}')
    x, y, w, h = map(int, m.groups()[1:])
    return {'image': image, 'x': x, 'y': y, 'w': w, 'h': h}


def cmd_add(args):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.id):
        fail('id 는 소문자 kebab-case 여야 해 (예: gisa-dojo)')
    if bool(args.root) == bool(args.url):
        fail('--root 와 --url 중 하나만 줘')
    data = load_apps()
    apps = data.setdefault('apps', [])
    existing = [a for a in apps if a.get('id') == args.id]
    if existing and not args.replace:
        fail(f'{args.id} 가 이미 있어. 바꾸려면 --replace')

    entry = {'id': args.id, 'title': args.title, 'summary': args.summary or ''}
    if args.root:
        root = os.path.realpath(os.path.expanduser(args.root))
        if not os.path.isdir(root):
            fail(f'폴더가 없어: {root}')
        for wide in TOO_WIDE:
            if is_same_or_ancestor(root, wide):
                fail(f'{root} 는 너무 넓어 ({wide} 와 같거나 그 위). 빌드 결과 폴더만 등록해')
        if not os.path.isfile(os.path.join(root, 'index.html')):
            fail(f'{root}/index.html 이 없어')
        if os.path.exists(os.path.join(root, '.git')) and not args.allow_repo_root:
            fail(f'{root} 는 저장소 최상위야 (.git). src/·설정까지 공개돼. '
                 '빌드 결과 폴더(dist/ 등)를 쓰거나, 이 폴더가 곧 정적 사이트이고 비밀이 없으면 --allow-repo-root')
        count, size, deny, warn, capped = scan(root)
        if deny:
            fail('비밀일 수 있는 파일이 있어서 거부했어:\n  ' + '\n  '.join(deny[:20]))
        for w in warn:
            print(f'! {w} — 점 파일이라 서버가 숨기지만, 정적 사이트에 둘 이유가 있는지 확인해')
        print(f"공개될 파일: {count}{'개 이상' if capped else '개'}, {human(size)}  (tailnet 의 모든 기기)")
        entry['root'] = root
        if args.thumb:
            entry['thumb'] = parse_thumb(args.thumb, root)
    else:
        if not re.match(r'https?://', args.url):
            fail('--url 은 http(s):// 로 시작해야 해')
        entry['url'] = args.url
        print('링크형 앱이야. 홈 서버는 링크만 보여 주고 프록시하지 않아.')

    if args.id in disabled_ids():
        print(f'! {args.id} 는 홈에서 꺼진 기록이 있어 (state.json). 홈 화면 스위치로 켜야 열려.')

    saved = backup()
    if existing:
        apps[apps.index(existing[0])] = entry
    else:
        apps.append(entry)
    write_apps(data)
    print(f"{'바꿈' if existing else '추가'}: {args.id}  (백업 {saved})")
    if entry.get('root'):
        print()
        return cmd_check(argparse.Namespace(id=args.id))
    return 0


def cmd_remove(args):
    data = load_apps()
    apps = data.get('apps', [])
    left = [a for a in apps if a.get('id') != args.id]
    if len(left) == len(apps):
        fail(f'apps.json 에 {args.id} 가 없어')
    saved = backup()
    data['apps'] = left
    write_apps(data)
    print(f'제거: {args.id}  (백업 {saved})')
    return 0


def main():
    ap = argparse.ArgumentParser(prog='tailnet-home', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('status', help='Tailscale·serve·앱 상태')
    p.add_argument('--json', action='store_true')
    p = sub.add_parser('check', help='앱이 로컬·tailnet 에서 열리는지')
    p.add_argument('id')
    p = sub.add_parser('add', help='apps.json 에 앱 추가')
    p.add_argument('--id', required=True)
    p.add_argument('--title', required=True)
    p.add_argument('--summary')
    p.add_argument('--root')
    p.add_argument('--url')
    p.add_argument('--thumb', help='이미지:x,y,w,h (root 기준)')
    p.add_argument('--replace', action='store_true')
    p.add_argument('--allow-repo-root', action='store_true')
    p = sub.add_parser('remove', help='apps.json 에서 앱 제거')
    p.add_argument('id')
    args = ap.parse_args()
    if not os.path.isfile(APPS) and args.cmd != 'status':
        fail(f'홈 서버 apps.json 이 없어: {APPS} (TAILNET_HOME_DIR 확인)')
    return {'status': cmd_status, 'check': cmd_check, 'add': cmd_add, 'remove': cmd_remove}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
