from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
import concurrent.futures
import logging
import sys
import subprocess

# Tentative d'import robuste
try:
    from sherlock_project.sherlock import sherlock
except ImportError:
    # Si l'import échoue, on essaie d'installer à la volée (débugging)
    # Note: Sur Render, ça devrait être déjà installé via requirements.txt
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sherlock-project==0.14.3"])
    from sherlock_project.sherlock import sherlock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock_search(username: str):
    try:
        logger.info(f"Démarrage recherche: {username}")
        
        results_raw = sherlock(
            username=username,
            site_list=TARGET_SITES,
            timeout=60,
            tor=False,
            unique_tor=False
        )
        
        found_profiles = []
        if isinstance(results_raw, dict):
            for site_name, result_data in results_raw.items():
                if isinstance(result_data, dict) and "status" in result_
                    if result_data["status"].is_found():
                        found_profiles.append({
                            "platform": site_name,
                            "url": result_data.get("url", ""),
                            "http_status": result_data.get("http_status", 0)
                        })
        return found_profiles
        
    except Exception as e:
        logger.error(f"Erreur Sherlock: {str(e)}")
        raise e

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom trop court")
        
    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, run_sherlock_search, request.username)
            
        return {
            "username": request.username,
            "profiles_found": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "OK"}
