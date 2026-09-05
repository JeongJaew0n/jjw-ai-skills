#!/bin/sh
# obsidian-deploy.sh — 빌드 산출물을 로컬 Obsidian vault 의 플러그인 폴더로 복사한다.
#
# 사용법:
#   obsidian-deploy.sh --src <플러그인_레포> --plugins-dir <vault>/.obsidian/plugins [옵션]
#
# 옵션:
#   --id <plugin-id>   manifest.json 의 id 대신 사용할 폴더명
#   --hotreload        대상 폴더에 .hotreload 를 남긴다 (Hot-Reload 플러그인용)
#   --dry-run          복사하지 않고 무엇을 할지만 출력한다
#
# 설계상 지키는 것:
#   - 대상 폴더를 통째로 지우지 않는다. 이름을 아는 파일만 덮어쓴다.
#   - data.json 은 절대 건드리지 않는다. 그건 사용자의 플러그인 설정이다.
#   - 이미 있는 폴더의 내용을 배포 전에 먼저 보고한다.

set -eu

SRC=""
PLUGINS_DIR=""
PLUGIN_ID=""
HOTRELOAD=0
DRY_RUN=0

die() { echo "오류: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --src)         SRC="${2:-}";         shift 2 ;;
    --plugins-dir) PLUGINS_DIR="${2:-}"; shift 2 ;;
    --id)          PLUGIN_ID="${2:-}";   shift 2 ;;
    --hotreload)   HOTRELOAD=1;          shift ;;
    --dry-run)     DRY_RUN=1;            shift ;;
    *) die "알 수 없는 인자: $1" ;;
  esac
done

[ -n "$SRC" ] || SRC="$(pwd)"
[ -d "$SRC" ] || die "--src 경로가 없습니다: $SRC"
[ -n "$PLUGINS_DIR" ] || die "--plugins-dir 이 필요합니다."

# plugins 디렉터리는 이미 존재해야 한다. 없다면 vault 경로가 틀렸다는 뜻이므로
# 새로 만들어서 엉뚱한 곳에 배포하지 않고 멈춘다.
[ -d "$PLUGINS_DIR" ] || die "플러그인 디렉터리가 없습니다: $PLUGINS_DIR
   vault 경로가 맞는지 확인하세요. (<vault>/.obsidian/plugins)"

MANIFEST="$SRC/manifest.json"
[ -f "$MANIFEST" ] || die "manifest.json 이 없습니다: $MANIFEST
   Obsidian 플러그인 레포 루트에서 실행해야 합니다."
[ -f "$SRC/main.js" ] || die "main.js 가 없습니다: $SRC/main.js
   먼저 빌드하세요 (예: npm run build)."

command -v python3 >/dev/null 2>&1 || die "python3 가 필요합니다 (manifest.json 파싱)."

read_manifest() {
  MANIFEST_PATH="$1" FIELD="$2" python3 - <<'PY'
import json, os, sys
try:
    with open(os.environ["MANIFEST_PATH"], encoding="utf-8") as f:
        data = json.load(f)
except (OSError, ValueError) as e:
    print(f"manifest.json 파싱 실패: {e}", file=sys.stderr)
    sys.exit(1)
value = data.get(os.environ["FIELD"])
print(value if isinstance(value, str) else "")
PY
}

[ -n "$PLUGIN_ID" ] || PLUGIN_ID="$(read_manifest "$MANIFEST" id)"
[ -n "$PLUGIN_ID" ] || die "manifest.json 에 id 가 없습니다. --id 로 직접 지정하세요."

# id 는 폴더명이 된다. 경로 구분자나 상위 참조가 들어오면 vault 밖으로 쓸 수 있다.
case "$PLUGIN_ID" in
  */*|*\\*|.|..|"") die "플러그인 id 가 폴더명으로 쓸 수 없는 값입니다: $PLUGIN_ID" ;;
esac

SRC_NAME="$(read_manifest "$MANIFEST" name)"
SRC_VERSION="$(read_manifest "$MANIFEST" version)"
TARGET="$PLUGINS_DIR/$PLUGIN_ID"

echo "플러그인 : $SRC_NAME ($PLUGIN_ID) ${SRC_VERSION:+v$SRC_VERSION}"
echo "소스     : $SRC"
echo "대상     : $TARGET"

# 대상이 이미 있으면 무엇을 덮어쓰게 되는지 먼저 드러낸다.
if [ -d "$TARGET" ]; then
  if [ -f "$TARGET/manifest.json" ]; then
    OLD_NAME="$(read_manifest "$TARGET/manifest.json" name)"
    OLD_VERSION="$(read_manifest "$TARGET/manifest.json" version)"
    echo "기존     : $OLD_NAME ${OLD_VERSION:+v$OLD_VERSION} (덮어씀)"
    if [ -n "$OLD_NAME" ] && [ -n "$SRC_NAME" ] && [ "$OLD_NAME" != "$SRC_NAME" ]; then
      echo "경고     : 대상의 플러그인 이름이 다릅니다 ($OLD_NAME → $SRC_NAME)." >&2
      echo "           같은 id 를 쓰는 다른 플러그인일 수 있습니다." >&2
    fi
  else
    echo "기존     : 폴더는 있으나 manifest.json 없음"
  fi
  [ -f "$TARGET/data.json" ] && echo "보존     : data.json (플러그인 설정, 건드리지 않음)"
else
  echo "기존     : 없음 (새로 만듦)"
fi

# main.js / manifest.json 은 필수, 나머지는 있을 때만 복사한다.
FILES="main.js manifest.json"
for optional in styles.css; do
  [ -f "$SRC/$optional" ] && FILES="$FILES $optional"
done

if [ "$DRY_RUN" -eq 1 ]; then
  echo "--- dry-run: 실제로 복사하지 않음 ---"
  for f in $FILES; do echo "  복사 예정: $f"; done
  [ "$HOTRELOAD" -eq 1 ] && echo "  생성 예정: .hotreload"
  exit 0
fi

mkdir -p "$TARGET"
for f in $FILES; do
  cp "$SRC/$f" "$TARGET/$f"
  echo "  복사: $f"
done

if [ "$HOTRELOAD" -eq 1 ]; then
  : > "$TARGET/.hotreload"
  echo "  생성: .hotreload"
fi

echo "완료: $TARGET"
