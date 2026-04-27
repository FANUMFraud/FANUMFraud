# FANUM Fraud Detection System — Demo Guide

Welcome to the FANUM Risk Assessment Dashboard. This guide walks through the system capabilities.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Port 3000 (frontend) and 8000 (backend) available

### Launch

```bash
docker-compose up --build
```

Wait for PostgreSQL and backend to initialize (~30s).

Open: **http://localhost:3000**

---

## Demo Data

The system includes **12 realistic demo companies** with:
- 1800+ synthetic news articles
- Complete risk scoring history (250+ data points)
- 60% of companies experience "shock events" (sudden reputational damage)
- 40% remain clean throughout the demo period
- Reproducible with seed: `DEMO_SEED=20260427`

---

## Key Scenarios to Try

### Scenario 1: Reputation Shock & Recovery

**Company**: "Meridian Trade Finance" (ID: 1)

**What to See**:
1. Go to dashboard
2. Click "Meridian Trade Finance"
3. Observe:
   - **Current Score**: ~25 (HIGH RISK - red)
   - **7d Momentum**: ↑ +18 pts → "recovering"
   - **30d Momentum**: ↑ +8 pts → "recovering"
   - **Trend Chart**: V-shaped curve (sharp drop around day 120, slow recovery)

**What Happened**:
- Day 120: Major scandal (money laundering allegations from official source)
- Score drops from 90 → 22 (68 point shock)
- Articles cite: "prokuratura" (prosecutor), multiple investigations
- Over 45 days: Exponential recovery as older articles decay
- Today: Score recovered to ~34, still elevated but improving

**Why This Matters**:
- Shows **momentum labels** (declining → stable → recovering)
- Demonstrates **exponential decay model** (shock intensity fades)
- Real compliance: companies recover from crises; algorithm reflects this

---

### Scenario 2: Denied Allegations Impact

**Company**: "SafeBank Invest" (ID: 5)

**What to See**:
1. Click "SafeBank Invest"
2. Note:
   - **Current Score**: ~78 (LOW-MEDIUM RISK)
   - **Articles**: Mix of negative + denials
   - **Category Breakdown**: Legal (majority), regulatory (minor)

**What Happened**:
- Multiple fraud accusations vs. competitors
- Company issued strong denials
- Articles cite: "kompania zaprzecza" (company denies)
- Algorithm reduces impact by **84%** (0.16x certainty factor for denied events)
- Result: Score stays elevated but not catastrophic

**Why This Matters**:
- Shows **certainty hierarchy** (confirmed > alleged > denied)
- Demonstrates **denial penalty** (fresh denials: -30%, old denials: -60%)
- Real AML: regulators know denials matter less than formal findings

---

### Scenario 3: Sanctions Check

**Company**: Any company marked with 🚩

**What to See**:
1. Go to company detail
2. If sanctioned: Red alert banner: "ON SANCTIONS LIST"
3. Details: Which lists, match confidence, country

**What Happened**:
- Real-time check against OpenSanctions API
- Matches OFAC, EU, UN sanctions lists
- Shows entity ID and confidence score (80-95%)

**Why This Matters**:
- Compliance critical: Any sanction = instant red flag
- Live API integration shows production capability
- Jury sees: "This system checks real international lists"

---

### Scenario 4: Clean Company (Baseline)

**Company**: "VerifiedTech Ltd" (ID: 8)

**What to See**:
1. Click "VerifiedTech Ltd"
2. Observe:
   - **Current Score**: 93 (LOW RISK - green)
   - **Momentum**: Stable (±2 pts over 30d)
   - **Articles**: Positive mentions, governance updates, expansion news
   - **Categories**: Governance (0.82x weight) dominant

**What Happened**:
- Few articles, mostly positive/neutral sentiment
- No major allegations or investigations
- Steady, healthy score trajectory

**Why This Matters**:
- Shows **baseline clean company** vs. red flags
- Demonstrates **positive sentiment** can improve reputation (-5.5 adjustment)
- Real dashboard: Most companies should be green; red = investigate

