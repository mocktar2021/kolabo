#!/usr/bin/env bash
#
# Nightly Postgres dump, verified, copied off the box, pruned. KOL-53.
#
#   cd kolabo/deploy && bash backup.sh
#
# INSTALL IT AS A CRON JOB, because a backup somebody has to remember is not a
# backup. As root on each box:
#
#   crontab -e
#   17 2 * * * cd /root/kolabo/deploy && bash backup.sh >> /var/log/kolabo-backup.log 2>&1
#
# 02:17 rather than 02:00 on purpose: every other cron on every other box runs
# on the hour, and a dump competing with somebody else's for disk and CPU is
# slower for no reason.
#
# WHAT THIS PROTECTS, and it is everything. verification_documents.ciphertext
# and the social OAuth access and refresh tokens are LargeBinary columns in
# Postgres, not files on disk, so pg_dump is the whole backup. There is no
# second store to think about.
#
# WHICH IS ALSO THE TRAP. The dump is useless without DOCUMENT_ENCRYPTION_KEY
# and dangerous beside it:
#
#   Restored WITHOUT the key, every verification document and every stored
#   social token is permanently unreadable ciphertext. The rest of the data
#   comes back fine, which is what makes this easy to discover too late.
#
#   Stored WITH the key in the same place, whoever takes a copy of the backup
#   has the KYC documents and live social tokens in plaintext.
#
# So the key belongs somewhere this script never writes to: a password manager,
# not this box and not the backup bucket. THIS SCRIPT DELIBERATELY DOES NOT
# BACK UP THE KEY. See RESTORE.md.
#
# CONFIGURATION, all read from deploy/.env, all optional except what compose
# already needs:
#
#   BACKUP_DIR         where dumps land. Default /var/backups/kolabo.
#                      Must be OUTSIDE the git working tree. An earlier version
#                      of the README's one-liner had no destination and wrote a
#                      dump into deploy/, one `git add -A` away from putting
#                      every user row into the repository's history.
#   BACKUP_KEEP_DAYS   local retention. Default 14.
#   R2_REMOTE          an rclone remote and path, e.g. r2:kolabo-backups.
#                      UNSET MEANS LOCAL ONLY: the dump still runs, is still
#                      verified, and the script warns loudly that there is no
#                      off-box copy. That is so a nightly backup can start
#                      tonight and the off-box leg can be switched on later
#                      without editing this file.
#   R2_KEEP_DAYS       remote retention. Default 90.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE=(docker compose -f docker-compose.prod.yml)

log() { printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "FAILED: $*"; exit 1; }

# ---------------------------------------------------------------- one at a time
#
# Two dumps at once would compete for the same disk and could interleave into
# the same filename. flock makes a second run exit rather than queue, because a
# backup that is already running does not need a second opinion.
exec 9>/tmp/kolabo-backup.lock
flock -n 9 || die "another backup is already running"

# ------------------------------------------------------------------ the config
[[ -f .env ]] || die "deploy/.env not found; run this from kolabo/deploy"

# READ VALUES WITHOUT SOURCING THE FILE, which is the convention
# checks/preflight-env.sh established and wrote the reason beside: nothing in
# .env is executed, because a value containing a backtick or a $( would
# otherwise run as this script's user, and that file holds POSTGRES_PASSWORD,
# JWT_SECRET, DOCUMENT_ENCRYPTION_KEY and META_APP_SECRET.
#
# It matters more here than there. This script runs as root, from cron, with
# nobody watching.
get() {
  sed -n "s/^[[:space:]]*$1=//p" ./.env | tail -n 1 \
    | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'\$/\1/"
}

POSTGRES_USER="$(get POSTGRES_USER)"
POSTGRES_DB="$(get POSTGRES_DB)"
[[ -n "$POSTGRES_USER" ]] || die "POSTGRES_USER is not set in deploy/.env"
[[ -n "$POSTGRES_DB" ]] || die "POSTGRES_DB is not set in deploy/.env"

BACKUP_DIR="$(get BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/var/backups/kolabo}"
BACKUP_KEEP_DAYS="$(get BACKUP_KEEP_DAYS)"; BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
R2_REMOTE="$(get R2_REMOTE)"
R2_KEEP_DAYS="$(get R2_KEEP_DAYS)"; R2_KEEP_DAYS="${R2_KEEP_DAYS:-90}"

