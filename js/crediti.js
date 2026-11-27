const tg = window.Telegram.WebApp;
tg.expand();

const MODALITA_PAGAMENTO_DEFAULT = [
    "Contanti",
    "Bonifico Bancario",
    "Carta di Credito / Debito",
    "PayPal",
    "Ricarica / Postepay",
    "Crypto",
    "Altro"
];

let movimentiCrediti = [];

function tornaMenu() {
    window.history.back();
}

function impostaDateDefault() {
    const oggi = new Date().toISOString().split('T')[0];
    if (!document.getElementById('saldo-iniziale-data').value) {
        document.getElementById('saldo-iniziale-data').value = oggi;
    }
    if (!document.getElementById('acquisto-data').value) {
        document.getElementById('acquisto-data').value = oggi;
    }
}

function aggiornaValoreTotaleAcquisto() {
    const qta = parseFloat(document.getElementById('acquisto-qta').value) || 0;
    const unit = parseFloat(document.getElementById('acquisto-prezzo-unit').value) || 0;
    const tot = qta * unit;
    document.getElementById('acquisto-valore-tot').value = tot.toFixed(2);
}

async function caricaFornitori() {
    const sel = document.getElementById('acquisto-fornitore');
    try {
        const res = await fetch('/api/resellers?nocache=' + Date.now());
        if (res.ok) {
            const rows = await res.json();
            const nomi = [...new Set(
                (Array.isArray(rows) ? rows : [])
                    .map(r => (r.nominativo || r.nome || '').trim())
                    .filter(Boolean)
            )];
            sel.innerHTML = '<option value="">-- Seleziona Fornitore --</option>';
            nomi.forEach(nome => {
                const opt = document.createElement('option');
                opt.value = nome;
                opt.textContent = nome;
                sel.appendChild(opt);
            });
        }
    } catch (e) {}
}

async function caricaModalitaPagamento() {
    const sel = document.getElementById('acquisto-modalita');
    let opzioni = [];
    try {
        const res = await fetch('/api/metodi_pagamento?nocache=' + Date.now());
        if (res.ok) {
            const rows = await res.json();
            opzioni = [...new Set(
                (Array.isArray(rows) ? rows : [])
                    .map(r => (r.nome || r.modalita_pagamento || r.nominativo || '').trim())
                    .filter(Boolean)
            )];
        }
    } catch (e) {}

    if (opzioni.length === 0) {
        opzioni = [...MODALITA_PAGAMENTO_DEFAULT];
    }

    const valoreAttuale = sel.value;
    sel.innerHTML = '<option value="">-- Seleziona Modalità di Pagamento --</option>';
    opzioni.forEach(nome => {
        const opt = document.createElement('option');
        opt.value = nome;
        opt.textContent = nome;
        sel.appendChild(opt);
    });

    if (valoreAttuale && opzioni.includes(valoreAttuale)) {
        sel.value = valoreAttuale;
    } else if (opzioni.length > 0) {
        sel.value = opzioni[0];
    }
}

async function salvaSaldoIniziale() {
    const qta = parseInt(document.getElementById('saldo-iniziale-qta').value, 10) || 0;
    const dataSaldo = document.getElementById('saldo-iniziale-data').value || new Date().toISOString().split('T')[0];
    const info = document.getElementById('saldo-iniziale-info').value.trim();

    const btn = document.getElementById('btn-salva-saldo-iniziale');
    btn.disabled = true;
    try {
        const res = await fetch('/api/saldo_iniziale', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dati: {
                    quantita: qta,
                    data_acquisto: dataSaldo,
                    fornitore: 'Saldo Iniziale',
                    modalita_pagamento: '-',
                    valore: 0,
                    note: info || 'Saldo iniziale'
                }
            })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || String(res.status));
        }
        mostraSuccesso('✅ Saldo iniziale salvato!');
        document.getElementById('saldo-iniziale-info').value = '';
        await caricaMovimentiCrediti();
        setTimeout(nascondiMessaggi, 3000);
    } catch (e) {
        mostraErrore('❌ HTTP ' + e.message);
    } finally {
        btn.disabled = false;
    }
}

