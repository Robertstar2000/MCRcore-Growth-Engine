# MCRcore Growth Engine

Automated B2B lead generation and nurturing pipeline for MCRcore's
managed IT and cybersecurity services.

The engine discovers leads, enriches them with company intelligence,
scores them against the Ideal Customer Profile, generates personalized
outreach, processes replies, and escalates hot opportunities to the
sales team -- all with full audit trails and CAN-SPAM compliance.


## Quick Start

```bash
# 1. Clone and enter the project
cd mcr-growth-engine

# 2. Create your environment file
cp .env.example .env
# Edit .env and fill in all PLACEHOLDER values

# 3. Initialize the database
python main.py init-db

# 4. Run the full daily pipeline
python main.py run-daily
```

### Docker Quick Start

```bash
cp .env.example .env
# Fill in .env values

# Initialize the database (one-time)
docker-compose --profile init run mcr-init

# Run the daily pipeline
docker-compose up mcr-engine

# Or start the scheduler for automated daily runs
docker-compose up -d mcr-scheduler
```


## CLI Commands

| Command                           | Description                                    |
|-----------------------------------|------------------------------------------------|
| `python main.py run-daily`        | Run the full daily pipeline (all steps)        |
| `python main.py discover`         | Lead discovery from approved sources           |
| `python main.py enrich`           | Enrich all un-enriched leads                   |
| `python main.py score`            | Score leads + match offers + daily ranking     |
| `python main.py outreach`         | Generate personalized outreach emails          |
| `python main.py process-replies`  | Fetch and classify inbox replies               |
| `python main.py nurture`          | Run nurture cadence processing                 |
| `python main.py import-csv FILE`  | Import leads from a CSV file                   |
| `python main.py init-db`          | Create tables and seed reference data          |
| `python main.py kpi`              | Calculate and display daily KPIs               |
| `python main.py schedule`         | Start scheduler daemon (daily runs at 06:00)   |
| `python main.py schedule --time HH:MM` | Start scheduler at custom UTC time       |


## Architecture Overview

```
main.py                      CLI entry point / scheduler
  |
  +-- src/agents/            Agent layer (business logic orchestration)
  |     base_agent.py          Abstract base with logging and audit
  |     lead_discovery_agent   Finds new leads from approved sources
  |     lead_enrichment_agent  Researches companies via LLM
  |     scoring_agent          Multi-dimensional lead scoring
  |     offer_matching_agent   Maps leads to service packages
  |     daily_ranking_agent    Produces daily top-5 priority list
  |     outreach_personalization_agent  Generates personalized emails
  |     compliance_agent       CAN-SPAM gatekeeper (9-check gate)
  |     reply_classification_agent  Classifies inbound replies via LLM
  |     escalation_agent       Builds handoff packets for sales
  |     erp_signal_agent       Detects ERP and industry signals
  |     source_compliance_agent  Validates data source provenance
  |
  +-- src/skills/            Pure-function skill modules
  |     lead_scoring           Scoring math and weights
  |     offer_matching         Offer routing logic
  |     compliance_check       CAN-SPAM rule functions
  |     reply_intent           Reply classification taxonomy
  |     erp_signal_detection   ERP keyword banks
  |     audit_first_outreach   Audit-first email templates
  |     package_specific_email Package-specific templates
  |     escalation_packet      Handoff packet builder
  |     analytics_reporting    KPI calculations
  |     icp_targeting          ICP matching functions
  |
  +-- src/services/          Cross-cutting services
  |     csv_importer           CSV file ingestion
  |     mailbox_processor      IMAP inbox processing pipeline
  |     suppression_manager    Email suppression list
  |     deliverability_monitor Bounce rate / domain health
  |     inbound_intake         Web form processing
  |
  +-- src/templates/         Email template blocks
  |     message_blocks         Differentiator, industry, title blocks
  |
  +-- src/utils/             Shared utilities
  |     llm_client             OpenAI-compatible LLM wrapper
  |     email_sender           SMTP email sending
  |     email_receiver         IMAP email fetching
  |     email_validator        Format + bounce risk checks
  |     teams_notifier         Microsoft Teams webhook alerts
  |     dedup                  Duplicate hash generation
  |     logger                 Structured logging setup
  |
  +-- config/                Business configuration
  |     settings               Environment-driven settings
  |     icp_rules              Ideal Customer Profile rules
  |     service_catalog        MCRcore service packages
  |     geo_routing            Geography-based routing
  |     source_policy          Approved data sources
  |     differentiators        Competitive differentiator blocks
  |
  +-- db/                    Database layer
        database               Engine, session factory, init_db
        models                 SQLAlchemy ORM models
        repositories           Repository pattern data access
        migrations/            Schema migrations
        seeds/                 Reference data seeding
```

