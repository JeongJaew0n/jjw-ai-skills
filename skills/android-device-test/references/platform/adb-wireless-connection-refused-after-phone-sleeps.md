# 무선 adb 가 Connection refused — 폰이 잠든 뒤 5555 리스너가 사라진다

> 실측 출처: 개인 Android 앱 개발 중 실기기에서 겪은 것. 앱 이름은 뺐다.

## 환경
`adb tcpip 5555` 방식(페어링 코드 방식 아님). Galaxy S23+ / Android 16.

## 증상
`adb connect <ip>:5555` → `Connection refused`. `ping` 은 되고 `nc -z <ip> 5555` 는 거부.
`adb mdns services` 에도 안 보인다.

## 원인
`adb tcpip 5555` 로 연 리스너는 재부팅·adbd 재시작으로 사라진다. 폰을 오래 잠재운 뒤
(전력 측정 30분) 끊긴 것을 확인했다. 폰의 "무선 디버깅" 토글과는 무관한 경로다.

## 해결
USB 를 꽂아 `adb tcpip 5555` 를 다시 건다. 폰 화면 조작만으로는 되살릴 수 없다.

## 재발 방지
없음. 여러 세션이 같은 adb 서버(5037)를 공유하므로 `adb kill-server` 는 쓰지 말 것 —
한쪽이 죽이면 다른 쪽 작업도 끊긴다.
