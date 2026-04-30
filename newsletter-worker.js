/**
 * GhidBursa.ro — Newsletter Worker v3 (ES Module format — necesar pentru D1)
 * Paste în: Workers & Pages → worker → Edit Code → Deploy
 *
 * SETUP D1 (o singură dată, în D1 Console):
 *
 *   -- Dacă tabela NU există:
 *   CREATE TABLE subscribers (
 *     id INTEGER PRIMARY KEY AUTOINCREMENT,
 *     email TEXT UNIQUE NOT NULL,
 *     subscribed_at TEXT NOT NULL,
 *     ip TEXT,
 *     active INTEGER DEFAULT 1,
 *     unsubscribe_token TEXT
 *   );
 *
 *   -- Dacă tabela EXISTĂ deja (fără coloana token):
 *   ALTER TABLE subscribers ADD COLUMN unsubscribe_token TEXT;
 *
 * BINDINGS (Worker → Settings → Bindings):
 *   D1 Database → Variable name: DB → Database: ghidbursa-newsletter
 *
 * ENV VARS (Worker → Settings → Variables):
 *   EXPORT_SECRET = o_parola_secreta
 */

const CORS = {
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
  'Access-Control-Allow-Origin': '*',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS },
  });
}

function isValidEmail(e) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(e);
}

function generateToken() {
  const arr = new Uint8Array(16);
  crypto.getRandomValues(arr);
  return Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
}

function unsubscribePage(success, email) {
  const title = success ? 'Te-ai dezabonat cu succes' : 'Link invalid';
  const icon  = success ? '✓' : '✗';
  const color = success ? '#00FF94' : '#FF4D6D';
  const msg   = success
    ? `Adresa <strong>${email}</strong> a fost eliminată din newsletter-ul GhidBursa.ro.`
    : 'Link-ul de dezabonare este invalid sau a fost deja folosit.';

  const html = `<!DOCTYPE html><html lang="ro"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="robots" content="noindex"/>
<title>${title} — GhidBursa.ro</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&family=Plus+Jakarta+Sans:wght@700&display=swap"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#080B0F;color:#E8EDF2;font-family:"DM Sans",sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.card{background:#111820;border:1px solid #1E2A38;border-radius:20px;padding:48px 40px;max-width:480px;width:100%;text-align:center}
.icon{width:64px;height:64px;border-radius:50%;border:2px solid ${color};display:flex;align-items:center;justify-content:center;font-size:28px;color:${color};margin:0 auto 24px}
h1{font-family:"Plus Jakarta Sans",sans-serif;font-size:22px;font-weight:700;margin-bottom:14px}
p{font-size:14px;color:#6B7A8D;line-height:1.7;margin-bottom:28px}
a.btn{display:inline-block;background:#00D4FF;color:#080B0F;font-family:"Plus Jakarta Sans",sans-serif;font-weight:700;font-size:14px;padding:12px 28px;border-radius:8px;text-decoration:none}
.foot{font-size:11px;color:#6B7A8D;margin-top:20px;opacity:.5}
</style></head><body>
<div class="card">
<div class="icon">${icon}</div>
<h1>${title}</h1>
<p>${msg}</p>
<a class="btn" href="https://www.ghidbursa.ro/">Înapoi pe GhidBursa.ro</a>
<p class="foot">GhidBursa.ro — Ghid independent pentru investitori BVB</p>
</div></body></html>`;

  return new Response(html, {
    status: success ? 200 : 400,
    headers: { 'Content-Type': 'text/html;charset=UTF-8' },
  });
}

