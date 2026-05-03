from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
import concurrent.futures
import logging
import os
import tempfile

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
    base_path = "/opt/render/project/src/.venv/bin/sherlock"
    if os.path.exists(base_path):
        return base_path
    return "sherlock"

SHERLOCK_CMD = get_sherlock_path()

def run_sherlock_cli(username: str):
    try:
        logger.info(f"Démarrage recherche CLI pour : {username}")
        
        # Création d'un fichier temporaire pour recevoir le JSON
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
            tmp_filename = tmp_file.name

        try:
            # Commande corrigée : --json prend maintenant le nom du fichier en argument
            cmd = [
                SHERLOCK_CMD,
                username,
                "--timeout", "60",
                "--json", tmp_filename, # On donne le fichier ici
                "--print-found"
            ]
            
            logger.debug(f"Commande lancée : {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=90
            )
            
            if result.stderr:
                logger.error(f"STDERR: {result.stderr}")

            # Lecture du fichier JSON généré
            if not os.path.exists(tmp_filename) or os.path.getsize(tmp_filename) == 0:
                logger.info("Fichier JSON vide ou inexistant.")
                return []

            with open(tmp_filename, 'r') as f:
                content = f.read().strip()
                
            if not content:
                return []

            found_profiles = []
            # Le fichier peut contenir plusieurs objets JSON ou un tableau
            # On essaie de parser ligne par ligne (NDJSON) ou comme un tableau
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
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

        finally:
            # Nettoyage du fichier temporaire
            if os.path.exists(tmp_filename):
                os.remove(tmp_filename)
                
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
