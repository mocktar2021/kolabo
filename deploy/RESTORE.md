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

R2 is a different provider from the VPS, which is the point: a backup on the
other Hostinger box does not survive losing the Hostinger account.

**The free tier is 10 GB and that is comfortable, not tight.** Measured rather
than guessed: the dev box dumps to 6.4 MB gzipped, so 90 days of retention is
about 580 MB per box and roughly 1.2 GB for both. An earlier version of this
file said "well under a megabyte", which was wrong by a factor of six. Recheck
the arithmetic if a dump ever gets into the tens of megabytes, because at 100
MB a day two boxes would reach the free tier in a bit over six months.

#### The bucket and the token

In the Cloudflare dashboard: **R2 Object Storage -> Create bucket**
(`kolabo-backups`). Then, in the **Account Details** panel on that page,
**Manage** next to **API Tokens -> Create Account API token**, permission
**Object Read & Write**, scoped to that bucket, **no expiration**. Keep the
account ID, the Access Key ID and the Secret Access Key: the secret is shown
once.

The general **Account API Tokens** builder also works, with the permission
group *Workers R2 Storage Bucket Item* at Read and Edit scoped to the bucket.
That is recorded because a previous version of this file blamed that flow for a
403 it did not cause. See the jurisdiction note below for what actually caused
it.

#### NOTE THE BUCKET'S JURISDICTION. THIS IS THE ONE THAT COSTS AN HOUR.

A bucket created in a jurisdiction is reachable **only** through that
jurisdiction's endpoint:

| Bucket | Endpoint |
|---|---|
| Automatic, no jurisdiction | `https://<accountid>.r2.cloudflarestorage.com` |
| **EU** | `https://<accountid>.eu.r2.cloudflarestorage.com` |

**`kolabo-backups` is an EU bucket, so it needs the `.eu.` endpoint.** The
bucket list shows the jurisdiction as a small tag beside the name.

Cloudflare answers a wrong-jurisdiction request with **403 Forbidden** and
**AccessDenied**, saying nothing about endpoints, so it reads exactly like a
permissions problem and sends you off to rebuild a token that was fine.

#### rclone

**Not the Debian package.** Debian 13 ships rclone v1.60.1 from 2022, and every
R2 upload fails on the first attempt with `501 NotImplemented` and succeeds on
the retry, deterministically. The backup still works, while logging an ERROR on
every single run, which is how a job teaches you to ignore its errors.
`backup.sh` refuses to run against anything below 1.70 for that reason.

The official installer needs `unzip`, which the minimal image lacks:

```bash
apt-get install -y unzip
curl https://rclone.org/install.sh | sudo bash
rclone version | head -1
```

Write the config directly rather than using `rclone config`, so no credential
reaches your shell history:

```bash
mkdir -p ~/.config/rclone
read -rp  'Cloudflare account ID: ' ACC
read -rp  'R2 Access Key ID: ' KID
read -rsp 'R2 Secret Access Key: ' SEC; echo
ACC=$(printf '%s' "$ACC" | grep -oE '[0-9a-f]{32}')
cat > ~/.config/rclone/rclone.conf <<CONF
[r2]
type = s3
provider = Cloudflare
region = auto
no_check_bucket = true
access_key_id = $KID
secret_access_key = $SEC
endpoint = https://$ACC.eu.r2.cloudflarestorage.com
acl = private
CONF
chmod 600 ~/.config/rclone/rclone.conf
unset KID SEC
```

Paste each `read` line **on its own**. Pasted as one block, `read` swallows the
next line of the paste as the value.

`region = auto` is what R2 expects. `no_check_bucket = true` matters more:
rclone checks a bucket exists before acting, which is a bucket-level operation
a correctly scoped token is denied.

#### Checking it

**Not `rclone lsd r2:`.** That lists buckets, an account-level operation your
object-scoped token cannot do, so it returns 403 even when everything is
correct. An earlier version of this file told you to verify with exactly that
command.

Do a round trip inside the bucket instead, which is what `backup.sh` actually
needs:

