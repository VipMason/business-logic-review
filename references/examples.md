# Domain Examples

These examples illustrate how to investigate across different business domains. Confirm actual names, values, statuses, and rules in the target project.

## Healthcare: cognitive screening

1. **Task and subject creation.** Separate county, locality, institution, and service area from public-health and clinician roles. Trace task definition, acceptance, clinician task creation, release, and creation of screening subjects; compare the management ledger and clinician H5 when a task is pending release.
2. **Different planned and default counts.** When a regional target is 5 while the assignment form opens at 20, verify the default source, saved value, and effective value, and check whether the approved rule constrains the sum across assigned service areas.
3. **Unmatched self-screening.** Compare a case with an existing pending subject against one without; inspect H5 results, subject state, Web screening record, and recovery or resubmission behavior.
4. **Screening records and quality-control issues.** When 15 records yield 5 issues, separate counting units, rule matching, pre-existing referrals, and manual operator flags.

## Commerce: refund approval and settlement

1. **Approval vs. funds movement.** Link the refund request, approval record, and payment-gateway settlement using a verified transaction ID. Check buyer-side status and retry behavior when approval succeeds while settlement is pending or fails asynchronously.
2. **Partial refund and inventory/coupon rollback.** Trace multi-SKU order splits, shipping/coupon proration, and whether inventory release or points reversal triggers on approval or on settlement completion.

## SaaS: menu, data, and action access

1. **Layered authorization checks.** Test with an account that manages Project A and only views Project B. Verify menu visibility, list scope, detail API scope, and write/export action permissions separately.
2. **Multi-role overlap and tenant boundaries.** Check whether permissive and restrictive roles merge by union or intersection, and confirm cross-tenant ID access is rejected in backend queries rather than hidden only in the UI.

## Government services: completion and next-day reporting

1. **Cross-role handoffs.** Trace applicant submission, intake pre-check, and caseworker handling; separate "intake accepted" from "caseworker task created" and check return/resubmit paths.
2. **T+1 cutoff and reporting mismatches.** When a completed record is missing from next-day reports, align counting unit, business vs. calendar day, cutoff time, time zone, deduplication rules, and records completed right before vs. after the cutoff.
