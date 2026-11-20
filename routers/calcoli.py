from datetime import datetime
from fastapi import APIRouter, Request
from auth import get_current_user
from database import db_conn
from models import CalcoloPayload

router = APIRouter()

@router.get("/api/calcoli/lista")
def api_calcoli_lista(nominativo: str = "", tipo: str = "", data_da: str = "", data_a: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """SELECT r.id, r.tipo, r.data_operazione, r.scadenza, r.orario_scadenza,
                r.importo_acconto, r.importo_saldo,
                r.num_credito_rich, r.num_credito_dato, r.num_credito_dare,
                r.val_singolo_nc_rich, r.val_nc_rich,
                r.note, n.nominativo
                FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id WHERE 1=1"""
            params = []
            if nominativo:
                query += " AND n.nominativo = %s"; params.append(nominativo)
            if tipo:
                query += " AND r.tipo = %s"; params.append(tipo)
            if data_da:
                query += " AND r.data_operazione >= %s"; params.append(data_da)
            if data_a:
                query += " AND r.data_operazione <= %s"; params.append(data_a)
            query += " ORDER BY r.data_operazione ASC"
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()

@router.get("/api/calcoli/calcola")
def api_calcoli_calcola(nominativo_da: str = "", nominativo_a: str = "", reseller_da: str = "", reseller_a: str = "", procuratore_da: str = "", procuratore_a: str = "", periodo_da: str = "", periodo_a: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query = """SELECT r.tipo, r.importo_acconto, r.importo_saldo,
                r.num_credito_rich, r.num_credito_dato, r.num_credito_dare,
                r.val_singolo_nc_rich, r.val_nc_rich, n.nominativo
                FROM rinnovi r JOIN nominativi n ON n.id = r.nominativo_id WHERE 1=1"""
            params = []
            if nominativo_da:
                query += " AND n.nominativo >= %s"; params.append(nominativo_da)
            if nominativo_a:
                query += " AND n.nominativo <= %s"; params.append(nominativo_a)
            if reseller_da:
                query += " AND n.reseller >= %s"; params.append(reseller_da)
            if reseller_a:
                query += " AND n.reseller <= %s"; params.append(reseller_a)
            if procuratore_da:
                query += " AND n.procuratore >= %s"; params.append(procuratore_da)
            if procuratore_a:
                query += " AND n.procuratore <= %s"; params.append(procuratore_a)
            if periodo_da:
                query += " AND r.data_operazione >= %s"; params.append(periodo_da)
            if periodo_a:
                query += " AND r.data_operazione <= %s"; params.append(periodo_a)
            cur.execute(query, params)
            rows = cur.fetchall()
            
            importo_nuovo = acconto_nuovo = acconto_saldo_nuovo = 0
            importo_rinnovo = acconto_rinnovo = acconto_saldo_rinnovo = 0
            importo_omaggio = acconto_omaggio = acconto_saldo_omaggio = 0
            crediti_rich = crediti_dati = crediti_dare = 0
            crediti_rich_omaggio = crediti_dati_omaggio = crediti_dare_omaggio = 0
            totale_nc = totale_nc_omaggio = 0
            
            for r in rows:
                val_acconto = float(r['importo_acconto'] or 0)
                val_saldo = float(r['importo_saldo'] or 0)
                val_tot = val_acconto + val_saldo
                rich = int(r['num_credito_rich'] or 0)
                dati = int(r['num_credito_dato'] or 0)
                dare = int(r['num_credito_dare'] or 0)
                nc = float(r['val_nc_rich'] or 0)
                
                if r['tipo'] == 'nuovo':
                    importo_nuovo += val_tot
                    acconto_nuovo += val_acconto
                    acconto_saldo_nuovo += val_saldo
                    crediti_rich += rich
                    crediti_dati += dati
                    crediti_dare += dare
                    totale_nc += nc
                elif r['tipo'] == 'omaggio':
                    importo_omaggio += val_tot
                    acconto_omaggio += val_acconto
                    acconto_saldo_omaggio += val_saldo
                    crediti_rich_omaggio += rich
                    crediti_dati_omaggio += dati
                    crediti_dare_omaggio += dare
                    totale_nc_omaggio += nc
                else:
                    importo_rinnovo += val_tot
                    acconto_rinnovo += val_acconto
                    acconto_saldo_rinnovo += val_saldo
            
            totale_acconti_nuovi = acconto_nuovo + acconto_saldo_nuovo
            totale_acconti_rinnovo = acconto_rinnovo + acconto_saldo_rinnovo
            totale_acconti_omaggio = acconto_omaggio + acconto_saldo_omaggio
            totale_generale = totale_acconti_nuovi + totale_acconti_rinnovo + totale_acconti_omaggio
            
            return {
                "importo_nuovo": importo_nuovo, "acconto_nuovo": acconto_nuovo, "acconto_saldo_nuovo": acconto_saldo_nuovo,
                "totale_acconti_nuovi": totale_acconti_nuovi,
                "importo_rinnovo": importo_rinnovo, "acconto_rinnovo": acconto_rinnovo, "acconto_saldo_rinnovo": acconto_saldo_rinnovo,
                "totale_acconti_rinnovo": totale_acconti_rinnovo,
                "importo_omaggio": importo_omaggio, "acconto_omaggio": acconto_omaggio, "acconto_saldo_omaggio": acconto_saldo_omaggio,
                "totale_acconti_omaggio": totale_acconti_omaggio,
                "crediti_rich": crediti_rich, "crediti_dati": crediti_dati, "crediti_dare": crediti_dare, "totale_nc": totale_nc,
                "crediti_rich_omaggio": crediti_rich_omaggio, "crediti_dati_omaggio": crediti_dati_omaggio, "crediti_dare_omaggio": crediti_dare_omaggio, "totale_nc_omaggio": totale_nc_omaggio,
                "totale_generale": totale_generale,
                "count_nuovi": sum(1 for r in rows if r['tipo'] == 'nuovo'),
                "count_rinnovi": sum(1 for r in rows if r['tipo'] == 'rinnovo'),
                "count_omaggi": sum(1 for r in rows if r['tipo'] == 'omaggio')
            }
    finally:
        conn.close()

@router.get("/api/calcoli")
def api_calcoli(request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM calcoli ORDER BY creato_il DESC")
            return cur.fetchall()
    finally:
        conn.close()

@router.post("/api/calcoli")
def api_calcoli_salva(payload: CalcoloPayload, request: Request):
    get_current_user(request)
    d = payload.dati
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO calcoli (
                nominativo_da, nominativo_a, reseller_da, reseller_a, procuratore_da, procuratore_a, periodo_da, periodo_a,
                importo_nuovo, acconto_nuovo, acconto_saldo_nuovo, totale_acconti_nuovi, info_saldo_nuovo, info_saldo_rinnovo_nuovo,
                importo_rinnovo, acconto_rinnovo, acconto_saldo_rinnovo, totale_acconti_rinnovo, info_saldo_rinnovo,
                importo_omaggio, acconto_omaggio, acconto_saldo_omaggio, totale_acconti_omaggio,
                crediti_rich, crediti_dati, crediti_dare, totale_nc,
                crediti_rich_omaggio, crediti_dati_omaggio, crediti_dare_omaggio, totale_nc_omaggio,
                totale_generale, note, creato_il
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (d.get("nominativo_da",""), d.get("nominativo_a",""), d.get("reseller_da",""), d.get("reseller_a",""),
                 d.get("procuratore_da",""), d.get("procuratore_a",""), d.get("periodo_da",""), d.get("periodo_a",""),
                 float(d.get("importo_nuovo",0)), float(d.get("acconto_nuovo",0)), float(d.get("acconto_saldo_nuovo",0)),
                 float(d.get("totale_acconti_nuovi",0)), d.get("info_saldo_nuovo",""), d.get("info_saldo_rinnovo_nuovo",""),
                 float(d.get("importo_rinnovo",0)), float(d.get("acconto_rinnovo",0)), float(d.get("acconto_saldo_rinnovo",0)),
                 float(d.get("totale_acconti_rinnovo",0)), d.get("info_saldo_rinnovo",""),
                 float(d.get("importo_omaggio",0)), float(d.get("acconto_omaggio",0)), float(d.get("acconto_saldo_omaggio",0)),
                 float(d.get("totale_acconti_omaggio",0)),
                 int(d.get("crediti_rich",0)), int(d.get("crediti_dati",0)), int(d.get("crediti_dare",0)), float(d.get("totale_nc",0)),
                 int(d.get("crediti_rich_omaggio",0)), int(d.get("crediti_dati_omaggio",0)), int(d.get("crediti_dare_omaggio",0)), float(d.get("totale_nc_omaggio",0)),
                 float(d.get("totale_generale",0)), d.get("note",""), datetime.now().isoformat()))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.delete("/api/calcoli/{id}")
def api_calcoli_cancella(id: int, request: Request):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM calcoli WHERE id = %s", (id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}

@router.get("/api/lista_crediti")
def api_lista_crediti(data_da: str = "", data_a: str = "", fornitore_da: str = "", fornitore_a: str = "", request: Request = None):
    get_current_user(request)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            query_acq = "SELECT SUM(quantita) as tot_qta, SUM(valore) as tot_val FROM crediti WHERE 1=1"
            params_acq = []
            if data_da:
                query_acq += " AND data_acquisto >= %s"; params_acq.append(data_da)
            if data_a:
                query_acq += " AND data_acquisto <= %s"; params_acq.append(data_a)
            if fornitore_da:
                query_acq += " AND fornitore >= %s"; params_acq.append(fornitore_da)
            if fornitore_a:
                query_acq += " AND fornitore <= %s"; params_acq.append(fornitore_a)
            cur.execute(query_acq, params_acq)
            acquisto = cur.fetchone()
            tot_acq_qta = int(acquisto['tot_qta'] or 0)
            tot_acq_val = float(acquisto['tot_val'] or 0)
            
            query_vend = """SELECT SUM(r.num_credito_dato) as tot_qta_vend, 
                SUM(r.num_credito_dato * r.val_singolo_nc_rich) as tot_val_vend
                FROM rinnovi r WHERE r.num_credito_dato > 0"""
            params_vend = []
            if data_da:
                query_vend += " AND r.data_operazione >= %s"; params_vend.append(data_da)
            if data_a:
                query_vend += " AND r.data_operazione <= %s"; params_vend.append(data_a)
            cur.execute(query_vend, params_vend)
            vendita = cur.fetchone()
            tot_vend_qta = int(vendita['tot_qta_vend'] or 0)
            tot_vend_val = float(vendita['tot_val_vend'] or 0)
            
            return {
                "tot_acq_qta": tot_acq_qta, "tot_acq_val": tot_acq_val,
                "tot_vend_qta": tot_vend_qta, "tot_vend_val": tot_vend_val,
                "saldo_qta": tot_acq_qta - tot_vend_qta,
                "saldo_val": tot_acq_val - tot_vend_val
            }
    finally:
        conn.close()
