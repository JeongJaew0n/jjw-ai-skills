#!/usr/bin/env python3
"""
claude-sessions — 이 맥에서 돌고 있는 Claude Code 세션을 보여준다.

읽기 전용이다. 아무것도 바꾸지 않는다.

출처는 두 가지를 대조한다.
  1. ~/.claude/sessions/<pid>.json  Claude Code 가 스스로 쓰는 레지스트리.
                                    이름·폴더·상태(busy/idle)가 여기 있다.
  2. ps                             실제로 살아 있는 claude 프로세스.

레지스트리만 믿으면 안 된다. 파일이 없는데 살아 있는 세션이 실제로 있었다
(docs/plans/claude-sessions/plan.md). 반대로 죽은 pid 의 파일이 남을 수도 있다.

  claude-sessions.py          살아 있는 세션
  claude-sessions.py --all    남은 레지스트리 파일(죽은 pid)까지
  claude-sessions.py --json   기계 판독용
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REGISTRY = Path.home() / ".claude" / "sessions"
STATUS_KO = {"busy": "작업 중", "idle": "대기", None: "알 수 없음"}


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 남의 프로세스지만 살아는 있다


def ps_table():
    """pid → (ppid, command). ps 한 번으로 전부 받는다."""
    out = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True
    ).stdout
    table = {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3:
            table[int(parts[0])] = (int(parts[1]), parts[2])
    return table


def is_claude(command):
    """claude CLI 본체만 고른다. 헬퍼·MCP 자식 프로세스는 제외."""
    exe = command.split(" ", 1)[0]
    return os.path.basename(exe) == "claude"


def find_self(table):
    """부모 체인을 올라가며 이 스크립트를 띄운 claude 를 찾는다."""
    pid = os.getpid()
    for _ in range(30):
        entry = table.get(pid)
        if not entry:
            return None
        ppid, command = entry
        if pid != os.getpid() and is_claude(command):
            return pid
        if ppid <= 1:
            return None
        pid = ppid
    return None


def lsof_cwd(pid):
    """레지스트리에 없는 프로세스만 쓴다 — 개당 수십 ms 라 전부에 돌리지 않는다."""
    try:
        out = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        for line in out.splitlines():
            if line.startswith("n"):
                return line[1:]
    except Exception:
        pass
    return None


def short(path):
    if not path:
        return "?"
    home = str(Path.home())
    if path == home:
        return "~"
    return "~" + path[len(home):] if path.startswith(home + "/") else path


def ago(ms):
    if not ms:
        return "?"
    sec = max(0, int(time.time() - ms / 1000))
    if sec < 60:
        return "방금"
    if sec < 3600:
        return f"{sec // 60}분 전"
    if sec < 86400:
        return f"{sec // 3600}시간 전"
    return f"{sec // 86400}일 전"


def collect(include_stale):
    table = ps_table()
    me = find_self(table)
    live_claude = {pid for pid, (_, cmd) in table.items() if is_claude(cmd)}

    sessions, seen = [], set()
    for f in sorted(REGISTRY.glob("*.json")) if REGISTRY.is_dir() else []:
        try:
            d = json.loads(f.read_text())
            pid = int(d.get("pid") or f.stem)
        except Exception:
            continue
        is_alive = pid in live_claude or alive(pid)
        seen.add(pid)
        if not is_alive and not include_stale:
            continue
        sessions.append({
            "pid": pid,
            "name": d.get("name"),
            "cwd": d.get("cwd"),
            "status": d.get("status") if is_alive else None,
            "kind": d.get("kind"),
            "updatedAt": d.get("updatedAt"),
            "sessionId": d.get("sessionId"),
            "source": "registry" if is_alive else "stale",
            "self": pid == me,
        })

    for pid in sorted(live_claude - seen):
        sessions.append({
            "pid": pid, "name": None, "cwd": lsof_cwd(pid), "status": None,
            "kind": None, "updatedAt": None, "sessionId": None,
            "source": "unregistered", "self": pid == me,
        })
    return sessions


def render(sessions):
    live = [s for s in sessions if s["source"] != "stale"]
    others = [s for s in live if not s["self"]]
    busy = sum(1 for s in others if s["status"] == "busy")
    idle = sum(1 for s in others if s["status"] == "idle")
    unknown = len(others) - busy - idle

    if not others:
        print("이 세션 말고 돌고 있는 Claude Code 세션은 없습니다.")
    else:
        parts = [f"작업 중 {busy}"] if busy else []
        parts += [f"대기 {idle}"] if idle else []
        parts += [f"상태 모름 {unknown}"] if unknown else []
        print(f"이 세션 말고 {len(others)}개가 돌고 있습니다 ({', '.join(parts)}).")
    print()

    order = {"busy": 0, "idle": 1, None: 2}
    rows = sorted(
        sessions,
        key=lambda s: (s["source"] == "stale", order.get(s["status"], 2),
                       -(s["updatedAt"] or 0)),
    )
    head = ("상태", "이름", "폴더", "마지막 활동", "pid")
    body = []
    for s in rows:
        if s["source"] == "stale":
            state = "종료됨"
        else:
            state = STATUS_KO.get(s["status"], s["status"])
        name = s["name"] or "(레지스트리 없음)"
        if s["self"]:
            name += "  ← 지금 이 세션"
        body.append((state, name, short(s["cwd"]), ago(s["updatedAt"]), str(s["pid"])))

    widths = [max(_w(r[i]) for r in [head] + body) for i in range(len(head))]
    for r in [head] + body:
        print("  ".join(_pad(c, widths[i]) for i, c in enumerate(r)).rstrip())

    if any(s["source"] == "unregistered" for s in sessions):
        print()
        print("(레지스트리 없음) — 프로세스는 살아 있는데 ~/.claude/sessions 에 파일이 없는 세션입니다.")
        print("  이름·상태는 알 수 없고, 폴더는 프로세스에서 직접 읽었습니다.")


def _w(s):
    """한글은 터미널에서 두 칸을 차지한다."""
    return sum(2 if ord(c) >= 0x1100 else 1 for c in s)


def _pad(s, width):
    return s + " " * (width - _w(s))


def main(argv):
    include_stale = "--all" in argv
    sessions = collect(include_stale)
    if "--json" in argv:
        print(json.dumps(sessions, ensure_ascii=False, indent=2))
    else:
        render(sessions)


if __name__ == "__main__":
    main(sys.argv[1:])
