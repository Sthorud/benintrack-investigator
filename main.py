from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
import concurrent.futures
import logging
import sys
import os

logging.basicConfig(level=logging.DEBUG) # On passe en DEBUG pour tout voir
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock_cli(username: str):
    """
    Lance Sherlock via python -m sherlock_project pour garantir l'exécution
    dans l'environnement virtuel de Render.
    """
    try:
        logger.info(f"Démarrage recherche CLI pour : {username}")
        
        # Utilisation de python -m pour être sûr d'utiliser la version installée dans le venv
        cmd = [
            sys.executable, "-m", "sherlock_project.sherlock",
            username,
            "--timeout", "60",
            "--json",
            "--print-found" # On ne veut que les trouvés pour réduire le bruit
        ]
        
        logger.debug(f"Commande lancée : {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=90 # On augmente le timeout global
        )
        
        # Loguer la sortie brute pour débogage si ça échoue
        if result.stdout:
            logger.debug(f"STDOUT: {result.stdout[:500]}...") # Les premiers 500 chars
        if result.stderr:
            logger.error(f"STDERR: {result.stderr}")

        if result.returncode != 0:
            logger.warning(f"Sherlock a retourné un code d'erreur: {result.returncode}")
            # Parfois Sherlock retourne 1 même s'il a trouvé des choses, on continue quand même
            
        output = result.stdout.strip()
        if not output:
            logger.info("Sortie vide de Sherlock.")
            return []
            
        found_profiles = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or not line.startswith('{'):
                continue # Ignorer les lignes qui ne sont pas du JSON
            
            try:
                data = json.loads(line)
                site_name = data.get("site", "")
                
                # Vérification basique : si le site est dans notre liste OU si on veut tout voir
                # Pour l'instant, on filtre strictement
                if site_name in TARGET_SITES:
                    found_profiles.append({
                        "platform": site_name,
                        "url": data.get("url", ""),
                        "http_status": data.get("http_status", 0)
                    })
                else:
                    logger.debug(f"Site ignoré (hors cible): {site_name}")
                    
            except json.JSONDecodeError as e:
                logger.debug(f"Ligne JSON invalide ignorée: {line[:50]}")
                continue

        logger.info(f"Recherche terminée. {len(found_profiles)} profils trouvés.")
        return found_profiles
        
    except subprocess.TimeoutExpired:
        logger.warning("Timeout du processus Sherlock.")
        return []
    except Exception as e:
        logger.error(f"Exception critique: {str(e)}", exc_info=True)
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
    return {"status": "API Running"}
