# Compose 드래그 루프에서 positionChange() 가 항상 Zero

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Jetpack Compose UI 1.12 (BOM 2026.08). `awaitEachGesture` + `drag()` 직접 루프.

## 증상
드래그 판정은 되는데 `onDrag(change.positionChange())` 로 넘기는 delta 가 항상 `Offset.Zero`.
컴파일도 되고 크래시도 없고, 창만 한 픽셀도 안 움직인다.

## 원인
`change.consume()` 을 **먼저** 부르고 `positionChange()` 를 읽었다. 소비된 변화의
`positionChange()` 는 Zero 를 돌려준다 (`positionChangeIgnoreConsumed()` 만 실제 값).
`detectDragGestures` 는 delta 를 미리 계산해 콜백에 넘기기 때문에 이 함정이 없었고,
직접 루프로 바꾸는 순간 걸렸다.

## 해결
```kotlin
val delta = change.positionChange()   // 소비 전에 읽는다
change.consume()
onDrag(delta)
```

## 재발 방지
직접 포인터 루프를 쓸 때 `consume()` 은 항상 마지막에.
