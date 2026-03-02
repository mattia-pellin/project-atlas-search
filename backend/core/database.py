from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import os

# Use DATABASE_DIR env var for data persistence (default: current directory)
_db_dir = os.environ.get("DATABASE_DIR", ".")
_db_path = os.path.join(_db_dir, "atlas_search.db")
DATABASE_URL = f"sqlite+aiosqlite:///{_db_path}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    import backend.models.search # Prevents circular import
    print("Initializing database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
