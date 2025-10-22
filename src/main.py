from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from .routes.general import general_router
from .routes.web import web_router
from .database.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup: Create database tables
    print("🚀 Starting application...")
    print("📊 Creating database tables...")
    try:
        create_db_and_tables()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"⚠️  Database initialization warning: {e}")
        print("   The app will continue, but database features may not work.")

    yield

    # Shutdown
    print("👋 Shutting down application...")


app = FastAPI(
    title="J Video Downloader",
    version="1.0.0",
    lifespan=lifespan,
)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory (for future CSS/JS files)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(web_router)  # Web interface routes (must be first for root route)
app.include_router(general_router)  # API routes


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Docker and monitoring systems.
    Returns 200 OK if the application is running.
    """
    return {"status": "healthy", "service": "j-video-downloader"}
