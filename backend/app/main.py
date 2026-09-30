import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .core.config import FRONTEND_DIR
from .core.database import initialize_database


# 일부 Windows 환경은 레지스트리 설정 때문에 .js를 text/plain으로 판단한다.
# ES module은 올바른 JavaScript MIME type이 아니면 브라우저가 실행을 거부한다.
mimetypes.add_type("application/javascript", ".js", strict=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Personal OS", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)


app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
