# Fictional example: update a private service request

All names, identifiers, domains, and attachment descriptions in this example are fictional. `portal.example.invalid` is an illustrative reserved domain, not a live service.

## User request

> In the private training workspace at portal.example.invalid, find request DEMO-1042, change its category to Facilities, attach the supplied fictional maintenance note, and save it. Do not send notifications or publish anything. If the session expires, leave the task ready to resume.

## Preparation

- Confirm the training workspace and the exact request identifier through the available service or browser tool.
- Read the relevant private playbook. It was validated against an earlier interface, so use its labels only as hints.
- Start a private journal with task alias `demo-update-01`. Record the outcome and scope, without copying the supplied file or full form contents into memory.
- Choose logical operation aliases such as `demo1042-category` and `demo1042-attachment`. An alias identifies the action; it is not a server idempotency guarantee.

## Execution

1. Inspect the current account/workspace and request details. Confirm the category has not already changed and the attachment is absent.
2. Record intent for the category update, inspect the current form, select Facilities, and save once.
3. Reopen or read the request details. Confirm the persisted category and mark that operation confirmed.
4. Check the supplied file and upload constraints, inspect the attachment control, and record upload intent.
5. Upload the file and save through supported controls. Do not use the adjacent public-share button.

## Interrupted outcome

Suppose the final save times out. The agent records an uncertain outcome and the last confirmed checkpoint. It does not upload another copy or claim the task complete.

On resumption, it checks the current session and request. If the intended attachment already appears and the persisted category matches, it confirms completion without repeating either operation. If absence is proven, it retries within the original scope. If evidence is insufficient, it leaves the upload uncertain and explains the exact blocker.

## Experience update

The agent observes that the attachment panel was renamed from "Files" to "Documents". It marks the old playbook step stale, records the verified new route, and updates its confidence and validation timestamp only after checking the saved result. It stores the reusable navigation lesson, not the maintenance note or personal account details.

## Example completion message

> Updated DEMO-1042 to Facilities and verified the attachment on the saved request. No notification or public action was requested. The interrupted upload was reconciled without a duplicate.

Only use that completion statement when the described evidence was actually observed.
