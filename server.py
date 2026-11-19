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
            conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

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
    oggi = datetime.now()
    tra30 = oggi + timedelta(days=30)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.scadenza, r.orario_scadenza, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id")
            rows = cur.fetchall()
            scadenze_list = []
            for r in rows:
                try:
                    scad = datetime.strptime(r["scadenza"], "%d/%m/%Y")
                    if oggi <= scad <= tra30:
                        giorni = (scad - oggi).days
                        scadenze_list.append({"nominativo": r["nominativo"], "scadenza": r["scadenza"], "orario_scadenza": r.get("orario_scadenza", ""), "giorni": giorni})
                except:
                    continue
            scadenze_list.sort(key=lambda x: x["giorni"])
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
                r.val_singolo_nc_rich, r.val_nc_rich,
                n.nominativo
                FROM rinnovi r
                JOIN nominativi n ON n.id = r.nominativo_id
                ORDER BY r.scadenza DESC""")
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
            val_nc_rich = num_rich * val_singolo
            num_dare = num_rich - num_dato
            cur.execute("""INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, orario_scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il, num_credito_rich, num_credito_dato, num_credito_dare, data_credito_rinnovo_rich, data_credito_rinnovo_dato, val_singolo_nc_rich, val_nc_rich)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (int(dati.get("nominativo_id")), dati.get("tipo", "rinnovo"), dati.get("data_operazione"),
                 num_rich, dati.get("scadenza"), dati.get("orario_scadenza", ""),
                 float(dati.get("importo_acconto", 0)), float(dati.get("importo_saldo", 0)),
                 datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_acconto", 0)) > 0 else "",
                 datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_saldo", 0)) > 0 else "",
                 dati.get("note", ""), datetime.now().isoformat(),
                 num_rich, num_dato, num_dare,
                 dati.get("data_credito_rinnovo_rich", ""),
                 dati.get("data_credito_rinnovo_dato", ""),
                 val_singolo, val_nc_rich))
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
                cur.execute("""INSERT INTO nominativi 
                    (nominativo, user_id, password, prezzo, cadenza, tipo, server, reseller, 
                     dispositivo, sistema_operativo, buffett, metodo_pagamento, 
                     cellulare, procuratore, apk_utilizzata, uso_vpn, quale_vpn, citta, 
                     data_iscrizione, data_fine, informazioni)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (dati.get("nominativo",""), dati.get("user_id",""), dati.get("password",""),
                     float(dati.get("prezzo",0)), dati.get("cadenza",""), dati.get("tipo",""),
                     dati.get("server",""), dati.get("reseller",""),
                     dati.get("dispositivo",""), dati.get("sistema_operativo",""),
                     dati.get("buffett",""), dati.get("metodo_pagamento",""),
                     dati.get("cellulare",""), dati.get("procuratore",""),
                     dati.get("apk_utilizzata",""), int(dati.get("uso_vpn",0)),
                     dati.get("quale_vpn",""), dati.get("citta",""),
                     dati.get("data_iscrizione",""), dati.get("data_fine",""),
                     dati.get("informazioni","")))
            elif azione == "modifica":
                cur.execute("""UPDATE nominativi SET 
                    nominativo=%s, user_id=%s, password=%s, prezzo=%s, cadenza=%s, tipo=%s,
                    server=%s, reseller=%s, dispositivo=%s, sistema_operativo=%s,
                    buffett=%s, metodo_pagamento=%s, cellulare=%s, procuratore=%s,
                    apk_utilizzata=%s, uso_vpn=%s, quale_vpn=%s, citta=%s,
                    data_iscrizione=%s, data_fine=%s, informazioni=%s WHERE id=%s""",
                    (dati.get("nominativo"), dati.get("user_id"), dati.get("password"),
                     float(dati.get("prezzo",0)), dati.get("cadenza"), dati.get("tipo"),
                     dati.get("server"), dati.get("reseller"),
                     dati.get("dispositivo"), dati.get("sistema_operativo"),
                     dati.get("buffett"), dati.get("metodo_pagamento"),
                     dati.get("cellulare"), dati.get("procuratore"),
                     dati.get("apk_utilizzata"), int(dati.get("uso_vpn",0)),
                     dati.get("quale_vpn"), dati.get("citta"),
                     dati.get("data_iscrizione"), dati.get("data_fine"),
                     dati.get("informazioni"), dati.get("id")))
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
                col = TABELLE_COLONNE.get(tabella, 'nome')
                cur.execute(f"UPDATE {tabella} SET {col} = %s WHERE id = %s", (dati.get("nome"), dati.get("id")))
            elif azione == "nuovo_generico":
                col = TABELLE_COLONNE.get(tabella, 'nome')
                cur.execute(f"INSERT INTO {tabella} ({col}) VALUES (%s)", (dati.get("nome"),))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/api/dispositivi")
def api_dispositivi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM dispositivi ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/sistemi_operativi")
def api_sistemi_operativi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM sistemi_operativi ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/buffett")
def api_buffett():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM buffett ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/buffetts")
def api_buffetts():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM buffett ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/metodi_pagamento")
def api_metodi_pagamento():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM metodi_pagamento ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()

TABELLE_COLONNE = {
    'dispositivi': 'nome',
    'sistemi_operativi': 'nome',
    'buffett': 'nome',
    'buffetts': 'nome',
    'metodi_pagamento': 'nome',
    'resellers': 'nominativo',
    'servers': 'nominativo',
    'procuratori': 'nominativo',
}

class ListaPayload(BaseModel):
    nome: str
    tabella: str

@app.post("/api/lista/nuovo")
def api_lista_nuovo(payload: ListaPayload):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(payload.tabella, 'nome')
            cur.execute(f"INSERT INTO {payload.tabella} ({col}) VALUES (%s)", (payload.nome,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.post("/api/lista/modifica")
def api_lista_modifica(id: int, nome: str, tabella: str):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(tabella, 'nome')
            cur.execute(f"UPDATE {tabella} SET {col} = %s WHERE id = %s", (nome, id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/lista/cancella/{id}")
def api_lista_cancella(id: int, tabella: str):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {tabella} WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/api/amici")
def api_amici():
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
def api_aggiungi_amico(payload: AmicoPayload):
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
def api_rimuovi_amico(amico_id: int):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/api/config_notifiche")
def api_config_notifiche():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ora, minuto, attivo FROM config_notifiche WHERE id = 1")
            row = cur.fetchone()
            if row:
                return {"ora": row["ora"], "minuto": row["minuto"], "attivo": bool(row["attivo"])}
            return {"ora": 7, "minuto": 0, "attivo": True}
    finally:
        conn.close()

class ConfigNotifichePayload(BaseModel):
    ora: int
    minuto: int
    attivo: bool

@app.post("/api/config_notifiche")
def api_config_notifiche_update(payload: ConfigNotifichePayload):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE config_notifiche SET ora = %s, minuto = %s, attivo = %s WHERE id = 1",
                        (payload.ora, payload.minuto, 1 if payload.attivo else 0))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/api/saldo_rinnovi")
def api_saldo_rinnovi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT s.id, s.rinnovo_id, s.num_credito_saldo, s.data_credito_rinnovo_saldo,
                s.val_nc_dato, s.val_nc_saldo, s.informazioni_note, s.creato_il,
                r.num_credito_rich, r.num_credito_dato, r.data_credito_rinnovo_rich,
                r.data_credito_rinnovo_dato, r.val_nc_rich, r.val_singolo_nc_rich,
                n.nominativo
                FROM saldo_rinnovi s
                JOIN rinnovi r ON r.id = s.rinnovo_id
                JOIN nominativi n ON n.id = r.nominativo_id
                ORDER BY s.creato_il DESC""")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/rinnovi_per_saldo")
