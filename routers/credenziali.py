import json
import urllib.request
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from auth import get_current_user
from database import db_conn
from models import CredenzialiPayload

router = APIRouter()

@router.get("/api/credenziali")
def api_credenziali(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, nome_file, link, percorso, user_id, password, file_token, scadenza, informazioni, creato_il FROM credenziali ORDER BY creato_il DESC")
            return cur.fetchall()
    finally:
        conn.close()

@router.post("/api/credenziali")
def api_credenziali_nuovo(payload: CredenzialiPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO credenziali (nominativo, nome_file, link, percorso, user_id, password, file_token, scadenza, informazioni, creato_il) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    d.get("nominativo", ""),
                    d.get("nome_file", ""),
                    d.get("link", ""),
                    d.get("percorso", ""),
                    d.get("user_id", ""),
                    d.get("password", ""),
                    d.get("file_token", ""),
                    d.get("scadenza", ""),
                    d.get("informazioni", ""),
                    datetime.now().isoformat()
                )
            )
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.put("/api/credenziali/{id}")
def api_credenziali_modifica(id: int, payload: CredenzialiPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE credenziali SET nominativo=%s, nome_file=%s, link=%s, percorso=%s, user_id=%s, password=%s, file_token=%s, scadenza=%s, informazioni=%s WHERE id=%s",
                (
                    d.get("nominativo", ""),
                    d.get("nome_file", ""),
                    d.get("link", ""),
                    d.get("percorso", ""),
                    d.get("user_id", ""),
                    d.get("password", ""),
                    d.get("file_token", ""),
                    d.get("scadenza", ""),
                    d.get("informazioni", ""),
                    id
                )
            )
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/credenziali/{id}")
def api_credenziali_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT file_token, percorso FROM credenziali WHERE id = %s", (id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Record non trovato")
            if item['percorso'] and item['file_token']:
                try:
                    cur.execute("SELECT user_id, password FROM credenziali WHERE id = %s", (id,))
                    creds = cur.fetchone()
                    if creds:
                        body = json.dumps({
                            "token": item['file_token'],
                            "user": creds['user_id'],
                            "password": creds['password']
                        }).encode('utf-8')
                        req = urllib.request.Request(item['percorso'], data=body, method='POST')
                        req.add_header('Content-Type', 'application/json')
                        urllib.request.urlopen(req, timeout=5)
                except Exception as e:
                    print(f"Avviso cancellazione remota: {e}")
            cur.execute("DELETE FROM credenziali WHERE id = %s", (id,))
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}
