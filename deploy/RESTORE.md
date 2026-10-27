# Restoring Kolabo

KOL-53. Read section 1 if something is already wrong. Everything else is setup
and rehearsal.

**You need two things and they live in different places.** The dump has the
data. `DOCUMENT_ENCRYPTION_KEY` decrypts the verification documents and the
stored social tokens inside it. A dump restored without the matching key comes
back looking fine: users, contracts, escrows and payments are all readable, and
every KYC document and every social OAuth token is permanently unreadable
ciphertext. Nothing warns you. **The key is not in the backup bucket and
`backup.sh` never writes it anywhere, on purpose.** It is in your password
manager, and if it is not, stop and put it there now.

---

## 1. Restoring, right now

### 1.1 Get a dump

Newest first, on the box:

```bash
ls -lt /var/backups/kolabo/
```

Or from R2, if the box is gone:

```bash
rclone lsl r2:kolabo-backups | sort -k2 | tail -5
rclone copy r2:kolabo-backups/kolabo-srv2032562-20261027T021700Z.sql.gz .
```

**Check the box name in the filename.** Production is `srv2032562`, dev is
`srv1901422`. Restoring the wrong box's data over a live database is a real
mistake and the filename is the only thing standing between you and it.

### 1.2 Restore into a SCRATCH database first, never over the live one

Even when the live database is the thing that is broken. A restore into a
scratch database costs two minutes and tells you whether the dump is good
before you have destroyed the only other copy of anything.

```bash
cd ~/kolabo/deploy

docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d postgres -c 'CREATE DATABASE kolabo_restore_check;'

gunzip -c /var/backups/kolabo/kolabo-srv2032562-20261027T021700Z.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T db \
      psql -U kolabo -d kolabo_restore_check -v ON_ERROR_STOP=1 -q
```

`ON_ERROR_STOP=1` matters. Without it psql prints errors and keeps going, and
you end up with a half restored database that reported success.

Sanity check what arrived:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d kolabo_restore_check -c \
  "select 'users' t, count(*) from users
   union all select 'contracts', count(*) from contracts
   union all select 'escrows', count(*) from escrows
   union all select 'documents', count(*) from verification_documents;"
```

### 1.3 Prove a document still decrypts

This is the step that distinguishes a restore from a restored-shaped thing. Skip
it and you will not know the key matches until somebody needs a document.

```bash
# Pull one document's ciphertext out as base64.
CT=$(docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d kolabo_restore_check -t -A -c \
  "select encode(ciphertext,'base64') from verification_documents limit 1;")

# Decrypt it with the key, without touching the app.
read -rsp 'DOCUMENT_ENCRYPTION_KEY: ' DEK; echo
docker compose -f docker-compose.prod.yml exec -T \
  -e DEK="$DEK" -e CT="$CT" backend python -c '
import base64, os
from cryptography.fernet import Fernet
raw = Fernet(os.environ["DEK"].encode()).decrypt(base64.b64decode(os.environ["CT"]))
print("decrypted", len(raw), "bytes; starts with", raw[:8])
'
unset DEK
```

A `cryptography.fernet.InvalidToken` here means the key does not match this
dump. The data is intact and the documents are gone. There is no recovery from
that except the right key, which is why section 0 is section 0.

If `verification_documents` is empty, there is nothing to prove and that is
fine. Run the drill in section 2 instead, which creates something to prove.

### 1.4 Only now, swap it in

```bash
cd ~/kolabo/deploy
docker compose -f docker-compose.prod.yml stop backend sweeps

docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d postgres -c 'ALTER DATABASE kolabo RENAME TO kolabo_broken;'
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d postgres -c 'ALTER DATABASE kolabo_restore_check RENAME TO kolabo;'

docker compose -f docker-compose.prod.yml start backend sweeps
docker compose -f docker-compose.prod.yml logs -f backend
```

**Renamed, not dropped.** `kolabo_broken` stays until you are sure, because the
broken database may hold rows the dump does not: anything written between the
last backup and the failure. Drop it deliberately, later, when you have looked.

Backend runs `alembic upgrade head` on start, so a dump from an older schema
migrates forward by itself. Watch the log and confirm it reaches head.

---

## 2. The drill, which is what closes KOL-53

**An untested backup is a belief.** Run this once on the dev box now, and again
after any change to `backup.sh` or the Postgres version.

It works on an empty database, because it creates the document it later proves.
Do it on **dev**: it inserts a junk row, which is harmless there.

```bash
cd ~/kolabo/deploy

# 1. Put a document with known contents into the dev database.
read -rsp 'DOCUMENT_ENCRYPTION_KEY: ' DEK; echo
docker compose -f docker-compose.prod.yml exec -T -e DEK="$DEK" backend python -c '
import base64, os
from cryptography.fernet import Fernet
print(base64.b64encode(Fernet(os.environ["DEK"].encode()).encrypt(b"KOL-53 DRILL PAYLOAD")).decode())
' > /tmp/drill.b64

