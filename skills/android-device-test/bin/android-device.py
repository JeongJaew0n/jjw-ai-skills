#!/usr/bin/env python3
"""android-device — adb 로 붙은 Android 실기기를 읽고, 검증하고, 테스트 뒤 원래대로 돌려놓는다.

Python 3 표준 라이브러리만 쓴다. 이미지 라이브러리(PIL)나 protobuf 없이 PNG 와
Preferences DataStore 를 직접 디코드한다 — 처음 보는 맥·세션에서도 설치 없이 돌아야 해서.

읽기 — 자동 호출로 바로 써도 되는 것:
  devices                         연결된 기기
  state [--package P]             최상단 앱·잠금·화면·배터리·음량·글자 크기·다크 모드·회전
  guard <package>                 그 앱이 최상단·포커스이고 잠금 화면이 아니면 0, 아니면 5

읽기 — 사용자가 기기를 보라고 했을 때 (화면 내용·앱 데이터를 가져오므로):
  shot [out.png]                  스크린샷 받기 (기본 $TMPDIR, git 작업 트리 안은 거부)
  px <png> name=x,y ...           지점 색
  stats <png> [--rect x,y,w,h]    최대 밝기·밝은 픽셀 수·무게중심
  crop <png> x,y,w,h <out.png>    잘라서 확대 저장
  ui [--find RE] [--switch-near LABEL]   uiautomator 덤프에서 좌표 찾기
  datastore <package> [keys...]   Preferences DataStore 읽기 (debuggable 빌드)
  snapshot <out.json> [--package P]      되돌릴 설정 기록
  diff <snapshot.json>            지금과 스냅샷의 차이 (있으면 종료 코드 1)

쓰기 — 사용자가 기기 테스트를 직접 시켰을 때만:
  restore <snapshot.json> --yes   스냅샷과 다른 값만 되돌린다 (--yes 없으면 계획만 출력)
  tap x y --package P             guard 를 통과해야 보낸다
  swipe x1 y1 x2 y2 ms --package P

종료 코드: 0 성공, 1 오류, 2 사용법·기기 미지정, 3 adb 없음, 4 기기 없음,
           5 가드 실패, 6 스냅샷과 다름(diff·restore 후 남은 차이)
"""

import argparse
import datetime
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib

EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NO_ADB = 3
EXIT_NO_DEVICE = 4
EXIT_GUARD = 5
EXIT_DIFFERS = 6

# 무선 adb 는 연결이 걸리면 끝없이 기다린다. 모든 호출에 상한을 둔다.
ADB_TIMEOUT = int(os.environ.get("ANDROID_DEVICE_TIMEOUT", "40"))

# 흔한 SDK 설치 위치. PATH 에 adb 가 없을 때만 본다.
SDK_GUESSES = [
    "/opt/homebrew/share/android-commandlinetools",
    "/usr/local/share/android-commandlinetools",
    "~/Library/Android/sdk",
    "~/Android/Sdk",
]

# snapshot 이 기록하는 설정. 테스트가 자주 바꾸고, 바뀐 채 남으면 사용자가 알아채기 어려운 것들이다.
SETTINGS = [
    ("system", "screen_off_timeout"),
    ("system", "font_scale"),
    ("system", "screen_brightness"),
    ("system", "screen_brightness_mode"),
    ("secure", "enabled_accessibility_services"),
    ("secure", "accessibility_enabled"),
    ("secure", "enabled_notification_listeners"),
    ("system", "show_touches"),
    ("system", "pointer_location"),
    ("system", "accelerometer_rotation"),
    ("system", "user_rotation"),
    ("global", "stay_on_while_plugged_in"),
    ("global", "low_power"),
    ("global", "zen_mode"),
    ("global", "window_animation_scale"),
    ("global", "transition_animation_scale"),
    ("global", "animator_duration_scale"),
]
# --package 를 줬을 때 기록하는 appops. 오버레이 앱 테스트에서 가장 자주 바꾼다.
APPOPS = ["SYSTEM_ALERT_WINDOW"]
STREAMS = {"music": 3, "ring": 2, "notification": 5}


def die(msg, code=EXIT_ERROR):
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------- adb

def find_adb():
    """adb 경로. ANDROID_ADB 를 주면 그것만 본다(없으면 없는 것이다)."""
    explicit = os.environ.get("ANDROID_ADB")
    if explicit is not None:
        return explicit if os.access(explicit, os.X_OK) else None
    found = shutil.which("adb")
    if found:
        return found
    roots = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")] + SDK_GUESSES
    for root in roots:
        if not root:
            continue
        cand = os.path.join(os.path.expanduser(root), "platform-tools", "adb")
        if os.access(cand, os.X_OK):
            return cand
    return None


def require_adb():
    adb = find_adb()
    if not adb:
        die("adb 를 찾지 못했습니다.\n"
            "  macOS: brew install --cask android-platform-tools\n"
            "  또는 ANDROID_HOME 을 SDK 경로로, ANDROID_ADB 를 adb 실행 파일로 지정하세요.",
            EXIT_NO_ADB)
    return adb


