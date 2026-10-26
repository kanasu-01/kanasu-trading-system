# Global SOP Registry — Active Git Mirror

> **Non-authoritative mirror.** The controlling Global SOP is the current
> `/SOP/GLOBAL_SOP_REGISTRY.md` in ChatGPT Library. This file carries only
> the currently ACTIVE complete Global SOP versions. Published Git commits
> preserve future versions from the first baseline forward; older versions
> and approval history remain preserved in the Library. Every future
> Library-to-Git change must follow its separately approved controls.

## SOP-G-000-V003 — Mandatory SOP loading and enforcement

**Status:** ACTIVE  
**Scope:** GLOBAL — all current and future projects.  
**Supersedes:** SOP-G-000 (original unversioned wording).

1. Before ChatGPT begins substantive work in any project, ChatGPT must obtain and apply the current `ACTIVE` Global SOPs and the current `ACTIVE` SOPs belonging to that project.

2. Global SOPs must be obtained from the authoritative Global SOP Registry. Project-specific SOPs must be obtained from the authoritative SOP Registry for that project.

3. ChatGPT must not rely on conversation memory, model memory, previous-chat summaries, recollection, or assumptions as a substitute for the authoritative SOP registries when those registries are available.

4. Each project must contain or otherwise provide a permanent bootstrap instruction directing ChatGPT to load and apply the authoritative Global SOP Registry and that project's authoritative Project SOP Registry before substantive project work.

5. Global SOP text must remain centrally maintained and must not be unnecessarily duplicated into individual project SOP registries. Individual projects inherit the current `ACTIVE` Global SOPs through the bootstrap mechanism.

6. During a continuing working session, ChatGPT does not need to reread every unchanged SOP before every individual reply when the applicable authoritative SOP state has already been established and remains available in the current working context.

7. ChatGPT must refresh or reverify the applicable SOP state when a new project working session begins, when the project changes, when an applicable SOP has changed, when the applicable SOP state is uncertain, or before a controlled modification when verification is necessary to ensure compliance.

8. If ChatGPT cannot access or verify a required authoritative SOP registry, ChatGPT must not silently proceed as though the SOP contents were known. ChatGPT must inform the human that the governing SOP state could not be verified before performing work that depends on those SOPs.

9. When only particular SOPs are relevant to the current task, ChatGPT may retrieve the applicable authoritative portions rather than repeatedly loading unrelated SOP material, provided this does not omit a governing rule.

10. Efficiency must not be achieved by intentionally skipping an applicable SOP. Usage reduction and context reduction are subordinate to correct application of the authoritative SOPs.

11. Adding, modifying, superseding, or retiring this SOP or any other authoritative SOP remains subject to the human-approval and version-control requirements of `SOP-G-003`.

12. The authoritative Global SOP source is `/SOP/GLOBAL_SOP_REGISTRY.md` in the user's persistent Library, unless the human explicitly approves and records another authoritative location. **Each project's permanent bootstrap must identify the one authoritative Project SOP Registry for its project-specific rules. A project with no project-specific SOPs may instead use a recorded, explicit, human-approved declaration that no such rules or registry exist. That declaration is the narrowly defined exception to requirements 1, 2, and 4: the project's bootstrap must identify the declaration and direct loading of the Global Registry, and ChatGPT must verify the declaration. If project-specific SOPs are stored in another source, the bootstrap must designate that source as the Project SOP Registry; the no-project-SOP exception does not apply.** Copies, exports, attachments, and working drafts do not become authoritative merely because they are newer or easier to access.

13. During normal project work, **only current approved ACTIVE SOP requirements may govern ChatGPT's behavior. Reading or retrieving an authoritative registry that necessarily includes superseded or historical text is permitted when required to verify which rules are ACTIVE, including when a retrieval tool returns the entire registry. Retrieval of historical text does not give it authority; ChatGPT must distinguish retrieval from application and exclude superseded, retired, and draft rules from the applicable instruction set. Once a verified authoritative current-only source or retrieval method exists, ordinary loading should use it without reopening history unless source verification, an audit, investigation, conflict resolution, controlled revision, or an explicit human request requires it.**

14. The intended authoritative storage model is one current approved SOP snapshot per designated Global or Project SOP source, with earlier approved versions and their change history retained separately. **Until a separately approved amendment to the applicable historical-preservation requirements authorizes a transition, a mixed-history authoritative registry remains valid and historical content must remain where those governing requirements specify. Approval of the target architecture does not authorize deleting, rewriting, or relocating earlier versions. Before an authorized transition removes history from the active source, the complete earlier approved wording, version identity, approval and change evidence, and source-publication identity must be retained in a separately accessible history location, with predecessor/successor links and a successful recovery check. Migration must follow the currently applicable approval, independent-review, exact-diff, and publication controls.**

15. If multiple sources claim to be authoritative, an expected Project SOP Registry is missing, or the currently approved version cannot be established, ChatGPT must not resolve the uncertainty by guessing. It must report the issue and avoid controlled actions dependent on the unresolved instructions. Read-only investigation and preparation of proposed corrections may continue without treating uncertain rules as verified. **Such activity remains subject to applicable access, security, and Runner restrictions; describing an operation as read-only does not itself authorize it.**

