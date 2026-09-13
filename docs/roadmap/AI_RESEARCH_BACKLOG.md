# Kanasu AI Research Backlog

## Purpose

This ledger preserves AI-001 through AI-010 as research hypotheses. These identifiers are permanent and are not roadmap implementation commitments.

An item remains research until it defines:

- a falsifiable hypothesis;
- prerequisites and roadmap dependencies;
- a deterministic or simple statistical baseline;
- a point-in-time dataset and labels;
- leakage-resistant evaluation;
- success and failure criteria;
- an experiment outcome; and
- an explicit decision to reject, continue research, or propose promotion.

AI must demonstrate measurable benefit over its baseline. A failed experiment with a documented result can be completed research. No model may bypass deterministic risk controls.

## AI-001 — News Sentiment Model

**Research status:** DEFERRED.

Hypothesis: information available at publication time can classify company/security news in a way that adds measurable value over a simple baseline.

Potential inputs include headline, article text, source, publication timestamp, company and sector. Subsequent price behavior may be an evaluation label, not an input that leaks the future.

Prerequisites: legally usable point-in-time news, publication/effective timestamps, symbol/entity resolution and a non-AI baseline.

## AI-002 — Company News Intelligence

**Research status:** DEFERRED.

Hypothesis: NLP can convert company news into reliable structured event type, importance, sentiment, confidence, affected company and sector fields.

Prerequisites: AI-001 data foundations, event taxonomy, annotation/evaluation set and point-in-time guarantees.

## AI-003 — Historical Condition Probability

**Research status:** DEFERRED.

Hypothesis: similarity across trend, volatility, volume, momentum, price structure, market regime, time of day and relative strength can produce calibrated out-of-sample outcome distributions.

Descriptive similarity must be distinguished from predictive value. Compare against unconditional and simple rule-based distributions.

## AI-004 — Support / Resistance Intelligence

**Research status:** DEFERRED.

Hypothesis: combining price reactions, volume, swing points, volatility, structure and timeframe agreement improves a measurable support/resistance objective over deterministic methods.

The first baseline should be deterministic; ML is optional rather than assumed.

## AI-005 — Big Money Flow

**Research status:** DEFERRED.

Hypothesis: explicitly defined observable features can estimate a useful large-participant activity proxy.

Potential inputs include volume, delivery data, open interest, futures/options data, block/bulk activity and breadth. “Big money” or “institutional” activity must not be claimed without a quantitative target and evidence.

Prerequisites include the relevant point-in-time datasets and, for derivatives, instrument/contract semantics.

## AI-006 — Social / Telegram Sentiment

**Research status:** DEFERRED.

Hypothesis: emerging narrative, sentiment velocity or unusual activity from permitted sources adds out-of-sample value after manipulation and noise.

Prerequisites: lawful/ToS-compliant access, source reliability, timestamp integrity, manipulation controls and a stable baseline.

## AI-007 — Trade Quality Model

**Research status:** DEFERRED.

Hypothesis: features available at decision time improve calibrated positive risk-adjusted outcome estimates over a strategy-only baseline.

Potential outputs include probability, expected return/drawdown and confidence. Labels and evaluation must include execution costs and avoid selection leakage.

## AI-008 — Regime Detection

**Research status:** DEFERRED.

Hypothesis: an explicit trending/sideways, volatility or risk-on/off regime representation improves a downstream validated decision.

Descriptive clusters are not automatically actionable regimes. Evaluation must test the downstream use.

## AI-009 — Adaptive Strategy Selection

**Research status:** DEFERRED.

Hypothesis: regime-conditioned selection among already validated strategies improves out-of-sample account outcomes over a fixed selection rule.

Prerequisites: validated candidate strategies, nested model-selection controls, complete configuration propagation and account-valid metrics.

## AI-010 — AI-Assisted Risk Management

**Research status:** DEFERRED.

Candidate capabilities include bounded allocation suggestions, position-size adjustments, concentration detection, correlation-aware exposure and drawdown adaptation.

AI output remains advisory and constrained. Hard exposure, order and loss controls remain deterministic and authoritative.

## Research flow

~~~text
point-in-time data
        ↓
reproducible features
        ↓
deterministic baseline and model
        ↓
calibrated probability/confidence
        ↓
validated strategy decision
        ↓
deterministic risk controls
        ↓
execution
~~~

## Promotion rule

Promotion from this ledger requires a roadmap proposal and, where the design changes a durable boundary, an architecture decision. The proposal must carry the experiment evidence, remaining failure modes, operational cost and monitoring requirement. Research status never grants order authority.
