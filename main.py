import os
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


def _trova_file_html(page_name: str):
    safe_name = os.path.basename(page_name).strip()
    if not safe_name:
        return None
    nomi_candidati = HTML_ALIASES.get(safe_name, [f"{safe_name}.html"])
    for nome in nomi_candidati:
        for base_dir in ("", "static", "templates"):
            percorso = os.path.join(base_dir, nome) if base_dir else nome
            if os.path.isfile(percorso):
                return percorso
    return None


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
        from db import db_conn, get_current_user
        if request is not None:
            try:
                get_current_user(request)
            except Exception:
                pass
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
                query += " AND LOWER(COALESCE(tipo::text, '')) = LOWER(%s)"
                params.append(tipo.strip())
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


@app.get("/api/metodi_pagamento")
def api_metodi_pagamento(request: Request = None):
    try:
        from db import db_conn, get_current_user
        if request is not None:
            try:
                get_current_user(request)
            except Exception:
                pass
        conn = db_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.metodi_pagamento') AS tab")
                tab_row = cur.fetchone()
                tab_exists = bool(
                    tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
                )
                if tab_exists:
                    cur.execute("SELECT * FROM metodi_pagamento ORDER BY id ASC")
                    rows = cur.fetchall() or []
                    if rows:
                        return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        pass
    return MODALITA_PAGAMENTO_DEFAULT


@app.get("/{page_name}.html")
def serve_any_html(page_name: str):
    percorso = _trova_file_html(page_name)
    if percorso:
        return FileResponse(percorso)
    raise HTTPException(status_code=404, detail=f"{page_name}.html non trovato")


if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")