### Data Flow

```
  CSV / Inbound / API / Referral
           |
    LeadDiscoveryAgent     -- normalize, dedup, create Lead
           |
    LeadEnrichmentAgent    -- company research via LLM
           |
    ERPSignalAgent         -- ERP & industry signal detection
           |
    ScoringAgent           -- fit, need, engagement, margin scores
           |
    OfferMatchingAgent     -- map to service package + CTA
           |
    DailyRankingAgent      -- top-5 prioritized leads -> Teams
           |
    OutreachPersonalization -- generate email via templates + LLM
           |
    ComplianceAgent        -- 9-check CAN-SPAM gate
           |
    Email Sending          -- SMTP with rate limiting
           |
    MailboxProcessor       -- fetch replies via IMAP
           |
    ReplyClassificationAgent -- intent classification
           |
    EscalationAgent        -- hot lead -> sales handoff + Teams alert
           |
    NurtureCadenceAgent    -- schedule follow-ups at day 7/30/90
```


## Required API Keys / Credentials

All configuration is via environment variables (`.env` file).

| Variable                   | Purpose                          | Required |
|----------------------------|----------------------------------|----------|
| `DATABASE_URL`             | SQLAlchemy database URL          | Yes      |
| `LLM_API_KEY`             | OpenAI-compatible API key        | Yes      |
| `LLM_API_BASE_URL`        | LLM API endpoint                 | Yes      |
| `LLM_MODEL`               | LLM model name (e.g. gpt-4)     | Yes      |
| `SMTP_HOST`               | Outbound email SMTP server       | Yes      |
| `SMTP_PORT`               | SMTP port (default: 587)         | Yes      |
| `SMTP_USERNAME`           | SMTP authentication username     | Yes      |
| `SMTP_PASSWORD`           | SMTP authentication password     | Yes      |
| `SMTP_USE_TLS`            | Enable TLS (default: true)       | No       |
| `SMTP_FROM_ADDRESS`       | Sender email address             | Yes      |
| `SMTP_RATE_LIMIT_PER_MINUTE` | Max emails per minute         | No       |
| `IMAP_HOST`               | Inbound email IMAP server        | Yes      |
| `IMAP_PORT`               | IMAP port (default: 993)         | Yes      |
| `IMAP_USERNAME`           | IMAP authentication username     | Yes      |
| `IMAP_PASSWORD`           | IMAP authentication password     | Yes      |
| `IMAP_USE_SSL`            | Enable SSL (default: true)       | No       |
| `IMAP_FOLDER`             | Mailbox folder (default: INBOX)  | No       |
| `MS_TEAMS_WEBHOOK_URL`    | Teams webhook for notifications  | No       |
| `LOG_LEVEL`               | Logging level (default: INFO)    | No       |
| `LOG_DIR`                 | Log file directory (default: logs) | No     |


## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python main.py init-db

# Import sample data
python main.py import-csv test_data/sample_leads.csv

# Run individual pipeline steps
python main.py discover
python main.py enrich
python main.py score
python main.py outreach

# Check KPIs
python main.py kpi
```


## License

Proprietary - MCRcore Internal Use Only
