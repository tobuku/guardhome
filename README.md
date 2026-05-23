# GuardHome

Self-hosted home LAN parental control platform. DNS-level content filtering, per-child profiles, schedule enforcement, and a parent dashboard — no cloud account, no monthly fee, no command-line knowledge required after setup.

## What it does

- **Blocks content by category** across every device on your home network — adult content, gore, gore/horror anime, gambling, drugs, social media, gaming, streaming, and more
- **Per-child profiles** — each child gets their own set of rules, assigned devices, and schedule
- **Schedule enforcement** — bedtime mode, school hours, or any custom blocked window; internet resumes automatically
- **Educational exceptions** — mark Khan Academy, Duolingo, or your school's LMS as always-on so homework tools are never blocked by a screen time limit
- **Pause internet** — one button per device, instant
- **Activity reports** — daily query counts, top visited domains, top blocked domains, live DNS log
- **Alerts** — VPN bypass attempts, birthday milestone reminders to review settings
- **iOS configuration profile** — download and install a `.mobileconfig` on a child's iPhone/iPad to enforce restrictions even if they change the DNS manually. No MDM server or Apple developer account required.
- **Honest coverage report** — plain-language statement of what GuardHome can and cannot see for each child's devices (no false confidence)

## How it works

GuardHome wraps [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) as its DNS backbone and adds a management layer on top.

```
Child devices (all DNS queries)
        │
        ▼
  AdGuard Home (:53)          ← actual DNS server, enforces block rules
        │ REST API
        ▼
  GuardHome API (:8000)       ← FastAPI, SQLite, scheduler, classifier
        │
        ▼
  Parent Dashboard (:3001)    ← React web app
```

Every device on your LAN points to this machine as its DNS server. GuardHome manages AdGuard's filter lists and per-client rules through AdGuard's REST API — it never touches AdGuard's database directly.

**Bypass hardening** is applied automatically:
- All outbound DNS (port 53) should be redirected to GuardHome via your router's NAT rules
- Known DNS-over-HTTPS providers are blocked by domain
- Firefox canary domain (`use-application-dns.net`) returns NXDOMAIN — Firefox disables DoH automatically
- iCloud Private Relay blocked (Apple-permitted for network administrators)
- Common VPN provider domains blocked; VPN attempts generate a parent alert instead of silently passing through
- SafeSearch enforced on Google, Bing, DuckDuckGo via DNS rewrite
- YouTube Restricted Mode enforced via DNS rewrite

**Three-tier content classifier** for novel or ambiguous domains:
1. Community-maintained category-tagged domain lists (instant, offline)
2. Cloudflare Radar or CleanBrowsing URL reputation API (optional)
3. Claude AI page content classifier (optional) — fetches the page server-side, classifies it, caches the result, and adds a block rule automatically

## Requirements

- Docker and Docker Compose v2
- A machine that stays on (Raspberry Pi 4/5, mini PC, or any always-on desktop/server)
- Your router must allow changing the DHCP DNS server address

## Install

```bash
git clone https://github.com/tobuku/guardhome.git
cd guardhome
bash setup.sh
```

The script pulls images, builds containers, starts the stack, and prints the URLs. Open `http://localhost:3001` and complete the 4-step setup wizard.

**After setup:** change your router's DHCP DNS server to this machine's IP address. All home devices will immediately route DNS through GuardHome.

## Manual install (without the script)

```bash
cp .env.example .env
# Edit .env — set a real SECRET_KEY at minimum
docker compose up -d
```

## URLs

| Service | URL | Notes |
|---|---|---|
| Parent dashboard | `http://[your-ip]:3001` | Main interface |
| GuardHome API | `http://[your-ip]:8000` | REST API + Swagger docs at `/docs` |
| AdGuard Home UI | `http://[your-ip]:80` | AdGuard's own interface |

## Environment variables

Copy `.env.example` to `.env` and edit before first run.

