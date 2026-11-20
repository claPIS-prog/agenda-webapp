import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL, ALL_MODULES

def db_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = db_conn()
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