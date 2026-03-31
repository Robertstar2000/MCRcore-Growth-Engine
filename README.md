# MCRcore Growth Engine

Automated B2B lead generation and nurturing pipeline for MCRcore's managed IT and cybersecurity services.

## ⚠️ Restore Instructions (Fresh Hermes Instance)

This repo contains the **complete source code** of the MCRcore Growth Engine, ready to be deployed on any new Hermes instance.

### Steps to Restore on a New Instance:

```bash
# 1. Clone the repo
git clone https://github.com/Robertstar2000/MCRcore-Growth-Engine.git
cd MCRcore-Growth-Engine

# 2. Create .env from example
cp .env.example .env
# Fill in all PLACEHOLDER values in .env

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
python main.py init-db

# 5. Run the daily pipeline
python main.py run-daily
```

### Docker Deployment:

```bash
cp .env.example .env
# Fill in .env values
docker-compose up mcr-engine
```

---

## Project Structure

```
mcr-growth-engine/
├── main.py                      # CLI entry point / scheduler
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container image
├── docker-compose.yml            # Multi-service orchestration
├── .env.example                  # Environment variable template
│
├── src/
│   ├── agents/                   # 15 agent modules
│   │   ├── base_agent.py
│   │   ├── lead_discovery_agent.py
│   │   ├── lead_enrichment_agent.py
│   │   ├── scoring_agent.py
│   │   ├── offer_matching_agent.py
│   │   ├── daily_ranking_agent.py
│   │   ├── outreach_personalization_agent.py
│   │   ├── compliance_agent.py
│   │   ├── reply_classification_agent.py
│   │   ├── escalation_agent.py
│   │   ├── erp_signal_agent.py
│   │   ├── source_compliance_agent.py
│   │   ├── nurture_cadence_agent.py
│   │   └── daily_orchestrator_agent.py
│   ├── skills/                   # 11 skill modules
│   ├── services/                 # 6 service modules
│   ├── templates/                # Email template blocks
│   └── utils/                    # 8 utility modules
│
├── config/                      # Business configuration
│   ├── settings.py               # Environment-driven settings
│   ├── icp_rules.py              # Ideal Customer Profile
│   ├── service_catalog.py        # Service packages
│   ├── geo_routing.py
│   ├── source_policy.py
│   └── differentiators.py
│
├── db/                          # Database layer
│   ├── database.py
│   ├── models.py
│   ├── repositories.py
│   ├── migrations/
│   └── seeds/
│
└── logs/                        # Runtime logs (gitkeep)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py run-daily` | Full daily pipeline |
| `python main.py discover` | Lead discovery |
| `python main.py enrich` | Lead enrichment |
| `python main.py score` | Scoring + ranking |
| `python main.py outreach` | Generate outreach emails |
| `python main.py process-replies` | Process inbox replies |
| `python main.py init-db` | Initialize database |
| `python main.py kpi` | Daily KPIs |
| `python main.py schedule` | Start scheduler daemon |

## Pipeline Flow

```
CSV/Inbound → LeadDiscovery → Enrichment → ERPSignal
    → Scoring → OfferMatching → DailyRanking → Teams Alert
    → Outreach → Compliance → SMTP
    → MailboxProcessor → ReplyClassification → Escalation → Teams Alert
    → NurtureCadence
```

---

## Backup Info

- **Last Backup**: March 31, 2026 at 10:07 AM ET
- **Backup Method**: Hermes Agent → GitHub API
- **Files Backed Up**: 64 source files + docs
- **Secrets**: None (code uses os.getenv() with PLACEHOLDER markers)

## ❌ NOT Backed Up

- `.env` (contains real credentials — never push to git)
- Database files (`.db`, `.sqlite`)
- Log files
- `test_data/` (if any)
