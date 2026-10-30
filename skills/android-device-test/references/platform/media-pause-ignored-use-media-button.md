# transportControls.pause() 가 무시된다 — 미디어 버튼 이벤트를 써라

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Android `MediaController` / `MediaSessionManager`. 실측: Galaxy S23+ / Android 16, 곰오디오.

## 증상
알림 접근 권한으로 얻은 `MediaController` 에 `transportControls.pause()` 를 보냈는데 재생이
멈추지 않는다. 클릭 콜백은 정상, 올바른 세션도 선택됐다(로그로 확인). 앱이 조용히 무시한다.

## 원인
그 세션의 `PlaybackState.actions` 가 `ACTION_PAUSE`(2)·`ACTION_PLAY`(4) 를 포함하지 않는다.
곰오디오는 `actions=0x204 = PLAY_PAUSE(0x200) + PLAY(0x4)` 만 준다 — 즉 개별 pause 는
지원하지 않고 **PLAY_PAUSE 토글만** 받는다. `transportControls.pause()` 는 `ACTION_PAUSE` 가
있어야 콜백까지 도달하고, 없으면 버려진다.

## 해결
잠금화면 재생 버튼과 같은 경로 — **미디어 버튼 이벤트**를 보낸다. 거의 모든 앱이 처리한다.
```kotlin
controller.dispatchMediaButtonEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE))
controller.dispatchMediaButtonEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE))
```
next/previous 도 `KEYCODE_MEDIA_NEXT`/`KEYCODE_MEDIA_PREVIOUS` 로. 상태로 아이콘만 가르고
실제 토글은 미디어 키에 맡긴다.

## 재발 방지
미디어 제어는 처음부터 미디어 버튼 이벤트로. transportControls 의 개별 play/pause 는
actions 비트가 보장될 때만 쓴다.
