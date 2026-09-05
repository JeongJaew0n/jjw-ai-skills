#!/bin/sh
# obsidian-vaults.sh — 이 컴퓨터에 등록된 Obsidian vault 를 찾아 TSV 로 출력한다.
#
# Obsidian 은 열어본 vault 목록을 obsidian.json 에 기록한다. 그 파일이 유일한
# 진실 원천이므로 디스크 전체를 뒤지지 않고 이것만 읽는다.
#
# 출력: <vault경로>\t<플러그인디렉터리>\t<플러그인디렉터리 존재여부: yes|no>
# vault 를 하나도 못 찾으면 아무것도 출력하지 않고 exit 1.

set -eu

# Obsidian 설정 파일 후보. 플랫폼마다 위치가 다르고, WSL 에서는 Windows 쪽을 본다.
candidates="
$HOME/Library/Application Support/obsidian/obsidian.json
$HOME/.config/obsidian/obsidian.json
$HOME/.var/app/md.obsidian.Obsidian/config/obsidian.json
${APPDATA:-}/obsidian/obsidian.json
"

# WSL: Windows 사용자 홈의 AppData 도 후보에 넣는다
if [ -d /mnt/c/Users ]; then
  for home in /mnt/c/Users/*/; do
    candidates="$candidates
${home}AppData/Roaming/obsidian/obsidian.json"
  done
fi

# 줄 단위로 읽는다. macOS 의 "Application Support" 처럼 경로에 공백이 있어서
# $candidates 를 그냥 단어 분리하면 조각난 경로만 검사하게 된다.
config=""
while IFS= read -r c; do
  [ -n "$c" ] || continue
  if [ -f "$c" ]; then config="$c"; break; fi
done <<EOF
$candidates
EOF

if [ -z "$config" ]; then
  echo "obsidian.json 을 찾지 못했습니다. Obsidian 이 설치돼 있고 vault 를 한 번 이상 연 적이 있어야 합니다." >&2
  exit 1
fi

command -v python3 >/dev/null 2>&1 || {
  echo "python3 가 필요합니다 (obsidian.json 파싱)." >&2
  exit 1
}

CONFIG="$config" python3 - <<'PY'
import json, os, sys

path = os.environ["CONFIG"]
try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
except (OSError, ValueError) as e:
    print(f"{path} 를 읽지 못했습니다: {e}", file=sys.stderr)
    sys.exit(1)

vaults = data.get("vaults")
if not isinstance(vaults, dict):
    print(f"{path} 에 vaults 항목이 없습니다.", file=sys.stderr)
    sys.exit(1)

rows = []
for meta in vaults.values():
    vault = meta.get("path") if isinstance(meta, dict) else None
    # 삭제했거나 외장 디스크에 있는 vault 는 목록에 남아 있어도 실재하지 않는다
    if not vault or not os.path.isdir(vault):
        continue
    plugins = os.path.join(vault, ".obsidian", "plugins")
    rows.append((vault, plugins, "yes" if os.path.isdir(plugins) else "no"))

if not rows:
    print("obsidian.json 에 기록된 vault 중 실제로 존재하는 것이 없습니다.", file=sys.stderr)
    sys.exit(1)

rows.sort()
for row in rows:
    print("\t".join(row))
PY
