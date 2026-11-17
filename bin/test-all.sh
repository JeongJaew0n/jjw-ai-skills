#!/usr/bin/env bash
# 저장소의 모든 스킬 도구 시험을 돌린다.
#
#   ./bin/test-all.sh          전부
#   ./bin/test-all.sh hud      경로에 "hud" 가 든 시험만
#
# 찾는 것: skills/**/bin/*.test.py, *.test.mjs, bin/*.test.py, 그리고 bash-guard.py --self-test.
# 시험은 모두 임시 폴더에서 돌고 실제 ~/.claude·기기·세션은 건드리지 않는다(각 시험 파일 머리말 참조).
# 이 맥의 NODE_OPTIONS 가 깨져 있을 수 있어서 node 는 NODE_OPTIONS 를 지우고 부른다.
set -u
cd "$(dirname "$0")/.."

filter="${1:-}"
pass=0
fail=0
failed=()

run() {   # run <이름> <명령...>
  local name="$1"; shift
  [ -n "$filter" ] && [[ "$name" != *"$filter"* ]] && return
  local out rc
  out="$("$@" 2>&1)"; rc=$?
  if [ $rc -eq 0 ]; then
    pass=$((pass + 1))
    printf 'ok    %s  — %s\n' "$name" "$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | tail -1)"
  else
    fail=$((fail + 1))
    failed+=("$name")
    printf 'FAIL  %s (종료 %s)\n' "$name" "$rc"
    printf '%s\n' "$out" | tail -30 | sed 's/^/      /'
  fi
}

run 'skills/ai-mistake-log/bin/bash-guard.py --self-test' python3 -I skills/ai-mistake-log/bin/bash-guard.py --self-test

while IFS= read -r f; do
  case "$f" in
    *.test.py)  run "$f" python3 -I "$f" ;;
    *.test.mjs) run "$f" env -u NODE_OPTIONS node "$f" ;;
  esac
done < <(find skills bin -type f \( -name '*.test.py' -o -name '*.test.mjs' \) -not -path '*/node_modules/*' | sort)

echo
echo "시험 파일 $((pass + fail))개 중 통과 $pass, 실패 $fail"
[ $fail -eq 0 ] || { printf '실패: %s\n' "${failed[@]}"; exit 1; }
