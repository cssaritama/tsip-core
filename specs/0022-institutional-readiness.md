# 0022 · Institutional readiness and integrations

Status: proposed gates for institutional access.

| Work | Acceptance |
|---|---|
| W-103 · Data contract and rights | For each instrument and feed record venue, cadence, timestamps, expected bars, holes, revisions, entitlement, output/audience rights and incident owner. Exercise stale, partial, fallback and missing states. Use complete sessions and explicitly version corrections. |
| W-104 · Reliability, audit and disaster recovery | Define SLOs for report freshness, serving and archived replay. Add canaries, escalation, incident register and rollback drill. Verify published artifact and archive fingerprint. Exercise offline recovery (W-86) and document RPO/RTO after a measured restore. |
| W-105 · Institutional security and procurement | Before private customer data, document authentication, access separation, retention/deletion, dependency review, audit events, support and contractual obligations. Test tenant isolation if a multi-tenant service is built. Require applicable rights, privacy and risk review. |
| W-106 · Export and integration | Implement 0019/W-91 after the pilot scope. Add a stable read-only schema and versioned exports only when a pilot has an integration owner and consumer. Document authorization, entitlement, as-of semantics, change handling and rollback. |
| W-107 · Institutional release gate | Demonstrate the user outcome, entitled data, evidence replay, operational response, privacy and security sign-offs. Separate private pilot, paid rollout and expansion decisions. Every launch records an accountable approver and known limitations. |