16. Successful SOP loading establishes the instructions that govern the work; it does not establish that the work complies with them. ChatGPT must verify applicable requirements at the relevant response, approval, implementation, or protected-operation boundary. Where reliable mechanical checks are available, they should be used. **A mandatory check that fails, cannot be performed, or gives an inconclusive result must prevent the affected controlled action; absent verification must never be treated as PASS. Before a controlled modification or protected operation, ChatGPT must reverify available authoritative source-version or freshness evidence and applicable cross-cutting rules, using an authoritative rule index or an equivalently complete rule-discovery method where available. A keyword search alone is not proof that all applicable rules were found. Where a material source change cannot reliably be detected, ChatGPT must disclose that limit and must not claim the source is freshly verified.**

**Required operating principle:**

`Load authoritative rules → establish applicable SOP state → perform work under those rules → reverify when the governing state may have changed`

**Reason:** Ensure that Global and Project SOPs operate as actual governing instructions rather than depending on ChatGPT remembering earlier conversations, while avoiding unnecessary repeated retrieval that would waste context and model usage.

The revised rule additionally establishes **current-only instruction authority while permitting necessary mixed-registry retrieval**, separate recoverable history, authoritative-source verification, and compliance checks without repeatedly processing obsolete SOP versions.

---

## SOP-G-001-V003 — PowerShell copy / clear convention

**Status:** ACTIVE  
**Scope:** GLOBAL — Kanasu Runner, Kanasu Trading System, and all future projects.  
**Supersedes:** SOP-G-001 (original unversioned wording).

When ChatGPT provides a PowerShell command or script intended to be copied and executed as part of a diagnostic, inspection, verification, or similar project workflow:

1. The useful detailed output intended for return to ChatGPT must be copied to the clipboard automatically whenever technically practical.

2. After execution finishes, the PowerShell screen must be cleared so the pasted command and the detailed result are no longer left on the visible screen.

3. After clearing, show only a short status message such as `SUCCESS - Result copied. Paste into ChatGPT.`

4. On failure, preserve useful diagnostic details in the clipboard when practical, clear the screen, and show only a short failure message.

5. Do not require the user to manually select/copy the diagnostic output when the script can copy it automatically.

6. `Clear-Host` clears the visible console; it does not erase PowerShell command history. History deletion is a separate action and must not be performed unless the user explicitly asks for it.

7. If a task genuinely requires the full output to remain visible, explain why or follow the user's explicit request instead of silently violating this SOP.

8. Before clearing the PowerShell screen, the script must confirm that the useful diagnostic output has been successfully preserved in the intended clipboard destination whenever clipboard preservation is required and technically supported. A failed or unverified clipboard operation must not be reported as successful. If the output cannot be safely preserved, the script must not clear the only remaining safe, useful copy of that output merely to satisfy requirements 2 or 4. Instead, it must report the preservation failure and provide a safe recovery method. This is an explicit failure-handling exception to the normal screen-clearing behavior.

**9. In both successful and failed diagnostic workflows, passwords, access tokens, API keys, authentication cookies, private credentials, and other protected secrets must not be exposed during diagnostic collection, command-output handling, publication, or recovery. Any diagnostic step that could produce protected information must prevent unprotected output at its source or securely capture that output for exclusion or safe redaction before it reaches a terminal, terminal transcript, log, clipboard, or fallback instruction. Protection must be applied before emission to each destination; clearing the screen or redacting a later clipboard copy does not undo an earlier disclosure. If safe suppression, capture, exclusion, or redaction cannot be established, the affected diagnostic step must not execute or publish unprotected output. The workflow must explain the limitation safely and report the actual operation and preservation outcomes truthfully. These protections apply regardless of whether the underlying command succeeds or fails.**

10. Command execution, diagnostic-output preservation, and terminal cleanup are separate outcomes and must be reported truthfully. A command must not display an overall success message if its intended operation failed or its required diagnostic-output preservation failed. If cleanup fails after successful execution and output preservation, the script must report the cleanup failure without incorrectly reporting that the underlying operation failed. Where a safe clipboard result exists, preserve the useful operation status and failure details needed for subsequent verification.

11. Copying diagnostic results to the clipboard must not itself grant authority to execute another command, approve a protected action, or change Runner operating mode. This SOP does not override any applicable Kanasu Runner command-envelope, command identity, MANUAL COPY, SAFE/ELEVATED, or human-authorization requirement. When clipboard monitoring or automation is involved, diagnostic-result handling must remain distinguishable from executable-command submission, and the workflow must fail safely if that distinction cannot be established.

**Reason:** Reduce repetitive manual copy/cleanup work and keep the PowerShell window clean and predictable across projects.

The additional requirements prevent diagnostic-data loss, protect sensitive information, make execution and clipboard failures distinguishable, and preserve independent Runner authorization controls.

---

## **SOP-G-002-V004** — Reply-ending Summary and User Action

**Status:** ACTIVE\
**Scope:** GLOBAL — Kanasu Runner, Kanasu Trading System, and all future projects.\
**Supersedes:** SOP-G-002 (original unversioned wording).

Every ChatGPT reply that permits additional conversational sections under the applicable instruction hierarchy and required output format must end with two clearly identified sections, in this order: `Summary` followed by `User Action`. Both sections must appear after the main response content, not at the beginning of the reply. If a higher-priority instruction, an explicit current-task override, or a mandatory exact-output format prohibits these sections, ChatGPT must follow that requirement without adding incompatible sections, fields, or surrounding text. Where a separate conversational explanation is permitted, the closing sections must appear at the end of that explanation. This exception must not be invoked for brevity, convenience, or unsupported assumptions about format incompatibility.

