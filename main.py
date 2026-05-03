from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import asyncio
import concurrent.futures
import logging
import os

# Configuration des logs pour voir ce qui se passe sur Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BeninTrack Investigator API")

# Liste ciblée pour les professionnels béninois (Vitesse + Pertinence)
TARGET_SITES = [
    "Facebook", "LinkedIn", "Twitter", "Instagram", 
    "GitHub", "TikTok", "Pinterest", "YouTube"
]

class SearchRequest(BaseModel):
    username: str

def run_sherlock_cli(username: str):
    """
    Lance Sherlock via la ligne de commande et parse le résultat JSON/NDJSON.
    Cette méthode est plus stable que l'import direct du module Python sur certains serveurs.
    """
    try:
        logger.info(f"Démarrage CLI Sherlock pour : {username}")
        
        # Construction de la commande
        # --json : Sortie en format JSON
        # --timeout : Temps max par site
        cmd = [
            "sherlock", 
            username, 
            "--timeout", "60",
            "--json"
        ]
        
        # Exécution de la commande
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=70 # Timeout global un peu plus large que le timeout par site
        )
        
        if result.returncode != 0:
            logger.error(f"Erreur CLI Sherlock: {result.stderr}")
            return []
            
        output = result.stdout.strip()
        if not output:
            logger.info("Aucune sortie de la part de Sherlock.")
            return []
            
        found_profiles = []
        
        # Sherlock retourne souvent du NDJSON (Newline Delimited JSON)
        # C'est-à-dire un objet JSON par ligne, pas un tableau global.
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # Extraction des données pertinentes
                site_name = data.get("site", "")
                
                # On ne garde que les sites qui nous intéressent
                if site_name in TARGET_SITES:
                    found_profiles.append({
                        "platform": site_name,
                        "url": data.get("url", ""),
                        "http_status": data.get("http_status", 0)
                    })
                    
            except json.JSONDecodeError:
                # Si une ligne n'est pas du JSON valide, on l'ignore
                continue

        logger.info(f"Recherche terminée. {len(found_profiles)} profils trouvés sur les sites ciblés.")
        return found_profiles
        
    except subprocess.TimeoutExpired:
        logger.warning("Le processus Sherlock a mis trop de temps.")
        return []
    except Exception as e:
        logger.error(f"Exception critique lors de l'exécution CLI: {str(e)}")
        raise e

@app.post("/investigate")
async def investigate_user(request: SearchRequest):
    """
    Endpoint principal pour lancer l'investigation.
    """
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur trop court (min 3 caractères)")
        
    try:
        # On utilise un ThreadPoolExecutor car subprocess.run est bloquant
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = await loop.run_in_executor(pool, run_sherlock_cli, request.username)
            
        return {
            "username": request.username,
            "profiles_found": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Erreur non gérée dans l'endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur interne du serveur: {str(e)}")

@app.get("/")
def read_root():
    """
    Endpoint de santé pour vérifier que l'API tourne.
    """
    return {"status": "API BeninTrack Investigator is running"}
