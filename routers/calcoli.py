from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from db import db_conn, estrai_dati, get_current_user

router = APIRouter()


def _to_int(val, default: int = 0) -> int:
    if val is None or val == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _to_float(val, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _estrai_righe_e_conteggi(cur, query: str, params: list):
    cur.execute(query, params)
    rows = cur.fetchall() or []
    righe = [dict(r) for r in rows]
    totale = len(righe)
    return {
        "righe": righe,
        "items": righe,
        "totale": totale,
        "count": totale,
    }


@router.get("/api/calcoli")
@router.get("/api/lista_calcoli")
def api_calcoli(
    nominativo_da: str = "",
    nominativo_a: str = "",
    data_da: str = "",
    data_a: str = "",
    request: Request = None,
):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.calcoli') AS tab")
            tab_row = cur.fetchone()
            tab_exists = bool(
                tab_row and (tab_row["tab"] if isinstance(tab_row, dict) else tab_row[0])
            )

            if not tab_exists:
                return {"righe": [], "items": [], "totale": 0, "count": 0}

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

            try:
                return _estrai_righe_e_conteggi(cur, query, params)
            except Exception:
                conn.rollback()
                with conn.cursor() as cur2:
                    return _estrai_righe_e_conteggi(
                        cur2, "SELECT * FROM calcoli ORDER BY id DESC", []
                    )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura calcoli: {e}")
    finally:
        conn.close()


@router.post("/api/calcoli")
async def api_calcoli_crea(request: Request):
    get_current_user(request)
    try:
        raw_body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")

    d = estrai_dati(raw_body)
    nominativo = str(d.get("nominativo") or "").strip()
    data_val = str(d.get("data") or datetime.now().strftime("%Y-%m-%d")).strip()
    importo = _to_float(d.get("importo"), 0.0)
    note = str(d.get("note") or "").strip()

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calcoli (nominativo, data, importo, note, creato_il)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (nominativo, data_val, importo, note, datetime.now().isoformat()),
            )
            row = cur.fetchone()
            record_id = row["id"] if isinstance(row, dict) else (row[0] if row else None)
        conn.commit()
        return {"ok": True, "id": record_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio calcolo: {e}")
    finally:
        conn.close()


@router.delete("/api/calcoli/{id}")
def api_calcoli_elimina(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM calcoli WHERE id = %s", (int(id),))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore cancellazione calcolo: {e}")
    finally:
        conn.close()
