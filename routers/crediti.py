from datetime import datetime
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import CreditoPayload

router = APIRouter()

@router.get("/api/crediti")
def api_crediti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crediti ORDER BY data_acquisto DESC")
            return cur.fetchall()
    finally:
        conn.close()

@router.post("/api/crediti")
def api_crediti_salva(payload: CreditoPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO crediti (data_acquisto, fornitore, modalita_pagamento, quantita, valore, note, creato_il) 
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (d.get("data_acquisto",""), d.get("fornitore",""), d.get("modalita_pagamento",""),
                 int(d.get("quantita",0)), float(d.get("valore",0)), d.get("note",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.put("/api/crediti/{id}")
def api_crediti_modifica(id: int, payload: CreditoPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""UPDATE crediti SET data_acquisto=%s, fornitore=%s, modalita_pagamento=%s, quantita=%s, valore=%s, note=%s WHERE id=%s""",
                (d.get("data_acquisto",""), d.get("fornitore",""), d.get("modalita_pagamento",""),
                 int(d.get("quantita",0)), float(d.get("valore",0)), d.get("note",""), id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/crediti/{id}")
def api_crediti_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM crediti WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
