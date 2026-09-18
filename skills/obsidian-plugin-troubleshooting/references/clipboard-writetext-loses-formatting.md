> 출처: `obsidian-plugin-for-inno/docs/troubleshootings/reusable/clipboard-writetext-loses-formatting.md` (2026-09-18 복사)
> 원본이 정본이다. 여기서 고치지 말고 원본을 고친 뒤 다시 가져온다.

# `navigator.clipboard.writeText` 로 복사하면 붙여넣은 곳에서 서식이 사라진다

## 환경

| 항목 | 값 |
|---|---|
| OS | macOS 26.6.2 |
| 호스트 앱 | Obsidian 1.13.7 (Electron / Chromium 렌더러) |
| 언어 | TypeScript 5.9.3 / Node 22.12.0 |
| 관련 API | Async Clipboard API (`navigator.clipboard`) |

Electron·Chromium 렌더러에서 클립보드에 쓰는 모든 코드에 해당한다. 특정 앱이나
프레임워크에 묶인 문제가 아니다.

## 증상

마크다운 텍스트를 `navigator.clipboard.writeText(markdown)` 으로 복사한 뒤
서식을 받는 앱(Teams·Slack·Confluence·워드·메일 작성창)에 붙여넣으면
**마크다운 기호가 글자 그대로 나온다.**

```
- **굵게** 와 *기울임*
- [링크](https://example.com)
```

같은 내용을 앱 안에서 마우스로 끌어 선택해 `Cmd+C` 로 복사하면 **서식이 살아 있다.**
굵게는 굵게, 링크는 링크, 표는 표로 붙는다. 같은 원문인데 결과가 다르다.

macOS 에서는 클립보드에 실린 타입 목록으로 차이를 바로 볼 수 있다.

```bash
osascript -e 'clipboard info'
```

```
# writeText 로 복사한 뒤
«class utf8», 113, «class ut16», 172, string, 4, Unicode text, 170

# 앱이 선택 영역을 복사한 뒤
«class HTML», 490, «class utf8», 113, «class ut16», 172, string, 4, Unicode text, 170
```

`«class HTML»` 이 있고 없고의 차이다.

## 원인

**클립보드는 하나의 값이 아니라 flavor(타입)별 값의 묶음이다.** 붙여넣는 앱이 자기가
다룰 수 있는 flavor 중 가장 서식이 풍부한 것을 고른다. 서식을 받는 앱은 `text/html`
(macOS 의 `«class HTML»`)을 먼저 찾고, 없으면 `text/plain` 으로 떨어진다.

`navigator.clipboard.writeText()` 는 **`text/plain` 하나만 싣는다.** 그래서 받는 앱에
고를 것이 없다. 마크다운 문자열은 평문으로서는 완전히 정상이고, 앱은 그것을 그대로
글자로 표시한다 — 앱은 그 문자열이 마크다운이라는 사실을 알 방법이 없다.

반면 사용자가 선택 영역을 복사할 때는 브라우저가 **선택된 DOM 을 직렬화해
`text/html` 도 함께** 싣는다. 그래서 서식이 따라온다. 마크다운이 아니라 **렌더된 HTML**
이 건너간 것이다.

즉 이건 마크다운 파서나 붙여넣는 앱의 문제가 아니다. **복사하는 쪽이 flavor 를
하나만 실은 것**이 원인이다.

## 해결

`clipboard.write()` 에 `ClipboardItem` 을 주고 **`text/html` 과 `text/plain` 을 함께**
싣는다. 받는 앱이 고르게 한다 — 서식을 받는 앱은 HTML 을, 코드 편집기·터미널은
평문을 가져간다. 어느 한쪽을 포기하지 않아도 된다.

```ts
const html = renderMarkdownToHtml(markdown); // 호스트 앱의 렌더러를 쓴다

await navigator.clipboard.write([
  new ClipboardItem({
    "text/html": new Blob([html], { type: "text/html" }),
    "text/plain": new Blob([markdown], { type: "text/plain" }),
  }),
]);
```

