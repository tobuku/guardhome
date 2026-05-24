#!/usr/bin/env bash
# GuardHome guided installer

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[GuardHome]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "  ================================================================"
echo "   GuardHome — Home LAN Parental Control Platform"
echo "   Open-source • Self-hosted • No cloud account needed"
echo "  ================================================================"
echo ""

# --- Preflight checks ---
command -v docker  >/dev/null 2>&1 || error "Docker is not installed. Install Docker first: https://docs.docker.com/get-docker/"
command -v docker  >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || error "Docker Compose v2 not found. Update Docker Desktop."

info "Docker found. Proceeding."

# --- .env setup ---
if [ ! -f .env ]; then
    cp .env.example .env
    SECRET=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 48 | head -n 1)
    sed -i "s/change-this-to-a-random-string-in-production/$SECRET/" .env
    info ".env created with a random secret key."
else
    info ".env already exists — skipping."
fi

# --- Pull and build ---
info "Pulling Docker images (this takes a minute the first time)..."
docker compose pull adguard

info "Building GuardHome containers..."
docker compose build

# --- Start stack ---
info "Starting GuardHome stack..."
docker compose up -d

echo ""
info "Stack is up. Waiting for services to initialize..."
sleep 5

# --- Auto-configure AdGuard on first run ---
ADGUARD_PASS="${ADGUARD_PASS:-guardhome}"
ADGUARD_USER="${ADGUARD_USER:-admin}"

info "Waiting for AdGuard setup wizard (port 3000)..."
AGH_READY=false
for i in {1..24}; do
    if curl -sf http://localhost:3000/control/install/get_addresses >/dev/null 2>&1; then
        AGH_READY=true; break
    fi
    sleep 5
done

if [ "$AGH_READY" = true ]; then
    info "Configuring AdGuard Home (admin / $ADGUARD_PASS)..."
    curl -sf -X POST http://localhost:3000/control/install/configure \
        -H "Content-Type: application/json" \
        -d "{
              \"web\":      {\"ip\": \"0.0.0.0\", \"port\": 80, \"https_port\": 0},
              \"dns\":      {\"ip\": \"0.0.0.0\", \"port\": 53},
              \"username\": \"$ADGUARD_USER\",
              \"password\": \"$ADGUARD_PASS\"
            }" >/dev/null 2>&1 && info "AdGuard configured." || warn "AdGuard configure call failed — may already be set up."
    sleep 5
else
    info "AdGuard setup wizard not found — assuming already configured."
fi

# --- Check API health ---
API_OK=false
for i in {1..12}; do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        API_OK=true; break
    fi
    sleep 5
done

if [ "$API_OK" = false ]; then
    warn "API did not respond within 60s. Check: docker compose logs api"
else
    info "API is healthy."
fi

echo ""
echo "  ================================================================"
echo "   SETUP COMPLETE"
echo ""
echo "   Dashboard:       http://localhost:3001"
echo "   API docs:        http://localhost:8000/docs"
echo "   AdGuard Home:    http://localhost:80"
echo ""
echo "   Open the dashboard and complete the Setup Wizard."
echo "   Then point your router's DNS to this machine's IP."
echo ""
echo "   To stop:   docker compose down"
echo "   To update: git pull && docker compose build && docker compose up -d"
echo "  ================================================================"
echo ""
