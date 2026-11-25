from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import AzionePayload

router = APIRouter()

@router.get("/api/nominativi")
def api_nominativi(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nominativo, tipo FROM nominativi ORDER BY nominativo")
            return cur.fetchall()
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
            return cur.fetchall()
    finally:
        conn.close()

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

            else:
                print(f"[ATTENZIONE] Azione non gestita: {azione}")
        
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
