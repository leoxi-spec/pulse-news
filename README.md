# Pulse

**News that keeps up with you.** A production-ready, self-hosted news app built for
students and teens: 331 publications from 51 countries, a permanent searchable
archive, live sports scores, optional AI overviews, study tools, and a feed that
actually learns what you read.

Runs on the Python standard library alone — no Node, no build step, no ads, no
tracking, no account.

```bash
python3 run.py
```

Then open <http://localhost:8787> in your browser.

---

## Why it exists

Most news apps are built for adults with unlimited time and a subscription to
everything. Pulse is built for the opposite: someone with ten minutes between
classes who still wants to understand what's happening. That means:

- **A preview and overview of every story**, so you can decide whether to read it.
- **An archive that never forgets**, so searching "climate" in six months still
  returns hundreds of stories.
- **Dates you can trust**, with "published" and "first seen" kept strictly apart.
- **Live scores** that refresh every 30 seconds.
- **Study features** that turn the day's news into a quiz, glossary and citation.

---

## Feature tour

### Reading
| | |
|---|---|
| **330+ sources** | 331 publications, 452 feeds, 51 countries, 19 topics. Wires, national dailies, local metros, specialists, student and teen outlets. |
| **Story clustering** | Ten outlets covering one event become one card with a "9 outlets covering" badge and a compare-coverage view. |
| **Clear read labels** | Every card states **📖 Read here** (full text inside Pulse), **👁️ Preview** (summary + overview, opens at the publisher) or **🔒 Subscription**. Articles open with a banner saying the same thing. A *Readable here* stream filters to in-app text only. |
| **Symbol key** | Sidebar → **Key** (or press `?`) explains every icon, badge and score marker. |
| **Search everywhere** | A search bar on the home page plus a command palette (`⌘K` or `/`) with headlines, topics, sources and quick actions as you type. |
| **Front-page sections** | Apple News-style **Top Stories** grid plus configurable rows: brief, For you, scores, any topic, long reads, saved, research. Reorder or hide them in *Customize*. |
| **15 themes** | Auto, Dark, Light, Sepia, Midnight, Forest, Sunset, Mono, Rose, Ocean, plus five calmer palettes: **Dusk, Sage, Sand, Mist, Clay**. |
| **Room to read** | No sidebars at all: a compact top bar, a personalised **Today** masthead, full-width sections and a mixed-size mosaic (1–3 stories per row, tall leads and compact briefs). |
| **Sports pins** | Apple News-style **Pinned** bar: pin leagues and teams (★ on any team), filter with **My sports**, and see pinned games on the front page. Scores stream in progressively so the page never waits on 15 leagues. |
| **Research desk** | Turn every saved story into a bibliography in MLA, APA, Chicago, Harvard or BibTeX; add books/websites by hand; export `.txt`/`.bib`; quote collector from your notes. |
| **Reader** | Full text when the publisher allows it, paywall/preview handling when not, focus mode, adjustable type (sans/serif/dyslexia-friendly), highlight & note. |
| **Permanent archive** | Articles are never deleted. Full-text search covers everything ever ingested, with filters (`source:bbc`, `topic:tech`, `after:2025-01-01`, `-trump`). |
| **Honest dates** | Publisher timestamp, normalised UTC, plus a confidence marker. Future-dated items are clamped and labelled "First seen". |

### Personalisation
- Six-step onboarding survey: name, year group, topics (with "love it" weighting),
  trusted outlets, reading length, goals, region, keywords.
- Ranker blends survey weights, follows, engagement (opens, reads, saves, likes,
  hides — with 21-day decay), saved-story keywords, freshness, coverage breadth
  and reading-time fit.
- Every card can explain itself: *"You follow Tech"*, *"10 outlets covering"*,
  *"Matches topics you save"*.
- Diversity pass stops one outlet or topic monopolising the feed.
- Settings for reading length, hiding paywalled stories, daily goal, theme
  (dark/light/sepia/system), text size, contrast, reduced motion.

### Teens & students
- **Daily brief** — five stories, ~2 minutes, ranked for you.
- **Study mode** — quiz generated from the article's own sentences, jargon decoder
  with flashcards, citation helper.
- **Quizzes** — rules-based by default (works with no API key), AI-generated when
  a provider is configured. Answers are always checkable against the text.
- **Citations** — MLA 9, APA 7, Chicago, Harvard and BibTeX, with publisher date
  and access date filled in.
- **XP, levels, streaks and badges** — reading streaks, weekly activity chart,
  topic balance, 12 unlockable badges.
