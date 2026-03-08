# Pilot Notes

## Longs (this repo)

- Bootstrap apply command succeeded:
  - `scripts/bootstrap-client.sh --client-root <repo> --pgservice longs --pgroservice longs_ai_ro --force`
- Generated/updated:
  - `.cursor/mcp.json`
  - `postgres-language-server.jsonc`
  - `.envrc` managed block

## VanBrock (additional client dry-run)

- Dry-run command executed and failed fast in validation:
  - missing `~/.pgpass` match for the `PGROSERVICE` user
- This confirms the preflight guard catches credential wiring issues before file writes.

## Suggested rollout

1. Validate each client service in `~/.pg_service.conf`.
2. Add matching `~/.pgpass` entries.
3. Run bootstrap with `--dry-run`, then re-run with `--force`.
4. Pin toolkit to tagged `VERSION` in each client.