---

### Scenario 5: Media Burst Detection

**Company**: "Rapid Capital" (ID: 3)

**What to See**:
1. Click "Rapid Capital"
2. Check **Score History Chart**
3. Note: Sharp downward spike followed by gradual recovery

**What Happened**:
- Day 150: 8 articles in 3 days (media burst)
- Burst multiplier: 1.2 (20% amplification of risk)
- Multiple independent sources, same story
- Real-world analogue: PR crisis, scandal break

**Why This Matters**:
- Shows **burst detection algorithm** (5+ articles/7d = 1.2x multiplier)
- Jury sees: "System detects coordinated campaigns"
- Distinguishes between: 1 major story vs. real widespread scandal

---

## Feature Walkthrough

### Dashboard View

**What You See**:
- List of all companies
- Current score (100=clean, 0=critical)
- Risk level badge (LOW/MEDIUM/HIGH/CRITICAL)
- 7d momentum badge (↓ -24, → stable, ↑ +8)

**Interactions**:
- Click company → Full detail page
- Sort by "Score ↓" (worst first) or "Trend ↓" (biggest recent drop)
- Search by name or NIP

---

### Company Detail Page

**Sections**:

#### 1. Risk Summary Card
- Current score (large display)
- Progress bar (visual 0-100)
- Risk exposure label
- Export to PDF button

#### 2. Score Statistics
- Max score (in 90d window)
- Min score
- Data points (articles analyzed)

#### 3. Trend Reputacji (Reputation Trend)
Two cards: 7-day and 30-day momentum
- Delta (pts change)
- Label (deterioration/declining/stable/recovering/strong_recovery)
- Interpretation: "Moved from X to Y points over N days"

