# Reviewer runbook

Start OmniRoute on this machine at port `20128` before the containers. The API reaches it as `http://host.docker.internal:20128/v1`. Hermes and OmniRoute settings stay as they are.

```bash
docker compose up --build
```

Desk: `http://127.0.0.1:8420`. API: `http://127.0.0.1:8421/health`.

Sign in with `reviewer@desert-ledger.example` / `ledger-demo-1`. Load the seeded batch. Watch the trace. The validator returns `DL-INV-1002` once, then leaves it `to verify` because the buyer identifier is still missing. Ask the Arabic question about AED 375,000. The English citation from the corporate-tax guide sits beside the desk translation. The auditor disagrees on `DL-INV-1005` (free zone) and `DL-INV-1004` (revenue conflict). `DL-INV-1006` prefers source T4 over the July 2026 date in T2. Approve the bounded pack. It is not a return and nothing is sent to an ASP.

The quiz score is a training score.

## Residency

`GET /api/residency` shows the storage path, the backup path, the log note, the OmniRoute URL, and `residency_verified: false`. A localhost URL does not prove where the upstream model processes data. `POST /api/documents` with `synthetic=false` returns 403 and does not call the model.

Set `RESIDENCY_VERIFIED=true` only after someone has checked the provider’s processing location and retention terms. The demo fixtures stay synthetic either way.

The tenant database and uploads sit on the `tenant` volume, encrypted with `TENANT_VOLUME_KEY`. Backups go to the `backup` volume. `POST /api/admin/backup` copies the database file. `DELETE /api/tenants/tenant_desert_ledger?actor=reviewer` removes that tenant’s documents and writes an audit row. Restarting the containers keeps the audit rows on the volume.

Logs stay on the container’s own stdout. The compose file does not add a remote log sink.

## If the gateway is down

```bash
LLM_MODE=replay docker compose up --build
```

The trace is labelled as a replay.

## Incident

See [incident.md](incident.md).