// ── ES MODULE FORMAT ─────────────────────────────────────────
export default {
  async fetch(request, env) {

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    const url = new URL(request.url);
    const DB  = env.DB;
    const EXPORT_SECRET = env.EXPORT_SECRET;

    // ── POST /subscribe ───────────────────────────────────
    if (url.pathname === '/subscribe' && request.method === 'POST') {
      let body;
      try { body = await request.json(); } catch {
        return json({ ok: false, error: 'Invalid JSON' }, 400);
      }

      const email = (body.email || '').trim().toLowerCase();
      if (!email || !isValidEmail(email)) {
        return json({ ok: false, error: 'Adresă de email invalidă.' }, 400);
      }

      const ip    = request.headers.get('CF-Connecting-IP') || null;
      const now   = new Date().toISOString();
      const token = generateToken();

      try {
        await DB.prepare(
          'INSERT INTO subscribers (email, subscribed_at, ip, unsubscribe_token) VALUES (?, ?, ?, ?)'
        ).bind(email, now, ip, token).run();

        return json({
          ok: true,
          message: 'Abonat cu succes!',
          unsubscribe_url: `https://newsletter.ghidbursa.ro/unsubscribe?token=${token}`,
        });

      } catch (err) {
        if (err.message?.includes('UNIQUE')) {
          // Email existent — returnăm token-ul sau generăm unul nou
          try {
            let row = await DB.prepare(
              'SELECT unsubscribe_token, active FROM subscribers WHERE email = ?'
            ).bind(email).first();

            let existingToken = row?.unsubscribe_token;

            if (!existingToken) {
              existingToken = generateToken();
              await DB.prepare(
                'UPDATE subscribers SET unsubscribe_token = ? WHERE email = ?'
              ).bind(existingToken, email).run();
            }

            if (row?.active === 0) {
              await DB.prepare(
                'UPDATE subscribers SET active = 1 WHERE email = ?'
              ).bind(email).run();
              return json({
                ok: true,
                message: 'Te-ai re-abonat cu succes!',
                unsubscribe_url: `https://newsletter.ghidbursa.ro/unsubscribe?token=${existingToken}`,
              });
            }

            return json({
              ok: true,
              message: 'Ești deja abonat.',
              unsubscribe_url: `https://newsletter.ghidbursa.ro/unsubscribe?token=${existingToken}`,
            });
          } catch {
            return json({ ok: true, message: 'Ești deja abonat.' });
          }
        }
        return json({ ok: false, error: 'Eroare internă. Încearcă din nou.' }, 500);
      }
    }

    // ── POST /unsubscribe-by-email ────────────────────────
    if (url.pathname === '/unsubscribe-by-email' && request.method === 'POST') {
      let body;
      try { body = await request.json(); } catch {
        return json({ ok: false, error: 'Invalid JSON' }, 400);
      }

      const email = (body.email || '').trim().toLowerCase();
      if (!email || !isValidEmail(email)) {
        return json({ ok: false, error: 'Adresă de email invalidă.' }, 400);
      }

      try {
        const row = await DB.prepare(
          'SELECT id, active FROM subscribers WHERE email = ?'
        ).bind(email).first();

        if (!row || row.active === 0) {
          return json({ ok: true, message: 'Dacă acest email era abonat, a fost dezabonat.' });
        }

        await DB.prepare(
          'UPDATE subscribers SET active = 0 WHERE email = ?'
        ).bind(email).run();

        return json({ ok: true, message: 'Te-ai dezabonat cu succes.' });

      } catch (err) {
        return json({ ok: false, error: 'Eroare internă. Încearcă din nou.' }, 500);
      }
    }

    // ── GET /unsubscribe?token= ───────────────────────────
    if (url.pathname === '/unsubscribe' && request.method === 'GET') {
      const token = url.searchParams.get('token');

      if (!token || token.length < 16) {
        return unsubscribePage(false, '');
      }

      try {
        const row = await DB.prepare(
          'SELECT email, active FROM subscribers WHERE unsubscribe_token = ?'
        ).bind(token).first();

        if (!row) return unsubscribePage(false, '');

        if (row.active === 0) return unsubscribePage(true, row.email);

        await DB.prepare(
          'UPDATE subscribers SET active = 0 WHERE unsubscribe_token = ?'
        ).bind(token).run();

        return unsubscribePage(true, row.email);

      } catch {
        return unsubscribePage(false, '');
      }
    }

    // ── GET /count ────────────────────────────────────────
    if (url.pathname === '/count' && request.method === 'GET') {
      try {
        const row = await DB.prepare(
          'SELECT COUNT(*) as n FROM subscribers WHERE active=1'
        ).first();
        return json({ count: row.n });
      } catch {
        return json({ count: 0 });
      }
    }

    // ── GET /export?secret= ───────────────────────────────
    if (url.pathname === '/export' && request.method === 'GET') {
      if (!EXPORT_SECRET || url.searchParams.get('secret') !== EXPORT_SECRET) {
        return new Response('Unauthorized', { status: 401 });
      }
      try {
        const result = await DB.prepare(
          'SELECT email, subscribed_at, unsubscribe_token FROM subscribers WHERE active=1 ORDER BY subscribed_at DESC'
        ).all();
        const csv = 'email,subscribed_at,unsubscribe_url\n' +
          result.results.map(r => {
            const u = r.unsubscribe_token
              ? `https://newsletter.ghidbursa.ro/unsubscribe?token=${r.unsubscribe_token}`
              : '';
            return `${r.email},${r.subscribed_at},${u}`;
          }).join('\n');
        return new Response(csv, {
          headers: {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename="subscribers.csv"',
          },
        });
      } catch (err) {
        return new Response('Error: ' + err.message, { status: 500 });
      }
    }

    return new Response('Not found', { status: 404 });
  },
};
