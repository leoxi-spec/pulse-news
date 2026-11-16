# Putting Pulse on Cloudflare

Pulse is not a static site. The front end is static, but the Today board, feed,
search, profiles, archive and live scores all come from the Python server in
`run.py` and its SQLite database. Cloudflare Workers/Pages only served the
static files in the current `pulse-news.leo-xi.workers.dev` deployment, so
`/api/health` returns 404 even though `/` returns 200. That is the "Can't reach
the Pulse server" screen.

Use one of these architectures.

## Option A — Cloudflare Tunnel (keep the Mac as the server)

This is the smallest change and keeps your existing archive and account data.
It needs a domain whose DNS is managed by Cloudflare. A `*.workers.dev`
subdomain cannot be pointed at a tunnel.

```bash
# 1. Run Pulse locally (the login service already does this):
cd "/Users/leozihanxi/.deepai-code/scratch/2026-11-10-make-a-completely-production-ready-fadd607d"
python3 tools/install_launch_agent.py

# 2. cloudflared is already installed at ~/bin/cloudflared in this checkout.
#    If it is missing, download the macOS build and then authorise it.
~/bin/cloudflared tunnel login

# 3. Create the tunnel and route a hostname.
~/bin/cloudflared tunnel create pulse
~/bin/cloudflared tunnel route dns pulse pulse.example.com

# 4. ~/.cloudflared/config.yml
cat > ~/.cloudflared/config.yml <<'YAML'
tunnel: REPLACE-WITH-THE-UUID
credentials-file: /Users/leozihanxi/.cloudflared/REPLACE-WITH-THE-UUID.json
ingress:
  - hostname: pulse.example.com
    service: http://127.0.0.1:8787
  - service: http_status:404
YAML

# 5. Test it.
~/bin/cloudflared tunnel run pulse

# 6. Keep it running at login (may ask for your password once).
sudo ~/bin/cloudflared service install
```

Open `https://pulse.example.com`. Do not expose the origin directly; keep
`PULSE_HOST=127.0.0.1` (the default). If the Mac sleeps, the public site is
offline, so disable sleep or run the server on an always-on machine.

For a private family/school deployment, add a **Cloudflare Access** policy for
the hostname. For a public app, leave Access off and use Pulse's own accounts.

## Option B — an always-on container with a volume (recommended for public)

A small Fly.io machine is enough. The repository already has a Dockerfile that
binds `0.0.0.0`, sets `PULSE_DATA_DIR=/data` and exposes 8787.

```bash
fly launch --no-deploy
fly volumes create pulse_data --size 3 --region yyz
```

Add the mount and keep exactly one machine running (SQLite must not be shared
by several writers):

```toml
# fly.toml
[mounts]
  source = "pulse_data"
  destination = "/data"

[http_service]
  internal_port = 8787
  force_https = true
  auto_stop_machines = false
  min_machines_running = 1
```

```bash
fly deploy
fly scale count 1
```

Then either use the generated `*.fly.dev` hostname, or put a custom domain in
front of it from Cloudflare (CNAME to the Fly hostname, proxy enabled, SSL
mode **Full (strict)** after Fly issues its certificate).

The first ingestion pass takes a few minutes. The volume keeps the archive,
profiles and translations across deploys.

## Option C — keep the Workers URL with a proxy

In the current dashboard, **Create application → Start with Hello World!** is the
blank Worker flow. There is no separate "Create Worker" button. Paste
`cloudflare/proxy.js`, add `PULSE_ORIGIN`, and deploy. Do not choose **Upload
your static files**.

If you specifically want `*.workers.dev` to stay as the address, run the real
server behind a Tunnel and put a tiny Worker in front of it. The Worker forwards
every request, including `/api/*`, to the Tunnel. This is the setup in
[`cloudflare/README.md`](cloudflare/README.md); it works with a Quick Tunnel
today, but the Quick Tunnel URL changes when it restarts.

Do not try to proxy to `http://localhost:8787` from the Worker: Cloudflare
cannot reach your Mac's loopback. The origin must be the public Tunnel URL.

## Option D — Cloudflare Containers

Cloudflare Containers can run the Docker image, but Pulse stores its archive in
a local SQLite file. Cloudflare Containers do not provide a normal persistent
block volume for that file. You would need to move storage to D1/R2 (and
replace FTS5/search/ingestion) before this is production-safe. That is a
backend rewrite, not a deployment setting.

## What not to do

- **Do not deploy only `pulse/static`.** It renders the shell, then every API
  call 404s.
- **Do not point a Worker at `http://localhost:8787`.** Cloudflare cannot reach
  your Mac's loopback address. A Worker proxy needs a public Tunnel or a
  container origin, and it also has to preserve cookies/CSRF correctly.
- **Do not run more than one SQLite writer.** Keep one machine/process for
  ingestion and API traffic.
