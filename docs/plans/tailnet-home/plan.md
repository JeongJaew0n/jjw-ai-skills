# tailnet-home — 이 맥의 Tailscale·홈 서버를 다른 세션에서도 쓰게 하는 스킬

> 이 저장소는 공개 저장소다. 호스트명·tailnet 이름·기기명·계정은 문서와 코드에 적지 않고
> 스크립트가 런타임에 알아낸다. 아래 `<이 맥>.<tailnet>.ts.net` 은 자리표시다.

## 목표

다른 폴더의 Claude Code 세션도 `/tailnet-home` 한 번으로 아래를 할 수 있게 한다.

1. Tailscale·홈 서버 상태 확인 (이 맥, 기기, 키 만료, serve 경로, 등록된 앱)
2. 만든 웹앱(정적 폴더)을 홈 서버 `apps.json` 에 올려 폰에서 `http://<이 맥>.<tailnet>.ts.net/apps/<id>/` 로 열리게 하기
3. 올린 앱이 실제로 열리는지 로컬·tailnet 양쪽에서 확인

## 전제가 되는 이 맥의 구성

| 사실 | 스킬에 주는 영향 |
|---|---|
| tailscaled 가 sudo 없이 userspace 로 돈다. 소켓이 `~/.local/share/tailscale/tailscaled.sock` | 그냥 `tailscale status` 는 `/var/run/tailscaled.socket` 을 찾다 실패한다. 스크립트가 `--socket` 을 붙인다 |
| 맥 자신은 tailnet 주소로 못 나간다 | tailnet URL 확인은 tailscaled 의 HTTP 프록시 `127.0.0.1:1055` 로만 한다. 프록시로 tailnet URL 을 그대로 요청하면 Host 헤더도 맞아 홈 서버의 host 검사를 통과한다 |
| serve 는 `/ → http://127.0.0.1:8700` 하나. 경로 추가(`--set-path`)는 root/operator 가 아니라 거부된다 | 앱마다 serve 를 고치지 않는다. 홈 서버가 `/apps/<id>/` 로 나눠 준다 |
| 홈 서버(`~/my/Dev/home/server.py`)는 요청마다 `apps.json` 을 읽고, 쓰지는 않는다. 켜기·끄기는 `state.json` | 앱 추가 후 재시작 불필요. 스크립트와 서버가 같은 파일을 쓰지 않는다 |
| `/api/status` 가 Tailscale 상태·serve 경로·앱 목록을 JSON 으로 준다 (로컬 요청은 관리 권한) | `status` 는 이걸 먼저 쓰고, 서버가 죽었으면 tailscale CLI 로 대신한다 |
| `apps.json` 항목: `id, title, summary, root` 또는 `url`(링크만), 선택 `thumb{image,x,y,w,h}` | `url` 은 프록시가 아니다. 다른 포트의 개발 서버는 폰에서 안 열린다 |
| `root` 는 서버 프로세스 cwd 기준 `realpath` 로 풀린다. root 밖·점 경로는 404, 나머지는 tailnet 에 공개 | 저장은 절대 realpath 로. root 를 넓게 잡으면 소스·설정이 공개된다 |
| 앱은 `/apps/<id>/` 아래에서 열린다 | 절대경로(`/assets/..`) 빌드는 깨진다. 상대경로 또는 Vite `base: './'` |

경로·포트는 스크립트 맨 위 상수 한 곳에 모으고 환경변수로 바꿀 수 있게 한다
(`TAILNET_HOME_DIR`, `TAILNET_HOME_PORT`, `TAILSCALE_SOCKET`, `TAILSCALE_PROXY`).

## 설계

### 위치·호출

- `skills/tailnet-home/` 에 만들고 `./bin/install.sh` 로 링크.
- frontmatter 기본값: `user-invocable: true`, `disable-model-invocation: true` (apps.json 을 고치므로 예외 대상 아님).
  다른 세션이 알아서 Tailscale 을 알아채지는 않는다. 사용자가 `/tailnet-home` 을 불러야 한다.
- `argument-hint: "[status | add <폴더> | check <id> | remove <id>]"`

### bin/tailnet-home.py (Python stdlib)

| 하위 명령 | 하는 일 | 쓰기 |
|---|---|---|
| `status [--json]` | 홈 서버 `/api/status` → 이 맥 주소·IP·키 만료(남은 일수), 기기 온라인, serve 경로, 앱(켜짐/꺼짐·공개 URL). 서버가 안 받으면 `tailscale --socket … status --json` 으로 Tailscale 부분만, LaunchAgent 상태 확인 명령 안내 | 없음 |
| `check <id>` | ① `127.0.0.1:<port>/apps/<id>/` ② 프록시로 `http://<DNSName>/apps/<id>/` ③ index.html 의 `src=`/`href=` 중 `/` 로 시작하는 절대경로 경고(`//` 프로토콜 상대 제외, JS 가 만드는 경로는 못 본다는 한 줄) ④ `state.json` 에서 꺼져 있으면 경고 | 없음 |
| `add --id --title --summary (--root DIR \| --url URL) [--thumb IMG:x,y,w,h] [--replace] [--allow-repo-root]` | 검증 → 백업 → 임시 파일 쓰고 원자적 교체 → 다시 읽어 JSON 검증 → `check` | apps.json |
| `remove <id>` | 백업 → 제거 → JSON 검증 | apps.json |

