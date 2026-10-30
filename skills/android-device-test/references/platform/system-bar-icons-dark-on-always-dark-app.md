# 항상 어두운 앱에서 상태바 아이콘이 어둡고 내비바가 밝게 나온다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
androidx.activity `enableEdgeToEdge()` (activity-compose, Compose BOM 2026.08.00) · Galaxy S23+ / Android 16 / One UI.
앱은 Compose `MaterialTheme(darkColorScheme)` 로 테마를 고정.

## 증상
설정 화면(항상 어두운 테마)에서 상태바 아이콘이 어두운 회색으로 묻히고, 하단 내비게이션 바가 `#E8E8E8`
밝은 띠로 나온다. 같은 빌드인데 몇 분 전 캡처에서는 멀쩡했다.

## 원인
`enableEdgeToEdge()` 의 기본값 `SystemBarStyle.auto` 는 **앱 테마가 아니라 기기의 다크 모드**를 보고 바
스타일을 고른다. 기기가 라이트 모드(`cmd uimode night` → `no`)가 되자 "밝은 화면용" 스타일(어두운 아이콘 +
밝은 내비바 스크림)이 적용됐다. 앱은 자체 테마로 항상 어두우니 둘이 어긋난다.
기기가 다크 모드일 때는 드러나지 않아, 멀쩡하다가 갑자기 깨진 것처럼 보였다.

## 해결
```kotlin
enableEdgeToEdge(
    statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
    navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
)
```
앱이 테마를 고정한다면 바 스타일도 같이 고정한다.

## 재발 방지
테마를 고정한 앱에서는 `enableEdgeToEdge()` 를 인자 없이 부르지 않는다. 테스트할 때 기기 다크 모드를 한 번씩 바꿔 본다.

## 확인
`adb shell cmd uimode night no` 인 상태에서 스크린샷 — 내비바 픽셀이 앱 배경색과 같고, 상태바 아이콘이 밝으면 통과.
