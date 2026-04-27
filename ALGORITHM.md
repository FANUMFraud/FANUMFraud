# FANUM Fraud Detection System — Deterministic Risk Scoring Algorithm

## Overview

This document describes the **deterministic risk scoring algorithm** used in the FANUM system to assess company reputational risk based on media analysis.

**Key Philosophy**: The algorithm separates data extraction (handled by LLM) from risk calculation (deterministic, auditable).

---

## System Architecture

```
Input: News Article
  ↓
LLM or Heuristic Analysis
  ├─ Extract companies mentioned
  ├─ Extract risk events (category, severity, certainty)
  ├─ Extract keywords (with weights)
  ├─ Detect sentiment (negative/mixed/neutral/positive)
  └─ Output: Structured JSON (not a final score)
  ↓
Deterministic Risk Scoring
  ├─ Apply category weights
  ├─ Apply certainty factors
  ├─ Apply role context
  ├─ Apply sentiment adjustments
  ├─ Calculate article risk score [0-100]
  └─ Output: ArticleRiskAnalysis
  ↓
Company Reputation Aggregation
  ├─ Accumulate risk signals over time
  ├─ Apply exponential decay (45-day half-life)
  ├─ Calculate momentum (7d, 30d)
  └─ Output: CompanyReputationScore [100-0]
  ↓
Final Dashboard
  ├─ Show current score
  ├─ Show momentum trend
  ├─ Show top risk signals
  ├─ Show sanctions status
  └─ Export PDF report
```

---

## Level 1: Article Risk Score [0-100]

Each article produces a risk score indicating how risky the content is for the mentioned company.

### Risk Score Calculation

```
raw_score =
  adjusted_core_points
  + sentiment_adjustment
  + text_context_adjustment
  + lexical_backstop_bonus

article_risk_score = clamp(raw_score, 0.0, 100.0)
```

### 1.1 Core Points Calculation

Core points combine keyword and event analysis:

```
core_points = keyword_points + event_points

adjusted_core_points =
  core_points
  × role_context_factor
  × certainty_context_factor
```

#### Keyword Points

```
keyword_points =
  min(mentions, 4)
  × keyword_weight
  × category_weight
  × 2.2 (multiplier)
```

**Category Weights** (reflect AML compliance risk hierarchy):

| Category | Weight | Rationale |
|----------|--------|-----------|
| money_laundering | 1.50 | AML compliance — highest regulatory risk |
| sanctions | 1.40 | International sanctions — asset freeze |
| corruption | 1.32 | Bribery/corruption — legal + reputational |
| fraud | 1.20 | Customer fraud — moderate damage |
| embezzlement | 1.15 | Internal theft — moderate damage |
| legal | 0.98 | General litigation — common, low weight |
| regulatory | 0.90 | KNF/UOKiK notices — routine |
| governance | 0.82 | Board changes — market-weighted |
| other | 0.60 | Unknown category — minimal weight |

Example:
```
Article mentions "money laundering" 3 times
mentions = 3
weight = 1.0 (from LLM)
category = money_laundering → 1.50
keyword_points = 3 × 1.0 × 1.50 × 2.2 = 9.9 points
```

#### Event Points

```
event_points =
  (EVENT_BASE_POINTS + severity × EVENT_SEVERITY_POINTS)
  × category_weight
  × certainty_factor
  × evidence_factor
  × role_factor

clamped_event_points = min(event_points, 34.0)
```

**Constants**:
- EVENT_BASE_POINTS = 4.5
- EVENT_SEVERITY_POINTS = 15.0
- EVENT_MAX_POINTS = 34.0

**Certainty Factors** (confidence in the allegation):

| Certainty | Factor | Interpretation |
|-----------|--------|-----------------|
| confirmed | 1.22 | Final verdict, proven facts |
| investigated | 1.00 | Active investigation/formal proceedings |
| alleged | 0.70 | Claims/accusations (25% discount) |
| rumor | 0.44 | Unconfirmed reports (56% discount) |
| denied | 0.16 | Company denies (84% discount) |

**Evidence Factor**:
```
evidence_factor = 1.0 + min(evidence_count, 4) × 0.06
max_evidence_factor = 1.24
```

More evidence → stronger event impact.

