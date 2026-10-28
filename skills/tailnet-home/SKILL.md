---
name: tailnet-home
description: |
  이 맥의 Tailscale(userspace 로 도는 tailscaled)과 홈 서버 상태를 보여주고, 만든 정적
  웹앱을 홈 서버에 올려 같은 tailnet 의 폰에서 `/apps/<id>/` 로 열리게 한다. 올린 뒤
  로컬과 tailnet 양쪽에서 실제로 열리는지 확인한다.
  사용자가 `/tailnet-home` 또는 `$tailnet-home` 을 명시적으로 호출했을 때만 사용한다.
  요청 내용이 관련 분야에 해당한다는 이유만으로 자동 사용하지 않는다.
user-invocable: true
disable-model-invocation: true
argument-hint: "[status | add <폴더> | check <id> | remove <id>]"
allowed-tools:
  - Bash
  - Read
---

# tailnet-home

이 맥에서 만든 웹앱을 폰에서 열게 해 주는 스킬이야. 구성은 이래.

```
폰 ──tailnet──▶ tailscale serve (/ → 127.0.0.1:8700) ──▶ 홈 서버 ──▶ /apps/<id>/ = apps.json 의 root 폴더
```

- tailscaled 는 sudo 없이 **userspace** 로 돌아. 그래서 그냥 `tailscale status` 는 기본 소켓을 찾다 실패해.
- 맥 자신은 tailnet 주소로 못 나가. 맥에서 tailnet URL 을 열면 안 열리는 게 정상이야.
- 홈 서버는 요청마다 `apps.json` 을 읽어. 앱을 추가해도 재시작할 필요 없어.

모든 일은 스크립트로 해. 경로·포트·소켓은 스크립트가 알아.

```bash
H=~/.claude/skills/tailnet-home/bin/tailnet-home.py
$H status                 # Tailscale·기기·키 만료·serve·앱 목록과 폰 URL
$H status --json          # 다른 처리에 넘길 때
$H check <id>             # 로컬·tailnet 양쪽에서 열리는지
$H add --id <id> --title <제목> --summary <한 줄> --root <폴더> [--thumb 이미지:x,y,w,h] [--replace] [--allow-repo-root]
$H add --id <id> --title <제목> --url <https://...>     # 링크만 거는 앱
$H remove <id>
```

## 타협 불가 가드레일

- **`/tailnet-home` 이나 `$tailnet-home` 호출에만 반응해.** 이름만 나온 건 호출이 아니야.
- Tailscale 상태는 **`tailnet-home.py status` 로만 봐.** `tailscale` CLI 를 직접 부르지 마.
- 아래는 하지 마. 사용자가 원하면 명령을 알려 주고 직접 하게 해.
  - `tailscale logout`, `down`, `up`(옵션 바꾸기 포함), `set`(`--webclient`, `--shields-up` 등), `cert`
  - `tailscale serve` / `funnel` 설정 변경·`reset`. **funnel(공용 인터넷 공개)은 절대 안 돼.**
  - 기기 삭제, 키 만료 변경 (관리 콘솔에서 사람이 할 일)
  - `launchctl bootout`/`unload` 로 tailscaled 나 홈 서버 끄기
  - 홈 서버 `server.py`, `state.json` 고치기 (state.json 은 서버가 쓰는 켜기·끄기 기록)
- `apps.json` 은 **스크립트로만 고쳐.** 스크립트가 백업(`backups/`, 최근 10개)하고 원자적으로 바꾼 뒤 JSON 을 다시 읽어 검증해. 손으로 고쳐야 하는 상황이면 먼저 읽고 백업하고, 고친 뒤 `python3 -m json.tool` 로 검증해.
- **root 폴더 안의 파일은 tailnet 의 모든 기기에 공개돼.** 홈 디렉터리나 소스 저장소 최상위를 root 로 잡지 마. 빌드 결과 폴더(`dist/`, `build/`, `out/`)를 써.
  - `--allow-repo-root` 는 저장소 최상위가 곧 정적 사이트이고, `src/`·설정·데이터 중 공개되면 안 되는 게 없는 걸 **직접 확인했을 때만** 써. 확인한 내용을 사용자에게 말해.
  - 스크립트가 비밀 파일 때문에 거부하면 **우회하지 마.** 파일을 옮기거나 다른 폴더를 쓰라고 안내해.
