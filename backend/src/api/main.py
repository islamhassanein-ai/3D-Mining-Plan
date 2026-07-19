import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.src.api.auth import router as auth_router
from backend.src.storage.local_filesystem import LocalFilesystemStorage

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FRONTEND_DIR = os.path.join(REPO_ROOT, "frontend")

app = FastAPI(
    title="Gold Prospect 3D Visualizer API",
    version="1.0.0",
    description="Backend API for the Gold Prospect 3D Visualization Tool"
)

# Serve uploaded files (topography CSVs, OBJ wireframes, etc.) referenced by
# their storage filename. Filenames are random UUIDs assigned at upload time
# (see LocalFilesystemStorage.save) -- unguessable, same trust model as this
# app's share-link tokens -- so an unauthenticated static mount is consistent
# with the existing security posture, not a new exposure.
app.mount("/uploads", StaticFiles(directory=LocalFilesystemStorage().base_dir), name="uploads")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.src.api.projects import router as projects_router
from backend.src.api.imports import router as imports_router
from backend.src.api.scene import router as scene_router
from backend.src.api.collars import router as collars_router
from backend.src.api.workspace import router as workspace_router
from backend.src.api.share_links import router as share_links_router, share_router as share_viewer_router
from backend.src.api.history import router as history_router
from backend.src.api.export import router as export_router
from backend.src.api.structural import router as structural_router
from backend.src.api.qaqc import router as qaqc_router

# Include routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(imports_router)
app.include_router(scene_router)
app.include_router(collars_router)
app.include_router(workspace_router)
app.include_router(share_links_router)
app.include_router(share_viewer_router)
app.include_router(history_router)
app.include_router(export_router)
app.include_router(structural_router)
app.include_router(qaqc_router)

@app.get("/api/health")
def read_root():
    return {"status": "healthy", "service": "Gold Prospect 3D Visualizer API"}

# Serve the built frontend (index.html + dist/bundle.js) from this same
# process/port, so the whole app is one thing to start and one URL to open.
# Must be mounted LAST: FastAPI/Starlette checks routes in registration
# order, so every API route above is matched first and this catch-all only
# serves what nothing else claimed. Requires `npm run build` in frontend/ to
# have produced frontend/dist/bundle.js -- see run.ps1 / README.md.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
