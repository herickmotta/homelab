# data_platform

Pinned minimal self-hosted Supabase subset for a dedicated data guest.
Defaults stay `enabled: false`. Postgres and Studio bind loopback. Kong
`:8000` is LAN-published behind a host INPUT allowlist. JWT is required by
PostgREST. Unused Supabase products (Realtime, Storage, Functions, analytics)
are omitted from Compose.

SQL migrations create only `ops_ledger`. GoTrue owns schema `auth`
(Postgres 15 no longer lets it create `schema_migrations` in `public`
without an explicit GRANT). Mint HS256 JWTs with
`files/mint_jwt.py` (read the secret from stdin; do not log the token):

```bash
printf '%s' "$JWT_SECRET" | python3 files/mint_jwt.py --role anon
printf '%s' "$JWT_SECRET" | python3 files/mint_jwt.py --role service_role
printf '%s' "$JWT_SECRET" | python3 files/mint_jwt.py --role ops_ledger_hermes
```

Backup: nightly `pg_dump` custom format plus `--roles-only` from the pinned
db container (so restore matches the image, not host postgresql-client),
age-encrypted onto `data_platform_backup_dir` (a site may VirtioFS that path
from healthy `iron` storage). S3 upload stays optional and off by default. `state: absent`
keeps `/opt/data-platform/data` and the backup directory. Restore into a
disposable directory with `restore.sh`; do not import onto the live volume
for proof.

Do not give Hermes the service-role key, dump age identity, or backup IAM.
