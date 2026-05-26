# KANASU RULE BOOK

## Purpose

This document defines the permanent engineering, architecture,
workflow, governance, and development rules for the
Kanasu Trading System.

These rules exist to:
- maintain long-term architectural stability
- avoid feature chaos
- avoid random implementation
- prevent overengineering
- maintain execution discipline
- preserve MVP scope boundaries
- support sustainable long-term development

This rule book acts as the permanent governance system
for the Kanasu Trading System.

---

# 1. PROJECT VISION

Kanasu is a professional, modular, Python-first,
broker-agnostic trading research and execution platform.

Primary long-term goals:
- strategy research
- backtesting
- walk-forward analysis
- replay systems
- paper trading
- live trading
- reporting
- portfolio analysis
- advanced market research
- future AI/ML integrations

Kanasu is intended to evolve gradually in phases.

---

# 2. MVP v1 PHILOSOPHY

MVP v1 goal is NOT:
- enterprise architecture
- distributed systems
- AI systems
- cloud systems
- multi-user SaaS
- advanced infrastructure

MVP v1 goal IS:
- stable execution
- usable workflows
- runtime separation
- research usability
- minimal refactoring later
- clean architecture boundaries
- end-to-end working system

Priority:
Execution quality > feature count.

---

# 3. MVP v1 SCOPE (LOCKED)

MVP v1 includes only:

- Single-symbol execution
- Backtesting
- Walk Forward Analysis (WFA)
- Replay mode
- Paper Trading
- Basic reports
- Stable research workflow
- Runtime stability
- Usability-first workflows

Explicitly postponed beyond MVP v1:
- Multi-symbol orchestration
- Portfolio allocation systems
- Sector/correlation systems
- AI/ML systems
- Distributed/cloud systems
- Advanced live infrastructure
- Options/futures complexity

No scope expansion without roadmap approval.

---

# 4. CORE MVP WORKFLOW

## Backtest Mode

Historical candles
→ strategy execution
→ metrics
→ reports
→ optional replay

---

## WFA Mode

Historical candles
→ window generation
→ optimization
→ OOS testing
→ reports
→ optional replay

---

## Replay Mode

Historical candles
→ interactive visualization

---

## Paper Trading Mode

Live candles
→ paper execution
→ portfolio monitoring
→ journaling/reports

Paper trading runtime must remain separate from backtest runtime.

---

# 5. ARCHITECTURE PRINCIPLES

## 5.1 Runtime Separation

The following runtimes must remain logically separated:

- Backtest Runtime
- WFA Runtime
- Replay Runtime
- Paper Trading Runtime
- Future Live Trading Runtime

No tight coupling between runtimes.

---

## 5.2 Separation of Concerns

The following responsibilities must remain separated:

- Strategy logic
- Execution logic
- Broker logic
- Portfolio logic
- Reporting logic
- UI logic
- Replay logic
- Data loading logic

No god classes.

---

## 5.3 Replay Rule

Replay is visualization only.

Replay must consume:
- candles
- signals
- trades
- journals

Replay must NOT drive strategy logic directly.

---

## 5.4 Strategy Rule

Strategies must remain plug-and-play.

Strategies must:
- be isolated
- avoid broker dependencies
- avoid UI dependencies
- avoid runtime-specific logic

---

## 5.5 Broker Rule

Broker architecture must remain broker-agnostic.

Broker implementations:
- AngelOne
- Zerodha
- future brokers

must remain interchangeable.

---

## 5.6 Simplicity Rule

Prefer:
- simple architecture
- stable workflows
- low cognitive overhead

Avoid:
- premature abstractions
- enterprise complexity
- unnecessary frameworks
- distributed architecture before required

---

# 6. DEVELOPMENT RULES

## 6.1 File Inspection Rule

No code modification suggestions may be given
without first inspecting the exact current file.

Always inspect actual current implementation first.

---

## 6.2 Incremental Development Rule

Development must proceed incrementally.

Avoid:
- massive rewrites
- uncontrolled refactors
- large unverified implementations

Small stable steps only.

---

## 6.3 Stability First Rule