def run(adb, args, serial=None, binary=False, timeout=ADB_TIMEOUT, check=False):
    cmd = [adb] + (["-s", serial] if serial else []) + args
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        die(f"adb 가 {timeout}초 안에 끝나지 않았습니다: {' '.join(args)}\n"
            "무선 연결이 끊겼을 수 있습니다. `devices` 로 상태를 보세요.")
    if check and proc.returncode != 0:
        die(f"adb 실패 ({' '.join(args)}): {proc.stderr.decode(errors='replace').strip()}")
    if binary:
        return proc.returncode, proc.stdout, proc.stderr.decode(errors="replace")
    return proc.returncode, proc.stdout.decode(errors="replace"), proc.stderr.decode(errors="replace")


def list_devices(adb):
    _, out, _ = run(adb, ["devices", "-l"])
    devs = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        serial = parts[0]
        wireless = ":" in serial or "_adb-tls-connect" in serial
        devs.append({"serial": serial, "state": parts[1], "transport": "wifi" if wireless else "usb",
                     "model": info.get("model", "")})
    return devs


class Device:
    def __init__(self, adb, serial):
        self.adb, self.serial = adb, serial

    def sh(self, cmd, timeout=ADB_TIMEOUT):
        _, out, _ = run(self.adb, ["shell", cmd], self.serial, timeout=timeout)
        return out

    def exec_out(self, cmd, timeout=ADB_TIMEOUT):
        return run(self.adb, ["exec-out", cmd], self.serial, binary=True, timeout=timeout)

    def prop(self, name):
        return self.sh(f"getprop {name}").strip()


def pick_device(serial_arg):
    adb = require_adb()
    devs = list_devices(adb)
    ready = [d for d in devs if d["state"] == "device"]
    serial = serial_arg or os.environ.get("ANDROID_SERIAL")
    if serial:
        if not any(d["serial"] == serial for d in ready):
            die(f"기기 {serial} 이(가) 연결돼 있지 않습니다. `devices` 로 목록을 보세요.", EXIT_NO_DEVICE)
        return Device(adb, serial)
    if not ready:
        other = [d for d in devs if d["state"] != "device"]
        hint = ""
        if any(d["state"] == "unauthorized" for d in other):
            hint = "\n폰 화면의 'USB 디버깅 허용' 을 눌러야 합니다."
        elif other:
            hint = "\n" + ", ".join(f"{d['serial']}={d['state']}" for d in other)
        die("연결된 Android 기기가 없습니다." + hint, EXIT_NO_DEVICE)
    if len(ready) > 1:
        die("기기가 여러 대입니다. -s <serial> 이나 ANDROID_SERIAL 로 고르세요:\n" +
            "\n".join(f"  {d['serial']}  {d['transport']}  {d['model']}" for d in ready), EXIT_USAGE)
    return Device(adb, ready[0]["serial"])


# ---------------------------------------------------------------- 상태 읽기

def first(pattern, text, group=1):
    m = re.search(pattern, text)
    return m.group(group) if m else None


def top_activity(dev):
    out = dev.sh("dumpsys activity activities")
    comp = (first(r"topResumedActivity=ActivityRecord\{\S+ \S+ (\S+/\S+)", out)
            or first(r"mResumedActivity: ActivityRecord\{\S+ \S+ (\S+/\S+)", out))
    if not comp:
        comp = first(r"mCurrentFocus=Window\{\S+ \S+ (\S+?)\}", dev.sh("dumpsys window"))
    return comp


def keyguard_showing(dev):
    for cmd in ("dumpsys window", "dumpsys activity activities"):
        v = first(r"(?:isKeyguardShowing|mKeyguardShowing|keyguardShowing)=(true|false)", dev.sh(cmd))
        if v:
            return v == "true"
    return None


def focused_window(dev):
    """입력이 실제로 들어갈 창. 알림창·키보드·시스템 대화상자가 앞에 있으면 최상단 Activity 와 다르다."""
    out = dev.sh("dumpsys window")
    return first(r"mCurrentFocus=Window\{\S+ \S+ ([^}]+)\}", out)


def rotation(dev):
    return first(r"mRotation=(\w+)", dev.sh("dumpsys display")) or first(r"mRotation=(\w+)", dev.sh("dumpsys window"))


def wakefulness(dev):
    return first(r"mWakefulness=(\w+)", dev.sh("dumpsys power"))


def volume(dev, stream):
    for cmd in (f"cmd media_session volume --stream {stream} --get", f"media volume --stream {stream} --get"):
        m = re.search(r"volume is (\d+) in range \[(\d+)\.\.(\d+)\]", dev.sh(cmd))
        if m:
            return int(m.group(1)), int(m.group(3))
    return None


def setting(dev, ns, key):
    v = dev.sh(f"settings get {ns} {key}").strip()
    return None if v in ("null", "") else v