def api_rinnovi_per_saldo(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT r.id, r.num_credito_rich, r.num_credito_dato, r.num_credito_dare,
                r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato,
                r.val_nc_rich, r.val_singolo_nc_rich,
                n.nominativo
                FROM rinnovi r
                JOIN nominativi n ON n.id = r.nominativo_id
                ORDER BY n.nominativo""")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/api/saldo_rinnovo")
def api_saldo_rinnovo_nuovo(payload: RinnovoPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            rinnovo_id = int(dati.get("rinnovo_id"))
            cur.execute("SELECT num_credito_dato, val_singolo_nc_rich FROM rinnovi WHERE id = %s", (rinnovo_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Rinnovo non trovato")
            num_dato = row["num_credito_dato"]
            val_singolo = row["val_singolo_nc_rich"] or 0
            num_saldo = int(dati.get("num_credito_saldo", 0))
            val_nc_dato = num_dato * val_singolo
            val_nc_saldo = num_saldo * val_singolo
            cur.execute("""INSERT INTO saldo_rinnovi (rinnovo_id, num_credito_saldo, data_credito_rinnovo_saldo, val_nc_dato, val_nc_saldo, informazioni_note, creato_il)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (rinnovo_id, num_saldo, dati.get("data_credito_rinnovo_saldo", ""),
                 val_nc_dato, val_nc_saldo, dati.get("informazioni_note", ""),
                 datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.post("/api/saldo_rinnovo_modifica")
def api_saldo_rinnovo_modifica(payload: RinnovoPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            rinnovo_id = int(dati.get("rinnovo_id"))
            cur.execute("SELECT num_credito_dato, val_singolo_nc_rich FROM rinnovi WHERE id = %s", (rinnovo_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Rinnovo non trovato")
            num_dato = row["num_credito_dato"]
            val_singolo = row["val_singolo_nc_rich"] or 0
            num_saldo = int(dati.get("num_credito_saldo", 0))
            val_nc_dato = num_dato * val_singolo
            val_nc_saldo = num_saldo * val_singolo
            cur.execute("""UPDATE saldo_rinnovi SET num_credito_saldo=%s, data_credito_rinnovo_saldo=%s, val_nc_dato=%s, val_nc_saldo=%s, informazioni_note=%s WHERE id=%s""",
                (num_saldo, dati.get("data_credito_rinnovo_saldo", ""),
                 val_nc_dato, val_nc_saldo, dati.get("informazioni_note", ""),
                 int(dati.get("id"))))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/saldo_rinnovo/{id}")
def api_saldo_rinnovo_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saldo_rinnovi WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)