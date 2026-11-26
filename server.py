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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

ALL_MODULES = [
    "nominativo", "lista", "scadenze", "rinnovi", "storico_rinnovi",
    "saldo_rinnovi", "reseller", "procuratori", "server", "nota",
    "credenziali", "permessi", "dispositivi", "sistemi_op", "buffett",
    "pagamenti", "operatori_it", "tabelle", "crediti"
]

def get_current_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        init_data = request.query_params.get("initData")
    if not init_data:
        if AUTHORIZED_IDS:
            return {"id": list(AUTHORIZED_IDS)[0], "first_name": "Admin", "is_admin": True}
        return None
    try:
        validate(init_data, BOT_TOKEN)
        data = parse(init_data)
        user = data.get("user")
        if user:
            return {"id": user["id"], "first_name": user.get("first_name", ""), "is_admin": user["id"] in AUTHORIZED_IDS}
        return None
    except Exception:
        if AUTHORIZED_IDS:
            return {"id": list(AUTHORIZED_IDS)[0], "first_name": "Admin", "is_admin": True}
        return None

def init_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS nominativi (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, tipo TEXT, prezzo REAL DEFAULT 0, cadenza TEXT, tipo_linea TEXT, dispositivo TEXT, sistema_operativo TEXT, buffett TEXT, metodo_pagamento TEXT, operatore_it TEXT, server TEXT, reseller TEXT, user_id TEXT, password TEXT, cellulare TEXT, procuratore TEXT, apk_utilizzata TEXT, uso_vpn INTEGER DEFAULT 0, quale_vpn TEXT, citta TEXT, data_iscrizione TEXT, data_fine TEXT, informazioni TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS rinnovi (id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), tipo TEXT, data_operazione TEXT, mesi INTEGER, scadenza TEXT, orario_scadenza TEXT, importo_acconto REAL DEFAULT 0, importo_saldo REAL DEFAULT 0, data_acconto TEXT, data_saldo TEXT, note TEXT, creato_il TEXT, num_credito_rich INTEGER DEFAULT 0, num_credito_dato INTEGER DEFAULT 0, num_credito_dare INTEGER DEFAULT 0, data_credito_rinnovo_rich TEXT, data_credito_rinnovo_dato TEXT, val_singolo_nc_rich REAL DEFAULT 0, val_nc_rich REAL DEFAULT 0)")
            cur.execute("CREATE TABLE IF NOT EXISTS servers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS resellers (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS procuratori (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS autorizzati (id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL, password TEXT NOT NULL, nome TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS dispositivi (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS sistemi_operativi (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS buffett (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS metodi_pagamento (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS operatori_it (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS saldo_rinnovi (id SERIAL PRIMARY KEY, rinnovo_id INTEGER NOT NULL REFERENCES rinnovi(id), num_credito_saldo INTEGER DEFAULT 0, data_credito_rinnovo_saldo TEXT, val_nc_dato REAL DEFAULT 0, val_nc_saldo REAL DEFAULT 0, informazioni_note TEXT, creato_il TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS note (id SERIAL PRIMARY KEY, nominativo_id INTEGER NOT NULL REFERENCES nominativi(id), messaggio TEXT NOT NULL, creato_il TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS credenziali (id SERIAL PRIMARY KEY, nominativo TEXT NOT NULL, nome_file TEXT, link TEXT, percorso TEXT, user_id TEXT, password TEXT, file_token TEXT, scadenza TEXT, informazioni TEXT, creato_il TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS permessi (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES autorizzati(id), modulo TEXT NOT NULL, attivo BOOLEAN DEFAULT FALSE, UNIQUE(user_id, modulo))")
            cur.execute("""CREATE TABLE IF NOT EXISTS calcoli (
                id SERIAL PRIMARY KEY,
                nominativo_da TEXT, nominativo_a TEXT,
                reseller_da TEXT, reseller_a TEXT,
                procuratore_da TEXT, procuratore_a TEXT,
                periodo_da TEXT, periodo_a TEXT,
                importo_nuovo REAL DEFAULT 0, acconto_nuovo REAL DEFAULT 0, acconto_saldo_nuovo REAL DEFAULT 0,
                totale_acconti_nuovi REAL DEFAULT 0, info_saldo_nuovo TEXT, info_saldo_rinnovo_nuovo TEXT,
                importo_rinnovo REAL DEFAULT 0, acconto_rinnovo REAL DEFAULT 0, acconto_saldo_rinnovo REAL DEFAULT 0,
                totale_acconti_rinnovo REAL DEFAULT 0, info_saldo_rinnovo TEXT,
                importo_omaggio REAL DEFAULT 0, acconto_omaggio REAL DEFAULT 0, acconto_saldo_omaggio REAL DEFAULT 0,
                totale_acconti_omaggio REAL DEFAULT 0,
                crediti_rich INTEGER DEFAULT 0, crediti_dati INTEGER DEFAULT 0, crediti_dare INTEGER DEFAULT 0,
                crediti_rich_omaggio INTEGER DEFAULT 0, crediti_dati_omaggio INTEGER DEFAULT 0, crediti_dare_omaggio INTEGER DEFAULT 0,
                totale_nc REAL DEFAULT 0, totale_nc_omaggio REAL DEFAULT 0,
                totale_generale REAL DEFAULT 0, note TEXT, creato_il TEXT
            )""")
            cur.execute("CREATE TABLE IF NOT EXISTS crediti (id SERIAL PRIMARY KEY, data_acquisto TEXT, fornitore TEXT, modalita_pagamento TEXT, quantita INTEGER DEFAULT 0, valore REAL DEFAULT 0, note TEXT, creato_il TEXT)")
            for col, typ in [("operatore_it","TEXT"),("server","TEXT"),("reseller","TEXT"),("user_id","TEXT"),("password","TEXT"),("cellulare","TEXT"),("procuratore","TEXT"),("apk_utilizzata","TEXT"),("quale_vpn","TEXT"),("citta","TEXT"),("data_iscrizione","TEXT"),("data_fine","TEXT"),("informazioni","TEXT"),("tipo_linea","TEXT")]:
                cur.execute(f"ALTER TABLE nominativi ADD COLUMN IF NOT EXISTS {col} {typ}")
            cur.execute("SELECT id FROM autorizzati")
            for u in cur.fetchall():
                for mod in ALL_MODULES:
                    cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, TRUE) ON CONFLICT (user_id, modulo) DO NOTHING", (u["id"], mod))
            conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# === PERMESSI / AMICI ===
