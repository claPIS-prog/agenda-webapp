from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload, PermessiPayload
from datetime import datetime

router = APIRouter()

@router.get("/api/amici")
def api_amici(request: Request):
    """Restituisce lista utenti autorizzati con date e permessi."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, telegram_id, nome, 
                       data_inizio_validita, data_revoca, data_fine_validita
                FROM autorizzati 
                ORDER BY nome
            """)
            return cur.fetchall()
    finally:
        conn.close()

@router.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    """Aggiunge nuovo utente con date di validità."""
    get_current_user(request)
    dati = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO autorizzati (telegram_id, password, nome, 
                    data_inizio_validita, data_revoca, data_fine_validita) 
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE SET 
                    password = excluded.password, 
                    nome = excluded.nome,
                    data_inizio_validita = excluded.data_inizio_validita,
                    data_revoca = excluded.data_revoca,
                    data_fine_validita = excluded.data_fine_validita
                RETURNING id
            """, (
                dati.get("telegram_id"),
                dati.get("password"),
                dati.get("nome"),
                dati.get("data_inizio_validita"),
                dati.get("data_revoca"),
                dati.get("data_fine_validita")
            ))
            new_id = cur.fetchone()["id"]
            
            # Crea permessi default per tutti i moduli
            for mod in ALL_MODULES:
                cur.execute("""
                    INSERT INTO permessi (user_id, modulo, attivo) 
                    VALUES (%s, %s, TRUE) 
                    ON CONFLICT (user_id, modulo) DO NOTHING
                """, (new_id, mod))
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/rimuovi_amico/{amico_id}")
def api_rimuovi_amico(amico_id: int, request: Request):
    """Rimuove utente e tutti i suoi permessi."""
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
    """Restituisce permessi modulo per modulo + date utente."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Permessi moduli
            cur.execute("""
                SELECT modulo, attivo FROM permessi WHERE user_id = %s
            """, (user_id,))
            rows = cur.fetchall()
            perms = {row["modulo"]: row["attivo"] for row in rows}
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            
            # Date utente
            cur.execute("""
                SELECT data_inizio_validita, data_revoca, data_fine_validita
                FROM autorizzati WHERE id = %s
            """, (user_id,))
            date_row = cur.fetchone()
            
            return {
                "permessi": perms,
                "date": {
                    "data_inizio_validita": date_row["data_inizio_validita"] if date_row else None,
                    "data_revoca": date_row["data_revoca"] if date_row else None,
                    "data_fine_validita": date_row["data_fine_validita"] if date_row else None
                }
            }
    finally:
        conn.close()

@router.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    """Salva permessi moduli + date validità utente."""
    get_current_user(request)
    dati = payload.dati
    user_id = dati.get("user_id")
    permessi = dati.get("permessi", {})
    
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id mancante")
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Salva permessi moduli
            for modulo, attivo in permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo) 
                        VALUES (%s, %s, %s) 
                        ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = EXCLUDED.attivo
                    """, (user_id, modulo, bool(attivo)))
            
            # Salva date validità
            cur.execute("""
                UPDATE autorizzati SET 
                    data_inizio_validita = %s,
                    data_revoca = %s,
                    data_fine_validita = %s
                WHERE id = %s
            """, (
                dati.get("data_inizio_validita"),
                dati.get("data_revoca"),
                dati.get("data_fine_validita"),
                user_id
            ))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
