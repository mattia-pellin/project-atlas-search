from sqlalchemy import Column, Integer, String, Text, DateTime
import datetime
from backend.core.database import Base

class SearchCache(Base):
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, unique=True, index=True)
    results_json = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