The closing sections must:

1. Be concise.

2. Use simple, easy-to-understand English.

3. Avoid technical terminology unless a technical term is unavoidable for correctness.

4. State the practical meaning, conclusion, or outcome of the reply clearly in the `Summary` section.

5. Include a simple everyday example when an example would make the point easier to understand.

6. Keep detailed explanations, code, tables, evidence, and technical reasoning in the main response rather than unnecessarily repeating them in the closing sections.

7. This requirement applies to every reply within the scope defined above, including greetings, acknowledgments, simple confirmations, brief factual answers, and substantive project discussions. For short or non-substantive replies, the `Summary` and `User Action` sections must remain present but may contain only the minimum information needed. ChatGPT must avoid unnecessary repetition while preserving both required sections.

8. The `Summary` section must accurately state what was established, completed, proposed, verified, failed, or remains pending, as applicable. It must distinguish actual completed actions from proposed or unverified actions. The `User Action` section must clearly identify the next required human decision, approval, or action. If no human action is required, it must explicitly state `No action required.` A proposed change, recommendation, or review result must not be represented as an authorization or completed action. The `User Action` section must be the final section of the reply, with no additional explanatory content following it.

**Reason:** Ensure that every ChatGPT response for which closing sections are permitted concludes with a clear, concise statement of the outcome and the next human action. This creates consistent response formatting, improves verification of completed versus pending work, and reduces the risk of missing required human decisions or approvals.

---

## **SOP-G-003-V008** — Human-language specification, independent review, code synchronization, traceability, and human verification

**Status:** ACTIVE  
**Scope:** GLOBAL — Kanasu Runner, Kanasu Trading System, and all future projects.  
**Supersedes:** **SOP-G-003-V007**  
**Immediately preceding approved and published version:** **SOP-G-003-V007**  
**Earlier approved, never-published version retained in history:** **SOP-G-003-V006**

For every project behavior implemented in code, the human-approved natural-language specification and the corresponding implementation code are both authoritative and must remain synchronized.

1. Any proposed new feature, behavior change, bug fix, blocker correction, safety correction, or similar implementation change may originate from the user, ChatGPT, another AI model, an independent reviewer, an auditor, testing, diagnostics, or later discovery. Regardless of origin, it must enter the same controlled specification-and-implementation process.

2. A project may first have a broader Milestone design describing overall direction. A Milestone may contain Steps and Sub-steps. Such high-level design provides direction and organization but does not by itself authorize code modification. Each Step or Sub-step that changes implemented behavior must have its own separately controlled authoritative natural-language specification before implementation.

3. Before implementation, ChatGPT must prepare the exact intended behavior in clear natural language for human review. The specification must be sufficiently complete that another human or AI should not need to guess what the requirement means.

4. The full natural-language wording approved by the human is authoritative. A shorter title, heading, label, identifier, summary, comment, or paraphrase may be used only for navigation and reference. It must never replace, weaken, reinterpret, summarize away, or become a substitute for the complete approved wording.

5. No word in an authoritative natural-language specification may be added, removed, replaced, or otherwise changed without explicit human approval.

6. The exact natural-language specification that the human approves must receive an independent AI or independent review channel PASS before implementation. The normal sequence is human exact-wording approval followed by independent review. An independent PASS issued before human approval may instead satisfy this review gate when the complete identical candidate, including required formatting, was reviewed, the independent findings were available to the human, and the human then explicitly approves that unchanged candidate. The exact reviewed and approved content identity must be verified with its matching SHA-256 or equally precise byte-for-byte evidence; the approval then adopts that existing PASS without requiring another independent review or a separate post-approval confirmation solely because of timing. When the candidate or its required formatting differs, the earlier review was incomplete, blocking findings remain unresolved, or exact identity cannot be established, the human-approved version requires its own independent review PASS before implementation. The reviewer must assess the specification for gaps, contradictions, unsafe behavior, missing cases, blockers, ambiguity, regressions, and other material weaknesses. The independent reviewer does not obtain implementation authority merely by reviewing it.

7. If the independent specification review passes without requiring a material change and the exact reviewed wording has human approval under requirement 6, implementation may proceed to the code-proposal stage. If the reviewer identifies a gap, blocker, correction, or proposed modification, ChatGPT must prepare a revised complete natural-language specification and return it to the human for review. The revised specification receives no authority until the human approves its exact wording. Before implementation proceeds, the revised specification must have exact human wording approval and an independent specification PASS for the same complete wording, using the normal review sequence or the earlier-PASS adoption rule in requirement 6.

