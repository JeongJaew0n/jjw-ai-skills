#!/usr/bin/env python3
"""cmux-where — 지금 이 터미널이 cmux 안에서 어디에 있는지, 형제 터미널이 어디에 있는지 보고한다.

`cmux tree` 는 pane 을 index 순으로 나열하는데 그 순서는 화면 배치 순서가 아니다.
2x2 격자에서 index 는 좌상 → 좌하 → 우상 → 우하 로 열 우선으로 돌기 때문에,
목록의 두 번째를 "우측" 으로 읽으면 실제로는 좌하단을 가리킨다.
좌우·상하를 알아낼 수 있는 유일한 경로는 `cmux rpc pane.list` 의 pixel_frame 이다.

사용법:
  cmux-where.py            # 내 위치 + 같은 workspace 의 형제
  cmux-where.py --all      # 모든 workspace 의 터미널 지도
  cmux-where.py --json     # 기계가 읽을 구조화 출력
"""

import json
import os
import subprocess
import sys

# pixel_frame 값은 460.5 처럼 소수가 나온다. 같은 행·열로 묶을 때 쓰는 허용 오차(px).
AXIS_TOLERANCE = 4.0


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def rpc(method, params=None):
    """cmux rpc 호출. 실패하면 None 을 준다 (호출부가 판단하게)."""
    cmd = ["cmux", "rpc", method]
    if params:
        cmd.append(json.dumps(params))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        die(f"cmux 호출 실패 ({method}): {exc}")
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def identify():
    """caller(= 이 터미널) 와 focused(= 지금 화면에 보이는 곳) 를 함께 얻는다.

    이 둘은 자주 다르다. 백그라운드 workspace 에서 도는 세션이 자기를 focused 로
    착각하면 남의 workspace 에 명령을 보내게 된다.
    """
    try:
        proc = subprocess.run(["cmux", "identify"], capture_output=True, text=True, timeout=15)
    except OSError as exc:
        die(f"cmux 를 실행할 수 없습니다: {exc}\n이 터미널이 cmux 안에서 돌고 있는지 확인하세요.")
    if proc.returncode != 0:
        die(f"cmux identify 실패:\n{proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except ValueError:
        die(f"cmux identify 출력을 파싱할 수 없습니다:\n{proc.stdout[:400]}")


def group_axis(values):
    """정렬된 좌표값들을 허용 오차로 묶어 대표값 리스트를 만든다."""
    buckets = []
    for v in sorted(values):
        if buckets and abs(v - buckets[-1]) <= AXIS_TOLERANCE:
            continue
        buckets.append(v)
    return buckets


def axis_index(value, buckets):
    for i, b in enumerate(buckets):
        if abs(value - b) <= AXIS_TOLERANCE:
            return i
    return len(buckets)


ORDINALS = ["첫", "두", "세", "네", "다섯", "여섯", "일곱", "여덟"]


def ordinal(i):
    return f"{ORDINALS[i]}번째" if i < len(ORDINALS) else f"{i + 1}번째"


def describe_position(row, col, nrows, ncols):
    """행/열 인덱스를 사람이 쓰는 방향 표현으로 바꾼다."""
    if nrows == 1 and ncols == 1:
        return "단독", "분할 없음 (이 workspace 에 pane 1개)"

    if nrows == 1:
        if ncols == 2:
            side = "좌측" if col == 0 else "우측"
        else:
            side = f"좌→우 {ordinal(col)}"
        return side, f"좌우 {ncols}분할 중 {ordinal(col)} (왼쪽부터)"

    if ncols == 1:
        if nrows == 2:
            side = "상단" if row == 0 else "하단"
        else:
            side = f"위→아래 {ordinal(row)}"
        return side, f"상하 {nrows}분할 중 {ordinal(row)} (위부터)"

    vert = "상" if row == 0 else ("하" if row == nrows - 1 else "중")
    horiz = "좌" if col == 0 else ("우" if col == ncols - 1 else "중")
    corner = f"{horiz}{vert}"
    return corner, f"{nrows}행 x {ncols}열 격자의 {row + 1}행 {col + 1}열"


def collect(workspace_id):
    """한 workspace 의 pane 기하 + surface 목록을 합쳐 위치가 붙은 터미널 목록을 만든다."""
    panes = (rpc("pane.list", {"workspace_id": workspace_id}) or {}).get("panes", [])
    surfaces = (rpc("surface.list", {"workspace_id": workspace_id}) or {}).get("surfaces", [])
    if not panes:
        return [], (0, 0)

    frames = {p["ref"]: p.get("pixel_frame") or {} for p in panes}
    xs = group_axis([f.get("x", 0) for f in frames.values()])
    ys = group_axis([f.get("y", 0) for f in frames.values()])
    nrows, ncols = len(ys), len(xs)

    rows = []
    for s in surfaces:
        frame = frames.get(s.get("pane_ref")) or {}
        col = axis_index(frame.get("x", 0), xs)
        row = axis_index(frame.get("y", 0), ys)
        label, detail = describe_position(row, col, nrows, ncols)
        binding = s.get("resume_binding") or {}
        rows.append({
            "surface_ref": s.get("ref"),
            "surface_id": s.get("id"),
            "pane_ref": s.get("pane_ref"),
            "title": s.get("title") or "",
            "type": s.get("type"),
            "selected_in_pane": bool(s.get("selected_in_pane")),
            "claude_session_id": binding.get("checkpoint_id"),
            "row": row,
            "col": col,
            "position": label,
            "position_detail": detail,
            "x": frame.get("x"),
            "y": frame.get("y"),
        })

    # 화면에서 읽는 순서(위→아래, 왼→오른쪽)로 정렬한다. index 순서는 이 순서가 아니다.
    rows.sort(key=lambda r: (r["row"], r["col"], not r["selected_in_pane"], r["surface_ref"]))
    return rows, (nrows, ncols)


def workspaces():
    data = rpc("workspace.list")
    if data is None:
        die("cmux rpc workspace.list 가 실패했습니다. cmux 앱이 떠 있는지 확인하세요.")
    return data if isinstance(data, list) else data.get("workspaces", [])


def build(show_all):
    ident = identify()
    caller = ident.get("caller") or {}
    focused = ident.get("focused") or {}

    all_ws = workspaces()
    by_ref = {w.get("ref"): w for w in all_ws}
    my_ws = by_ref.get(caller.get("workspace_ref"))
    if my_ws is None:
        die(f"내 workspace({caller.get('workspace_ref')}) 를 workspace.list 에서 찾지 못했습니다.")

    targets = all_ws if show_all else [my_ws]
    result = {
        "caller": caller,
        "focused": focused,
        "caller_is_focused": (
            caller.get("workspace_ref") == focused.get("workspace_ref")
            and caller.get("surface_ref") == focused.get("surface_ref")
        ),
        "my_workspace_ref": my_ws.get("ref"),
        "my_claude_session_id": os.environ.get("CLAUDE_CODE_SESSION_ID"),
        "workspaces": [],
    }

    for w in targets:
        rows, (nrows, ncols) = collect(w["id"])
        for r in rows:
            r["is_me"] = r["surface_ref"] == caller.get("surface_ref")
        result["workspaces"].append({
            "ref": w.get("ref"),
            "title": w.get("title") or "",
            "selected": bool(w.get("selected")),
            "is_mine": w.get("ref") == my_ws.get("ref"),
            "grid": {"rows": nrows, "cols": ncols},
            "terminals": rows,
        })
    return result


def render(data):
    out = []
    me = None
    for w in data["workspaces"]:
        for t in w["terminals"]:
            if t.get("is_me"):
                me = (w, t)
    caller = data["caller"]

    out.append("== 나 ==")
    if me:
        w, t = me
        out.append(f'경로   : {caller.get("window_ref")} > {w["ref"]} "{w["title"]}" > {t["pane_ref"]} > {t["surface_ref"]}')
        out.append(f'위치   : {t["position"]} — {t["position_detail"]}')
        if t["title"]:
            out.append(f'제목   : {t["title"]}')
    else:
        # --all 없이 호출했는데 내가 목록에 없으면 안 되는 상태다. 조용히 넘기지 않는다.
        out.append(f'경로   : {caller.get("window_ref")} > {caller.get("workspace_ref")} > '
                   f'{caller.get("pane_ref")} > {caller.get("surface_ref")}')
        out.append("위치   : 판정 실패 — pane 기하에서 내 surface 를 찾지 못했습니다")
    if data.get("my_claude_session_id"):
        out.append(f'세션   : {data["my_claude_session_id"]}')

    if not data["caller_is_focused"]:
        out.append("")
        out.append("== 주의: 내가 보이는 화면이 아니다 ==")
        out.append(f'지금 화면에 보이는 곳 : {focused_label(data)}')
        out.append("--workspace / --surface 를 생략한 cmux 명령은 저쪽으로 갈 수 있습니다.")
        out.append("다른 터미널을 조작할 때는 항상 --surface <ref> 를 명시하세요.")

    for w in data["workspaces"]:
        others = [t for t in w["terminals"] if not t.get("is_me")]
        header = f'== {w["ref"]} "{w["title"]}"'
        header += "  [내 workspace]" if w["is_mine"] else ""
        header += "  [화면에 보이는 중]" if w["selected"] else ""
        header += f'  ({w["grid"]["rows"]}행 x {w["grid"]["cols"]}열) =='
        out.append("")
        out.append(header)
        if not w["terminals"]:
            out.append("  (터미널 없음)")
            continue
        for t in w["terminals"]:
            mark = "←나 " if t.get("is_me") else "    "
            tab = "" if t["selected_in_pane"] else " [배경 탭]"
            claude = f'claude={t["claude_session_id"][:8]}' if t["claude_session_id"] else ""
            out.append(f'  {mark}{t["position"]:<6} {t["surface_ref"]:<11} {t["pane_ref"]:<9} {claude:<15}{tab}  {t["title"][:38]}')
        if others:
            out.append("  전송 예시:")
            for t in others[:4]:
                out.append(f'    {t["position"]} → cmux send --surface {t["surface_ref"]} "<text>" '
                           f'&& cmux send-key --surface {t["surface_ref"]} enter')
    return "\n".join(out)


def focused_label(data):
    f = data["focused"]
    return f'{f.get("workspace_ref")} > {f.get("pane_ref")} > {f.get("surface_ref")}'


def main():
    args = sys.argv[1:]
    show_all = "--all" in args
    as_json = "--json" in args
    for a in args:
        if a not in ("--all", "--json"):
            die(f"알 수 없는 인자: {a}\n사용법: cmux-where.py [--all] [--json]")

    data = build(show_all)
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))


if __name__ == "__main__":
    main()
