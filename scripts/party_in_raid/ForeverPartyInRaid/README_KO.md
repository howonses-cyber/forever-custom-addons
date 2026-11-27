# Forever Party in Raid 1.0.0

알터랙 계곡과 10~40인 공격대에 입장했을 때 **EllesmereUI의 공격대 프레임을 유지하면서** 내 공격대 소그룹(본인 포함 최대 5명)을 별도 파티형 창에 표시합니다.

- **기존 Blizzard/EllesmereUI 프레임을 직접 숨기거나 재배치하지 않습니다.** 기본 파티 프레임을 억지로 다시 켜는 대신, 실제 `raid#` 단위를 사용하는 독립 SecureGroupHeader입니다.
- 기본 표시: 공격대에 속한 경우에만. 일반 5인 파티/솔로에서는 나타나지 않습니다.
- 클릭: 좌클릭으로 대상 선택. 힐러용 클릭시전/마우스오버 동작은 EUI 자체 프레임과 동일함을 보장하지 않습니다.
- 캐릭터가 속한 공대 소그룹(1~8)을 자동 선택하며, 전투 중 조 변경은 보호 API 제한으로 전투 종료 후 반영합니다.
- 파티/공대 창 위치, 공격대 진영, 그룹 순서 등 EUI 설정과 WTF 파일은 수정하지 않습니다.

## 명령어

- `/fpr` 또는 `/공대파티` — 도움말
- `/fpr on` / `/fpr off` — 켜기/끄기
- `/fpr unlock` / `/fpr lock` — 상단 제목 드래그 허용/잠금 (전투 밖)
- `/fpr scale 1.2` — 크기 조절, 0.65~1.65
- `/fpr reset` — 위치와 크기만 초기화
- `/fpr status` — 현재 상태

## 제한 및 확인

현재 검증은 WoW Lua API 모의 검사와 정적/문법 검사이며, WoW Forever 게임 안에서 실제 40인 알방, 전투 중 공대 조 변경, 클릭시전, EUI 레이아웃 충돌은 테스트하지 않았습니다. 첫 설치 후 비전투 중 원하는 위치로 옮겨 이용하세요. 전투 중 UI 보호 제한을 우회하거나 다른 프레임을 강제로 노출하지 않습니다.

## Third-party

[EllesmereUI](https://github.com/EllesmereGaming/EllesmereUI) is an optional standalone addon by Ellesmere. Its source is not bundled with this addon. This implementation is independently authored.
