from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers.config import router as config_router
from routers.pages import router as pages_router
from routers.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="电商AI内容生产工具", lifespan=lifespan)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# API routers — always active
app.include_router(tasks_router)
app.include_router(config_router)

# Serve React SPA from frontend/dist
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist):
    # SPA mode: serve React frontend
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="spa_assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        """Serve React SPA — catch-all that returns index.html for client-side routing."""
        # API routes are already handled by routers, this only catches non-API paths
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return FileResponse(index_path, status_code=404)
else:
    # Fallback: Jinja2 pages (transitional — removed once React SPA is built)
    app.include_router(pages_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)