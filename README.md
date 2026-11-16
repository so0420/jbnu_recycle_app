# jbnu_recycle_app

전북대 창의적공학설계 팀 과제: 분리배출 안내 + 수집형 게임 앱 (시범 지역: 전주시)

| 폴더 | 내용 |
|---|---|
| `backend/` | FastAPI + SQLAlchemy(async) + Alembic + MariaDB |
| `frontend/` | React + Vite + TypeScript, Capacitor(안드로이드 APK) |
| `deploy/` | 서버 배포용 docker compose, nginx 설정 |
| `data/` | 전주시 수거장·행정동 데이터 (원본: 분리의정석, 전주시 생활지리정보) |
| `docs/` | 개발계획, 게임 시스템 설계, 아트, 개인정보처리방침·이용약관 |
| `scripts/` | 데이터 가공, 밸런스 시뮬레이션 |

## 서버 배포 (SER9 Max, `~/projects/recycle`)

```bash
cd ~/projects/recycle && ./deploy/deploy.sh   # git pull → 이미지 빌드 → 재시작 → /health 확인
```
- 앱 `127.0.0.1:11010` (nginx → https://recycle.so4.kr), AI(Ollama clef-flash) `127.0.0.1:11001`, DB 는 서버 MariaDB(`recycle`)
- 설정: `deploy/.env` (git 제외, 예시는 `deploy/.env.example`). OpenAI 키·관리자 아이디·보상 배율을 여기서 바꾼다
- nginx 설정 원본: `deploy/nginx/recycle.so4.kr`
- 사진·로그·AI 모델: `deploy/runtime/` (git 제외)
- 앱 설치 파일: `deploy/runtime/apk/recycle.apk` → https://recycle.so4.kr/download/recycle.apk

## 로컬 개발
- 백엔드: `cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt`, `.env` 작성 후 `python -X utf8 -m uvicorn main:app --port 11010`
- 프론트: `cd frontend && npm install && npm run dev` (5173, `/api` 는 11010 으로 프록시)
- 게임 수치: `backend/app/game_data/*.yaml` (관리자 API `/api/v1/admin/reload-game-data` 로 다시 읽기)
- APK: `scripts/build_apk.ps1`