async function salvaNuovoAcquisto() {
    const fornitore = document.getElementById('acquisto-fornitore').value.trim();
    const modalitaPagamento = document.getElementById('acquisto-modalita').value.trim();
    const dataAcquisto = document.getElementById('acquisto-data').value || new Date().toISOString().split('T')[0];
    const quantita = parseInt(document.getElementById('acquisto-qta').value, 10) || 0;
    const prezzoUnitario = parseFloat(document.getElementById('acquisto-prezzo-unit').value) || 0;
    const valoreTotale = parseFloat((quantita * prezzoUnitario).toFixed(2));
    const note = document.getElementById('acquisto-note').value.trim();

    if (!modalitaPagamento) {
        mostraErrore('Seleziona una modalità di pagamento.');
        return;
    }
    if (quantita <= 0) {
        mostraErrore('Inserisci una quantità crediti valida.');
        return;
    }

    const btn = document.getElementById('btn-salva-acquisto');
    btn.disabled = true;
    btn.textContent = '⏳ Salvataggio...';

    try {
        const res = await fetch('/api/crediti', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dati: {
                    fornitore,
                    modalita_pagamento: modalitaPagamento,
                    data_acquisto: dataAcquisto,
                    quantita,
                    prezzo_unitario: prezzoUnitario,
                    valore: valoreTotale,
                    note
                }
            })
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || String(res.status));
        }
        mostraSuccesso('✅ Nuovo acquisto credito salvato!');
        document.getElementById('acquisto-note').value = '';
        await caricaMovimentiCrediti();
        setTimeout(nascondiMessaggi, 3000);
    } catch (e) {
        mostraErrore('❌ HTTP ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Salva Nuovo Acquisto';
    }
}

async function caricaMovimentiCrediti() {
    try {
        const res = await fetch('/api/crediti?nocache=' + Date.now());
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const rows = await res.json();
        movimentiCrediti = Array.isArray(rows) ? rows : [];
        document.getElementById('total-badge').textContent = 'Totale: ' + movimentiCrediti.length;
        renderMovimentiCrediti(movimentiCrediti);
    } catch (e) {
        document.getElementById('listaCreditiContainer').innerHTML = `<div class="empty-state">Errore caricamento: ${e.message}</div>`;
    }
}

function renderMovimentiCrediti(items) {
    const container = document.getElementById('listaCreditiContainer');
    container.innerHTML = '';
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state">Nessun movimento crediti registrato.</div>';
        return;
    }
    items.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'list-item';
        const fornitore = item.fornitore || '-';
        const modPag = item.modalita_pagamento || '-';
        const dataAcq = item.data_acquisto || '-';
        const qta = Number(item.quantita || 0);
        const val = Number(item.valore || 0).toFixed(2);
        const note = item.note ? ` | Note: ${item.note}` : '';

        div.innerHTML = `
            <div class="num">${idx + 1}</div>
            <div class="info">
                <div class="title">${fornitore} — ${qta} crediti (€ ${val})</div>
                <div class="meta">
                    Data: <strong>${dataAcq}</strong> | Pagamento: <strong>${modPag}</strong>${note}
                </div>
            </div>
            <div class="actions">
                <button type="button" class="btn-action btn-info" onclick="event.stopPropagation(); apriInfoCredito(${item.id})" title="Dettaglio">ℹ️</button>
                <button type="button" class="btn-action btn-del" onclick="event.stopPropagation(); eliminaMovimento(${item.id})" title="Elimina">🗑️</button>
            </div>
        `;
        container.appendChild(div);
    });
}

