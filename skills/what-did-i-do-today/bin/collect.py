#!/usr/bin/env python3
"""collect — 최근 기간에 사용자가 실제로 입력한 프롬프트를 세션별로 모은다.

전사에는 사용자가 친 것과 시스템·AI 가 넣은 것이 같은 `type: "user"` 로 섞여 들어간다.
도구 실행 결과, 시스템 리마인더, 다른 세션이 보낸 메시지, 작업 완료 알림이 전부
같은 자리에 쌓이므로, 구분하지 않고 세면 "오늘 뭐 했나" 가 노이즈에 묻힌다.

다행히 스키마에 판별자가 있다.

  origin.kind == "human"                      사람이 한 것
  origin.kind in (task-notification, peer)    시스템·다른 세션이 넣은 것
  promptSource == typed|queued|suggestion_accepted   사람이 입력한 경로
  promptSource == system|sdk                  프로그램이 넣은 경로
  isMeta == true                              주입된 내용
  isSidechain == true                         서브에이전트 내부 대화

사용법:
  collect.py                 최근 24시간
  collect.py --hours 48
  collect.py --days 7
  collect.py --json          구조화 출력
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

CLAUDE_PROJECTS = os.path.expanduser("~/.claude/projects")
CODEX_SESSIONS = os.path.expanduser("~/.codex/sessions")

HUMAN_SOURCES = {"typed", "queued", "suggestion_accepted"}
MACHINE_SOURCES = {"system", "sdk"}

# 사용자가 친 글이 아니라 클라이언트가 끼워 넣는 표식들. 이게 본문에 있으면
# 사람이 입력한 것으로 세지 않는다.
INJECTED_MARKERS = (
    "<bash-stdout>",
    "<bash-stderr>",
    "<system-reminder>",
    "<command-name>",
    "<command-message>",
    "<local-command-stdout>",
    "<cross-session-message",
    "Caveat: The messages below were generated",
    "[Request interrupted by user",
)


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                return None          # 도구 결과는 사용자 발화가 아니다
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts) if parts else None
    return None


def classify(entry, body):
    """(분류, 사유) 를 준다. 분류는 human / machine / unknown."""
    if entry.get("isSidechain"):
        return "machine", "서브에이전트"
    if entry.get("isMeta"):
        return "machine", "주입된 내용"

    origin = entry.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    source = entry.get("promptSource")

    if kind and kind != "human":
        return "machine", kind
    if source in MACHINE_SOURCES:
        return "machine", source

    for marker in INJECTED_MARKERS:
        if marker in body:
            return "machine", marker.strip("<>[ ")

    if kind == "human" or source in HUMAN_SOURCES:
        return "human", source or "human"

    # `!` 로 직접 친 셸 명령. 판별 필드가 없던 시절 전사에도 이 표식은 남아 있다.
    if "<bash-input>" in body:
        return "human", "bash-input"

    # 두 필드가 모두 없는 옛 전사. 사람으로 단정하지 않고 따로 표시한다.
    return "unknown", "판별 정보 없음"


def collect_claude(cutoff):
    sessions = {}
    for path in glob.glob(os.path.join(CLAUDE_PROJECTS, "*", "*.jsonl")):
        # 파일 전체가 기간 밖이면 읽지 않는다 (전사는 100MB 단위로 커진다)
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) < cutoff:
                continue
        except OSError:
            continue

        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("type") != "user":
                    continue
                ts = parse_ts(entry.get("timestamp"))
                if ts is None or ts < cutoff:
                    continue
                body = text_of(entry.get("message", {}).get("content"))
                if body is None or not body.strip():
                    continue

                verdict, reason = classify(entry, body)
                sid = entry.get("sessionId") or os.path.basename(path)[:8]
                sess = sessions.setdefault(sid, {
                    "session_id": sid,
                    "cwd": entry.get("cwd"),
                    "git_branch": entry.get("gitBranch"),
                    "first": ts, "last": ts,
                    "human": [], "machine": 0, "unknown": [],
                    "machine_reasons": {},
                })
                sess["first"] = min(sess["first"], ts)
                sess["last"] = max(sess["last"], ts)
                if entry.get("cwd"):
                    sess["cwd"] = entry["cwd"]

                if verdict == "machine":
                    sess["machine"] += 1
                    sess["machine_reasons"][reason] = sess["machine_reasons"].get(reason, 0) + 1
                else:
                    bucket = sess["human"] if verdict == "human" else sess["unknown"]
                    bucket.append({"at": ts, "text": body.strip(), "source": reason})
    return sessions


def collect_codex(cutoff):
    """Codex 는 참고용이다. 사람 입력을 표시하는 필드가 없어 확정할 수 없다."""
    rows = []
    for path in glob.glob(os.path.join(CODEX_SESSIONS, "**", "*.jsonl"), recursive=True):
        try:
            if datetime.fromtimestamp(os.path.getmtime(path), timezone.utc) < cutoff:
                continue
        except OSError:
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                payload = entry.get("payload") or {}
                if entry.get("type") != "event_msg" or payload.get("type") != "user_message":
                    continue
                ts = parse_ts(entry.get("timestamp"))
                if ts is None or ts < cutoff:
                    continue
                msg = str(payload.get("message") or "").strip()
                if not msg:
                    continue
                rows.append({"at": ts, "text": msg, "file": os.path.basename(path)})
    return rows


def dedupe(items):
    """재시도·분기로 같은 문장이 여러 번 기록된다. 처음 것만 남긴다."""
    seen, out = set(), []
    for item in sorted(items, key=lambda x: x["at"]):
        key = item["text"]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main():
    ap = argparse.ArgumentParser(description="최근 기간의 내 입력을 세션별로 모은다")
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--days", type=float)
    ap.add_argument("--codex", action="store_true", help="Codex 세션도 포함 (판별 불확실)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-chars", type=int, default=0, help="프롬프트 표시 길이 제한 (0=제한 없음)")
    args = ap.parse_args()

    hours = args.days * 24 if args.days else args.hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    if not os.path.isdir(CLAUDE_PROJECTS):
        print(f"전사 디렉터리가 없습니다: {CLAUDE_PROJECTS}", file=sys.stderr)
        return 1

    sessions = collect_claude(cutoff)
    for sess in sessions.values():
        sess["human"] = dedupe(sess["human"])
        sess["unknown"] = dedupe(sess["unknown"])

    active = [s for s in sessions.values() if s["human"] or s["unknown"]]
    active.sort(key=lambda s: s["last"], reverse=True)

    codex_rows = dedupe(collect_codex(cutoff)) if args.codex else []

    if args.json:
        def ser(s):
            out = dict(s)
            out["first"] = s["first"].isoformat()
            out["last"] = s["last"].isoformat()
            for k in ("human", "unknown"):
                out[k] = [{"at": i["at"].isoformat(), "text": i["text"], "source": i["source"]} for i in s[k]]
            return out
        print(json.dumps({
            "cutoff": cutoff.isoformat(),
            "hours": hours,
            "sessions": [ser(s) for s in active],
            "codex": [{"at": r["at"].isoformat(), "text": r["text"], "file": r["file"]} for r in codex_rows],
        }, ensure_ascii=False, indent=2))
        return 0

    local_cut = cutoff.astimezone()
    print(f"기간: {local_cut:%Y-%m-%d %H:%M} 이후 (최근 {hours:g}시간)")
    total_h = sum(len(s["human"]) for s in active)
    total_m = sum(s["machine"] for s in active)
    total_u = sum(len(s["unknown"]) for s in active)
    print(f"세션 {len(active)}개 · 직접 입력 {total_h}건 · AI/시스템 {total_m}건"
          + (f" · 판별불가 {total_u}건" if total_u else ""))

    if not active:
        print("\n이 기간에 입력한 내용이 없습니다.")
        return 0

    by_project = {}
    for sess in active:
        by_project.setdefault(sess["cwd"] or "(경로 불명)", []).append(sess)

    for cwd, group in sorted(by_project.items(), key=lambda kv: -max(s["last"].timestamp() for s in kv[1])):
        print(f"\n━━ {cwd}")
        for sess in sorted(group, key=lambda s: s["last"], reverse=True):
            first_l, last_l = sess["first"].astimezone(), sess["last"].astimezone()
            span = (f"{first_l:%m/%d %H:%M}~{last_l:%H:%M}" if first_l.date() == last_l.date()
                    else f"{first_l:%m/%d %H:%M}~{last_l:%m/%d %H:%M}")
            head = (f"  [{sess['session_id'][:8]}] {span}"
                    f" · 직접 {len(sess['human'])}건 · AI/시스템 {sess['machine']}건")
            if sess["git_branch"]:
                head += f" · {sess['git_branch']}"
            print(head)
            for item in sess["human"]:
                text = " ".join(item["text"].split())
                if args.max_chars and len(text) > args.max_chars:
                    text = text[:args.max_chars] + "…"
                print(f"      {item['at'].astimezone():%H:%M}  {text}")
            for item in sess["unknown"]:
                text = " ".join(item["text"].split())
                if args.max_chars and len(text) > args.max_chars:
                    text = text[:args.max_chars] + "…"
                print(f"      {item['at'].astimezone():%H:%M}  [판별불가] {text}")

    if args.codex:
        print(f"\n━━ Codex 세션 ({len(codex_rows)}건) — 사람 입력 표시가 없어 확정 불가")
        for row in codex_rows:
            text = " ".join(row["text"].split())
            print(f"      {row['at'].astimezone():%m/%d %H:%M}  {text[:120]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
