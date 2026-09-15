#!/usr/bin/env python3
"""skill-sync.py — Claude(~/.claude/skills)와 Codex(~/.codex/skills)의 스킬을 대조한다.

  skill-sync.py analyze [--json]
  skill-sync.py apply --direction claude-to-codex|codex-to-claude [--only a,b,c]

analyze 는 읽기 전용이다. apply 는 복사 전 반드시 백업한다.
어느 쪽도 **삭제하지 않는다** — 한쪽에만 있는 것은 채우고, 다른 것은 덮어쓸 뿐이다.
"""
import argparse, hashlib, json, os, shutil, sys, time

HOME = os.path.expanduser("~")
CLAUDE = os.path.join(HOME, ".claude", "skills")
CODEX = os.path.join(HOME, ".codex", "skills")
REPO = os.path.join(HOME, "my", "Dev", "jjw-ai-skills", "skills")
BACKUP_ROOT = os.path.join(HOME, ".claude", "backups")

TEXT_EXT = (".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt")


def skill_names(d):
    if not os.path.isdir(d):
        return set()
    return {n for n in os.listdir(d)
            if not n.startswith(".") and os.path.isdir(os.path.join(d, n))}


def files_of(d):
    """스킬 디렉터리의 (상대경로, 절대경로). 링크를 따라간다."""
    out = []
    for root, dirs, fs in os.walk(d, followlinks=True):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git")]
        for f in fs:
            if f.startswith("."):
                continue
            p = os.path.join(root, f)
            out.append((os.path.relpath(p, d), p))
    return sorted(out)


def digest(d):
    """내용 해시. 파일 경로와 바이트를 함께 넣어 배치까지 반영한다."""
    h = hashlib.sha256()
    for rel, p in files_of(d):
        h.update(rel.encode())
        try:
            with open(p, "rb") as fh:
                h.update(fh.read())
        except OSError:
            h.update(b"<unreadable>")
    return h.hexdigest()


def newest_mtime(d):
    best = 0.0
    for _, p in files_of(d):
        try:
            best = max(best, os.stat(p).st_mtime)
        except OSError:
            pass
    return best


# mtime 만으로는 최신을 못 가린다. 복사·체크아웃이 시각을 바꾸고, 래퍼 껍데기가
# 본체보다 나중 시각을 가질 수 있다(실제로 meeting-minutes 가 그랬다 — 24줄 래퍼가
# 400줄 본체보다 나중이었다). 그래서 내용 규모를 보조 신호로 함께 본다.
SHRINK = 0.6   # 최신 쪽이 반대쪽의 이 비율 미만이면 의심


def size_of(d):
    """(파일 수, 총 바이트)."""
    fs = files_of(d)
    total = 0
    for _, p in fs:
        try:
            total += os.path.getsize(p)
        except OSError:
            pass
    return len(fs), total


def link_target(p):
    return os.path.realpath(p) if os.path.islink(p) else None


def description(d):
    p = os.path.join(d, "SKILL.md")
    if not os.path.isfile(p):
        return ""
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            if line.startswith("description:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def classify(name):
    """한 스킬 이름에 대한 양쪽 상태를 판정한다."""
    a, b = os.path.join(CLAUDE, name), os.path.join(CODEX, name)
    ea, eb = os.path.isdir(a), os.path.isdir(b)
    r = {"name": name, "in_claude": ea, "in_codex": eb,
         "excluded": None, "state": None, "newer": None,
         "claude_mtime": None, "codex_mtime": None,
         "claude_bytes": None, "codex_bytes": None,
         "claude_files": None, "codex_files": None, "suspect": None}

    # 저장소가 관리하는 스킬은 bin/install.sh 의 일이다. 여기서 건드리지 않는다.
    if os.path.isdir(os.path.join(REPO, name)):
        r["excluded"] = "저장소 관리 (bin/install.sh)"
    else:
        # 양쪽 description 을 각각 본다. 한쪽만 [OMX] 면 같은 이름에 다른 계보가
        # 앉아 있는 것이고, 어느 방향으로 밀어도 한쪽이 파괴된다.
        oa = "[OMX]" in description(a) if ea else False
        ob = "[OMX]" in description(b) if eb else False
        if oa and ob:
            r["excluded"] = "다른 패키지 (oh-my-codex)"
        elif (oa or ob) and ea and eb:
            r["excluded"] = "계보 충돌 — 같은 이름, 다른 출처"
        elif oa or ob:
            r["excluded"] = "다른 패키지 (oh-my-codex)"

    if ea and eb:
        ta, tb = link_target(a), link_target(b)
        if ta and tb and ta == tb:
            r["state"] = "동일(같은 원본 공유)"
        elif digest(a) == digest(b):
            r["state"] = "동일(내용 일치)"
        else:
            r["state"] = "다름"
            ma, mb = newest_mtime(a), newest_mtime(b)
            r["claude_mtime"], r["codex_mtime"] = ma, mb
            r["newer"] = "claude" if ma > mb else ("codex" if mb > ma else "동시")

            (r["claude_files"], r["claude_bytes"]) = size_of(a)
            (r["codex_files"], r["codex_bytes"]) = size_of(b)
            if r["newer"] in ("claude", "codex"):
                nb = r["claude_bytes"] if r["newer"] == "claude" else r["codex_bytes"]
                ob = r["codex_bytes"] if r["newer"] == "claude" else r["claude_bytes"]
                if ob and nb < ob * SHRINK:
                    pct = round(nb * 100 / ob)
                    r["suspect"] = (f"mtime 은 {r['newer']} 가 최신인데 내용이 "
                                    f"반대쪽의 {pct}% 뿐이다")
    elif ea:
        r["state"] = "claude 에만"
        r["newer"] = "claude"
        r["claude_mtime"] = newest_mtime(a)
    elif eb:
        r["state"] = "codex 에만"
        r["newer"] = "codex"
        r["codex_mtime"] = newest_mtime(b)
    return r


def collect():
    names = sorted(skill_names(CLAUDE) | skill_names(CODEX))
    return [classify(n) for n in names]


def ts(v):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(v)) if v else "-"


