import os
import json
import urllib.request
from datetime import datetime, timedelta
from typing import Any
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
    "pagamenti", "operatori_it", "tabelle", "crediti", "calcoli", "ingressi"
]

def get_current_user(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data") if request else None
    if not init_data and request:
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
            cur.execute("CREATE TABLE IF NOT EXISTS autorizzati (id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL, password TEXT NOT NULL, nome TEXT, note TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS dispositivi (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS sistemi_operativi (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS buffett (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS metodi_pagamento (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS operatori_it (id SERIAL PRIMARY KEY, nome TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS saldo_rinnovi (id SERIAL PRIMARY KEY, rinnovo_id INTEGER REFERENCES rinnovi(id), num_credito_saldo INTEGER DEFAULT 0, data_credito_rinnovo_saldo TEXT, val_nc_dato REAL DEFAULT 0, val_nc_saldo REAL DEFAULT 0, informazioni_note TEXT, creato_il TEXT)")
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
            cur.execute("""CREATE TABLE IF NOT EXISTS ingressi (
                id SERIAL PRIMARY KEY,
                nominativo TEXT NOT NULL,
                data_ingresso TEXT NOT NULL,
                ora_entrata TEXT DEFAULT '',
                data_uscita TEXT NOT NULL,
                ora_uscita TEXT DEFAULT '',
                tempo INTEGER DEFAULT 0,
                form_visualizzato TEXT DEFAULT '',
                posizione TEXT DEFAULT '',
                note TEXT DEFAULT '',
                creato_il TEXT
            )""")
            for col, typ in [("operatore_it","TEXT"),("server","TEXT"),("reseller","TEXT"),("user_id","TEXT"),("password","TEXT"),("cellulare","TEXT"),("procuratore","TEXT"),("apk_utilizzata","TEXT"),("quale_vpn","TEXT"),("citta","TEXT"),("data_iscrizione","TEXT"),("data_fine","TEXT"),("informazioni","TEXT"),("tipo_linea","TEXT")]:
                cur.execute(f"ALTER TABLE nominativi ADD COLUMN IF NOT EXISTS {col} {typ}")
            cur.execute("ALTER TABLE autorizzati ADD COLUMN IF NOT EXISTS note TEXT")
            cur.execute("ALTER TABLE saldo_rinnovi ALTER COLUMN rinnovo_id DROP NOT NULL")
            cur.execute("ALTER TABLE ingressi ADD COLUMN IF NOT EXISTS ora_entrata TEXT DEFAULT ''")
            cur.execute("ALTER TABLE ingressi ADD COLUMN IF NOT EXISTS ora_uscita TEXT DEFAULT ''")
            cur.execute("SELECT id FROM autorizzati")
            for u in cur.fetchall():
                for mod in ALL_MODULES:
                    cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, TRUE) ON CONFLICT (user_id, modulo) DO NOTHING", (u["id"], mod))
            for tbl in [
                "nominativi", "rinnovi", "servers", "resellers", "procuratori",
                "autorizzati", "dispositivi", "sistemi_operativi", "buffett",
                "metodi_pagamento", "operatori_it", "saldo_rinnovi", "note",
                "credenziali", "permessi", "calcoli", "crediti", "ingressi"
            ]:
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE((SELECT MAX(id) FROM {tbl}), 1), true)"
                )
            conn.commit()
    finally:
        conn.close()

init_db()

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def estrai_dati(body: Any) -> dict:
    if isinstance(body, dict):
        if isinstance(body.get("dati"), dict):
            merged = dict(body["dati"])
            for k, v in body.items():
                if k != "dati" and k not in merged:
                    merged[k] = v
            return merged
        return body
    return {}

def _parse_data_ora_it(val_data: str, val_ora: str = "") -> datetime | None:
    if not val_data:
        return None
    s_data = str(val_data).strip()
    s_ora = str(val_ora or "").strip()
    combinato = f"{s_data} {s_ora}".strip() if s_ora else s_data
    for fmt in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(combinato, fmt)
        except Exception:
            pass
    return None

def _format_data_it(dt: datetime | None, fallback: str = "") -> str:
    if dt is not None:
        return dt.strftime("%d/%m/%Y")
    return str(fallback or "").strip()

