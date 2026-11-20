from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from database import init_db
from routers import nominativi, rinnovi, saldo, calcoli, crediti, liste, note, credenziali, permessi

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inizializza il database all'avvio
init_db()

# Registra tutti i router
app.include_router(nominativi.router)
app.include_router(rinnovi.router)
app.include_router(saldo.router)
app.include_router(calcoli.router)
app.include_router(crediti.router)
app.include_router(liste.router)
app.include_router(note.router)
app.include_router(credenziali.router)
app.include_router(permessi.router)

# Serve i file statici (HTML, JS, CSS)
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)