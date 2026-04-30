/* GhidBursa.ro — shared.js v4 FINAL
   Complete: hamburger, reveal, counters, page-entry, nav-scroll,
   chart rebuild, screener filters+sort, tab switching
*/
(function () {
  'use strict';

  /* ─── PAGE ENTRY FADE ─── */
  /* Handled purely by CSS animation now — no JS opacity manipulation
     that could leave the page invisible if scripts fail */
  function initPageEntry() {
    // no-op: removed JS opacity hack that caused blank pages on mobile
  }

  /* ─── NAV SCROLL ─── */
  function initNavScroll() {
    var nav = document.querySelector('nav');
    if (!nav) return;
    var onScroll = function () {
      if (window.scrollY > 30) {
        nav.style.background = 'rgba(8,11,15,.98)';
        nav.style.boxShadow = '0 2px 24px rgba(0,0,0,.45)';
      } else {
        nav.style.background = 'rgba(8,11,15,.92)';
        nav.style.boxShadow = 'none';
      }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ─── HAMBURGER ─── */
  function initHamburger() {
    var btn = document.getElementById('hamburgerBtn');
    var menu = document.getElementById('mobileNav');
    if (!btn || !menu) return;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = btn.classList.toggle('open');
      menu.classList.toggle('open', open);
    });
    document.addEventListener('click', function (e) {
      if (!menu.contains(e.target) && !btn.contains(e.target)) {
        btn.classList.remove('open');
        menu.classList.remove('open');
      }
    });
    menu.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        btn.classList.remove('open');
        menu.classList.remove('open');
      });
    });
  }

  /* ─── SCROLL REVEAL ─── */
  function initReveal() {
    var els = document.querySelectorAll('.reveal, .reveal-left, .reveal-right, .reveal-scale');
    if (!els.length) return;

    // Stagger grid children automatically
    document.querySelectorAll(
      '.grid-2, .grid-3, .grid-4, .guide-grid, .similar-grid, .sim-grid, .broker-cards, .stats-band-inner'
    ).forEach(function (grid) {
      var children = Array.from(grid.querySelectorAll('.reveal, .reveal-scale'));
      children.forEach(function (child, i) {
        if (!child.style.transitionDelay) {
          child.style.transitionDelay = (i * 0.07) + 's';
        }
      });
    });

    if (!('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.classList.add('visible'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -28px 0px' });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ─── COUNTERS ─── */
  function animateCounter(el) {
    var target = parseFloat(el.getAttribute('data-target')) || 0;
    var suffix = el.getAttribute('data-suffix') || '';
    var prefix = el.getAttribute('data-prefix') || '';
    var dec = parseInt(el.getAttribute('data-decimals')) || 0;
    var start = null, dur = 1800;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var ease = 1 - Math.pow(1 - p, 4);
      el.textContent = prefix + (ease * target).toFixed(dec) + suffix;
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = prefix + target.toFixed(dec) + suffix;
    }
    requestAnimationFrame(step);
  }
  function initCounters() {
    var els = document.querySelectorAll('.counter[data-target]');
    if (!els.length) return;
    if (!('IntersectionObserver' in window)) { els.forEach(animateCounter); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { animateCounter(e.target); io.unobserve(e.target); } });
    }, { threshold: 0.5 });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ─── LIVE DOTS ─── */
  function initLiveDots() {
    setTimeout(function () {
      document.querySelectorAll('.ph-dot, .live-dot, .nav-dot').forEach(function (d) {
        d.classList.add('live');
      });
    }, 1200);
  }

  /* ─── TAB SWITCHING ─── */
  window.switchTab = function (id, btn) {
    document.querySelectorAll('.tab-content').forEach(function (t) { t.classList.remove('active'); });
    document.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
    var target = document.getElementById('tab-' + id);
    if (target) {
      target.style.opacity = '0';
      target.style.transform = 'translateY(6px)';
      target.classList.add('active');
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          target.style.transition = 'opacity .28s ease, transform .28s ease';
          target.style.opacity = '1';
          target.style.transform = 'none';
        });
      });
    }
    if (btn) btn.classList.add('active');
  };

  /* ─── LEGAL TABS ─── */
  window.showLTab = function (id, btn) {
    document.querySelectorAll('.ltab-content').forEach(function (t) { t.classList.remove('active'); });
    document.querySelectorAll('.ltab').forEach(function (b) { b.classList.remove('active'); });
    var el = document.getElementById('ltab-' + id);
    if (el) el.classList.add('active');
    if (btn) btn.classList.add('active');
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', '#' + id);
    }
  };

  /* ─── CHART REBUILD (setChartInterval) ─── */
  window.setChartInterval = function (interval, btn) {
    document.querySelectorAll('.pbtn').forEach(function (b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    var wrap = document.getElementById('tvChartWrap');
    if (!wrap) return;
    var sym = wrap.getAttribute('data-symbol');
    if (!sym) return;
    var map = { D: '5', W: '60', M: '240', '3M': 'D', '12M': 'W', '60M': 'M' };
    var tvInt = map[interval] || 'D';
    wrap.style.transition = 'opacity .2s';
    wrap.style.opacity = '0';
    setTimeout(function () {
      wrap.innerHTML = '';
      var cont = document.createElement('div');
      cont.className = 'tradingview-widget-container';
      cont.style.cssText = 'height:100%;width:100%';
      var inner = document.createElement('div');
      inner.className = 'tradingview-widget-container__widget';
      inner.style.cssText = 'height:calc(100% - 32px);width:100%';
      cont.appendChild(inner);
      var credit = document.createElement('div');
      credit.style.cssText = 'font-size:11px;padding:5px 0;color:#6B7A8D';
      credit.innerHTML = '<a href="https://www.tradingview.com/symbols/' + sym.replace(':', '-') + '/" rel="noopener nofollow" target="_blank" style="color:#00D4FF;text-decoration:none">' + sym.split(':')[1] + ' chart</a> by TradingView';
      cont.appendChild(credit);
      var sc = document.createElement('script');
      sc.type = 'text/javascript';
      sc.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
      sc.async = true;
      sc.text = JSON.stringify({
        symbol: sym, interval: tvInt,
        timezone: 'Europe/Bucharest', theme: 'dark', style: '1', locale: 'ro',
        backgroundColor: '#111820', gridColor: 'rgba(30,42,56,0.8)',
        allow_symbol_change: false, calendar: false,
        hide_side_toolbar: true, hide_top_toolbar: false,
        hide_legend: false, hide_volume: false,
        save_image: false, autosize: true
      });
      cont.appendChild(sc);
      wrap.appendChild(cont);
      wrap.style.opacity = '1';
    }, 200);
  };

  /* ─── SCREENER ─── */
  window.applyFilters = function () {
    var q = ((document.getElementById('searchInput') || {}).value || '').toLowerCase();
    var sec = (document.getElementById('sectorFilter') || {}).value || '';
    var minDiv = parseFloat((document.getElementById('divFilter') || {}).value) || 0;
    var maxPE = parseFloat((document.getElementById('peFilter') || {}).value) || 999;
    var vis = 0;
    document.querySelectorAll('.stock-row').forEach(function (row) {
      var t = ((row.querySelector('.td-ticker a') || {}).textContent || '').toLowerCase();
      var n = ((row.querySelector('.td-name a') || {}).textContent || '').toLowerCase();
      var ok = (!q || t.includes(q) || n.includes(q))
        && (!sec || row.getAttribute('data-sector') === sec)
        && (parseFloat(row.getAttribute('data-div')) || 0) >= minDiv
        && (parseFloat(row.getAttribute('data-pe')) || 999) <= maxPE;
      row.classList.toggle('hidden', !ok);
      if (ok) vis++;
    });
    document.querySelectorAll('.stock-card').forEach(function (card) {
      var t = ((card.querySelector('.sc-ticker') || {}).textContent || '').toLowerCase();
      var n = ((card.querySelector('.sc-name') || {}).textContent || '').toLowerCase();
      var ok = (!q || t.includes(q) || n.includes(q))
        && (!sec || card.getAttribute('data-sector') === sec)
        && (parseFloat(card.getAttribute('data-div')) || 0) >= minDiv
        && (parseFloat(card.getAttribute('data-pe')) || 999) <= maxPE;
      card.style.display = ok ? '' : 'none';
    });
    var cEl = document.getElementById('countVisible');
    if (cEl) cEl.textContent = vis;
    var nr = document.getElementById('noResults');
    if (nr) nr.classList.toggle('visible', vis === 0);
    var vr = Array.from(document.querySelectorAll('.stock-row:not(.hidden)'));
    var divs = vr.map(function (r) { return parseFloat(r.getAttribute('data-div')); }).filter(Boolean);
    var pes = vr.map(function (r) { return parseFloat(r.getAttribute('data-pe')); }).filter(function (p) { return p > 0 && p < 100; });
    var dEl = document.getElementById('avgDiv'), pEl = document.getElementById('avgPE');
    if (dEl) dEl.textContent = divs.length ? (divs.reduce(function (a, b) { return a + b; }, 0) / divs.length).toFixed(1) + '%' : '—';
    if (pEl) pEl.textContent = pes.length ? (pes.reduce(function (a, b) { return a + b; }, 0) / pes.length).toFixed(1) + 'x' : '—';
  };
  window.resetFilters = function () {
    ['searchInput', 'sectorFilter', 'divFilter', 'peFilter'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = el.tagName === 'SELECT' ? el.options[0].value : '';
    });
    window.applyFilters();
  };
  var sortState = {};
  window.sortTable = function (key) {
    var dir = sortState[key] === 'asc' ? 'desc' : 'asc';
    sortState[key] = dir;
    var tbody = document.getElementById('screenerBody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('.stock-row'));
    rows.sort(function (a, b) {
      var va, vb;
      if (key === 'ticker' || key === 'name' || key === 'sector') {
        va = key === 'sector' ? a.getAttribute('data-sector') : ((a.querySelector('.' + (key === 'ticker' ? 'td-ticker' : 'td-name') + ' a') || {}).textContent || '');
        vb = key === 'sector' ? b.getAttribute('data-sector') : ((b.querySelector('.' + (key === 'ticker' ? 'td-ticker' : 'td-name') + ' a') || {}).textContent || '');
        return dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      if (key === 'div') { va = parseFloat(a.getAttribute('data-div')); vb = parseFloat(b.getAttribute('data-div')); }
      if (key === 'pe') { va = parseFloat(a.getAttribute('data-pe')); vb = parseFloat(b.getAttribute('data-pe')); }
      if (key === 'cap') { va = parseFloat((a.querySelectorAll('td')[4] || {}).textContent) || 0; vb = parseFloat((b.querySelectorAll('td')[4] || {}).textContent) || 0; }
      return isNaN(va) || isNaN(vb) ? 0 : dir === 'asc' ? va - vb : vb - va;
    });
    rows.forEach(function (r) { tbody.appendChild(r); });
  };

  /* ─── PROGRESS BAR ─── */
  function initProgressBar() {
    var bar = document.createElement('div');
    bar.className = 'progress-bar';
    document.body.appendChild(bar);
    window.addEventListener('scroll', function() {
      var scrollTop = window.scrollY;
      var docHeight = document.documentElement.scrollHeight - window.innerHeight;
      var pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      bar.style.width = Math.min(pct, 100) + '%';
    }, { passive: true });
  }

  /* ─── BACK TO TOP ─── */
  function initBackToTop() {
    var btn = document.createElement('a');
    btn.className = 'back-to-top';
    btn.href = '#';
    btn.innerHTML = '↑';
    btn.setAttribute('aria-label', 'Înapoi sus');
    document.body.appendChild(btn);
    window.addEventListener('scroll', function() {
      btn.classList.toggle('visible', window.scrollY > 400);
    }, { passive: true });
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  /* ─── ACTIVE NAV ─── */
  function initActiveNav() {
    document.querySelectorAll('.nav-links a').forEach(function(link) {
      if (link.href === window.location.href ||
          link.pathname === window.location.pathname) {
        link.classList.add('active');
      }
    });
  }

  /* ─── INIT ─── */
  document.addEventListener('DOMContentLoaded', function () {
    initHamburger();
    initReveal();
    initCounters();
    initNavScroll();
    initPageEntry();
    initLiveDots();
    initProgressBar();
    initBackToTop();
    initActiveNav();
    // Legal hash navigation
    if (window.location.hash) {
      var hash = window.location.hash.replace('#', '');
      var lbtn = document.querySelector('[onclick*="' + hash + '"]');
      if (lbtn) window.showLTab(hash, lbtn);
    }
  });
})();
