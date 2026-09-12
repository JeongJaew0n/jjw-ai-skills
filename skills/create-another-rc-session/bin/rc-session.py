#!/usr/bin/env python3
"""rc-session — 다른 디렉터리에 Remote Control 서버를 띄워 그 디렉터리에 뿌리내린 세션을 만든다.

Remote Control(폰 / claude.ai/code)로 붙은 세션에서는 `/cd` 가 막혀 있다:

    /cd isn't available over Remote Control.

그래서 "폰에서 다른 폴더로 옮겨 새 컨텍스트로 시작" 이 안 된다. 해법은 cd 가 아니라
대상 디렉터리에 RC 서버를 새로 띄우는 것이다. 그러면 폰에서 그 디렉터리에 뿌리내린
빈 세션으로 갈아탈 수 있다 (= /cd + /clear 와 같은 결과).

서브커맨드는 위험도 순으로 분리돼 있다. 한 번에 다 하는 경로는 일부러 두지 않았다.

  audit   대상 디렉터리의 신뢰 상태와 안전성만 조사한다 (변경 없음)
  trust   신뢰 플래그를 기록한다 (보안 게이트 우회 — 확인 플래그 필수)
  start   RC 서버를 띄우고 접속 URL 을 뽑는다
  list    지금 떠 있는 RC 세션 목록
  stop    RC 서버 종료
"""

import argparse
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime

CLAUDE_JSON = os.path.expanduser("~/.claude.json")
SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")

# claude 실서버는 진짜 바이너리로 띄운다. PATH 의 `claude` 는 cmux 래퍼로 잡힐 수 있고
# (그 래퍼는 --session-id 와 --settings 를 주입한다), ~/.local/bin/claude 는 현재
# 활성 버전을 가리키는 심볼릭 링크라 versions/ 를 mtime 으로 고르는 것보다 정확하다.
CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")

# Claude Code 가 디렉터리를 열 때 자동으로 읽어 실행까지 이어질 수 있는 것들.
# 이것이 있는 디렉터리의 신뢰 게이트는 이 도구가 절대 우회하지 않는다.
EXECUTABLE_CONFIG = [
    ".claude",          # settings.json, hooks, 스킬
    "CLAUDE.md",        # 자동 주입되는 지시문
    "CLAUDE.local.md",
    ".mcp.json",        # MCP 서버 정의
    ".claude.json",
]