| Variable | Default | Required |
|---|---|---|
| `SECRET_KEY` | insecure default | **Yes — change this** |
| `ADGUARD_USER` | `admin` | Recommended to change |
| `ADGUARD_PASS` | `guardhome` | Recommended to change |
| `ANTHROPIC_API_KEY` | — | Optional — enables AI content classifier |
| `CLOUDFLARE_TOKEN` | — | Optional — enables Cloudflare Radar domain lookup |
| `CLEANBROWSING_KEY` | — | Optional — enables CleanBrowsing domain lookup |

## Content categories

| Category | What it blocks |
|---|---|
| Adult / Pornography | All sexually explicit content |
| Gore & Graphic Violence | Graphic injuries, death, torture |
| Gore Anime | Hentai gore, ero-guro, horror anime |
| Gambling | Online casinos, sports betting, poker |
| Drugs & Alcohol | Drug purchase sites, pro-drug content |
| Political Extremism | Hate groups, radicalization content |
| Self-Harm | Pro-ana, suicide methods, self-harm content |
| Social Media | Facebook, Instagram, TikTok, Twitter, Snapchat |
| Gaming Sites | Online gaming portals |
| Streaming | Netflix, Hulu, YouTube, Twitch, Disney+ |
| Chat Apps | Discord, WhatsApp, Telegram |
| VPN / Proxy | VPN providers and anonymizing proxies |

## iOS device setup

For the strongest enforcement on iPhones and iPads:

1. Open the dashboard → child's profile → **Download .mobileconfig**
2. AirDrop or email the file to the child's device
3. On the device: Settings → Downloaded Profile → Install

The profile enforces DNS settings, disables VPN installation, disables Personal Hotspot (optional), and restricts content ratings. No MDM server or Apple developer account needed.

For supervised devices (strongest — prevents profile removal), use Apple Configurator 2 to supervise the device via USB first.

## Honest limitations

GuardHome does not hide what it cannot do:

- **End-to-end encrypted chat** (iMessage, WhatsApp, Signal) — content cannot be read at the network level by any product
- **In-game voice chat** (Roblox, Fortnite, Discord voice) — not monitorable by any consumer product
- **Cellular data** — if a device has an active SIM/LTE connection, it bypasses all LAN controls entirely; the iOS supervised profile can disable cellular data
- **Content within platforms** — DNS blocking either allows all of Reddit/Twitter/Discord or blocks the entire domain; blocking specific content within a platform requires the companion app approach (not yet implemented)
- **Obfuscated VPNs** — tools like VLESS+XTLS or Shadowsocks that mimic HTTPS cannot be reliably blocked at home scale; GuardHome alerts you to VPN attempts rather than silently failing

The dashboard's Coverage Report (per-child) gives a plain-language summary of what is and is not monitored for each assigned device.

## Deployment modes

**Raspberry Pi (recommended)** — dedicate a Pi 4/5 or mini PC to run the stack 24/7. Lowest power, always available.

**Docker on an existing machine** — works on any always-on Windows, Mac, or Linux machine with Docker Desktop installed.

## Development

```bash
# API — local dev with hot reload
cd api
pip install -r requirements.txt
ADGUARD_URL=http://localhost:80 DB_PATH=./dev.db uvicorn main:app --reload

# Dashboard — local dev server
cd dashboard
npm install
npm run dev   # http://localhost:5173 — proxies /api to :8000

# Rebuild a single container after changes
docker compose build api
docker compose up -d api
```

API docs (Swagger UI): `http://localhost:8000/docs`

## Roadmap

- [x] Phase 1 — DNS filtering, per-child profiles, schedules, dashboard, iOS profiles
- [ ] Phase 2 — Windows monitoring agent, macOS Screen Time profile generator
- [ ] Phase 3 — Per-client AdGuard filtering (currently category toggles are global)
- [ ] Phase 4 — ntfy.sh push notifications, weekly email digest
- [ ] Phase 5 — Community blocklist plugin system, multi-language support

## Stack

- **DNS**: AdGuard Home
- **Backend**: Python, FastAPI, SQLite (aiosqlite), APScheduler
- **Frontend**: React, TypeScript, Tailwind CSS, Vite
- **Deploy**: Docker Compose
- **iOS agent**: Python plistlib (.mobileconfig generator)
- **AI classifier**: Claude API (claude-haiku — optional)

## License

MIT
