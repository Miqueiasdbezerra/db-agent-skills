# Browser and service workflows

## Choose a capable tool

Inspect connected service capabilities first. A connector can provide structured reads, updates, stable record IDs, and supported idempotency. Use it when sufficient for the authorized workflow. Otherwise use the available documented browser interface, including accessibility snapshots, visible controls, form inputs, and file-upload operations. Tools and browser engines are supplied by the host, not bundled here.

Read tool documentation before invoking unfamiliar methods. Do not assume a Playwright, CDP, native desktop, or vendor-specific API is present. If the available tools cannot perform a required step, preserve the confirmed state, explain the missing capability, and continue independent work.

## Observe, act, verify

Before each mutation, confirm the intended domain and account/workspace, inspect the current page, and identify the exact object and control. Prefer accessible role/name, label, or stable semantic references. Reacquire references after navigation, a rerender, or a modal transition. Coordinates are a fallback only when current visual evidence identifies the control unambiguously.

Wait for an observed state change using supported tooling; do not replace state inspection with arbitrary long sleeps. After acting, independently inspect the resulting page or service record. The verification should prove the user-visible outcome rather than merely successful tool execution.

## Navigate and locate records

1. Inspect the current URL and screen; compare with the authorized site and environment.
2. Use the site's normal navigation or a known authorized URL. Follow redirects only when they belong to the expected workflow.
3. Filter/search by the minimum required reference, then verify the selected record before editing it. Similar names are not sufficient evidence.
4. If a target is missing, distinguish wrong workspace, permissions, stale filters, navigation changes, and absence of the record.
5. Clear filters or return through known navigation when safe. Do not create a replacement until absence is verified and creation is authorized.

## Fill and submit forms

Read labels, required-field markers, types, defaults, validation rules, and submit behavior before filling. Map user values to the intended fields. Do not invent required legal, identity, payment, or contact information.

Localized or automatically translated labels may differ from the values accepted by a form. Use supported stable option values when the browser tool exposes them; reacquire current controls instead of relying on yesterday's display text. If validation rejects a translated value, inspect the error and persisted state before correcting it. Do not change the user's browser language or bypass server validation to make a submission succeed.

For each step, inspect the state before changing it and confirm that the input retains the intended value after blur or the relevant update. Handle checkboxes, radio buttons, dropdowns, dates, locale formats, disabled fields, dynamic sections, and multistep forms explicitly when present. A masked value may require a safe field-specific verification rather than logging it.

Before submission, review the populated form, selected account, attachment, destination, and approval boundary. Record intent and a stable operation key, submit once, then verify through a persisted detail view or supported read. If submission returns a field validation error, correct only the identified issue, inspect the current state again, and verify that the first submission did not create a record.

## Upload an authorized file

Verify the local file is the one the user supplied or approved, exists, and meets the site's extension, size, and count constraints. Confirm the destination, visibility, and overwrite behavior before selecting it. Do not send a file to a different service or external upload endpoint without authority.

Use the documented file-input/upload capability. Check progress and error states, then verify the attachment is listed on the intended record after saving. An upload progress indicator reaching 100% does not prove the parent record saved. If content validation is possible, compare file size or a supported checksum without storing the document in memory.

For a retry, check whether the attachment already exists. Never click "Replace", "Share", or "Publish" as an incidental step if the effect falls outside authorization.

## Recovery and duplicate prevention

| Symptom | First response | Retry condition |
| --- | --- | --- |
| Stale element or changed label | Inspect a fresh snapshot and confirm the logical target | Current state proves the intended action has not occurred |
| Navigation timeout | Inspect current URL, page, and service state | Safe navigation can be repeated without submitting again |
| Save timeout after click | Mark outcome uncertain; search persisted records or history | Evidence proves no effect, or a supported idempotency guarantee applies |
| Form validation error | Read field errors and inspect whether a record exists | Specific correction is known and prior save did not succeed |
| Session expired | Preserve journal and use normal sign-in/user handoff | Authorized session is restored and current state reconciled |
| Permission denied or CAPTCHA | Preserve checkpoint and hand off the supported flow | User or service restores legitimate access |
| Changed interface | Identify current labels/structure; mark affected playbook stale | Newly observed route is understood and remains authorized |

Use bounded retries for transient safe actions. Stop a repeating error when no new evidence changes the next attempt. Repeated non-idempotent clicks are not recovery.

There is no generic exactly-once guarantee across a local journal and a remote website. A process can stop after the server commits but before the journal records success. Durable intent plus reconciliation prevents blind retries; a supported remote idempotency key is stronger when available. When ambiguity cannot be resolved, preserve it and ask for a targeted decision before repeating the irreversible action.

## Resume checks

Load the last confirmed checkpoint and operation ledger. Confirm the live domain, account/workspace, record, authentication state, and current values again. Reconcile in-flight or uncertain operations before attempting new dependent work. Do not rely on an open tab or a remembered selector as evidence of completion.
