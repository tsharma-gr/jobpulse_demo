from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.database.models import Cache
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class TTLCacheManager:
    """
    Manages caching of URLs and extracted content with a TTL (Time To Live).
    """
    
    @staticmethod
    def get(db: Session, key: str) -> Optional[str]:
        cache_entry = db.query(Cache).filter(Cache.key == key).first()
        if not cache_entry:
            return None
            
        # Check TTL
        if cache_entry.expires_at.tzinfo is None:
            cache_entry.expires_at = cache_entry.expires_at.replace(tzinfo=timezone.utc)
            
        if datetime.now(timezone.utc) > cache_entry.expires_at:
            logger.info(f"Cache expired for key: {key}")
            db.delete(cache_entry)
            db.commit()
            return None
            
        logger.info(f"Cache hit for key: {key}")
        return cache_entry.content

    @staticmethod
    def set(db: Session, key: str, content: str):
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.CACHE_EXPIRY_HOURS)
        
        # Upsert logic
        existing = db.query(Cache).filter(Cache.key == key).first()
        if existing:
            existing.content = content
            existing.expires_at = expires_at
        else:
            new_cache = Cache(key=key, content=content, expires_at=expires_at)
            db.add(new_cache)
            
        db.commit()
        logger.info(f"Cache set for key: {key} (Expires in {settings.CACHE_EXPIRY_HOURS}h)")

ttl_cache = TTLCacheManager()
