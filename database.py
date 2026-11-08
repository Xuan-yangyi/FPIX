from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from settings import SETTINGS

engine = create_async_engine(SETTINGS.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    from models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session