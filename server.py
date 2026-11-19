import os
import json
import urllib.request
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
    raise SystemExit("DATABASE_URL o BOT_TOKEN mancanti.")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        return None
    try:
        validate(init_data, BOT_TOKEN)
        data = parse(init_data)
        return data.get("user")
    except Exception:
        return None

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS nominativi (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, prezzo REAL DEFAULT 0, cadenza TEXT, tipo TEXT, dispositivo TEXT, sistema_operativo TEXT, buffett TEXT, metodo_pagamento TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS rinnovi (id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), tipo TEXT, data_operazione TEXT, mesi INTEGER, scadenza TEXT, orario_scadenza TEXT, importo_acconto REAL DEFAULT 0, importo_saldo REAL DEFAULT 0, data_acconto TEXT, data_saldo TEXT, note TEXT, creato_il TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS servers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS resellers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS procuratori (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS autorizzati (id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL, password TEXT NOT NULL, nome TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS dispositivi (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS sistemi_operativi (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS buffett (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS metodi_pagamento (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS config_notifiche (id INTEGER PRIMARY KEY CHECK (id = 1), ora INTEGER DEFAULT 7, minuto INTEGER DEFAULT 0, attivo INTEGER DEFAULT 1)")
            cur.execute("CREATE TABLE IF NOT EXISTS saldo_rinnovi (id SERIAL PRIMARY KEY, rinnovo_id INTEGER NOT NULL REFERENCES rinnovi(id), num_credito_saldo INTEGER DEFAULT 0, data_credito_rinnovo_saldo TEXT, val_nc_dato REAL DEFAULT 0, val_nc_saldo REAL DEFAULT 0, informazioni_note TEXT, creato_il TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS note (id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), messaggio TEXT NOT NULL, creato_il TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS credenziali (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, percorso TEXT, user_id TEXT, password TEXT, informazioni TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS apk (id SERIAL PRIMARY KEY, nome_file TEXT NOT NULL, link TEXT NOT NULL, file_token TEXT, creato_il TEXT)")
            
            cur.execute("INSERT INTO config_notifiche (id, ora, minuto, attivo) VALUES (1, 7, 0, 1) ON CONFLICT (id) DO NOTHING")
            cur.execute("ALTER TABLE nominativi ADD COLUMN IF NOT EXISTS dispositivo TEXT")
            cur.execute("ALTER TABLE nominativi ADD COLUMN IF NOT EXISTS sistema_operativo TEXT")
            cur.execute("ALTER TABLE nominativi ADD COLUMN IF NOT EXISTS buffett TEXT")
            cur.execute("ALTER TABLE nominativi ADD COLUMN IF NOT EXISTS metodo_pagamento TEXT")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS orario_scadenza TEXT")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS num_credito_rich INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS num_credito_dato INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS num_credito_dare INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS data_credito_rinnovo_rich TEXT")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS data_credito_rinnovo_dato TEXT")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS val_singolo_nc_rich REAL DEFAULT 0")
            cur.execute("ALTER TABLE rinnovi ADD COLUMN IF NOT EXISTS val_nc_rich REAL DEFAULT 0")
            cur.execute("ALTER TABLE apk ADD COLUMN IF NOT EXISTS file_token TEXT")
            conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# --- API ESISTENTI (Contatti, Nominativi, Scadenze, Rinnovi, Liste, ecc.) ---
# (Per brevità, mantengo la struttura identica ai file precedenti. Assicurati che tutte le API precedenti siano presenti come nel file che ti ho mandato l'ultima volta. Qui aggiungo solo le nuove per Credenziali e APK aggiornato).

@app.get("/api/contatti")
def api_contatti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, prezzo, cadenza, tipo, dispositivo, sistema_operativo, buffett, metodo_pagamento FROM nominativi ORDER BY nominativo")
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
    oggi = datetime.now().date()
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.scadenza ASC")
            rows = cur.fetchall()
            scadenze_list = []
            for r in rows:
                scad = None
                try:
                    scad = datetime.strptime(r["scadenza"], "%d/%m/%Y").date()
                except:
                    try:
                        scad = datetime.strptime(r["scadenza"], "%Y-%m-%d").date()
                    except:
                        continue
                if scad and scad < oggi:
                    giorni_scaduti = (oggi - scad).days
                    scadenze_list.append({
                        "id": r["id"], "nominativo_id": r["nominativo_id"], "nominativo": r["nominativo"],
                        "scadenza": r["scadenza"], "orario_scadenza": r.get("orario_scadenza", ""),
                        "scaduta": True, "giorni": -giorni_scaduti
                    })
            return scadenze_list
    finally:
        conn.close()

@app.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.id, r.nominativo_id, r.tipo, r.data_operazione, r.mesi,
                r.scadenza, r.orario_scadenza, r.importo_acconto, r.importo_saldo,
                r.data_acconto, r.data_saldo, r.note, r.creato_il,
                r.num_credito_rich, r.num_credito_dato, r.num_credito_dare,
                r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato,
                r.val_singolo_nc_rich, r.val_nc_rich, n.nominativo
                FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.creato_il DESC""")
            return cur.fetchall()
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
            num_rich = int(dati.get("num_credito_rich", 0))
            num_dato = int(dati.get("num_credito_dato", 0))
            val_singolo = float(dati.get("val_singolo_nc_rich", 0))
            cur.execute("""INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, orario_scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il, num_credito_rich, num_credito_dato, num_credito_dare, data_credito_rinnovo_rich, data_credito_rinnovo_dato, val_singolo_nc_rich, val_nc_rich)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (int(dati.get("nominativo_id")), dati.get("tipo", "rinnovo"), dati.get("data_operazione"),
                 num_rich, dati.get("scadenza"), dati.get("orario_scadenza", ""),
                 float(dati.get("importo_acconto", 0)), float(dati.get("importo_saldo", 0)),
                 datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_acconto", 0)) > 0 else "",
                 datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_saldo", 0)) > 0 else "",
                 dati.get("note", ""), datetime.now().isoformat(),
                 num_rich, num_dato, num_rich - num_dato,
                 dati.get("data_credito_rinnovo_rich", ""), dati.get("data_credito_rinnovo_dato", ""),
                 val_singolo, num_rich * val_singolo))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/rinnovo/{id}")
def api_rinnovo_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saldo_rinnovi WHERE rinnovo_id = %s", (id,))
            cur.execute("DELETE FROM rinnovi WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# ... (Mantieni tutte le altre API esistenti per dispositivi, server, note, saldo_rinnovi, ecc. come nel file precedente) ...
# Per risparmiare spazio, includo qui SOLO le nuove API per Credenziali e APK. 
# ASSICURATI di avere anche le API: /api/resellers, /api/procuratori, /api/servers, /api/dispositivi, /api/sistemi_operativi, /api/buffett, /api/metodi_pagamento, /api/note, /api/saldo_rinnovi, ecc.

@app.get("/api/credenziali")
def api_credenziali(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, percorso, user_id, password, informazioni FROM credenziali ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()

class CredenzialiPayload(BaseModel):
    dati: dict

@app.post("/api/credenziali")
def api_credenziali_nuovo(payload: CredenzialiPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO credenziali (nominativo, percorso, user_id, password, informazioni)
                VALUES (%s, %s, %s, %s, %s)""",
                (dati.get("nominativo", ""), dati.get("percorso", ""), dati.get("user_id", ""),
                 dati.get("password", ""), dati.get("informazioni", "")))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.put("/api/credenziali/{id}")
def api_credenziali_modifica(id: int, payload: CredenzialiPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE credenziali SET nominativo=%s, percorso=%s, user_id=%s, password=%s, informazioni=%s WHERE id=%s""",
                (dati.get("nominativo", ""), dati.get("percorso", ""), dati.get("user_id", ""),
                 dati.get("password", ""), dati.get("informazioni", ""), id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/credenziali/{id}")
def api_credenziali_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM credenziali WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# --- API APK AGGIORNATA ---

@app.get("/api/apk")
def api_apk(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome_file, link, file_token, creato_il FROM apk ORDER BY creato_il DESC")
            return cur.fetchall()
    finally:
        conn.close()

class ApkPayload(BaseModel):
    dati: dict

@app.post("/api/apk")
def api_apk_nuovo(payload: ApkPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO apk (nome_file, link, file_token, creato_il)
                VALUES (%s, %s, %s, %s)""",
                (dati.get("nome_file", ""), dati.get("link", ""), dati.get("file_token", ""),
                 datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/apk/{id}")
def api_apk_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT nome_file, link, file_token FROM apk WHERE id = %s", (id,))
            apk = cur.fetchone()
            if not apk:
                raise HTTPException(status_code=404, detail="APK non trovato")
            
            # 1. Prova a cancellare dal server remoto (Ufile.io)
            cur.execute("SELECT percorso, user_id, password FROM credenziali ORDER BY id LIMIT 1")
            creds = cur.fetchone()
            
            if creds and creds['percorso'] and apk['file_token']:
                try:
                    # Payload generico per l'API di cancellazione. 
                    # L'utente deve impostare 'percorso' come l'URL esatto dell'API di delete di Ufile (es. https://api.ufile.io/v2/delete)
                    req_data = json.dumps({
                        "token": apk['file_token'],
                        "user": creds['user_id'],
                        "password": creds['password']
                    }).encode('utf-8')
                    
                    req = urllib.request.Request(creds['percorso'], data=req_data, method='POST')
                    req.add_header('Content-Type', 'application/json')
                    try:
                        urllib.request.urlopen(req, timeout=5)
                    except Exception as e:
                        print(f"Avviso cancellazione remota Ufile: {e}") # Procediamo comunque con la cancellazione locale
                except Exception as e:
                    print(f"Errore configurazione cancellazione remota: {e}")

            # 2. Cancella dal database locale
            cur.execute("DELETE FROM apk WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)