from fastapi import APIRouter, Request, HTTPException
from auth import get_current_user
from database import db_conn
from config import ALL_MODULES
from models import AmicoPayload, PermessiPayload
from datetime import datetime

router = APIRouter()

# -----------------------------------------------------------------------------
# 1. LISTA NOMINATIVI (per la dropdown)
# -----------------------------------------------------------------------------
@router.get("/api/amici")
def api_amici(request: Request):
    """Restituisce TUTTI i nominativi dalla tabella nominativi."""
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo as nome FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 2. GET PERMESSI + DATE per un nominativo
# -----------------------------------------------------------------------------
@router.get("/api/permessi/{user_id}")
def api_get_permessi(user_id: int, request: Request):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Permessi moduli
            cur.execute("SELECT modulo, attivo FROM permessi WHERE user_id = %s", (user_id,))
            rows = cur.fetchall()
            perms = {}
            for row in rows:
                if isinstance(row, dict):
                    perms[row["modulo"]] = row["attivo"]
                else:
                    perms[row[0]] = row[1]
            for mod in ALL_MODULES:
                if mod not in perms:
                    perms[mod] = False

            # Date (se esistono righe permessi per questo user)
            cur.execute("""
                SELECT data_inizio_validita, data_revoca, data_fine_validita
                FROM permessi WHERE user_id = %s LIMIT 1
            """, (user_id,))
            date_row = cur.fetchone()

            dates = {
                "data_inizio_validita": "",
                "data_revoca": "",
                "data_fine_validita": ""
            }
            if date_row:
                d = dict(date_row) if isinstance(date_row, dict) else dict(zip(
                    ["data_inizio_validita", "data_revoca", "data_fine_validita"], date_row
                ))
                for k in ["data_inizio_validita", "data_revoca", "data_fine_validita"]:
                    if d.get(k):
                        dates[k] = str(d[k])[:10]

            return {"permessi": perms, "date": dates}
    finally:
        conn.close()

# -----------------------------------------------------------------------------
# 3. SALVA PERMESSI + DATE (gestisce FK autorizzati)
# -----------------------------------------------------------------------------
@router.post("/api/salva_permessi")
def api_salva_permessi(payload: PermessiPayload, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Se non esiste un record in autorizzati con quell'id, lo creo
            # (per rispettare il FK permessi.user_id → autorizzati.id)
            cur.execute("SELECT id FROM autorizzati WHERE id = %s", (payload.user_id,))
            if not cur.fetchone():
                cur.execute("SELECT nominativo FROM nominativi WHERE id = %s", (payload.user_id,))
                nom = cur.fetchone()
                nome = nom["nominativo"] if nom else f"Nominativo #{payload.user_id}"
                cur.execute("""
                    INSERT INTO autorizzati (id, telegram_id, password, nome)
                    VALUES (%s, %s, 'auto', %s)
                    ON CONFLICT (id) DO NOTHING
                """, (payload.user_id, -payload.user_id, nome))

            # Salva permessi moduli
            for modulo, attivo in payload.permessi.items():
                if modulo in ALL_MODULES:
                    cur.execute("""
                        INSERT INTO permessi (user_id, modulo, attivo)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, modulo) DO UPDATE SET attivo = EXCLUDED.attivo
                    """, (payload.user_id, modulo, bool(attivo)))

            # Salva date
            cur.execute("""
                UPDATE permessi SET
                    data_inizio_validita = %s,
                    data_revoca = %s,
                    data_fine_validita = %s
                WHERE user_id = %s
            """, (
                payload.data_inizio_validita or None,
                payload.data_revoca or None,
                payload.data_fine_validita or None,
                payload.user_id
            ))
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
    return {"ok": True}

# -----------------------------------------------------------------------------
# 4. AGGIUNGI / RIMUOVI AMICO (mantenuti per compatibilità)
# -----------------------------------------------------------------------------
@router.post("/api/aggiungi_amico")
def api_aggiungi_amico(payload: AmicoPayload, request: Request):
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
