from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sherlock_project.sherlock import sherlock
import asyncio
import concurrent.futures

app = FastAPI(title="BeninTrack Investigator API")

# Liste ciblée pour les pros béninois (Vitesse + Pertinence)
TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock(username: str):
    """
    Fonction bloquante pour lancer Sherlock dans un thread séparé
    """
    # Sherlock retourne un dict complexe. On le simplifie.
    results_raw = sherlock(
        username=username,
        site_list=TARGET_SITES,
        timeout=60,
        tor=False,
        unique_tor=False
    )
    
    found_profiles = []
    for site_name, result_data in results_raw.items():
        # Si le statut indique que c'est trouvé
        if result_data["status"].is_found():
            found_profiles.append({
                "platform": site_name,
                "url": result_data["url"],
                "http_status": result_data["http_status"]
            })
            
    return found_profiles

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur trop court")
        
    # On lance Sherlock dans un thread pour ne pas bloquer l'API FastAPI
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        results = await loop.run_in_executor(pool, run_sherlock, request.username)
        
    return {
        "username": request.username,
        "profiles_found": results,
        "count": len(results)
    }

@app.get("/")
def read_root():
    return {"status": "API BeninTrack Investigator is running"}