def _format_ora_it(dt: datetime | None, fallback: str = "") -> str:
    s_fb = str(fallback or "").strip()
    if s_fb:
        return s_fb[:5]
    if dt is not None:
        return dt.strftime("%H:%M")
    return ""

def _calcola_tempo_minuti(dt_in: datetime | None, dt_out: datetime | None, fornito: Any = None) -> int:
    if dt_in is not None and dt_out is not None:
        diff_min = int(round((dt_out - dt_in).total_seconds() / 60.0))
        return max(0, diff_min)
    if fornito not in (None, ""):
        try:
            return max(0, int(round(float(fornito))))
        except Exception:
            pass
    return 0

# === PERMESSI / AMICI ===
@app.get("/api/amici")
def api_amici(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.telegram_id, a.password,
                       COALESCE(a.nome, n.nominativo) AS nome,
                       COALESCE(a.nome, n.nominativo) AS nominativo,
                       COALESCE(a.note, '') AS note
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
                       COALESCE(a.nome, n.nominativo, 'Utente #' || a.id::text) AS nominativo,
                       COALESCE(a.note, '') AS note
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
                    "note": u.get("note", ""),
                    "permessi": mappa,
                    "moduli_lista": attivi,
                    "moduli_attivi": len(attivi),
                    "totale_moduli_attivi": len(attivi)
                })
            return risultato
    finally:
        conn.close()

class AmicoPayload(BaseModel):
    id: int | None = None
    telegram_id: int | None = None
    password: str = ""
    nome: str = ""
    note: str = ""