def night_mode(dev):
    return first(r"Night mode: (\w+)", dev.sh("cmd uimode night"))


def app_locales(dev, package):
    out = dev.sh(f"cmd locale get-app-locales {package} --user current")
    v = first(r"are \[(.*)\]", out)
    return v if v is not None else None


def package_windows(dev, package):
    """그 패키지가 가진 창을 종류(ty=)별로 센다. 해제한 뒤 0 이어야 누수가 없다."""
    out = dev.sh("dumpsys window windows")
    counts = {}
    for block in re.split(r"\n(?=  Window #)", out):
        head = block.split("\n", 1)[0]
        if package not in head and f"package={package}" not in block:
            continue
        ty = first(r"\bty=(\w+)", block) or "?"
        counts[ty] = counts.get(ty, 0) + 1
    return counts


def package_services(dev, package):
    out = dev.sh(f"dumpsys activity services {package}")
    return {"running": len(re.findall(r"\* ServiceRecord\{", out)),
            "foreground": len(re.findall(r"isForeground=true", out))}


def battery(dev):
    out = dev.sh("dumpsys battery")
    powered = [k for k in ("AC", "USB", "Wireless") if re.search(rf"{k} powered: true", out)]
    return {"level": int(first(r"level: (\d+)", out) or -1),
            "charge_counter_uah": int(first(r"Charge counter: (\d+)", out) or -1),
            "powered": powered}


def cmd_devices(args):
    adb = require_adb()
    devs = list_devices(adb)
    for d in devs:
        if d["state"] == "device":
            dev = Device(adb, d["serial"])
            d.update(manufacturer=dev.prop("ro.product.manufacturer"), model=dev.prop("ro.product.model"),
                     android=dev.prop("ro.build.version.release"), sdk=dev.prop("ro.build.version.sdk"))
    if args.json:
        print(json.dumps(devs, ensure_ascii=False, indent=2))
    elif not devs:
        print("연결된 기기 없음")
    else:
        for d in devs:
            extra = f"{d.get('manufacturer', '')} {d['model']}  Android {d.get('android', '?')} (SDK {d.get('sdk', '?')})" \
                if d["state"] == "device" else ""
            print(f"{d['serial']}  {d['state']}  {d['transport']}  {extra}".rstrip())
    if not any(d["state"] == "device" for d in devs):
        sys.exit(EXIT_NO_DEVICE)


def cmd_state(args):
    dev = pick_device(args.serial)
    s = {"serial": dev.serial, "top": top_activity(dev), "focus": focused_window(dev),
         "rotation": rotation(dev), "keyguard": keyguard_showing(dev),
         "wakefulness": wakefulness(dev), "battery": battery(dev),
         "font_scale": setting(dev, "system", "font_scale"), "night_mode": night_mode(dev),
         "volume": {}}
    for name, stream in STREAMS.items():
        v = volume(dev, stream)
        s["volume"][name] = f"{v[0]}/{v[1]}" if v else None
    if args.package:
        s["package"] = {"name": args.package, "windows": package_windows(dev, args.package),
                        "services": package_services(dev, args.package),
                        "app_locales": app_locales(dev, args.package)}
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return
    b = s["battery"]
    print(f"기기        {s['serial']}")
    print(f"최상단      {s['top']}")
    print(f"포커스 창   {s['focus']}   회전 {s['rotation']}")
    print(f"잠금 화면   {s['keyguard']}   화면 {s['wakefulness']}")
    print(f"배터리      {b['level']}%  카운터 {b['charge_counter_uah']} µAh  전원 {','.join(b['powered']) or '없음'}")
    print(f"음량        " + "  ".join(f"{k} {v}" for k, v in s["volume"].items()))
    print(f"글자 크기   {s['font_scale']}   다크 모드 {s['night_mode']}")
    if args.package:
        p = s["package"]
        print(f"{p['name']}: 창 {p['windows'] or 0}  서비스 {p['services']}  앱 로케일 [{p['app_locales']}]")


def guard_check(dev, package):
    top = top_activity(dev)
    focus = focused_window(dev)
    kg = keyguard_showing(dev)
    wake = wakefulness(dev)
    problems = []
    if not top or top.split("/")[0] != package:
        problems.append(f"최상단이 {package} 가 아님 (지금 {top})")
    if focus and focus.split("/")[0] != package:
        problems.append(f"포커스 창이 {package} 가 아님 (지금 {focus} — 알림창·키보드·대화상자일 수 있음)")
    if kg:
        problems.append("잠금 화면이 떠 있음")
    if wake and wake != "Awake":
        problems.append(f"화면이 꺼져 있음 ({wake})")
    return problems


def cmd_guard(args):
    dev = pick_device(args.serial)
    problems = guard_check(dev, args.package)
    if problems:
        die("가드 실패 — 입력을 보내지 마세요: " + "; ".join(problems), EXIT_GUARD)
    print(f"통과: {args.package} 가 최상단·포커스이고 잠금 화면이 아님 (회전 {rotation(dev)})")


