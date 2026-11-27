import os
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

MODALITA_PAGAMENTO_DEFAULT = [
    {"id": 1, "nome": "Contanti"},
    {"id": 2, "nome": "Bonifico Bancario"},
    {"id": 3, "nome": "Carta di Credito / Debito"},
    {"id": 4, "nome": "PayPal"},
    {"id": 5, "nome": "Ricarica / Postepay"},
    {"id": 6, "nome": "Crypto"},
    {"id": 7, "nome": "Altro"},
]

HTML_ALIASES = {
    "contabilita_dettaglio": ["contabilita_dettagli.html", "contabilita_dettaglio.html"],
    "contabilita_dettagli": ["contabilita_dettagli.html", "contabilita_dettaglio.html"],
    "tabella": ["tabelle.html", "tabella.html"],
    "tabelle": ["tabelle.html", "tabella.html"],
}


def _nome_tabella_sicuro(nome: str) -> str:
    pulito = re.sub(r"[^a-zA-Z0-9_]", "", (nome or "").strip().lower())
    if not pulito:
        raise HTTPException(status_code=400, detail="Nome tabella non valido")
    return pulito


def _trova_file_html(page_name: str):
    safe_name = os.path.basename(page_name).strip()
    if safe_name.lower().endswith(".html"):
        safe_name = safe_name[:-5]
    if not safe_name:
        return None
    nomi_candidati = HTML_ALIASES.get(safe_name, [f"{safe_name}.html"])
    for nome in nomi_candidati:
        for base_dir in ("", "static", "templates"):
            percorso = os.path.join(base_dir, nome) if base_dir else nome
            if os.path.isfile(percorso):
                return percorso
    return None


def _verifica_utente_se_disponibile(request: Request = None):
    try:
        from db import get_current_user
        if request is not None:
            get_current_user(request)
    except HTTPException:
        raise
    except Exception:
        pass


def _leggi_tabella_semplice(table_name: str, order_col: str = "id"):
    tab = _nome_tabella_sicuro(table_name)
    try:
        from db import db_conn
    except Exception:
        return []

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )
            if not tab_exists:
                return []
            try:
                cur.execute(f"SELECT * FROM {tab} ORDER BY {order_col} ASC")
            except Exception:
                conn.rollback()
                cur.execute(f"SELECT * FROM {tab}")
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]
    finally:
        conn.close()