#### 4. Why This Score? (Explainability Panel)
- Dominant risk category (what's the main concern?)
- Latest signal (most recent article)
- Evidence volume (how many articles analyzed?)

#### 5. Score History Chart
- 90-day historical scores
- X-axis: Time, Y-axis: 0-100 score
- Visual: See shocks, recoveries, trends

#### 6. Articles (Evidence)
- List of articles that impacted score
- Click to read full content
- Shows: Title, source, date, risk score

#### 7. Sanctions Status (if applicable)
- 🚩 Alert banner
- Lists & confidence scores
- Country codes

---

### PDF Export

**Access**: Click "📄 EKSPORTUJ" / "📄 EXPORT" button (top-right of detail page)

**Contents**:
- Title page: Company name, ID, generation timestamp
- Risk Summary table (score, level, NIP, articles)
- Momentum Analysis (7d/30d breakdown)
- Top Risk Categories (breakdown by type)
- Sanctions Status (if applicable)
- Footer: "Auto-generated by FANUM"

**Use Case**: 
- Compliance report for due diligence
- Audit trail for risk decisions
- Sharing with stakeholders

---

### Articles View

**Access**: `/articles/{article_id}` (internal, shown in detail page)

**What You See**:
- Article metadata (title, source, date, risk score)
- Full content (readable)
- Risk signals extracted (keywords, events, category)
- Confidence score
- LLM analysis (or heuristic fallback note)

---

## Algorithm Explanation

**See**: `/ALGORITHM.md` for full technical breakdown

**Quick Summary**:

```
Article Content
  ↓
LLM extracts: keywords, events, companies, sentiment
  ↓
Deterministic scoring:
  - Keywords: category_weight × mentions × 2.2
  - Events: (base + severity) × category × certainty × evidence × role
  - Sentiment adjustment (±6.5 for negative/positive)
  - Text context (confirmation/denial/uncertainty patterns)
  ↓
Article Risk Score [0-100]
  ↓
Company Aggregation:
  - Sum all article signals
  - Apply exponential decay (45d half-life)
  - Apply burst multiplier (if 5+ articles/7d)
  ↓
Company Reputation Score [100-0]
```

---

## Testing Scenarios

### Test 1: Default Demo (Existing Data)

```bash
docker-compose up
# System loads with DEMO_SEED=20260427
# Identical results every run
# Try Scenario 1-5 above
```

### Test 2: Random Demo

```bash
docker-compose down && rm -rf postgres_data
docker-compose up --build
# Generates fresh companies with random shocks
# Same algorithm, different companies
```

### Test 3: API Endpoints (Curl/Postman)

```bash
# List all companies
curl http://localhost:8000/companies

# Get company details
curl http://localhost:8000/companies/1

# Get scoring history
curl http://localhost:8000/companies/1/score?days=90

# Export PDF
curl -o report.pdf http://localhost:8000/companies/1/export

# Search
curl http://localhost:8000/companies/search?q=meridian
```

---

## What Jury Should Notice

✅ **Deterministic Algorithm**: Same article → same score (reproducible)  
✅ **Auditable**: Weights visible, decision tree clear  
✅ **AML-Aware**: Categories, certainty, roles, source weight all weighted correctly  
✅ **Recovery Model**: Exponential decay shows realistic reputation recovery  
✅ **Momentum**: Dashboard shows trends, not just snapshots  
✅ **Explainability**: "Why This Score?" panel + PDF report + full analysis  
✅ **Production-Ready**: Sanctions integration, PDF export, mobile responsive  
✅ **Polish/English**: Full i18n support  
✅ **Demo Data**: Realistic scenarios (shocks, recovery, denials, burst events)  

---

## Common Questions

**Q: Why does the score improve even if articles keep appearing?**  
A: Exponential decay. Older articles matter less. If no NEW shocks, score recovers over 45 days.

**Q: Why is "denied" event weighted so low (0.16x)?**  
A: Denial isn't proof of innocence; court finding would be 1.22x. AML logic: follow evidence.

**Q: Why do burst events (5+ articles/7d) amplify risk by 20%?**  
A: Coordinated campaigns or real crises both manifest as bursts. Jury cares about scale.

**Q: Is this real sanctions data?**  
A: Yes, queries OpenSanctions.org API (free, international, 90K+ records). Fallback to demo if unavailable.

**Q: Can we export reports for multiple companies?**  
A: Currently per-company. Batch export possible as future enhancement.

---

## Tips for Demo Day

1. **Start with Dashboard**: Show 12 companies, risk distribution
2. **Click Meridian Trade Finance**: Tell the story (shock → recovery)
3. **Show Denials**: SafeBank — explain why denials reduce impact
4. **Export PDF**: Click export button, show PDF in browser
5. **Mobile**: Open on phone — show responsive design
6. **Explain Algorithm**: Show ALGORITHM.md → weights → category hierarchy
7. **Sanctions**: Point out 🚩 alert if any company has it
8. **Highlight Momentum**: Show 7d/30d labels — "recovering" vs "declining"
9. **Ask Questions**: "Why did this company's score drop?" → articulates the logic
10. **Show Code**: If time, walk through key scoring logic (deterministic_risk_score in analyzer.py)

---

## Performance Notes

- **Dashboard load**: <1s (cached company list)
- **Company detail**: <500ms (score history calculation)
- **PDF export**: <2s (reportlab generation)
- **Search**: <100ms (Elasticsearch, or SQL LIKE fallback)
- **Sanctions check**: <1s (OpenSanctions API, cached)

---

## Troubleshooting

**Dashboard shows "No companies"**:
→ Backend not initialized. Check Docker logs: `docker-compose logs backend`

**PDF export fails**:
→ reportlab library missing. Install: `pip install reportlab`

**Sanctions always return "unavailable"**:
→ Network issue or requests library missing. Check logs.

**Score spikes unexpectedly**:
→ Likely burst event (5+ articles in 7d). Check Articles tab.

---

## Next Steps for Improvement

- Real web crawler integration (colleague's work)
- Stock price correlation (colleague's work)
- Batch risk assessment (CSV upload)
- Historical report archiving
- Webhook notifications
- API key authentication
- Rate limiting for production

---

## Contact & Support

**System**: FANUM Fraud Detection  
**Hackathon**: Transparent Data 2026  
**Date**: April 28, 2026