8. Historical approved specifications must never be silently rewritten. After an explicitly approved and verified transition to the Active Snapshot + Separate Version History model, the authoritative current specification source must contain the complete latest published `ACTIVE` version of each specification family, while every earlier approved version is preserved unchanged in a separately designated, recoverable historical store. Human wording approval and independent-review PASS do not by themselves activate a specification: activation occurs only when the separately approved exact publication change has been applied to the designated authoritative source and a successful read-back verifies that the resulting published content matches that approved change. This exact source read-back is the activation verification. A later independent document check and explicit final human acceptance are mandatory completion gates, not additional activation prerequisites. A never-published but human-approved version must be retained as approval history without being represented as formerly `ACTIVE`. Historical metadata must identify publication status and any later supersession or retirement without silently rewriting the originally preserved version. Only the latest validly published `ACTIVE` complete wording governs current controlled work. Before a matching read-back, the predecessor remains the last established governing version; if an attempted publication has made the actual source uncertain or inconsistent, affected controlled actions must pause instead of assuming either source is currently verified. If a later independent document check fails or final human acceptance is withheld or rejected, the successor remains the published governing version when its activation read-back passed, but the amendment is not closed and affected controlled actions must pause pending human-controlled resolution. Such a finding never authorizes an automatic rollback, silent deletion, or replacement; any corrective publication requires its own exact-diff approval and read-back verification. Until the pre-removal checks in requirement 55 pass and the separately approved migration removal operation begins, all existing mixed-history placement obligations remain binding. At the start of that exact approved removal operation, a narrowly scoped exception applies solely to the historical items and locations explicitly identified in its approved diff; all other historical-preservation requirements remain in force. While the source is being migrated, affected controlled actions must pause until the new authoritative snapshot passes its exact-content read-back.

9. Related later bugs, blockers, audit findings, and corrections must remain traceably associated with the affected specification family and exact version through permanent identifiers and linked historical evidence, rather than merely being appended to an unrelated document. The active snapshot may reference the relevant historical records without containing their complete superseded wording once an authorized migration is complete.

10. After an authoritative natural-language specification has passed independent review, ChatGPT may prepare the exact proposed code/file changes required to implement it. The proposed implementation must remain strictly within the approved specification.

11. Before any controlled implementation file is changed, the human must be shown the exact proposed additions, removals, and modifications and must explicitly approve them. Every added, removed, or changed controlled line requires this approval. Unrelated cleanup, refactoring, renaming, reformatting, comment changes, documentation changes, or additional improvements are not implicitly authorized.

12. If preparing or implementing the code reveals that the approved specification is incomplete, ambiguous, unsafe, or requires an additional behavior change, implementation must stop and return to the natural-language specification process. ChatGPT must not silently resolve the issue by inventing new behavior.

13. After the human approves the exact proposed code/file changes, those exact approved changes may be applied. The applied implementation must not exceed the approved difference.

14. After implementation, the resulting implementation must be challenged by an independent AI model or independent review channel. That review must compare the implementation against the complete current ACTIVE natural-language specification and examine relevant correctness, safety, regression, and implementation concerns.

15. If the post-implementation independent review identifies a specification gap or required behavior modification, the process returns to the natural-language specification stage. If it identifies an implementation defect without requiring a specification change, ChatGPT must prepare the exact corrective code/file difference for human approval before applying it. No reviewer finding grants automatic permission to alter files.

16. When the post-implementation independent review passes, ChatGPT must present the human with the actual modifications for final verification. The verification reply must show only the actual relevant changes: the before/after difference in the authoritative specification document when that document changed, and the before/after difference in every implementation file changed. Unchanged file contents should not be presented as though they were modifications unless the human requests additional context.

17. The human reviews the actual applied modifications against the approved specification and approved code change. The Step or Sub-step is considered human-verified only after the human explicitly accepts this final verification.

18. The authoritative natural-language specification and corresponding implementation code must both be version-controlled in Git and preserved together in project history. Git history must make it possible to determine which approved specification governed a particular implementation change.

19. A permanent identifier and short heading may identify a Specification, Step, Sub-step, or Milestone, but the identifier or heading is never itself the authoritative behavior. The complete latest ACTIVE human-approved natural-language wording is the authority.

20. Read-only diagnostics, inspection, investigation, explanation, log review, and similar work that does not modify the authoritative specification or project files may proceed without this modification-approval sequence. Such investigation may discover a proposed change, but once a change is proposed it must enter this SOP before implementation.

### Change visibility and human comparison

21. When a completely new authoritative specification is being introduced and no earlier version of that specification exists, the complete proposed specification must be presented to the human for approval. Because the entire specification is new, individual words or sentences do not need special change highlighting.

22. When an existing approved specification is being revised, the earlier approved version must remain unchanged and preserved as historical evidence. The complete proposed successor and its comparison with the immediately preceding human-approved version must be presented together for review. After the matching authoritative-source activation read-back defined in requirement 8 succeeds, the complete new `ACTIVE` version belongs in the authoritative current source and the previous approved wording belongs in the designated historical store; the two complete versions need not remain adjacent in the active source after a separately approved migration. Until the precise pre-removal conditions and authorized operation specified in requirements 8 and 55 are met, the existing mixed-history placement requirements remain binding. Approval of the target architecture, archive preparation, or an unverified publication does not itself create an exception.

23. In the complete proposed successor and its archived review record, every word, phrase, sentence, or other portion whose wording differs from the immediately preceding approved version must be visually highlighted so that the human can identify the modification without manually comparing the two complete versions. This includes changed version identifiers and other changed metadata. The immediately preceding approved version may have been approved but never published; the published predecessor must also be identified separately when the publication comparison differs.