Priority order:

1. Runtime stability
2. Execution correctness
3. Workflow usability
4. Validation
5. Reporting
6. Optimization
7. Automation
8. Scale
9. Intelligence systems

---

## 6.4 Vertical Slice Rule

Build complete working workflows first.

Preferred:
- complete small workflows

Avoid:
- unfinished architecture layers
- incomplete infrastructure systems

---

## 6.5 Refactor Rule

Refactors are allowed only if:
- architecture becomes unstable
- duplication becomes dangerous
- workflow becomes blocked
- runtime correctness is affected

Avoid refactoring for aesthetics alone.

---

# 7. ROADMAP GOVERNANCE RULES

## 7.1 Permanent Roadmap Rule

The Kanasu Roadmap is the permanent implementation authority.

All implementation must follow roadmap order.

---

## 7.2 Mandatory Roadmap Entry Rule

No feature, subsystem, refactor, optimization,
workflow addition, or architecture change
may be implemented without first being added
to the roadmap.

---

## 7.3 Status Rule

Allowed statuses:

- Implementing
- Future
- Completed
- Deferred
- Cancelled

Only ONE roadmap item may remain
in "Implementing" status at a time.

---

## 7.4 Completion Rule

After implementation:
- current item becomes Completed
- next roadmap item becomes Implementing

Roadmap must always reflect actual project state.

---

## 7.5 New Goal Rule

New goals discovered during development:
- must first be proposed
- must be inserted into roadmap
- must be prioritized correctly

Priority depends on:
- dependency order
- architecture necessity
- urgency
- workflow impact
- MVP scope

---

## 7.6 Emergency Rule

Critical blockers or mandatory architectural fixes
may be inserted at highest priority
only after roadmap review.

---

## 7.7 Non-Critical Addition Rule

Non-critical features must be inserted
in logical roadmap position,
not implemented immediately.

---

# 8. TESTING RULES

Testing is mandatory for:
- runtime correctness
- portfolio correctness
- WFA correctness
- journal correctness
- replay correctness
- execution stability

Automated tests must expand gradually with development.

---

# 9. JOURNALING RULES

Journals must remain:
- session-isolated
- scalable
- append-based

JSONL is preferred for MVP v1.

---

# 10. REPORTING RULES

MVP v1 reporting should remain simple.

Focus:
- usability
- clarity
- stability

Avoid advanced analytics during MVP v1.

---

# 11. UI RULES

Frontend must remain:
- modular
- lightweight
- workflow-oriented

Avoid:
- excessive UI complexity
- overdesigned dashboards
- premature feature-heavy interfaces

Functionality first.

---

# 12. AI/ML RULES

AI/ML systems are explicitly postponed beyond MVP v1.

No AI implementation unless added through roadmap governance.

---

# 13. DOCUMENTATION RULE

Major architecture decisions must be documented.

Roadmap and Rule Book must remain synchronized
with actual project direction.

---

# 14. LONG-TERM ENGINEERING PHILOSOPHY

Kanasu must evolve:
- gradually
- modularly
- sustainably

Goal is not:
- fastest feature expansion

Goal is:
- durable research infrastructure
- stable execution workflows
- long-term maintainability
- controlled complexity growth

---

# 15. FINAL PRINCIPLE

For MVP v1:

Shipping stable workflows
is more important than
architectural sophistication.

Execution discipline is mandatory.

# 16. Code Change Precision Rule

When suggesting code modifications:

- always provide exact file
- exact function
- nearby existing lines
- insertion location
- 3-5 surrounding lines minimum

Avoid vague instructions like:
- "inside this function"
- "near this block"

Reason:
Prevents ambiguity, wrong edits,
duplicate changes, and incorrect implementation.

# 17.Code Modification Diff Rule

When suggesting code changes:

- use diff-style blocks whenever possible
- removed lines must use:
  - red diff lines (-)
- added lines must use:
  - green diff lines (+)

Especially required when:
- only few lines change
- replacement is small
- avoiding accidental duplicate edits is important

Also provide:
- exact file
- exact function
- nearby surrounding lines