**Role Factors** (company's position in the event):

| Role | Event Factor | Context Factor |
|------|--------------|---|
| accused | 1.15 | 1.10 |
| regulator | 1.00 | 0.98 |
| witness | 0.96 | 0.95 |
| mentioned | 0.92 | 0.90 |
| unknown | 0.86 | 0.86 |
| victim | 0.65 | 0.62 |

Being **accused** increases risk; being a **victim** decreases it.

Example:
```
Event:
- category = corruption → 1.32
- severity = 0.8
- certainty = investigated → 1.00
- evidence = 3 fragments → 1.18
- role = accused → 1.15

event_points = (4.5 + 0.8×15) × 1.32 × 1.0 × 1.18 × 1.15
             = 16.5 × 1.32 × 1.0 × 1.18 × 1.15
             = 29.5 points
```

### 1.2 Sentiment Adjustment

**Sentiment Scale**:

| Sentiment | Adjustment | Effect |
|-----------|------------|--------|
| negative | +6.5 | Strengthens risk score |
| mixed | +2.5 | Moderate risk |
| neutral | 0.0 | No impact |
| positive | -5.5 | Reduces risk score |

Positive articles can improve reputation (negative contribution to risk).

**Safety Rule**: If core_points ≤ 0, sentiment_adjustment is clamped to ≤ 0.
This prevents pure positive sentiment from creating risk on a clean article.

### 1.3 Text Context Adjustment

System scans article text for contextual patterns that modify interpretation:

**Confirmed Patterns** (add risk):
```
"skazany" (convicted), "wyrok" (verdict), "confirmed"
→ contribution: +2.4 per match
```

**Investigated Patterns** (add mild risk):
```
"śledztwo" (investigation), "postępowanie" (proceedings)
→ contribution: +0.8 per match
```

**Uncertainty Patterns** (reduce risk):
```
"rzekomy" (alleged), "rumor", "alleged"
→ contribution: -1.8 per match
```

**Denial Patterns** (strong risk reduction):
```
"zaprzecza" (denies), "oddalono" (dismissed)
→ contribution: -2.8 per match
```

**Positive Patterns** (reduce risk):
```
"uniewinniony" (acquitted), "brak nieprawidłowości" (no violations)
→ contribution: -2.4 per match
```

**Clamping**:
```
text_context_adjustment ∈ [-18.0, +12.0]
```

### 1.4 Lexical Backstop Bonus

If LLM fails to extract keywords/events, system uses regex fallback.

**Trigger**: No keywords AND no events AND 2+ risk categories detected by regex

**Calculation**:
```
lexical_backstop_bonus =
  LEXICAL_GAP_BONUS_BASE +
  min(total_backstop_points × LEXICAL_GAP_BONUS_SCALE, LEXICAL_GAP_BONUS_CAP)

Base = 12.0, Scale = 0.45, Cap = 10.0
```

Ensures fallback articles still get scored when LLM unavailable.

### 1.5 Final Article Score

```
raw_score =
  adjusted_core_points
  + sentiment_adjustment
  + text_context_adjustment
  + lexical_backstop_bonus

article_risk_score = clamp(raw_score, 0.0, 100.0)
article_risk_score = round(score, 2)  # 2 decimal places
```

**Risk Level Mapping**:

| Score | Level |
|-------|-------|
| 0-19.99 | Low |
| 20-44.99 | Medium |
| 45-74.99 | High |
| 75-100 | Critical |

---

## Level 2: Company Reputation Score [100-0]

Aggregates article risk signals over time to compute a company's overall reputation.

### 2.1 Risk Signal

Each article generates a **RiskSignal**:

```python
signal_impact =
  article_risk_score
  × sentiment_factor
  × confidence_factor
  × source_weight
  × denial_penalty
```

**Sentiment Factor**:
| Sentiment | Factor |
|-----------|--------|
| negative | 1.0 |
| mixed | 0.7 |
| neutral | 0.25 |
| positive | -0.25 |

**Confidence Factor**:
```
confidence_factor = 0.35 + (0.65 × article_confidence)
range: [0.35, 1.0]
```

Even weak confidence doesn't zero out the signal.

**Source Weight** (source credibility):

| Source | Weight | Tier |
|--------|--------|------|
| Official (KNF, OFAC, court) | 1.35 | Official |
| Business media (Bloomberg, Reuters) | 1.08 | Business |
| Standard | 1.00 | Standard |
| Local/social | 0.88 | Local |
| Unknown | 0.72 | Unknown |

**Denial Penalty** (if event is denied):
```
denial_penalty = 1.0 - (0.3 × min(days_since_denial / 14, 1.0))
floor = 0.4

Example:
1 day old denial → penalty = 0.7 (30% reduction)
14+ days old denial → penalty = 0.4 (60% reduction)
```

### 2.2 Exponential Decay

Risk signals decay over time with **45-day half-life**:

```
decay_multiplier = exp(-λ × age_days)
λ = ln(2) / 45 ≈ 0.0154

Example:
After 45 days: impact × 0.5
After 90 days: impact × 0.25
After 135 days: impact × 0.125
```

This models reputation recovery after shocks.

### 2.3 Burst Detection

If 5+ articles about a company in 7 days, multiply risk by up to 1.2:

```
if articles_in_7d < 5:
  multiplier = 1.0 + (articles_in_7d / 5) × 0.2

if articles_in_7d ≥ 5:
  multiplier = 1.2
```

Detects coordinated media campaigns or real crises.

### 2.4 Final Company Score

```
active_risk = sum(decayed_impact of all signals)

company_reputation_score = clamp(100 - active_risk, 0, 100)
```

**Example**:
```
Total decayed risk = 35 points
Score = 100 - 35 = 65

Company is moderately risky (65/100 is medium-high risk)
```

---

## Level 3: Momentum Analysis

Tracks how company reputation changes over 7 and 30 days.

### 3.1 Momentum Calculation

```
delta = current_score - past_score_N_days_ago
momentum_label = _momentum_label(delta)
```

### 3.2 Labels

| Delta | Label | Meaning |
|-------|-------|---------|
| ≤ -20 | rapid_deterioration | Score dropped >20 pts fast |
| -20 to -5 | declining | Worsening trend |
| -5 to +5 | stable | No significant change |
| +5 to +20 | recovering | Reputation improving |
| > +20 | strong_recovery | Rapid reputation recovery |

---

## Sanctions Integration

### Real-Time Checking

Each company is checked against **OpenSanctions API** for presence on:
- OFAC (US Office of Foreign Assets Control)
- EU sanctions lists
- UN sanctions lists
- National sanctions lists

**If Match Found**:
- Company display includes 🚩 **SANCTIONS ALERT**
- All scores immediately flagged
- PDF reports highlight sanctions status

---

## Confidence Score [0.2-0.95]

Indicates reliability of the article analysis:

```
base = 0.22

+ 0.03 per keyword (max 8 keywords)
+ 0.09 per event (max 5 events)
+ 0.025 per evidence piece (max 6)
+ 0.05 per confirmed/investigated event (max 3)
+ 0.06 if text ≥ 800 chars
+ 0.03 if text ≥ 300 chars
+ 0.04 if primary company identified

- 0.04 per rumor/denied event (max 3)
- 0.015 per uncertainty phrase (max 4)

final = clamp(base, 0.2, 0.95)
```

High confidence = more structured evidence.

---

## PDF Report Export

Each company can be exported as a compliance-ready PDF containing:

1. **Risk Summary** (current score, level, NIP, articles count)
2. **Momentum Analysis** (7d and 30d trends)
3. **Top Risk Categories** (breakdown by event type)
4. **Sanctions Status** (if applicable)
5. **Metadata** (generation date, system version)

---

## Why This Approach?

✅ **Auditable**: Every score can be traced back to specific rules  
✅ **Deterministic**: No randomness; same article always → same score  
✅ **Explainable**: Jury understands weights and logic  
✅ **Contextual**: Handles Polish/English text, flection, synonyms  
✅ **AML-Aligned**: Weighs compliance categories correctly  
✅ **Resilient**: Fallback heuristic when LLM unavailable  
✅ **Recovery-Aware**: Exponential decay models reputation recovery  
✅ **Time-Aware**: Momentum shows trends, not just snapshots  

---

## Comparison vs. Naive Keyword Matching

| Aspect | Naive Approach | FANUM Algorithm |
|--------|---|---|
| "Money laundering" mention | +10 always | +1.5 to +34 (depends on certainty, role, evidence) |
| Denied accusations | Still counts full | Reduced 84% (0.16x factor) |
| Positive articles | Ignored | Can improve score (-5.5 adjustment) |
| Article spam (10x in 1 day) | No amplification | +20% burst multiplier |
| Company as victim | Same as accused | 60% reduction (0.65x role factor) |
| Recovery after shock | No decay | Exponential (45d half-life) |

---

## Testing & Validation

The algorithm is validated on 12 demo companies with:
- 1800+ synthetic articles
- 268+ historical score points
- 60% companies with shock events (day 120-200)
- 40% clean companies
- Reproducible with `DEMO_SEED=20260427`

---

## Version

**Algorithm Version**: `deterministic-risk-v2.1`  
**Last Updated**: 2026-04-28  
**Maintained By**: FANUM Fraud Detection Team
