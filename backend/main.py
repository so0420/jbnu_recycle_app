from dotenv import load_dotenv

# 환경변수 로드 (pydantic-settings 도 .env 를 읽지만, log.py 등에서
# 직접 os.getenv 를 쓰는 모듈을 위해 가장 먼저 로드)
load_dotenv()

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import router as api_router
from app.services import scheduler

from app.core.config import settings
from app.core.security import setup_security
from app.database import engine, get_db
from app.services.ai import system_one
from app.utils.log import logger, setup_uvicorn_logging
from app.utils.custom_exceptions import http_exception_handler, global_exception_handler


async def _warm_up_ai() -> None:
    """서버 시작 때 AI 모델을 미리 메모리에 올려 첫 요청 지연을 없앤다."""
    await asyncio.sleep(3)
    try:
        await system_one.warm_up()
        logger.info("AI 모델 준비 완료")
    except httpx.HTTPError as e:
        logger.warning(f"AI 모델 준비 실패: {e!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Application startup (env={settings.ENVIRONMENT})")
    task = asyncio.create_task(scheduler.loop())
    asyncio.create_task(_warm_up_ai())
    yield
    task.cancel()
    await engine.dispose()
    logger.info("Application shutdown - DB engine disposed")


# docs 노출 여부에 따라 URL 차단
docs_url = "/docs" if settings.docs_visible else None
redoc_url = "/redoc" if settings.docs_visible else None
openapi_url = "/openapi.json" if settings.docs_visible else None

app = FastAPI(
    lifespan=lifespan,
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url,
)

# 보안 미들웨어 + rate limiter 일괄 설정
setup_security(app)

# uvicorn, fastapi 로그를 파일 핸들러와 통합
setup_uvicorn_logging()

# Exception Handlers 등록
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """DB·AI 연결 상태를 확인하는 헬스체크."""
    await db.execute(text("SELECT 1"))
    ai = "down"
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(system_one.base_url() + "/api/ps")
            ai = "ok" if r.status_code == 200 else "down"
    except httpx.HTTPError:
        pass
    return {"status": "ok", "database": "ok", "system_one": ai, "openai": bool(settings.OPENAI_API_KEY)}


@app.get("/download/recycle.apk", include_in_schema=False)
async def apk():
    f = Path(settings.UPLOAD_DIR).parent / "apk" / "recycle.apk"
    if not f.is_file():
        from fastapi import HTTPException
        raise HTTPException(404, "아직 앱 파일이 없어요")
    # 새 버전을 올리면 바로 받게 Cloudflare·브라우저 캐시를 막는다
    return FileResponse(f, media_type="application/vnd.android.package-archive", filename="recycle.apk",
                        headers={"Cache-Control": "no-store, max-age=0"})


# ---- 프론트(SPA) 서빙: 빌드 결과가 있으면 같은 주소에서 제공 ----
_dist = Path(settings.FRONTEND_DIST)
if _dist.is_dir():
    if (_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        f = (_dist / full_path).resolve()
        if full_path and f.is_file() and _dist.resolve() in f.parents:
            return FileResponse(f)
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(404)
        return FileResponse(_dist / "index.html", headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn

    # 프록시(nginx 등) 뒤에서 동작 시 X-Forwarded-For / X-Forwarded-Proto 를 신뢰하여
    # request.client.host 를 실제 클라이언트 IP 로 설정. slowapi 의 rate limit 도
    # 이 값을 사용하므로 IP 기반 제한이 정상 동작합니다.
    forwarded_allow_ips = ",".join(settings.TRUSTED_PROXIES)

    if settings.ENVIRONMENT == "production":
        logger.info("Server starting in production...")
        uvicorn.run(
            "main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            log_config=None,
            proxy_headers=True,
            forwarded_allow_ips=forwarded_allow_ips,
            server_header=False,  # "Server: uvicorn" 헤더 제거 (정보 노출 최소화)
        )
    elif settings.ENVIRONMENT == "local":
        logger.info("Server starting in local...")
        uvicorn.run(
            "main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=True,
            log_config=None,
            proxy_headers=True,
            forwarded_allow_ips=forwarded_allow_ips,
            server_header=False,  # "Server: uvicorn" 헤더 제거 (정보 노출 최소화)
        )
