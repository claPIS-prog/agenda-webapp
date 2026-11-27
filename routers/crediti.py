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


def _leggi_righe_crediti(data_da: str = "", data_a: str = "", fornitore_da: str = "", fornitore_a: str = ""):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = (
                "SELECT id, data_acquisto, fornitore, modalita_pagamento, quantita, valore, note, creato_il "
                "FROM crediti WHERE 1=1"
            )
            params = []
            if data_da:
                query += " AND data_acquisto >= %s"
                params.append(data_da)
            if data_a:
                query += " AND data_acquisto <= %s"
                params.append(data_a)
            if fornitore_da:
                query += " AND fornitore >= %s"
                params.append(fornitore_da)
            if fornitore_a:
                query += " AND fornitore <= %s"
                params.append(fornitore_a)
            query += " ORDER BY COALESCE(data_acquisto, '') DESC, id DESC"
            cur.execute(query, params)
            return cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura crediti: {e}")
    finally:
        conn.close()


async def _salva_acquisto_credito(d: dict, id_record: int | None = None):
    qta = _to_int(d.get("quantita", d.get("qta", 0)), 0)
    prezzo_unit = _to_float(d.get("prezzo_unitario", d.get("prezzo", d.get("valore_singolo", 0))), 0.0)
    valore_raw = d.get("valore", d.get("valore_totale", d.get("importo")))
    valore = _to_float(valore_raw, 0.0) if valore_raw not in (None, "") else round(qta * prezzo_unit, 2)

    data_acq = str(d.get("data_acquisto") or d.get("data") or datetime.now().strftime("%Y-%m-%d")).strip()
    fornitore = str(d.get("fornitore") or d.get("nominativo") or d.get("tipo") or "").strip()
    mod_pag = str(d.get("modalita_pagamento") or d.get("metodo_pagamento") or "").strip()
    note = str(d.get("note") or d.get("informazioni") or "").strip()

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if id_record is not None:
                cur.execute(
                    """
                    UPDATE crediti
                    SET data_acquisto=%s, fornitore=%s, modalita_pagamento=%s, quantita=%s, valore=%s, note=%s
                    WHERE id=%s
                    """,
                    (data_acq, fornitore, mod_pag, qta, valore, note, id_record),
                )
                record_id = id_record
            else:
                cur.execute(
                    """
                    INSERT INTO crediti (data_acquisto, fornitore, modalita_pagamento, quantita, valore, note, creato_il)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (data_acq, fornitore, mod_pag, qta, valore, note, datetime.now().isoformat()),
                )
                row = cur.fetchone()
                record_id = row["id"] if row else None
        conn.commit()
        return {"ok": True, "id": record_id, "valore": valore}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore salvataggio credito: {e}")
    finally:
        conn.close()


def _elimina_credito_by_id(record_id: int):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crediti WHERE id = %s", (int(record_id),))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Errore DB cancellazione credito: {e}")
    finally:
        conn.close()


@router.get("/api/crediti")
@router.get("/api/lista_crediti")
@router.get("/api/crediti_disponibili")
def api_crediti(data_da: str = "", data_a: str = "", fornitore_da: str = "", fornitore_a: str = "", request: Request = None):
    get_current_user(request)
    return _leggi_righe_crediti(data_da, data_a, fornitore_da, fornitore_a)


@router.post("/api/crediti")
@router.post("/api/credito")
@router.post("/api/saldo_iniziale")
async def api_crediti_salva(request: Request):
    get_current_user(request)
    try:
        raw_body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")
    d = estrai_dati(raw_body)
    return await _salva_acquisto_credito(d)


@router.put("/api/crediti/{id}")
@router.put("/api/credito/{id}")
async def api_crediti_modifica(id: int, request: Request):
    get_current_user(request)
    raw_body = await request.json()
    d = estrai_dati(raw_body)
    return await _salva_acquisto_credito(d, id_record=id)


@router.delete("/api/crediti/{id}")
@router.delete("/api/credito/{id}")
def api_crediti_cancella(id: int, request: Request):
    get_current_user(request)
    _elimina_credito_by_id(id)
    return {"ok": True}


@router.delete("/api/crediti")
@router.delete("/api/credito")
def api_crediti_cancella_query(id: int | None = None, request: Request = None):
    get_current_user(request)
    if id is not None:
        _elimina_credito_by_id(id)
    return {"ok": True}
