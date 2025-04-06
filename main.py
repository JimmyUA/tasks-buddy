# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager # Import asynccontextmanager
from api.v1.endpoints import tasks
from core.config import settings

# --- Lifespan Context Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    print("Application startup...")
    # You could add checks here, e.g., ensure Firestore client is working if needed.
    # Ensure Firebase Admin SDK was initialized (check done in auth_service.py)
    # Ensure Vertex AI was initialized (check done in ai_service.py)
    print(f"Running with settings: Project={settings.gcp_project_id}, Region={settings.vertex_ai_region}")
    print("--- Lifespan Startup Complete ---")

    yield # The application runs while the context manager is active

    # Code to run on shutdown
    print("--- Lifespan Shutdown Starting ---")
    print("Application shutdown...")
    # Add any cleanup logic here if needed in the future
    print("--- Lifespan Shutdown Complete ---")

# --- Initialize FastAPI app with the lifespan manager ---
app = FastAPI(
    title="AI Task Planner API",
    description="API for processing and managing tasks using AI.",
    version="0.1.0",
    lifespan=lifespan # Assign the lifespan context manager
)

# --- CORS Middleware (configure as needed for your frontend) ---
# Allows requests from your frontend domain during development/production
origins = [
    "http://localhost:5173", # Vite default dev server
    "http://localhost:3000", # Create React App default
    # Add your Firebase Hosting URL (or custom domain) when deployed
    # "https://your-firebase-project-id.web.app",
    # "https://your-custom-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)

# --- API Routers ---
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])

# --- Root Endpoint (Health Check) ---
@app.get("/", tags=["Health Check"])
async def read_root():
    return {"status": "ok", "message": "Welcome to the AI Task Planner API!"}

# --- REMOVE the old @app.on_event("startup") and @app.on_event("shutdown") functions ---
# These are now handled by the 'lifespan' context manager above.


if __name__ == '__main__':
    import uvicorn

    # Run the FastAPI app using uvicorn
    # 'app.main:app' refers to the 'app' instance in the 'app/main.py' file
    # reload=True enables auto-reloading for development, Uvicorn watches for file changes
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