# ---------------------------------------------------------------- PNG (stdlib)

def png_load(path, max_rows=None):
    """8비트 PNG 를 (w, h, channels, rows) 로. rows[y] 는 bytearray.

    max_rows 를 주면 그 줄까지만 푼다 — 필터가 윗줄에 의존해서 위에서부터는 다 풀어야 하지만
    아래는 건너뛸 수 있다. 1080x2400 을 다 풀면 순수 파이썬으로 몇 초 걸린다.
    """
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        die(f"PNG 가 아닙니다: {path}")
    i, idat, ihdr = 8, [], None
    while i < len(data):
        n, typ = struct.unpack(">I4s", data[i:i + 8])
        chunk = data[i + 8:i + 8 + n]
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif typ == b"IDAT":
            idat.append(chunk)
        elif typ == b"IEND":
            break
        i += 12 + n
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        die(f"지원하지 않는 PNG 형식입니다 (bit depth {depth}, color type {ctype}, interlace {interlace}). "
            "screencap 결과는 8비트 RGBA 라 해당 없음.")
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = w * ch
    rows, prev, o = [], bytearray(stride), 0
    last = h if max_rows is None else min(h, max_rows)
    for _ in range(last):
        f = raw[o]
        line = bytearray(raw[o + 1:o + 1 + stride])
        o += 1 + stride
        if f == 1:
            for x in range(ch, stride):
                line[x] = (line[x] + line[x - ch]) & 255
        elif f == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif f == 3:
            for x in range(stride):
                left = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                b = prev[x]
                c = prev[x - ch] if x >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, ch, rows


def rgb_at(row, x, ch):
    if ch in (1, 2):
        v = row[x * ch]
        return v, v, v
    return row[x * ch], row[x * ch + 1], row[x * ch + 2]


def png_write(path, w, h, rgb_rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rgb_rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def parse_rect(text, w, h):
    try:
        x, y, rw, rh = (int(v) for v in text.split(","))
    except ValueError:
        die(f"영역은 x,y,w,h 로 주세요: {text}", EXIT_USAGE)
    x2, y2 = min(w, x + rw), min(h, y + rh)
    if x < 0 or y < 0 or x >= x2 or y >= y2:
        die(f"영역이 이미지({w}x{h}) 밖입니다: {text}", EXIT_USAGE)
    return x, y, x2, y2


def git_worktree(path):
    d = os.path.dirname(os.path.abspath(path)) or "."
    while not os.path.isdir(d):
        d = os.path.dirname(d)
    try:
        proc = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def out_path(path, suffix, allow_repo):
    """기기에서 가져온 것(화면·설정)을 저장할 경로.

    스크린샷과 스냅샷에는 사용자의 화면 내용, 기기 모델, 접근성 서비스 목록이 들어간다.
    자동 커밋하는 저장소 안에 떨어지면 그대로 푸시되므로 기본은 임시 폴더, 작업 트리 안은 거부.
    """
    if not path:
        base = os.path.join(os.environ.get("TMPDIR", "/tmp"), "android-device")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + suffix)
    top = git_worktree(path)
    if top and not allow_repo:
        die(f"{path} 은(는) git 작업 트리({top}) 안입니다. 화면·기기 정보가 커밋될 수 있어 거부합니다.\n"
            "경로를 빼면 임시 폴더에 저장합니다. 정말 저장소에 둘 거면 --in-repo.", EXIT_USAGE)
    return path


def cmd_shot(args):
    args.out = out_path(args.out, ".png", args.in_repo)
    dev = pick_device(args.serial)
    code, data, err = dev.exec_out("screencap -p")
    if code != 0 or data[:8] != b"\x89PNG\r\n\x1a\n":
        die(f"스크린샷 실패: {err.strip() or '응답이 PNG 가 아님'}")
    with open(args.out, "wb") as f:
        f.write(data)
    w, h = struct.unpack(">II", data[16:24])
    print(f"{args.out}  {w}x{h}")


def cmd_px(args):
    points = []
    for p in args.points:
        name, _, xy = p.rpartition("=")
        try:
            x, y = (int(v) for v in xy.split(","))
        except ValueError:
            die(f"지점은 이름=x,y 로 주세요: {p}", EXIT_USAGE)
        points.append((name or xy, x, y))
    w, h, ch, rows = png_load(args.png, max_rows=max(y for _, _, y in points) + 1)
    out = []
    for name, x, y in points:
        if not (0 <= x < w and 0 <= y < h):
            die(f"{name} ({x},{y}) 이 이미지({w}x{h}) 밖입니다", EXIT_USAGE)
        r, g, b = rgb_at(rows[y], x, ch)
        out.append({"name": name, "x": x, "y": y, "hex": f"#{r:02X}{g:02X}{b:02X}"})
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for o in out:
            print(f"{o['name']:24s} ({o['x']},{o['y']})  {o['hex']}")


