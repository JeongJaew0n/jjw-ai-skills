# 실기기 검증하다 속은 것들

> 실측 출처: 개인 Android 앱(화면 전체를 덮는 오버레이 앱)을 Galaxy S23+ / Android 16 에 붙여
> 몇 주간 adb 로 검증하면서 실제로 한 번씩 속은 것. 앱 이름은 뺐다.

각 항목은 **증상 → 실제 원인 → 어떻게 피하나** 순서다.

## 입력

### 탭이 사용자가 보던 다른 앱에 들어갔다
- 증상: 우리 앱 설정을 바꾸려고 보낸 탭이 메신저 대화창에 들어갔다.
- 원인: `am start` 가 앱을 앞으로 가져오지 못했는데(사용자가 폰을 쓰는 중이었다) 좌표 탭을 그대로 보냈다.
- 피하기: 입력은 `android-device.py tap/swipe --package <pkg>` 로만 보낸다. 최상단 Activity·포커스 창·잠금 상태를 확인하고, 아니면 보내지 않는다.

### 좌표가 바뀌어 엉뚱한 스위치를 껐다
- 증상: 스위치 하나를 끄자 목록이 접혀 다음 좌표의 스위치가 바뀌었다. 설정 화면의 스크롤 위치도 매번 달랐다.
- 피하기: **누를 때마다 덤프를 다시 받는다.** 좌표를 한 번에 여러 개 계산해 두고 차례로 누르지 않는다. 라벨 옆 스위치는 `ui --switch-near "<라벨>"` 로 찾고, 원하는 상태가 될 때까지 "덤프 → 상태 확인 → 탭" 을 반복한다.

### 테스트 탭이 앱 설정을 조용히 바꿨다
- 증상: 화면이 잠긴 줄 모르고 보낸 탭이 해제 방식 설정을 바꿨다. 이후 "제스처 회귀" 로 오진했다.
- 피하기: 동작을 검증하기 전에 그 동작을 정하는 **저장된 설정값부터** 본다(`datastore <pkg>`).

### 테스트가 사용자 데이터를 바꿨다
- 증상: 앱의 "켜면 미디어 볼륨을 0 으로" 옵션이 켜진 줄 모르고 기능을 켰다. 사용자의 미디어 볼륨이 8 → 0 이 됐다.
- 원인: 그 옵션은 해제해도 되돌리지 않는 설계였다.
- 피하기: 기능을 켜기 전에 **부작용 있는 설정을 먼저 읽는다.** 테스트 전에 `snapshot`, 끝나고 `diff` 를 돈다. 이 경우 `dumpsys audio | grep setStreamVolume` 로 원래 값을 찾아 되돌렸다.

## 판정

### uiautomator 덤프에 있다고 화면에 있는 게 아니다
- 증상: 사라진 카드가 덤프에 남아 있어 "카드가 안 사라진다" 로 오진했다. 한참 원인을 찾았다.
- 피하기: 덤프는 **좌표 찾기에만** 쓴다. 보이는지는 스크린샷 픽셀로 판정한다(`shot` → `px`/`stats`).

### 밝기는 스크린샷에 안 찍힌다
- 원인: `screencap` 은 프레임버퍼를 뜬다. 창의 `screenBrightness` 나 패널 밝기는 반영되지 않는다. 픽셀이 찍혀도 눈에는 안 보일 수 있다.
- 피하기: 밝기 오버라이드가 걸렸는지는 `dumpsys display | grep mWindowManagerBrightnessOverride` 로 본다. 실제로 보이는지는 **사람 눈**으로 확인하고, 사용자에게 그렇게 말한다. "스크린샷으로 확인했다" 고 보고하지 않는다.

### 생체 인증 UI 는 스크린샷에 안 찍힌다
- 증상: 지문 프롬프트 창(`BiometricPromptRoot`)은 있는데 스크린샷에 아이콘이 없다. 삼성의 화면 내장 센서 UI 는 별도 레이어다.
- 피하기: 프롬프트가 떴는지는 창 이름(`dumpsys window windows`)으로 본다. 동작은 실제 손가락으로만 확인된다.

### 미세한 변화는 평균 밝기로 재지 않는다
- 증상: 버블이 서서히 사라지는(페이드) 효과는 뒤 배경이 어두우면 평균 밝기가 움직이지 않는다.
- 피하기: 고대비 지점(흰 막대)의 픽셀값을 본다(`px`). 위치 이동은 `stats --rect` 의 무게중심으로 잰다.

### DataStore 의 boolean 은 `strings` 로 구분이 안 된다
- 원인: `strings` 로 보면 키 이름만 보이고 값은 안 보인다.
- 피하기: `datastore <pkg>` 로 디코드한다(debuggable 빌드만). release 빌드면 동작으로 검증한다.

