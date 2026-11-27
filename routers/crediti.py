from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from db import db_conn, estrai_dati, get_current_user

router = APIRouter()

def _leggi_righe_crediti(data_da: str = "", data_a: str = "", fornitore_da: str = "", fornitore_a: str = ""):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = "SELECT id, data_acquisto, fornitore, modalita_pagamento, quantita, valore, note, creato_il FROM crediti WHERE 1=1"
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
    finally:
        conn.close()

async def _salva_acquisto_credito(d: dict, id_record: int | None = None):
    qta = int(d.get("quantita", d.get("qta", 0)) or 0)
    prezzo_unit = float(d.get("prezzo_unitario", d.get("prezzo", d.get("valore_singolo", 0))) or 0)
    valore_raw = d.get("valore", d.get("valore_totale", d.get("importo")))
    valore = float(valore_raw or 0) if valore_raw not in (None, "") else (qta * prezzo_unit)

    data_acq = d.get("data_acquisto") or d.get("data") or datetime.now().strftime("%Y-%m-%d")
    fornitore = d.get("fornitore") or d.get("nominativo") or d.get("tipo") or ""
    mod_pag = d.get("modalita_pagamento") or d.get("metodo_pagamento") or ""
    note = d.get("note") or d.get("informazioni") or ""

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if id_record is not None:
                cur.execute("""
                    UPDATE crediti
                    SET data_acquisto=%s, fornitore=%s, modalita_pagamento=%s, quantita=%s, valore=%s, note=%s
                    WHERE id=%s
                """, (data_acq, fornitore, mod_pag, qta, valore, note, id_record))
                record_id = id_record
            else:
                cur.execute("""
                    INSERT INTO crediti (data_acquisto, fornitore, modalita_pagamento, quantita, valore, note, creato_il)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (data_acq, fornitore, mod_pag, qta, valore, note, datetime.now().isoformat()))
                record_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": record_id, "valore": valore}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
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
    d = estrai_dati(await request.json())
    return await _salva_acquisto_credito(d)

@router.put("/api/crediti/{id}")
@router.put("/api/credito/{id}")
async def api_crediti_modifica(id: int, request: Request):
    get_current_user(request)
    d = estrai_dati(await request.json())
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
