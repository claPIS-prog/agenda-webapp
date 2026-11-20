from datetime import datetime
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import NotaPayload

router = APIRouter()

@router.get("/api/note")
def api_note(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT n.id, n.nominativo_id, n.messaggio, n.creato_il, nom.nominativo FROM note n JOIN nominativi nom ON nom.id = n.nominativo_id ORDER BY n.creato_il DESC")
            return cur.fetchall()
    finally: conn.close()

@router.post("/api/note")
def api_note_nuovo(payload: NotaPayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note (nominativo_id, messaggio, creato_il) VALUES (%s,%s,%s)", (int(dati.get("nominativo_id")), dati.get("messaggio",""), datetime.now().isoformat()))
        conn.commit()
    finally: conn.close()
    return {"ok": True}

@router.delete("/api/note/{id}")
def api_note_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM note WHERE id = %s", (id,))
        conn.commit()
    finally: conn.close()
    return {"ok": True}