- **Media literacy** — the compare-coverage panel shows the approximate editorial
  spread of who covered a story, explicitly labelled as approximate.

### Sports
- Live scores for NBA, WNBA, NFL, college football/basketball, MLB, NHL, MLS,
  Premier League, LaLiga, Serie A, Bundesliga, Ligue 1, Champions League and F1.
- Live/upcoming/final filters, venue and broadcast info, team following,
  30-second auto-refresh while the page is visible.
- ESPN's public scoreboard and news APIs; cached server-side so a classroom of
  clients doesn't hammer upstream.

### App
- Installable PWA with offline shell and cached API responses.
- Keyboard shortcuts (`/`, `g h`, `g d`, `g s`, `g b`, `?`, `Esc`).
- Responsive: sidebar + right rail on desktop, bottom nav on mobile.
- Accessible: skip link, focus rings, ARIA labels, reduced-motion support,
  high-contrast option, print stylesheet for articles.

---

## AI overviews (optional, never required)

Pulse works fully without an AI provider. When `PULSE_AI_BASE_URL` is not set,
overviews use an **extractive** summariser and the UI says *"Auto summary"* —
never "AI".

To enable AI overviews, point Pulse at any OpenAI-compatible endpoint:

```bash
# OpenAI
export PULSE_AI_BASE_URL=https://api.openai.com/v1
export PULSE_AI_API_KEY=sk-...
export PULSE_AI_MODEL=gpt-4o-mini

# Local Ollama
export PULSE_AI_BASE_URL=http://localhost:11434
export PULSE_AI_MODEL=llama3.1
```

The prompt is deliberately restrictive: the model may only restate facts from the
supplied article text, must return JSON, and is told to say when the text is
insufficient. Results are labelled *"AI overview"* with the model name and a
warning to check the original. Results are cached per article+model, and there is
a per-hour rate limit (`PULSE_AI_RATE`).

Quiz, jargon decoding, explain-simply and citations all have deterministic local
implementations, so study features never depend on an API key.

---

## Quick start

Requirements: **Python 3.10+** (3.13 recommended). No packages to install.

```bash
git clone <your-repo> pulse && cd pulse
python3 run.py
```

Open <http://localhost:8787>. The first run seeds the catalogue and starts
ingesting in the background; the feed fills within a minute or two.

Useful flags:

```bash
python3 run.py --port 9000        # run on a different port
python3 run.py --host 0.0.0.0     # expose on the network (pair with a token)
python3 run.py --no-ingest        # serve only, don't fetch feeds
python3 run.py --ingest-once      # one fetch pass, then exit
```

Copy the commands without the trailing comments — some shells (macOS zsh by
default) do not treat `#` as a comment in interactive mode and will pass it to
Python as an argument.

Data lives in `~/Library/Application Support/pulse-news` (macOS),
`~/.local/share/pulse-news` (Linux) or `%LOCALAPPDATA%\pulse-news` (Windows).
Override with `PULSE_DATA_DIR`.

---

## Troubleshooting

**`run.py: error: unrecognized arguments: # → http://localhost:8787`**
Paste only the command, not the trailing note. macOS `zsh` does not treat `#` as
a comment in interactive mode, so it gets passed to Python. Run:

```bash
python3 run.py
```

**`Address already in use`**
An instance is already running. Find and stop it:

```bash
lsof -nP -iTCP:8787 -sTCP:LISTEN -t | xargs kill
```

**How do I stop the server?**
Press `Ctrl+C` in the Terminal window running it (it shuts down cleanly).

**The feed looks empty on first run**
Expected for the first ~60 seconds: the app is fetching 421 feeds and stores them
as they arrive. The onboarding survey takes you straight into the feed.

**A source says "blocked" or "unreachable"**
Open *Sources → Feed health*. School/office filters and some publishers (AP,
Reuters) block automated requests; those sources stay in the catalogue and retry.

**The UI looks stale after an update**
The service worker caches the app shell. Hard-reload with `Cmd+Shift+R`, or
unregister it in DevTools → Application → Service Workers.

