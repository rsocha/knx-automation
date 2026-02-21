import logging
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, select, func

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class GroupAddressModel(Base):
    __tablename__ = "group_addresses"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    dpt: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    function: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # Internal address (not on KNX bus)
    last_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.session_factory = None
    
    async def init_db(self):
        db_path = Path(__file__).parent.parent / "data"
        db_path.mkdir(exist_ok=True)
        
        database_url = f"sqlite+aiosqlite:///{db_path}/knx_automation.db"
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized")
    
    async def create_group_address(self, ga_data) -> GroupAddressModel:
        async with self.session_factory() as session:
            existing = await session.execute(
                select(GroupAddressModel).where(GroupAddressModel.address == ga_data.address)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Address {ga_data.address} already exists")
            
            ga = GroupAddressModel(
                address=ga_data.address,
                name=ga_data.name,
                dpt=ga_data.dpt,
                description=ga_data.description,
                room=ga_data.room,
                function=ga_data.function,
                enabled=ga_data.enabled if hasattr(ga_data, 'enabled') else True,
                is_internal=ga_data.is_internal if hasattr(ga_data, 'is_internal') else False
            )
            session.add(ga)
            await session.commit()
            await session.refresh(ga)
            return ga
    
    async def upsert_group_address(self, ga_data) -> tuple:
        """Insert or update group address. Returns (model, created: bool)"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(GroupAddressModel).where(GroupAddressModel.address == ga_data.address)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing - only update if new data has values
                if ga_data.name and ga_data.name != f"GA_{ga_data.address}":
                    existing.name = ga_data.name
                if ga_data.dpt:
                    existing.dpt = ga_data.dpt
                if hasattr(ga_data, 'description') and ga_data.description:
                    existing.description = ga_data.description
                if hasattr(ga_data, 'room') and ga_data.room:
                    existing.room = ga_data.room
                if hasattr(ga_data, 'function') and ga_data.function:
                    existing.function = ga_data.function
                existing.updated_at = datetime.now()
                await session.commit()
                await session.refresh(existing)
                return existing, False
            else:
                # Create new
                ga = GroupAddressModel(
                    address=ga_data.address,
                    name=ga_data.name,
                    dpt=ga_data.dpt,
                    description=getattr(ga_data, 'description', None),
                    room=getattr(ga_data, 'room', None),
                    function=getattr(ga_data, 'function', None),
                    enabled=getattr(ga_data, 'enabled', True),
                    is_internal=getattr(ga_data, 'is_internal', False)
                )
                session.add(ga)
                await session.commit()
                await session.refresh(ga)
                return ga, True
    
    async def get_all_group_addresses(self, room=None, function=None, enabled_only=False, internal_only=None) -> List[GroupAddressModel]:
        async with self.session_factory() as session:
            query = select(GroupAddressModel)
            if room:
                query = query.where(GroupAddressModel.room == room)
            if function:
                query = query.where(GroupAddressModel.function == function)
            if enabled_only:
                query = query.where(GroupAddressModel.enabled == True)
            if internal_only is True:
                query = query.where(GroupAddressModel.is_internal == True)
            elif internal_only is False:
                query = query.where(GroupAddressModel.is_internal == False)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_group_address(self, address: str) -> Optional[GroupAddressModel]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(GroupAddressModel).where(GroupAddressModel.address == address)
            )
            return result.scalar_one_or_none()
    
    async def update_group_address(self, address: str, update_data) -> Optional[GroupAddressModel]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(GroupAddressModel).where(GroupAddressModel.address == address)
            )
            ga = result.scalar_one_or_none()
            if not ga:
                return None
            
            for key, value in update_data.model_dump(exclude_unset=True).items():
                setattr(ga, key, value)
            
            await session.commit()
            await session.refresh(ga)
            return ga
    
    async def update_group_address_value(self, address: str, value: str):
        async with self.session_factory() as session:
            result = await session.execute(
                select(GroupAddressModel).where(GroupAddressModel.address == address)
            )
            ga = result.scalar_one_or_none()
            if ga:
                ga.last_value = value
                ga.last_updated = datetime.now()
                await session.commit()
    
    async def delete_group_address(self, address: str) -> bool:
        async with self.session_factory() as session:
            result = await session.execute(
                select(GroupAddressModel).where(GroupAddressModel.address == address)
            )
            ga = result.scalar_one_or_none()
            if not ga:
                return False
            
            await session.delete(ga)
            await session.commit()
            return True
    
    async def get_group_address_count(self) -> int:
        async with self.session_factory() as session:
            result = await session.execute(select(func.count(GroupAddressModel.id)))
            return result.scalar() or 0
    
    async def clear_all_group_addresses(self):
        """Delete all group addresses from database"""
        async with self.session_factory() as session:
            await session.execute(GroupAddressModel.__table__.delete())
            await session.commit()
            logger.info("All group addresses cleared")

db_manager = DatabaseManager()