24. The standard visual highlighting mechanism for changed natural-language specification wording will be bold Markdown unless another mechanism is explicitly approved for a particular format. The exact highlighted successor and its comparison must be preserved in the historical review evidence and in Git when the controlled specification belongs to a Git-versioned project. A current-only published snapshot may omit review-only highlighting only when its exact published formatting has been shown and approved in the publication diff and verified after publication; otherwise the approved marked formatting must remain unchanged. Historical approval copies may not be reformatted retroactively.

25. Bold formatting used for change highlighting is a visual review aid only. It does not shorten, replace, summarize, or alter the authoritative meaning of the specification. The complete wording of the latest validly published `ACTIVE` version remains authoritative. A review copy marked `ACTIVE` does not acquire authority before the exact approved publication and matching authoritative-source read-back described in requirements 8 and 53. Independent document review and final human acceptance remain required completion gates as specified there.

26. Change highlighting in each proposed and archived specification version must show the changes relative to its immediately preceding approved version. Historical versions retain their own historical highlighting. This allows the evolution of the requirement to be understood version by version. The history record must distinguish approval succession from publication succession, particularly where an approved intermediate version was never activated.

27. Words that were unchanged from the preceding version must not be highlighted merely for emphasis. Change highlighting must be used specifically to identify actual approved wording changes. A changed version identifier must be highlighted; preexisting structural formatting, such as an unchanged bold metadata label, must not be treated as change highlighting.

### Code change presentation

28. When a completely new code file or completely new code block is being introduced and no earlier implementation exists, the complete proposed new code may be presented without special word-by-word or line-by-line highlighting because the entire implementation is new.

29. When existing code is being modified, the source code file stored locally and in Git must remain ordinary valid source code. Bold markers, review symbols, or other visual change markers must not be inserted into executable source code merely for human review.

30. Before an existing code implementation is modified, ChatGPT must present the human with an exact comparison that clearly identifies every proposed addition, removal, and replacement. The presentation must make it immediately visible which line, expression, word, statement, or code block will change.

31. The preferred presentation for modifications to existing code is an exact diff-style comparison, using clear removed and added sections such as:

```diff
- old code
+ new code
```

When a change occurs inside a larger line or block and the ordinary line diff would make the specific alteration difficult to notice, ChatGPT must additionally explain or visually identify the precise changed portion in the reply.

32. Human approval applies only to the exact code difference that was presented. Code surrounding the approved difference is not automatically authorized for modification.

### Post-implementation verification

33. After approved changes have been applied, the next human-verification reply must present the actual applied changes, not merely repeat the intended changes.

34. For a revised authoritative specification, the post-implementation presentation must show the actual relevant before/after difference between the formerly published authoritative source and the newly published authoritative source, identify the exact approved publication version, and verify that the complete published wording matches the approved file changes. The full immediately preceding human-approved version, complete published successor, and their changed-word highlighting must remain accessible in the historical review evidence. The human must be given the actual diff directly, not merely an assertion of matching hashes or Git history. The older complete wording need not remain in the normal active source after an authorized migration.

35. For modified existing code, the post-implementation presentation must show an exact actual diff between the version before implementation and the version after implementation. It must clearly show every line added, removed, or altered.

36. If the actual post-implementation difference contains anything that was not part of the human-approved proposed difference, the Step or Sub-step must not be treated as complete. The unexpected difference must be brought to the human for review and resolution.

37. When the entire specification or entire code implementation is new, post-implementation verification may show the complete new content without change highlighting because there is no earlier corresponding content against which individual changes need to be distinguished.

38. Git remains the permanent technical history, but Git history alone is not a substitute for presenting the actual relevant differences directly to the human in the ChatGPT reply.

### Permanent hierarchy, insertion numbering, and specification-to-code traceability

39. Controlled project work must use permanent hierarchical identities in the order `Project -> Milestone -> Step -> optional Sub-step -> Specification -> Specification Version`. Each level identifies a different kind of object and must not be used as a substitute for another level.

40. Project codes must be short and stable. Examples include `KR` for Kanasu Runner and `KTS` for Kanasu Trading System. Future projects receive a stable project code when their controlled hierarchy is created.

41. Normal planned items use zero-padded permanent numbers, for example `M001`, `M002`; `S001`, `S002`; `SS001`, `SS002`; and `SPEC001`, `SPEC002`. Once assigned, an identifier must never be reused or renumbered merely to make the sequence look tidy.

42. When a newly discovered Milestone, Step, Sub-step, or Specification logically belongs between two existing permanent items, it must be inserted by appending a capital letter to the immediately preceding item's identifier rather than renumbering existing items or assigning an unrelated later number. Examples: `M001A` between `M001` and `M002`; `S003A` between `S003` and `S004`; `SS001A` between `SS001` and `SS002`; `SPEC001A` between `SPEC001` and `SPEC002`. Further insertions at the same position use `B`, `C`, and so on.

43. If an insertion is later required between two already inserted lettered items, a numeric suffix may be added to the preceding inserted identifier, for example `SPEC001A1`, `SPEC001A2`, while all previously assigned identifiers remain unchanged. The same principle may be used at Milestone, Step, and Sub-step levels when genuinely required.

44. An insertion suffix and a specification version mean different things and must never be confused. `SPEC001A` identifies a separate specification inserted logically after `SPEC001`. `SPEC001-V002` identifies the second approved complete wording of the same `SPEC001` requirement.

