#!/usr/bin/env bash
#
# Refuse to deploy on a deploy/.env that cannot work, BEFORE anything starts.
#
#   cd kolabo/deploy && bash checks/preflight-env.sh
#
# WHAT THIS EXISTS TO CATCH, and why it is a script rather than a paragraph in
# the README: this deployment carries five URLs that all have to agree with two
# hostnames, and every single one of them has been wrong at least once, each
# time with no error message anywhere.
#
#   API_PUBLIC_BASE_URL was absent, so every OAuth redirect_uri was built
#   against localhost and Meta refused the handshake before drawing a consent
#   screen. Nothing in any log named the variable.
#
#   WEB_PUBLIC_BASE_URL was absent, so the callback refused the web app's own
#   redirect_to, logged one WARNING line that no logging configuration was
#   surfacing at the time, and completed the connection anyway.
#
#   VITE_API_URL is compiled into the browser bundle, so a wrong value is a web
#   app that cannot reach its api and a `restart` that does not fix it.
#
# A deployment is not safer for having a human promise to check these. It is
# safer for refusing to start.
#
# WHAT THIS DELIBERATELY DOES NOT CHECK. The secrets. config.py's
# _refuse_committed_secrets_in_production validator already refuses to boot with
# ENV=production while JWT_SECRET or DOCUMENT_ENCRYPTION_KEY is the committed
# default, or while FEDAPAY_SECRET_KEY is set with no webhook secret. That check
# lives next to the values it reads and runs on every boot, not only when
# somebody remembers a script. Two copies of one rule is how they drift.
#
# Exit 0 clean, 1 on any error. Warnings alone do not fail the run.

set -uo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=".env"

errors=0
warnings=0

fail() { printf '  FAIL  %s\n' "$1"; errors=$((errors + 1)); }
warn() { printf '  WARN  %s\n' "$1"; warnings=$((warnings + 1)); }
ok()   { printf '  ok    %s\n' "$1"; }

if [[ ! -f "$ENV_FILE" ]]; then
  echo "No deploy/.env. Run bash bootstrap-env.sh first."
  exit 1
fi

# Read a value without sourcing the file. Nothing in .env is executed: a value
# containing a backtick or a $( would otherwise run as this script's user, and
# the file holds every credential the stack has.
get() {
  sed -n "s/^[[:space:]]*$1=//p" "$ENV_FILE" | tail -n 1 \
    | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

echo
echo "deploy/.env preflight"
echo

# ----------------------------------------------------------------- required
for key in \
  POSTGRES_USER POSTGRES_DB POSTGRES_PASSWORD \
  ENV JWT_SECRET DOCUMENT_ENCRYPTION_KEY \
  WEB_HOSTNAME API_HOSTNAME ACME_EMAIL ACME_CA \
  CORS_ORIGINS API_PUBLIC_BASE_URL WEB_PUBLIC_BASE_URL \
  PAYMENT_RETURN_URL VITE_API_URL
do
  if [[ -z "$(get "$key")" ]]; then
    fail "$key is empty"
  fi
done

APP_ENV="$(get ENV)"
WEB_HOST="$(get WEB_HOSTNAME)"
API_HOST="$(get API_HOSTNAME)"

# --------------------------------------------------------------------- env
case "$APP_ENV" in
  development|production) ok "ENV=$APP_ENV" ;;
  "")                     ;;  # already reported as empty above
  *)                      fail "ENV=$APP_ENV is neither development nor production" ;;
esac

