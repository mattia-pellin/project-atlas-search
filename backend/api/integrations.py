import myjdapi
import qbittorrentapi
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.core.database import get_db
from backend.models.settings import SiteCredential

router = APIRouter()

class QBittorrentRequest(BaseModel):
    links: List[str]

class JDownloaderRequest(BaseModel):
    links: List[str]
    password: Optional[str] = None
    package_name: Optional[str] = None

@router.post("/qbittorrent")
async def send_to_qbittorrent(req: QBittorrentRequest, db: AsyncSession = Depends(get_db)):
    if not req.links:
        return {"status": "success", "message": "No links provided"}
        
    result = await db.execute(select(SiteCredential).where(SiteCredential.site_key == "qbittorrent"))
    cred = result.scalars().first()
    
    if not cred or not cred.is_enabled:
        raise HTTPException(status_code=400, detail="qBittorrent integration is not configured or disabled")
        
    try:
        host = cred.custom_url
        if not host:
            raise HTTPException(status_code=400, detail="qBittorrent URL is not configured")
            
        qbt_client = qbittorrentapi.Client(
            host=host,
            username=cred.username,
            password=cred.password,
        )
        
        qbt_client.auth_log_in()
        qbt_client.torrents_add(urls=req.links)
        
        return {"status": "success", "message": f"Sent {len(req.links)} links to qBittorrent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to communicate with qBittorrent: {str(e)}")

@router.post("/jdownloader")
async def send_to_jdownloader(req: JDownloaderRequest, db: AsyncSession = Depends(get_db)):
    if not req.links:
        return {"status": "success", "message": "No links provided"}
        
    result = await db.execute(select(SiteCredential).where(SiteCredential.site_key == "jdownloader"))
    cred = result.scalars().first()
    
    if not cred or not cred.is_enabled:
        raise HTTPException(status_code=400, detail="JDownloader integration is not configured or disabled")
        
    try:
        jd = myjdapi.Myjdapi()
        jd.set_app_key("AtlasSearch")
        
        if not cred.username or not cred.password:
            raise HTTPException(status_code=400, detail="JDownloader email or password not configured")
            
        if not jd.connect(cred.username, cred.password):
            raise HTTPException(status_code=401, detail="Failed to authenticate with MyJDownloader")
            
        # The device name is stored in custom_name
        device_name = cred.custom_name
        if not device_name:
            raise HTTPException(status_code=400, detail="JDownloader Device Name is not configured")
            
        device = jd.get_device(device_name)
        if not device:
            raise HTTPException(status_code=404, detail=f"Device '{device_name}' not found")
            
        # Prepare parameters
        params = [
            {
                "autostart": True,
                "links": ",".join(req.links),
                "packageName": req.package_name if req.package_name else "Atlas Search Download",
                "extractPasswords": [req.password] if req.password else []
            }
        ]
        
        # Add links to linkgrabber
        device.linkgrabber.add_links(params)
        
        return {"status": "success", "message": f"Sent {len(req.links)} links to JDownloader"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to communicate with JDownloader: {str(e)}")