def cmd_stats(args):
    with open(args.png, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    x1, y1, x2, y2 = parse_rect(args.rect, w, h) if args.rect else (0, 0, w, h)
    _, _, ch, rows = png_load(args.png, max_rows=y2)
    mx, bright, sx, sy, total = 0, 0, 0, 0, 0
    for y in range(y1, y2):
        row = rows[y]
        for x in range(x1, x2):
            v = max(rgb_at(row, x, ch))
            total += v
            if v > mx:
                mx = v
            if v > args.threshold:
                bright += 1
                sx += x
                sy += y
    n = (x2 - x1) * (y2 - y1)
    res = {"rect": [x1, y1, x2 - x1, y2 - y1], "pixels": n, "max": mx, "mean": round(total / n, 2),
           "threshold": args.threshold, "bright": bright,
           "centroid": [round(sx / bright, 1), round(sy / bright, 1)] if bright else None}
    if args.json:
        print(json.dumps(res, indent=2))
        return
    print(f"영역 {res['rect']}  픽셀 {n}")
    print(f"최대 {mx}  평균 {res['mean']}  (채널 중 가장 밝은 값 기준)")
    print(f"{args.threshold} 보다 밝은 픽셀 {bright}" + (f"  무게중심 {res['centroid']}" if bright else "  — 순수 검정"))


def cmd_crop(args):
    args.out = out_path(args.out, ".png", args.in_repo)
    with open(args.png, "rb") as f:
        head = f.read(24)
    w, h = struct.unpack(">II", head[16:24])
    x1, y1, x2, y2 = parse_rect(args.rect, w, h)
    _, _, ch, rows = png_load(args.png, max_rows=y2)
    k = max(1, args.scale)
    out = []
    for y in range(y1, y2):
        line = bytearray()
        for x in range(x1, x2):
            line += bytes(rgb_at(rows[y], x, ch)) * k
        out.extend([line] * k)
    png_write(args.out, (x2 - x1) * k, (y2 - y1) * k, out)
    print(f"{args.out}  {(x2 - x1) * k}x{(y2 - y1) * k}")


# ---------------------------------------------------------------- uiautomator

def ui_dump(dev):
    for _ in range(4):
        code, data, _ = dev.exec_out("uiautomator dump /dev/tty", timeout=60)
        text = data.decode("utf-8", errors="replace")
        end = text.rfind("</hierarchy>")
        if end > 0:
            return text[text.find("<"):end + len("</hierarchy>")]
    die("uiautomator 덤프를 받지 못했습니다. 화면이 계속 움직이는 중(애니메이션)이면 실패할 수 있습니다.")


def ui_nodes(xml):
    nodes = []
    for raw in re.findall(r"<node [^>]*>", xml):
        attrs = dict(re.findall(r'(\S+?)="([^"]*)"', raw))
        b = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attrs.get("bounds", ""))
        if not b:
            continue
        x0, y0, x1, y1 = map(int, b.groups())
        nodes.append({"text": attrs.get("text", ""), "desc": attrs.get("content-desc", ""),
                      "id": attrs.get("resource-id", ""), "class": attrs.get("class", ""),
                      "bounds": [x0, y0, x1, y1], "center": [(x0 + x1) // 2, (y0 + y1) // 2],
                      "clickable": attrs.get("clickable") == "true",
                      "checkable": attrs.get("checkable") == "true", "checked": attrs.get("checked") == "true"})
    return nodes


def cmd_ui(args):
    if args.local:
        with open(args.local, encoding="utf-8") as f:
            xml = f.read()
    else:
        xml = ui_dump(pick_device(args.serial))
    if args.save:
        args.save = out_path(args.save, ".xml", args.in_repo)
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(xml)
    nodes = ui_nodes(xml)
    if args.switch_near:
        labels = [n for n in nodes if re.search(args.switch_near, n["text"] or n["desc"])]
        switches = [n for n in nodes if n["checkable"]]
        if not labels:
            die(f"라벨 '{args.switch_near}' 이 덤프에 없습니다 (스크롤 밖일 수 있음)", EXIT_ERROR)
        if not switches:
            die("체크 가능한 노드가 없습니다", EXIT_ERROR)
        ly = labels[0]["center"][1]
        best = min(switches, key=lambda n: abs(n["center"][1] - ly))
        res = {"label": labels[0]["text"] or labels[0]["desc"], "center": best["center"], "checked": best["checked"]}
        print(json.dumps(res, ensure_ascii=False) if args.json else
              f"{res['center'][0]} {res['center'][1]} {'checked' if res['checked'] else 'unchecked'}")
        return
    if args.find:
        nodes = [n for n in nodes if re.search(args.find, n["text"]) or re.search(args.find, n["desc"])]
    else:
        nodes = [n for n in nodes if n["text"] or n["desc"]]
    if args.json:
        print(json.dumps(nodes, ensure_ascii=False, indent=2))
    else:
        for n in nodes:
            flags = "".join(c for c, on in (("C", n["clickable"]), ("✓", n["checked"])) if on)
            print(f"{n['center'][0]:5d} {n['center'][1]:5d}  {flags:2s} {n['text'] or '(' + n['desc'] + ')'}")
    print("※ 덤프는 화면에 이미 없는 노드를 담고 있을 수 있어요. 그러면 그 아래 좌표도 밀려 있어요. 보이는지와 누를 좌표는 스크린샷으로 확인하세요.",
          file=sys.stderr)
    if args.find and not nodes:
        sys.exit(EXIT_ERROR)


# ---------------------------------------------------------------- DataStore (protobuf wire format)

def varint(b, i):
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7f) << s
        s += 7
        if c < 0x80:
            return r, i


