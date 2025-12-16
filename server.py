import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

app = FastAPI()

# Paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
HTML_FILE = os.path.join(ROOT_DIR, "OpenScout.htm")
RADAR_FILE = os.path.join(DATA_DIR, "radar_scores.json")
USERS_LIST_FILE = os.path.join(DATA_DIR, "users_list.json")

# Load data
def load_radar_scores():
    if os.path.exists(RADAR_FILE):
        with open(RADAR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_users_list():
    if os.path.exists(USERS_LIST_FILE):
        with open(USERS_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

@app.get("/")
async def get_index():
    return FileResponse(HTML_FILE)

@app.get("/api/radar/{username}")
async def get_radar_score(username: str):
    scores = load_radar_scores()
    if username in scores:
        return {
            "username": username,
            "radar": scores[username],
            "found": True
        }
    else:
        # Return default low scores if not found, or error
        # For demo purposes, let's return a "not found" structure
        # or just return zeros so the UI doesn't crash
        return {
            "username": username,
            "radar": [50, 50, 50, 50, 50, 50],
            "found": False,
            "message": "User data not calculated yet"
        }

@app.get("/api/users")
async def get_users():
    return load_users_list()

if __name__ == "__main__":
    print("Starting OpenScout Server at http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