45. A complete specification identity should preserve its hierarchy. Example: `KR-M001-S002-SS001-SPEC001A-V001`. If a Sub-step is not needed, that level may be omitted without inventing a placeholder.

46. The specification family identifier, such as `KR-M001-S001-SPEC001`, identifies the requirement through its lifetime. A versioned identifier, such as `KR-M001-S001-SPEC001-V002`, identifies one exact approved wording of that requirement. The implementation must be traceable to the exact governing approved version, not merely to the specification family.

47. Each controlled project must maintain a specification-to-code traceability register. For every implemented specification version, the register must identify at least the specification version, implementation status, relevant implementation file paths, stable implementation locations such as function/class/module names where applicable, relevant tests, independent review status or evidence, and the Git commit or commits that implement the approved specification.

48. Permanent traceability must not rely primarily on source-code line numbers because ordinary edits can move lines. File paths plus stable function, class, module, symbol, or equivalent implementation locations should be used for long-term mapping. Line numbers may still be shown in a particular review reply when useful for immediate human inspection.

49. One specification may map to multiple files, functions, modules, or tests, and one implementation file may implement multiple specifications. The traceability register must represent these relationships explicitly rather than assuming a one-specification-to-one-file relationship.

50. Important implementation boundaries may contain a source-code comment referring to the relevant specification family or version when useful, but such comments are supplementary rather than the authoritative traceability record. Adding, removing, or changing such a comment is itself a controlled file change and requires the same human approval as any other controlled code change.

51. Git commits that implement or modify controlled behavior should include the governing specification identifier or version in the commit message so that specification history, code history, tests, and independent reviews can be connected later.

52. The hierarchy and traceability system exists to preserve both logical reading order and historical truth. A later discovery may be inserted where it logically belongs without renumbering old work, while revisions to an existing requirement remain attached to that same requirement through explicit versioning.

### Authoritative publication, historical migration, and SOP governance

53. For Global SOP and Project SOP amendments maintained in a persistent Library or Project registry rather than as a specification/code pair, the controlled process is: complete exact proposed SOP wording -> human exact-wording approval and independent specification challenge PASS on identical content (normally in that order, or with an earlier PASS adopted under requirement 6) -> complete exact proposed registry and archive file differences -> separate human approval of those exact changes -> controlled publication -> successful read-back proving the authoritative published content matches the exact approved file changes (the activation event) -> independent document verification -> actual changes shown to the human -> explicit final human acceptance (the completion event). Until activation read-back succeeds, no newly written version may be represented as verified governing authority. After activation, independent document verification and final human acceptance must still pass before the amendment is closed. If either later gate fails, affected controlled actions must pause for explicit human-controlled correction or recovery; activation is not silently undone and no automatic rollback is authorized. The code-specific independent implementation challenge remains mandatory when executable code, automation, or application behavior is changed. A document-only publication check is not evidence that operational Runner or application behavior was tested. Neither wording approval nor a reviewer PASS authorizes publication. **For a single approved work package that has both authoritative Library/Project changes and GitHub changes, one human approval 2 must be requested for the complete set of exact proposed file-content differences across those destinations; this content-change approval is not multiplied merely because there are several files, stores, or artifact types. It does not waive the distinct protected Git operation approvals in requirement 56, the authoritative Library activation read-back, independent actual-state verification, or final human acceptance.**

54. The authoritative current SOP snapshot must be distinguishable from review drafts, human-approved but unpublished versions, and previously published versions. A version's `ACTIVE` label inside a proposed or historical copy is prospective or historical evidence, not proof of present authority. Publication evidence must identify the exact Library/Project source identity and version or, where applicable, repository commit; preserve the approved wording and proposed file diff; and verify the resulting complete content after publication. The evidence must separately identify whether the activation read-back succeeded, whether independent document verification passed, and whether final human acceptance was granted; these are distinct events, not interchangeable claims of completion. An `ACTIVE` label written into an unverified or partially modified source is not sufficient to prove activation. `SUPERSEDED` and `RETIRED` describe prior published authority, not a never-published draft or review failure.

55. Migration from a mixed-history authoritative source to an active-only snapshot is a distinct controlled change and requires its own exact file-diff approval and verification after the applicable amendment authorizes that model. Before removing or relocating any historical wording, preserve each complete prior approved version, its unchanged original formatting, version identity, approval and review evidence, historical publication status, predecessor/successor links, and a recoverable copy of the pre-migration source. Verify archive existence, exact content, retrieval, and recovery against a recorded source identifier or digest before executing any approved removal or relocation; a proposed archive, untested backup, or post-removal recovery check is insufficient. The human-approved migration diff must identify the exact historical text and locations to be removed or relocated, the replacement authoritative source, the scope of the temporary placement exception, the verification gates, and the allowed recovery procedure, if any. Only after these pre-removal checks pass may the exact approved migration operation begin; at that point, and only for the listed items and locations, the old in-place placement obligation is suspended solely to permit the transition. During any partially applied or unverified transition, affected controlled actions must pause and no intermediate snapshot may be represented as authoritative. The new active-only snapshot becomes governing when the approved replacement source passes exact-content read-back as required by clauses 8 and 53; subsequent independent document verification and final human acceptance are still required for closure. If migration publication or verification fails or the human withholds final acceptance, pause affected controlled actions, preserve all already verified history and pre-migration evidence, and seek explicit human authorization for a corrective operation. Restoration is permitted only through an exact human-approved correction or a recovery operation expressly approved as part of the original migration diff; it must itself be read-back verified. A missing, inaccessible, unverifiable, or incomplete historical record blocks the affected migration; it must not be repaired by inventing earlier approvals or retroactively altering historical text. Ordinary loading may use a verified active-only source afterward, but audit and controlled-revision workflows must retain access to relevant history.