def cmd_analyze(args):
    rows = collect()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    act = [r for r in rows if not r["excluded"] and r["state"] != "동일(같은 원본 공유)"
           and not str(r["state"]).startswith("동일")]
    same = [r for r in rows if not r["excluded"] and str(r["state"]).startswith("동일")]
    excl = [r for r in rows if r["excluded"]]

    print(f"Claude : {CLAUDE}")
    print(f"Codex  : {CODEX}\n")

    if act:
        print("== 동기화가 필요한 스킬 ==")
        print(f"  {'스킬':<32} {'상태':<16} {'최신':<7} {'claude':<17} {'codex'}")
        for r in act:
            mark = " !" if r["suspect"] else ""
            print(f"  {r['name']:<32} {r['state']:<16} {str(r['newer'] or '-'):<7} "
                  f"{ts(r['claude_mtime']):<17} {ts(r['codex_mtime'])}{mark}")
    else:
        print("== 동기화가 필요한 스킬 없음 ==")

    c = sum(1 for r in act if r["newer"] == "claude")
    x = sum(1 for r in act if r["newer"] == "codex")
    print(f"\n  claude 가 최신: {c}개    codex 가 최신: {x}개    이미 같음: {len(same)}개")
    if c and x:
        print("  ** 양쪽에 최신이 섞여 있다. 한 방향으로 밀면 반대쪽 최신본을 덮어쓴다. **")

    sus = [r for r in act if r["suspect"]]
    if sus:
        print(f"\n== ! 최신 판정이 의심스러운 {len(sus)}개 ==")
        print("   mtime 은 최신인데 내용이 훨씬 작다. 래퍼 껍데기이거나 잘린 사본일 수 있다.")
        for r in sus:
            print(f"   {r['name']}")
            print(f"     {r['suspect']}")
            print(f"     claude {r['claude_files']}파일/{r['claude_bytes']}B"
                  f"   codex {r['codex_files']}파일/{r['codex_bytes']}B")
        print("   ** 이 항목은 방향을 정하기 전에 내용을 직접 열어 확인한다. **")

    if excl:
        print(f"\n== 제외 {len(excl)}개 (건드리지 않음) ==")
        seen = {}
        for r in excl:
            seen.setdefault(r["excluded"], []).append(r["name"])
        for why, names in seen.items():
            mark = " **" if "충돌" in why else ""
            print(f"  {why}: {len(names)}개{mark}")
            print(f"    {', '.join(names)}")
        if any("충돌" in w for w in seen):
            print("\n  ** 계보 충돌은 자동으로 처리하지 않는다. 같은 이름이지만 서로 다른")
            print("     스킬이라 한쪽을 복사하면 다른 쪽이 사라진다. 사람이 이름을 바꾸거나")
            print("     한쪽을 버리기로 정해야 한다.")
    return 0


def cmd_apply(args):
    src_root, dst_root = (CLAUDE, CODEX) if args.direction == "claude-to-codex" else (CODEX, CLAUDE)
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    rows = [r for r in collect() if not r["excluded"]]
    rows = [r for r in rows if not str(r["state"]).startswith("동일")]
    if only:
        rows = [r for r in rows if r["name"] in only]
    if not rows:
        print("적용할 대상이 없습니다.")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(BACKUP_ROOT, f"skill-sync-{stamp}")
    print(f"방향: {args.direction}")
    print(f"백업: {backup}\n")

    done = skipped = 0
    for r in rows:
        name = r["name"]
        src, dst = os.path.join(src_root, name), os.path.join(dst_root, name)
        if not os.path.isdir(src):
            print(f"  건너뜀 {name} — 원본 쪽에 없음 (이 방향으로는 채울 수 없다)")
            skipped += 1
            continue
        # 의심 항목을 '작은 쪽' 방향으로 미는 경우에만 경고한다.
        if r["suspect"] and args.direction.startswith(r["newer"] or "\0"):
            print(f"  ! 주의 {name} — {r['suspect']}")
            print(f"    이 방향은 더 작은 쪽을 원본으로 삼는다. 의도한 것인지 확인하라.")
        if os.path.exists(dst):
            os.makedirs(backup, exist_ok=True)
            shutil.copytree(dst, os.path.join(backup, name), symlinks=True,
                            dirs_exist_ok=True)
            if os.path.islink(dst):
                os.unlink(dst)
            else:
                shutil.rmtree(dst)
            print(f"  덮어씀 {name}  (기존본 백업)")
        else:
            print(f"  채움   {name}")
        shutil.copytree(src, dst, symlinks=False)
        done += 1

    print(f"\n적용 {done}개, 건너뜀 {skipped}개")
    if os.path.isdir(backup):
        print(f"덮어쓴 것 백업: {backup}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=cmd_analyze)
    p = sub.add_parser("apply")
    p.add_argument("--direction", required=True,
                   choices=["claude-to-codex", "codex-to-claude"])
    p.add_argument("--only")
    p.set_defaults(fn=cmd_apply)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
