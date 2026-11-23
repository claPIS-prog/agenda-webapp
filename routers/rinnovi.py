@app.get("/api/scadenze")
def api_scadenze(request: Request):
    get_current_user(request)
    oggi = datetime.datetime.now().date()
    limite = oggi + timedelta(days=7)  # Mostra scadenze entro 7 giorni
    
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # Query che ESCLUDE i nominativi con rinnovi futuri già attivi
            # e mostra SOLO l'ultima scadenza valida per ogni contatto
            cur.execute("""
                SELECT r.id, r.scadenza, r.orario_scadenza, r.nominativo_id, n.nominativo 
                FROM rinnovi r 
                JOIN nominativi n ON n.id = r.nominativo_id 
                WHERE r.scadenza::date BETWEEN %s AND %s
                AND NOT EXISTS (
                    SELECT 1 FROM rinnovi r2 
                    WHERE r2.nominativo_id = r.nominativo_id 
                    AND r2.data_operazione > r.data_operazione
                    AND r2.scadenza::date > %s
                )
                ORDER BY r.scadenza ASC
            """, (oggi.isoformat(), limite.isoformat(), oggi.isoformat()))
            
            rows = cur.fetchall()
            out = []
            for r in rows:
                scad_date = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        scad_date = datetime.datetime.strptime(r["scadenza"], fmt).date()
                        break
                    except: pass
                
                if not scad_date: continue
                
                delta = (scad_date - oggi).days
                out.append({
                    "id": r["id"], 
                    "nominativo_id": r["nominativo_id"], 
                    "nominativo": r["nominativo"], 
                    "scadenza": r["scadenza"], 
                    "orario_scadenza": r.get("orario_scadenza",""), 
                    "scaduta": delta < 0, 
                    "giorni": delta
                })
            return out
    finally:
        conn.close()