56. Requirements that explicitly refer to implementation code, executable tests, Git commits, or a specification-to-code traceability register continue to apply to Git-versioned implementation work. They do not by themselves require a Library-only SOP registry to be copied into Git or permit protected Git operations. For Library-only SOP changes, permanent Library version identity, the separately retained immutable history, exact publication diffs, and verified human acceptance provide the document-publication evidence; if an approved workflow also maintains a Git mirror, its updates are separately controlled. Staging, committing, pushing, branch switching, merging, resetting, and other protected Git actions remain subject to independent explicit human authorization.

### Standard Git-involved workflow: three human approval gates and two independent Codex reviews

57. For preparation of SOPs, designs, specifications, documentation, code changes, and other controlled work that involves GitHub, the primary human-review sequence is: complete proposal, human approval 1 and independent Codex review 1 PASS (normally in that order, or with an earlier independent PASS adopted upon later human approval 1 under requirement 6), exact proposed file and publication changes, human approval 2, authorized implementation and Git publication, independent Codex review 2 PASS on the actual published result, human approval 3 for final acceptance, and then the next task. This is one controlled workflow; do not invent routine additional wording approvals or repeat an unchanged PASS review. Requirements for authoritative Library activation, historical preservation, tests, and separately authorized protected Git operations remain applicable and are not waived by the three primary human gates. **This standard workflow applies uniformly to SOP preparation, project and system design, specifications, documentation, executable source, tests, and combined code-and-documentation work when GitHub is involved. A task must not be treated as requiring a fresh design-approval or review-1 cycle solely because a complete valid independent PASS has been supplied for the unchanged human-approved proposal.**

58. At human approval 1, the human approves the complete exact intended design, specification, document wording, or change requirements. Codex review 1 independently challenges the identical candidate for completeness, correctness, consistency, risks, and regressions before implementation or publication, normally after human approval 1 or earlier under the exact-content adoption conditions of requirement 6. If this review reports FAIL or requires a material correction, present the complete corrected proposal for a fresh exact-wording approval and independent review. An independent PASS issued before human approval 1 counts as Codex review 1 when the human then explicitly approves the identical unchanged reviewed candidate with the findings available, and the byte-exact identity check in requirement 6 succeeds. No repeat Codex challenge or post-approval confirmation is required solely to change the review/approval order; an incomplete review, changed content or unresolved blocking finding requires renewed review after correction.

59. After review 1 reports PASS and human approval 1 is established for the exact reviewed content under requirement 6, prepare the exact proposed additions, removals, and replacements in every controlled file; identify the destination repository, Git branch, expected source identity and commit, and any related Library changes. Human approval 2 authorizes only these exact proposed file and publication changes, and no unrelated changes. Do not ask the human to approve unchanged wording again. Human approval 2 must not be interpreted as a blanket approval of Git staging, commit creation, push or remote-reference update, branch switching, merge, or other protected actions: each such action still requires the applicable distinct explicit authorization under requirement 56 and the project Runner protocol. If the required target of a protected action is not yet known, obtain its exact guarded authorization when that target becomes known. **When ChatGPT receives the Codex review 1 PASS and human approval 1 is established for the same exact content, its next substantive reply must present the complete bounded implementation/publication plan with the exact proposed controlled-file differences, identify all affected code, test, design, documentation, Library and GitHub destinations as applicable, and ask directly for human approval 2 to implement those exact changes. The request must be one coherent content-change approval for the identified task, not a series of duplicate ordinary file-write approvals. If source identity, target commit, exact changes or access cannot yet be verified, ChatGPT must report the precise blocker and gather permitted read-only evidence rather than ask the human to reapprove the design or obtain an unnecessary repeated Codex review. Human approval 2 authorizes the listed ordinary file writes and associated agreed verification work, not additional scope, protected Git actions requiring separate authorization, or a permanent workflow exception.**

60. After the required approvals and precondition checks, apply only the authorized file changes through the approved repository workflow. Identify and verify the exact updated Git commit and branch, the actual remote contents, and the actual difference from the approved predecessor. If publication to an authoritative Library or Project source is also involved, perform its separately approved update and matching authoritative-source read-back; Git publication by itself never activates a Library SOP. A working-branch commit is not final publication to the designated official branch; any promotion or merge remains separately protected and must be verified at the resulting official branch. The source identities, content fingerprints, commit lineage, relevant tests, and any divergence between Library and Git must be recorded truthfully. **Following human approval 2, ChatGPT must carry out the specifically approved edits to code, tests, design, documentation, Library and GitHub as applicable, with the available tests, source guards and read-backs, without requesting another generic permission to begin editing the same already-approved files. Where a protected Git operation or another mandatory external authority has not yet been separately authorized, stop only at that boundary, identify the specific missing action and expected target, obtain its required approval, and then resume the approved package without repeating human approval 1, Codex review 1 or human approval 2. A partly completed Library/Git publication must be reported as incomplete rather than represented as synchronized or final.**

