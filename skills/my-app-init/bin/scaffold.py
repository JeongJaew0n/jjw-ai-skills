#!/usr/bin/env python3
"""scaffold — my-app-init 의 기계적인 부분. 디렉터리 골격과 git 신원을 만든다.

판단이 필요한 일(어떤 계정을 쓸지, 커밋 정책, 브랜치 정책, README/CLAUDE.md 내용)은
여기서 하지 않는다. 그건 사람에게 묻고 AI 가 쓴다. 이 스크립트는 답이 정해진 뒤의
반복 작업만 담당한다.

  detect   이 컴퓨터에서 쓸 수 있는 git 신원 후보를 나열한다 (변경 없음)
  apply    docs 골격 생성 + git 신원 기록

기존 파일은 절대 덮어쓰지 않는다. 이미 있는 프로젝트에서 돌려도 안전해야 한다.
"""

import argparse
import os
import shutil
import subprocess
import sys

DOC_TREE = {
    "docs/plans/README.md": """# plans

AI 의 작업 계획이 쌓이는 곳이다. 작업 하나당 폴더 하나(`<slug>/`)를 만든다.

계획 없이 시작한 작업은 여기에 흔적이 남지 않는다. 그러면 다음 세션이 무엇을 왜
하던 중이었는지 복원할 수 없다. **여러 단계짜리 작업은 코드를 건드리기 전에 여기에
먼저 적는다.**

```
docs/plans/<slug>/
├── spec.md       무엇을 만들 것인가 — 범위·완료 조건
├── context.md    왜 시작했는가 — 원 요청·결정 이유·기각된 대안
└── checklist.md  어디까지 했는가 — 진행하며 갱신하는 체크박스
```

`<slug>` 는 영문 kebab-case 로, 주제가 드러나게 짓는다 (`fix`, `refactor` 같은
일반명사 단독 금지).
""",

    "docs/troubleshootings/README.md": """# troubleshootings

만들면서 터진 오류와 해결 내용을 남긴다. 목적은 기록이 아니라 **다시 안 겪는 것**이다.

두 폴더로 나뉘고, 가르는 기준은 하나다.

| 폴더 | 기준 |
|---|---|
| `reusable/` | 원인이 **라이브러리·프레임워크·런타임·OS·외부 서비스**에 있다 |
| `project-specific/` | 원인이 **이 프로젝트의 코드·설정·데이터**에 있다 |

판단이 애매하면 이렇게 자문한다 — **"같은 기술 스택으로 다른 프로젝트를 시작해도
이 글이 쓸모 있나?"** 그렇다면 `reusable/`, 아니면 `project-specific/`.

## 언제 쓰나

- 원인을 찾는 데 **시간이 걸린** 오류 (바로 보이는 오타는 안 적는다)
- 에러 메시지만 보고는 원인을 알 수 없었던 것
- 다시 만났을 때 또 헤맬 것 같은 것

## 파일 이름

증상이 검색되게 짓는다. 나중에 찾는 사람은 원인이 아니라 **증상**으로 찾는다.

```
reusable/vite-build-fails-on-node-22.md
project-specific/login-redirect-loop-on-staging.md
```
""",

    "docs/troubleshootings/reusable/README.md": """# reusable

원인이 **이 프로젝트 밖**(라이브러리·프레임워크·런타임·OS·외부 서비스)에 있는 오류.
같은 기술 스택을 쓰는 다음 프로젝트에서 그대로 써먹을 수 있는 것들이다.

프로젝트 이름, 내부 모듈명, 사내 URL 같은 것에 **의존하지 않게** 쓴다. 그것들이
들어가면 다음 프로젝트에서 못 읽는다.

## 템플릿

```markdown
# <증상 한 줄>

## 환경
언어·런타임·라이브러리 버전. 버전이 원인인 경우가 많아 반드시 적는다.

## 증상
에러 메시지 원문과 재현 조건.

## 원인
왜 그런지. 여기가 이 글의 값어치다.

## 해결
실제로 통한 조치. 통하지 않은 시도도 적어두면 다음 사람이 시간을 아낀다.

## 재발 방지
버전 고정, 린트 규칙, CI 체크 등 재발을 막는 조치. 없으면 "없음" 이라고 적는다.
```
""",

    "docs/troubleshootings/project-specific/README.md": """# project-specific

원인이 **이 프로젝트의 코드·설정·데이터**에 있는 오류. 다른 프로젝트로 가져가도
쓸모가 없는 것들이다.

여기 쌓인 글이 비슷한 주제로 반복되면 설계에 문제가 있다는 신호다. 글을 더 쓰기 전에
원인을 없앨 수 있는지 본다.

## 템플릿

```markdown
# <증상 한 줄>

## 증상
에러 메시지와 재현 조건.

## 원인
이 프로젝트의 어느 부분인지 — 파일·설정·데이터를 짚는다.

## 해결
실제로 통한 조치.

## 재발 방지
테스트 추가, 설정 정리, 문서화 등.
```
""",
}


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def git(root, *args, check=False):
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        die(f"git {' '.join(args)} 실패:\n{proc.stderr.strip()}")
    return proc


