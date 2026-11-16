// Pulse Cloudflare Worker proxy.
//
// Use this only when you want to keep the Workers URL while the real Pulse
// server runs somewhere else (for example behind a Cloudflare Tunnel).
// Set PULSE_ORIGIN to the public origin, e.g.
//   https://fog-innovation-epa-tail.trycloudflare.com
//
// The Worker forwards every request, including /api/*, so the front end and
// backend share the workers.dev origin. It does not try to run the Python app
// inside a Worker.

export default {
  async fetch(request, env) {
    const originValue = env.PULSE_ORIGIN;
    if (!originValue) {
      return new Response(
        JSON.stringify({ error: 'PULSE_ORIGIN is not configured', code: 'origin_missing' }),
        { status: 503, headers: { 'content-type': 'application/json; charset=utf-8' } },
      );
    }

    const incoming = new URL(request.url);
    const origin = new URL(originValue);
    const target = new URL(incoming.pathname + incoming.search, origin);
    const headers = new Headers(request.headers);

    const init = {
      method: request.method,
      headers,
      redirect: 'manual',
    };
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      init.body = request.body;
    }

    const response = await fetch(target, init);
    const out = new Response(response.body, response);

    // The tunnel host is not the browser's host. Keep cookies host-only on
    // the workers.dev domain so profile/account sessions survive the proxy.
    const cookies = response.headers.getSetCookie?.() ?? [];
    if (cookies.length) {
      out.headers.delete('set-cookie');
      for (const cookie of cookies) {
        out.headers.append('set-cookie', cookie.replace(/;\s*Domain=[^;]+/ig, ''));
      }
    }

    // Absolute redirects from the Python server should stay on workers.dev.
    const location = out.headers.get('location');
    if (location) out.headers.set('location', location.replace(origin.origin, incoming.origin));

    return out;
  },
};
