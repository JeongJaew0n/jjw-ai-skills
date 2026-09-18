#!/usr/bin/env python3
"""scan-sources.py — Obsidian 플러그인 프로젝트의 트러블슈팅 문서를 훑어
이 스킬의 references/ 에 아직 없는 것을 찾는다.

색인은 시간이 지나면 낡는다. 새 프로젝트에서 트러블슈팅을 쓰고 여기로
가져오는 것을 잊으면, 이 스킬은 조용히 옛 지식만 갖게 된다.

읽기 전용이다. 복사하지 않고 **무엇이 빠졌는지만** 알려준다 —
가져올지는 사람이 판단한다(project-specific 은 대개 가져오면 안 된다).
"""
import json, os, sys, glob, hashlib

DEV = os.path.expanduser("~/my/Dev")
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(SKILL, "references")


def md_files(d):
    return [p for p in sorted(glob.glob(os.path.join(d, "*.md")))
            if os.path.basename(p) != "README.md"]


def body_hash(p):
    """출처 주석을 뺀 본문 해시. 복사본과 원본을 비교하려면 머리말을 걷어내야 한다."""
    lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
    while lines and (lines[0].startswith("> 출처:")
                     or lines[0].startswith("> 원본이 정본")
                     or not lines[0].strip()):
        lines.pop(0)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def is_obsidian_plugin(d):
    """Obsidian 플러그인 판정 — 루트 manifest.json 의 minAppVersion.

    Chrome 확장도 manifest.json 을 쓰지만 그쪽은 manifest_version 이다.
    이 구분이 없으면 pmset·Chrome 같은 무관한 트러블슈팅이 섞여 들어온다.
    """
    m = os.path.join(d, "manifest.json")
    if not os.path.isfile(m):
        return False
    try:
        j = json.load(open(m, encoding="utf-8"))
    except Exception:
        return False
    return "minAppVersion" in j and "manifest_version" not in j


def title(p):
    for l in open(p, encoding="utf-8", errors="replace"):
        if l.startswith("# "):
            return l[2:].strip()
    return "(제목 없음)"


def main():
    if not os.path.isdir(DEV):
        print(f"{DEV} 가 없습니다.", file=sys.stderr)
        return 3

    have = {os.path.basename(p): body_hash(p) for p in md_files(REFS)}
    cands = sorted(
        d for d in glob.glob(os.path.join(DEV, "*"))
        if os.path.isdir(os.path.join(d, "docs", "troubleshootings")))
    projects = [d for d in cands if is_obsidian_plugin(d)]
    skipped = [d for d in cands if d not in projects]

    if not projects:
        print("Obsidian 플러그인 프로젝트를 찾지 못했습니다.")
        return 0

    new, changed, ok, proj_specific = [], [], 0, []
    for proj in projects:
        name = os.path.basename(proj)
        base = os.path.join(proj, "docs", "troubleshootings")
        for p in md_files(os.path.join(base, "reusable")):
            f = os.path.basename(p)
            if f not in have:
                new.append((name, f, title(p)))
            elif have[f] != body_hash(p):
                changed.append((name, f, title(p)))
            else:
                ok += 1
        for p in md_files(os.path.join(base, "project-specific")):
            proj_specific.append((name, os.path.basename(p), title(p)))

    print(f"Obsidian 플러그인 프로젝트 {len(projects)}개: "
          f"{', '.join(os.path.basename(d) for d in projects)}")
    if skipped:
        print(f"제외 {len(skipped)}개 (Obsidian 플러그인 아님): "
              f"{', '.join(os.path.basename(d) for d in skipped)}")
    print()
    if new:
        print(f"== references/ 에 없는 reusable 문서 {len(new)}개 ==")
        for n, f, t in new:
            print(f"  {n}/{f}\n    {t}")
        print("  → 가져오려면 해당 파일을 references/ 로 복사하고 SKILL.md 색인에 추가한다.\n")
    if changed:
        print(f"== 원본이 바뀐 문서 {len(changed)}개 ==")
        for n, f, t in changed:
            print(f"  {n}/{f}\n    {t}")
        print("  → 원본이 정본이다. references/ 쪽을 다시 가져온다.\n")
    if not new and not changed:
        print("== reusable 문서는 모두 최신 ==\n")
    print(f"일치 {ok}개")

    if proj_specific:
        print(f"\n== project-specific {len(proj_specific)}개 (가져오지 않는다) ==")
        for n, f, t in proj_specific:
            print(f"  {n}/{f}  — {t}")
        print("  원인이 그 프로젝트 안에 있다는 뜻이다. 색인에 포인터로만 둔다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
