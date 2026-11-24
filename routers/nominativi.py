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
            # Query COMPLETA che include TUTTI i campi necessari alla maschera Info
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
                # FIX CRITICO: Inclusi user_id e password nella query UPDATE
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
                    dati.get("user_id"), dati.get("password"),  # <-- CAMPI AGGIUNTI
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
        
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