HTML 을 직접 만들지 말고 **호스트 앱의 렌더러를 쓴다.** 마크다운 → HTML 변환을
손으로 구현하면 앱의 렌더 결과와 어긋나고, 표·중첩 목록·각주에서 금방 깨진다.
Obsidian 이라면 `MarkdownRenderer.render(app, markdown, el, sourcePath, component)`
로 화면 밖 엘리먼트에 렌더한 뒤 `el.innerHTML` 을 쓴다.

렌더 대상 엘리먼트는 **`document.body` 에 붙인다.** 완전히 떼어 둔(detached)
엘리먼트는 일부 렌더러가 처리하지 않는다. 화면 밖으로 밀어두고 끝나면 지운다.

```ts
const host = document.createElement("div");
host.style.position = "fixed";
host.style.left = "-9999px";
document.body.appendChild(host);
try {
  await render(markdown, host);
  return host.innerHTML;
} finally {
  host.remove();
}
```

### 반드시 같이 알아야 할 것 — `write()` 는 문서 포커스를 요구한다

**`clipboard.write()` 는 `writeText()` 와 달리 문서에 포커스가 없으면 거부한다.**
창이 백그라운드인 상태로 호출하면 예외가 나고, `writeText()` 로 폴백해 둔 코드는
**아무 오류 없이 평문만 실은 채 성공한 것처럼 보인다.**

이 차이 때문에 진단이 어긋날 수 있다. 실제로 이 문제를 조사할 때, 수정한 코드를
백그라운드에서 호출해 검증하다가 `«class HTML»` 이 안 붙는 것을 보고 **수정이
실패했다고 잘못 판단했다.** 창을 활성화하고 같은 호출을 하니 그대로 붙었다.

```bash
# macOS 에서 대상 앱을 활성화한 뒤 검증한다
osascript -e 'tell application "<앱 이름>" to activate'
```

폴백을 둘 때는 **어느 경로를 탔는지 사용자에게 알린다.** 서식이 빠진 것을
붙여넣고 나서 아는 것이 제일 나쁘다.

```ts
// 서식까지 실었는지를 돌려주고, 호출부가 그에 맞는 안내를 띄운다
return true;  // text/html + text/plain
return false; // text/plain 만
```

### 통하지 않은 것

- **`writeText()` 에 HTML 문자열을 넣기** — `text/plain` flavor 에 HTML 태그가
  글자로 실린다. 증상만 바뀐다 (`<strong>` 이 보인다).
- **플랫폼 도구로 우회** — macOS 의 `textutil`·`pbcopy` 로 HTML flavor 를 만드는 것은
  앱 안에서는 쓸 수 없고, 데스크톱 전용이 되어 모바일에서 깨진다.

## 재발 방지

- **클립보드에 쓰는 코드는 `writeText()` 를 기본으로 쓰지 않는다.** 붙여넣는 곳이
  서식을 받는 앱일 수 있으면 flavor 를 두 개 싣는다. 평문만으로 충분한 경우
  (경로·토큰·명령어)에만 `writeText()` 를 쓴다.
- **폴백은 조용히 두지 않는다.** `ClipboardItem` 이 없거나 `write()` 가 거부된 경로는
  사용자에게 보이게 한다.
- **클립보드 동작을 자동 테스트로 덮으려 하지 않는다.** 포커스와 권한에 의존해
  헤드리스에서 재현되지 않는다. 대신 위의 `clipboard info` 로 **flavor 목록을
  눈으로 확인**하는 절차를 수동 점검 항목에 넣는다. 확인할 것은 값이 아니라
  `«class HTML»` 의 존재 여부다.
- 검증할 때는 **대상 앱을 활성화한 상태**에서 한다. 백그라운드 호출은 거짓 음성을 준다.
