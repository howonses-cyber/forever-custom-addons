# Forever 제작 애드온 공개 업데이트 저장소

본 폴더는 **GPT 제작 애드온 전용 공개 GitHub 저장소의 초기 파일**입니다. 게임 내 공식·개인 애드온, WTF, 계정 데이터, 개인 프로필은 업로드하지 않습니다.

## 최초 한 번 필요한 작업

1. GitHub에서 `forever-custom-addons` 같은 **공개(Public)** 저장소를 만듭니다. Private 저장소는 다른 사용자가 로그인 없이 파일을 받을 수 없습니다.
2. 이 ZIP의 폴더 내용 전체(`addons`, `scripts`, `.github`, `catalog.json`, 이 README)를 공개 저장소 기본 브랜치 `main`에 올립니다. 기존 애드온 ZIP 6개를 포함합니다.
3. 저장소의 Actions 사용을 허용하고, Actions 권한이 `Contents: write`를 허용하는지 확인합니다. 최초 `push`가 게시 작업을 시작하지 않았다면 Actions → `Publish GPT custom addons` → `Run workflow`를 실행합니다.
4. Releases의 최신 릴리스에서 `catalog.json`과 여섯 ZIP이 보이고, 다음 주소가 열리는지 확인합니다.
   `https://github.com/OWNER/REPO/releases/latest/download/catalog.json`
5. **그때부터** Forever Addon Manager의 `Catalog/connection.json`에 위 URL을 고정하여 재배포합니다. 배포받는 친구는 설정할 필요가 없습니다.

## 이후 새 애드온 또는 버전업 자동 게시

- 새 제작 애드온을 만들면 `addons/` 폴더에 **애드온별 ZIP 1개**를 추가합니다.
- 버전업이면 그 애드온의 기존 ZIP을 제거하고 새 ZIP을 넣습니다. `.toc`의 `## Version`을 반드시 올려야 합니다.
- GitHub 기본 브랜치에 ZIP 변경을 커밋하면 Actions가 ZIP 구조/위험파일/버전/해시를 검사하고 공개 Release와 최신 카탈로그를 자동 갱신합니다.
- 관리툴 사용자는 실행할 때와 새로고침할 때 최신 목록을 조회하고, 필요시 업데이트 버튼으로 설치합니다. 도구 자체를 매번 업데이트할 필요는 없습니다.

### ChatGPT Library 연동 범위

`/Addon` Library는 외부 사용자가 읽을 수 없는 내부 원본 저장소입니다. Library에 ZIP을 올리기 **만으로** GitHub에 자동 게시되지 않습니다. 애드온 제작/버전업 작업 시 동일 ZIP을 GitHub 저장소 `addons/`에도 올려야 합니다. GitHub 연결이 준비되면 이 복사·커밋 작업을 대화 중 작업 흐름에 포함할 수 있습니다.

### 안전 정책

- 매니페스트에는 `kind:custom`만 포함합니다.
- 다른 사용자의 공식 애드온을 자동으로 삭제하거나 다운그레이드하지 않습니다.
- SHA-256과 압축 내부 파일 해시를 모두 검증합니다.
- 기존 제작 애드온을 단순 삭제한 커밋은 게시를 차단합니다(무단 원격 삭제 방지).
- 익명으로 공개되는 ZIP에는 비밀번호·개인 설정·WTF가 들어가면 안 됩니다.

### 참고

이 파일은 **저장소 초기 구성용**입니다. 실제 외부 서비스 연결에는 GitHub 저장소 소유자 권한 및 게시 승인 작업이 필요합니다. 이 ZIP을 만들었다고 인터넷 공개 배포가 이미 시작된 것은 아닙니다.