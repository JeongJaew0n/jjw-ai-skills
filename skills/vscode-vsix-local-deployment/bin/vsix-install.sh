#!/bin/sh

set -eu

usage() {
  cat <<'EOF'
Usage: vsix-install.sh [repo-or-vsix] [--cli <command-or-path>] [--dry-run]
EOF
}

TARGET=""
CLI_INPUT=""
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --cli)
      [ "$#" -ge 2 ] || { echo "--cli 값이 필요합니다." >&2; exit 2; }
      CLI_INPUT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --*)
      echo "알 수 없는 옵션: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      [ -z "$TARGET" ] || { echo "대상은 하나만 지정할 수 있습니다." >&2; exit 2; }
      TARGET="$1"
      shift
      ;;
  esac
done

[ -n "$TARGET" ] || TARGET="$PWD"

resolve_cli() {
  if [ -n "$CLI_INPUT" ]; then
    case "$CLI_INPUT" in
      */*)
        [ -x "$CLI_INPUT" ] || { echo "실행할 수 없는 VS Code CLI입니다: $CLI_INPUT" >&2; exit 1; }
        printf '%s\n' "$CLI_INPUT"
        ;;
      *)
        command -v "$CLI_INPUT" 2>/dev/null || {
          echo "VS Code CLI를 PATH에서 찾지 못했습니다: $CLI_INPUT" >&2
          exit 1
        }
        ;;
    esac
    return
  fi

  if command -v code >/dev/null 2>&1; then
    command -v code
    return
  fi

  for candidate in \
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
    "$HOME/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  echo "Visual Studio Code CLI를 찾지 못했습니다. --cli로 경로를 지정하세요." >&2
  exit 1
}

CLI="$(resolve_cli)"

if [ -f "$TARGET" ]; then
  case "$TARGET" in
    *.vsix) VSIX="$(cd "$(dirname "$TARGET")" && pwd -P)/$(basename "$TARGET")" ;;
    *) echo "VSIX 파일이 아닙니다: $TARGET" >&2; exit 1 ;;
  esac
elif [ -d "$TARGET" ]; then
  REPO="$(cd "$TARGET" && pwd -P)"
  PACKAGE_JSON="$REPO/package.json"
  [ -f "$PACKAGE_JSON" ] || { echo "package.json을 찾지 못했습니다: $REPO" >&2; exit 1; }

  PROJECT_META="$(node -e '
    const p = require(process.argv[1]);
    if (!p.publisher || !p.name || !p.version || !p.engines?.vscode) process.exit(2);
    process.stdout.write(`${p.name}\n${p.version}`);
  ' "$PACKAGE_JSON")" || {
    echo "publisher, name, version, engines.vscode가 있는 VS Code 확장 package.json이 필요합니다." >&2
    exit 1
  }
  PROJECT_NAME="$(printf '%s\n' "$PROJECT_META" | sed -n '1p')"
  PROJECT_VERSION="$(printf '%s\n' "$PROJECT_META" | sed -n '2p')"
  EXPECTED="$REPO/artifacts/$PROJECT_NAME-$PROJECT_VERSION.vsix"

  if [ -f "$EXPECTED" ]; then
    VSIX="$EXPECTED"
  else
    CANDIDATE_COUNT=0
    VSIX=""
    for candidate in "$REPO"/artifacts/*.vsix "$REPO"/*.vsix; do
      [ -f "$candidate" ] || continue
      CANDIDATE_COUNT=$((CANDIDATE_COUNT + 1))
      VSIX="$candidate"
    done
    if [ "$CANDIDATE_COUNT" -eq 0 ]; then
      echo "설치할 VSIX가 없습니다. 먼저 저장소의 패키징 절차를 실행하세요." >&2
      exit 1
    fi
    if [ "$CANDIDATE_COUNT" -gt 1 ]; then
      echo "VSIX가 여러 개입니다. 설치할 파일을 직접 지정하세요." >&2
      exit 1
    fi
  fi
else
  echo "대상을 찾을 수 없습니다: $TARGET" >&2
  exit 1
fi

command -v node >/dev/null 2>&1 || { echo "VSIX manifest 검사에 Node.js가 필요합니다." >&2; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo "VSIX manifest 검사에 unzip이 필요합니다." >&2; exit 1; }

MANIFEST_FILE="$(mktemp "${TMPDIR:-/tmp}/vsix-manifest.XXXXXX")"
trap 'rm -f "$MANIFEST_FILE"' EXIT HUP INT TERM
unzip -p "$VSIX" extension/package.json > "$MANIFEST_FILE" || {
  echo "VSIX에서 extension/package.json을 읽지 못했습니다: $VSIX" >&2
  exit 1
}

EXTENSION_META="$(node -e '
  const fs = require("node:fs");
  const p = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
  if (!p.publisher || !p.name || !p.version || !p.engines?.vscode) process.exit(2);
  process.stdout.write(`${p.publisher}.${p.name}\n${p.version}\n${p.engines.vscode}`);
' "$MANIFEST_FILE")" || {
  echo "VSIX manifest에 publisher, name, version, engines.vscode가 필요합니다." >&2
  exit 1
}

EXTENSION_ID="$(printf '%s\n' "$EXTENSION_META" | sed -n '1p')"
EXTENSION_VERSION="$(printf '%s\n' "$EXTENSION_META" | sed -n '2p')"
VSCODE_RANGE="$(printf '%s\n' "$EXTENSION_META" | sed -n '3p')"
VSCODE_VERSION="$("$CLI" --version 2>/dev/null | sed -n '1p' | tr -d '\r')"

printf '%s\n' "$VSCODE_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+' || {
  echo "VS Code CLI 버전을 확인하지 못했습니다: $CLI" >&2
  exit 1
}

node -e '
  const installed = process.argv[1].split(".").map(Number);
  const range = process.argv[2].trim();
  const match = range.match(/^(?:\^|>=\s*)?(\d+)\.(\d+)\.(\d+)/);
  if (!match) process.exit(0);
  const required = match.slice(1).map(Number);
  const compare = (a, b) => {
    for (let i = 0; i < 3; i += 1) {
      if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) - (b[i] ?? 0);
    }
    return 0;
  };
  if (compare(installed, required) < 0) process.exit(3);
  if (range.startsWith("^") && installed[0] !== required[0]) process.exit(3);
' "$VSCODE_VERSION" "$VSCODE_RANGE" || {
  echo "VS Code ${VSCODE_VERSION}은(는) ${EXTENSION_ID}의 요구 범위 ${VSCODE_RANGE}보다 낮거나 호환되지 않습니다." >&2
  echo "Visual Studio Code를 업데이트한 뒤 다시 실행하세요." >&2
  exit 1
}

echo "CLI:   $CLI (VS Code $VSCODE_VERSION)"
echo "VSIX:  $VSIX"
echo "확장:  $EXTENSION_ID@$EXTENSION_VERSION"
echo "요구:  VS Code $VSCODE_RANGE"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "dry-run: 설치하지 않았습니다."
  exit 0
fi

"$CLI" --install-extension "$VSIX" --force

INSTALLED="$("$CLI" --list-extensions --show-versions 2>/dev/null)"
printf '%s\n' "$INSTALLED" | awk -v wanted="$EXTENSION_ID@$EXTENSION_VERSION" '
  BEGIN { found = 0 }
  tolower($0) == tolower(wanted) { found = 1 }
  END { exit(found ? 0 : 1) }
' || {
  echo "CLI 명령은 끝났지만 설치 목록에서 $EXTENSION_ID@$EXTENSION_VERSION을 확인하지 못했습니다." >&2
  exit 1
}

echo "설치 검증 완료: $EXTENSION_ID@$EXTENSION_VERSION"
echo "열려 있는 VS Code 창에서는 Developer: Reload Window를 실행하세요."