**Reset everything**
Quit Pulse, then delete `~/Library/Application Support/pulse-news` (macOS),
`~/.local/share/pulse-news` (Linux) or `%LOCALAPPDATA%\pulse-news` (Windows).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PULSE_HOST` / `PULSE_PORT` | `127.0.0.1` / `8787` | Bind address |
| `PULSE_DATA_DIR` | OS data dir | SQLite DB, caches and logs |
| `PULSE_ACCESS_TOKEN` | unset | Require a bearer token / cookie before serving anything |
| `PULSE_INGEST` | `1` | Enable background ingestion |
| `PULSE_INGEST_INTERVAL` | `300` | Seconds between full sweeps (conditional GET keeps this cheap) |
| `PULSE_INGEST_WORKERS` | `12` | Concurrent feed fetches |
| `PULSE_MAX_PER_FEED` | `40` | Items kept per feed per sweep |
| `PULSE_EXTRACT_BODIES` | `1` | Fetch and extract full article text |
| `PULSE_EXTRACT_PER_CYCLE` | `60` | How many articles to extract per sweep |
| `PULSE_EXTRACT_WORKERS` | `4` | Concurrent extraction fetches |
| `PULSE_ARCHIVE_FULLTEXT` | `1` | Store full extracted text (set `0` to keep only previews) |
| `PULSE_AI_BASE_URL` | unset | OpenAI-compatible endpoint |
| `PULSE_AI_API_KEY` | unset | Provider key |
| `PULSE_AI_MODEL` | `gpt-4o-mini` | Model name |
| `PULSE_AI_RATE` | `120` | AI requests per hour |
| `PULSE_SPORTS` | `1` | Enable scoreboards |
| `PULSE_SPORTS_CACHE` | `20` | Scoreboard cache seconds |
| `PULSE_USER_AGENT` | desktop Chrome UA | Override the outbound user agent |
| `PULSE_HONEST_UA` | `0` | `1` sends an explicit bot user agent instead |
| `PULSE_ALLOW_PRIVATE_HOSTS` | `0` | Allow fetching private IPs (testing only) |
| `PULSE_CA_BUNDLE` | OS store | Extra CA bundle path |

---

## Architecture

```
Browser (PWA: vanilla ES modules, no build step)
   │  JSON over fetch, HttpOnly profile cookie, X-Pulse-Client CSRF header
   ▼
ThreadingHTTPServer ──► api.py ──► feed.py ──► rank.py ──► SQLite (WAL)
   │                     │           │            │
   static + gzip + ETag  │           │            ├─ stories.py   clustering
   CSP + security headers│           │            ├─ profiles.py  XP/streaks
                         │           │            └─ search.py    FTS5
                         │           ├─ ai.py         (optional provider + extractive)
                         │           ├─ citations.py
                         │           └─ sports.py     (ESPN, cached)
                         │
                         └─ ingest.py ─► httpclient.py ─► feeds (421)
                                          tls.py (OS trust store, curl fallback)
```

**Ingestion loop** (background thread):
1. fetch all due feeds concurrently, with ETag/Last-Modified and backoff
2. parse RSS/Atom/RDF/JSON Feed, normalise, classify, upsert (never delete)
   — articles are stored as each feed arrives, so a fresh install fills in seconds
3. cluster into stories, recompute coverage counts and breaking flags
4. extract readable text for the highest-value recent articles (robots-aware)
5. record a run report + per-feed health, sleep, repeat

**Storage**: one SQLite file with WAL, FTS5 external-content index and triggers,
`busy_timeout`, and a single writer lock. Articles are append-only; housekeeping
only prunes caches and old run logs.

---

## API (selected)

Everything the UI does is available as JSON:

```
GET    /api/bootstrap                 catalogue, profile, AI/ingest status
GET    /api/feed?mode=for-you|top|breaking|latest|longreads&topic=&offset=
GET    /api/discover                  topics, trending, editors' picks, sources
GET    /api/articles/:id              full article + blocks + coverage + notes
GET    /api/articles/:id/overview     AI or extractive overview
GET    /api/articles/:id/quiz         quiz (AI or rules-based)
GET    /api/articles/:id/explain      plain-language rewrite + jargon
GET    /api/articles/:id/citations    MLA/APA/Chicago/Harvard/BibTeX
GET    /api/research/bibliography     bibliography from saved stories
POST   /api/research/cite             cite a manually entered source
POST   /api/articles/:id/save         save to a collection
POST   /api/articles/:id/notes        highlight/note
GET    /api/search?q=&topic=&source=&since=&sort=
GET    /api/search/suggest?q=
GET    /api/brief                     two-minute briefing
GET    /api/sports?leagues=nba,nfl    live scoreboards
GET    /api/sources                   directory + feed health
PATCH  /api/profile                   survey / preferences
POST   /api/events                    reading events (XP, streak, ranking)
POST   /api/ingest/refresh            trigger a sweep
GET    /api/health                    liveness + counts
```

Mutating requests need `X-Pulse-Client: web` (defence in depth alongside the
`SameSite=Lax` cookie). Visiting `/?profile=<id>` switches the local profile
(handy when siblings share a computer); when `PULSE_ACCESS_TOKEN` is set, the
server serves a small token login page before anything else. If `PULSE_ACCESS_TOKEN` is set, every request also needs
`Authorization: Bearer …` or `?token=…` once to set a cookie.

---

## Testing

```bash
python3 -m unittest discover -s tests -v     # 113 tests, no network required
python3 tools/verify_catalog.py              # catalogue integrity
python3 tools/verify_catalog.py --live       # fetch every feed (slow)
python3 tools/check_js.py                    # syntax-check the ES modules
python3 tools/browser_check.py               # headless Chrome end-to-end run
```

`tools/browser_check.py` launches headless Chrome, drives the real UI through the
DevTools protocol (no third-party packages) and checks home sections, read labels,
the command palette, the symbol key, the customizer, saving, citations, quizzes,
search, scores, brief, study, research, theme switching, the survey-skip path,
mobile layout and the offline shell, while failing on any console error.

The suite covers date parsing (including publisher clock skew), HTML extraction
and boilerplate stripping, feed parsing across four formats, topic and story
clustering, search query parsing, citations, profiles/XP/streaks, the ingest →
store → cluster path, the JSON API (including SSRF rejection), and the HTTP
server's security headers, CSRF check, ETag and traversal defences.

---

## Deployment

**Behind a reverse proxy** (nginx/caddy), set `PULSE_ACCESS_TOKEN` and
`PULSE_HOST=127.0.0.1`, then proxy to `:8787`.

**systemd** (Linux):

```ini
[Unit]
Description=Pulse news
After=network-online.target

