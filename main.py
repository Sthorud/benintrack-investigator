from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
import concurrent.futures
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

# Liste ciblée
TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock_cli(username: str):
    """
    Lance Sherlock via la ligne de commande et parse le résultat JSON
    """
    try:
        logger.info(f"Lancement CLI Sherlock pour : {username}")
        
        # Construction de la commande
        # --json produit une sortie facile à parser
        cmd = [
            "sherlock", 
            username, 
            "--timeout", "60",
            "--print-found", # Affiche seulement les trouvés
            "--json"         # Sortie en JSON
        ]
        
        # Ajout des sites ciblés si on veut limiter (optionnel, sinon il cherche partout)
        # Pour la vitesse, on laisse chercher partout et on filtre après, 
        # ou on ajoute --site Facebook --site Twitter etc. si la version CLI le supporte bien.
        # Ici, on utilise --print-found pour avoir uniquement les résultats positifs.
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=70
        )
        
        if result.returncode != 0:
            logger.error(f"Erreur CLI Sherlock: {result.stderr}")
            return []
            
        # Parse le JSON retourné par Sherlock
        # Attention: Sherlock peut retourner plusieurs objets JSON ou un tableau selon la version
        output = result.stdout.strip()
        if not output:
            return []
            
        found_profiles = []
        try:
            # Sherlock retourne souvent une liste d'objets JSON quand --json est utilisé
            data = json.loads(output)
            
            # Si c'est une liste
            if isinstance(data, list):
                for item in data:
                    site_name = item.get("site", "")
                    # Filtrer sur nos sites ciblés
                    if site_name in TARGET_SITES:
                        found_profiles.append({
                            "platform": site_name,
                            "url": item.get("url", ""),
                            "http_status": item.get("http_status", 0)
                        })
            # Si c'est un dict unique (cas rare)
            elif isinstance(data, dict):
                 site_name = data.get("site", "")
                 if site_name in TARGET_SITES:
                    found_profiles.append({
                        "platform": site_name,
                        "url": data.get("url", ""),
                        "http_status": data.get("http_status", 0)
                    })
                    
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {str(e)} - Output: {output[:200]}")
            return []

        logger.info(f"CLI terminé. {len(found_profiles)} profils trouvés.")
        return found_profiles
        
    except Exception as e:
        logger.error(f"Exception critique: {str(e)}")
        raise e

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom trop court")
        
    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, run_sherlock_cli, request.username)
            
        return {
            "username": request.username,
            "profiles_found": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "API BeninTrack Investigator is running"}