@app.post("/api/salva_amico")
def api_salva_amico(payload: AmicoPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            target_id = payload.id if payload.id is not None else payload.telegram_id
            if target_id is None:
                raise HTTPException(status_code=400, detail="ID utente mancante")

            tg_id = payload.telegram_id if payload.telegram_id is not None else target_id
            cur.execute("SELECT id, note FROM autorizzati WHERE id = %s OR telegram_id = %s", (target_id, tg_id))
            exists = cur.fetchone()

            if exists:
                record_id = exists["id"]
                cur.execute("""
                    UPDATE autorizzati SET
                        telegram_id = %s,
                        password = %s,
                        nome = COALESCE(NULLIF(%s, ''), nome),
                        note = %s
                    WHERE id = %s
                """, (tg_id, payload.password, payload.nome, payload.note, record_id))
            else:
                cur.execute("""
                    INSERT INTO autorizzati (id, telegram_id, password, nome, note)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (target_id, tg_id, payload.password, payload.nome, payload.note))
                record_id = cur.fetchone()["id"]

                for mod in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo)
                        VALUES (%s, %s, FALSE)
                        ON CONFLICT (user_id, modulo) DO NOTHING
                    """, (record_id, mod))

            conn.commit()
            return {"ok": True, "id": record_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO autorizzati (telegram_id, password, nome, note) VALUES (%s, %s, %s, %s) ON CONFLICT (telegram_id) DO UPDATE SET password = excluded.password, nome = excluded.nome, note = excluded.note RETURNING id", (payload.telegram_id, payload.password, payload.nome, payload.note))
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
            return {"permessi": perms}
    finally:
        conn.close()

@app.delete("/api/permessi/{user_id}")
def api_delete_permessi(user_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE permessi SET attivo = FALSE WHERE user_id = %s", (user_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

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

@app.post("/api/azione")
async def api_azione(request: Request):
    get_current_user(request)
    raw_body = await request.json()
    dati = estrai_dati(raw_body)
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
                     float(dati.get("prezzo",0) or 0), dati.get("cadenza",""), dati.get("tipo_linea",""), 
                     dati.get("server",""), dati.get("reseller",""),
                     dati.get("dispositivo",""), dati.get("sistema_operativo",""),
                     dati.get("buffett",""), dati.get("metodo_pagamento",""), dati.get("operatore_it",""),
                     dati.get("cellulare",""), dati.get("procuratore",""),
                     dati.get("apk_utilizzata",""), int(dati.get("uso_vpn",0) or 0),
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
                     float(dati.get("prezzo",0) or 0), dati.get("cadenza"), dati.get("tipo_linea"), 
                     dati.get("server"), dati.get("reseller"),
                     dati.get("dispositivo"), dati.get("sistema_operativo"),
                     dati.get("buffett"), dati.get("metodo_pagamento"), dati.get("operatore_it"),
                     dati.get("cellulare"), dati.get("procuratore"),
                     dati.get("apk_utilizzata"), int(dati.get("uso_vpn",0) or 0),
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

def _leggi_elenco_rinnovi(q: str = ""):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT r.id, r.nominativo_id, r.tipo, r.data_operazione, r.mesi, r.scadenza,
                       r.orario_scadenza, r.importo_acconto, r.importo_saldo, r.data_acconto,
                       r.data_saldo, r.note, r.creato_il, r.num_credito_rich, r.num_credito_dato,
                       r.num_credito_dare, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato,
                       r.val_singolo_nc_rich, r.val_nc_rich, n.nominativo
                FROM rinnovi r
                JOIN nominativi n ON n.id = r.nominativo_id
                WHERE 1=1
            """
            params = []
            if q and q.strip():
                query += " AND LOWER(n.nominativo) LIKE %s"
                params.append(f"%{q.strip().lower()}%")
            query += " ORDER BY COALESCE(r.creato_il, '') DESC, r.id DESC"
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/api/elenco_rinnovi")
def api_elenco_rinnovi(q: str = "", request: Request = None):
    get_current_user(request)
    return _leggi_elenco_rinnovi(q)

@app.get("/api/lista_rinnovi")
def api_lista_rinnovi(q: str = "", request: Request = None):
    get_current_user(request)
    return _leggi_elenco_rinnovi(q)

@app.post("/api/rinnovo")
async def api_rinnovo(request: Request):
    get_current_user(request)
    dati = estrai_dati(await request.json())
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            num_rich = int(dati.get("num_credito_rich", 0) or 0)
            num_dato = int(dati.get("num_credito_dato", 0) or 0)
            val_singolo = float(dati.get("val_singolo_nc_rich", 0) or 0)
            cur.execute("INSERT INTO rinnovi (nominativo_id, tipo, data_operazione, mesi, scadenza, orario_scadenza, importo_acconto, importo_saldo, data_acconto, data_saldo, note, creato_il, num_credito_rich, num_credito_dato, num_credito_dare, data_credito_rinnovo_rich, data_credito_rinnovo_dato, val_singolo_nc_rich, val_nc_rich) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (int(dati.get("nominativo_id")), dati.get("tipo","rinnovo"), dati.get("data_operazione"), num_rich, dati.get("scadenza"), dati.get("orario_scadenza",""), float(dati.get("importo_acconto",0) or 0), float(dati.get("importo_saldo",0) or 0), datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_acconto",0) or 0)>0 else "", datetime.now().strftime("%d/%m/%Y") if float(dati.get("importo_saldo",0) or 0)>0 else "", dati.get("note",""), datetime.now().isoformat(), num_rich, num_dato, num_rich - num_dato, dati.get("data_credito_rinnovo_rich",""), dati.get("data_credito_rinnovo_dato",""), val_singolo, num_rich * val_singolo))
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
def _elenco_saldo_rinnovi():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, s.rinnovo_id, s.num_credito_saldo, s.data_credito_rinnovo_saldo,
                       s.val_nc_dato, s.val_nc_saldo, s.informazioni_note, s.creato_il,
                       r.num_credito_rich, r.num_credito_dato, r.data_credito_rinnovo_rich,
                       r.data_credito_rinnovo_dato, r.val_nc_rich, r.val_singolo_nc_rich,
                       COALESCE(n.nominativo, 'Stock / Crediti') AS nominativo
                FROM saldo_rinnovi s
                LEFT JOIN rinnovi r ON r.id = s.rinnovo_id
                LEFT JOIN nominativi n ON n.id = r.nominativo_id
                ORDER BY COALESCE(s.creato_il, '') DESC, s.id DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

async def _salva_saldo_rinnovo_da_request(request: Request):
    dati: dict = {}
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
            dati = estrai_dati(body)
        except Exception:
            dati = {}
    for k, v in request.query_params.items():
        if k not in dati:
            dati[k] = v

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            rinnovo_raw = dati.get("rinnovo_id")
            rinnovo_id = int(rinnovo_raw) if rinnovo_raw not in (None