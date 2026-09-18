> 출처: `my-obsidian-tools/docs/troubleshootings/reusable/container-type-inline-size-blocks-width-auto.md` (2026-09-18 복사)
> 원본이 정본이다. 여기서 고치지 말고 원본을 고친 뒤 다시 가져온다.

# `container-type: inline-size` 가 걸린 요소는 `width: auto` 로 줄지 않는다

## 환경

- CSS Containment Level 3 (`container-type`) 을 지원하는 브라우저·Electron 전반
- 확인 시점: 2026-09, Chromium 기반 Electron 앱

## 증상

폭이 고정된 요소를 내용물 크기로 줄이려고 폭 속성을 풀었다.

```css
/* 호스트 앱이 걸어둔 규칙 */
.tab { container-type: inline-size; flex: 1 1 0; width: 200px; max-width: 320px; }

/* 내용물 크기로 줄이려는 시도 */
.tab.is-compact { flex: 0 0 auto; width: auto; max-width: none; }
```

줄기는 줄었는데 **내용물보다 작게 줄어 글자가 잘렸다.** 폭을 명시하면 잘리지 않지만
그러면 내용물 크기에 맞추려던 목적이 사라진다.

## 원인

`container-type: inline-size` 는 그 요소에 **inline 축 크기 컨테인먼트**를 적용한다
(`contain: layout style inline-size` 에 해당). 컨테인먼트가 걸린 요소는 **가로 크기를
자식과 무관하게** 정한다. 자식의 intrinsic size 기여가 없는 것으로 취급되므로
`width: auto` · `max-content` · `fit-content` 가 모두 "내용물 없음" 기준으로 계산된다.

컨테이너 쿼리(`@container`)를 쓰려면 이 선언이 필요하다. 그래서 프레임워크나 호스트 앱이
반응형 처리를 위해 걸어두는 경우가 많고, 그 요소를 내용물 크기로 줄이려는 쪽과 충돌한다.

## 해결

그 요소에 한해 컨테인먼트를 해제한다.

```css
.tab.is-compact {
  container-type: normal;   /* 이게 없으면 아래 셋을 풀어도 내용물 크기로 안 커진다 */
  flex: 0 0 auto;
  width: auto;
  max-width: none;
}
```

해제 전에 **그 요소를 대상으로 하는 `@container` 쿼리가 있는지** 확인한다. 있으면 그
쿼리가 적용되지 않게 되므로, 잃는 스타일이 무엇인지 보고 판단한다. 대상이 되는 자식을
어차피 숨기는 상황이라면 잃을 것이 없다.

## 재발 방지

폭이 안 줄어들거나 반대로 너무 줄어드는데 `width` · `flex` · `max-width` 를 다 만져도
안 되면 **개발자 도구에서 `container-type` 과 `contain` 을 먼저 본다.** 이 둘은 계산된
스타일에 조용히 들어가 있고 폭 속성만 보고 있으면 눈에 띄지 않는다.
