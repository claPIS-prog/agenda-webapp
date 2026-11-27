import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()


def _to_float(val, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


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


@app.get("/calcoli.html")
def serve_calcoli():
    for candidate in ("calcoli.html", "static/calcoli.html", "templates/calcoli.html"):
        if os.path.exists(candidate):
            return FileResponse(candidate)
    return {"detail": "calcoli.html non trovato"}


if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")