            elif azione == "modifica":
                cur.execute("""
                    UPDATE nominativi SET 
                        nominativo=%s, tipo=%s, prezzo=%s, cadenza=%s, 
                        user_id=%s, password=%s,  <-- QUESTI DUE CAMPI SONO FONDAMENTALI
                        tipo_linea=%s, operatore_it=%s, server=%s, reseller=%s, 
                        dispositivo=%s, sistema_operativo=%s, buffett=%s, 
                        metodo_pagamento=%s, cellulare=%s, procuratore=%s, 
                        apk_utilizzata=%s, uso_vpn=%s, quale_vpn=%s, citta=%s, 
                        data_iscrizione=%s, data_fine=%s, informazioni=%s 
                    WHERE id=%s
                """, (
                    dati.get("nominativo"), dati.get("tipo"), float(dati.get("prezzo",0)), dati.get("cadenza"),
                    dati.get("user_id"), dati.get("password"),  <-- E ANCHE QUI NEL TUPLA DEI VALORI
                    dati.get("tipo_linea"), dati.get("operatore_it"), dati.get("server"), dati.get("reseller"),
                    dati.get("dispositivo"), dati.get("sistema_operativo"),
                    dati.get("buffett"), dati.get("metodo_pagamento"),
                    dati.get("cellulare"), dati.get("procuratore"),
                    dati.get("apk_utilizzata"), int(dati.get("uso_vpn",0)),
                    dati.get("quale_vpn"), dati.get("citta"),
                    dati.get("data_iscrizione"), dati.get("data_fine"),
                    dati.get("informazioni"), dati.get("id")
                ))