# --------------------------------------------------------------- hostnames
# Hostnames, not URLs. Caddy uses each one as a site address, so a scheme or a
# path here is a config Caddy will not parse, and a port would be a site it
# never serves on 443.
hostnames_ok=1
for pair in "WEB_HOSTNAME:$WEB_HOST" "API_HOSTNAME:$API_HOST"; do
  key="${pair%%:*}"; val="${pair#*:}"
  if [[ -z "$val" ]]; then hostnames_ok=0; continue; fi
  if [[ "$val" == *://* ]];      then fail "$key must be a hostname with no scheme: $val"; hostnames_ok=0
  elif [[ "$val" == */* ]];      then fail "$key must be a hostname with no path: $val"; hostnames_ok=0
  elif [[ "$val" == *:* ]];      then fail "$key must be a hostname with no port: $val"; hostnames_ok=0
  elif [[ "$val" != *.* ]];      then fail "$key does not look like a public hostname: $val"; hostnames_ok=0
  elif [[ "$val" =~ [[:space:]] ]]; then fail "$key contains whitespace: $val"; hostnames_ok=0
  else ok "$key=$val"
  fi
done

# ----------------------------------------------------------------- acme ca
# WHICH LET'S ENCRYPT ENDPOINT, checked here because the cost of getting this
# one wrong is measured in days rather than minutes. Five certificates per
# hostname per week, failed challenges counted, no appeal and no override: a
# first boot that goes straight at the production endpoint and fails on DNS
# that has not propagated, or on a typo in a hostname, can leave the real name
# unable to get a certificate until the window rolls. A new box does its first
# boot on staging and is switched afterwards.
#
# THE SELECTED ENDPOINT IS NAMED ON EVERY RUN, not only when it is wrong. A box
# left on staging serves certificates signed by a CA no browser trusts while
# looking entirely healthy in its own logs, so it is not a state anybody
# discovers from the server side.
acme_ca="$(get ACME_CA)"
le_production="https://acme-v02.api.letsencrypt.org/directory"
le_staging="https://acme-staging-v02.api.letsencrypt.org/directory"
case "$acme_ca" in
  "")
    ;;  # already reported as empty above
  "$le_production")
    ok "ACME_CA is the Let's Encrypt production endpoint"
    ;;
  "$le_staging")
    warn "ACME_CA is the Let's Encrypt STAGING endpoint: certificates will be signed by a CA no browser trusts and every visitor sees a security warning. Right for the first boot of a new box, wrong for anything anyone is meant to use."
    ;;
  https://*)
    warn "ACME_CA is neither Let's Encrypt endpoint: $acme_ca"
    ;;
  *)
    fail "ACME_CA must be an https ACME directory URL: $acme_ca"
    ;;
esac

# ------------------------------------------------------- the five agreements
expect() {
  local key="$1" want="$2" got
  got="$(get "$key")"
  [[ -z "$got" ]] && return 0        # already reported
  if [[ "$got" == "$want" ]]; then
    ok "$key=$got"
  else
    fail "$key=$got but the hostnames above imply $want"
  fi
}

# Only worth comparing once the hostnames themselves are well formed. Deriving
# an expected URL from a malformed hostname produces advice like
# "https://https://host//checkout/return", which sends the reader after the
# wrong line.
if (( hostnames_ok )); then
  expect API_PUBLIC_BASE_URL "https://$API_HOST"
  expect WEB_PUBLIC_BASE_URL "https://$WEB_HOST"
  expect VITE_API_URL        "https://$API_HOST"
  expect PAYMENT_RETURN_URL  "https://$WEB_HOST/checkout/return"

  # CORS_ORIGINS is the one that is allowed to carry more than one value, so it
  # is checked by membership rather than by equality.
  cors="$(get CORS_ORIGINS)"
  if [[ -n "$cors" ]]; then
    if [[ ",$cors," == *",https://$WEB_HOST,"* ]]; then
      ok "CORS_ORIGINS=$cors"
    else
      fail "CORS_ORIGINS=$cors does not include https://$WEB_HOST"
    fi
  fi
fi

# A trailing slash on a base url is a doubled slash in every URL built from it,
# and OAuth compares redirect_uri byte for byte.
for key in API_PUBLIC_BASE_URL WEB_PUBLIC_BASE_URL VITE_API_URL; do
  val="$(get "$key")"
  [[ "$val" == */ ]] && fail "$key has a trailing slash: $val"
done

# ------------------------------------------------------------------ admins
admins="$(get ADMIN_EMAILS)"
if [[ -z "$admins" ]]; then
  warn "ADMIN_EMAILS is empty: nobody is an admin, so no dispute resolution and no manual sweeps"
elif [[ "$admins" == *"you@example.com"* ]]; then
  fail "ADMIN_EMAILS still contains the example address you@example.com"
else
  ok "ADMIN_EMAILS=$admins"
fi

# ------------------------------------------------------------------- meta
meta_id="$(get META_APP_ID)"; meta_secret="$(get META_APP_SECRET)"
if [[ -n "$meta_id" && -z "$meta_secret" ]] || [[ -z "$meta_id" && -n "$meta_secret" ]]; then
  fail "META_APP_ID and META_APP_SECRET must both be set or both be empty; one alone leaves the Facebook connect button answering oauth_platform_unsupported"
fi

# -------------------------------------------------------------------- mail
# PRODUCTION HAS TO BE ABLE TO SEND, and this is the one required pair that
# app/core/config.py deliberately does NOT enforce. That validator refuses a
# secret still sitting at a value published in this repository, because such a
# default is an open door; it says in as many words that an unset mail key is
# "no door at all" and that a deployment which has not set one "should quietly
# send no mail rather than refuse to boot". That reasoning is right for the
# validator. It is wrong about production, for one reason:
#
# QUIETLY SENDING NO MAIL IS NOT WHAT HAPPENS. Both halves are needed, and
# missing either one takes the same path. notifications/email.py
# build_default_email_sender returns the real provider only when
# RESEND_API_KEY and MAIL_FROM are both set and returns LoggingEmailSender
# otherwise; auth/otp.py build_default_sender sees that and returns its own
# LoggingSender, which writes the code to the log and answers
# SendResult(ok=True). So a production box missing either value tells every
# person registering that their code is on the way, writes the code into the
# container log, sends nothing, and NOBODY CAN EVER VERIFY AN ACCOUNT.
# Registration looks like it works, which is the expensive kind of silence
# this whole script exists to catch.
#
# Development is untouched, and has to be: a laptop and the test suite have no
# mail credentials and must keep printing the code, which is how anybody works
# locally.
if [[ "$APP_ENV" == "production" ]]; then
  mail_ok=1
  for key in RESEND_API_KEY MAIL_FROM; do
    if [[ -z "$(get "$key")" ]]; then
      fail "$key is empty with ENV=production: every verification code would be logged instead of sent, and no account could be verified"
      mail_ok=0
    fi
  done
  if (( mail_ok )); then
    ok "mail is configured for production"
  fi
fi

# ------------------------------------------------------------- informational
if [[ "$APP_ENV" == "production" && "$(get FEDAPAY_SANDBOX)" == "true" ]]; then
  echo
  echo "  note  ENV=production with FEDAPAY_SANDBOX=true. That is the correct"
  echo "        state for an environment that is still dark. Flipping it is a"
  echo "        separate, deliberate act at go-live."
fi

if [[ "$APP_ENV" == "production" && "$acme_ca" == "$le_staging" ]]; then
  echo
  echo "  note  ENV=production with the STAGING certificate authority. That is"
  echo "        the right combination for the dry run of a new box and the"
  echo "        wrong one for a box anybody is using. Switch ACME_CA to the"
  echo "        production endpoint, run up.sh again, and check the served"
  echo "        certificate from somewhere other than this box."
fi

# --------------------------------------------------------------------- done
echo
if (( errors > 0 )); then
  echo "$errors problem(s), $warnings warning(s). NOT ready. Fix deploy/.env and run this again."
  exit 1
fi
echo "No problems, $warnings warning(s). deploy/.env is consistent."
echo
echo "Run from deploy/:  bash up.sh   (which is what just called this)"
exit 0
