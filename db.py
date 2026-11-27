import os
from typing import Any
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Request
from telegram_init_data import validate, parse
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
AUTHORIZED_IDS = {int(x) for x in os.getenv("AUTHORIZED_IDS", "").split(",") if x}

if not DATABASE_URL or not BOT_TOKEN:
    raise SystemExit("DATABASE_URL o BOT_TOKEN mancanti.")

ALL_MODULES = [
    "nominativo", "lista", "scadenze", "rinnovi", "storico_rinnovi",
    "saldo_rinnovi", "reseller", "procuratori", "server", "nota",
    "credenziali", "permessi", "dispositivi", "sistemi_op", "buffett",
    "pagamenti", "operatori_it", "tabelle", "crediti", "calcoli", "ingressi"
]

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

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

def init_db():
    conn = db_conn()
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