# Pulse on Render

The live Render deployment is still reporting **Pulse 2.2.1**. The current
checkout is **3.4.3**. The service is a **Docker** web service, so it needs a
`Dockerfile` at the repository root. The previous upload omitted it and the
deploys failed before the container started.

## Recommended settings

Use these values in **Render Dashboard → pulse-news → Settings**.

| Setting | Value |
| --- | --- |
| Runtime | Docker |
| Dockerfile Path | `Dockerfile` |
| Build command | Leave blank |
| Start command | Leave blank (the Dockerfile runs the app) |
| Docker command | Leave blank |
| Health check path | `/api/health` |
| Instance type | Free (512 MB) for testing; Starter/Standard for a public site |
| Auto deploy | On, if the service is connected to GitHub |

Environment:

```text
PYTHONUNBUFFERED=1
MALLOC_ARENA_MAX=2

PULSE_DATA_DIR=/data
PULSE_INGEST=1
PULSE_INGEST_WORKERS=3
PULSE_INGEST_INTERVAL=600
PULSE_FEED_TIMEOUT=15
PULSE_ARTICLE_TIMEOUT=15
PULSE_MAX_PER_FEED=20

PULSE_EXTRACT_BODIES=0
PULSE_EXTRACT_WORKERS=1
PULSE_EXTRACT_PER_CYCLE=0
PULSE_ARCHIVE_FULLTEXT=0

PULSE_SPORTS_CACHE=30
```

`MALLOC_ARENA_MAX=2` and the smaller feed pool prevent the 512 MB free
instance from being killed while 12 feed workers and 8 extraction workers run
at once. Full-body extraction is the largest memory user; leave it off on the
free tier. Feed previews, images, search, scores and the archive still work.

## Deploy the current code

The GitHub repository at `leoxi-spec/pulse-news` is now on the current code.
Render is a **Docker** service: it needs a `Dockerfile` at the repository root.
The 3.4.3 uploads omitted that file, so every Docker build failed before the
process could start.

Make the repository root look like this checkout:

```text
run.py
requirements.txt
render.yaml
pulse/
tools/
```

not:

```text
Pulse News/
  run.py
  pulse/
```

### Replace the repository with the current build

On your Mac:

```bash
# 1. Clone the repository.
git clone https://github.com/leoxi-spec/pulse-news.git
cd pulse-news

# 2. Remove the old uploaded app from the repository.
rm -rf "Pulse News"

# 3. Copy the current build to the repository root.
rsync -a "/Users/leozihanxi/.deepai-code/scratch/2026-11-10-make-a-completely-production-ready-fadd607d/dist/Pulse-Student-News/" ./

# 4. Commit and push.
git add -A
git commit -m "Deploy Pulse 3.4.3"
git push
```

If you prefer the GitHub website, use **Add file → Upload files** and upload
the **contents** of `dist/Pulse-Student-News`, not the enclosing folder. Delete
the old `Pulse News` folder first.

In Render:

- **Root Directory**: leave blank.
- **Auto-Deploy**: on.
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python3 run.py --host 0.0.0.0 --port $PORT`

If the service was originally configured with **Root Directory = Pulse News**,
clear it. Otherwise Render will keep starting the old app. The uploaded build
also includes a small `Pulse News/run.py` compatibility launcher, so an old
Root Directory will still start the current app; clearing it is still tidier.

Alternatively, use Render's manual upload deploy and upload
`dist/Pulse-Student-News.zip`; the zip currently contains the current build.

After the deploy, verify:

```bash
curl -fsS https://pulse-news-6b68.onrender.com/api/health
```

The response must say `"version": "3.4.3"`. If it still says `2.2.1`, Render is
still running the old upload.

## The two empty sections

`Top Stories` and `For you` were not missing features. They were rendering
their empty state while the new instance was still ingesting its first feeds.
The current UI now shows **Building the first edition** with live percentage
and re-checks `/api/ingest/status` until articles arrive.

A cold Render start needs a few minutes: the service fetches from hundreds of
feeds. The page fills itself in without a manual reload.

## Persistent data

Render free instances use an ephemeral disk. On restart or redeploy the SQLite
archive starts over and must ingest again. That is why `/api/health` can show a
small article count after a fresh deploy.

For a persistent archive, use a paid instance and add a disk:

1. Render Dashboard → **Disks** → **Add Disk**.
2. Name: `pulse-data`.
3. Mount path: `/data`.
4. Size: 1 GB or more.
5. Keep `PULSE_DATA_DIR=/data` (the disk mount path is `/data`).
6. Redeploy.

`render.yaml` deliberately does not declare a disk because disks are not
available on the free plan.

## Reliability

- Free instances spin down after inactivity; the first request can take
  30–60 seconds.
- Keep one Render instance only. SQLite must have a single writer.
- Do not enable `PULSE_EXTRACT_BODIES` on the free tier.
- Check **Logs** for the process restarting; the memory-kill email means the
  old high-concurrency settings are still active.
