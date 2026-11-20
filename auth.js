// auth.js - Fix automatico per autenticazione Telegram
// Versione 2.0 con debug e gestione errori

(function() {
    'use strict';
    
    console.log('🔧 auth.js: Inizio caricamento...');
    
    const originalFetch = window.fetch;
    
    window.fetch = function(url, options = {}) {
        const tg = window.Telegram?.WebApp;
        
        // Debug: mostra cosa stiamo per fare
        console.log('🔧 auth.js: Fetch chiamato per:', url);
        
        if (tg && tg.initData) {
            console.log('✅ auth.js: initData trovato, lunghezza:', tg.initData.length);
            
            // Assicurati che headers esista
            if (!options.headers) {
                options.headers = {};
            }
            
            // Se headers è un oggetto, aggiungi direttamente
            if (typeof options.headers === 'object' && !Array.isArray(options.headers)) {
                options.headers['X-Telegram-Init-Data'] = tg.initData;
                console.log('✅ auth.js: Header aggiunto (oggetto)');
            } 
            // Se headers è un'istanza di Headers, usa set()
            else if (options.headers instanceof Headers) {
                options.headers.set('X-Telegram-Init-Data', tg.initData);
                console.log('✅ auth.js: Header aggiunto (Headers)');
            }
            // Altrimenti, converti in oggetto
            else {
                const headersObj = {};
                if (options.headers && typeof options.headers.forEach === 'function') {
                    options.headers.forEach((value, key) => {
                        headersObj[key] = value;
                    });
                }
                headersObj['X-Telegram-Init-Data'] = tg.initData;
                options.headers = headersObj;
                console.log('✅ auth.js: Header aggiunto (convertito)');
            }
        } else {
            console.warn('⚠️ auth.js: initData NON trovato o Telegram non disponibile');
            if (!tg) console.warn('⚠️ auth.js: window.Telegram.WebApp non esiste');
            else if (!tg.initData) console.warn('⚠️ auth.js: tg.initData è vuoto');
        }
        
        return originalFetch.call(this, url, options);
    };
    
    console.log('✅ auth.js: Caricamento completato - autenticazione automatica attiva');
})();