### 화면에 떴는지는 빌드 성공이 알려 주지 않는다
- 증상: Composable 을 만들어 놓고 호출 분기를 빠뜨렸다. 컴파일도 lint 도 통과했다.
- 피하기: UI 를 추가했으면 기기 화면에 실제로 떴는지로 확인한다.

## adb 와 연결

### `adb kill-server` 를 하지 마
- 원인: 여러 세션이 같은 adb 서버(5037)를 쓴다. 한쪽이 죽이면 다른 쪽 작업도 끊긴다. 실제로 다른 세션의 테스트를 끊은 적이 있다.
- 피하기: 연결이 이상하면 `adb devices` 로 상태만 보고 사용자에게 알린다.

### 무선 adb 가 갑자기 Connection refused
- 원인: `adb tcpip 5555` 로 연 리스너는 폰이 오래 잠들거나 adbd 가 재시작되면 사라진다.
- 피하기: USB 를 다시 꽂아 `adb tcpip` 를 건다. 자세한 건 `platform/adb-wireless-connection-refused-after-phone-sleeps.md`.

### 무선 연결이 걸리면 adb 가 안 끝난다
- 피하기: 모든 adb 호출에 타임아웃을 건다. `android-device.py` 는 기본 40초(`ANDROID_DEVICE_TIMEOUT`).

### 화면이 꺼지면 `adb shell sleep` 이 멈춘다
- 원인: 기기가 딥슬립에 들어간다.
- 피하기: 대기는 호스트 쪽에서 한다. 읽기에는 재연결 재시도를 넣는다.

### 재설치·`force-stop` 뒤 접근성 서비스가 꺼져 있다
- 원인: `accessibility_enabled` 가 0 이 된다. 시스템이 알려 주지 않는다. "접근성 창 0개" 를 코드 버그로 오진하기 쉽다.
- 피하기: 설치 전에 `snapshot`, 설치 뒤에 `diff` 를 돈다. 자세한 건 `platform/accessibility-service-silently-disabled-by-reinstall.md`.
- 알림 접근(`enabled_notification_listeners`)도 같은 이유로 꺼질 수 있다.

### adb 로 비공개 서비스·Activity 를 띄울 수 없다
- 증상: `exported="false"` 면 `am start`·`am start-foreground-service` 가 `SecurityException` / `Requires permission not exported` 로 거부된다.
- 피하기: 같은 인텐트를 쓰는 앱 UI 경로로 검증한다. 테스트하려고 export 하지 않는다. 자세한 건 `platform/adb-cannot-start-non-exported-service.md`.

### `cmd statusbar click-tile` 만으로는 TileService 가 안 붙는다
- 원인: `onStartListening` 이 돌지 않는다.
- 피하기: `cmd statusbar expand-settings` 를 먼저 부른다. 앱 버그가 아니라 adb 아티팩트다.

## 기기 상태

### 글자 크기(`font_scale`)를 바꾸면 재생 중이던 유튜브가 멈춘다
- 원인: 구성 변경으로 유튜브가 STOPPED 가 된다. 미디어 세션을 읽는 기능이 "사라졌다" 고 오진하기 쉽다.
- 피하기: 글자 크기를 먼저 바꾸고 재생을 다시 시작한 뒤 검증한다.

### 화면을 실제로 끄는 기능을 테스트하면 기기가 잠긴다
- 원인: `GLOBAL_ACTION_LOCK_SCREEN` 등으로 잠긴다. 비밀번호가 있으면 adb 로 못 푼다. 사람이 풀어야 한다.
- 피하기: 그런 테스트는 **맨 마지막에** 한다. 사용자에게 미리 말한다.

### 배터리를 많이 쓴 뒤 폰이 느려졌다
- 원인: 배터리가 떨어지자 절전 모드가 자동으로 켜졌다(Sticky). 절전 모드가 주사율을 60Hz 로 묶었고, 절전을 꺼도 주사율이 안 돌아왔다.
- 피하기: 오래 돌린 테스트 뒤 `settings get global low_power` 와 `dumpsys display | grep primary=physical` 을 확인한다. 주사율은 설정 → 디스플레이에서 사람이 되돌린다.

### 화면 회전 고정을 바꾸면 좌표가 다 틀린다
- 피하기: `guard`·`state` 가 회전을 출력한다. 좌표를 쓰기 전에 0(세로)인지 본다.

### 앱별 언어는 기기 언어를 안 바꿔도 된다 (Android 13+)
```bash
adb shell cmd locale set-app-locales <pkg> --user current --locales en-US
adb shell cmd locale set-app-locales <pkg> --user current --locales en-XA   # 의사 로케일(긴 문자열 확인)
adb shell cmd locale set-app-locales <pkg> --user current --locales ""      # 원복
```
- 바뀌지 않는 것: 런처 이름·타일 이름·접근성 설명은 그대로인 게 정상이다. 이것들은 기기 언어를 바꿔야 본다.
- 기기 언어를 바꾸는 건 사용자에게 큰 변화라 확인받는다.