def wire_fields(b):
    i = 0
    while i < len(b):
        key, i = varint(b, i)
        num, wt = key >> 3, key & 7
        if wt == 0:
            v, i = varint(b, i)
        elif wt == 1:
            v, i = b[i:i + 8], i + 8
        elif wt == 2:
            n, i = varint(b, i)
            v, i = b[i:i + n], i + n
        elif wt == 5:
            v, i = b[i:i + 4], i + 4
        else:
            raise ValueError(f"지원하지 않는 wire type {wt}")
        yield num, wt, v


def signed64(v):
    return v - (1 << 64) if v >= 1 << 63 else v


def decode_preferences(data):
    """androidx.datastore Preferences 의 PreferenceMap.

    map<string, Value> preferences = 1;
    Value: boolean 1, float 2, integer 3, long 4, string 5, string_set 6, double 7, bytes 8
    """
    out = {}
    for num, _, entry in wire_fields(data):
        if num != 1:
            continue
        key, value = "", None
        for n, _, v in wire_fields(entry):
            if n == 1:
                key = v.decode("utf-8", errors="replace")
            elif n == 2:
                for vn, _, vv in wire_fields(v):
                    if vn == 1:
                        value = bool(vv)
                    elif vn == 2:
                        value = struct.unpack("<f", vv)[0]
                    elif vn in (3, 4):
                        value = signed64(vv)
                    elif vn == 5:
                        value = vv.decode("utf-8", errors="replace")
                    elif vn == 6:
                        value = sorted(s.decode("utf-8", errors="replace") for sn, _, s in wire_fields(vv) if sn == 1)
                    elif vn == 7:
                        value = struct.unpack("<d", vv)[0]
                    elif vn == 8:
                        value = "bytes:" + vv.hex()
        out[key] = value
    return out


def cmd_datastore(args):
    if args.local:
        with open(args.local, "rb") as f:
            data = f.read()
        keys = ([args.package] if args.package else []) + args.keys
    else:
        if not args.package:
            die("패키지를 주거나 --local <파일> 을 쓰세요", EXIT_USAGE)
        dev = pick_device(args.serial)
        name = args.file
        if not name:
            code, out, err = dev.exec_out(f"run-as {args.package} ls files/datastore")
            listing = out.decode(errors="replace")
            if code != 0 or "not debuggable" in listing or "Unknown package" in listing:
                die(f"run-as 실패: {(listing + err).strip()}\n"
                    "release 빌드는 읽을 수 없어요. debuggable 빌드가 필요합니다.")
            files = [f for f in listing.split() if f.endswith(".preferences_pb")]
            if len(files) != 1:
                die("DataStore 파일을 하나로 정할 수 없습니다. --file 로 고르세요: " + " ".join(listing.split()),
                    EXIT_USAGE)
            name = files[0]
        code, data, err = dev.exec_out(f"run-as {args.package} cat files/datastore/{name}")
        if code != 0 or data.startswith(b"run-as:"):
            die(f"읽기 실패: {(data.decode(errors='replace') + err).strip()}")
        keys = args.keys
    prefs = decode_preferences(data)
    if keys:
        prefs = {k: prefs.get(k) for k in keys}
    if args.json:
        print(json.dumps(prefs, ensure_ascii=False, indent=2))
    else:
        for k, v in prefs.items():
            print(f"{k}={v}")


# ---------------------------------------------------------------- snapshot / diff / restore

def appop(dev, package, op):
    out = dev.sh(f"cmd appops get {package} {op}")
    return first(rf"{op}: (\w+)", out) or "default"


def runtime_permissions(dev, package):
    """런타임 권한의 부여 상태. 설치 시 권한(install permissions)은 바꿀 수 없어 뺀다."""
    out = dev.sh(f"dumpsys package {package}")
    perms = {}
    for section in re.findall(r"runtime permissions:\n((?:\s+\S+: granted=\w+.*\n)+)", out):
        for name, granted in re.findall(r"(\S+): granted=(\w+)", section):
            perms[name] = granted == "true"
    return perms


def idle_whitelisted(dev, package):
    out = dev.sh("dumpsys deviceidle whitelist")
    return bool(re.search(rf"^\w+,{re.escape(package)},", out, re.M))