tailscale 명령 중계(`ts`)는 두지 않는다. 필요한 정보는 `status` 가 다 보여 주고, 중계를 두면 허용목록 우회(전역 플래그, `serve` 뒤 토큰)를 막아야 하는 공격면만 생긴다.

`add` 검증:
- id: 소문자 kebab-case. 중복은 `--replace` 없으면 거부
- root: `os.path.realpath(os.path.expanduser(...))` 로 바꿔 저장. 존재·`index.html` 필수
- root 가 `$HOME`·`~/my`·`~/my/Dev`·`/` 와 같거나 그 조상이면 거부
- root 에 `.git` 이 있으면(저장소 최상위) 기본 거부, `--allow-repo-root` 로만 허용 (`.git` 은 숨겨져도 `src/`·`config.*`·`node_modules/` 는 공개되므로)
- 비밀 파일 재귀 검사 (`node_modules`·점 폴더 건너뜀, 파일 2만 개 상한): `*.key`·`*.pem`·`id_rsa*`·`secrets*`·`credentials*` 는 거부, `.env*` 는 숨겨지지만 경고
- 공개될 파일 수·총 크기 출력
- thumb 이미지는 root 안에 있어야 함
- `state.json` 의 `disabled` 에 id 가 있으면 경고(서버 소유 파일이라 고치지 않음 → 홈 화면 스위치로 켜라고 안내)
- 백업은 `~/my/Dev/home/backups/apps.json.<YYYYmmdd-HHMMSS>`, 최근 10개만 유지

### SKILL.md (반말)

- 순서: `status` → (앱이면) 빌드 결과 폴더 정하기·상대경로 확인 → `add` → `check` → 폰 URL 안내 + "tailnet 의 모든 기기에 공개" 안내
- **타협 불가 가드레일**
  - `/tailnet-home` 호출에만 반응
  - tailscale 상태는 `tailnet-home.py status` 로만 본다. `tailscale` CLI 를 직접 부르지 않는다
  - 금지: `tailscale logout`·`down`·`up`·`set`·`serve`/`funnel` 변경·`reset`·`cert`, 기기 삭제·키 만료 변경, funnel(공용 인터넷 공개), `launchctl bootout/unload` 로 tailscaled·홈 서버 끄기, `server.py`·`state.json` 수정
  - apps.json 은 스크립트로만 고친다. 손으로 고쳐야 하면 먼저 읽고 백업, 고친 뒤 JSON 검증
  - 홈 디렉터리·소스 루트를 root 로 등록하지 않는다. `--allow-repo-root` 는 그 폴더가 곧 정적 사이트이고 비밀이 없음을 확인했을 때만
  - 맥에서 tailnet URL 을 직접 열어 보고 "안 열린다"고 판단하지 않는다
- 문제 해결 표: 502(홈 서버 기동 중), 403(홈에서 꺼짐), 404(index.html·절대경로), 소켓 실패

### 그 외

- README 에 새 묶음 "폰에서 열기 (Tailscale·홈 서버)" 한 줄. 호스트명 없이
- `docs/troubleshootings/reusable/tailscale-userspace-socket.md`: 기본 소켓 경로 실패, `--set-path` 거부, 맥에서 tailnet 주소 불가 → 프록시
- `~/my/Dev/home/README.md`(비공개)에 "다른 세션에서는 `/tailnet-home`" 한 줄

## 검증

1. `status` 실제 출력에 이 맥·기기·키 만료·serve 경로·앱 2개
2. 임시 앱(scratch 폴더, index.html 하나) `add` → `check` 로컬 200·프록시 200 → `remove` 후 404, 백업 생성
3. 거부: root=`~`, `~/my/Dev`, index.html 없음, 중복 id, 대문자 id, `.git` 있는 폴더(플래그 없이), `secret.key` 포함
4. 경고: `.env` 포함, 절대경로 HTML(프로토콜 상대는 제외), disabled id
5. 저장된 root 가 절대 realpath
6. `./bin/install.sh --check`, 새 세션에서 `/tailnet-home` 보임
7. frontmatter 하이픈 대조, 커밋 전 `grep` 으로 호스트명·tailnet·기기명·계정이 저장소에 없는지

## 범위 밖

- 다른 포트의 개발 서버를 폰에 프록시하기 (홈 서버 기능 추가 필요)
- HTTPS, 키 만료 해제 (관리 콘솔)
- 자동 호출 예외 등재

## 리뷰 반영 (2026-10-29, jjw-ai-skills 세션)

공개 저장소 하드코딩 제거, root 절대 realpath 저장, `ts` 중계 삭제, root 금지 규칙 정리와 `--allow-repo-root`, 비밀 파일 재귀 검사·공개 크기 출력, `state.json` disabled 경고, 절대경로 검사 범위, 백업 폴더·개수 제한, README 새 묶음. 8개 모두 반영.

## 호출 정책 변경 (2026-10-29, 사용자 결정)

다른 세션에서 "테일넷 스킬 참조해" 처럼 말로 부를 수 있게 `disable-model-invocation: false` 로 바꾸고 AGENTS.md 자동 호출 예외 표에 등록했다.
읽기 전용 조건은 만족하지 않으므로 범위를 좁혔다: 자동 호출로 바로 하는 건 `status`·`check` 까지, `add` 는 사용자가 올려 달라고 직접 말했을 때만, `remove`·`--replace` 는 확인 후.
