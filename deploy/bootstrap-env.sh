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
  echo "Delete it first if you really mean to regenerate every secret."
  echo "Note that rotating JWT_SECRET signs out every user, and rotating"
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

# Fernet needs a specific shape (32 url-safe base64 encoded bytes), so this
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

WHICH ENVIRONMENT IS THIS BOX. Answer it first, because the eight values
below all follow from the answer and nothing in .env.example names a deployment
any more. It used to: this file copied the dev box's own hostnames onto every
new server, which booted clean and pointed at the wrong environment.

  ENV                      development or production, and not decorative.
                           development PRINTS EVERY OTP CODE to the container
                           logs, advertises mock payments, and serves /docs.
                           A production box says production, before first boot.

  WEB_HOSTNAME             the two names this box answers on, hostnames only,
  API_HOSTNAME             no scheme and no path. Caddy takes them straight
                           from this file as its site addresses and gets a
                           certificate for each, so their DNS must already
                           point here. Either one unset is a caddy container
                           that refuses to start.

  ACME_CA                  which Let's Encrypt endpoint Caddy asks. Shipped as
                           the real one, so nothing inherits the other by
                           accident. ON A NEW BOX, POINT IT AT STAGING FOR THE
                           FIRST BOOT: five certificates per hostname per week,
                           failed challenges counted, so DNS that has not
                           propagated or a typo in a hostname can spend the
                           allowance before the name is even right. Staging
                           issues certificates signed by a CA no browser
                           trusts, and that warning is the success signal on a
                           dry run. Then switch to the real endpoint, run up.sh
                           again, and check what is served from off this box.

THE FIVE URLS THAT MUST AGREE WITH THOSE TWO HOSTNAMES. Every one of them has
been wrong at least once, each time with no error message anywhere:

  CORS_ORIGINS             https://$WEB_HOSTNAME
  API_PUBLIC_BASE_URL      https://$API_HOSTNAME
  WEB_PUBLIC_BASE_URL      https://$WEB_HOSTNAME
  PAYMENT_RETURN_URL       https://$WEB_HOSTNAME/checkout/return
  VITE_API_URL             https://$API_HOSTNAME   (compiled into the web
                           bundle, so changing it needs a rebuild and not a
                           restart)

AND THE REST:

  ADMIN_EMAILS             the email address you registered your account with.
                           Empty means NOBODY is an admin, so no dispute
                           resolution and no manual sweeps. Renamed from
                           ADMIN_PHONES; the old name is ignored, not rejected.
  FEDAPAY_SECRET_KEY       sandbox.fedapay.com -> Developers -> API keys
  FEDAPAY_PUBLIC_KEY       same screen
  FEDAPAY_WEBHOOK_SECRET   the dashboard's Webhooks tab, prefixed wh_.
                           NOT the same value as FEDAPAY_SECRET_KEY.

Then ONE COMMAND brings it up. It runs the preflight first and refuses to start
anything if deploy/.env cannot work, which matters because a box that starts on
a bad hostname still spends one of Let's Encrypt's five certificate attempts per
hostname per week:

  bash up.sh

To see the preflight's findings without starting anything:

  bash checks/preflight-env.sh

EOF
