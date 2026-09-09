# WS-33-B Rehearsal Checklist

- [ ] Four required application/Connector images and ingress image built from clean commit; immutable identities recorded.
- [ ] Production Compose resolves and starts using images only; no source mounts, dev servers, or public DB port.
- [ ] HTTPS routes Diner, Staff, and `/api`; SPA fallback and security headers pass.
- [ ] `/health` remains live during isolated DB outage; `/ready` fails and recovers after DB restoration.
- [ ] Fresh DB migrates to head; representative prior DB upgrades to head; failed migration blocks promotion.
- [ ] Backup checksum validates; isolated restore reaches head, retains representative data, serves `/ready` and a representative read.
- [ ] Secret/artifact checks pass; health/readiness/log sampling exposes no secrets or sensitive provider payload.
- [ ] Prometheus targets/rules pass and synthetic alert fires in the rule test.
- [ ] Traffic stop, prior image selection, compatible redeploy, and manual fallback steps rehearsed.
- [ ] Connector image replacement preserves external config/credential/ledger; compatible prior identity selectable.
