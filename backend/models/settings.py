from sqlalchemy import Column, Integer, String, Boolean
from backend.core.database import Base

class SiteCredential(Base):
    __tablename__ = "site_credentials"

    id = Column(Integer, primary_key=True, index=True)
    site_key = Column(String, unique=True, index=True) # e.g. 'hditaliabits'
    custom_name = Column(String, default="")
    is_enabled = Column(Boolean, default=True)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    requires_login = Column(Boolean, default=True)

class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    max_results = Column(Integer, default=50)