function apriInfoCredito(id) {
    const item = movimentiCrediti.find(m => Number(m.id) === Number(id));
    if (!item) return;

    const v = (val) => (val !== undefined && val !== null && String(val).trim() !== '') ? val : '-';
    const qta = Number(item.quantita || 0);
    const valTot = Number(item.valore || 0);
    const prezzoUnit = qta > 0 ? (valTot / qta).toFixed(2) : '0.00';

    let html = '<div class="info-grid">';
    html += '<div class="info-section-title">Generale</div>';
    html += `<div class="info-row"><div class="info-label">ID Transazione:</div><div class="info-value">#${v(item.id)}</div></div>`;
    html += `<div class="info-row"><div class="info-label">Fornitore:</div><div class="info-value">${v(item.fornitore)}</div></div>`;
    html += `<div class="info-row"><div class="info-label">Data Acquisto:</div><div class="info-value">${v(item.data_acquisto)}</div></div>`;
    html += `<div class="info-row"><div class="info-label">Modalità Pagamento:</div><div class="info-value">${v(item.modalita_pagamento)}</div></div>`;

    html += '<div class="info-section-title">Importi & Crediti</div>';
    html += `<div class="info-row"><div class="info-label">Quantità Crediti:</div><div class="info-value">${qta}</div></div>`;
    html += `<div class="info-row"><div class="info-label">Prezzo Unitario:</div><div class="info-value">€ ${prezzoUnit}</div></div>`;
    html += `<div class="info-row"><div class="info-label">Valore Totale:</div><div class="info-value">€ ${valTot.toFixed(2)}</div></div>`;

    html += '<div class="info-section-title">Note / Informazioni</div>';
    html += `<div class="info-row" style="flex-direction:column;"><div class="info-label" style="width:100%;margin-bottom:4px;">Note:</div><div class="info-value" style="background:#f9f9f9;padding:8px;border-radius:4px;white-space:pre-line;">${v(item.note)}</div></div>`;
    html += '</div>';

    document.getElementById('infoContent').innerHTML = html;
    document.getElementById('infoModal').classList.add('active');
}

function chiudiInfoCredito() {
    document.getElementById('infoModal').classList.remove('active');
}

function chiudiInfoOverlay(event) {
    if (event.target && event.target.id === 'infoModal') {
        chiudiInfoCredito();
    }
}

async function eseguiEliminazioneMovimento(id) {
    const res = await fetch(`/api/crediti/${encodeURIComponent(id)}?nocache=${Date.now()}`, {
        method: 'DELETE'
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || String(res.status));
    }
    mostraSuccesso('✅ Movimento crediti eliminato!');
    await caricaMovimentiCrediti();
    setTimeout(nascondiMessaggi, 2500);
}

function eliminaMovimento(id) {
    if (tg && typeof tg.showConfirm === 'function') {
        try {
            tg.showConfirm('Eliminare questo movimento crediti?', async (ok) => {
                if (!ok) return;
                try {
                    await eseguiEliminazioneMovimento(id);
                } catch (e) {
                    mostraErrore('❌ HTTP ' + e.message);
                }
            });
            return;
        } catch (e) {}
    }
    if (confirm('Eliminare questo movimento crediti?')) {
        eseguiEliminazioneMovimento(id).catch((e) => mostraErrore('❌ HTTP ' + e.message));
    }
}

function mostraErrore(msg) {
    const el = document.getElementById('error-msg');
    el.textContent = msg;
    el.style.display = 'block';
    document.getElementById('success-msg').style.display = 'none';
}

function mostraSuccesso(msg) {
    const el = document.getElementById('success-msg');
    el.textContent = msg;
    el.style.display = 'block';
    document.getElementById('error-msg').style.display = 'none';
}

function nascondiMessaggi() {
    document.getElementById('error-msg').style.display = 'none';
    document.getElementById('success-msg').style.display = 'none';
}

(async function initCrediti() {
    impostaDateDefault();
    aggiornaValoreTotaleAcquisto();
    await Promise.all([
        caricaFornitori(),
        caricaModalitaPagamento(),
        caricaMovimentiCrediti()
    ]);
})();