def take_snapshot(dev, packages):
    snap = {"serial": dev.serial, "taken_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "settings": {f"{ns}:{key}": setting(dev, ns, key) for ns, key in SETTINGS},
            "volume": {}, "night_mode": night_mode(dev), "app_locales": {}, "appops": {},
            "permissions": {}, "idle_whitelist": {}}
    for name, stream in STREAMS.items():
        v = volume(dev, stream)
        snap["volume"][name] = v[0] if v else None
    for package in packages:
        snap["app_locales"][package] = app_locales(dev, package)
        snap["appops"][package] = {op: appop(dev, package, op) for op in APPOPS}
        snap["permissions"][package] = runtime_permissions(dev, package)
        snap["idle_whitelist"][package] = idle_whitelisted(dev, package)
    return snap


def snapshot_diff(old, new):
    changes = []
    for k, v in old["settings"].items():
        if new["settings"].get(k) != v:
            changes.append(("settings", k, v, new["settings"].get(k)))
    for k, v in old["volume"].items():
        if v is not None and new["volume"].get(k) != v:
            changes.append(("volume", k, v, new["volume"].get(k)))
    if old.get("night_mode") and new.get("night_mode") != old["night_mode"]:
        changes.append(("night_mode", "night_mode", old["night_mode"], new.get("night_mode")))
    for k, v in old.get("app_locales", {}).items():
        if new.get("app_locales", {}).get(k) != v:
            changes.append(("app_locales", k, v, new["app_locales"].get(k)))
    for pkg, ops in old.get("appops", {}).items():
        for op, mode in ops.items():
            now = new.get("appops", {}).get(pkg, {}).get(op)
            if now != mode:
                changes.append(("appops", f"{pkg}:{op}", mode, now))
    for pkg, perms in old.get("permissions", {}).items():
        now_perms = new.get("permissions", {}).get(pkg, {})
        for perm, granted in perms.items():
            if now_perms.get(perm) != granted:
                changes.append(("permission", f"{pkg}:{perm}", granted, now_perms.get(perm)))
    for pkg, on in old.get("idle_whitelist", {}).items():
        if new.get("idle_whitelist", {}).get(pkg) != on:
            changes.append(("idle_whitelist", pkg, on, new["idle_whitelist"].get(pkg)))
    return changes


def load_snapshot(path, dev):
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    if snap.get("serial") != dev.serial:
        print(f"주의: 스냅샷은 {snap.get('serial')} 에서 찍었고 지금 기기는 {dev.serial} 입니다", file=sys.stderr)
    return snap


def cmd_snapshot(args):
    args.out = out_path(args.out, ".json", args.in_repo)
    dev = pick_device(args.serial)
    snap = take_snapshot(dev, args.package)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    print(f"{args.out} 에 기록했습니다 ({len(snap['settings'])}개 설정, 음량 {len(snap['volume'])}개"
          + (f", 앱 {', '.join(args.package)}: 로케일·appops·런타임 권한·배터리 최적화 예외" if args.package else "") + ")")


def current_for(dev, snap):
    return take_snapshot(dev, list(snap.get("app_locales", {})))


def print_changes(changes):
    for kind, key, old, new in changes:
        print(f"  {kind:11s} {key:42s} 원래 {old!r:>14}  지금 {new!r}")


def cmd_diff(args):
    dev = pick_device(args.serial)
    snap = load_snapshot(args.snapshot, dev)
    changes = snapshot_diff(snap, current_for(dev, snap))
    if not changes:
        print("스냅샷과 같습니다")
        return
    print(f"스냅샷과 다른 값 {len(changes)}개:")
    print_changes(changes)
    sys.exit(EXIT_DIFFERS)


def cmd_restore(args):
    dev = pick_device(args.serial)
    snap = load_snapshot(args.snapshot, dev)
    changes = snapshot_diff(snap, current_for(dev, snap))
    if not changes:
        print("되돌릴 것이 없습니다")
        return
    print(("되돌립니다" if args.yes else "되돌릴 계획 (--yes 로 실행)") + f" — {len(changes)}개:")
    print_changes(changes)
    if not args.yes:
        return
    for kind, key, old, _ in changes:
        if kind == "settings":
            ns, name = key.split(":", 1)
            # 빈 문자열을 put 하면 'Bad arguments' 가 나는 키가 있어 비었던 값은 delete 로 되돌린다
            cmd = f"settings delete {ns} {name}" if old in (None, "") else f"settings put {ns} {name} '{old}'"
        elif kind == "volume":
            cmd = f"cmd media_session volume --stream {STREAMS[key]} --set {old}"
        elif kind == "night_mode":
            cmd = f"cmd uimode night {old}"
        elif kind == "appops":
            pkg, op = key.split(":", 1)
            cmd = f"cmd appops set {pkg} {op} {old}"
        elif kind == "permission":
            pkg, perm = key.split(":", 1)
            cmd = f"pm {'grant' if old else 'revoke'} {pkg} {perm}"
        elif kind == "idle_whitelist":
            cmd = f"cmd deviceidle whitelist {'+' if old else '-'}{key}"
        else:
            cmd = f"cmd locale set-app-locales {key} --user current --locales '{old or ''}'"
        dev.sh(cmd)
    left = snapshot_diff(snap, current_for(dev, snap))
    if left:
        print("되돌리지 못한 값:")
        print_changes(left)
        sys.exit(EXIT_DIFFERS)
    print("스냅샷과 같아졌습니다")


