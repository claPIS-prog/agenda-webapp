from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import AzionePayload

router = APIRouter()


def _row_to_dict(cur, row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def _rows_to_dicts(cur, rows):
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/api/nominativi")
def api_nominativi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nominativo, nominativo AS nome, tipo, user_id, password
                FROM nominativi
                ORDER BY nominativo
            """)
            return _rows_to_dicts(cur, cur.fetchall())
    finally:
        conn.close()


@router.get("/api/contatti")
def api_contatti(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nominativo, tipo, prezzo, cadenza, user_id, password, 
                       tipo_linea, dispositivo, sistema_operativo, buffett, metodo_pagamento, 
                       operatore_it, server, reseller, cellulare, procuratore, 
                       apk_utilizzata, uso_vpn, quale_vpn, citta, 
                       data_iscrizione, data_fine, informazioni 
                FROM nominativi 
                ORDER BY nominativo
            """)
            return _rows_to_dicts(cur, cur.fetchall())
    finally:
        conn.close()


# -------------------------------------------------
# ENDPOINT GESTIONE AMICI (TABELLA autorizzati)
# -------------------------------------------------
@router.get("/api/amici")
def api_amici(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, telegram_id, password, nome FROM autorizzati ORDER BY id DESC")
            return _rows_to_dicts(cur, cur.fetchall())
    finally:
        conn.close()


@router.get("/api/amici/{amico_id}")
def api_amico_dettaglio(amico_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, telegram_id, password, nome FROM autorizzati WHERE id = %s", (amico_id,))
            row = _row_to_dict(cur, cur.fetchone())
            if not row:
                return {"id": None, "telegram_id": None, "password": "", "nome": ""}
            return row
    finally:
        conn.close()


@router.post("/api/salva_amico")
async def api_salva_amico(request: Request):
    get_current_user(request)
    payload = await request.json()
    amico_id = payload.get("id")
    telegram_id = payload.get("telegram_id")
    password = payload.get("password", "")
    nome = payload.get("nome", "")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            if amico_id:
                cur.execute("""
                    UPDATE autorizzati
                    SET telegram_id = %s, password = %s, nome = %s
                    WHERE id = %s
                """, (telegram_id, password, nome, amico_id))
            else:
                cur.execute("""
                    INSERT INTO autorizzati (telegram_id, password, nome)
                    VALUES (%s, %s, %s)
                """, (telegram_id, password, nome))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.delete("/api/amici/{amico_id}")
def api_elimina_amico(amico_id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM autorizzati WHERE id = %s", (amico_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@router.post("/api/azione")
def api_azione(payload: AzionePayload, request: Request):
    get_current_user(request)
    dati = payload.dati
    azione = dati.get("azione", "")
    conn = db_conn()
    try:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # AZIONI SUI NOMINATIVI / CONTATTI
            # -------------------------------------------------
            if azione == "cancella":
                cur.execute("DELETE FROM nominativi WHERE id = %s", (dati.get("id"),))
            
            elif azione == "nuovo":
                cur.execute("""
                    INSERT INTO nominativi (
                        nominativo, tipo, user_id, password, prezzo, cadenza, tipo_linea, 
                        server, reseller, dispositivo, sistema_operativo, buffett, 
                        metodo_pagamento, operatore_it, cellulare, procuratore, 
                        apk_utilizzata, uso_vpn, quale_vpn, citta, 
                        data_iscrizione, data_fine, informazioni
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    dati.get("nominativo",""), dati.get("tipo",""), dati.get("user_id",""), 
                    dati.get("password",""), float(dati.get("prezzo",0)), dati.get("cadenza",""), 
                    dati.get("tipo_linea",""), dati.get("server",""), dati.get("reseller",""),
                    dati.get("dispositivo",""), dati.get("sistema_operativo",""),
                    dati.get("buffett",""), dati.get("metodo_pagamento",""), dati.get("operatore_it",""),
                    dati.get("cellulare",""), dati.get("procuratore",""),
                    dati.get("apk_utilizzata",""), int(dati.get("uso_vpn",0)),
                    dati.get("quale_vpn",""), dati.get("citta",""),
                    dati.get("data_iscrizione",""), dati.get("data_fine",""),
                    dati.get("informazioni","")
                ))
            
            elif azione == "modifica":
                cur.execute("""
                    UPDATE nominativi SET 
                        nominativo=%s, tipo=%s, user_id=%s, password=%s, prezzo=%s, cadenza=%s, 
                        tipo_linea=%s, server=%s, reseller=%s, dispositivo=%s, sistema_operativo=%s, 
                        buffett=%s, metodo_pagamento=%s, operatore_it=%s, cellulare=%s, procuratore=%s, 
                        apk_utilizzata=%s, uso_vpn=%s, quale_vpn=%s, citta=%s, 
                        data_iscrizione=%s, data_fine=%s, informazioni=%s 
                    WHERE id=%s
                """, (
                    dati.get("nominativo"), dati.get("tipo"), 
                    dati.get("user_id"), dati.get("password"),
                    float(dati.get("prezzo",0)), dati.get("cadenza"), dati.get("tipo_linea"), 
                    dati.get("server"), dati.get("reseller"),
                    dati.get("dispositivo"), dati.get("sistema_operativo"),
                    dati.get("buffett"), dati.get("metodo_pagamento"), dati.get("operatore_it"),
                    dati.get("cellulare"), dati.get("procuratore"),
                    dati.get("apk_utilizzata"), int(dati.get("uso_vpn",0)),
                    dati.get("quale_vpn"), dati.get("citta"),
                    dati.get("data_iscrizione"), dati.get("data_fine"),
                    dati.get("informazioni"), dati.get("id")
                ))

            # -------------------------------------------------
            # AZIONI SUI RINNOVI
            # -------------------------------------------------
            elif azione == "modifica_rinnovo":
                cur.execute("""
                    UPDATE rinnovi SET 
                        tipo = %s,
                        data_operazione = %s,
                        scadenza = %s,
                        note = %s,
                        num_credito_rich = %s,
                        num_credito_dato = %s,
                        num_credito_dare = %s,
                        data_credito_rinnovo_rich = %s,
                        data_credito_rinnovo_dato = %s
                    WHERE id = %s
                """, (
                    dati.get("tipo", "rinnovo"),
                    dati.get("data_operazione") or None,
                    dati.get("scadenza") or None,
                    dati.get("note", ""),
                    int(dati.get("num_credito_rich", 0) or 0),
                    int(dati.get("num_credito_dato", 0) or 0),
                    int(dati.get("num_credito_dare", 0) or 0),
                    dati.get("data_credito_rinnovo_rich") or None,
                    dati.get("data_credito_rinnovo_dato") or None,
                    dati.get("id")
                ))

            elif azione == "cancella_rinnovo":
                cur.execute("DELETE FROM rinnovi WHERE id = %s", (dati.get("id"),))

            elif azione == "salda_credito":
                rinnovo_id = dati.get("id")
                data_saldo = dati.get("data_credito_saldo")
                if rinnovo_id and data_saldo:
                    cur.execute("""
                        INSERT INTO saldo_rinnovi (rinnovo_id, data_credito_rinnovo_saldo)
                        VALUES (%s, %s)
