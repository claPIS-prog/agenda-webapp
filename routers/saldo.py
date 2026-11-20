from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from auth import get_current_user
from database import db_conn
from models import RinnovoPayload

router = APIRouter()

@router.get("/api/saldo_rinnovi")
def api_saldo_rinnovi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT s.id, s.rinnovo_id, s.num_credito_saldo, s.data_credito_rinnovo_saldo, s.val_nc_dato, s.val_nc_saldo, s.informazioni_note, s.creato_il, r.num_credito_rich, r.num_credito_dato, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato, r.val_nc_rich, r.val_singolo_nc_rich, n.nominativo FROM saldo_rinnovi s JOIN rinnovi r ON r.id = s.rinnovo_id JOIN nominativi n ON n.id = r.nominativo_id ORDER BY s.creato_il DESC")
            return cur.fetchall()
    finally:
        conn.close()

@router.get("/api/rinnovi_per_saldo")
def api_rinnovi_per_saldo(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT r.id, r.num_credito_rich, r.num_credito_dato, r.num_credito_dare, r.data_credito_rinnovo_rich, r.data_credito_rinnovo_dato, r.val_nc_rich, r.val_singolo_nc_rich, n.nominativo FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id ORDER BY n.nominativo")
            return cur.fetchall()
    finally:
        conn.close()

@router.post("/api/saldo_rinnovo")
def api_saldo_rinnovo_nuovo(payload: RinnovoPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            rinnovo_id = int(dati.get("rinnovo_id"))
            cur.execute("SELECT num_credito_dato, val_singolo_nc_rich FROM rinnovi WHERE id = %s", (rinnovo_id,))
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Rinnovo non trovato")
            num_dato = row["num_credito_dato"]; val_singolo = row["val_singolo_nc_rich"] or 0
            num_saldo = int(dati.get("num_credito_saldo", 0))
            cur.execute("INSERT INTO saldo_rinnovi (rinnovo_id, num_credito_saldo, data_credito_rinnovo_saldo, val_nc_dato, val_nc_saldo, informazioni_note, creato_il) VALUES (%s,%s,%s,%s,%s,%s,%s)", (rinnovo_id, num_saldo, dati.get("data_credito_rinnovo_saldo",""), num_dato*val_singolo, num_saldo*val_singolo, dati.get("informazioni_note",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/saldo_rinnovo/{id}")
def api_saldo_rinnovo_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM saldo_rinnovi WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
