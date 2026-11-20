// auth.js v4.0 - Fix autenticazione Telegram con fallback URL hash
// Risolve il problema di initData vuoto su Telegram Web

(function() {
    var originalFetch = window.fetch;
    
    function getInitData() {
        // Metodo 1: da window.Telegram.WebApp.initData
        try {
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
                return window.Telegram.WebApp.initData;
            }
        } catch (e) {}
        
        // Metodo 2: da window.Telegram.WebApp.initDataRaw
        try {
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataRaw) {
                return window.Telegram.WebApp.initDataRaw;
            }
        } catch (e) {}
        
        // Metodo 3: FALLBACK - leggi dall'URL hash (funziona sempre su Telegram Web)
        try {
            var hash = window.location.hash || '';
            if (hash.indexOf('tgWebAppData=') !== -1) {
                var hashContent = hash.substring(1); // rimuovi il #
                var params = new URLSearchParams(hashContent);
                var initData = params.get('tgWebAppData');
                if (initData && initData.length > 10) {
                    return decodeURIComponent(initData);
                }
            }
        } catch (e) {}
        
        // Metodo 4: cerca initData in query string (caso raro)
        try {
            var search = window.location.search || '';
            if (search.indexOf('initData=') !== -1) {
                var params = new URLSearchParams(search.substring(1));
                var initData = params.get('initData');
                if (initData) return decodeURIComponent(initData);
            }
        } catch (e) {}
        
        return null;
    }
    
    window.fetch = function(url, options) {
        options = options || {};
        var initData = getInitData();
        
        if (initData) {
            // Gestisci headers come oggetto
            if (!options.headers || (typeof options.headers === 'object' && !(options.headers instanceof Headers))) {
                options.headers = options.headers || {};
                options.headers['X-Telegram-Init-Data'] = initData;
            }
            // Gestisci headers come istanza Headers
            else if (options.headers instanceof Headers) {
                if (!options.headers.has('X-Telegram-Init-Data')) {
                    options.headers.append('X-Telegram-Init-Data', initData);
                }
            }
        }
        
        return originalFetch.call(this, url, options);
    };
    
    // Rendi disponibile la funzione getInitData per altri script
    window.getTelegramInitData = getInitData;
    
    console.log('✅ auth.js v4.0 caricato con fallback URL hash');
})();