#!/usr/bin/env python3
"""android-device.py 시험 — 진짜 adb 는 한 번도 부르지 않는다.

모든 실행은 가짜 adb(이 파일이 임시 폴더에 쓰는 파이썬 스크립트)를 ANDROID_ADB 로 지정하고,
PATH 도 그 폴더 + /usr/bin:/bin 만 준다. find_adb() 는 ANDROID_ADB 가 있으면 그것만 보므로
사용자 폰이 연결돼 있어도 닿지 않는다. 가짜 adb 는 상태 파일(state.json)에서 답하고, 받은 argv 를
log.jsonl 에 남긴다 — 가드가 입력을 막았는지, restore 가 정확히 어떤 명령을 보내는지 그걸로 본다.
출력은 모두 tempfile.TemporaryDirectory 안에 쓴다.

  python3 -I android-device.test.py        exit 0 이면 모두 기대대로
"""

import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "android-device.py")
PKG = "com.example.app"
SERIAL = "FAKESERIAL01"
SYS_PATH = "/usr/bin:/bin"   # 가짜 adb 폴더 뒤에 붙는 PATH. 여기에 adb 가 있으면 시험을 시작하지 않는다.

# 도구를 모듈로도 불러 순수 함수를 직접 시험한다. 저장소 안에 __pycache__ 를 만들지 않는다.
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("android_device", TOOL)
ad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ad)


def setUpModule():
    if shutil.which("adb", path=SYS_PATH):
        raise RuntimeError(f"{SYS_PATH} 에 진짜 adb 가 있어 시험을 멈춥니다")


# ---------------------------------------------------------------- 가짜 adb

FAKE_ADB = r'''
import json, os, shlex, sys, time
D = os.environ["FAKE_ADB_DIR"]
argv = sys.argv[1:]
with open(os.path.join(D, "log.jsonl"), "a") as f:
    f.write(json.dumps(argv) + "\n")
with open(os.path.join(D, "state.json")) as f:
    S = json.load(f)
if S.get("sleep"):
    time.sleep(S["sleep"])
if argv[:1] == ["-s"]:
    argv = argv[2:]


def save():
    with open(os.path.join(D, "state.json"), "w") as f:
        json.dump(S, f)


def writable(key):
    return key not in S.get("stuck", [])


def shell(cmd):
    if cmd in S["shell"]:
        return S["shell"][cmd]
    a = shlex.split(cmd)
    if a[:2] == ["settings", "get"]:
        v = S["settings"].get(f"{a[2]}:{a[3]}")
        return ("null" if v is None else v) + "\n"
    if a[:2] == ["settings", "put"] and writable(f"{a[2]}:{a[3]}"):
        S["settings"][f"{a[2]}:{a[3]}"] = a[4]
    elif a[:2] == ["settings", "delete"] and writable(f"{a[2]}:{a[3]}"):
        S["settings"].pop(f"{a[2]}:{a[3]}", None)
    elif a[:3] == ["cmd", "media_session", "volume"]:
        stream = a[a.index("--stream") + 1]
        if "--get" in a:
            v, mx = S["volume"][stream]
            return f"volume is {v} in range [0..{mx}]\n"
        S["volume"][stream][0] = int(a[a.index("--set") + 1])
    elif a[:3] == ["cmd", "uimode", "night"]:
        if len(a) == 3:
            return f"Night mode: {S['night']}\n"
        S["night"] = a[3]
    elif a[:3] == ["cmd", "appops", "get"]:
        mode = S["appops"].get(f"{a[3]}:{a[4]}")
        return f"{a[4]}: {mode}; time=+1d2h ago\n" if mode else "No operations.\n"
    elif a[:3] == ["cmd", "appops", "set"]:
        S["appops"][f"{a[3]}:{a[4]}"] = a[5]
    elif a[:2] == ["dumpsys", "package"]:
        perms = S["perms"].get(a[2], {})
        lines = "".join(f"        {p}: granted={'true' if g else 'false'}, flags=[ USER_SET ]\n" for p, g in perms.items())
        return (f"Packages:\n  Package [{a[2]}] (1a2b3c):\n    install permissions:\n"
                f"      android.permission.INTERNET: granted=true\n    User 0: installed=true\n"
                f"      runtime permissions:\n{lines}")
    elif a[:1] == ["pm"] and a[1] in ("grant", "revoke"):
        S["perms"].setdefault(a[2], {})[a[3]] = a[1] == "grant"
    elif a == ["dumpsys", "deviceidle", "whitelist"]:
        return "system-excidle,com.android.shell,2000\n" + "".join(f"user,{p},10234\n" for p in S["whitelist"])
    elif a[:3] == ["cmd", "deviceidle", "whitelist"]:
        p = a[3][1:]
        if a[3][0] == "+" and p not in S["whitelist"]:
            S["whitelist"].append(p)
        elif a[3][0] == "-" and p in S["whitelist"]:
            S["whitelist"].remove(p)
    elif a[:3] == ["cmd", "locale", "get-app-locales"]:
        return f"Locales for {a[3]} for user 0 are [{S['locales'].get(a[3], '')}]\n"
    elif a[:3] == ["cmd", "locale", "set-app-locales"]:
        S["locales"][a[3]] = a[a.index("--locales") + 1]
    else:
        return ""
    save()
    return ""


if argv[:1] == ["devices"]:
    sys.stdout.write(S["devices"])
elif argv[:1] == ["shell"]:
    sys.stdout.write(shell(" ".join(argv[1:])))
elif argv[:1] == ["exec-out"]:
    e = S["exec"].get(" ".join(argv[1:]))
    if e is None:
        sys.stderr.write("fake adb: no exec fixture\n")
        sys.exit(1)
    if "file" in e:
        with open(e["file"], "rb") as f:
            sys.stdout.buffer.write(f.read())
    else:
        sys.stdout.buffer.write(e.get("text", "").encode())
    sys.stderr.write(e.get("err", ""))
    sys.exit(e.get("code", 0))
else:
    sys.stderr.write("fake adb: unsupported " + " ".join(argv) + "\n")
    sys.exit(1)
'''

# restore·tap 이 보내는 "상태를 바꾸는" 셸 명령. 가드·계획 모드에서는 하나도 없어야 한다.
WRITE_RE = re.compile(r"^(input |settings (put|delete) |pm (grant|revoke) |cmd appops set |cmd locale set-app-locales "
                      r"|cmd deviceidle whitelist [+-]|cmd uimode night \S|cmd media_session volume .*--set|am |svc |reboot)")


def act(top):
    return (f"ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n"
            f"  topResumedActivity=ActivityRecord{{a1b2c3d u0 {top} t42}}\n") if top else "ACTIVITY MANAGER ACTIVITIES\n"


def win(focus, keyguard="false"):
    lines = "WINDOW MANAGER\n"
    if focus:
        lines += f"  mCurrentFocus=Window{{e5f6a7 u0 {focus}}}\n"
    if keyguard is not None:
        lines += f"  isKeyguardShowing={keyguard}\n"
    return lines + "  mRotation=0\n"


