from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
import concurrent.futures
import logging
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
    base_path = "/opt/render/project/src/.venv/bin/sherlock"
    if os.path.exists(base_path):
        return base_path
    return "sherlock"

SHERLOCK_CMD = get_sherlock_path()

def run_sherlock_cli(username: str):
    # On utilise un fichier dans le dossier courant pour éviter les soucis de /tmp
    output_file = "result.json"
    
    try:
        logger.info(f"Démarrage recherche CLI pour : {username}")
        
        # Nettoyage préalable
        if os.path.exists(output_file):
            os.remove(output_file)

        cmd = [
            SHERLOCK_CMD,
            username,
            "--timeout", "60",
            "--json", output_file,
            "--folderoutput", "." # Force l'écriture dans le dossier courant
        ]
        
        logger.debug(f"Commande : {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=90,
            cwd="/opt/render/project/src" # On s'assure d'être dans le bon dossier
        )
        
        logger.debug(f"Return Code: {result.returncode}")
        if result.stderr:
            logger.error(f"STDERR: {result.stderr}")
        if result.stdout:
            logger.debug(f"STDOUT: {result.stdout}")

        if not os.path.exists(output_file):
            logger.warning("Le fichier result.json n'a pas été créé.")
            return []

        with open(output_file, 'r') as f:
            content = f.read().strip()
            
        # Nettoyage après lecture
        os.remove(output_file)

        if not content:
            return []

        found_profiles = []
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
            
        return found_profiles

    except Exception as e:
        logger.error(f"Exception: {str(e)}", exc_info=True)
        raise e
    finally:
        if os.path.exists(output_file):
            try: os.remove(output_file)
            except: pass

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom trop court")
    try:
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, run_sherlock_cli, request.username)
        return {"username": request.username, "profiles_found": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "API Running"}
