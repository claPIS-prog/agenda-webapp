import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()


def _leggi_calcoli_fallback(
    nominativo_da: str = "",
    nominativo_a: str = "",
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
            if data_da:
                query += " AND COALESCE(data::text, '') >= %s"
                params.append(data_da)
            if data_a:
                query += " AND COALESCE(data::text, '') <= %s"
                params.append(data_a)
            if nominativo_da:
                query += " AND COALESCE(nominativo::text, '') >= %s"
                params.append(nominativo_da)
            if nominativo_a:
                query += " AND COALESCE(nominativo::text, '') <= %s"
                params.append(nominativo_a)
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
        nominativo_da: str = "",
        nominativo_a: str = "",
        data_da: str = "",
        data_a: str = "",
        request: Request = None,
    ):
        return _leggi_calcoli_fallback(nominativo_da, nominativo_a, data_da, data_a, request)

try:
    from routers.crediti import router as crediti_router
    app.include_router(crediti_router)
except Exception as e:
    print(f"Avviso import routers.crediti: {e}")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/contabilita.html")
def serve_contabilita():
    for candidate in ("contabilita.html", "static/contabilita.html", "templates/contabilita.html"):
        if os.path.exists(candidate):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="contabilita.html non trovato")

@app.get("/calcoli.html")
def serve_calcoli():
    for candidate in ("calcoli.html", "static/calcoli.html", "templates/calcoli.html"):
        if os.path.exists(candidate):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="calcoli.html non trovato")

@app.get("/crediti.html")
def serve_crediti():
    for candidate in ("crediti.html", "static/crediti.html", "templates/crediti.html"):
        if os.path.exists(candidate):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="crediti.html non trovato")

@app.get("/lista_calcoli.html")
def serve_lista_calcoli():
    for candidate in ("lista_calcoli.html", "static/lista_calcoli.html", "templates/lista_calcoli.html"):
        if os.path.exists(candidate):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="lista_calcoli.html non trovato")

@app.get("/contabilita_dettagli.html")
def serve_contabilita_dettagli():
    for candidate in ("contabilita_dettagli.html", "static/contabilita_dettagli.html", "templates/contabilita_dettagli.html"):
        if os.path.exists(candidate):
            return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="contabilita_dettagli.html non trovato")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")