def cmd_detect(args):
    """쓸 수 있는 git 신원 후보를 모은다. 사용자에게 실제 선택지를 보여주기 위한 것."""
    print("=== git global ===")
    name = subprocess.run(["git", "config", "--global", "user.name"],
                          capture_output=True, text=True).stdout.strip()
    email = subprocess.run(["git", "config", "--global", "user.email"],
                           capture_output=True, text=True).stdout.strip()
    print(f"  {name or '(없음)'} <{email or '(없음)'}>")

    print("=== gh 로그인 계정 ===")
    # gh auth status 는 stdout 이 아니라 stderr 로 쓰고, 계정 하나가 타임아웃 나면
    # 나머지가 멀쩡해도 반환코드가 0 이 아니다. 반환코드로 판단하면 안 된다.
    if shutil.which("gh") is None:
        print("  (gh 설치 안 됨)")
    else:
        proc = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        lines = [l.strip() for l in (proc.stdout + proc.stderr).splitlines()
                 if "account" in l.lower()]
        for line in lines:
            print(f"  {line}")
        if not lines:
            print("  (미로그인)")

    root = os.path.abspath(os.path.expanduser(args.root))
    if os.path.isdir(os.path.join(root, ".git")):
        print("=== 이 저장소의 local 설정 ===")
        ln = git(root, "config", "--local", "user.name").stdout.strip()
        le = git(root, "config", "--local", "user.email").stdout.strip()
        print(f"  {ln or '(미설정 — global 을 따름)'} <{le or '(미설정)'}>")
    return 0


def cmd_apply(args):
    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        die(f"디렉터리가 없습니다: {root}")

    created, skipped = [], []

    # 1) docs 골격. 각 폴더에 목적을 적은 README 를 둔다 — 빈 폴더는 git 이 추적하지
    #    않을뿐더러, 용도를 쓰는 자리에서 설명해야 실제로 지켜진다.
    for rel, body in DOC_TREE.items():
        path = os.path.join(root, rel)
        if os.path.exists(path):
            skipped.append(rel)
            continue
        if not args.dry_run:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        created.append(rel)

    # 2) git 초기화 (요청한 경우에만). 이미 저장소면 건드리지 않는다.
    has_git = os.path.isdir(os.path.join(root, ".git"))
    if args.git_init and not has_git:
        if not args.dry_run:
            git(root, "init", check=True)
        created.append(".git/")
        has_git = True

    # 3) git 신원. 산문으로 적어두는 것만으로는 커밋 author 가 바뀌지 않는다.
    #    --local 로 실제 설정해야 강제된다.
    identity = None
    if args.author_name or args.author_email:
        if not (args.author_name and args.author_email):
            die("--author-name 과 --author-email 은 함께 줘야 합니다.")
        if not has_git:
            die("git 저장소가 아니라 신원을 설정할 수 없습니다. --git-init 을 붙이세요.")
        if not args.dry_run:
            git(root, "config", "--local", "user.name", args.author_name, check=True)
            git(root, "config", "--local", "user.email", args.author_email, check=True)
        identity = f"{args.author_name} <{args.author_email}>"

    print(f"대상 : {root}")
    if args.dry_run:
        print("--dry-run: 아무것도 쓰지 않았습니다.\n")
    for rel in created:
        print(f"  생성 : {rel}")
    for rel in skipped:
        print(f"  유지 : {rel} (이미 있음 — 덮어쓰지 않음)")
    if identity:
        print(f"  신원 : {identity}  (git config --local)")

    if not args.dry_run and identity:
        actual_n = git(root, "config", "--local", "user.name").stdout.strip()
        actual_e = git(root, "config", "--local", "user.email").stdout.strip()
        print(f"  확인 : {actual_n} <{actual_e}>")

    print("\n남은 일: CLAUDE.md 에 결정 사항 기록, README.md 작성 (AI 가 한다)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="my-app-init 의 골격 생성")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="git 신원 후보 조사 (변경 없음)")
    d.add_argument("--root", default=".")
    d.set_defaults(func=cmd_detect)

    a = sub.add_parser("apply", help="docs 골격 + git 신원")
    a.add_argument("--root", default=".")
    a.add_argument("--author-name")
    a.add_argument("--author-email")
    a.add_argument("--git-init", action="store_true", help="저장소가 아니면 git init")
    a.add_argument("--dry-run", action="store_true")
    a.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
