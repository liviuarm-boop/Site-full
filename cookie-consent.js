/* GhidBursa.ro — Cookie Consent + GA4 Loader
   Înlocuiește G-XXXXXXXXXX cu Measurement ID-ul tău din Google Analytics 4
   Settings → Data Streams → Web → Measurement ID */

(function(){
  var GA4_ID = 'G-NLVTK68EHY';

  var CONSENT_KEY = 'gb_cookie_consent';

  function getConsent(){ return localStorage.getItem(CONSENT_KEY); }
  function setConsent(val){ localStorage.setItem(CONSENT_KEY, val); }

  // Load GA4
  function loadGA4(){
    if(document.getElementById('ga4-script')) return;
    var s = document.createElement('script');
    s.id = 'ga4-script';
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA4_ID;
    s.async = true;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    function gtag(){ dataLayer.push(arguments); }
    window.gtag = gtag;
    gtag('js', new Date());
    gtag('config', GA4_ID, {
      anonymize_ip: true,
      cookie_flags: 'SameSite=None;Secure'
    });
    // Track CTA clicks
    document.addEventListener('click', function(e){
      var a = e.target.closest('a[href*="xtb"],[href*="trading212"],[href*="etoro"],[href*="plus500"],[href*="interactivebrokers"]');
      if(a){
        gtag('event','broker_cta_click',{
          broker: a.href.match(/xtb|trading212|etoro|plus500|interactivebrokers/i)?.[0] || 'unknown',
          page: window.location.pathname
        });
      }
      var btn = e.target.closest('.btn-main,.btn-primary,.nav-cta');
      if(btn && !a){
        gtag('event','cta_click',{
          label: btn.textContent.trim().substring(0,50),
          page: window.location.pathname
        });
      }
    });
  }

  // Build banner HTML
  function showBanner(){
    if(document.getElementById('gb-cookie-banner')) return;
    var banner = document.createElement('div');
    banner.id = 'gb-cookie-banner';
    banner.setAttribute('role','dialog');
    banner.setAttribute('aria-label','Consimțământ cookie-uri');
    banner.innerHTML = '<div class="gb-cookie-inner">'
      + '<div class="gb-cookie-text">'
      + '<strong>Folosim cookie-uri</strong>'
      + '<p>GhidBursa.ro folosește Google Analytics pentru a înțelege cum este utilizat site-ul. Nu stocăm date personale fără consimțământul tău.</p>'
      + '</div>'
      + '<div class="gb-cookie-btns">'
      + '<button id="gb-accept" class="gb-btn-accept">Accept</button>'
      + '<button id="gb-decline" class="gb-btn-decline">Refuz</button>'
      + '<a href="legal.html#gdpr" class="gb-cookie-link">Politica de confidențialitate</a>'
      + '</div>'
      + '</div>';
    document.body.appendChild(banner);

    document.getElementById('gb-accept').addEventListener('click', function(){
      setConsent('accepted');
      hideBanner();
      loadGA4();
    });
    document.getElementById('gb-decline').addEventListener('click', function(){
      setConsent('declined');
      hideBanner();
    });
  }

  function hideBanner(){
    var b = document.getElementById('gb-cookie-banner');
    if(b){ b.classList.add('gb-hide'); setTimeout(function(){ b.remove(); }, 300); }
  }

  // Init
  var consent = getConsent();
  if(consent === 'accepted'){
    loadGA4();
  } else if(!consent){
    // Show banner after short delay so it doesn't block above-fold render
    setTimeout(showBanner, 1500);
  }
})();
