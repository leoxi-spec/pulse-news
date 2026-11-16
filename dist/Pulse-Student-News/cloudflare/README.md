# Pulse on a Workers URL without moving the Python server

This is the stop-gap for a Worker that already exists at
`pulse-news.leo-xi.workers.dev` but only serves static assets.

1. Start Pulse locally (the login service does this):

   ```bash
   python3 tools/install_launch_agent.py
   ```

2. Expose the local server with a Quick Tunnel:

   ```bash
   ~/bin/cloudflared tunnel --url http://127.0.0.1:8787
   ```

   Copy the `https://….trycloudflare.com` URL it prints. The URL changes when
   the tunnel restarts.

3. Create or edit a Worker in the Cloudflare dashboard and paste
   [`proxy.js`](proxy.js). Add a plain-text variable:

   - Name: `PULSE_ORIGIN`
   - Value: the `https://….trycloudflare.com` URL

4. Deploy. Open the Worker URL. Every request, including `/api/*`, now reaches
   the Python server.

If the existing `pulse-news` Worker is static-only, delete it and create a new
Worker with the same name (or use a new name) and paste the proxy. The Worker
does not need a static-assets binding because the tunnel serves the front end
too.

For a permanent setup, replace the Quick Tunnel with a named Tunnel on a domain
you control; see [`../CLOUDFLARE.md`](../CLOUDFLARE.md). A Quick Tunnel has no
uptime guarantee.