[Service]
User=pulse
WorkingDirectory=/opt/pulse
Environment=PULSE_DATA_DIR=/var/lib/pulse
ExecStart=/usr/bin/python3 run.py --host 127.0.0.1 --port 8787
Restart=always

[Install]
WantedBy=multi-user.target
```

**launchd** (macOS): run `python3 run.py` from a `LaunchAgent` with
`PULSE_DATA_DIR` set to a folder you back up.

**Docker**: `docker build -t pulse . && docker run -p 8787:8787 -v pulse-data:/data pulse`

Back up one file: `pulse.sqlite3` (plus `-wal` while running, or use
`sqlite3 pulse.sqlite3 ".backup backup.sqlite3"`).

---

## Privacy & security

- No analytics, no third-party scripts, no fonts or CDNs. Everything is served
  from your machine.
- Images are proxied through `/api/img` with SSRF guards and an image-type
  allowlist, so publishers never see your IP or referrer.
- Article HTML is never injected: it is converted to plain text blocks and
  escaped on render. The CSP forbids inline script (`script-src 'self'`).
- The profile cookie is `HttpOnly`, `SameSite=Lax`, and holds only a random id.
- `GET /api/profile/export` returns everything stored about you; resetting the
  profile deletes it.

---

## Honest limitations

- **Paywalls**: Pulse shows the publisher's preview, an overview and metadata,
  then links out. It never bypasses a paywall.
- **Extraction** depends on the page. Some sites are JS-only, some block
  non-browser clients; those fall back to previews and say so. School/office
  filters can block whole domains — those sources stay in the catalogue, are
  flagged "blocked on this network", and keep retrying.
- **Publisher dates** are sometimes wrong (bogus timezones, clocks a day ahead).
  Pulse clamps future timestamps and labels them "First seen" rather than
  inventing precision.
- **AI overviews** can be wrong even when grounded; the UI says so and links to
  the original. The default mode is non-AI.
- **Upstream feeds come and go.** Health is reported per feed in *Sources →
  Feed health*. Some outlets (AP, Reuters, ESPN RSS) block automated fetches;
  ESPN scores/news use their public JSON API instead.
- **Editorial leans** are approximate, hand-set labels for a media-literacy
  feature, not a verdict on accuracy.

---

## Adding a source

1. Add a line to `SOURCES_RAW` in `pulse/sources.py`:
   `id|Name|domain|CC|Region|lean|paywall|audience|topics|about`
2. Add one or more feeds to `FEEDS_RAW`: `id|topic|url` (RSS, Atom, RDF or JSON
   Feed; `espn-json:nba` for ESPN).
3. Run `python3 tools/verify_catalog.py --live --limit 20` to check it.
4. Restart; the ingester picks it up automatically and backfills the archive.

---

## Licence

Application code: MIT. News content, headlines, images and summaries remain the
property of their publishers; Pulse stores them locally for personal reading and
search, and every article links back to the original.