# NOT INSIDE THE REPOSITORY, and the check is against the repository root
# rather than against this directory. An earlier version compared with $PWD,
# which is deploy/, so /root/kolabo/backups would have passed and then sat in
# the working tree, one `git add -A` away from putting every user row and every
# document ciphertext into this repository's history. That has nearly happened
# once already, which is why deploy/README.md §9 carries the same warning.
#
# readlink -m rather than realpath: it canonicalises a path that does not exist
# yet, which BACKUP_DIR usually does not on a first run.
REPO_ROOT="$(cd .. && pwd -P)"
BACKUP_ABS="$(readlink -m "$BACKUP_DIR")"
case "$BACKUP_ABS/" in
  "$REPO_ROOT"/*) die "BACKUP_DIR is inside the git tree ($REPO_ROOT): $BACKUP_DIR" ;;
esac
BACKUP_DIR="$BACKUP_ABS"

# The box name is in the filename so that a shared bucket cannot confuse the
# production dump with the dev one. Restoring the wrong box's data over a live
# database is not a mistake anybody should be one filename away from.
BOX="$(hostname -s 2>/dev/null || echo unknown)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
NAME="kolabo-${BOX}-${STAMP}.sql.gz"
DEST="${BACKUP_DIR}/${NAME}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# ------------------------------------------------------------------- the dump
#
# Plain SQL, gzipped, rather than pg_dump -Fc. Custom format restores
# selectively and in parallel, which is the better tool on a big database and
# the wrong one here: the person running RESTORE.md is panicking, and
# `gunzip | psql` is one pipe they can read, inspect and reason about, where
# pg_restore is a second command with its own flags to get wrong at 3am.
log "dumping ${POSTGRES_DB} from ${BOX}"
if ! "${COMPOSE[@]}" exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
     | gzip -9 > "$DEST"; then
  rm -f "$DEST"
  die "pg_dump or gzip failed (is the db container up?)"
fi
chmod 600 "$DEST"

# -------------------------------------------------------------- the verification
#
# THIS IS THE PART THAT MAKES IT A BACKUP RATHER THAN A FILE. A dump cut off
# halfway, by a full disk or a container killed mid-write, is still a valid
# gzip of a partial file: it decompresses cleanly, it has a plausible size, and
# it restores most of the schema before failing. Nothing about it looks wrong
# until the day it is needed.
#
# pg_dump writes a completion marker as the last line of its output, so the
# presence of that line is proof the dump ran to the end rather than being
# truncated. Checked on every run, and a dump that fails is deleted rather than
# left to be found and trusted.
log "verifying ${NAME}"
gzip -t "$DEST" 2>/dev/null || { rm -f "$DEST"; die "the dump is not valid gzip"; }

if ! gunzip -c "$DEST" | tail -5 | grep -q 'PostgreSQL database dump complete'; then
  rm -f "$DEST"
  die "the dump has no completion marker, so it is truncated; deleted it"
fi

# A completion marker on an empty database is still a completion marker, so
# check that the thing actually contains the tables we expect. `users` is the
# one table no Kolabo database can be missing.
if ! gunzip -c "$DEST" | grep -qE 'CREATE TABLE (public\.)?users'; then
  rm -f "$DEST"
  die "the dump has no users table, so it is not a Kolabo database; deleted it"
fi

SIZE="$(du -h "$DEST" | cut -f1)"
log "ok: ${DEST} (${SIZE})"

# ----------------------------------------------------------------- off the box
#
# A backup on the same disk as the database is not a backup. It survives a
# dropped table and a bad migration, which is worth having, and it does nothing
# at all about the failure this ticket exists for: losing the box.
if [[ -z "$R2_REMOTE" ]]; then
  log "WARNING: R2_REMOTE is unset, so this dump exists ONLY on this box."
  log "WARNING: losing ${BOX} still loses every contract, escrow and document."
  log "WARNING: see deploy/RESTORE.md for the rclone setup that closes this."
elif ! command -v rclone >/dev/null 2>&1; then
  die "R2_REMOTE is set but rclone is not installed; see deploy/RESTORE.md"
else
  log "copying to ${R2_REMOTE}"
  rclone copyto "$DEST" "${R2_REMOTE}/${NAME}" --s3-no-check-bucket \
    || die "rclone could not upload to ${R2_REMOTE}"

  # Confirm it is THERE rather than trusting that the command exited zero. A
  # verified local dump and a successful-looking upload still leaves the
  # question of whether the bytes arrived, and that question is cheap to close.
  REMOTE_SIZE="$(rclone size "${R2_REMOTE}/${NAME}" --json 2>/dev/null \
    | sed -n 's/.*"bytes":\([0-9]*\).*/\1/p')"
  LOCAL_SIZE="$(stat -c %s "$DEST")"
  if [[ "$REMOTE_SIZE" != "$LOCAL_SIZE" ]]; then
    die "uploaded ${LOCAL_SIZE} bytes but the remote reports '${REMOTE_SIZE}'"
  fi
  log "ok: ${R2_REMOTE}/${NAME} (${LOCAL_SIZE} bytes)"

  if [[ "$R2_KEEP_DAYS" -gt 0 ]]; then
    rclone delete "$R2_REMOTE" --min-age "${R2_KEEP_DAYS}d" \
      --include "kolabo-${BOX}-*.sql.gz" 2>/dev/null \
      || log "WARNING: remote prune failed; backups still uploaded fine"
  fi
fi

# ------------------------------------------------------------------- the prune
#
# Scoped to this box's own files by name. A shared bucket mounted locally, or
# two boxes writing to one directory, must not have one of them deleting the
# other's history.
if [[ "$BACKUP_KEEP_DAYS" -gt 0 ]]; then
  find "$BACKUP_DIR" -maxdepth 1 -name "kolabo-${BOX}-*.sql.gz" \
    -mtime "+${BACKUP_KEEP_DAYS}" -print -delete
fi

# The file the staleness check reads. Written LAST and only on success, so its
# timestamp means "a verified dump completed", not "the script started".
date -u +%Y-%m-%dT%H:%M:%SZ > "${BACKUP_DIR}/last-success"
chmod 600 "${BACKUP_DIR}/last-success"

log "done"
