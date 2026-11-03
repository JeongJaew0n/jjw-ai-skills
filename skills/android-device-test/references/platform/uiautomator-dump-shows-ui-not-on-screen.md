# uiautomator 덤프에 화면에 없는 UI 가 있다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Galaxy S23+ / Android 16. adb 셸의 `uiautomator dump`·`uiautomator events`.

## 증상
- 화면(스크린샷)에는 없는 카드가 `uiautomator dump` 에 있다. 다시 덤프해도 같다.
- 카드 높이(약 320px)만큼 그 아래 노드 좌표가 밀려 있다. 덤프는 탭을 y=663 이라 했는데 화면의 탭은 y=340 이었다.
- 처음엔 "덤프가 사라진 노드를 붙들고 있다" 로 오진했다.
- 그 앱은 **자기 접근성 서비스가 붙어 있지 않으면** "권한이 필요합니다" 카드를 그리는 앱이었다.

## 원인
uiautomator 는 UiAutomation 으로 붙는다. 기본값이 **붙어 있는 동안 다른 접근성 서비스를 끄는 것(suppress)** 이다.
`UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES` 를 줘야 안 끄는데, 셸의 `uiautomator dump`·`events` 에는 줄 방법이 없다.

그래서 접근성 서비스 연결 상태에 따라 화면이 바뀌는 앱은 덤프하는 순간 **실제로** 화면이 바뀐다. 덤프가 그걸 찍는다.
덤프가 끝나면 서비스가 다시 붙어 화면이 돌아오므로 앞뒤 스크린샷에는 없다.

재현:
- `uiautomator events` 를 켜 둔 동안 `dumpsys accessibility` 의 `Bound services` 에서 그 서비스가 빠졌다. 실제 화면에도
  카드가 떴다. 끄자 몇 초 안에 다시 붙고 카드가 사라졌다.
- `uiautomator dump` 도 도는 동안 서비스가 빠졌다(`dumpsys accessibility` 로 확인). 덤프에 카드가 찍힌 것은 처음 증상 그대로다.
- 덤프 직전에 가드를 통과해도, 덤프가 도는 사이 사용자가 다른 앱으로 넘어가면 덤프는 그 앱을 담는다. 덤프 결과의
  `package` 가 대상 앱인지 먼저 본다.

TalkBack 같은 사용자의 접근성 서비스도 같이 꺼진다.

## 해결
- 보이는지는 스크린샷 픽셀로 판정하고, 누를 좌표도 스크린샷에서 확인한다. 덤프 좌표는 덤프가 바꿔 놓은 화면의 좌표일 수 있다.
- 앱이 받는 접근성 이벤트를 보려고 `uiautomator events` 를 쓰지 않는다. 붙어 있는 내내 대상 서비스가 꺼져 있다.
  시험 빌드에서 그 서비스의 `onAccessibilityEvent` 를 로그로 찍는다. 서비스 설정의 `eventTypes` 에 보려는 종류가 들어 있어야 한다.
- 접근성 오버레이 창(그 서비스가 띄운 창)은 서비스가 빠질 때 같이 떨어질 수 있다고 가정한다(실측은 안 했다).
- 사용자가 TalkBack 을 쓰는 중이면 덤프 전에 말한다. 몇 초지만 화면 낭독이 끊긴다.

## 재발 방지
덤프 중에 `adb shell dumpsys accessibility | grep "Bound services"` 를 보면 이 함정인지 바로 안다. 대상 서비스가 빠지면 이것이다.
