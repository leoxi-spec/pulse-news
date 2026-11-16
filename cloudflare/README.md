# Pulse on a Workers URL without moving the Python server

This is the stop-gap for a Worker that only serves static assets (for example
`pulse-news.leo-xi.workers.dev`). It is **not** the permanent-link setup; a
Quick Tunnel URL changes whenever the tunnel restarts.

## Create the Worker (current Cloudflare dashboard)

Cloudflare's current **Create an app** screen does not have a separate
"Create Worker" button. Use:

1. Open **Workers & Pages → Create application**.
2. Choose **Start with Hello World!**. This creates a blank Worker.
3. Name it `pulse-news` if you want the existing workers.dev address, or use a
   new name such as `pulse-news-live`.
4. Deploy the Hello World worker once.
5. Choose **Edit code**, delete the sample code, and paste [`proxy.js`](proxy.js).
6. Open **Settings → Variables and Secrets**, add a text variable:
   - `PULSE_ORIGIN` = the public tunnel origin, for example
     `https://fog-innovation-epa-tail.trycloudflare.com`
7. Deploy again.

The Worker does not need a static-assets binding. It forwards the whole app,
including `/api/*`, to the tunnel origin.

Do **not** choose **Upload your static files** or **Continue to Pages**. Those
create a static-only app, which is why the current deployment returns 404 for
`/api/health`.

## Quick demo origin

Start Pulse locally, then run a Quick Tunnel:

```bash
python3 tools/install_launch_agent.py
~/bin/cloudflared tunnel --url http://127.0.0.1:8787
```

Copy the `https://….trycloudflare.com` URL into `PULSE_ORIGIN`. The URL changes
when the tunnel restarts, so this is only for a demo.

## Permanent link

For a stable, professional URL, use a named Tunnel on a domain managed by
Cloudflare. See [`../CLOUDFLARE.md`](../CLOUDFLARE.md), Option A. A
`*.workers.dev` address cannot be the origin of a Tunnel.