# ---------------------------------------------------------------- 입력 (가드 필수)

def guarded_input(args, cmd):
    dev = pick_device(args.serial)
    problems = guard_check(dev, args.package)
    if problems:
        die("보내지 않았습니다: " + "; ".join(problems), EXIT_GUARD)
    dev.sh(cmd)
    print(f"보냄: {cmd}")


def cmd_tap(args):
    guarded_input(args, f"input tap {args.x} {args.y}")


def cmd_swipe(args):
    guarded_input(args, f"input swipe {args.x1} {args.y1} {args.x2} {args.y2} {args.ms}")


# ---------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(prog="android-device", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-s", "--serial", help="기기 시리얼 (없으면 ANDROID_SERIAL, 그것도 없으면 유일한 기기)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    sp = add("devices", cmd_devices, "연결된 기기 목록")
    sp.add_argument("--json", action="store_true")
    sp = add("state", cmd_state, "기기 상태 한눈에")
    sp.add_argument("--package")
    sp.add_argument("--json", action="store_true")
    sp = add("guard", cmd_guard, "그 앱이 최상단이고 잠금 화면이 아닌지")
    sp.add_argument("package")
    sp = add("shot", cmd_shot, "스크린샷 받기")
    sp.add_argument("out", nargs="?", help="생략하면 $TMPDIR/android-device/")
    sp.add_argument("--in-repo", action="store_true", help="git 작업 트리 안에 저장하는 것을 허용")
    sp = add("px", cmd_px, "지점 색 읽기")
    sp.add_argument("png")
    sp.add_argument("points", nargs="+", metavar="name=x,y")
    sp.add_argument("--json", action="store_true")
    sp = add("stats", cmd_stats, "영역 밝기 통계")
    sp.add_argument("png")
    sp.add_argument("--rect", metavar="x,y,w,h")
    sp.add_argument("--threshold", type=int, default=8, help="이보다 밝으면 '밝은 픽셀' (기본 8)")
    sp.add_argument("--json", action="store_true")
    sp = add("crop", cmd_crop, "잘라서 확대 저장")
    sp.add_argument("png")
    sp.add_argument("rect", metavar="x,y,w,h")
    sp.add_argument("out", nargs="?", help="생략하면 $TMPDIR/android-device/")
    sp.add_argument("--scale", type=int, default=1)
    sp.add_argument("--in-repo", action="store_true")
    sp = add("ui", cmd_ui, "uiautomator 덤프에서 좌표 찾기")
    sp.add_argument("--find", metavar="REGEX")
    sp.add_argument("--switch-near", metavar="LABEL_REGEX")
    sp.add_argument("--save", metavar="PATH")
    sp.add_argument("--local", metavar="XML", help="기기 대신 저장된 덤프를 읽는다")
    sp.add_argument("--in-repo", action="store_true")
    sp.add_argument("--json", action="store_true")
    sp = add("datastore", cmd_datastore, "Preferences DataStore 읽기")
    sp.add_argument("package", nargs="?")
    sp.add_argument("keys", nargs="*")
    sp.add_argument("--file", help="files/datastore/ 안의 파일 이름")
    sp.add_argument("--local", metavar="PB", help="기기 대신 로컬 파일을 디코드")
    sp.add_argument("--json", action="store_true")
    sp = add("snapshot", cmd_snapshot, "되돌릴 설정 기록")
    sp.add_argument("out", nargs="?", help="생략하면 $TMPDIR/android-device/")
    sp.add_argument("--package", action="append", default=[], help="여러 번 줄 수 있다")
    sp.add_argument("--in-repo", action="store_true")
    sp = add("diff", cmd_diff, "스냅샷과 지금 비교")
    sp.add_argument("snapshot")
    sp = add("restore", cmd_restore, "스냅샷으로 되돌리기 (--yes 필요)")
    sp.add_argument("snapshot")
    sp.add_argument("--yes", action="store_true")
    sp = add("tap", cmd_tap, "가드 통과 후 탭")
    sp.add_argument("x", type=int)
    sp.add_argument("y", type=int)
    sp.add_argument("--package", required=True)
    sp = add("swipe", cmd_swipe, "가드 통과 후 스와이프")
    for a in ("x1", "y1", "x2", "y2", "ms"):
        sp.add_argument(a, type=int)
    sp.add_argument("--package", required=True)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
