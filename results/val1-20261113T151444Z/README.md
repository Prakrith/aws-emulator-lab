# Which services to learn on the emulator

Pinned build v1.0.338 (commit `32b3cf3`). `ranking.md` is the ranked list and `table.csv` has the same rows. Produced by:

    python3 -I scripts/rank.py results/ver2-20261113T003946Z/by_service.csv results/ver3-20261112T232814Z/counts.csv results/ver4-20261113T102029Z/results.csv results/val1-20261113T151444Z

## Columns

- **Sampled pass:** AWS's fidelity suite, up to 40 happy-path tests per service, each on a fresh emulator. It says nothing about error handling or edge cases. VPC has no label of its own, so it shares the `ec2` row.
- **Ops implemented:** operations in the service's Smithy model that are not marked `SCAFFOLDED, NOT IMPLEMENTED:` at the pinned commit. VPC shares the EC2 crate.
- **Smoke:** calls run by `scripts/smoke.py` that returned a successful CLI response, out of the calls made. Only the Lambda Invoke payload is checked. The harness does not otherwise check returned values, resource readiness, job execution or that a delete completed. For example, the Batch job stayed `RUNNABLE` and the RDS instance stayed `creating`. Athena's DeleteWorkGroup returned 501.

## Tiers

Fixed rules, applied by `scripts/rank.py`:

- **A:** sampled pass 85% or more and implemented operations 85% or more. Learn here.
- **B:** between the two. Expect gaps and some failures, so check the operation you need first.
- **C:** sampled pass under 50% or implemented operations under 60%. Learn elsewhere, or expect 501s.

Within a tier, services are ordered by sampled pass rate, then implemented share.

## Limitations

- 40 tests per service are a sample, not the whole suite. The pass rates carry sampling noise of several points.
- Timeouts (27 in the sample) were retried. Most still ran past 180 s, so a timeout here may be a slow emulator, not a missing feature. See the `jfs` notes and `results/ver2-retry*`.
- "Target errors" is the runner's own category, counted here as reported and not broken down further. They are not 501s. Six API Gateway tests failed only because no invoke-URL template was supplied.
- Operation counts treat an operation as implemented if it has code, not if it is faithful. The two columns measure different things.
- One service per crate was counted. EventBridge uses the `eventbridge` crate (57/57); the legacy `cloudwatchevents` crate is 7/51. CloudWatch Logs, API Gateway v2 and SageMaker runtimes are separate crates and are not counted.
- The emulator does not evaluate IAM, bucket or key policies, and does not run containers (Batch jobs fail, U-2 unchecked on this pin). Results say nothing about authorization.
- One machine, one pinned version. The emulator releases several times a day.
