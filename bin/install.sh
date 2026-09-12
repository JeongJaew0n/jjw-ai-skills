#!/bin/sh
# install.sh — 이 저장소의 스킬을 Claude Code 와 Codex 에 설치한다.
#
#   ./bin/install.sh              설치 (기본)
#   ./bin/install.sh --dry-run    무엇을 할지만 출력
#   ./bin/install.sh --check      현재 상태만 점검 (변경 없음)
#
# 복사가 아니라 **심볼릭 링크**를 건다. 복사본은 저장소를 고쳐도 반영되지 않아
# 어느 쪽이 최신인지 알 수 없게 되는데, 실제로 그 상태가 한 번 만들어졌었다.
#
# 저장소에 없는 스킬은 건드리지 않는다. 전역에만 있는 것들이 있고,
# 그것들을 지우는 것은 이 스크립트의 일이 아니다.

set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/skills"
TARGETS="$HOME/.claude/skills $HOME/.codex/skills"
BACKUP="$HOME/.claude/backups/skill-install-$(date +%Y%m%d-%H%M%S)"

DRY=0
CHECK=0
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --check)   CHECK=1; DRY=1 ;;
    *) echo "알 수 없는 인자: $a" >&2; exit 1 ;;
  esac
done

[ -d "$SRC" ] || { echo "skills/ 를 찾을 수 없습니다: $SRC" >&2; exit 1; }

# SKILL.md frontmatter 에서 값을 뽑는다. 스킬은 중첩될 수 있어(hud) 최상위에
# SKILL.md 가 없을 수도 있다.
field() {
  [ -f "$1" ] || return 0
  sed -n "s/^$2: *//p" "$1" | head -1 | tr -d '"'
}

echo "저장소: $ROOT"
[ "$CHECK" -eq 1 ] && echo "(점검 모드 — 변경하지 않음)"
[ "$DRY" -eq 1 ] && [ "$CHECK" -eq 0 ] && echo "(dry-run — 변경하지 않음)"
echo

for skill_dir in "$SRC"/*/; do
  name="$(basename "$skill_dir")"
  skill_md="$skill_dir/SKILL.md"

  # Codex 정책 파일을 frontmatter 에서 생성한다. 저장소의 명시적 호출 정책
  # (disable-model-invocation) 이 Codex 쪽에서도 걸리게 하려면 이 파일이 필요하다.
  # Claude 는 frontmatter 를 직접 읽으므로 이 파일과 무관하다.
  if [ -f "$skill_md" ]; then
    dmi="$(field "$skill_md" "disable-model-invocation")"
    implicit="true"
    [ "$dmi" = "true" ] && implicit="false"
    yaml="$skill_dir/agents/openai.yaml"
    if [ "$DRY" -eq 0 ]; then
      mkdir -p "$skill_dir/agents"
      cat > "$yaml" <<YAML
# bin/install.sh 가 SKILL.md frontmatter 에서 생성한다. 직접 고치지 말 것.
interface:
  display_name: "$name"
  default_prompt: "Use \$$name."

policy:
  allow_implicit_invocation: $implicit
YAML
    fi
    printf "%-34s policy: allow_implicit_invocation=%s\n" "$name" "$implicit"
  else
    printf "%-34s (중첩 스킬 — SKILL.md 없음, 정책 파일 생략)\n" "$name"
  fi

  for tdir in $TARGETS; do
    label="$(basename "$(dirname "$tdir")")"   # .claude / .codex
    link="$tdir/$name"

    [ -d "$tdir" ] || { printf "    %-9s 대상 디렉터리 없음 — 건너뜀\n" "$label"; continue; }

    if [ -L "$link" ]; then
      cur="$(readlink "$link")"
      if [ "$cur" = "$skill_dir" ] || [ "$cur" = "${skill_dir%/}" ]; then
        printf "    %-9s 이미 연결됨\n" "$label"
        continue
      fi
      printf "    %-9s 다른 곳을 가리킴 → 교체 (%s)\n" "$label" "$cur"
      [ "$DRY" -eq 0 ] && rm -f "$link"
    elif [ -d "$link" ]; then
      # 실디렉터리는 복사본이다. 지우기 전에 백업하고, 런타임 파일은 저장소로 옮긴다.
      printf "    %-9s 복사본 발견 → 백업 후 링크로 교체\n" "$label"
      if [ "$DRY" -eq 0 ]; then
        mkdir -p "$BACKUP/$label"
        cp -R "$link" "$BACKUP/$label/$name"
        # config.json 같은 런타임 상태는 저장소 쪽에 없으면 옮겨 살린다
        for runtime in config.json; do
          if [ -f "$link/$runtime" ] && [ ! -f "${skill_dir%/}/$runtime" ]; then
            cp "$link/$runtime" "${skill_dir%/}/$runtime"
            printf "    %-9s   런타임 파일 보존: %s\n" "$label" "$runtime"
          fi
        done
        rm -rf "$link"
      fi
    fi

    if [ "$DRY" -eq 0 ]; then
      ln -s "${skill_dir%/}" "$link"
      printf "    %-9s 연결\n" "$label"
    else
      printf "    %-9s 연결 예정\n" "$label"
    fi
  done
done

echo
echo "=== 저장소에 없는 전역 스킬 (건드리지 않음) ==="
for tdir in $TARGETS; do
  [ -d "$tdir" ] || continue
  label="$(basename "$(dirname "$tdir")")"
  for item in "$tdir"/*; do
    [ -e "$item" ] || continue
    n="$(basename "$item")"
    case "$n" in .*) continue ;; esac
    [ -d "$SRC/$n" ] || printf "  %-9s %s\n" "$label" "$n"
  done
done

if [ "$DRY" -eq 0 ] && [ -d "$BACKUP" ]; then
  echo
  echo "교체된 복사본 백업: $BACKUP"
fi