```bash
echo "check $(date -u +%FT%TZ)" > /tmp/r2test.txt
rclone copy /tmp/r2test.txt r2:kolabo-backups/
rclone ls   r2:kolabo-backups
rclone cat  r2:kolabo-backups/r2test.txt
rclone delete r2:kolabo-backups/r2test.txt
rclone ls   r2:kolabo-backups
rm -f /tmp/r2test.txt
```

The file listed, its contents echoed, then an empty listing. That is write,
read and delete confirmed, which covers the upload, the size check and the
prune.

#### The settings

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

### 3.2 The schedule

**These boxes ship without cron.** Debian 13 minimal has no `crontab` binary,
and installing one would be the worse answer anyway. KOL-53 asks that backup
failure be visible, and the usual failure is a schedule that quietly stopped
weeks ago. A crontab that is no longer there looks exactly like one that is. A
systemd timer can be interrogated.

The units live in the repository, so `git pull` updates them. As root on each
box:

```bash
ln -sf /root/kolabo/deploy/systemd/kolabo-backup.service /etc/systemd/system/
ln -sf /root/kolabo/deploy/systemd/kolabo-backup.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kolabo-backup.timer
```

Confirm it is scheduled, then force one run and read the result:

```bash
systemctl list-timers kolabo-backup.timer
systemctl start kolabo-backup.service
systemctl status kolabo-backup.service
journalctl -u kolabo-backup.service -n 20 --no-pager
```

**After a `git pull` that changes either unit file, run `systemctl
daemon-reload`.** The symlink points at the working tree, so the new content is
there immediately, but systemd keeps its parsed copy until told otherwise.

Three commands worth remembering, because they are the answer to "is the backup
actually running":

| Question | Command |
|---|---|
| When did it last run, when does it run next | `systemctl list-timers kolabo-backup.timer` |
| How did the last run exit | `systemctl status kolabo-backup.service` |
| What did it print, every run | `journalctl -u kolabo-backup.service` |

`Persistent=true` is on, so a run missed because the box was down fires on the
next boot rather than being skipped. That is the behaviour cron does not have
and it matters most on the kind of box where you want backups.

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

### 3.4 Who watches the schedule

A nightly job does not usually fail loudly. It fails as a unit somebody
disabled, a symlink that broke after a `git pull` with no `daemon-reload`, or a
script that started exiting non-zero into a journal nobody reads. Weeks later
somebody needs a restore and the newest dump is from last month. That is the
failure KOL-53 names, and the three `systemctl` commands above only find it if
somebody runs them.

So the **sweeps container** reads `BACKUP_DIR/last-success` on every pass. It is
there rather than in a second timer on purpose: a watcher that shares a
mechanism with the thing it watches is not a watcher. If the timer system is
what stopped, a watching timer stopped with it. The sweeps container is a
different process under a different supervisor, already waking up every five
minutes for reasons of its own.

`docker-compose.prod.yml` bind mounts `BACKUP_DIR` into that container **read
only**, at the same path inside as outside, so one setting means one thing in
`backup.sh`, in the compose file and in the check. The container can read the
marker and cannot touch a dump.

| Setting | Default | What it does |
|---|---|---|
| `BACKUP_MAX_AGE_HOURS` | 36 | How old the last verified backup may get. The timer is nightly, so a healthy gap is about 24. `0` switches the check off. |
| `BACKUP_ALERT_INTERVAL_HOURS` | 24 | How often it may email `ADMIN_EMAILS`. The log gets a line every pass; `0` keeps the log line and sends no mail. |

What it says, and where:

```bash
docker compose -f docker-compose.prod.yml logs sweeps | grep BACKUP
```

- `BACKUP STALE` with an age and the two commands to run next.
- `BACKUP NEVER` when the directory is mounted and holds no marker at all,
  which is a box that has prod compose and no verified backup.
- `BACKUP UNREADABLE` when the marker is there and is not a timestamp.
- Nothing at all when the directory is not mounted. A laptop on the
  development compose file is not a box that failed to back up, and a logger
  that cries wolf is one an operator learns to ignore.

**Two things it cannot promise, stated so that silence is not read as health.**
The email path swallows its own delivery failures by design, so a Resend outage
leaves the warning in the sweeps log only. And `ADMIN_EMAILS` empty means the
warning reaches nobody; the check says that in the log too, once a day, rather
than appearing to have sent something.

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
