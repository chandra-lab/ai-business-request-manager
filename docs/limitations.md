# Known limitations

## Product / process

- AI recommends **department only**; managers assign individuals. No auto-assignment of people.
- HR deep policies (case workflows, retention, e-discovery) are intentionally shallow beyond notes + grants.
- Reviewer UX is functional, not a full case-management console.
- Manager assignment UI expects an assignee UUID (demo defaults to the logged-in manager).

## Technical

- SSE uses a short-lived server stream (~3 minutes) then relies on polling; not a durable pub/sub bus.
- Mock AI is keyword-based — adversarial phrasing can still match the wrong fixture if keywords collide (ordering prefers HR → Finance → Fleet → Legal → IT).
- Anthropic path requires network + API key; without them the factory falls back to Mock when configured that way / key missing.
- Outbox drain is best-effort; production should schedule `drain_outbox` periodically.
- Attachments are local disk under `UPLOAD_DIR` (not object storage).
- `main` may lag feature branches in this workspace until an explicit merge/push.

## Security caveats

- Admins are powerful for non-HR data but must receive an **HRCaseAccess** grant (or hold the `hr` role) for HR content — verify grants are reviewed operationally.
- Audit logs record denials; there is no SIEM export in-tree yet.
- Prompt-injection mitigations reduce risk but cannot guarantee model obedience on live Anthropic calls — always validate JSON schema server-side.

## Testing

- Integration tests use isolated DB `aibrm_test` and skip Celery broker (`APP_ENV=test`).
- Live Compose demos need bridge networking (`net.bridge.bridge-nf-call-iptables=0` on some VMs).
