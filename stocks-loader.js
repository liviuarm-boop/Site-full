/**
 * GhidBursa.ro — stocks-loader.js
 * Adaugă acest script pe TOATE paginile actiune-*.html și screener.html
 * 
 * Citește data/stocks.json din GitHub și actualizează valorile afișate.
 * 
 * ADAUGĂ ÎN <head> pe fiecare pagină de acțiune:
 *   <script src="stocks-loader.js?v=1" defer></script>
 * 
 * SAU inline la sfârșitul <body>:
 *   <script src="stocks-loader.js?v=1"></script>
 */

(function() {
  'use strict';

  var DATA_URL = 'https://raw.githubusercontent.com/liviuarm-boop/ghidbursa-data/main/data/stocks.json';
  var CACHE_KEY = 'ghidbursa_stocks_v1';
  var CACHE_TTL = 6 * 60 * 60 * 1000; // 6 ore în ms

  function loadData(callback) {
    // Verifică cache localStorage
    try {
      var cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        var obj = JSON.parse(cached);
        if (obj.ts && (Date.now() - obj.ts) < CACHE_TTL) {
          callback(obj.data);
          return;
        }
      }
    } catch(e) {}

    // Fetch fresh
    fetch(DATA_URL)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        try {
          localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: data }));
        } catch(e) {}
        callback(data);
      })
      .catch(function(e) {
        console.warn('GhidBursa stocks-loader: failed to load data', e);
      });
  }

  function formatPE(val) {
    if (!val) return null;
    return '~' + val.toFixed(1) + 'x';
  }

  function formatDiv(val) {
    if (!val) return null;
    return '~' + val.toFixed(1) + '%';
  }

  function formatCap(val) {
    if (!val) return null;
    return '~' + val.toFixed(1) + ' mld';
  }

  function formatYTD(val) {
    if (val === null || val === undefined) return null;
    var sign = val >= 0 ? '+' : '';
    return sign + val.toFixed(1) + '%';
  }

  function formatDivPerShare(val) {
    if (!val) return null;
    return '~' + val.toFixed(2) + ' RON';
  }

  function ytdColor(val) {
    if (val === null || val === undefined) return '';
    return val >= 0 ? '#00FF94' : '#FF4D6D';
  }

  function updateEl(id, value) {
    var el = document.getElementById(id);
    if (el && value !== null && value !== undefined) {
      el.textContent = value;
    }
  }

  function updateText(selector, value) {
    var el = document.querySelector(selector);
    if (el && value !== null && value !== undefined) {
      el.textContent = value;
    }
  }

  // Detectează ticker-ul paginii curente din URL
  function getPageTicker() {
    var path = window.location.pathname;
    var m = path.match(/actiune-([^.]+)\.html/);
    if (m) {
      return m[1].toUpperCase();
    }
    return null;
  }




  function updateFinancialProductSchema(stock) {
    // Find FinancialProduct schema script in head and inject real dividend data
    var scripts = document.querySelectorAll('script[type="application/ld+json"]');
    scripts.forEach(function(s) {
      try {
        var data = JSON.parse(s.textContent);
        if (data['@type'] !== 'FinancialProduct') return;
        if (!data.additionalProperty) return;

        // Only update if we have real data from Yahoo Finance
        if (stock.last_div_amount) {
          // Remove any existing dividend props first
          data.additionalProperty = data.additionalProperty.filter(function(p) {
            return !['Dividend (ultimul)', 'Randament dividend (ultimul)', 'Data ex-dividend (ultimul)'].includes(p.name);
          });
          // Add real data
          var year = stock.last_div_ex_date ? stock.last_div_ex_date.substring(0, 4) : '';
          data.additionalProperty.push(
            {"@type": "PropertyValue", "name": "Dividend (ultimul)", "value": stock.last_div_amount.toFixed(4) + " RON/acțiune"},
            {"@type": "PropertyValue", "name": "Data ex-dividend (ultimul)", "value": stock.last_div_ex_date || ""},
            {"@type": "PropertyValue", "name": "Randament dividend (ultimul)", "value": stock.last_div_yield ? stock.last_div_yield.toFixed(2) + "%" : ""}
          );
          s.textContent = JSON.stringify(data);
        }
      } catch(e) {}
    });
  }


  function updateScreenerItemListSchema() {
    // Only runs on screener page
    if (!window.location.pathname.includes('screener')) return;

    var SCHEMA_URL = 'https://raw.githubusercontent.com/liviuarm-boop/ghidbursa-data/main/data/screener_schema.json';

    fetch(SCHEMA_URL)
      .then(function(r) { return r.json(); })
      .then(function(schema) {
        // Find existing ItemList script tag and replace
        var scripts = document.querySelectorAll('script[type="application/ld+json"]');
        scripts.forEach(function(s) {
          try {
            var data = JSON.parse(s.textContent);
            if (data['@type'] === 'ItemList') {
              s.textContent = JSON.stringify(schema);
            }
          } catch(e) {}
        });
      })
      .catch(function() {}); // silent fail — static schema still in place as fallback
  }

  function applyToSimCards(allStocks) {
    document.querySelectorAll('.sim-card').forEach(function(card) {
      var href = card.getAttribute('href') || '';
      var m = href.match(/actiune-([^.]+)\.html/);
      if (!m) return;
      var ticker = m[1].toUpperCase();
      var stock = allStocks[ticker];
      if (!stock) return;

      var capEl = card.querySelector('[data-live="cap"]');
      if (capEl && stock.market_cap_bln !== null) {
        capEl.textContent = 'Cap. ' + stock.market_cap_bln.toFixed(1) + ' mld RON';
        capEl.classList.add('loaded');
      }
      var divEl = card.querySelector('[data-live="div"]');
      if (divEl && stock.div_yield !== null) {
        divEl.textContent = 'Div. ' + stock.div_yield.toFixed(1) + '%';
        divEl.classList.add('loaded');
      }
    });
  }

  function formatDate(iso) {
    if (!iso) return '—';
    var parts = iso.split('-');
    if (parts.length < 3) return iso;
    return parts[2] + '.' + parts[1] + '.' + parts[0];
  }

  function renderDivHistory(divHistory) {
    var container = document.getElementById('div-history-container');
    if (!container) return;
    var loading = document.getElementById('div-history-loading');
    if (loading) loading.style.display = 'none';
    if (!divHistory || divHistory.length === 0) {
      container.innerHTML = '<p style="font-size:13px;color:var(--muted);padding:10px 0">Nu există date de dividende disponibile pe Yahoo Finance pentru această acțiune.</p>';
      return;
    }
    var maxAmount = Math.max.apply(null, divHistory.map(function(d) { return d.amount || 0; }));
    var rows = divHistory.map(function(d) {
      var barWidth = maxAmount > 0 ? Math.round((d.amount / maxAmount) * 80) : 0;
      var yieldStr = d.yield_pct ? d.yield_pct.toFixed(2) + '%' : '—';
      return '<tr>' +
        '<td>' + formatDate(d.ex_date) + '</td>' +
        '<td class="dh-dps">' + (d.amount % 1 === 0 ? d.amount.toFixed(2) : d.amount.toFixed(4)) + ' RON</td>' +
        '<td class="dh-yield">' + yieldStr + '</td>' +
        '<td><span style="display:inline-block;height:5px;width:' + barWidth + 'px;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:3px;opacity:.7"></span></td>' +
        '</tr>';
    }).join('');
    container.innerHTML =
      '<table class="div-hist-table">' +
        '<thead><tr>' +
          '<th>Data ex-dividend</th>' +
          '<th>Dividend/acțiune</th>' +
          '<th>Randament la plată</th>' +
          '<th>Evoluție</th>' +
        '</tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table>' +
      '<div class="dh-note">Date reale Yahoo Finance · Randament calculat față de prețul din ziua ex-dividend · Actualizat zilnic · <a href="https://iris.bvb.ro" target="_blank" style="color:var(--accent)">Verifică pe IRIS BVB</a></div>';
  }

  function applyToActiunePage(stock) {
    if (!stock) return;

    var pe     = formatPE(stock.pe);
    var div    = formatDiv(stock.div_yield);
    var cap    = formatCap(stock.market_cap_bln);
    var ytd    = formatYTD(stock.ytd);
    var divps  = formatDivPerShare(stock.div_per_share);

    // Price hero metrics
    updateEl('metricDivHero', div);
    updateEl('metricPEHero', pe);

    // Sidebar indicators (m-row spans)
    document.querySelectorAll('.m-row').forEach(function(row) {
      var label = (row.querySelector('.m-label') || {}).textContent || '';
      var valEl = row.querySelector('.m-val');
      if (!valEl) return;

      if (label.includes('P/E')) {
        valEl.textContent = pe || valEl.textContent;
      } else if (label.includes('Dividend yield')) {
        valEl.textContent = div || valEl.textContent;
      } else if (label.includes('Dividend/ac')) {
        valEl.textContent = divps || valEl.textContent;
      } else if (label.includes('Capitalizare')) {
        var capFull = stock.market_cap_bln ? '~' + stock.market_cap_bln.toFixed(1) + ' mld RON' : null;
        valEl.textContent = capFull || valEl.textContent;
      }
    });

    // Render dividend history table
    renderDivHistory(stock.div_history || []);

    // Update FinancialProduct schema with real dividend data
    updateFinancialProductSchema(stock);

    // Live tag pe P/E și dividend
    var divTag = document.getElementById('divLiveTag');
    var peTag  = document.getElementById('peLiveTag');
    if (divTag) divTag.textContent = '▸ live';
    if (peTag)  peTag.textContent  = '▸ live';

    // Updated date
    var updEl = document.getElementById('stockDataUpdated');
    if (updEl) updEl.textContent = 'Actualizat: ' + stock.updated;
  }

  function applyToScreener(allStocks) {
    // Actualizează tabelul screener — data-div, data-pe, data-cap attributes
    document.querySelectorAll('.stock-row, .stock-card').forEach(function(row) {
      // Găsim ticker-ul din link
      var link = row.querySelector('a[href*="actiune-"]') || (row.tagName === 'A' ? row : null);
      if (!link) return;

      var href = link.getAttribute('href') || '';
      var m = href.match(/actiune-([^.]+)\.html/);
      if (!m) return;

      var ticker = m[1].toUpperCase();
      var stock = allStocks[ticker];
      if (!stock) return;

      // Actualizează data attributes pentru filtrare/sortare
      if (stock.div_yield !== null) row.setAttribute('data-div', stock.div_yield);
      if (stock.pe !== null)        row.setAttribute('data-pe', stock.pe);

      // Actualizează textul vizibil în celule
      row.querySelectorAll('td, .sc-metric-val').forEach(function(cell) {
        var cls = cell.className || '';
        var text = cell.textContent.trim();

        if (cls.includes('td-div') || (cell.previousElementSibling && (cell.previousElementSibling.textContent || '').includes('Div'))) {
          if (stock.div_yield !== null) cell.textContent = stock.div_yield.toFixed(1) + '%';
        }
        if (cls.includes('td-pe') || (cell.previousElementSibling && (cell.previousElementSibling.textContent || '').includes('P/E'))) {
          if (stock.pe !== null) cell.textContent = stock.pe.toFixed(1) + 'x';
        }
        if (cls.includes('td-cap')) {
          if (stock.market_cap_bln !== null) cell.textContent = stock.market_cap_bln.toFixed(1);
        }
      });

      // YTD în screener cards
      var ytdEls = row.querySelectorAll('.sc-metric-val');
      ytdEls.forEach(function(el) {
        var labelEl = el.previousElementSibling;
        if (labelEl && labelEl.textContent.includes('YTD')) {
          if (stock.ytd !== null) {
            el.textContent = formatYTD(stock.ytd);
            el.style.color = ytdColor(stock.ytd);
          }
        }
      });
    });

    // Actualizează și celulele YTD din tabel
    document.querySelectorAll('.stock-row').forEach(function(row) {
      var link = row.querySelector('.td-ticker a');
      if (!link) return;
      var ticker = (link.textContent || '').trim().toUpperCase();
      var stock = allStocks[ticker];
      if (!stock) return;

      var ytdCell = row.querySelector('.td-ytd, .col-ytd');
      if (ytdCell && stock.ytd !== null) {
        ytdCell.textContent = formatYTD(stock.ytd);
        ytdCell.style.color = ytdColor(stock.ytd);
      }

      var divCell = row.querySelector('.td-div');
      if (divCell && stock.div_yield !== null) {
        divCell.textContent = stock.div_yield.toFixed(1) + '%';
        row.setAttribute('data-div', stock.div_yield);
      }

      var peCell = row.querySelector('.td-pe');
      if (peCell && stock.pe !== null) {
        peCell.textContent = stock.pe.toFixed(1) + 'x';
        row.setAttribute('data-pe', stock.pe);
      }

      var capCell = row.querySelector('.td-cap');
      if (capCell && stock.market_cap_bln !== null) {
        capCell.textContent = stock.market_cap_bln.toFixed(1);
      }
    });
  }

  // ── INIT ──────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {
    var isScreener = window.location.pathname.includes('screener');
    var pageTicker = getPageTicker();

    if (!isScreener && !pageTicker) return; // pagina nu e relevantă

    loadData(function(data) {
      if (!data || !data.stocks) return;

      if (isScreener) {
        applyToScreener(data.stocks);
        updateScreenerItemListSchema();
        // Re-run filtrele dacă există, ca să țină cont de noile data-div/data-pe
        if (typeof window.applyFilters === 'function') {
          window.applyFilters();
        }
      } else if (pageTicker) {
        applyToActiunePage(data.stocks[pageTicker]);
        applyToSimCards(data.stocks);
      }
    });
  });

})();