61. Immediately after the actual authorized GitHub publication has been verified, prepare the independent Codex review 2 request using the actual published repository branch, commit, file contents, approved original proposal, human-approved file differences, and implementation/test evidence where applicable. Codex must independently compare the design or specification that was approved with the human-authorized file differences and the actual published GitHub result, and must assess implementation correctness, relevant tests, regressions, and Library-source evidence where applicable. Supplied snapshots alone must not be falsely represented as independent live-source retrieval. A reviewer unable to verify required evidence must report BLOCKED or FAIL, not PASS. The review request may be prepared before publication, but its actual-state claims must be populated only after successful remote read-back. **After the authorized implementation and actual-state read-back, ChatGPT must supply the ready-to-submit Codex review 2 prompt in the same completion response, populated with the real Git branch, commit, actual modified files, exact approved design/wording, human-approved implementation diff, Library source/version and verification evidence where applicable. The prompt must explicitly require the independent reviewer to check that the designed content, human-approved changes and actually implemented/published content agree, and to check code correctness and regressions when relevant. Preparing this reviewer prompt needs no additional routine human permission. If publication is blocked or incomplete, label any prepared prompt as not yet executable and do not claim that review 2 can verify an uncreated commit.**

62. Only after Codex review 2 reports PASS for the actual final Git state and other mandatory document or implementation checks have passed, present the actual before-and-after changes and verification evidence for human approval 3. Human approval 3 is final acceptance and closure of the specific task, step, specification, design, SOP, documentation change, or code change; then proceed to the next authorized item. Neither publication nor Codex PASS alone constitutes human acceptance. If review 2 fails, content differs, source evidence is unavailable, or final acceptance is withheld, keep the work OPEN, pause affected controlled operations, preserve evidence, and follow the existing exact-correction and approval safeguards; do not silently rollback, fabricate a PASS, or initiate the next controlled change as though closure occurred. **When Codex review 2 PASS is returned for the verified actual result, ChatGPT must next present the actual relevant changes and verification for human approval 3, without an added reapproval of unchanged design or a third independent review. On explicit human approval 3, the controlled task is accepted and closed, and ChatGPT may move to the next authorized item.**


63. **A human's report of an independent review 1 PASS is a workflow handoff, not a request to restart the design. ChatGPT must classify the result against the exact approved candidate and proceed to the implementation-permission request in requirement 59 when its gates are met. After the implementation/publication and required read-backs, ChatGPT must advance to the actual-state review 2 handoff in requirement 61. The three primary human gates are: approval 1 for complete intended behavior or content; approval 2 for exact proposed implementation/publication file changes; and approval 3 for final acceptance after review 2 PASS. Additional independently protected Git-operation authorizations under requirement 56 remain mandatory and must be called out explicitly rather than hidden or presented as duplicate wording approvals.**

64. **The currently ACTIVE Global SOP and applicable Project SOP and Runner controls govern controlled work over an inconsistent ordinary chat instruction. If a chat request conflicts with a governing SOP, ChatGPT must identify the exact conflict and its effect before taking the conflicting action; it must not silently follow the chat instruction, invent an approval, or amend the SOP by implication. A human may request a clearly identified exception confined to one message and its corresponding assistant reply only where the governing rule and higher-priority safeguards permit that exception; the request must specify the affected rule, exact temporary scope and authorized action, and the exception expires with that response. This narrow exception cannot itself waive mandatory specification or implementation reviews, actual file-diff approval, independent verification, final human acceptance, protected Git approvals, safety requirements or any higher-priority instruction. Where the controlling requirements do not permit an exception, a separately approved SOP amendment is required instead.**

### Required controlled flow

For GitHub-involved work: complete proposal -> human approval 1 and Codex review 1 PASS (normal order or prior PASS adopted upon human approval 1 under requirement 6) -> exact proposed file changes -> human approval 2 -> authorized implementation and Git publication -> Codex review 2 PASS on actual published Git state -> actual before/after differences shown to human -> human approval 3 (final acceptance) -> next task. Separately protected Git operations retain their required authorizations. **Immediately after a valid review 1 PASS, the next substantive reply requests human approval 2 for the exact multi-destination implementation package. After human approval 2, implement the authorized file changes, comply with independently protected Git authorizations, verify the actual sources and prepare the ready actual-state Codex review 2 prompt.**

If either independent challenge returns a material problem:

`Finding -> revised full specification where required -> human approval -> independent challenge again -> continue only after PASS`

For a document-only SOP amendment: **Where the same package publishes both Library/Project and Git content, human approval 2 covers the complete exact content-change plan for both destinations, while separately protected Git actions still require their own permission.**

Complete exact SOP wording -> human wording approval **and** independent specification PASS **(normal order or prior PASS adopted upon human wording approval under requirement 6)** -> exact proposed registry/archive diff -> separate human approval -> controlled publication -> matching authoritative-source read-back (activation) -> independent document check -> actual diff -> final human acceptance (closure)

When GitHub is also part of an SOP amendment, apply requirements **57–64** alongside this Library activation flow without replacing its authoritative-source read-back or final human acceptance.

**Reason:** Prevent silent interpretation drift between what the human intended and what the software actually implements, while preserving permanent identities, review history, exact change visibility, and traceability from approved human language to real code and Git history.
