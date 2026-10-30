# 재설치·force-stop 뒤 접근성 서비스가 조용히 꺼진다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
Android 16 (Galaxy S23+). 다른 버전도 같다.

## 증상
`adb install -r` 이나 `am force-stop` 뒤 접근성 서비스가 바인딩되지 않는다.
`accessibility_enabled` 가 0 이 되고, 접근성 오버레이가 필요한 기능이 아무 말 없이 안 된다.

## 원인
Android 정상 동작. 앱 코드가 교체되거나 강제 종료되면 시스템이 접근성 서비스 등록을 해제한다.

## 해결
```
SVC=<pkg>/<service>
adb shell settings put secure enabled_accessibility_services $SVC
adb shell settings put secure accessibility_enabled 1
adb shell dumpsys accessibility | grep -c 'label='   # 1 이어야 한다
```

## 재발 방지
설치 스크립트 끝에 위 세 줄을 붙인다. adb 아티팩트가 아니라 **실사용에도 걸린다** — 사용자가
앱을 강제 종료하면 같은 상태가 된다.
