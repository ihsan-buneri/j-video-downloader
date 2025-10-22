from sqlmodel import create_engine, SQLModel, Session
from typing import Generator
import os
from dotenv import load_dotenv

# Import all models here so SQLModel knows about them
from ..models.download_history import DownloadHistory

# Load environment variables
load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DATABASE_USERNAME')}:{os.getenv('DATABASE_PASSWORD')}@{os.getenv('DATABASE_HOST')}:{os.getenv('DATABASE_PORT')}/{os.getenv('DATABASE_NAME')}"

# Create engine
# For production, you might want to add pool settings
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to False in production to reduce logs
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Maximum number of connections to keep in the pool
    max_overflow=10,  # Maximum overflow size of the pool
)


def create_db_and_tables():
    """
    Create all database tables.
    Call this function on application startup.
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    Use this in FastAPI endpoints with Depends().

    Example:
        @app.get("/users")
        def get_users(session: Session = Depends(get_session)):
            users = session.exec(select(User)).all()
            return users
    """
    with Session(engine) as session:
        yield session