# 빈 디렉터리로 간주할 수 있는 항목. git init 직후 상태를 허용하기 위한 것.
INERT_ENTRIES = {".git", ".gitignore", ".DS_Store"}


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load_claude_json():
    try:
        with open(CLAUDE_JSON, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(f"{CLAUDE_JSON} 이 없습니다. claude 를 한 번도 실행하지 않은 계정입니다.")
    except ValueError as e:
        die(f"{CLAUDE_JSON} 파싱 실패: {e}\n손상된 설정을 덮어쓰지 않기 위해 중단합니다.")


def trust_state(target):
    """대상 디렉터리의 신뢰 상태. (등록됨, 신뢰됨) 를 준다."""
    entry = load_claude_json().get("projects", {}).get(target)
    if entry is None:
        return False, False
    return True, entry.get("hasTrustDialogAccepted") is True


def audit_dir(target):
    """디렉터리 내용으로 신뢰 우회 허용 여부를 판정한다.

    INERT      비어 있음 (또는 git 골격뿐) — 우회할 보안 결정이 실질적으로 없다
    HAS_CONFIG Claude 가 자동 로드해 실행까지 갈 수 있는 설정이 있다 — 우회 금지
    HAS_CONTENT그 외 내용물이 있다 — 확인 후에만
    """
    if not os.path.isdir(target):
        return "MISSING", [], []

    entries = sorted(os.listdir(target))
    found_config = [e for e in entries if e in EXECUTABLE_CONFIG]
    others = [e for e in entries if e not in INERT_ENTRIES and e not in EXECUTABLE_CONFIG]

    if found_config:
        return "HAS_CONFIG", found_config, others
    if others:
        return "HAS_CONTENT", [], others
    return "INERT", [], []


def cmd_audit(args):
    target = os.path.abspath(os.path.expanduser(args.dir))
    registered, trusted = trust_state(target)
    verdict, config, others = audit_dir(target)

    print(f"대상       : {target}")
    print(f"존재       : {'예' if os.path.isdir(target) else '아니오'}")
    print(f"등록됨     : {'예' if registered else '아니오'} (~/.claude.json projects)")
    print(f"신뢰됨     : {'예' if trusted else '아니오'}")
    print(f"내용 판정  : {verdict}")
    if config:
        print(f"  자동 로드 설정: {', '.join(config)}")
    if others:
        shown = ", ".join(others[:12]) + (" …" if len(others) > 12 else "")
        print(f"  기타 항목({len(others)}): {shown}")

    print()
    if trusted:
        print("→ 이미 신뢰된 디렉터리입니다. trust 단계는 필요 없습니다. 바로 start 하세요.")
        return 0
    if verdict == "MISSING":
        print("→ 디렉터리가 없습니다. 먼저 만들어야 합니다 (start --create 또는 직접 mkdir).")
        return 0
    if verdict == "HAS_CONFIG":
        print("→ 신뢰 우회 불가. 이 디렉터리에는 Claude 가 열 때 자동으로 읽고 실행까지")
        print("  이어질 수 있는 설정이 있습니다. 신뢰 다이얼로그가 막으려는 대상이 정확히")
        print("  이것이므로 이 도구는 우회하지 않습니다.")
        print(f"  맥 앞에서 직접 승인하세요:  cd {target} && claude")
        return 0
    if verdict == "HAS_CONTENT":
        print("→ 내용물이 있는 디렉터리입니다. 사용자에게 위 목록을 보여주고 확인을 받은 뒤에만")
        print("  trust --i-understand-trust-bypass 로 진행하세요.")
        return 0
    print("→ 비어 있습니다. 우회할 보안 결정이 실질적으로 없습니다.")
    print("  사용자 확인 후 trust --i-understand-trust-bypass 로 진행할 수 있습니다.")
    return 0


def cmd_trust(args):
    target = os.path.abspath(os.path.expanduser(args.dir))

    if not args.i_understand_trust_bypass:
        die("이 명령은 워크스페이스 신뢰 다이얼로그(보안 게이트)를 우회합니다.\n"
            "사용자에게 그 사실을 알리고 확인을 받은 뒤 --i-understand-trust-bypass 를 붙여\n"
            "다시 실행하세요. 먼저 audit 으로 디렉터리 내용을 확인하세요.")

    if not os.path.isdir(target):
        die(f"디렉터리가 없습니다: {target}")

    registered, trusted = trust_state(target)
    if trusted:
        print(f"이미 신뢰됨: {target} (변경 없음)")
        return 0

    verdict, config, others = audit_dir(target)
    if verdict == "HAS_CONFIG":
        die(f"거부: {target} 에 자동 로드 설정이 있습니다 ({', '.join(config)}).\n"
            "신뢰 다이얼로그가 막으려는 것이 정확히 이것이라 이 도구는 우회하지 않습니다.\n"
            f"맥 앞에서 직접 승인하세요:  cd {target} && claude")

    data = load_claude_json()

    # 쓰기 전 백업. 이 파일에는 계정 전체 설정이 들어 있어 되돌릴 수 없으면 안 된다.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{CLAUDE_JSON}.bak-{stamp}"
    shutil.copy2(CLAUDE_JSON, backup)

    projects = data.setdefault("projects", {})
    entry = projects.setdefault(target, {})
    # 기존 항목의 다른 키는 건드리지 않는다. 신뢰 플래그 하나만 올린다.
    entry.setdefault("allowedTools", [])
    entry.setdefault("mcpContextUris", [])
    entry.setdefault("mcpServers", {})
    entry.setdefault("enabledMcpjsonServers", [])
    entry.setdefault("disabledMcpjsonServers", [])
    entry["hasTrustDialogAccepted"] = True

    # 원자적 교체. 도중에 죽어도 반쪽 JSON 이 남지 않게 한다.
    tmp = f"{CLAUDE_JSON}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CLAUDE_JSON)

    print(f"신뢰 기록  : {target}")
    print(f"백업       : {backup}")
    print(f"판정       : {verdict}" + (f" (내용 {len(others)}개)" if others else " (비어 있음)"))
    print()
    print("이것은 보안 다이얼로그 우회입니다. 사용자에게 반드시 고지하세요.")
    print(f"되돌리기   : cp {backup} {CLAUDE_JSON}")
    return 0


def build_start_cmd(target, name, extra):
    cmd = [CLAUDE_BIN, "remote-control", "--create-session-in-dir", "--spawn", "same-dir"]
    if name:
        cmd += ["--name", name]
    cmd += extra
    return cmd


def cmd_start(args):
    target = os.path.abspath(os.path.expanduser(args.dir))

    if args.create and not os.path.isdir(target):
        os.makedirs(target, exist_ok=True)
        print(f"생성       : {target}")

    if not os.path.isdir(target):
        die(f"디렉터리가 없습니다: {target}\n--create 를 붙이거나 직접 만드세요.")

    if not os.path.exists(CLAUDE_BIN):
        die(f"claude 바이너리를 찾지 못했습니다: {CLAUDE_BIN}")

    registered, trusted = trust_state(target)
    if not trusted:
        die(f"거부: {target} 는 신뢰되지 않은 디렉터리입니다.\n"
            "이대로 띄우면 서버가 즉시 죽습니다:\n"
            "  Error: Workspace not trusted. Please run `claude` in <경로> first ...\n"
            "먼저 audit 으로 내용을 확인하고, 사용자 확인을 받아 trust 를 실행하세요.")

    log = os.path.abspath(os.path.expanduser(args.log)) if args.log else os.path.join(
        target, ".rc-session.log")
    cmd = build_start_cmd(target, args.name, args.extra or [])

    print(f"대상       : {target}")
    print(f"바이너리   : {CLAUDE_BIN} -> {os.path.realpath(CLAUDE_BIN)}")
    print(f"명령       : {' '.join(cmd)}")
    print(f"로그       : {log}")

    if args.dry_run:
        print("\n--dry-run: 서버를 띄우지 않았습니다.")
        return 0

    with open(log, "wb") as out:
        proc = subprocess.Popen(cmd, cwd=target, stdout=out, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    print(f"PID        : {proc.pid}")

    # 서버가 연결을 맺고 URL 을 찍기까지 시간이 걸린다. 로그를 폴링해 조기 종료도 잡는다.
    env_url = session_id = None
    deadline = time.time() + args.wait
    while time.time() < deadline:
        time.sleep(1)
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = ""
        if "Workspace not trusted" in text:
            die("서버가 신뢰 오류로 죽었습니다. audit → trust 를 먼저 하세요.\n"
                f"로그: {log}")
        m = re.search(r"https://claude\.ai/code\?environment=(env_[A-Za-z0-9]+)", text)
        if m:
            env_url = m.group(0)
        m2 = re.search(r"session_[A-Za-z0-9]+", text)
        if m2:
            session_id = m2.group(0)
        if env_url and session_id:
            break
        if proc.poll() is not None:
            die(f"서버가 조기 종료했습니다 (exit={proc.returncode}).\n로그: {log}")

    print()
    if env_url:
        print(f"환경 링크  : {env_url}")
    if session_id:
        # 세션 직링크는 로그에 OSC-8 하이퍼링크로 박혀 있어 id 만 뽑아 조립한다.
        print(f"세션 직링크: https://claude.ai/code/{session_id}")
    if not (env_url or session_id):
        print(f"URL 을 아직 못 뽑았습니다. --wait 를 늘리거나 로그를 직접 보세요: {log}")

    print(f"\n종료       : {sys.argv[0]} stop --pid {proc.pid}")
    return 0


def rc_sessions():
    rows = []
    for path in sorted(glob.glob(os.path.join(SESSIONS_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        rows.append(d)
    return rows


def cmd_list(args):
    rows = rc_sessions()
    if not rows:
        print("세션 기록이 없습니다.")
        return 0
    print(f'{"PID":>7}  {"RC":<3} {"kind":<12} {"name":<32} cwd')
    for d in sorted(rows, key=lambda r: str(r.get("cwd"))):
        bridged = "예" if d.get("bridgeSessionId") else "-"
        if args.rc_only and not d.get("bridgeSessionId"):
            continue
        print(f'{d.get("pid", "?"):>7}  {bridged:<3} {str(d.get("kind")):<12} '
              f'{str(d.get("name"))[:32]:<32} {d.get("cwd")}')
    return 0


def cmd_stop(args):
    pid = args.pid
    # 남의 프로세스를 죽이지 않도록 세션 기록에 있는 PID 인지 먼저 확인한다.
    known = {d.get("pid") for d in rc_sessions()}
    if pid not in known and not args.force:
        die(f"PID {pid} 는 ~/.claude/sessions 기록에 없습니다.\n"
            "다른 프로세스를 죽이지 않도록 중단합니다. 확실하면 --force 를 붙이세요.")
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        die(f"PID {pid} 가 이미 없습니다.")
    except PermissionError:
        die(f"PID {pid} 를 종료할 권한이 없습니다.")
    print(f"SIGTERM 보냄: {pid}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="다른 디렉터리에 RC 세션을 띄운다")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="신뢰 상태와 안전성 조사 (변경 없음)")
    a.add_argument("--dir", required=True)
    a.set_defaults(func=cmd_audit)

    t = sub.add_parser("trust", help="신뢰 플래그 기록 (보안 게이트 우회)")
    t.add_argument("--dir", required=True)
    t.add_argument("--i-understand-trust-bypass", action="store_true",
                   help="사용자에게 우회 사실을 고지하고 확인받았음")
    t.set_defaults(func=cmd_trust)

    s = sub.add_parser("start", help="RC 서버 기동")
    s.add_argument("--dir", required=True)
    s.add_argument("--name", help="claude.ai/code 에 표시될 이름")
    s.add_argument("--create", action="store_true", help="없으면 디렉터리 생성")
    s.add_argument("--log", help="로그 경로 (기본: <dir>/.rc-session.log)")
    s.add_argument("--wait", type=int, default=25, help="URL 대기 초 (기본 25)")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--extra", nargs=argparse.REMAINDER,
                   help="remote-control 에 그대로 넘길 추가 플래그")
    s.set_defaults(func=cmd_start)

    l = sub.add_parser("list", help="세션 목록")
    l.add_argument("--rc-only", action="store_true", help="RC 로 붙은 것만")
    l.set_defaults(func=cmd_list)

    k = sub.add_parser("stop", help="RC 서버 종료")
    k.add_argument("--pid", type=int, required=True)
    k.add_argument("--force", action="store_true")
    k.set_defaults(func=cmd_stop)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
