from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
import concurrent.futures
import logging
import sys
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def get_sherlock_path():
    """
    Trouve le chemin absolu de l'exécutable sherlock dans le venv de Render.
    Sur Render, le venv est souvent dans /opt/render/project/src/.venv/bin/
    """
    # Chemin standard sur Render
    base_path = "/opt/render/project/src/.venv/bin/sherlock"
    if os.path.exists(base_path):
        return base_path
    
    # Fallback: essayer de le trouver via which (si disponible)
    try:
        result = subprocess.run(["which", "sherlock"], capture_output=True, text=True)
        if result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
        
    return "sherlock" # Dernier recours: espérer qu'il soit dans le PATH global

SHERLOCK_CMD = get_sherlock_path()
logger.info(f"Chemin Sherlock détecté : {SHERLOCK_CMD}")

def run_sherlock_cli(username: str):
    try:
        logger.info(f"Démarrage recherche CLI pour : {username}")
        
        # On utilise l'exécutable direct trouvé plus haut
        cmd = [
            SHERLOCK_CMD,
            username,
            "--timeout", "60",
            "--json",
            "--print-found"
        ]
        
        logger.debug(f"Commande lancée : {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=90
        )
        
        if result.stdout:
            logger.debug(f"STDOUT brut: {result.stdout[:200]}...")
        if result.stderr:
            logger.error(f"STDERR: {result.stderr}")

        output = result.stdout.strip()
        if not output:
            logger.info("Sortie vide de Sherlock.")
            return []
            
        found_profiles = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or not line.startswith('{'):
                continue 
            
            try:
                data = json.loads(line)
                site_name = data.get("site", "")
                
                if site_name in TARGET_SITES:
                    found_profiles.append({
                        "platform": site_name,
                        "url": data.get("url", ""),
                        "http_status": data.get("http_status", 0)
                    })
                    
            except json.JSONDecodeError:
                continue

        logger.info(f"Recherche terminée. {len(found_profiles)} profils trouvés.")
        return found_profiles
        
    except subprocess.TimeoutExpired:
        logger.warning("Timeout du processus Sherlock.")
        return []
    except FileNotFoundError:
        logger.error(f"L'exécutable Sherlock n'a pas été trouvé à : {SHERLOCK_CMD}")
        raise HTTPException(status_code=500, detail="Sherlock non installé correctement")
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
