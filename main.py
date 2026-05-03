from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sherlock_project.sherlock import sherlock
import asyncio
import concurrent.futures
import logging

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

# Liste des sites à vérifier (ciblés pour les pros)
TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock_search(username: str):
    """
    Fonction qui lance Sherlock et filtre les résultats.
    Compatible avec sherlock-project 0.14.3
    """
    try:
        logger.info(f"Démarrage recherche pour : {username}")
        
        # Lancement de Sherlock
        results_raw = sherlock(
            username=username,
            site_list=TARGET_SITES,
            timeout=60,
            tor=False,
            unique_tor=False
        )
        
        found_profiles = []
        
        # Traitement des résultats
        if isinstance(results_raw, dict):
            for site_name, result_data in results_raw.items():
                # Vérification que result_data est un dictionnaire et contient 'status'
                if isinstance(result_data, dict) and "status" in result_data:
                    # Si le statut indique que le compte est trouvé
                    if result_data["status"].is_found():
                        found_profiles.append({
                            "platform": site_name,
                            "url": result_data.get("url", ""),
                            "http_status": result_data.get("http_status", 0)
                        })
        
        logger.info(f"Recherche terminée. {len(found_profiles)} profils trouvés.")
        return found_profiles
        
    except Exception as e:
        logger.error(f"Erreur critique Sherlock: {str(e)}")
        raise e

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur trop court")
        
    try:
        # Exécution dans un thread pour ne pas bloquer l'API
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, run_sherlock_search, request.username)
            
        return {
            "username": request.username,
            "profiles_found": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Erreur endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "API BeninTrack Investigator is running"}
