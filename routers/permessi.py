from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload, PermessiPayload

router = APIRouter()

@router.get("/api/amici")
def api_amici(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, telegram_id, nome FROM autorizzati ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()

@router.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO autorizzati (telegram_id, password, nome) VALUES (%s, %s, %s) ON CONFLICT (telegram_id) DO UPDATE SET password = excluded.password, nome = excluded.nome RETURNING id", (payload.telegram_id, payload.password, payload.nome))
            new_id = cur.fetchone()["id"]
            for mod in ALL_MODULES:
                cur.execute("INSERT INTO permessi (user_id, modulo, attivo) VALUES (%s, %s, TRUE) ON CONFLICT (user_id, modulo) DO NOTHING", (new_id, mod))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/rimuovi_amico/{amico_id}")
def api_rimuovi_amico(amico_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM permessi WHERE user_id = %s", (amico_id,))
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.get("/api/permessi/{user_id}")
def api_get_permessi(user_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {row["modulo"]: row["attivo"] for row in rows}
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            return perms
    finally:
        conn.close()

@router.post("/api/salva_permessi")
async def api_salva_permessi(request: Request):
    """
    Versione più tollerante: accetta anche campi extra (date) senza rompersi.
    """
    get_current_user(request)
    body = {}
    try:
        body = await request.json()
    except:
        pass

    user_id = body.get("user_id")
    permessi = body.get("permessi") or {}

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id mancante")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            for modulo, attivo in permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo) 
                        VALUES (%s, %s, %s) 
                        ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = EXCLUDED.attivo
                    """, (user_id, modulo, bool(attivo)))
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
