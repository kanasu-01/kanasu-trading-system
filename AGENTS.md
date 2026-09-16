# Kanasu Agent Instructions

Before changing the repository:

1. Read [Project Status](docs/PROJECT_STATUS.md).
2. Locate the authorized task in the [Roadmap](docs/roadmap/ROADMAP.md).
3. Read the relevant current and target boundaries in [Architecture](docs/architecture/ARCHITECTURE.md).
4. Read applicable accepted or proposed [Architecture Decisions](docs/architecture/DECISIONS.md).
5. Read the relevant [Validation Plan](docs/validation/VALIDATION_PLAN.md).
6. Inspect the exact current files before suggesting or making production-code changes.
7. Do not silently expand the authorized scope.
8. Preserve permanent M, DW, AI, and AD identifiers.
9. Record material newly discovered deferred work without implementing it outside scope.
10. Run the validation authorized for the task and report exact evidence.
11. Perform the documentation-impact check before task closure.
12. During production implementation, apply the relevant [Governance](docs/governance/GOVERNANCE.md) quality requirements for validation, failure/error behavior, logging and diagnostics, resource safety, configuration, security and secrets, code documentation, and risk-proportionate success, boundary, failure, and regression testing.
13. At major task, milestone, or version closure, use Governance's progress-summary convention when applicable.
14. Use the lean execution policy in Governance: run focused tests needed for implementation and debugging; leave routine full-suite regression and mechanical Git verification to independent review when practical; run broader validation yourself when correct implementation, diagnosis, integration, or explicit task instructions require it. Resource saving never overrides required validation or engineering quality.

Follow [Governance](docs/governance/GOVERNANCE.md) for detailed workflow, status, identifier, source-of-truth, and documentation-synchronization rules. Destructive actions, Git publication, external communication, live/broker actions, and material scope expansion require explicit authorization. Routine work already clearly authorized by the user does not require repeated confirmation.