async def _crea_voce_tabella(table_name: str, request: Request, campi_chiave: tuple[str, ...]):
    tab = _nome_tabella_sicuro(table_name)
    _verifica_utente_se_disponibile(request)
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")

    data = payload or {}
    valore = ""
    for chiave in campi_chiave:
        if data.get(chiave) is not None and str(data.get(chiave)).strip():
            valore = str(data.get(chiave)).strip()
            break
    if not valore:
        for v in data.values():
            if v is not None and str(v).strip():
                valore = str(v).strip()
                break
    if not valore:
        raise HTTPException(status_code=400, detail="Valore obbligatorio")

    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )
            if not tab_exists:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {tab} (
                        id SERIAL PRIMARY KEY,
                        nome TEXT NOT NULL
                    )
                    """
                )
            cur.execute(
                f"INSERT INTO {tab} (nome) VALUES (%s) RETURNING id, nome",
                (valore,),
            )
            row = cur.fetchone()
        conn.commit()
        if isinstance(row, dict):
            return {"ok": True, **row}
        return {"ok": True, "id": row[0] if row else None, "nome": valore}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio in {tab}: {e}")
    finally:
        conn.close()


def _elimina_voce_tabella(table_name: str, item_id: int, request: Request):
    tab = _nome_tabella_sicuro(table_name)
    _verifica_utente_se_disponibile(request)
    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )
            if tab_exists:
                cur.execute(f"DELETE FROM {tab} WHERE id = %s", (int(item_id),))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore eliminazione da {tab}: {e}")
    finally:
        conn.close()


def _leggi_calcoli_fallback(
    nominativo: str = "",
    nominativo_da: str = "",
    nominativo_a: str = "",
    tipo: str = "",
    data_da: str = "",
    data_a: str = "",
    request: Request = None,
):
    try:
        from db import db_conn
        _verifica_utente_se_disponibile(request)
    except HTTPException:
        raise
    except Exception:
        return {"righe": [], "items": [], "totale": 0, "count": 0, "nuovi": 0, "rinnovi": 0, "omaggi": 0}

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.calcoli') AS tab")
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )
            if not tab_exists:
                return {"righe": [], "items": [], "totale": 0, "count": 0, "nuovi": 0, "rinnovi": 0, "omaggi": 0}

            query = "SELECT * FROM calcoli WHERE 1=1"
            params = []
            if nominativo:
                query += " AND LOWER(COALESCE(nominativo::text, '')) = LOWER(%s)"
                params.append(nominativo.strip())
            if data_da:
                query += " AND COALESCE(data::text, '') >= %s"
                params.append(data_da.strip())
            if data_a:
                query += " AND COALESCE(data::text, '') <= %s"
                params.append(data_a.strip())
            if nominativo_da:
                query += " AND COALESCE(nominativo::text, '') >= %s"
                params.append(nominativo_da.strip())
            if nominativo_a:
                query += " AND COALESCE(nominativo::text, '') <= %s"
                params.append(nominativo_a.strip())
            if tipo:
                query += " AND (LOWER(COALESCE(tipo::text, '')) = LOWER(%s) OR LOWER(COALESCE(categoria::text, '')) LIKE LOWER(%s))"
                params.append(tipo.strip())
                params.append(f"%{tipo.strip()}%")
            query += " ORDER BY id DESC"

            cur.execute(query, params)
            rows = cur.fetchall() or []
            righe = [dict(r) for r in rows]
            totale = len(righe)
            return {
                "righe": righe,
                "items": righe,
                "totale": totale,
                "count": totale,
                "nuovi": totale,
                "rinnovi": 0,
                "omaggi": 0,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura calcoli: {e}")
    finally:
        conn.close()


def _assicura_colonne_rinnovi(cur, tab_name: str = "calcoli"):
    tab = _nome_tabella_sicuro(tab_name)
    colonne_extra = [
        ("numeraz_trans_crediti", "TEXT"),
        ("credito_richiesto", "NUMERIC DEFAULT 0"),
        ("credito_dato", "NUMERIC DEFAULT 0"),
        ("credito_resta", "NUMERIC DEFAULT 0"),
        ("importo_acconto", "NUMERIC DEFAULT 0"),
        ("importo_resta", "NUMERIC DEFAULT 0"),
    ]
    for col, col_type in colonne_extra:
        try:
            cur.execute(f"ALTER TABLE {tab} ADD COLUMN IF NOT EXISTS {col} {col_type}")
        except Exception:
            pass


_router_calcoli_caricato = False
try:
    from routers.calcoli import router as calcoli_router
    app.include_router(calcoli_router)
    _router_calcoli_caricato = True
except Exception as e:
    print(f"Avviso import routers.calcoli: {e}")

if not _router_calcoli_caricato:
    @app.get("/api/calcoli")
    @app.get("/api/lista_calcoli")
    def api_calcoli_diretto(
        nominativo: str = "",
        nominativo_da: str = "",
        nominativo_a: str = "",
        tipo: str = "",
        data_da: str = "",
        data_a: str = "",
        request: Request = None,
    ):
        return _leggi_calcoli_fallback(
            nominativo, nominativo_da, nominativo_a, tipo, data_da, data_a, request
        )

    @app.get("/api/calcoli/lista")
    def api_calcoli_lista_diretto(
        nominativo: str = "",
        nominativo_da: str = "",
        nominativo_a: str = "",
        tipo: str = "",
        data_da: str = "",
        data_a: str = "",
        request: Request = None,
    ):
        dati = _leggi_calcoli_fallback(
            nominativo, nominativo_da, nominativo_a, tipo, data_da, data_a, request
        )
        return dati.get("righe", [])

_router_crediti_caricato = False
try:
    from routers.crediti import router as crediti_router
    app.include_router(crediti_router)
    _router_crediti_caricato = True
except Exception as e:
    print(f"Avviso import routers.crediti: {e}")


@app.get("/")
@app.head("/")
def root():
    percorso = _trova_file_html("index")
    if percorso:
        return FileResponse(percorso)
    return {"ok": True, "service": "AgendaGest WebApp"}


@app.get("/health")
@app.head("/health")
def health():
    return {"ok": True}


@app.get("/api/rinnovi")
@app.get("/api/rinnovo")
def api_rinnovi_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    dati = _leggi_calcoli_fallback(tipo="Rinnovo", request=request)
    righe = dati.get("righe", [])
    if righe:
        return righe
    for tab in ("rinnovi", "rinnovo"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/rinnovi")
@app.post("/api/rinnovo")
async def api_rinnovi_crea(request: Request):
    _verifica_utente_se_disponibile(request)
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")

    data = payload or {}
    nominativo = str(data.get("nominativo") or data.get("nome") or "").strip()
    if not nominativo:
        raise HTTPException(status_code=400, detail="Nominativo obbligatorio")

    def _num(chiavi, default=0.0):
        for k in chiavi:
            if k in data and data.get(k) not in (None, ""):
                try:
                    return float(str(data.get(k)).replace(",", "."))
                except Exception:
                    pass
        return float(default)

    data_op = str(data.get("data") or "").strip()
    scadenza = str(data.get("scadenza") or "").strip()
    numeraz_trans_crediti = str(
        data.get("NumerazTransCrediti")
        or data.get("numeraz_trans_crediti")
        or data.get("numeraztranscrediti")
        or ""
    ).strip()
    credito_richiesto = _num(["CreditoRichiesto", "credito_richiesto", "creditorichiesto"], 0.0)
    credito_dato = _num(["CreditoDato", "credito_dato", "creditodato"], 0.0)
    credito_resta = _num(["CreditoResta", "credito_resta", "creditoresta"], credito_richiesto - credito_dato)
    importo = _num(["importo", "Importo"], 0.0)
    importo_acconto = _num(["ImportoAcconto", "importo_acconto", "importoacconto"], 0.0)
    importo_resta = _num(["ImportoResta", "importo_resta", "importoresta"], importo - importo_acconto)
    metodo = str(data.get("metodo_pagamento") or "").strip()
    note = str(data.get("note") or "").strip()

    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.calcoli') AS tab")
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )
            if not tab_exists:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS calcoli (
                        id SERIAL PRIMARY KEY,
                        nominativo TEXT NOT NULL,
                        tipo TEXT,
                        categoria TEXT,
                        data TEXT,
                        scadenza TEXT,
                        numeraz_trans_crediti TEXT,
                        credito_richiesto NUMERIC DEFAULT 0,
                        credito_dato NUMERIC DEFAULT 0,
                        credito_resta NUMERIC DEFAULT 0,
                        importo NUMERIC DEFAULT 0,
                        importo_acconto NUMERIC DEFAULT 0,
                        importo_resta NUMERIC DEFAULT 0,
                        metodo_pagamento TEXT,
                        note TEXT
                    )
                    """
                )
            else:
                _assicura_colonne_rinnovi(cur, "calcoli")

            try:
                cur.execute(
                    """
                    INSERT INTO calcoli (
                        nominativo, tipo, categoria, data, scadenza,
                        numeraz_trans_crediti, credito_richiesto, credito_dato, credito_resta,
                        importo, importo_acconto, importo_resta, metodo_pagamento, note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, nominativo, tipo, categoria, data, scadenza,
                              numeraz_trans_crediti, credito_richiesto, credito_dato, credito_resta,
                              importo, importo_acconto, importo_resta, metodo_pagamento, note
                    """,
                    (
                        nominativo,
                        "Rinnovo",
                        "Rinnovo",
                        data_op,
                        scadenza,
                        numeraz_trans_crediti,
                        credito_richiesto,
                        credito_dato,
                        credito_resta,
                        importo,
                        importo_acconto,
                        importo_resta,
                        metodo,
                        note,
                    ),
                )
            except Exception:
                conn.rollback()
                cur.execute(
                    """
                    INSERT INTO calcoli (nominativo, tipo, categoria, data, scadenza, importo, metodo_pagamento, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, nominativo, tipo, categoria, data, scadenza, importo, metodo_pagamento, note
                    """,
                    (nominativo, "Rinnovo", "Rinnovo", data_op, scadenza, importo, metodo, note),
                )
            row = cur.fetchone()
        conn.commit()
        if isinstance(row, dict):
            return {
                "ok": True,
                "NumerazTransCrediti": numeraz_trans_crediti,
                "CreditoRichiesto": credito_richiesto,
                "CreditoDato": credito_dato,
                "CreditoResta": credito_resta,
                "ImportoAcconto": importo_acconto,
                "ImportoResta": importo_resta,
                **row,
            }
        return {
            "ok": True,
            "nominativo": nominativo,
            "tipo": "Rinnovo",
            "NumerazTransCrediti": numeraz_trans_crediti,
            "CreditoRichiesto": credito_richiesto,
            "CreditoDato": credito_dato,
            "CreditoResta": credito_resta,
            "ImportoAcconto": importo_acconto,
            "ImportoResta": importo_resta,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio rinnovo: {e}")
    finally:
        conn.close()


@app.get("/api/nominativi")
def api_nominativi(request: Request = None):
    try:
        from db import db_conn
        _verifica_utente_se_disponibile(request)
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.nominativi') AS tab")
                tab_row = cur.fetchone()
                tab_exists = bool(
                    tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
                )
                if tab_exists:
                    cur.execute("SELECT * FROM nominativi ORDER BY id DESC")
                    rows = cur.fetchall() or []
                    return [dict(r) for r in rows]
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception:
        pass
    return []


@app.post("/api/nominativi")
async def api_nominativi_crea(request: Request):
    _verifica_utente_se_disponibile(request)
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")

    data = payload or {}
    nominativo = str(data.get("nominativo") or data.get("nome") or "").strip()
    if not nominativo:
        raise HTTPException(status_code=400, detail="Nominativo obbligatorio")

    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.nominativi') AS tab")
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )
            if not tab_exists:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nominativi (
                        id SERIAL PRIMARY KEY,
                        nominativo TEXT NOT NULL,
                        telefono TEXT,
                        email TEXT,
                        data TEXT,
                        stato TEXT,
                        note TEXT
                    )
                    """
                )

            telefono = str(data.get("telefono") or "").strip()
            email = str(data.get("email") or "").strip()
            data_op = str(data.get("data") or "").strip()
            stato = str(data.get("stato") or "").strip()
            note = str(data.get("note") or "").strip()

            try:
                cur.execute(
                    """
                    INSERT INTO nominativi (nominativo, telefono, email, data, stato, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, nominativo, telefono, email, data, stato, note
                    """,
                    (nominativo, telefono, email, data_op, stato, note),
                )
            except Exception:
                conn.rollback()
                cur.execute(
                    "INSERT INTO nominativi (nominativo) VALUES (%s) RETURNING id, nominativo",
                    (nominativo,),
                )
            row = cur.fetchone()
        conn.commit()
        if isinstance(row, dict):
            return {"ok": True, **row}
        return {"ok": True, "nominativo": nominativo}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio nominativo: {e}")
    finally:
        conn.close()


@app.get("/api/crediti")
@app.get("/api/crediti/lista")
def api_crediti_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("crediti", "transazioni_crediti", "movimenti_crediti"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/crediti")
async def api_crediti_crea(request: Request):
    return await _crea_voce_tabella(
        "crediti",
        request,
        ("NumerazTransCrediti", "numeraz_trans_crediti", "codice", "nome", "nominativo"),
    )


@app.get("/api/metodi_pagamento")
def api_metodi_pagamento(request: Request = None):
    try:
        _verifica_utente_se_disponibile(request)
        rows = _leggi_tabella_semplice("metodi_pagamento", "id")
        if rows:
            return rows
    except HTTPException:
        raise
    except Exception:
        pass
    return MODALITA_PAGAMENTO_DEFAULT


@app.get("/api/reseller")
@app.get("/api/resellers")
def api_reseller_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("reseller", "resellers"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/reseller")
@app.post("/api/resellers")
async def api_reseller_crea(request: Request):
    return await _crea_voce_tabella("reseller", request, ("nome", "reseller", "valore", "descrizione"))


@app.delete("/api/reseller/{item_id}")
@app.delete("/api/resellers/{item_id}")
def api_reseller_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("reseller", item_id, request)


@app.get("/api/procuratori")
@app.get("/api/procuratore")
def api_procuratori_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("procuratori", "procuratore"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/procuratori")
@app.post("/api/procuratore")
async def api_procuratori_crea(request: Request):
    return await _crea_voce_tabella("procuratori", request, ("nome", "procuratore", "valore", "descrizione"))


@app.delete("/api/procuratori/{item_id}")
@app.delete("/api/procuratore/{item_id}")
def api_procuratori_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("procuratori", item_id, request)


@app.get("/api/operatori")
@app.get("/api/operatore")
@app.get("/api/operatori_it")
@app.get("/api/operatore_it")
def api_operatori_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("operatori_it", "operatori", "operatore_it", "operatore"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/operatori")
@app.post("/api/operatore")
@app.post("/api/operatori_it")
@app.post("/api/operatore_it")
async def api_operatori_crea(request: Request):
    return await _crea_voce_tabella("operatori_it", request, ("nome", "operatore", "operatori_it", "valore", "descrizione"))


@app.delete("/api/operatori/{item_id}")
@app.delete("/api/operatore/{item_id}")
@app.delete("/api/operatori_it/{item_id}")
@app.delete("/api/operatore_it/{item_id}")
def api_operatori_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("operatori_it", item_id, request)


@app.get("/api/server")
@app.get("/api/servers")
def api_server_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("server", "servers"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/server")
@app.post("/api/servers")
async def api_server_crea(request: Request):
    return await _crea_voce_tabella("server", request, ("nome", "server", "valore", "descrizione"))


@app.delete("/api/server/{item_id}")
@app.delete("/api/servers/{item_id}")
def api_server_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("server", item_id, request)


@app.get("/api/sistemi_operativi")
@app.get("/api/sistema_operativo")
@app.get("/api/so")
def api_sistemi_operativi_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("sistemi_operativi", "sistema_operativo", "so"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/sistemi_operativi")
@app.post("/api/sistema_operativo")
@app.post("/api/so")
async def api_sistemi_operativi_crea(request: Request):
    return await _crea_voce_tabella("sistemi_operativi", request, ("nome", "sistema_operativo", "so", "valore", "descrizione"))


@app.delete("/api/sistemi_operativi/{item_id}")
@app.delete("/api/sistema_operativo/{item_id}")
@app.delete("/api/so/{item_id}")
def api_sistemi_operativi_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("sistemi_operativi", item_id, request)


@app.get("/api/buffett")
@app.get("/api/buffet")
def api_buffett_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("buffett", "buffet"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/buffett")
@app.post("/api/buffet")
async def api_buffett_crea(request: Request):
    return await _crea_voce_tabella("buffett", request, ("nome", "buffett", "buffet", "valore", "descrizione"))


@app.delete("/api/buffett/{item_id}")
@app.delete("/api/buffet/{item_id}")
def api_buffett_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("buffett", item_id, request)


@app.get("/api/dispositivi")
@app.get("/api/dispositivo")
def api_dispositivi_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("dispositivi", "dispositivo"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/dispositivi")
@app.post("/api/dispositivo")
async def api_dispositivi_crea(request: Request):
    return await _crea_voce_tabella("dispositivi", request, ("nome", "dispositivo", "valore", "descrizione"))


@app.delete("/api/dispositivi/{item_id}")
@app.delete("/api/dispositivo/{item_id}")
def api_dispositivi_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("dispositivi", item_id, request)


@app.get("/api/permessi")
@app.get("/api/permesso")
def api_permessi_lista(request: Request = None):
    _verifica_utente_se_disponibile(request)
    for tab in ("permessi", "permesso"):
        rows = _leggi_tabella_semplice(tab, "id")
        if rows:
            return rows
    return []


@app.post("/api/permessi")
@app.post("/api/permesso")
async def api_permessi_crea(request: Request):
    return await _crea_voce_tabella("permessi", request, ("nome", "permesso", "valore", "descrizione"))


@app.delete("/api/permessi/{item_id}")
@app.delete("/api/permesso/{item_id}")
def api_permessi_elimina(item_id: int, request: Request):
    return _elimina_voce_tabella("permessi", item_id, request)


@app.get("/api/tabelle/{table_name}")
@app.get("/api/{table_name}")
def api_tabella_generica_lista(table_name: str, request: Request = None):
    _verifica_utente_se_disponibile(request)
    return _leggi_tabella_semplice(table_name, "id")


@app.post("/api/tabelle/{table_name}")
@app.post("/api/{table_name}")
async def api_tabella_generica_crea(table_name: str, request: Request):
    return await _crea_voce_tabella(table_name, request, ("nome", "valore", "descrizione"))


@app.delete("/api/tabelle/{table_name}/{item_id}")
@app.delete("/api/{table_name}/{item_id}")
def api_tabella_generica_elimina(table_name: str, item_id: int, request: Request):
    return _elimina_voce_tabella(table_name, item_id, request)


@app.get("/{page_name}.html")
def serve_any_html(page_name: str):
    percorso = _trova_file_html(page_name)
    if percorso:
        return FileResponse(percorso)
    raise HTTPException(status_code=404, detail=f"{page_name}.html non trovato")


@app.get("/{page_name}")
def serve_page_without_ext(page_name: str):
    if page_name.startswith("api/") or page_name in ("health", "docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=404, detail="Not Found")
    percorso = _trova_file_html(page_name)
    if percorso:
        return FileResponse(percorso)
    raise HTTPException(status_code=404, detail=f"{page_name} non trovato")


if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")