WINDOWS = f"""WINDOW MANAGER WINDOWS (dumpsys window windows)
  Window #0 Window{{aa u0 {PKG}/{PKG}.MainActivity}}:
    mDisplayId=0 mSession=Session{{1 2:u0a234}} package={PKG} appop=NONE
    mAttrs={{(0,0)(fillxfill) ty=BASE_APPLICATION fmt=TRANSLUCENT}}
  Window #1 Window{{bb u0 {PKG}}}:
    mDisplayId=0 package={PKG} appop=SYSTEM_ALERT_WINDOW
    mAttrs={{(0,0)(fillxfill) ty=APPLICATION_OVERLAY}}
  Window #2 Window{{cc u0 NotificationShade}}:
    mDisplayId=0 package=com.android.systemui appop=NONE
    mAttrs={{(0,0)(fillxfill) ty=NOTIFICATION_SHADE}}
"""


def default_state():
    main = f"{PKG}/.MainActivity"
    return {
        "devices": f"List of devices attached\n{SERIAL}       device usb:1-1 product:fake model:SM_X000N device:fake transport_id:3\n\n",
        "shell": {
            "dumpsys activity activities": act(main),
            "dumpsys window": win(f"{PKG}/{PKG}.MainActivity"),
            "dumpsys power": "POWER MANAGER\n  mWakefulness=Awake\n  mWakefulnessChanging=false\n",
            "dumpsys display": "",
            "dumpsys battery": "Current Battery Service state:\n  AC powered: false\n  USB powered: true\n"
                               "  Wireless powered: false\n  level: 77\n  Charge counter: 3456000\n",
            "dumpsys window windows": WINDOWS,
            f"dumpsys activity services {PKG}": f"  * ServiceRecord{{f00 u0 {PKG}/.OverlayService}}\n    isForeground=true foregroundId=1\n",
            "getprop ro.product.manufacturer": "samsung\n",
            "getprop ro.product.model": "SM-X000N\n",
            "getprop ro.build.version.release": "16\n",
            "getprop ro.build.version.sdk": "36\n",
        },
        "exec": {},
        "settings": {
            "system:screen_off_timeout": "30000",
            "system:font_scale": "1.0",
            "system:screen_brightness": "128",
            "system:screen_brightness_mode": "1",
            "secure:enabled_accessibility_services": f"{PKG}/{PKG}.Svc",
            "secure:accessibility_enabled": "1",
            "system:accelerometer_rotation": "0",
            "system:user_rotation": "0",
            "global:zen_mode": "0",
            "global:low_power": "0",
        },
        "volume": {"3": [8, 15], "2": [5, 15], "5": [5, 15]},
        "night": "yes",
        "appops": {f"{PKG}:SYSTEM_ALERT_WINDOW": "allow"},
        "perms": {PKG: {"android.permission.POST_NOTIFICATIONS": True, "android.permission.CAMERA": False}},
        "whitelist": [PKG],
        "locales": {PKG: ""},
    }


class FakeDev:
    """모듈 함수를 직접 시험할 때 쓰는 기기. sh() 가 표에서 답한다 — 프로세스도 adb 도 없다."""

    def __init__(self, table, serial=SERIAL):
        self.table, self.serial = table, serial

    def sh(self, cmd, timeout=None):
        return self.table.get(cmd, "")


class ToolCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="android-device-test-")
        self.dir = os.path.realpath(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        for d in ("bin", "fake", "home", "out"):
            os.makedirs(os.path.join(self.dir, d))
        self.fake_dir = os.path.join(self.dir, "fake")
        self.adb = os.path.join(self.dir, "bin", "adb")
        with open(self.adb, "w") as f:
            f.write(f"#!{sys.executable} -I\n" + FAKE_ADB)
        os.chmod(self.adb, 0o755)
        self.state = default_state()
        self.save_state()

    def save_state(self):
        with open(os.path.join(self.fake_dir, "state.json"), "w") as f:
            json.dump(self.state, f)

    def load_state(self):
        with open(os.path.join(self.fake_dir, "state.json")) as f:
            return json.load(f)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def run_tool(self, *args, adb=None, env=None):
        e = {"PATH": f"{os.path.dirname(self.adb)}:{SYS_PATH}", "HOME": self.path("home"),
             "TMPDIR": self.path("out"), "FAKE_ADB_DIR": self.fake_dir, "LANG": "en_US.UTF-8",
             "PYTHONIOENCODING": "utf-8", "ANDROID_ADB": adb or self.adb}
        e.update(env or {})
        assert e["ANDROID_ADB"] != "" and os.path.dirname(e["ANDROID_ADB"]) == os.path.dirname(self.adb)
        return subprocess.run([sys.executable, "-I", TOOL, *args], cwd=self.dir, env=e,
                              capture_output=True, text=True, timeout=60)

    def calls(self):
        log = os.path.join(self.fake_dir, "log.jsonl")
        if not os.path.exists(log):
            return []
        with open(log) as f:
            return [json.loads(line) for line in f]

    def shell_cmds(self):
        out = []
        for argv in self.calls():
            if argv[:1] == ["-s"]:
                argv = argv[2:]
            if argv[:1] == ["shell"]:
                out.append(" ".join(argv[1:]))
        return out

    def writes(self):
        return [c for c in self.shell_cmds() if WRITE_RE.match(c)]

    def assertExit(self, proc, code):
        self.assertEqual(proc.returncode, code, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


# ---------------------------------------------------------------- 안전장치·adb 찾기

class AdbLocationTest(ToolCase):
    def test_fake_adb_is_the_one_used(self):
        p = self.run_tool("devices")
        self.assertExit(p, 0)
        self.assertEqual(self.calls()[0], ["devices", "-l"])
        self.assertTrue(all(a[:2] == ["-s", SERIAL] for a in self.calls()[1:]))

    def test_missing_adb_exits_3_for_every_device_command(self):
        missing = self.path("bin", "no-such-adb")
        for args in (["devices"], ["state"], ["guard", PKG], ["tap", "1", "2", "--package", PKG], ["shot"]):
            with self.subTest(args=args):
                p = self.run_tool(*args, adb=missing)
                self.assertExit(p, 3)
                self.assertIn("adb 를 찾지 못했습니다", p.stderr)
        self.assertEqual(self.calls(), [])

    def test_non_executable_android_adb_counts_as_missing(self):
        os.chmod(self.adb, 0o644)
        self.assertExit(self.run_tool("devices"), 3)
        self.assertEqual(self.calls(), [])

    def test_adb_timeout_exits_1(self):
        self.state["sleep"] = 3
        self.save_state()
        p = self.run_tool("devices", env={"ANDROID_DEVICE_TIMEOUT": "1"})
        self.assertExit(p, 1)
        self.assertIn("1초 안에 끝나지 않았습니다", p.stderr)


# ---------------------------------------------------------------- devices / 기기 고르기

class DevicesTest(ToolCase):
    def set_devices(self, *lines):
        self.state["devices"] = "List of devices attached\n" + "".join(l + "\n" for l in lines) + "\n"
        self.save_state()

    def test_list_devices_parses_transport_state_and_model(self):
        self.set_devices(f"{SERIAL}       device usb:1-1 product:fake model:SM_X000N transport_id:3",
                         "192.168.0.7:5555 device product:x model:Pixel_8 transport_id:4",
                         "adb-FAKE-AbCd._adb-tls-connect._tcp device model:Pixel_9 transport_id:5",
                         "ZY22FAKE       unauthorized usb:1-2 transport_id:6")
        p = self.run_tool("devices", "--json")
        self.assertExit(p, 0)
        devs = json.loads(p.stdout)
        self.assertEqual([(d["serial"], d["state"], d["transport"]) for d in devs], [
            (SERIAL, "device", "usb"), ("192.168.0.7:5555", "device", "wifi"),
            ("adb-FAKE-AbCd._adb-tls-connect._tcp", "device", "wifi"), ("ZY22FAKE", "unauthorized", "usb")])
        self.assertEqual(devs[0]["manufacturer"], "samsung")
        self.assertEqual(devs[0]["android"], "16")
        self.assertEqual(devs[3]["model"], "")
        self.assertNotIn("android", devs[3])
        # unauthorized 기기에는 getprop 을 보내지 않는다
        self.assertFalse(any("ZY22FAKE" in a for a in self.calls()))

    def test_devices_text_output(self):
        p = self.run_tool("devices")
        self.assertExit(p, 0)
        self.assertEqual(p.stdout.strip(), f"{SERIAL}  device  usb  samsung SM-X000N  Android 16 (SDK 36)")

    def test_no_device_exits_4(self):
        self.set_devices()
        p = self.run_tool("devices")
        self.assertExit(p, 4)
        self.assertIn("연결된 기기 없음", p.stdout)
        self.assertExit(self.run_tool("state"), 4)
        self.assertExit(self.run_tool("tap", "1", "2", "--package", PKG), 4)
        self.assertEqual(self.writes(), [])

    def test_only_unauthorized_exits_4_with_hint(self):
        self.set_devices("ZY22FAKE unauthorized usb:1-2 transport_id:6")
        p = self.run_tool("devices")
        self.assertExit(p, 4)
        self.assertIn("ZY22FAKE  unauthorized  usb", p.stdout)
        p = self.run_tool("state")
        self.assertExit(p, 4)
        self.assertIn("USB 디버깅 허용", p.stderr)

    def test_offline_device_listed_in_hint(self):
        self.set_devices("192.168.0.7:5555 offline transport_id:4")
        p = self.run_tool("state")
        self.assertExit(p, 4)
        self.assertIn("192.168.0.7:5555=offline", p.stderr)

    def test_two_devices_need_serial(self):
        self.set_devices(f"{SERIAL} device model:A transport_id:3", "192.168.0.7:5555 device model:B transport_id:4")
        p = self.run_tool("state")
        self.assertExit(p, 2)
        self.assertIn("-s <serial>", p.stderr)
        self.assertIn("192.168.0.7:5555  wifi  B", p.stderr)
        p = self.run_tool("-s", SERIAL, "state", "--json")
        self.assertExit(p, 0)
        self.assertEqual(json.loads(p.stdout)["serial"], SERIAL)
        p = self.run_tool("state", "--json", env={"ANDROID_SERIAL": "192.168.0.7:5555"})
        self.assertExit(p, 0)
        self.assertEqual(json.loads(p.stdout)["serial"], "192.168.0.7:5555")

    def test_unknown_serial_exits_4(self):
        p = self.run_tool("-s", "NOPE", "state")
        self.assertExit(p, 4)
        self.assertIn("NOPE", p.stderr)

    def test_serial_of_unauthorized_device_exits_4(self):
        self.set_devices("ZY22FAKE unauthorized usb:1-2 transport_id:6")
        self.assertExit(self.run_tool("-s", "ZY22FAKE", "state"), 4)


# ---------------------------------------------------------------- state

class StateTest(ToolCase):
    def test_state_json(self):
        p = self.run_tool("state", "--package", PKG, "--json")
        self.assertExit(p, 0)
        s = json.loads(p.stdout)
        self.assertEqual(s["top"], f"{PKG}/.MainActivity")
        self.assertEqual(s["focus"], f"{PKG}/{PKG}.MainActivity")
        self.assertIs(s["keyguard"], False)
        self.assertEqual(s["wakefulness"], "Awake")
        self.assertEqual(s["rotation"], "0")
        self.assertEqual(s["battery"], {"level": 77, "charge_counter_uah": 3456000, "powered": ["USB"]})
        self.assertEqual(s["volume"], {"music": "8/15", "ring": "5/15", "notification": "5/15"})
        self.assertEqual(s["font_scale"], "1.0")
        self.assertEqual(s["night_mode"], "yes")
        self.assertEqual(s["package"]["windows"], {"BASE_APPLICATION": 1, "APPLICATION_OVERLAY": 1})
        self.assertEqual(s["package"]["services"], {"running": 1, "foreground": 1})
        self.assertEqual(s["package"]["app_locales"], "")
        self.assertEqual(self.writes(), [])

    def test_state_text(self):
        p = self.run_tool("state")
        self.assertExit(p, 0)
        self.assertIn(f"최상단      {PKG}/.MainActivity", p.stdout)
        self.assertIn("잠금 화면   False   화면 Awake", p.stdout)
        self.assertIn("전원 USB", p.stdout)

    def test_state_falls_back_when_values_missing(self):
        self.state["shell"]["dumpsys battery"] = ""
        self.state["shell"]["dumpsys window"] = ""
        self.state["shell"]["dumpsys activity activities"] = ""
        self.state["volume"] = {}
        self.save_state()
        # 음량 명령이 실패해도(가짜 adb 가 KeyError 로 죽음) None 으로 둔다
        p = self.run_tool("state", "--json")
        self.assertExit(p, 0)
        s = json.loads(p.stdout)
        self.assertIsNone(s["top"])
        self.assertIsNone(s["keyguard"])
        self.assertEqual(s["battery"]["level"], -1)
        self.assertEqual(s["volume"], {"music": None, "ring": None, "notification": None})

    # BUG: package_windows 가 창 머리줄·package= 를 부분 문자열로 비교해서, com.example.app 을 물으면
    # com.example.app.helper 의 창까지 센다. 해제 뒤 "창 0개" 로 누수를 판정하는 용도라 틀린 경고가 난다.
    def test_package_windows_ignores_other_package_with_same_prefix(self):
        extra = (f"  Window #3 Window{{dd u0 {PKG}.helper}}:\n"
                 f"    mDisplayId=0 package={PKG}.helper appop=NONE\n    mAttrs={{ty=TOAST}}\n")
        counts = ad.package_windows(FakeDev({"dumpsys window windows": WINDOWS + extra}), PKG)
        self.assertEqual(counts, {"BASE_APPLICATION": 1, "APPLICATION_OVERLAY": 1})


# ---------------------------------------------------------------- 가드 (가장 중요)

def guard_table(top=f"{PKG}/.MainActivity", focus=f"{PKG}/{PKG}.MainActivity", keyguard="false", wake="Awake"):
    t = {"dumpsys activity activities": act(top), "dumpsys window": win(focus, keyguard)}
    t["dumpsys power"] = f"  mWakefulness={wake}\n" if wake else ""
    return t


class GuardUnitTest(unittest.TestCase):
    def check(self, **kw):
        return ad.guard_check(FakeDev(guard_table(**kw)), PKG)

    def test_passes_when_target_on_top_focused_unlocked_awake(self):
        self.assertEqual(self.check(), [])

    def test_other_app_on_top(self):
        probs = self.check(top="com.kakao.talk/.activity.chatroom.ChatRoomActivity",
                           focus="com.kakao.talk/com.kakao.talk.activity.chatroom.ChatRoomActivity")
        self.assertEqual(len(probs), 2)
        self.assertIn("최상단이 com.example.app 가 아님", probs[0])

    def test_package_prefix_is_not_the_target(self):
        self.assertTrue(self.check(top=f"{PKG}.debug/.MainActivity", focus=f"{PKG}.debug/x.Main"))
        self.assertTrue(self.check(top="com.example/.MainActivity", focus="com.example/x.Main"))

    def test_no_top_activity_refuses(self):
        probs = ad.guard_check(FakeDev({"dumpsys activity activities": "", "dumpsys window": win(None),
                                        "dumpsys power": "  mWakefulness=Awake\n"}), PKG)
        self.assertEqual(probs, ["최상단이 com.example.app 가 아님 (지금 None)"])

    def test_focus_on_notification_shade_refuses(self):
        probs = self.check(focus="NotificationShade")
        self.assertEqual(len(probs), 1)
        self.assertIn("포커스 창이", probs[0])

    def test_focus_on_other_apps_dialog_refuses(self):
        self.assertTrue(self.check(focus="com.google.android.permissioncontroller/"
                                         "com.android.permissioncontroller.permission.ui.GrantPermissionsActivity"))

    def test_focus_on_keyboard_refuses(self):
        self.assertTrue(self.check(focus="InputMethod"))

    def test_focus_with_spaces_refuses(self):
        self.assertTrue(self.check(focus="Application Not Responding: com.example.app"))

    def test_keyguard_showing_refuses(self):
        self.assertEqual(self.check(keyguard="true"), ["잠금 화면이 떠 있음"])

    def test_keyguard_read_from_activity_dump_when_window_has_none(self):
        t = guard_table(keyguard=None)
        t["dumpsys activity activities"] += "  KeyguardController:\n    keyguardShowing=true\n"
        self.assertEqual(ad.guard_check(FakeDev(t), PKG), ["잠금 화면이 떠 있음"])

    def test_screen_off_refuses(self):
        for wake in ("Asleep", "Dozing", "Dreaming"):
            with self.subTest(wake=wake):
                self.assertEqual(self.check(wake=wake), [f"화면이 꺼져 있음 ({wake})"])

    def test_all_problems_reported_together(self):
        self.assertEqual(len(self.check(top="a.b/.C", focus="NotificationShade", keyguard="true", wake="Asleep")), 4)

    def test_older_android_resumed_activity_format(self):
        t = guard_table()
        t["dumpsys activity activities"] = f"    mResumedActivity: ActivityRecord{{1 u0 {PKG}/.MainActivity t9}}\n"
        self.assertEqual(ad.guard_check(FakeDev(t), PKG), [])

    def test_top_falls_back_to_focused_window(self):
        t = guard_table()
        t["dumpsys activity activities"] = ""
        self.assertEqual(ad.top_activity(FakeDev(t)), f"{PKG}/{PKG}.MainActivity")
        self.assertEqual(ad.guard_check(FakeDev(t), PKG), [])

    # BUG: 잠금 상태를 읽지 못하면(패턴이 없는 Android 버전·제조사) keyguard_showing() 이 None 을 주고
    # guard_check 는 그걸 "잠금 아님" 으로 통과시킨다 (fail-open). 화면 상태(mWakefulness)도 같다.
    # 가드의 약속은 "잠금 화면이 아니면 0" 인데, 모르는 건 아님이 아니다.
    def test_unknown_lock_state_refuses(self):
        self.assertTrue(self.check(keyguard=None))


class GuardCliTest(ToolCase):
    def set_screen(self, **kw):
        self.state["shell"].update(guard_table(**kw))
        self.save_state()

    def assert_no_input_sent(self):
        self.assertEqual(self.writes(), [])
        self.assertFalse(any("input" in " ".join(a) for a in self.calls()))

    def test_guard_command(self):
        p = self.run_tool("guard", PKG)
        self.assertExit(p, 0)
        self.assertIn("통과", p.stdout)
        self.set_screen(top="com.kakao.talk/.Main", focus="com.kakao.talk/x.Main")
        p = self.run_tool("guard", PKG)
        self.assertExit(p, 5)
        self.assertIn("가드 실패", p.stderr)

    def test_tap_sent_only_when_guard_passes(self):
        p = self.run_tool("tap", "540", "1200", "--package", PKG)
        self.assertExit(p, 0)
        self.assertEqual(self.writes(), ["input tap 540 1200"])
        self.assertEqual(self.shell_cmds()[-1], "input tap 540 1200")
        self.assertIn("보냄: input tap 540 1200", p.stdout)

    def test_swipe_sent_only_when_guard_passes(self):
        p = self.run_tool("swipe", "100", "2000", "100", "500", "300", "--package", PKG)
        self.assertExit(p, 0)
        self.assertEqual(self.writes(), ["input swipe 100 2000 100 500 300"])

    def test_tap_refused_in_each_bad_state(self):
        cases = {
            "messenger on top": dict(top="com.kakao.talk/.Main", focus="com.kakao.talk/x.Main"),
            "prefix package": dict(top=f"{PKG}.debug/.Main", focus=f"{PKG}.debug/x.Main"),
            "notification shade": dict(focus="NotificationShade"),
            "keyboard focus": dict(focus="InputMethod"),
            "locked": dict(keyguard="true"),
            "screen off": dict(wake="Asleep"),
            "no top": dict(top=None, focus=None),
        }
        for name, kw in cases.items():
            for cmd in (["tap", "10", "20"], ["swipe", "1", "2", "3", "4", "100"]):
                with self.subTest(case=name, cmd=cmd[0]):
                    open(os.path.join(self.fake_dir, "log.jsonl"), "w").close()
                    self.set_screen(**kw)
                    p = self.run_tool(*cmd, "--package", PKG)
                    self.assertExit(p, 5)
                    self.assertIn("보내지 않았습니다", p.stderr)
                    self.assert_no_input_sent()
                    self.assertTrue(self.shell_cmds(), "가드가 기기 상태를 읽어야 함")
                    self.assertTrue(all(c.startswith("dumpsys ") for c in self.shell_cmds()), self.shell_cmds())


# ---------------------------------------------------------------- snapshot / diff / restore

class SnapshotTest(ToolCase):
    def snapshot(self):
        out = self.path("out", "snap.json")
        p = self.run_tool("snapshot", out, "--package", PKG)
        self.assertExit(p, 0)
        with open(out) as f:
            return out, json.load(f)

    def mutate(self):
        """테스트가 기기를 바꿔 놓은 상태."""
        s = self.load_state()
        s["settings"]["system:font_scale"] = "1.3"
        s["settings"].pop("secure:enabled_accessibility_services")      # 재설치로 꺼짐
        s["settings"]["secure:accessibility_enabled"] = "0"
        s["settings"]["system:show_touches"] = "1"                       # 원래 없던 값
        s["volume"]["3"][0] = 0
        s["night"] = "no"
        s["locales"][PKG] = "en-US"
        s["appops"][f"{PKG}:SYSTEM_ALERT_WINDOW"] = "ignore"
        s["perms"][PKG]["android.permission.POST_NOTIFICATIONS"] = False
        s["perms"][PKG]["android.permission.CAMERA"] = True
        s["whitelist"] = []
        self.state = s
        self.save_state()

    def clear_log(self):
        open(os.path.join(self.fake_dir, "log.jsonl"), "w").close()

    def test_snapshot_records_everything(self):
        _, snap = self.snapshot()
        self.assertEqual(snap["serial"], SERIAL)
        self.assertEqual(len(snap["settings"]), len(ad.SETTINGS))
        self.assertEqual(snap["settings"]["system:font_scale"], "1.0")
        self.assertIsNone(snap["settings"]["system:show_touches"])
        self.assertEqual(snap["volume"], {"music": 8, "ring": 5, "notification": 5})
        self.assertEqual(snap["night_mode"], "yes")
        self.assertEqual(snap["app_locales"], {PKG: ""})
        self.assertEqual(snap["appops"], {PKG: {"SYSTEM_ALERT_WINDOW": "allow"}})
        self.assertEqual(snap["permissions"], {PKG: {"android.permission.POST_NOTIFICATIONS": True,
                                                     "android.permission.CAMERA": False}})
        self.assertNotIn("android.permission.INTERNET", snap["permissions"][PKG])   # 설치 권한은 뺀다
        self.assertEqual(snap["idle_whitelist"], {PKG: True})
        self.assertEqual(self.writes(), [])

    def test_snapshot_default_path_is_tmpdir(self):
        p = self.run_tool("snapshot")
        self.assertExit(p, 0)
        path = p.stdout.split(" 에 기록했습니다")[0]
        self.assertTrue(path.startswith(self.path("out", "android-device") + os.sep), path)
        self.assertTrue(os.path.exists(path))

    def test_diff_same_then_different(self):
        out, _ = self.snapshot()
        p = self.run_tool("diff", out)
        self.assertExit(p, 0)
        self.assertIn("스냅샷과 같습니다", p.stdout)
        self.mutate()
        p = self.run_tool("diff", out)
        self.assertExit(p, 6)
        self.assertIn("스냅샷과 다른 값 11개", p.stdout)
        self.assertEqual(self.writes(), [])

    def test_restore_plan_without_yes_sends_nothing(self):
        out, _ = self.snapshot()
        self.mutate()
        self.clear_log()
        p = self.run_tool("restore", out)
        self.assertExit(p, 0)
        self.assertIn("되돌릴 계획 (--yes 로 실행) — 11개", p.stdout)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.load_state(), self.state)

    def test_restore_round_trip_issues_exact_commands(self):
        out, _ = self.snapshot()
        self.mutate()
        self.clear_log()
        p = self.run_tool("restore", out, "--yes")
        self.assertExit(p, 0)
        self.assertIn("스냅샷과 같아졌습니다", p.stdout)
        self.assertEqual(self.writes(), [
            "settings put system font_scale '1.0'",
            f"settings put secure enabled_accessibility_services '{PKG}/{PKG}.Svc'",
            "settings put secure accessibility_enabled '1'",
            "settings delete system show_touches",
            "cmd media_session volume --stream 3 --set 8",
            "cmd uimode night yes",
            f"cmd locale set-app-locales {PKG} --user current --locales ''",
            f"cmd appops set {PKG} SYSTEM_ALERT_WINDOW allow",
            f"pm grant {PKG} android.permission.POST_NOTIFICATIONS",
            f"pm revoke {PKG} android.permission.CAMERA",
            f"cmd deviceidle whitelist +{PKG}",
        ])
        p = self.run_tool("diff", out)
        self.assertExit(p, 0)
        self.assertEqual(self.load_state()["settings"], default_state()["settings"])

    def test_restore_nothing_to_do(self):
        out, _ = self.snapshot()
        self.clear_log()
        p = self.run_tool("restore", out, "--yes")
        self.assertExit(p, 0)
        self.assertIn("되돌릴 것이 없습니다", p.stdout)
        self.assertEqual(self.writes(), [])

    def test_restore_reports_values_that_did_not_come_back(self):
        out, _ = self.snapshot()
        self.mutate()
        self.state["stuck"] = ["system:font_scale"]
        self.save_state()
        p = self.run_tool("restore", out, "--yes")
        self.assertExit(p, 6)
        self.assertIn("되돌리지 못한 값", p.stdout)
        tail = p.stdout.split("되돌리지 못한 값:")[1]
        self.assertIn("system:font_scale", tail)
        self.assertNotIn("accessibility_enabled", tail)

    def test_snapshot_from_other_device_warns(self):
        out, snap = self.snapshot()
        snap["serial"] = "OTHER"
        with open(out, "w") as f:
            json.dump(snap, f)
        p = self.run_tool("diff", out)
        self.assertExit(p, 0)
        self.assertIn("스냅샷은 OTHER 에서 찍었고", p.stderr)

    def test_snapshot_diff_unit(self):
        old = {"settings": {"a:b": "1", "c:d": None}, "volume": {"music": 3, "ring": None},
               "night_mode": None, "app_locales": {}, "appops": {}, "permissions": {}, "idle_whitelist": {}}
        new = {"settings": {"a:b": "1", "c:d": "x"}, "volume": {"music": 3, "ring": 7},
               "night_mode": "yes", "app_locales": {}, "appops": {}, "permissions": {}, "idle_whitelist": {}}
        # 스냅샷 때 못 읽은 음량·다크 모드(None)는 비교하지 않는다
        self.assertEqual(ad.snapshot_diff(old, new), [("settings", "c:d", None, "x")])


# ---------------------------------------------------------------- 저장 경로 (작업 트리 거부)

class OutPathTest(ToolCase):
    def setUp(self):
        super().setUp()
        self.repo = self.path("repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True, capture_output=True,
                       env={"PATH": SYS_PATH, "HOME": self.path("home")})
        self.png = self.path("in.png")
        with open(self.png, "wb") as f:
            f.write(png_bytes(4, 3, 2, [[0] * 12] * 3))
        self.state["exec"]["screencap -p"] = {"file": self.png}
        self.save_state()

    def test_shot_into_repo_refused_before_touching_adb(self):
        p = self.run_tool("shot", os.path.join(self.repo, "sub", "x.png"))
        self.assertExit(p, 2)
        self.assertIn("git 작업 트리", p.stderr)
        self.assertEqual(self.calls(), [])

    def test_snapshot_into_repo_refused_before_touching_adb(self):
        self.assertExit(self.run_tool("snapshot", os.path.join(self.repo, "s.json")), 2)
        self.assertEqual(self.calls(), [])

    def test_crop_and_ui_save_into_repo_refused(self):
        self.assertExit(self.run_tool("crop", self.png, "0,0,2,2", os.path.join(self.repo, "c.png")), 2)
        xml = self.path("d.xml")
        with open(xml, "w") as f:
            f.write(UI_XML)
        self.assertExit(self.run_tool("ui", "--local", xml, "--save", os.path.join(self.repo, "d.xml")), 2)
        self.assertEqual(os.listdir(self.repo), [".git"])

    def test_in_repo_flag_allows(self):
        target = os.path.join(self.repo, "x.png")
        p = self.run_tool("shot", target, "--in-repo")
        self.assertExit(p, 0)
        self.assertEqual(p.stdout.strip(), f"{target}  4x3")

    def test_shot_default_path(self):
        p = self.run_tool("shot")
        self.assertExit(p, 0)
        path = p.stdout.split("  ")[0]
        self.assertTrue(path.startswith(self.path("out", "android-device") + os.sep))
        with open(path, "rb") as f, open(self.png, "rb") as g:
            self.assertEqual(f.read(), g.read())

    def test_shot_failure_exits_1(self):
        self.state["exec"]["screencap -p"] = {"text": "", "err": "Error: no display\n", "code": 1}
        self.save_state()
        p = self.run_tool("shot")
        self.assertExit(p, 1)
        self.assertIn("no display", p.stderr)
        self.state["exec"]["screencap -p"] = {"text": "not a png"}
        self.save_state()
        p = self.run_tool("shot")
        self.assertExit(p, 1)
        self.assertIn("응답이 PNG 가 아님", p.stderr)


# ---------------------------------------------------------------- PNG (합성 이미지)

def png_bytes(w, h, ctype, rows, filters=(0,), depth=8, split_idat=False):
    """시험용 PNG 인코더 — 도구의 디코더와 따로 짠다. 줄마다 filters 를 돌아가며 쓴다."""
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw, prev = bytearray(), bytes(w * ch)
    for y, row in enumerate(rows):
        row, ft = bytes(row), filters[y % len(filters)]
        raw.append(ft)
        for x in range(len(row)):
            a = row[x - ch] if x >= ch else 0
            b, c = prev[x], (prev[x - ch] if x >= ch else 0)
            if ft == 0:
                pred = 0
            elif ft == 1:
                pred = a
            elif ft == 2:
                pred = b
            elif ft == 3:
                pred = (a + b) // 2
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
            raw.append((row[x] - pred) & 255)
        prev = row

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    z = zlib.compress(bytes(raw))
    idat = chunk(b"IDAT", z[:len(z) // 2]) + chunk(b"IDAT", z[len(z) // 2:]) if split_idat else chunk(b"IDAT", z)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, 0))
            + chunk(b"tEXt", b"k\x00v") + idat + chunk(b"IEND", b""))


def canvas(w, h, fill=(0, 0, 0, 255)):
    return [[list(fill) for _ in range(w)] for _ in range(h)]


def flat(pixels):
    return [[v for px in row for v in px] for row in pixels]


class PngTest(ToolCase):
    def write_png(self, name, data):
        path = self.path(name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_decoder_handles_every_filter_and_color_type(self):
        import random
        rnd = random.Random(7)
        for ctype, ch in ((0, 1), (2, 3), (4, 2), (6, 4)):
            w, h = 7, 10
            rows = [[rnd.randrange(256) for _ in range(w * ch)] for _ in range(h)]
            for filters in ((0,), (1,), (2,), (3,), (4,), (0, 1, 2, 3, 4)):
                with self.subTest(ctype=ctype, filters=filters):
                    path = self.write_png("f.png", png_bytes(w, h, ctype, rows, filters, split_idat=True))
                    gw, gh, gch, grows = ad.png_load(path)
                    self.assertEqual((gw, gh, gch), (w, h, ch))
                    self.assertEqual([list(r) for r in grows], rows)
                    _, _, _, part = ad.png_load(path, max_rows=3)
                    self.assertEqual([list(r) for r in part], rows[:3])

    def make_screen(self):
        # 20x10 검정, (10..13, 2..5) 에 흰 사각형 4x4, (1,1) 에 빨강
        px = canvas(20, 10)
        for y in range(2, 6):
            for x in range(10, 14):
                px[y][x] = [255, 255, 255, 255]
        px[1][1] = [255, 0, 0, 255]
        return self.write_png("screen.png", png_bytes(20, 10, 6, flat(px), (4, 1, 2, 3, 0)))

    def test_px(self):
        png = self.make_screen()
        p = self.run_tool("px", png, "red=1,1", "white=11,3", "0,0", "--json")
        self.assertExit(p, 0)
        self.assertEqual([(o["name"], o["hex"]) for o in json.loads(p.stdout)],
                         [("red", "#FF0000"), ("white", "#FFFFFF"), ("0,0", "#000000")])
        p = self.run_tool("px", png, "white=11,3")
        self.assertExit(p, 0)
        self.assertRegex(p.stdout, r"white\s+\(11,3\)  #FFFFFF")
        self.assertEqual(self.calls(), [])

    def test_px_bad_input(self):
        png = self.make_screen()
        self.assertExit(self.run_tool("px", png, "a=20,0"), 2)
        self.assertExit(self.run_tool("px", png, "a=0,10"), 2)
        self.assertExit(self.run_tool("px", png, "a=-1,0"), 2)
        self.assertExit(self.run_tool("px", png, "a=1;2"), 2)

    def test_stats_pure_black_and_centroid(self):
        png = self.make_screen()
        p = self.run_tool("stats", png, "--rect", "0,6,20,4", "--json")
        self.assertExit(p, 0)
        r = json.loads(p.stdout)
        self.assertEqual((r["max"], r["bright"], r["centroid"], r["pixels"]), (0, 0, None, 80))
        p = self.run_tool("stats", png, "--rect", "0,6,20,4")
        self.assertIn("순수 검정", p.stdout)
        p = self.run_tool("stats", png, "--rect", "5,0,15,10", "--json")
        r = json.loads(p.stdout)
        self.assertEqual((r["max"], r["bright"], r["centroid"]), (255, 16, [11.5, 3.5]))
        # 영역이 이미지 밖으로 넘치면 잘라 낸다
        r = json.loads(self.run_tool("stats", png, "--rect", "10,2,100,100", "--json").stdout)
        self.assertEqual(r["rect"], [10, 2, 10, 8])

    def test_stats_whole_image_and_threshold(self):
        png = self.make_screen()
        r = json.loads(self.run_tool("stats", png, "--json").stdout)
        self.assertEqual((r["pixels"], r["bright"]), (200, 17))
        r = json.loads(self.run_tool("stats", png, "--threshold", "255", "--json").stdout)
        self.assertEqual(r["bright"], 0)

    def test_stats_bad_rect(self):
        png = self.make_screen()
        for rect in ("1,2,3", "a,b,c,d", "20,0,5,5", "0,0,0,5", "-1,0,5,5"):
            with self.subTest(rect=rect):
                self.assertExit(self.run_tool("stats", png, "--rect", rect), 2)

    def test_unsupported_and_non_png(self):
        p16 = self.write_png("16.png", png_bytes(2, 2, 2, [[0] * 6] * 2, depth=16))
        p = self.run_tool("stats", p16)
        self.assertExit(p, 1)
        self.assertIn("지원하지 않는 PNG", p.stderr)
        bad = self.write_png("bad.png", b"GIF89a" + b"\x00" * 40)
        p = self.run_tool("px", bad, "a=0,0")
        self.assertExit(p, 1)
        self.assertIn("PNG 가 아닙니다", p.stderr)

    def test_crop_scales(self):
        png = self.make_screen()
        out = self.path("out", "crop.png")
        p = self.run_tool("crop", png, "0,0,2,2", out, "--scale", "3")
        self.assertExit(p, 0)
        self.assertEqual(p.stdout.strip(), f"{out}  6x6")
        w, h, ch, rows = ad.png_load(out)
        self.assertEqual((w, h, ch), (6, 6, 3))
        self.assertEqual(ad.rgb_at(rows[0], 0, ch), (0, 0, 0))
        for y in range(3, 6):
            for x in range(3, 6):
                self.assertEqual(ad.rgb_at(rows[y], x, ch), (255, 0, 0))
        self.assertEqual(ad.rgb_at(rows[3], 2, ch), (0, 0, 0))

    def test_crop_default_out_and_zero_scale(self):
        png = self.make_screen()
        p = self.run_tool("crop", png, "10,2,4,4", "--scale", "0")
        self.assertExit(p, 0)
        path, size = p.stdout.strip().split("  ")
        self.assertEqual(size, "4x4")
        self.assertTrue(path.startswith(self.path("out", "android-device")))

    def test_png_size(self):
        png = self.make_screen()
        self.assertEqual(ad.png_size(png), (20, 10))


# ---------------------------------------------------------------- uiautomator

def node(text="", desc="", pkg=PKG, bounds="[0,0][10,10]", checkable=False, checked=False, clickable=False,
         cls="android.widget.TextView", close=True):
    return (f'<node index="0" text="{text}" resource-id="" class="{cls}" package="{pkg}" content-desc="{desc}" '
            f'checkable="{str(checkable).lower()}" checked="{str(checked).lower()}" clickable="{str(clickable).lower()}" '
            f'enabled="true" bounds="{bounds}"' + (" />" if close else ">"))


UI_XML = ("<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation=\"0\">"
          + node(cls="android.widget.FrameLayout", bounds="[0,0][1080,2400]", close=False)
          + node("Settings", bounds="[40,100][400,180]")
          + node("Dark mode", bounds="[40,300][600,380]")
          + node(cls="android.widget.Switch", checkable=True, checked=True, clickable=True, bounds="[900,310][1040,370]")
          + node("Vibrate", bounds="[40,500][600,580]")
          + node(cls="android.widget.Switch", checkable=True, clickable=True, bounds="[900,510][1040,570]")
          + node(desc="Back", clickable=True, bounds="[0,0][100,100]")
          # 화면 밖(2400 아래)에 남아 있는 노드 — 덤프에는 있지만 화면에는 없다
          + node("Grant permission", clickable=True, bounds="[40,2600][1040,2900]")
          + node("no bounds", bounds="")
          + "</node>"
          + node("12:30", pkg="com.android.systemui", bounds="[0,0][200,60]")
          + "</hierarchy>")


class UiTest(ToolCase):
    def setUp(self):
        super().setUp()
        self.xml = self.path("dump.xml")
        with open(self.xml, "w", encoding="utf-8") as f:
            f.write(UI_XML)

    def test_ui_nodes_unit(self):
        nodes = ad.ui_nodes(UI_XML)
        self.assertEqual(len(nodes), 9)    # bounds 없는 노드는 뺀다
        sw = [n for n in nodes if n["checkable"]]
        self.assertEqual([(n["center"], n["checked"]) for n in sw], [([970, 340], True), ([970, 540], False)])
        back = next(n for n in nodes if n["desc"] == "Back")
        self.assertEqual((back["bounds"], back["clickable"], back["text"]), ([0, 0, 100, 100], True, ""))

    def test_list_includes_off_screen_nodes_and_warns(self):
        p = self.run_tool("ui", "--local", self.xml)
        self.assertExit(p, 0)
        lines = p.stdout.splitlines()
        self.assertEqual(len(lines), 6)       # 글자나 설명이 있는 노드만
        self.assertTrue(any("Grant permission" in l and "540  2750" in l for l in lines), lines)
        self.assertTrue(any(l.split()[:3] == ["50", "50", "C"] and "(Back)" in l for l in lines), lines)
        self.assertIn(f"※ 덤프에 담긴 앱: {PKG}", p.stderr)
        self.assertIn("덤프에는 화면에 없는 노드가 있을 수 있어요", p.stderr)
        self.assertNotIn("접근성 서비스", p.stderr)
        self.assertEqual(self.calls(), [])

    def test_dominant_package_reported_when_other_app_owns_dump(self):
        xml = UI_XML.replace(f'package="{PKG}"', 'package="com.kakao.talk"')
        path = self.path("other.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(xml)
        p = self.run_tool("ui", "--local", path)
        self.assertIn("※ 덤프에 담긴 앱: com.kakao.talk", p.stderr)

    def test_find(self):
        p = self.run_tool("ui", "--local", self.xml, "--find", "^Dark", "--json")
        self.assertExit(p, 0)
        nodes = json.loads(p.stdout)
        self.assertEqual([(n["text"], n["center"]) for n in nodes], [("Dark mode", [320, 340])])
        p = self.run_tool("ui", "--local", self.xml, "--find", "Back")
        self.assertExit(p, 0)
        self.assertIn("(Back)", p.stdout)
        p = self.run_tool("ui", "--local", self.xml, "--find", "Nope")
        self.assertExit(p, 1)
        self.assertEqual(p.stdout, "")

    def test_switch_near(self):
        p = self.run_tool("ui", "--local", self.xml, "--switch-near", "Vibrate")
        self.assertExit(p, 0)
        self.assertEqual(p.stdout.strip(), "970 540 unchecked")
        p = self.run_tool("ui", "--local", self.xml, "--switch-near", "Dark", "--json")
        self.assertEqual(json.loads(p.stdout), {"label": "Dark mode", "center": [970, 340], "checked": True})
        p = self.run_tool("ui", "--local", self.xml, "--switch-near", "Missing")
        self.assertExit(p, 1)
        self.assertIn("라벨 'Missing'", p.stderr)

    def test_switch_near_without_switches(self):
        path = self.path("plain.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write("<hierarchy>" + node("Vibrate", bounds="[0,0][10,10]") + "</hierarchy>")
        p = self.run_tool("ui", "--local", path, "--switch-near", "Vibrate")
        self.assertExit(p, 1)
        self.assertIn("체크 가능한 노드가 없습니다", p.stderr)

    def test_save_writes_dump(self):
        out = self.path("out", "saved.xml")
        self.assertExit(self.run_tool("ui", "--local", self.xml, "--save", out), 0)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(f.read(), UI_XML)

    def test_device_dump_with_accessibility_services(self):
        self.state["exec"]["uiautomator dump /dev/tty"] = {"text": UI_XML + "UI hierchary dumped to: /dev/tty\n"}
        self.save_state()
        p = self.run_tool("ui", "--find", "Settings")
        self.assertExit(p, 0)
        self.assertIn("Settings", p.stdout)
        self.assertIn("켜진 접근성 서비스 1개", p.stderr)
        self.assertEqual(self.writes(), [])

    def test_device_dump_retries_then_fails(self):
        self.state["exec"]["uiautomator dump /dev/tty"] = {"text": "ERROR: could not get idle state.\n", "code": 0}
        self.save_state()
        p = self.run_tool("ui")
        self.assertExit(p, 1)
        self.assertIn("uiautomator 덤프를 받지 못했습니다", p.stderr)
        self.assertEqual(sum(1 for a in self.calls() if "exec-out" in a), 4)

    # BUG: 덤프의 속성값은 XML 이스케이프돼 있는데(&amp; &lt; &quot; &#39;) ui_nodes 가 풀지 않는다.
    # "Sound & vibration" 이 "Sound &amp; vibration" 으로 나오고, --find "Sound & vibration" 이 못 찾는다.
    def test_xml_entities_are_unescaped(self):
        nodes = ad.ui_nodes("<hierarchy>" + node("Sound &amp; vibration", bounds="[0,0][10,10]") + "</hierarchy>")
        self.assertEqual(nodes[0]["text"], "Sound & vibration")


# ---------------------------------------------------------------- DataStore

def varint(n):
    n &= (1 << 64) - 1
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def field(num, wt, payload):
    key = varint(num << 3 | wt)
    if wt == 0:
        return key + varint(payload)
    if wt == 2:
        return key + varint(len(payload)) + payload
    return key + payload


def prefs_pb(entries):
    out = b""
    for key, value_msg in entries:
        entry = field(1, 2, key.encode()) + field(2, 2, value_msg)
        out += field(1, 2, entry)
    return out


PREFS = prefs_pb([
    ("dark", field(1, 0, 1)),
    ("off", field(1, 0, 0)),
    ("scale", field(2, 5, struct.pack("<f", 1.5))),
    ("count", field(3, 0, -3)),
    ("big", field(4, 0, 2 ** 40)),
    ("name", field(5, 2, "안녕".encode())),
    ("tags", field(6, 2, field(1, 2, b"b") + field(1, 2, b"a"))),
    ("ratio", field(7, 1, struct.pack("<d", 0.25))),
    ("blob", field(8, 2, b"\x01\xff")),
])
PREFS_DECODED = {"dark": True, "off": False, "scale": 1.5, "count": -3, "big": 2 ** 40, "name": "안녕",
                 "tags": ["a", "b"], "ratio": 0.25, "blob": "bytes:01ff"}


class DataStoreTest(ToolCase):
    def setUp(self):
        super().setUp()
        self.pb = self.path("settings.preferences_pb")
        with open(self.pb, "wb") as f:
            f.write(PREFS)

    def test_decode_unit(self):
        self.assertEqual(ad.decode_preferences(PREFS), PREFS_DECODED)
        self.assertEqual(ad.decode_preferences(b""), {})
        self.assertEqual(ad.signed64(2 ** 64 - 1), -1)

    def test_unknown_wire_type_raises(self):
        with self.assertRaises(ValueError):
            list(ad.wire_fields(bytes([1 << 3 | 3])))

    def test_local_file(self):
        p = self.run_tool("datastore", "--local", self.pb, "--json")
        self.assertExit(p, 0)
        self.assertEqual(json.loads(p.stdout), PREFS_DECODED)
        # --local 에서는 첫 위치 인자(package 자리)도 키로 본다
        p = self.run_tool("datastore", "--local", self.pb, "dark", "missing")
        self.assertExit(p, 0)
        self.assertEqual(p.stdout.splitlines(), ["dark=True", "missing=None"])
        self.assertEqual(self.calls(), [])

    def test_device_read(self):
        self.state["exec"][f"run-as {PKG} ls files/datastore"] = {"text": "settings.preferences_pb\n"}
        self.state["exec"][f"run-as {PKG} cat files/datastore/settings.preferences_pb"] = {"file": self.pb}
        self.save_state()
        p = self.run_tool("datastore", PKG, "name", "tags", "--json")
        self.assertExit(p, 0)
        self.assertEqual(json.loads(p.stdout), {"name": "안녕", "tags": ["a", "b"]})
        self.assertEqual(self.writes(), [])

    def test_device_file_option_skips_listing(self):
        self.state["exec"][f"run-as {PKG} cat files/datastore/x.preferences_pb"] = {"file": self.pb}
        self.save_state()
        p = self.run_tool("datastore", PKG, "--file", "x.preferences_pb", "dark")
        self.assertExit(p, 0)
        self.assertEqual(p.stdout.strip(), "dark=True")
        self.assertFalse(any(" ls " in " ".join(a) for a in self.calls()))

    def test_release_build_exits_1(self):
        self.state["exec"][f"run-as {PKG} ls files/datastore"] = {"text": f"run-as: package not debuggable: {PKG}\n",
                                                                  "code": 1}
        self.save_state()
        p = self.run_tool("datastore", PKG)
        self.assertExit(p, 1)
        self.assertIn("debuggable 빌드가 필요합니다", p.stderr)

    def test_ambiguous_file_exits_2(self):
        self.state["exec"][f"run-as {PKG} ls files/datastore"] = {"text": "a.preferences_pb\nb.preferences_pb\n"}
        self.save_state()
        p = self.run_tool("datastore", PKG)
        self.assertExit(p, 2)
        self.assertIn("--file", p.stderr)

    def test_cat_failure_exits_1(self):
        self.state["exec"][f"run-as {PKG} ls files/datastore"] = {"text": "s.preferences_pb\n"}
        self.state["exec"][f"run-as {PKG} cat files/datastore/s.preferences_pb"] = {"text": "run-as: couldn't stat\n"}
        self.save_state()
        p = self.run_tool("datastore", PKG)
        self.assertExit(p, 1)
        self.assertIn("읽기 실패", p.stderr)

    def test_no_package_exits_2_without_adb(self):
        self.assertExit(self.run_tool("datastore"), 2)
        self.assertEqual(self.calls(), [])


# ---------------------------------------------------------------- CLI 검증

class CliTest(ToolCase):
    def test_usage_errors_exit_2_without_adb(self):
        for args in ([], ["nope"], ["tap", "1", "2"], ["tap", "x", "2", "--package", PKG],
                     ["swipe", "1", "2", "3", "4", "--package", PKG], ["guard"], ["px", "a.png"],
                     ["diff"], ["restore"], ["stats", "a.png", "--threshold", "hi"]):
            with self.subTest(args=args):
                self.assertExit(self.run_tool(*args), 2)
        self.assertEqual(self.calls(), [])

    def test_help(self):
        p = self.run_tool("--help")
        self.assertExit(p, 0)
        for cmd in ("devices", "state", "guard", "shot", "px", "stats", "crop", "ui", "datastore",
                    "snapshot", "diff", "restore", "tap", "swipe"):
            self.assertIn(cmd, p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=1)