- 맥에서 tailnet URL 을 직접 열어 보고 "안 열린다"고 판단하지 마. tailnet 확인은 `check` 가 프록시로 해.

## 앱 올리기 순서

1. `status` 로 Tailscale 이 `Running` 이고 serve 가 홈 서버를 가리키는지 봐. 아니면 멈추고 [문제 해결](#문제-해결)로.
2. **올릴 폴더를 정해.**
   - 빌드 도구가 있으면 먼저 빌드하고 결과 폴더를 써. 그 폴더에 `index.html` 이 있어야 해.
   - 앱은 `/apps/<id>/` 아래에서 열려. `/assets/..` 처럼 `/` 로 시작하는 경로는 깨져. 상대경로(`./`)로 만들어. Vite 는 `base: './'`, CRA 는 `"homepage": "."`, Next 정적 export 는 `basePath` 를 `/apps/<id>` 로.
   - 라우터가 있으면 해시 라우팅(`#/`)이 안전해. 서버는 없는 경로에 index.html 을 돌려주지 않아.
   - 다른 포트에서 도는 개발 서버는 폰에서 안 열려. 홈 서버는 정적 파일만 서빙해.
3. id 는 소문자 kebab-case 로, 보통 폴더 이름. title·summary 는 홈 화면 카드에 그대로 나와. 한국어로 짧게.
4. `add` 실행. 출력의 "공개될 파일" 수와 크기, 경고를 사용자에게 그대로 전해.
5. `add` 가 이어서 `check` 를 돌려. **로컬·tailnet 둘 다 200 이어야** 올렸다고 말해. 절대경로 경고가 나오면 고치고 다시 `check`.
6. 사용자에게 알려 줄 것:
   - 폰 URL (`status` 출력의 앱 줄 그대로)
   - 홈 화면 카드에서도 열린다는 것
   - **같은 tailnet 의 모든 기기에서 열린다**는 것

썸네일은 선택이야. root 안의 이미지에서 `x,y,w,h` 영역을 잘라 홈 카드에 2배로 그려. 도트 스프라이트처럼 작은 그림에 어울려.

이미 있는 앱을 바꾸려면 `--replace`. 지울 때는 사용자에게 확인받고 `remove`.

## 문제 해결

| 증상 | 원인 | 할 일 |
|---|---|---|
| `status` 가 "홈 서버: 응답 없음" | 로그인 직후 몇 초는 기동 중, 아니면 LaunchAgent 가 꺼짐 | 몇 초 뒤 다시. 계속이면 출력에 나온 `launchctl print` 결과를 보여 주고 사용자에게 맡겨 |
| Tailscale 연결 실패 | tailscaled LaunchAgent 가 안 돎 | 위와 같이 상태만 확인하고 보고. 재시작은 사용자 결정 |
| 폰에서 502 | 홈 서버 기동 중 | 몇 초 뒤 새로 고침 |
| 403 | 홈 화면에서 그 앱 스위치가 꺼져 있음 | 홈 화면에서 켜라고 안내 (state.json 은 고치지 마) |
| 404 | root 에 `index.html` 없음, 또는 하위 파일 경로가 `/` 로 시작 | 빌드 설정을 상대경로로 |
| 화면이 하얗고 콘솔에 404 | JS 가 절대경로로 불러옴. `check` 는 index.html 만 봐 | 빌드 설정의 base 경로 확인 |
| tailnet 만 실패 | 폰이 tailnet 에 없거나, 키 만료, serve 가 바뀜 | `status` 의 기기·키 만료·serve 줄을 보여 줘 |

## 경로 바꾸기

홈 서버나 소켓 위치가 바뀌면 환경변수로 덮어써: `TAILNET_HOME_DIR`, `TAILNET_HOME_PORT`, `TAILSCALE_SOCKET`, `TAILSCALE_PROXY`.

## 한계

- 정적 파일만 올릴 수 있어. API 서버나 개발 서버를 폰에 프록시하는 기능은 홈 서버에 없어.
- HTTP 야. HTTPS 는 관리 콘솔에서 사람이 켜야 해.
- 다른 세션이 Tailscale 을 알아서 쓰지는 않아. `/tailnet-home` 을 불러야 해.