docker compose -f docker-compose.prod.yml exec -T db psql -U kolabo -d kolabo -v ON_ERROR_STOP=1 -c "
insert into verification_documents (id, user_id, doc_type, filename, ciphertext, status, created_at)
select 'kol53-drill', id, 'business_registration', 'drill.pdf',
       decode('$(cat /tmp/drill.b64)','base64'), 'pending', now()
from users limit 1;"

# 2. Take a backup.
bash backup.sh

# 3. Restore it into a scratch database and decrypt the drill row.
DUMP=$(ls -t /var/backups/kolabo/*.sql.gz | head -1)
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d postgres -c 'DROP DATABASE IF EXISTS kolabo_drill;' -c 'CREATE DATABASE kolabo_drill;'
gunzip -c "$DUMP" | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d kolabo_drill -v ON_ERROR_STOP=1 -q

CT=$(docker compose -f docker-compose.prod.yml exec -T db psql -U kolabo -d kolabo_drill -t -A -c \
  "select encode(ciphertext,'base64') from verification_documents where id='kol53-drill';")
docker compose -f docker-compose.prod.yml exec -T -e DEK="$DEK" -e CT="$CT" backend python -c '
import base64, os
from cryptography.fernet import Fernet
raw = Fernet(os.environ["DEK"].encode()).decrypt(base64.b64decode(os.environ["CT"]))
assert raw == b"KOL-53 DRILL PAYLOAD", raw
print("DRILL PASSED: the dump restored and the document decrypted")
'

# 4. Clean up.
unset DEK; rm -f /tmp/drill.b64
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d postgres -c 'DROP DATABASE kolabo_drill;'
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U kolabo -d kolabo -c "delete from verification_documents where id='kol53-drill';"
```

`DRILL PASSED` is the acceptance criterion. Write the date you saw it on
KOL-53.

If step 1 inserts zero rows, the dev database has no users. Register one
through the app first; the drill needs a `user_id` to hang the document off.

---

## 3. One-time setup

### 3.1 rclone and R2

Free tier is 10 GB and a gzipped dump of this database is well under a
megabyte, so the limit is not a concern for a long time. R2 is a different
provider from the VPS, which is the point: a backup on the other Hostinger box
does not survive losing the Hostinger account.

In the Cloudflare dashboard: **R2 -> Create bucket** (`kolabo-backups`), then
**Manage R2 API Tokens -> Create API token**, Object Read and Write, scoped to
that bucket. Keep the account ID, access key ID and secret.

On each box:

```bash
curl https://rclone.org/install.sh | sudo bash
rclone config
```

`n` for new remote, name it `r2`, storage `s3`, provider `Cloudflare`, then the
access key and secret, region `auto`, and endpoint
`https://<accountid>.r2.cloudflarestorage.com`. Leave the rest default.

Check it:

```bash
rclone lsd r2:
```

Then add to `deploy/.env` on each box:

```
BACKUP_DIR=/var/backups/kolabo
BACKUP_KEEP_DAYS=14
R2_REMOTE=r2:kolabo-backups
R2_KEEP_DAYS=90
```

**`R2_REMOTE` unset is a supported state**, not a broken one. `backup.sh` still
dumps, still verifies, and warns on every run that the dump exists only on that
box. So the nightly backup can start before R2 is ready.

### 3.2 The cron

As root on each box:

```bash
crontab -e
```

```
17 2 * * * cd /root/kolabo/deploy && bash backup.sh >> /var/log/kolabo-backup.log 2>&1
```

Confirm it took, and that a manual run works:

```bash
crontab -l
cd ~/kolabo/deploy && bash backup.sh
tail -20 /var/log/kolabo-backup.log
```

### 3.3 What `backup.sh` refuses to do

It exits non-zero and deletes the file when a dump is truncated, when the gzip
is corrupt, or when the dump has no `users` table. A dump cut off halfway by a
full disk is still valid gzip of a plausible size and restores most of the
schema before failing, so "the file exists" proves nothing. The completion
marker pg_dump writes as its last line is what proves it ran to the end.

It also refuses to write into the git working tree. An earlier version of the
README's one-liner had no destination and wrote a dump into `deploy/`, one
`git add -A` away from putting every user row and every document ciphertext
into this repository's history.

---

## 4. Retention

| Where | Default | Setting |
|---|---|---|
| On the box | 14 days | `BACKUP_KEEP_DAYS` |
| In R2 | 90 days | `R2_KEEP_DAYS` |

Pruning is scoped by filename to the box that wrote the file, so two boxes
sharing one bucket never delete each other's history.

Set either to `0` to keep everything. At this data volume that is a defensible
choice for a while, and it is not the default because "keep everything" quietly
becomes the reason a disk fills up at 2am, which is how you get a truncated
dump.
