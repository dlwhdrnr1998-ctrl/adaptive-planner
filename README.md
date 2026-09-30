# Personal OS MVP

흩어진 자료를 한곳으로 옮기지 않고, 오늘 실행할 행동만 통제하는 로컬 전용 Personal OS입니다.

## 현재 기능

- `TODAY`: 당일 Task, 계획시간, 80% Capacity, 주간 진행률
- `ROUTINES`: 반복 주기, 선호 요일, 목표 횟수, 수행시간 관리
- `PROJECTS`: deadline과 `NEXT ACTION` 중심의 프로젝트 관리
- `INBOX`: 제목 하나로 빠르게 저장
- 최소형 수행 기록: 실제 시간, 실제 수행량, 결과, 메모
- 복습 예정일에 따른 Review Task 생성
- 최근 수행 기록을 사용하는 적응형 목표량 추천 API
- Routine/Project의 외부 자료 위치 및 링크

## 계획 정책

Today를 열 때 당일분만 생성합니다.

1. 고정 또는 선호 요일인 Routine을 확인합니다.
2. 선호 요일이 없는 Routine은 주간 부족량과 남은 평일 수를 확인합니다.
3. 당일 계획 한도(`가용시간 × 0.8`) 안에서 Task를 생성합니다.
4. 한도를 넘는 항목은 저장하지 않고 `추가 후보`로 표시합니다.
5. 생성된 Task의 날짜를 시스템이 임의로 변경하지 않습니다.
6. 지난 미완료 항목은 별도 표시하며, 사용자 확인 후에만 재예약합니다.

주간 수행 횟수는 실제 시간이 Routine의 최소 수행시간 이상인 기록만 인정합니다.

## 기술 구성

- Python 3.11+
- FastAPI
- SQLite (`sqlite3` 표준 라이브러리)
- HTML, CSS, Vanilla JavaScript

프론트엔드는 `/api`만 호출합니다. 계획 규칙은 `backend/app/services`에 있어 UI와 분리되어 있습니다.

## 실행

PowerShell에서 프로젝트 루트 기준으로 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.seed.sample_data
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload
```

브라우저에서 <http://127.0.0.1:8000>을 엽니다. API 문서는 <http://127.0.0.1:8000/docs>에서 확인할 수 있습니다.

Windows의 `python` 실행 별칭이 잘못 연결된 경우, 설치된 Python 실행 파일의 전체 경로로 첫 번째 명령을 실행하세요.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## 데이터

SQLite 데이터는 `data/personal_os.db`에 저장되며 Git에 포함되지 않습니다. 백업할 때는 서버를 종료한 뒤 이 파일을 복사하면 됩니다.

샘플 데이터 생성은 데이터가 없는 테이블만 채우므로 여러 번 실행해도 기존 Routine과 Project를 중복 생성하지 않습니다. 시험일과 실제 deadline은 보호 대상이므로 샘플 데이터에서 임의로 지정하지 않았습니다.

## 주요 API

- `GET /api/today`: 오늘 계획 생성 및 조회
- `GET/POST/PUT /api/routines`: Routine 관리
- `GET/POST/PUT /api/projects`: Project 관리
- `POST/PATCH /api/tasks`: Task 생성 및 변경
- `POST /api/progress`: 수행 기록
- `GET/POST /api/review-items`: 복습 항목 관리
- `GET/POST /api/resources`: 원본 자료 위치 관리
- `GET/POST /api/inbox`: Inbox 관리
- `GET /api/routines/{id}/recommendation`: 수행속도 기반 추천

Task 날짜 변경에는 `confirm_reschedule=true`가 필요합니다. Routine과 Project 삭제에는 `confirm=true`가 필요합니다. 이 확인 규칙은 향후 Agent가 API를 호출해도 그대로 적용됩니다.

## 구조

```text
backend/app/api/       HTTP 요청과 응답
backend/app/core/      설정, DB 연결, 스키마
backend/app/services/  계획·용량·진행률·추천 로직
backend/seed/          샘플 데이터
frontend/              네 화면과 API 클라이언트
tests/                 비즈니스 규칙 테스트
data/                  로컬 SQLite 데이터
```
