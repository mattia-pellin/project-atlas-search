from pydantic import BaseModel
from typing import List, Optional

class SearchResult(BaseModel):
    title: str
    poster: Optional[str]
    quality: Optional[str]
    date: Optional[str]
    site: str
    url: str

class FetchLinksResult(BaseModel):
    links: List[str]
    password: Optional[str]

class SearchStatus(BaseModel):
    site: str
    status: str # 'searching', 'completed', 'error'
    error_message: Optional[str] = None
