#!/usr/bin/env bash
#
# Create deploy/.env with freshly generated secrets.
#
# RUN THIS ON THE SERVER, NOT ON A LAPTOP AND NOT IN A CHAT WINDOW. That is the
# entire point of it existing: the three secrets below are generated where they
# will be used and never travel anywhere. A secret that has been pasted into an
# email, a terminal you screen-shared, or an AI conversation is a secret you
# have to assume is public.
#
#   cd kolabo/deploy && bash bootstrap-env.sh
#
# It refuses to touch an existing .env, so it is safe to run twice.

set -euo pipefail

cd "$(dirname "$0")"

if [[ -f .env ]]; then
  echo "deploy/.env already exists. Refusing to overwrite it."
  echo "Delete it first if you really mean to regenerate every secret —"
  echo "note that rotating JWT_SECRET signs out every user, and rotating"
  echo "DOCUMENT_ENCRYPTION_KEY makes already-stored verification documents"
  echo "permanently unreadable."
  exit 1
fi

for cmd in openssl python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required command: $cmd"; exit 1; }
done

echo "Generating secrets..."

JWT_SECRET="$(openssl rand -hex 32)"
POSTGRES_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)"

# Fernet needs a specific shape — 32 url-safe base64 encoded bytes — so this
# cannot be `openssl rand`. Generated with the same library that will read it,
# which is the only way to be sure it is valid before the app tries to boot.
DOCUMENT_ENCRYPTION_KEY="$(python3 - <<'PY'
try:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
except ImportError:
    import base64, os
    # Same shape, no dependency: 32 random bytes, url-safe base64. Fernet
    # accepts this; the library is only used above as a correctness check.
    print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
)"

cp .env.example .env

# In-place substitution on the empty assignments only. `|` as the delimiter
# because base64 output contains `/`.
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" .env
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PASSWORD}|" .env
sed -i "s|^DOCUMENT_ENCRYPTION_KEY=.*|DOCUMENT_ENCRYPTION_KEY=${DOCUMENT_ENCRYPTION_KEY}|" .env

chmod 600 .env

cat <<'EOF'

deploy/.env created, mode 600, with three generated secrets:
  JWT_SECRET, POSTGRES_PASSWORD, DOCUMENT_ENCRYPTION_KEY

STILL TO FILL IN BY HAND — the stack will not work without them:

  ADMIN_EMAILS             the email address you registered your account with.
                           Empty means NOBODY is an admin, so no dispute
                           resolution and no manual sweeps. Renamed from
                           ADMIN_PHONES; the old name is ignored, not rejected.
  FEDAPAY_SECRET_KEY       sandbox.fedapay.com -> Developers -> API keys
  FEDAPAY_PUBLIC_KEY       same screen
  FEDAPAY_WEBHOOK_SECRET   the dashboard's Webhooks tab, prefixed wh_.
                           NOT the same value as FEDAPAY_SECRET_KEY.

Then:
  docker compose -f docker-compose.prod.yml up -d --build

EOF
