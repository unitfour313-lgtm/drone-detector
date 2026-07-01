"""Database models and operations."""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base
import os

logger = logging.getLogger(__name__)

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://detector:password@postgres:5432/drone_detection"
)

Base = declarative_base()

class Detection(Base):
    """Detection model."""
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, default=datetime.utcnow)
    object_type = Column(String, index=True)
    confidence = Column(Float)
    x_min = Column(Float)
    y_min = Column(Float)
    x_max = Column(Float)
    y_max = Column(Float)
    track_id = Column(Integer, nullable=True, index=True)
    
    def __repr__(self):
        return f"Detection(id={self.id}, type={self.object_type}, conf={self.confidence:.2f})"

class Database:
    """Database manager."""
    
    def __init__(self, database_url: str = DATABASE_URL):
        """Initialize database.
        
        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self.session = None
    
    async def init(self):
        """Initialize database connection and create tables."""
        try:
            # Create async engine
            self.engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_size=20,
                max_overflow=40
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✓ Database initialized")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    async def add_detection(self, detection: Detection) -> Detection:
        """Add detection to database.
        
        Args:
            detection: Detection object
            
        Returns:
            Saved detection
        """
        try:
            async with self.SessionLocal() as session:
                session.add(detection)
                await session.commit()
                await session.refresh(detection)
                return detection
        except Exception as e:
            logger.error(f"Error adding detection: {e}")
            raise
    
    async def get_detection(self, detection_id: int) -> Optional[Detection]:
        """Get detection by ID.
        
        Args:
            detection_id: Detection ID
            
        Returns:
            Detection or None
        """
        try:
            async with self.SessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Detection).filter(Detection.id == detection_id)
                )
                return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting detection: {e}")
            return None
    
    async def get_detections(
        self,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Detection]:
        """Get detections with filters.
        
        Args:
            since: Filter by timestamp (UTC)
            limit: Maximum number of results
            
        Returns:
            List of detections
        """
        try:
            async with self.SessionLocal() as session:
                from sqlalchemy import select, desc
                query = select(Detection)
                
                if since:
                    query = query.filter(Detection.timestamp >= since)
                
                query = query.order_by(desc(Detection.timestamp)).limit(limit)
                
                result = await session.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting detections: {e}")
            return []
    
    async def get_detections_by_track(self, track_id: int) -> List[Detection]:
        """Get all detections for a specific track.
        
        Args:
            track_id: Track ID
            
        Returns:
            List of detections
        """
        try:
            async with self.SessionLocal() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(Detection)
                    .filter(Detection.track_id == track_id)
                    .order_by(Detection.timestamp)
                )
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting track detections: {e}")
            return []
    
    async def get_stats(self, since: Optional[datetime] = None) -> dict:
        """Get statistics.
        
        Args:
            since: Filter by timestamp
            
        Returns:
            Statistics dictionary
        """
        try:
            detections = await self.get_detections(since=since, limit=10000)
            
            if not detections:
                return {
                    'total_detections': 0,
                    'unique_tracks': 0,
                    'average_confidence': 0.0,
                    'object_types': {}
                }
            
            # Calculate stats
            unique_tracks = len(set(d.track_id for d in detections if d.track_id))
            avg_confidence = sum(d.confidence for d in detections) / len(detections)
            
            # Count by object type
            object_types = {}
            for d in detections:
                object_types[d.object_type] = object_types.get(d.object_type, 0) + 1
            
            return {
                'total_detections': len(detections),
                'unique_tracks': unique_tracks,
                'average_confidence': avg_confidence,
                'object_types': object_types
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    async def clear_old_detections(self, days: int = 7):
        """Delete detections older than specified days.
        
        Args:
            days: Number of days to keep
        """
        try:
            from datetime import timedelta
            from sqlalchemy import delete
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async with self.SessionLocal() as session:
                await session.execute(
                    delete(Detection).filter(Detection.timestamp < cutoff_date)
                )
                await session.commit()
                logger.info(f"Cleared detections older than {days} days")
        except Exception as e:
            logger.error(f"Error clearing old detections: {e}")
    
    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")