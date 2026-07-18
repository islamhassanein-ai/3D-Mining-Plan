from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.src.api.auth import router as auth_router

app = FastAPI(
    title="Gold Prospect 3D Visualizer API",
    version="1.0.0",
    description="Backend API for the Gold Prospect 3D Visualization Tool"
)

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

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Gold Prospect 3D Visualizer API"}
