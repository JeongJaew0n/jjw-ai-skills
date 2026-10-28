# sudo 없이 띄운 tailscaled(userspace)를 다룰 때 막히는 세 가지

2026-10-29, macOS, Homebrew tailscale 1.104.4

## 상황

Homebrew `tailscale` 을 쓰면서 시스템 확장·sudo 없이 사용자 LaunchAgent 로 이렇게 띄웠다.

```
tailscaled --tun=userspace-networking \
  --statedir=$HOME/.local/share/tailscale \
  --socket=$HOME/.local/share/tailscale/tailscaled.sock \
  --outbound-http-proxy-listen=127.0.0.1:1055
```

## 1. 그냥 `tailscale` 명령이 실패한다

```
failed to connect to local tailscaled (which appears to be running as tailscaled, pid …).
… dial unix /var/run/tailscaled.socket: connect: no such file or directory
```

CLI 는 기본 소켓 `/var/run/tailscaled.socket` 만 찾는다. 데몬은 살아 있다. 매번 `--socket=<경로>` 를 붙여야 한다.
다른 도구·세션에서 쓰려면 소켓 경로를 한 곳(스크립트 상수, 환경변수)에 두고 감싸서 부른다.

## 2. `tailscale serve --set-path` 가 거부된다

```
must be root, or be an operator and able to run tailscale serve …
```

userspace 데몬을 사용자 권한으로 돌리면 경로별 serve 를 추가할 수 없었다. `serve reset` 후 `/` 하나만
로컬 HTTP 서버로 프록시하고, 경로 나누기는 그 서버가 하게 바꿨다.

## 3. 맥 자신은 tailnet 주소로 못 나간다

userspace 모드는 OS 에 네트워크 인터페이스를 만들지 않는다. 같은 맥의 브라우저·curl 로
`http://<이 맥>.<tailnet>.ts.net/` 을 열면 실패하는 게 정상이다. 폰에서는 열린다.

맥에서 tailnet 쪽 응답을 확인하려면 데몬의 HTTP 프록시를 거친다.

```bash
curl -x http://127.0.0.1:1055 http://<이 맥>.<tailnet>.ts.net/
```

프록시로 tailnet URL 을 그대로 요청하면 Host 헤더도 tailnet DNS 로 가서, Host 를 검사하는 서버도 통과한다.
