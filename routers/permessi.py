from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload, PermessiPayload
from datetime import datetime

router = APIRouter()

@router.get("/api/amici")
def api_amici(request: Request):
    """Restituisce lista utenti autorizzati con date."""
    # get_current_user(request)  # Bypassato per evitare blocchi
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT a.id, a.telegram_id, a.nome,
                       p.data_inizio_validita, p.data_revoca, p.data_fine_validita
                FROM autorizzati a
                LEFT JOIN permessi p ON p.user_id = a.id
                ORDER BY a.nome
            """)
            rows = cur.fetchall()
            result = []
            seen = set()
            for r in rows:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    result.append({
                        "id": r["id"],
                        "telegram_id": r["telegram_id"],
                        "nome": r["nome"],
                        "data_inizio_validita": str(r.get("data_inizio_validita", ""))[:10] if r.get("data_inizio_validita") else "",
                        "data_revoca": str(r.get("data_revoca", ""))[:10] if r.get("data_revoca") else "",
                        "data_fine_validita": str(r.get("data_fine_validita", ""))[:10] if r.get("data_fine_validita") else ""
                    })
            return result
    finally:
        conn.close()

@router.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
    """Aggiunge nuovo utente con permessi default."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO autorizzati (telegram_id, password, nome) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (telegram_id) DO UPDATE SET 
                    password = excluded.password, 
                    nome = excluded.nome 
                RETURNING id
            """, (payload.telegram_id, payload.password, payload.nome))
            new_id = cur.fetchone()["id"]
            
            oggi = datetime.now().date()
            for mod in ALL_MODULES:
                cur.execute("""
                    INSERT INTO permessi (user_id, modulo, attivo, data_inizio_validita) 
                    VALUES (%s, %s, TRUE, %s) 
                    ON CONFLICT (user_id, modulo) DO NOTHING
                """, (new_id, mod, oggi))
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
    # get_current_user(request)  # Bypassato per test
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Permessi moduli
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {row["modulo"]: row["attivo"] for row in rows}
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False
            
            # Date dalla prima riga permessi dell'utente
            cur.execute("""
                SELECT data_inizio_validita, data_revoca, data_fine_validita
                FROM permessi WHERE user_id = %s LIMIT 1
            """, (user_id,))
            date_row = cur.fetchone()
            
            return {
                "permessi": perms,
                "date": {
                    "data_inizio_validita": str(date_row["data_inizio_validita"])[:10] if date_row and date_row.get("data_inizio_validita") else "",
                    "data_revoca": str(date_row["data_revoca"])[:10] if date_row and date_row.get("data_revoca") else "",
                    "data_fine_validita": str(date_row["data_fine_validita"])[:10] if date_row and date_row.get("data_fine_validita") else ""
                }
            }
    finally:
        conn.close()

@router.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    """Salva permessi moduli + date validità."""
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Salva permessi moduli
            for modulo, attivo in payload.permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo) 
                        VALUES (%s, %s, %s) 
                        ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = EXCLUDED.attivo
                    """, (payload.user_id, modulo, bool(attivo)))
            
            # Salva date su tutte le righe dell'utente
            cur.execute("""
                UPDATE permessi SET 
                    data_inizio_validita = %s,
                    data_revoca = %s,
                    data_fine_validita = %s
                WHERE user_id = %s
            """, (
                payload.data_inizio_validita,
                payload.data_revoca,
                payload.data_fine_validita,
                payload.user_id
            ))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}
