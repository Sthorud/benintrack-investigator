from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sherlock_project.sherlock import sherlock
import asyncio
import concurrent.futures
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

# Liste ciblée pour les pros béninois
TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock_search(username: str):
    """
    Fonction isolée pour lancer Sherlock sans bloquer l'API
    """
    try:
        logger.info(f"Démarrage de la recherche pour : {username}")
        
        # Dans la version 0.15+, on appelle sherlock sans site_list
        # Il cherche partout, puis on filtre nous-mêmes les résultats
        results_raw = sherlock(
            username=username,
            timeout=60,
            tor=False,
            unique_tor=False
            # On retire site_list car il n'est plus accepté ainsi
        )
        
        found_profiles = []
        if isinstance(results_raw, dict):
            for site_name, result_data in results_raw.items():
                # On ne garde que les sites qui sont dans notre liste blanche
                if site_name in TARGET_SITES:
                    if isinstance(result_data, dict) and "status" in result_data:
                        if result_data["status"].is_found():
                            found_profiles.append({
                                "platform": site_name,
                                "url": result_data.get("url", ""),
                                "http_status": result_data.get("http_status", 0)
                            })
        else:
            logger.warning(f"Format de retour inattendu de Sherlock: {type(results_raw)}")
            
        logger.info(f"Recherche terminée. {len(found_profiles)} profils trouvés.")
        return found_profiles
        
    except Exception as e:
        logger.error(f"Erreur critique lors de la recherche Sherlock: {str(e)}")
        raise e

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur trop court")
        
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
        logger.error(f"Erreur non gérée dans l'endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "API BeninTrack Investigator is running"}
