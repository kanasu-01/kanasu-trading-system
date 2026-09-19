# Kanasu Agent Instructions

Use targeted context. The repository documentation remains authoritative, but agents must read only the sections needed for the current task instead of repeatedly loading whole governance documents.

Before changing the repository:

1. Establish the current branch, baseline, milestone/step, and authorized task from the dashboard/current-work portion of [Project Status](docs/PROJECT_STATUS.md). Read the whole file only when the needed state cannot be resolved from the relevant section.
2. Locate only the authorized task/child-step section, its immediate dependencies, and its non-goals in the [Roadmap](docs/roadmap/ROADMAP.md).
3. Read only the relevant current/target boundaries in [Architecture](docs/architecture/ARCHITECTURE.md), the applicable accepted or proposed entries in [Architecture Decisions](docs/architecture/DECISIONS.md), and the relevant task section in the [Validation Plan](docs/validation/VALIDATION_PLAN.md). Prefer heading-targeted search or line ranges over full-document reads.
4. Read only the [Governance](docs/governance/GOVERNANCE.md) sections applicable to the task. Read the whole Governance document only when the task is genuinely cross-cutting or the applicable rule cannot be determined safely.
5. Inspect the exact current production, test, and documentation files that may change before suggesting or making changes.
6. Do not silently expand the authorized scope.
7. Preserve permanent M, DW, AI, and AD identifiers.
8. Record material newly discovered deferred work without implementing it outside scope.
9. Run the validation authorized for the task and report exact evidence.
10. Perform the documentation-impact check before task closure.
11. During production implementation, apply the relevant Governance quality requirements for validation, failure/error behavior, logging and diagnostics, resource safety, configuration, security and secrets, code documentation, and risk-proportionate success, boundary, failure, and regression testing.
12. At major task, milestone, or version closure, use Governance's progress-summary convention when applicable.
13. Use the lean execution policy in Governance: run focused tests needed for implementation and debugging; leave routine full-suite regression and mechanical Git verification to independent review when practical; run broader validation yourself when correct implementation, diagnosis, integration, or explicit task instructions require it. Resource saving never overrides required validation or engineering quality.
14. Reuse context within the same task and unchanged baseline. Do not reread unchanged governance sections or unrelated completed-milestone history unless the branch/HEAD changes materially, a dependency becomes relevant, or uncertainty requires reinspection.
15. For independent review, start from the accepted contract, exact changed-file set, and exact diff. Expand into neighboring source, tests, or governance sections only where needed to validate behavior or scope.

Follow Governance for detailed workflow, status, identifier, source-of-truth, and documentation-synchronization rules. Destructive actions, Git publication beyond the current authorized task branch, external communication, live/broker actions, and material scope expansion require explicit authorization. Routine work already clearly authorized by the user does not require repeated confirmation.
