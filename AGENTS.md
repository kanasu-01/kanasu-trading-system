# Kanasu Agent Instructions

## 1. Global SOP

Before substantive controlled work, load the currently ACTIVE Global SOPs from:

Repository: `kanasu-01/kanasu-sops`

File: `global/GLOBAL_SOP_REGISTRY.md`

Kanasu currently has no project-specific SOP registry.

If the authoritative SOP requirements cannot be verified, do not modify controlled project files.

## 2. Source of Truth

- GitHub repository: `kanasu-01/kanasu-trading-system`
- `milestones.md`: milestone progress overview.
- Approved and published Human Language Specifications: authoritative intended behavior.
- Current source code and tests: implementation and verification evidence.
- Relevant Git history: implementation and specification history.

Do not treat proposed or historical specifications as currently approved merely because they exist in GitHub.

## 3. Git-First Development

Before proposing implementation:

1. Verify the current branch, HEAD, and repository state.
2. Establish the exact user-authorized task and governing specification.
3. Inspect the relevant existing code and tests.
4. Prepare the exact proposed file changes.
5. Follow the applicable Global SOP review and approval requirements.
6. Execute only approved operations.
7. Verify the resulting repository state.

Stop if the repository state or proposed change scope differs from what was authorized.

## 4. Documentation

Keep the active repository minimal.

Do not add review packages, HTML reports, progress journals, or other documentation merely because they were generated during development.

Any required documentation must be covered by the applicable SOP and exact approved change manifest.

Preserve approved specification wording, permanent identifiers, required traceability, and recoverable history.

## 5. Authority

The project owner determines development scope and approves controlled changes.

Do not stage, commit, push, merge, reset, switch branches, or perform other protected Git operations outside the exact applicable authorization.

Never silently modify an accepted behavioral contract or expand a task beyond its approved scope.
