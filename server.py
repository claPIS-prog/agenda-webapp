# server.py
import os
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram_init_data import validate, parse
import uvicorn
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTHORIZED_IDS = {int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x}

if not DATABASE_URL or not BOT_TOKEN:
    raise SystemExit("❌ DATABASE_URL o BOT_TOKEN mancanti.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- FUNZIONE DI SICUREZZA ---
def get_current_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        raise HTTPException(status_code=401, detail="Header initData mancante")
    
    try:
        validate(init_data, BOT_TOKEN)
        data = parse(init_data)
        user = data.get("user")
        
        if not user:
            raise HTTPException(status_code=401, detail="Dati utente non trovati")
            
        uid = user.get("id")
        if AUTHORIZED_IDS and uid not in AUTHORIZED_IDS:
            raise HTTPException(status_code=403, detail="Utente non autorizzato")
            
        return user
    except Exception as e:
        print(f"❌ ERRORE VALIDAZIONE: {type(e).__name__} - {e}")
        raise HTTPException(status_code=401, detail=f"Autenticazione fallita: {e}")

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS nominativi (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, prezzo REAL DEFAULT 0, cadenza TEXT, tipo TEXT);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS rinnovi (id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), tipo TEXT, data_operazione TEXT, mesi INTEGER, scadenza TEXT, importo_acconto REAL DEFAULT 0, importo_saldo REAL DEFAULT 0, data_acconto TEXT, data_saldo TEXT, note TEXT, creato_il TEXT);""")
            cur.execute("CREATE TABLE IF NOT EXISTS servers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS resellers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS procuratori (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL);")
            cur.execute("""CREATE TABLE IF NOT EXISTS autorizzati (id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL, password TEXT NOT NULL, nome TEXT);""")
        conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# --- API PROTETTE ---
@app.get("/api/contatti")
def api_contatti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, prezzo, cadenza, tipo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/nominativi")
def api_nominativi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/scadenze")
def api_scadenze(request: Request):
    get_current_user(request)
    oggi = datetime.now()
    tra30 = oggi + timedelta(days=30)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.scadenza, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id")
            rows = cur.fetchall()
            scadenze_list = []
            for r in rows:
                try:
                    scad = datetime.strptime(r["scadenza"], "%d/%m/%Y")
                    if oggi <= scad <= tra30:
                        giorni = (scad - oggi).days
                        scadenze_list.append({"nominativo": r["nominativo"], "scadenza": r["scadenza"], "giorni": giorni})
                except:
                    continue
            scadenze_list.sort(key=lambda x: x["giorni"])
            return scadenze_list
    finally:
        conn.close()

class RinnovoPayload(BaseModel):
    dati: dict

@app.post("/api/rinnovo")
def api_rinnovo(payload: RinnovoPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                           (int(dati.get("nominativo_id")), dati.get("tipo", "rinnovo"), dati.get("data_operazione"), int(dati.get("mesi")), dati.get("scadenza"), float(dati.get("importo_acconto", 0)), float(dati.get("importo_saldo", 0)), "", "", "", datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/api/resellers")
def api_resellers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM resellers ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/procuratori")
def api_procuratori(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM procuratori ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/servers")
def api_servers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM servers ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

class AzionePayload(BaseModel):
    dati: dict

@app.post("/api/azione")
def api_azione(payload: AzionePayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    azione = dati.get("azione", "")
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if azione == "cancella":
                cur.execute("DELETE FROM nominativi WHERE id = %s", (dati.get("id"),))
            elif azione == "nuovo":
                cur.execute("""INSERT INTO nominativi (nominativo, prezzo, cadenza, tipo) VALUES (%s, %s, %s, %s)""", 
                (dati.get("nominativo", ""), float(dati.get("prezzo", 0)), dati.get("cadenza", ""), dati.get("tipo", "")))
            elif azione == "modifica":
                cur.execute("""UPDATE nominativi SET nominativo=%s, prezzo=%s, cadenza=%s, tipo=%s WHERE id=%s""", 
                (dati.get("nominativo"), float(dati.get("prezzo", 0)), dati.get("cadenza"), dati.get("tipo"), dati.get("id")))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.post("/api/azione_generica")
def api_azione_generica(payload: AzionePayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    azione = dati.get("azione", "")
    tabella = dati.get("tabella", "")
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if azione == "cancella_generica":
                cur.execute(f"DELETE FROM {tabella} WHERE id = %s", (dati.get("id"),))
            elif azione == "modifica_generica":
                cur.execute(f"UPDATE {tabella} SET nominativo = %s WHERE id = %s", (dati.get("nominativo"), dati.get("id")))
            elif azione == "nuovo_generico":
                cur.execute(f"INSERT INTO {tabella} (nominativo) VALUES (%s)", (dati.get("nominativo"),))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# --- API PER GLI AMICI (PROTETTE) ---
@app.get("/api/amici")
def api_amici(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, telegram_id, nome FROM autorizzati ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()

class AmicoPayload(BaseModel):
    telegram_id: int
    password: str
    nome: str

@app.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO autorizzati (telegram_id, password, nome) VALUES (%s, %s, %s) 
                           ON CONFLICT (telegram_id) DO UPDATE SET password = excluded.password, nome = excluded.nome""",
                        (payload.telegram_id, payload.password, payload.nome))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/rimuovi_amico/{amico_id}")
def api_rimuovi_amico(amico_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)