# data_platform

Pinned minimal self-hosted Supabase subset for a dedicated data guest.
Defaults stay `enabled: false`. Postgres and Studio bind loopback. Kong
`:8000` is LAN-published behind a host INPUT allowlist. JWT is required by
PostgREST. Unused Supabase products (Realtime, Storage, Functions, analytics)
are omitted from Compose.

SQL migrations create only `ops_ledger`. Mint HS256 JWTs with
`files/mint_jwt.py` (read the secret from stdin; do not log the token):

```bash
printf '%s' "$JWT_SECRET" | python3 files/mint_jwt.py --role anon
printf '%s' "$JWT_SECRET" | python3 files/mint_jwt.py --role service_role
printf '%s' "$JWT_SECRET" | python3 files/mint_jwt.py --role ops_ledger_hermes
```

Backup: nightly `pg_dump` custom format plus `--roles-only`, age-encrypted,
one local generation, S3 upload with a dedicated IAM user. `state: absent`
keeps `/opt/data-platform/data`. Restore into a disposable directory with
`restore.sh`; do not import onto the live volume for proof.

Do not give Hermes the service-role key or backup IAM credentials.
