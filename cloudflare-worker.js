// BVB CORS Proxy — Cloudflare Worker (Service Worker format)
// Paste this in: Workers & Pages → bvb-proxy → Edit Code → Deploy
// Works immediately, no configuration needed.

const ALLOWED = [
  'stooq.com',
  'query1.finance.yahoo.com',
  'query2.finance.yahoo.com',
  'bvb-prices.ro',
  'raw.githubusercontent.com',
];

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};

function isAllowed(urlString) {
  try {
    const hostname = new URL(urlString).hostname;
    return ALLOWED.some(d => hostname === d || hostname.endsWith('.' + d));
  } catch (e) {
    return false;
  }
}

addEventListener('fetch', function(event) {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  // CORS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS });
  }

  if (request.method !== 'GET') {
    return new Response(JSON.stringify({ error: 'Only GET allowed' }), {
      status: 405,
      headers: Object.assign({}, CORS, { 'Content-Type': 'application/json' }),
    });
  }

  const targetUrl = new URL(request.url).searchParams.get('url');

  if (!targetUrl) {
    return new Response(JSON.stringify({
      error: 'Missing ?url= parameter',
      example: '?url=https://stooq.com/q/d/l/?s=bet.xb&i=d',
      allowed_domains: ALLOWED,
    }), {
      status: 400,
      headers: Object.assign({}, CORS, { 'Content-Type': 'application/json' }),
    });
  }

  if (!isAllowed(targetUrl)) {
    return new Response(JSON.stringify({
      error: 'Domain not whitelisted',
      requested: targetUrl,
      allowed: ALLOWED,
    }), {
      status: 403,
      headers: Object.assign({}, CORS, { 'Content-Type': 'application/json' }),
    });
  }

  try {
    const upstream = await fetch(targetUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; GhidBursa-Proxy/1.0)',
        'Accept': '*/*',
      },
    });

    const responseHeaders = new Headers(upstream.headers);
    Object.keys(CORS).forEach(function(k) { responseHeaders.set(k, CORS[k]); });
    responseHeaders.delete('Content-Security-Policy');
    responseHeaders.delete('X-Frame-Options');

    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 502,
      headers: Object.assign({}, CORS, { 'Content-Type': 'application/json' }),
    });
  }
}
