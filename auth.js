// auth.js - Fix automatico per autenticazione Telegram
// Aggiunge automaticamente l'header X-Telegram-Init-Data a ogni richiesta fetch

(function() {
    const originalFetch = window.fetch;
    
    window.fetch = function(url, options = {}) {
        const tg = window.Telegram?.WebApp;
        
        // Se Telegram WebApp è disponibile e ha initData, aggiungi l'header
        if (tg && tg.initData) {
            options.headers = options.headers || {};
            options.headers['X-Telegram-Init-Data'] = tg.initData;
        }
        
        // Chiama il fetch originale con le opzioni modificate
        return originalFetch.call(this, url, options);
    };
    
    console.log('✅ auth.js caricato - autenticazione automatica attiva');
})();