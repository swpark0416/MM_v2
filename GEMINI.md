# MM_v2 (Miracle Morning & Habit Tower) 개발 가이드라인

통합 모노레포(Monorepo) 프로젝트인 **MM_v2**의 프론트엔드, 백엔드, 노션 DB 연동 및 하네스 개발 규칙 문서입니다[cite: 1, 2].

---

## 1. 프로젝트 폴더 구조 (Monorepo)
MM_v2/
├── index.html           <-- 프론트엔드 (GitHub Pages 배포 루트)[cite: 1, 2]
├── GEMINI.md            <-- 프로젝트 하네스 가이드라인 (본 파일)
└── backend/             <-- 백엔드 (Render 서비스 Root Directory)[cite: 1, 2]
    ├── main.py          <-- FastAPI 메인 서버 로직[cite: 1, 2]
    ├── test_main.py     <-- Pytest 자동화 테스트 스크립트[cite: 1, 2]
    ├── requirements.txt <-- 파이썬 의존성 패키지 목록
    └── .env             <-- 노션 API 인증 키 (Git 제외 대상)[cite: 1, 2]

---

## 2. 기술 스택 및 배포 정보
- **Frontend**: React 18 (UMD CDN), Babel Standalone, Vanilla CSS (`index.html` 단일 파일)[cite: 1, 2, 3]
  - **배포 주소**: GitHub Pages (`https://<username>.github.io/MM_v2`)[cite: 2]
- **Backend**: Python 3.10+, FastAPI, `notion-client`, `requests`, `uvicorn` (`backend/main.py`)[cite: 1, 2]
  - **배포 주소**: Render (`https://mm-back.onrender.com`)[cite: 1, 2]
  - **API Docs**: `https://mm-back.onrender.com/docs`[cite: 2]
- **Database**: Notion API (공부, 취미, 외면, 내면 4대 영역)[cite: 1, 2]

---

## 3. Notion 데이터베이스 스키마 제약 조건
백엔드 API 및 노션 연동 시 아래 필드명과 데이터 타입을 엄격히 준수합니다[cite: 1, 2].
* **Name** (title): 습관 이름[cite: 1, 2]
* **영역** (select): `공부`, `취미`, `외면`, `내면`[cite: 1, 2]
* **습관 상태** (select): `보유 습관`, `만들고 싶은 습관`[cite: 1, 2]
* **수준** (select): `상` (3칸), `중` (2칸), `하` (1칸)[cite: 1, 2, 4]
* **완료** (checkbox): `true` / `false`[cite: 4]

---

## 4. 핵심 기능 및 UI/UX 규칙
### 프론트엔드 (`index.html`)[cite: 1, 3]
* **3개 슬라이드 구조**: `0. Silence (명상)`, `1. Affirmation (사명서)`, `2. 습관 탑`[cite: 3]
* **상단 네비게이션**: 파란색 Active 탭 스타일 (`.top-nav`)[cite: 3]
* **습관 탑 정렬 및 게이지**:
  - 활성화된 습관은 탑 상단(배열 뒤쪽)에 배치[cite: 3]
  - 비활성화된 습관은 탑 하단(배열 앞쪽)에 흐리게 처리하여 배치[cite: 3]
  - 수준 표시는 직사각형 3칸 바 형태(상: 3칸, 중: 2칸, 하: 1칸)[cite: 3, 4]
* **상호작용**:
  - 단일 터치: 비활성화/활성화 토글 (`localStorage`에 `inactive_habit_ids` 저장)[cite: 3]
  - 롱 프레스(0.3초): 수준 변경 및 삭제 모달 창 호출[cite: 3]
  - 대기 중 습관: 각 영역 탑 하단 대기 영역 배치 및 터치 시 보유 습관 탑 승격[cite: 3]

### 백엔드 (`backend/main.py`)[cite: 1, 2]
* `GET /api/habits`: 영역별 `owned` / `wish` 분류 조회[cite: 1, 2]
* `POST /api/habits`: 새 습관 블록 추가[cite: 1, 2]
* `PATCH /api/habits/{page_id}`: 습관 수준(`level`) 또는 상태(`status`) 부분 수정[cite: 1, 2]
* `DELETE /api/habits/{page_id}`: 지정 습관 아카이브 처리[cite: 1, 2]

---

## 5. 하네스 엔지니어링 및 개발 규칙 (Gemini CLI 지침)
1. **코드 변경 시 동시성 유지**: API 수정이나 데이터 구조 변경 요청 시, `backend/main.py`와 `index.html`을 함께 검토하여 연동 에러가 발생하지 않도록 동시에 업데이트할 것[cite: 1, 2].
2. **백엔드 자동화 테스트**: 백엔드 코드 수정 후에는 반드시 `backend/` 디렉터리에서 `pytest`를 실행하여 테스트(`test_main.py`)를 통과시킬 것[cite: 1, 2].
3. **의존성 확장 금지**: 프론트엔드는 npm 빌드 도구(Vite, Webpack) 없이 CDN 방식을 고수할 것[cite: 1, 2].
4. **Git 푸시 절차**: 코드 검증이 완료되면 `git add .`, `git commit`, `git push`를 실행하여 Render 및 GitHub Pages 자동 배포를 수행할 것[cite: 1, 4].