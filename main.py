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
                cur.execute(f"SELECT * FROM {tab} ORDER BY {order_col} DESC")
            except Exception:
                conn.rollback()
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


def _aggiorna_record_dinamico(item_id: int, data: dict, request: Request = None):
    _verifica_utente_se_disponibile(request)
    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            for tab in ("nominativi", "contatti", "clienti", "anagrafica", "scadenze", "calcoli"):
                cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
                tab_row = cur.fetchone()
                tab_exists = bool(
                    tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
                )
                if not tab_exists:
                    continue

                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (tab,),
                )
                cols_rows = cur.fetchall() or []
                colonne_tabella = {
                    (r["column_name"] if isinstance(r, dict) else r[0]) for r in cols_rows
                }

                aggiornabili = []
                valori = []
                for k, v in (data or {}).items():
                    col_pulita = re.sub(r"[^a-zA-Z0-9_]", "", str(k))
                    if col_pulita and col_pulita != "id" and col_pulita in colonne_tabella:
                        aggiornabili.append(f"{col_pulita} = %s")
                        valori.append(v)

                if not aggiornabili:
                    continue

                cur.execute(f"SELECT id FROM {tab} WHERE id = %s", (int(item_id),))
                esiste = cur.fetchone()
                if not esiste:
                    continue

                valori.append(int(item_id))
                sql = f"UPDATE {tab} SET {', '.join(aggiornabili)} WHERE id = %s RETURNING *"
                cur.execute(sql, valori)
                row = cur.fetchone()
                conn.commit()
                if isinstance(row, dict):
                    return {"ok": True, "tabella": tab, **row}
                return {"ok": True, "tabella": tab, "id": item_id}
        return {"ok": True, "id": item_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore aggiornamento record: {e}")
    finally:
        conn.close()


def _elimina_record_nominativo(item_id: int, request: Request = None):
    _verifica_utente_se_disponibile(request)
    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            for tab in ("nominativi", "contatti", "clienti", "anagrafica", "scadenze"):
                cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
                tab_row = cur.fetchone()
                tab_exists = bool(
                    tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
                )
                if not tab_exists:
                    continue
                cur.execute(f"DELETE FROM {tab} WHERE id = %s RETURNING id", (int(item_id),))
                deleted = cur.fetchone()
                if deleted:
                    conn.commit()
                    return {"ok": True, "tabella": tab, "id": item_id}
        conn.commit()
        return {"ok": True, "id": item_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore eliminazione record: {e}")
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

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'calcoli'
                """
            )
            cols_rows = cur.fetchall() or []
            colonne = {
                (r["column_name"] if isinstance(r, dict) else r[0]) for r in cols_rows
            }
            col_nom = next((c for c in ("nominativo", "nome", "cliente") if c in colonne), None)
            col_data = next((c for c in ("data", "data_operazione", "data_op") if c in colonne), None)
            col_tipo = next((c for c in ("tipo", "categoria") if c in colonne), None)

            query = "SELECT * FROM calcoli WHERE 1=1"
            params = []
            if nominativo and col_nom:
                query += f" AND LOWER(COALESCE({col_nom}::text, '')) = LOWER(%s)"
                params.append(nominativo.strip())
            if data_da and col_data:
                query += f" AND COALESCE({col_data}::text, '') >= %s"
                params.append(data_da.strip())
            if data_a and col_data:
                query += f" AND COALESCE({col_data}::text, '') <= %s"
                params.append(data_a.strip())
            if nominativo_da and col_nom:
                query += f" AND COALESCE({col_nom}::text, '') >= %s"
                params.append(nominativo_da.strip())
            if nominativo_a and col_nom:
                query += f" AND COALESCE({col_nom}::text, '') <= %s"
                params.append(nominativo_a.strip())
            if tipo and col_tipo:
                query += f" AND LOWER(COALESCE({col_tipo}::text, '')) LIKE LOWER(%s)"
                params.append(f"%{tipo.strip()}%")
            if "id" in colonne:
                query += " ORDER BY id DESC"

            cur.execute(query, params)
            rows = cur.fetchall() or []
            righe = []
            for r in rows:
                d = dict(r)
                if "nominativo" not in d and col_nom and d.get(col_nom) is not None:
                    d["nominativo"] = d[col_nom]
                righe.append(d)

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


def _leggi_scadenze_aggregate(request: Request = None):
    _verifica_utente_se_disponibile(request)
    rows_tab = _leggi_tabella_semplice("scadenze", "id")
    if rows_tab:
        return rows_tab

    risultati = []
    for tab in ("nominativi", "contatti", "clienti", "anagrafica", "calcoli"):
        rows = _leggi_tabella_semplice(tab, "id")
        for r in rows:
            scad = r.get("data_fine") or r.get("scadenza") or r.get("data_scadenza") or ""
            if str(scad).strip():
                copia = dict(r)
                if not copia.get("nominativo"):
                    copia["nominativo"] = copia.get("nome") or copia.get("cliente") or ""
                if not copia.get("scadenza"):
                    copia["scadenza"] = str(scad).strip()
                if not copia.get("data_fine"):
                    copia["data_fine"] = str(scad).strip()
                risultati.append(copia)
        if risultati:
            return risultati
    return []


def _assicura_colonne_rinnovi(cur, tab_name: str = "calcoli"):
    tab = _nome_tabella_sicuro(tab_name)
    colonne_extra = [
        ("nominativo", "TEXT"),
        ("tipo", "TEXT"),
        ("categoria", "TEXT"),
        ("data", "TEXT"),
        ("scadenza", "TEXT"),
        ("numeraz_trans_crediti", "TEXT"),
        ("credito_richiesto", "NUMERIC DEFAULT 0"),
        ("credito_dato", "NUMERIC DEFAULT 0"),
        ("credito_resta", "NUMERIC DEFAULT 0"),
        ("importo", "NUMERIC DEFAULT 0"),
        ("importo_acconto", "NUMERIC DEFAULT 0"),
        ("importo_resta", "NUMERIC DEFAULT 0"),
        ("data_credito_saldo", "TEXT"),
        ("numero_credito_saldo", "TEXT"),
        ("metodo_pagamento", "TEXT"),
        ("note", "TEXT"),
    ]
    for col, col_type in colonne_extra:
        try:
            cur.execute(f"ALTER TABLE {tab} ADD COLUMN IF NOT EXISTS {col} {col_type}")
        except Exception:
            conn_err = getattr(cur, "connection", None)
            if conn_err is not None:
                try:
                    conn_err.rollback()
                except Exception:
                    pass


def _inserisci_rinnovo_adattivo(cur, valori_mappati: dict):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'calcoli'
        """
    )
    cols_rows = cur.fetchall() or []
    colonne_reali = {
        (r["column_name"] if isinstance(r, dict) else r[0]) for r in cols_rows
    }

    aliases = {
        "nominativo": ["nominativo", "nome", "cliente"],
        "tipo": ["tipo"],
        "categoria": ["categoria"],
        "data": ["data", "data_operazione", "data_op"],
        "scadenza": ["scadenza", "data_scadenza", "data_fine"],
        "numeraz_trans_crediti": ["numeraz_trans_crediti", "numeraztranscrediti"],
        "credito_richiesto": ["credito_richiesto", "creditorichiesto"],
        "credito_dato": ["credito_dato", "creditodato"],
        "credito_resta": ["credito_resta", "creditoresta"],
        "importo": ["importo"],
        "importo_acconto": ["importo_acconto", "importoacconto"],
        "importo_resta": ["importo_resta", "importoresta"],
        "metodo_pagamento": ["metodo_pagamento", "pagamento", "modalita_pagamento"],
        "note": ["note", "informazioni", "info"],
    }

    colonne_insert = []
    valori_insert = []
    for log_col, val in valori_mappati.items():
        if val is None:
            continue
        candidati = aliases.get(log_col, [log_col])
        col_target = next((c for c in candidati if c in colonne_reali), None)
        if col_target and col_target not in colonne_insert:
            colonne_insert.append(col_target)
            valori_insert.append(val)

    if not colonne_insert:
        raise HTTPException(status_code=500, detail="Nessuna colonna compatibile trovata nella tabella calcoli")

    placeholders = ", ".join(["%s"] * len(colonne_insert))
    cols_sql = ", ".join(colonne_insert)
    cur.execute(
        f"INSERT INTO calcoli ({cols_sql}) VALUES ({placeholders}) RETURNING *",
        valori_insert,
    )
    row = cur.fetchone()
    return dict(row) if isinstance(row, dict) else {}


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


@app.get("/api/scadenze")
@app.get("/api/scadenza")
def api_scadenze_lista(request: Request = None):
    return _leggi_scadenze_aggregate(request)


@app.put("/api/scadenze/{item_id}")
@app.patch("/api/scadenze/{item_id}")
async def api_scadenze_aggiorna(item_id: int, request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")
    return _aggiorna_record_dinamico(item_id, payload or {}, request)


@app.delete("/api/scadenze/{item_id}")
def api_scadenze_elimina(item_id: int, request: Request):
    return _elimina_record_nominativo(item_id, request)


@app.post("/api/rinnovi/saldo_credito")
async def api_rinnovi_saldo_credito(request: Request):
    _verifica_utente_se_disponibile(request)
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")

    data = payload or {}
    nominativo = str(data.get("nominativo") or "").strip()
    rinnovo_id = data.get("rinnovo_id")
    data_credito_saldo = str(data.get("DataCreditoSaldo") or data.get("data_credito_saldo") or "").strip()
    numero_credito_saldo = str(data.get("NumeroCreditoSaldo") or data.get("numero_credito_saldo") or "").strip()

    if not data_credito_saldo or not numero_credito_saldo:
        raise HTTPException(status_code=400, detail="DataCreditoSaldo e NumeroCreditoSaldo sono obbligatori")

    try:
        from db import db_conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database non disponibile: {e}")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            aggiornato = False
            for tab in ("calcoli", "rinnovi"):
                cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
                tab_row = cur.fetchone()
                tab_exists = bool(
                    tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
                )
                if not tab_exists:
                    continue

                _assicura_colonne_rinnovi(cur, tab)

                if rinnovo_id not in (None, ""):
                    cur.execute(
                        f"""
                        UPDATE {tab}
                        SET data_credito_saldo = %s,
                            numero_credito_saldo = %s,
                            credito_dato = COALESCE(NULLIF(credito_richiesto, 0), credito_dato),
                            credito_resta = 0
                        WHERE id = %s
                        RETURNING id
                        """,
                        (data_credito_saldo, numero_credito_saldo, int(rinnovo_id)),
                    )
                    if cur.fetchone():
                        aggiornato = True
                        break

                if not aggiornato and nominativo:
                    cur.execute(
                        f"""
                        UPDATE {tab}
                        SET data_credito_saldo = %s,
                            numero_credito_saldo = %s,
                            credito_dato = COALESCE(NULLIF(credito_richiesto, 0), credito_dato),
                            credito_resta = 0
                        WHERE id = (
                            SELECT id FROM {tab}
                            WHERE LOWER(COALESCE(nominativo::text, '')) = LOWER(%s)
                            ORDER BY id DESC
                            LIMIT 1
                        )
                        RETURNING id
                        """,
                        (data_credito_saldo, numero_credito_saldo, nominativo),
                    )
                    if cur.fetchone():
                        aggiornato = True
                        break

        conn.commit()
        return {
            "ok": True,
            "aggiornato": aggiornato,
            "DataCreditoSaldo": data_credito_saldo,
            "NumeroCreditoSaldo": numero_credito_saldo,
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore aggiornamento saldo credito: {e}")
    finally:
        conn.close()


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
    nominativo = str(
        data.get("nominativo")
        or data.get("nome")
        or data.get("cliente")
        or ""
    ).strip()
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
                        data_credito_saldo TEXT,
                        numero_credito_saldo TEXT,
                        metodo_pagamento TEXT,
                        note TEXT
                    )
                    """
                )
            else:
                _assicura_colonne_rinnovi(cur, "calcoli")

            valori_mappati = {
                "nominativo": nominativo,
                "tipo": "Rinnovo",
                "categoria": "Rinnovo",
                "data": data_op,
                "scadenza": scadenza,
                "numeraz_trans_crediti": numeraz_trans_crediti,
                "credito_richiesto": credito_richiesto,
                "credito_dato": credito_dato,
                "credito_resta": credito_resta,
                "importo": importo,
                "importo_acconto": importo_acconto,
                "importo_resta": importo_resta,
                "metodo_pagamento": metodo,
                "note": note,
            }
            row = _inserisci_rinnovo_adattivo(cur, valori_mappati)
        conn.commit()
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
            **row,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio rinnovo: {e}")
    finally:
        conn.close()


@app.get("/api/contatti")
@app.get("/api/nominativi")
def api_nominativi(request: Request = None):
    try:
        from db import db_conn
        _verifica_utente_se_disponibile(request)
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                for tab in ("nominativi", "contatti", "clienti", "anagrafica"):
                    cur.execute("SELECT to_regclass(%s) AS tab", (f"public.{tab}",))
                    tab_row = cur.fetchone()
                    tab_exists = bool(
                        tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
                    )
                    if not tab_exists:
                        continue
                    try:
                        cur.execute(f"SELECT * FROM {tab} ORDER BY id DESC")
                    except Exception:
                        conn.rollback()
                        cur.execute(f"SELECT * FROM {tab}")
                    rows = cur.fetchall() or []
                    if rows:
                        return [dict(r) for r in rows]
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception:
        pass
    return []


@app.post("/api/contatti")
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


@app.put("/api/contatti/{item_id}")
@app.patch("/api/contatti/{item_id}")
@app.put("/api/nominativi/{item_id}")
@app.patch("/api/nominativi/{item_id}")
async def api_nominativi_aggiorna(item_id: int, request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")
    return _aggiorna_record_dinamico(item_id, payload or {}, request)


@app.delete("/api/contatti/{item_id}")
@app.delete("/api/nominativi/{item_id}")
def api_nominativi_elimina(item_id: int, request: Request):
    return _elimina_record_nominativo(item_id, request)


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