@app.get("/api/amici")
def api_amici(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.telegram_id,
                       COALESCE(a.nome, n.nominativo) AS nome,
                       COALESCE(a.nome, n.nominativo) AS nominativo
                FROM autorizzati a
                LEFT JOIN nominativi n ON n.id = a.id
                ORDER BY nome, a.id
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/lista_permessi")
def api_lista_permessi(q: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT a.id, a.telegram_id,
                       COALESCE(a.nome, n.nominativo, 'Utente #' || a.id::text) AS nome,
                       COALESCE(a.nome, n.nominativo, 'Utente #' || a.id::text) AS nominativo
                FROM autorizzati a
                LEFT JOIN nominativi n ON n.id = a.id
                WHERE 1=1
            """
            params = []
            if q and q.strip():
                query += " AND (LOWER(COALESCE(a.nome, n.nominativo, '')) LIKE %s OR CAST(a.telegram_id AS TEXT) LIKE %s)"
                pattern = f"%{q.strip().lower()}%"
                params.extend([pattern, pattern])
            query += " ORDER BY nome, a.id"
            cur.execute(query, params)
            utenti = cur.fetchall()

            cur.execute("SELECT user_id, modulo, attivo FROM permessi")
            perm_rows = cur.fetchall()
            perms_by_user = {}
            for pr in perm_rows:
                uid = pr["user_id"]
                if uid not in perms_by_user:
                    perms_by_user[uid] = {mod: False for mod in ALL_MODULES}
                if pr["modulo"] in ALL_MODULES:
                    perms_by_user[uid][pr["modulo"]] = bool(pr["attivo"])

            risultato = []
            for u in utenti:
                uid = u["id"]
                mappa = perms_by_user.get(uid, {mod: False for mod in ALL_MODULES})
                attivi = [mod for mod, attivo in mappa.items() if attivo]
                risultato.append({
                    "id": uid,
                    "telegram_id": u["telegram_id"],
                    "nome": u["nome"],
                    "nominativo": u["nominativo"],
                    "permessi": mappa,
                    "moduli_attivi": attivi,
                    "totale_moduli_attivi": len(attivi)
                })
            return risultato
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
            cur.execute("INSERT INTO autorizzati (telegram_id, password, nome) VALUES (%s, %s, %s) ON CONFLICT (telegram_id) DO UPDATE SET password = excluded.password, nome = excluded.nome RETURNING id", (payload.telegram_id, payload.password, payload.nome))
            new_id = cur.fetchone()["id"]
            for mod in ALL_MODULES:
                cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, TRUE) ON CONFLICT (user_id, modulo) DO NOTHING", (new_id, mod))
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
            cur.execute("DELETE FROM permessi WHERE user_id = %s", (amico_id,))
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.get("/api/permessi/{user_id}")
def api_get_permessi(user_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {row["modulo"]: bool(row["attivo"]) for row in rows}
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            return perms
    finally:
        conn.close()

class PermessiPayload(BaseModel):
    user_id: int
    permessi: dict

@app.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            for modulo, attivo in payload.permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, %s) ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = excluded.attivo", (payload.user_id, modulo, bool(attivo)))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === NOMINATIVI / LISTA ===
@app.get("/api/nominativi")
def api_nominativi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, tipo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/contatti")
def api_contatti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, tipo, prezzo, cadenza, tipo_linea, dispositivo, sistema_operativo, buffett, metodo_pagamento, operatore_it FROM nominativi ORDER BY nominativo")
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
                    (nominativo, tipo, user_id, password, prezzo, cadenza, tipo_linea, server, reseller, 
                     dispositivo, sistema_operativo, buffett, metodo_pagamento, operatore_it, 
                     cellulare, procuratore, apk_utilizzata, uso_vpn, quale_vpn, citta, 
                     data_iscrizione, data_fine, informazioni) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                    (dati.get("nominativo",""), dati.get("tipo",""), dati.get("user_id",""), dati.get("password",""), 
                     float(dati.get("prezzo",0)), dati.get("cadenza",""), dati.get("tipo_linea",""), 
                     dati.get("server",""), dati.get("reseller",""),
                     dati.get("dispositivo",""), dati.get("sistema_operativo",""),
                     dati.get("buffett",""), dati.get("metodo_pagamento",""), dati.get("operatore_it",""),
                     dati.get("cellulare",""), dati.get("procuratore",""),
                     dati.get("apk_utilizzata",""), int(dati.get("uso_vpn",0)),
                     dati.get("quale_vpn",""), dati.get("citta",""),
                     dati.get("data_iscrizione",""), dati.get("data_fine",""),
                     dati.get("informazioni","")))
            elif azione == "modifica":
                cur.execute("""UPDATE nominativi SET 
                    nominativo=%s, tipo=%s, user_id=%s, password=%s, prezzo=%s, cadenza=%s, tipo_linea=%s, 
                    server=%s, reseller=%s, dispositivo=%s, sistema_operativo=%s, 
                    buffett=%s, metodo_pagamento=%s, operatore_it=%s, cellulare=%s, procuratore=%s, 
                    apk_utilizzata=%s, uso_vpn=%s, quale_vpn=%s, citta=%s, 
                    data_iscrizione=%s, data_fine=%s, informazioni=%s WHERE id=%s""", 
                    (dati.get("nominativo"), dati.get("tipo"), dati.get("user_id"), dati.get("password"), 
                     float(dati.get("prezzo",0)), dati.get("cadenza"), dati.get("tipo_linea"), 
                     dati.get("server"), dati.get("reseller"),
                     dati.get("dispositivo"), dati.get("sistema_operativo"),
                     dati.get("buffett"), dati.get("metodo_pagamento"), dati.get("operatore_it"),
                     dati.get("cellulare"), dati.get("procuratore"),
                     dati.get("apk_utilizzata"), int(dati.get("uso_vpn",0)),
                     dati.get("quale_vpn"), dati.get("citta"),
                     dati.get("data_iscrizione"), dati.get("data_fine"),
                     dati.get("informazioni"), dati.get("id")))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === SCADENZE ===
@app.get("/api/scadenze")
def api_scadenze(request: Request):
    get_current_user(request)
    oggi = datetime.now().date()
    limite = oggi + timedelta(days=7)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.scadenza ASC")
            rows = cur.fetchall()
            out = []
            for r in rows:
                scad = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        scad = datetime.strptime(r["scadenza"], fmt).date(); break
                    except: pass
                if not scad:
                    continue
                if scad <= limite:
                    delta = (scad - oggi).days
                    out.append({"id": r["id"], "nominativo_id": r["nominativo_id"], "nominativo": r["nominativo"], "scadenza": r["scadenza"], "orario_scadenza": r.get("orario_scadenza",""), "scaduta": delta < 0, "giorni": delta})
            return out
    finally:
        conn.close()

@app.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.nominativo_id, r.tipo, r.data_operazione, r.mesi, r.scadenza, r.orario_scadenza, r.importo_acconto, r.importo_saldo, r.data_acconto, r.data_saldo, r.note, r.creato_il, r.num_credito_rich, r.num_credito_dato, r.num_credito_dare, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato, r.val_singolo_nc_rich, r.val_nc_rich, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY r.creato_il DESC")
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
            cur.execute("INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, orario_scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il, num_credito_rich, num_credito_dato, num_credito_dare, data_credito_rinnovo_rich, data_credito_rinnovo_dato, val_singolo_nc_rich, val_nc_rich) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (int(dati.get("nominativo_id")), dati.get("tipo","rinnovo"), dati.get("data_operazione"), num_rich, dati.get("scadenza"), dati.get("orario_scadenza",""), float(dati.get("importo_acconto",0)), float(dati.get("importo_saldo",0)), datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_acconto",0))>0 else "", datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_saldo",0))>0 else "", dati.get("note",""), datetime.now().isoformat(), num_rich, num_dato, num_rich - num_dato, dati.get("data_credito_rinnovo_rich",""), dati.get("data_credito_rinnovo_dato",""), val_singolo, num_rich * val_singolo))
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

# === SALDO RINNOVI ===
@app.get("/api/saldo_rinnovi")
def api_saldo_rinnovi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT s.id, s.rinnovo_id, s.num_credito_saldo, s.data_credito_rinnovo_saldo, s.val_nc_dato, s.val_nc_saldo, s.informazioni_note, s.creato_il, r.num_credito_rich, r.num_credito_dato, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato, r.val_nc_rich, r.val_singolo_nc_rich, n.nominativo FROM saldo_rinnovi s JOIN rinnovi r ON r.id = s.rinnovo_id JOIN nominativi n ON n.id = r.nominativo_id ORDER BY s.creato_il DESC")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/rinnovi_per_saldo")
def api_rinnovi_per_saldo(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.num_credito_rich, r.num_credito_dato, r.num_credito_dare, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato, r.val_nc_rich, r.val_singolo_nc_rich, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY n.nominativo")
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
            if not row: raise HTTPException(status_code=404, detail="Rinnovo non trovato")
            num_dato = row["num_credito_dato"]; val_singolo = row["val_singolo_nc_rich"] or 0
            num_saldo = int(dati.get("num_credito_saldo", 0))
            cur.execute("INSERT INTO saldo_rinnovi (rinnovo_id, num_credito_saldo, data_credito_rinnovo_saldo, val_nc_dato, val_nc_saldo, informazioni_note, creato_il) VALUES (%s,%s,%s,%s,%s,%s,%s)", (rinnovo_id, num_saldo, dati.get("data_credito_rinnovo_saldo",""), num_dato*val_singolo, num_saldo*val_singolo, dati.get("informazioni_note",""), datetime.now().isoformat()))
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

# === LISTE DI SUPPORTO ===
@app.get("/api/resellers")
def api_resellers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM resellers ORDER BY nominativo"); return cur.fetchall()
    finally: conn.close()

@app.get("/api/procuratori")
def api_procuratori(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM procuratori ORDER BY nominativo"); return cur.fetchall()
    finally: conn.close()

@app.get("/api/servers")
def api_servers(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo FROM servers ORDER BY nominativo"); return cur.fetchall()
    finally: conn.close()

@app.get("/api/dispositivi")
def api_dispositivi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM dispositivi ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@app.get("/api/sistemi_operativi")
def api_sistemi_operativi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM sistemi_operativi ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@app.get("/api/buffett")
def api_buffett():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM buffett ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

@app.get("/api/metodi_pagamento")
def api_metodi_pagamento():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM metodi_pagamento ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

TABELLE_COLONNE = {'dispositivi':'nome','sistemi_operativi':'nome','buffett':'nome','metodi_pagamento':'nome','resellers':'nominativo','servers':'nominativo','procuratori':'nominativo','operatori_it':'nome'}

class ListaPayload(BaseModel):
    nome: str
    tabella: str

@app.post("/api/lista/nuovo")
def api_lista_nuovo(payload: ListaPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(payload.tabella, 'nome')
            cur.execute(f"INSERT INTO {payload.tabella} ({col}) VALUES (%s)", (payload.nome,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.post("/api/lista/modifica")
def api_lista_modifica(id: int, nome: str, tabella: str, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            col = TABELLE_COLONNE.get(tabella, 'nome')
            cur.execute(f"UPDATE {tabella} SET {col} = %s WHERE id = %s", (nome, id))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.delete("/api/lista/cancella/{id}")
def api_lista_cancella(id: int, tabella: str, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {tabella} WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

# === OPERATORI IT ===
@app.get("/api/operatori_it")
def api_operatori_it(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome FROM operatori_it ORDER BY nome"); return cur.fetchall()
    finally: conn.close()

class OperatorePayload(BaseModel):
    dati: dict

@app.post("/api/operatori_it")
def api_operatori_it_nuovo(payload: OperatorePayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO operatori_it (nome) VALUES (%s)", (payload.dati.get("nome",""),))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.put("/api/operatori_it/{id}")
def api_operatori_it_modifica(id: int, payload: OperatorePayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE operatori_it SET nome = %s WHERE id = %s", (payload.dati.get("nome",""), id))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.delete("/api/operatori_it/{id}")
def api_operatori_it_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operatori_it WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

# === NOTE ===
@app.get("/api/note")
def api_note(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT n.id, n.nominativo_id, n.messaggio, n.creato_il, nom.nominativo FROM note n JOIN nominativi nom ON nom.id = n.nominativo_id ORDER BY n.creato_il DESC")
            return cur.fetchall()
    finally: conn.close()

class NotaPayload(BaseModel):
    dati: dict

@app.post("/api/note")
def api_note_nuovo(payload: NotaPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note (nominativo_id, messaggio, creato_il) VALUES (%s,%s,%s)", (int(dati.get("nominativo_id")), dati.get("messaggio",""), datetime.now().isoformat()))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.delete("/api/note/{id}")
def api_note_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM note WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

# === CREDENZIALI ===
@app.get("/api/credenziali")
def api_credenziali(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, nome_file, link, percorso, user_id, password, file_token, scadenza, informazioni, creato_il FROM credenziali ORDER BY creato_il DESC")
            return cur.fetchall()
    finally: conn.close()

class CredenzialiPayload(BaseModel):
    dati: dict

@app.post("/api/credenziali")
def api_credenziali_nuovo(payload: CredenzialiPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO credenziali (nominativo, nome_file, link, percorso, user_id, password, file_token, scadenza, informazioni, creato_il) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (d.get("nominativo",""),d.get("nome_file",""),d.get("link",""),d.get("percorso",""),d.get("user_id",""),d.get("password",""),d.get("file_token",""),d.get("scadenza",""),d.get("informazioni",""), datetime.now().isoformat()))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.put("/api/credenziali/{id}")
def api_credenziali_modifica(id: int, payload: CredenzialiPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE credenziali SET nominativo=%s, nome_file=%s, link=%s, percorso=%s, user_id=%s, password=%s, file_token=%s, scadenza=%s, informazioni=%s WHERE id=%s", (d.get("nominativo",""),d.get("nome_file",""),d.get("link",""),d.get("percorso",""),d.get("user_id",""),d.get("password",""),d.get("file_token",""),d.get("scadenza",""),d.get("informazioni",""), id))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@app.delete("/api/credenziali/{id}")
def api_credenziali_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT file_token, percorso FROM credenziali WHERE id = %s", (id,))
            item = cur.fetchone()
            if not item: raise HTTPException(status_code=404, detail="Record non trovato")
            if item['percorso'] and item['file_token']:
                try:
                    cur.execute("SELECT user_id, password FROM credenziali WHERE id = %s", (id,))
                    creds = cur.fetchone()
                    if creds:
                        body = json.dumps({"token": item['file_token'], "user": creds['user_id'], "password": creds['password']}).encode('utf-8')
                        req = urllib.request.Request(item['percorso'], data=body, method='POST')
                        req.add_header('Content-Type', 'application/json')
                        urllib.request.urlopen(req, timeout=5)
                except Exception as e:
                    print(f"Avviso cancellazione remota: {e}")
            cur.execute("DELETE FROM credenziali WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

# === LISTA CALCOLI ===
@app.get("/api/calcoli/lista")
def api_calcoli_lista(nominativo: str = "", tipo: str = "", data_da: str = "", data_a: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """SELECT r.id, r.tipo, r.data_operazione, r.scadenza, r.orario_scadenza,
                r.importo_acconto, r.importo_saldo,
                r.num_credito_rich, r.num_credito_dato, r.num_credito_dare,
                r.val_singolo_nc_rich, r.val_nc_rich,
                r.note, n.nominativo
                FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id WHERE 1=1"""
            params = []
            if nominativo:
                query += " AND n.nominativo = %s"
                params.append(nominativo)
            if tipo:
                query += " AND r.tipo = %s"
                params.append(tipo)
            if data_da:
                query += " AND r.data_operazione >= %s"
                params.append(data_da)
            if data_a:
                query += " AND r.data_operazione <= %s"
                params.append(data_a)
            query += " ORDER BY r.data_operazione ASC"
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()

# === CALCOLI ===
@app.get("/api/calcoli/calcola")
def api_calcoli_calcola(nominativo_da: str = "", nominativo_a: str = "", reseller_da: str = "", reseller_a: str = "", procuratore_da: str = "", procuratore_a: str = "", periodo_da: str = "", periodo_a: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """SELECT r.tipo, r.importo_acconto, r.importo_saldo,
                r.num_credito_rich, r.num_credito_dato, r.num_credito_dare,
                r.val_singolo_nc_rich, r.val_nc_rich, n.nominativo
                FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id WHERE 1=1"""
            params = []
            if nominativo_da:
                query += " AND n.nominativo >= %s"; params.append(nominativo_da)
            if nominativo_a:
                query += " AND n.nominativo <= %s"; params.append(nominativo_a)
            if reseller_da:
                query += " AND n.reseller >= %s"; params.append(reseller_da)
            if reseller_a:
                query += " AND n.reseller <= %s"; params.append(reseller_a)
            if procuratore_da:
                query += " AND n.procuratore >= %s"; params.append(procuratore_da)
            if procuratore_a:
                query += " AND n.procuratore <= %s"; params.append(procuratore_a)
            if periodo_da:
                query += " AND r.data_operazione >= %s"; params.append(periodo_da)
            if periodo_a:
                query += " AND r.data_operazione <= %s"; params.append(periodo_a)
            cur.execute(query, params)
            rows = cur.fetchall()
            
            importo_nuovo = acconto_nuovo = acconto_saldo_nuovo = 0
            importo_rinnovo = acconto_rinnovo = acconto_saldo_rinnovo = 0
            importo_omaggio = acconto_omaggio = acconto_saldo_omaggio = 0
            crediti_rich = crediti_dati = crediti_dare = 0
            crediti_rich_omaggio = crediti_dati_omaggio = crediti_dare_omaggio = 0
            totale_nc = totale_nc_omaggio = 0
            
            for r in rows:
                val_acconto = float(r['importo_acconto'] or 0)
                val_saldo = float(r['importo_saldo'] or 0)
                val_tot = val_acconto + val_saldo
                rich = int(r['num_credito_rich'] or 0)
                dati = int(r['num_credito_dato'] or 0)
                dare = int(r['num_credito_dare'] or 0)
                nc = float(r['val_nc_rich'] or 0)
                
                if r['tipo'] == 'nuovo':
                    importo_nuovo += val_tot
                    acconto_nuovo += val_acconto
                    acconto_saldo_nuovo += val_saldo
                    crediti_rich += rich
                    crediti_dati += dati
                    crediti_dare += dare
                    totale_nc += nc
                elif r['tipo'] == 'omaggio':
                    importo_omaggio += val_tot
                    acconto_omaggio += val_acconto
                    acconto_saldo_omaggio += val_saldo
                    crediti_rich_omaggio += rich
                    crediti_dati_omaggio += dati
                    crediti_dare_omaggio += dare
                    totale_nc_omaggio += nc
                else:
                    importo_rinnovo += val_tot
                    acconto_rinnovo += val_acconto
                    acconto_saldo_rinnovo += val_saldo
            
            totale_acconti_nuovi = acconto_nuovo + acconto_saldo_nuovo
            totale_acconti_rinnovo = acconto_rinnovo + acconto_saldo_rinnovo
            totale_acconti_omaggio = acconto_omaggio + acconto_saldo_omaggio
            totale_generale = totale_acconti_nuovi + totale_acconti_rinnovo + totale_acconti_omaggio
            
            return {
                "importo_nuovo": importo_nuovo, "acconto_nuovo": acconto_nuovo, "acconto_saldo_nuovo": acconto_saldo_nuovo,
                "totale_acconti_nuovi": totale_acconti_nuovi,
                "importo_rinnovo": importo_rinnovo, "acconto_rinnovo": acconto_rinnovo, "acconto_saldo_rinnovo": acconto_saldo_rinnovo,
                "totale_acconti_rinnovo": totale_acconti_rinnovo,
                "importo_omaggio": importo_omaggio, "acconto_omaggio": acconto_omaggio, "acconto_saldo_omaggio": acconto_saldo_omaggio,
                "totale_acconti_omaggio": totale_acconti_omaggio,
                "crediti_rich": crediti_rich, "crediti_dati": crediti_dati, "crediti_dare": crediti_dare, "totale_nc": totale_nc,
                "crediti_rich_omaggio": crediti_rich_omaggio, "crediti_dati_omaggio": crediti_dati_omaggio, "crediti_dare_omaggio": crediti_dare_omaggio, "totale_nc_omaggio": totale_nc_omaggio,
                "totale_generale": totale_generale,
                "count_nuovi": sum(1 for r in rows if r['tipo'] == 'nuovo'),
                "count_rinnovi": sum(1 for r in rows if r['tipo'] == 'rinnovo'),
                "count_omaggi": sum(1 for r in rows if r['tipo'] == 'omaggio')
            }
    finally:
        conn.close()

@app.get("/api/calcoli")
def api_calcoli(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM calcoli ORDER BY creato_il DESC")
            return cur.fetchall()
    finally:
        conn.close()

class CalcoloPayload(BaseModel):
    dati: dict

@app.post("/api/calcoli")
def api_calcoli_salva(payload: CalcoloPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO calcoli (
                nominativo_da, nominativo_a, reseller_da, reseller_a, procuratore_da, procuratore_a, periodo_da, periodo_a,
                importo_nuovo, acconto_nuovo, acconto_saldo_nuovo, totale_acconti_nuovi, info_saldo_nuovo, info_saldo_rinnovo_nuovo,
                importo_rinnovo, acconto_rinnovo, acconto_saldo_rinnovo, totale_acconti_rinnovo, info_saldo_rinnovo,
                importo_omaggio, acconto_omaggio, acconto_saldo_omaggio, totale_acconti_omaggio,
                crediti_rich, crediti_dati, crediti_dare, totale_nc,
                crediti_rich_omaggio, crediti_dati_omaggio, crediti_dare_omaggio, totale_nc_omaggio,
                totale_generale, note, creato_il
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (d.get("nominativo_da",""), d.get("nominativo_a",""), d.get("reseller_da",""), d.get("reseller_a",""),
                 d.get("procuratore_da",""), d.get("procuratore_a",""), d.get("periodo_da",""), d.get("periodo_a",""),
                 float(d.get("importo_nuovo",0)), float(d.get("acconto_nuovo",0)), float(d.get("acconto_saldo_nuovo",0)),
                 float(d.get("totale_acconti_nuovi",0)), d.get("info_saldo_nuovo",""), d.get("info_saldo_rinnovo_nuovo",""),
                 float(d.get("importo_rinnovo",0)), float(d.get("acconto_rinnovo",0)), float(d.get("acconto_saldo_rinnovo",0)),
                 float(d.get("totale_acconti_rinnovo",0)), d.get("info_saldo_rinnovo",""),
                 float(d.get("importo_omaggio",0)), float(d.get("acconto_omaggio",0)), float(d.get("acconto_saldo_omaggio",0)),
                 float(d.get("totale_acconti_omaggio",0)),
                 int(d.get("crediti_rich",0)), int(d.get("crediti_dati",0)), int(d.get("crediti_dare",0)), float(d.get("totale_nc",0)),
                 int(d.get("crediti_rich_omaggio",0)), int(d.get("crediti_dati_omaggio",0)), int(d.get("crediti_dare_omaggio",0)), float(d.get("totale_nc_omaggio",0)),
                 float(d.get("totale_generale",0)), d.get("note",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/calcoli/{id}")
def api_calcoli_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM calcoli WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

# === LISTA CREDITI ===
@app.get("/api/lista_crediti")
def api_lista_crediti(data_da: str = "", data_a: str = "", fornitore_da: str = "", fornitore_a: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query_acq = "SELECT SUM(quantita) as tot_qta, SUM(valore) as tot_val FROM crediti WHERE 1=1"
            params_acq = []
            if data_da:
                query_acq += " AND data_acquisto >= %s"
                params_acq.append(data_da)
            if data_a:
                query_acq += " AND data_acquisto <= %s"
                params_acq.append(data_a)
            if fornitore_da:
                query_acq += " AND fornitore >= %s"
                params_acq.append(fornitore_da)
            if fornitore_a:
                query_acq += " AND fornitore <= %s"
                params_acq.append(fornitore_a)
            
            cur.execute(query_acq, params_acq)
            acquisto = cur.fetchone()
            tot_acq_qta = int(acquisto['tot_qta'] or 0)
            tot_acq_val = float(acquisto['tot_val'] or 0)
            
            query_vend = """SELECT SUM(r.num_credito_dato) as tot_qta_vend, 
                SUM(r.num_credito_dato * r.val_singolo_nc_rich) as tot_val_vend
                FROM rinnovi r WHERE r.num_credito_dato > 0"""
            params_vend = []
            if data_da:
                query_vend += " AND r.data_operazione >= %s"
                params_vend.append(data_da)
            if data_a:
                query_vend += " AND r.data_operazione <= %s"
                params_vend.append(data_a)
            
            cur.execute(query_vend, params_vend)
            vendita = cur.fetchone()
            tot_vend_qta = int(vendita['tot_qta_vend'] or 0)
            tot_vend_val = float(vendita['tot_val_vend'] or 0)
            
            saldo_qta = tot_acq_qta - tot_vend_qta
            saldo_val = tot_acq_val - tot_vend_val
            
            return {
                "tot_acq_qta": tot_acq_qta,
                "tot_acq_val": tot_acq_val,
                "tot_vend_qta": tot_vend_qta,
                "tot_vend_val": tot_vend_val,
                "saldo_qta": saldo_qta,
                "saldo_val": saldo_val
            }
    finally:
        conn.close()

# === CREDITI ===
@app.get("/api/crediti")
def api_crediti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crediti ORDER BY data_acquisto DESC")
            return cur.fetchall()
    finally:
        conn.close()

class CreditoPayload(BaseModel):
    dati: dict

@app.post("/api/crediti")
def api_crediti_salva(payload: CreditoPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO crediti (data_acquisto, fornitore, modalita_pagamento, quantita, valore, note, creato_il) 
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (d.get("data_acquisto",""), d.get("fornitore",""), d.get("modalita_pagamento",""),
                 int(d.get("quantita",0)), float(d.get("valore",0)), d.get("note",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.put("/api/crediti/{id}")
def api_crediti_modifica(id: int, payload: CreditoPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE crediti SET data_acquisto=%s, fornitore=%s, modalita_pagamento=%s, quantita=%s, valore=%s, note=%s WHERE id=%s""",
                (d.get("data_acquisto",""), d.get("fornitore",""), d.get("modalita_pagamento",""),
                 int(d.get("quantita",0)), float(d.get("valore",0)), d.get("note",""), id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@app.delete("/api/crediti/{id}")
def api_crediti_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crediti WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)