# Kanasu — AI Research Backlog

This document records AI capabilities that may eventually become
part of Kanasu.

The objective is not to add AI merely for the sake of using AI.

AI components must demonstrate measurable improvement over a
well-defined baseline.

---

## AI-001 — News Sentiment Model

Goal:
Determine whether newly published information is likely positive,
negative or neutral for a company/security.

Potential inputs:
- News headline
- Article text
- Source
- Publication timestamp
- Company
- Sector
- Historical price reaction

Future evaluation:
Compare AI sentiment against subsequent market behaviour.

---

## AI-002 — Company News Intelligence

Goal:
Convert large amounts of company-related news into structured
information.

Potential outputs:
- Event type
- Importance
- Sentiment
- Expected impact
- Confidence
- Affected company
- Affected sector

---

## AI-003 — Historical Condition Probability

Goal:
Given a current market condition, find historically similar
conditions and estimate the probability of future outcomes.

Potential features:
- Trend
- Volatility
- Volume
- Momentum
- Price structure
- Market regime
- Time of day
- Relative market strength

---

## AI-004 — Support / Resistance Intelligence

Goal:
Identify significant support and resistance areas using multiple
sources of evidence rather than a single technical indicator.

Potential inputs:
- Historical price reactions
- Volume
- Swing points
- Volatility
- Market structure
- Timeframe agreement

---

## AI-005 — Big Money Flow

Goal:
Estimate institutional or large-participant activity.

Potential inputs may include:
- Volume
- Delivery data
- Open interest
- Futures data
- Options data
- Block/bulk activity
- Market breadth

Important:
"Big money flow" must be defined quantitatively before attempting
to claim accuracy.

---

## AI-006 — Social / Telegram Sentiment

Goal:
Detect emerging narratives and sentiment changes.

Potential outputs:
- Sentiment
- Topic
- Velocity
- Unusual activity
- Confidence

Important:
Data availability, reliability, manipulation and legal/ToS
constraints must be evaluated.

---

## AI-007 — Trade Quality Model

Goal:
Estimate the probability that a candidate trade will produce a
positive risk-adjusted outcome.

Potential output:

Trade Quality Score
Probability of Profit
Expected Return
Expected Drawdown
Confidence

---

## AI-008 — Regime Detection

Goal:
Identify the current market regime.

Examples:
- Trending
- Sideways
- High volatility
- Low volatility
- Risk-on
- Risk-off

---

## AI-009 — Adaptive Strategy Selection

Goal:
Determine which validated strategy is most appropriate for the
current market regime.

Important:
The AI should select among validated strategies rather than
inventing trades without constraints.

---

## AI-010 — AI-Assisted Risk Management

Potential capabilities:

- Dynamic risk allocation
- Position-size adjustment
- Risk concentration detection
- Correlation-aware exposure
- Drawdown adaptation

Important:
AI must never bypass hard safety/risk controls.

---

## AI Development Principle

Kanasu AI should initially be an intelligence layer around a
deterministic trading system.

AI recommendations must pass through:

Market Data
    ↓
Feature Engineering
    ↓
AI / Statistical Model
    ↓
Probability / Confidence
    ↓
Strategy Decision
    ↓
Risk Controls
    ↓
Execution Engine

Hard risk controls remain deterministic.