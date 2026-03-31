TECHNICAL ARCHITECTURE SPEC

Project: MCRcore Growth Engine
Version: 2.1
Target platform: Hermes multi-agent automation stack

Architecture overview

The system is a multi-agent sales operations platform built around five core layers:
– Ingestion layer
– Intelligence layer
– Decision layer
– Execution layer
– Governance and reporting layer

Primary purpose:
Acquire, enrich, score, contact, nurture, and escalate B2B leads for MCRcore services using an ICP-tuned outbound motion.

Primary system outcomes:
– 50 new qualified leads per day
– audit-first personalized outreach
– reply-aware pipeline progression
– daily top-5 high-probability queue
– human escalation for likely sales opportunities
– full compliance and audit trail

End of section.

High-level component architecture

2.1 Ingestion layer

Responsible for collecting leads and signals from approved sources.

Components:
– Source connector service
– Lead intake API
– Inbound website form ingestion
– Referral ingestion
– Email inbox listener
– Source policy validator

Inputs:
– LinkedIn Sales Navigator exports or connector feeds
– Apollo.io data
– ZoomInfo data
– Tallman referral inputs
– mcrcore.com inbound form submissions
– association or chamber lead lists from approved sources
– mailbox replies and bounce events

Outputs:
– normalized lead candidates
– inbound inquiry records
– reply events
– source provenance records

2.2 Intelligence layer

Responsible for enrichment, research, and summarization.

Components:
– Company research engine
– Contact enrichment engine
– ERP/industry signal detector
– Service-fit inference engine
– lead memory store

Outputs:
– factual lead summary
– vertical system signals
– pain point hypotheses
– recommended offer
– recommended CTA
– confidence score

2.3 Decision layer

Responsible for scoring, ranking, and routing.

Components:
– ICP fit scorer
– Need scorer
– Engagement scorer
– Margin band estimator
– Priority ranker
– Reply classifier
– Nurture scheduler
– Opportunity escalation router

Outputs:
– lead score
– sales probability band
– next best action
– queue assignment
– escalation decision
– nurture date

2.4 Execution layer

Responsible for sending and updating.

Components:
– Personalized email generator
– Follow-up generator
– outbound mailer
– internal escalation sender
– workflow orchestrator

Outputs:
– first-touch messages
– 7-day messages
– 30-day messages
– 90-day messages
– internal opportunity summaries

2.5 Governance and reporting layer

Responsible for safety, logging, and visibility.

Components:
– Compliance gate
– Suppression manager
– deliverability monitor
– audit logger
– KPI dashboard
– exception manager

Outputs:
– pass/fail send approval
– compliance exception logs
– bounce reports
– opt-out records
– daily KPI summaries

End of section.

Multi-agent runtime design

3.1 Lead Discovery Agent

Consumes:
– source connector output
– ICP targeting rules
– geo rules
– title rules

Produces:
– raw leads
– source metadata
– service hints

3.2 Source Compliance Agent

Consumes:
– raw source records
– source allowlist
– owner override table

Produces:
– approved or blocked source status
– source risk classification

3.3 Lead Enrichment Agent

Consumes:
– approved lead records
– company websites
– public company/contact data

Produces:
– structured enrichment profile
– summary notes
– evidence map

3.4 ERP and Industry Signal Agent

Consumes:
– enrichment text
– website content
– profile signals

Produces:
– Epicor Prophet 21 signal
– Point of Rental signal
– McLeod signal
– DAT Keypoint signal
– logistics/manufacturing/insurance relevance

3.5 Offer Matching Agent

Consumes:
– enrichment profile
– signal profile
– title and geography
– service rules

Produces:
– best-fit package
– best entry offer
– audit-first flag
– recommended CTA

3.6 Scoring Agent

Consumes:
– fit features
– need features
– engagement features
– package fit
– margin rules

Produces:
– fit score
– need score
– engagement score
– margin band
– sales probability
– queue tier

3.7 Outreach Personalization Agent

Consumes:
– lead summary
– package recommendation
– differentiator library
– prior thread history

Produces:
– personalized message draft
– subject line
– CTA
– variation tracking signature

3.8 Reply Classification Agent

Consumes:
– reply text
– full thread
– lead profile
– current stage

Produces:
– class label
– intent confidence
– escalation decision
– nurture update
– opt-out flag

3.9 Opportunity Escalation Agent

Consumes:
– qualified thread
– summary
– score profile
– package recommendation

Produces:
– internal handoff email
– communication timeline
– action recommendation

3.10 Nurture Cadence Agent

Consumes:
– lead state
– last touch date
– reply state
– suppression state

Produces:
– next follow-up date
– stage-specific outreach request

3.11 Deliverability and Compliance Agent

Consumes:
– draft email
– sender config
– suppression data
– legal rule set

Produces:
– send approval
– corrective notes
– risk flags

3.12 Daily Orchestrator Agent

Consumes:
– schedules
– queue status
– job status
– KPIs

Produces:
– daily workflow execution
– backlog decisions
– summary report

End of section.

Required skills architecture

4.1 icp-targeting skill

Purpose:
Turn business strategy into machine-usable targeting rules.

Artifacts:
– target industries
– company-size weights
– geo routing rules
– title priority map
– exclusion list

4.2 approved-source-control skill

Purpose:
Apply source governance before production use.

Artifacts:
– allowlist
– denylist
– pending-review list
– source risk scoring rules

4.3 company-and-contact-research skill

Purpose:
Create factual summaries for company and contact.

Artifacts:
– summary template
– evidence schema
– confidence rules

4.4 erp-and-industry-signal-detection skill

Purpose:
Detect ERP and vertical relevance.

Artifacts:
– keyword sets
– weighted evidence rules
– confidence labels

4.5 offer-matching skill

Purpose:
Map lead to best package and CTA.

Artifacts:
– package routing matrix
– audit-first rules
– geo-service eligibility rules

4.6 lead-scoring skill

Purpose:
Produce probability and priority.

Artifacts:
– weighted scoring model
– probability bands
– tie-break logic

4.7 audit-first-outreach skill

Purpose:
Create cold outbound messages anchored on the technical audit.

Artifacts:
– audit-first messaging templates
– CTA variants
– title-specific language blocks

4.8 package-specific-email skill

Purpose:
Create package-aware emails.

Artifacts:
– Essential Cybersecurity blocks
– Network Monitoring blocks
– Total Plan blocks
– Virtual Servers blocks
– Fractional CIO blocks
– Automation blocks
– Remote work enablement blocks

4.9 reply-intent skill

Purpose:
Classify replies and extract action signals.

Artifacts:
– intent taxonomy
– objection taxonomy
– opt-out detection patterns

4.10 escalation-packet skill

Purpose:
Prepare handoff summaries.

Artifacts:
– internal summary template
– timeline template
– action checklist

4.11 nurture-cadence skill

Purpose:
Schedule and generate timed follow-ups.

Artifacts:
– stage rules
– uniqueness rules
– reset logic

4.12 compliance-check skill

Purpose:
Block unsafe or non-compliant sending.

Artifacts:
– CAN-SPAM checklist
– suppression rules
– sender-auth checks

4.13 analytics-reporting skill

Purpose:
Summarize daily and weekly system health.

Artifacts:
– KPI definitions
– funnel definitions
– anomaly thresholds

End of section.

Data architecture

5.1 Canonical stores

The system should use these core stores:
– Relational operational database
– event log store
– search/index store for research and threads
– queue store
– metrics store

5.2 Core entities

Main entities:
– Lead
– Contact
– Company
– Source
– EnrichmentProfile
– SignalProfile
– ScoreSnapshot
– OutreachEvent
– ReplyEvent
– Opportunity
– SuppressionRecord
– AuditEvent
– WorkflowJob

5.3 Recommended relational model

Lead
– lead_id
– company_id
– contact_id
– source_id
– status
– substatus
– recommended_offer
– recommended_entry_cta
– owner_agent
– created_at
– updated_at

Company
– company_id
– company_name
– domain
– industry
– employee_band
– geography
– summary
– website_url

Contact
– contact_id
– full_name
– title
– email
– profile_url
– role_priority
– do_not_contact

Source
– source_id
– source_name
– source_type
– approved_flag
– risk_level
– provenance_ref

EnrichmentProfile
– enrichment_id
– lead_id
– operational_pain_summary
– it_pain_points
– compliance_signals
– remote_work_signals
– infrastructure_signals
– confidence_score
– updated_at

SignalProfile
– signal_id
– lead_id
– epicor_signal
– por_signal
– mcleod_signal
– dat_keypoint_signal
– manufacturing_signal
– logistics_signal
– insurance_signal
– scaling_signal

ScoreSnapshot
– score_id
– lead_id
– fit_score
– need_score
– engagement_score
– package_fit_score
– margin_band
– sales_probability
– priority_tier
– scored_at

OutreachEvent
– outreach_id
– lead_id
– stage
– package_angle
– subject
– body_hash
– sent_at
– delivery_status
– click_status
– open_status

ReplyEvent
– reply_id
– lead_id
– thread_id
– received_at
– raw_text
– classified_as
– intent_confidence
– opt_out_flag

Opportunity
– opportunity_id
– lead_id
– recommended_package
– estimated_value_band
– estimated_margin_band
– escalated_at
– status

SuppressionRecord
– suppression_id
– email
– reason
– source
– effective_at

AuditEvent
– audit_id
– actor
– entity_type
– entity_id
– action
– before_json
– after_json
– timestamp

WorkflowJob
– job_id
– job_type
– status
– scheduled_at
– started_at
– completed_at
– error_message

End of section.

Workflow architecture

6.1 Daily production workflow

Load source allowlist and suppression list
Pull candidate leads from approved channels
Normalize and deduplicate
Validate source policy
Enrich leads
Detect ERP and industry signals
Match services and CTA
Score and rank
Check mailbox and classify replies
Escalate likely opportunities
Schedule nurture jobs
Select top 5 high-probability unprocessed leads
Generate and send approved messages
Persist logs and metrics
Emit daily report

6.2 Event-driven workflows

Triggered by:
– new reply
– bounce event
– opt-out event
– referral event
– inbound quote form
– manual sales override

Each event must:
– update lead state
– update score if needed
– append audit record
– schedule next action

End of section.

Scoring architecture

7.1 Weighted score model

Final score should combine:
– ICP fit
– need intensity
– service package fit
– engagement
– margin attractiveness
– data confidence

Recommended weighting for first build:
– Fit: 30%
– Need: 25%
– Package fit: 20%
– Engagement: 15%
– Margin: 10%

7.2 Rule overlays

Rules should override score where necessary.

Examples:
– Opt-out overrides all, suppress send
– Invalid email overrides all, suppress send
– Inbound quote request forces high priority
– Referral from Tallman forces boosted priority
– Midwest manufacturing using Epicor gets package-fit boost
– Northern Florida logistics operator gets geo boost for managed services
– North America remote infrastructure need gets virtual-server eligibility boost

End of section.

Messaging architecture

8.1 Message composition model

Each outbound draft should contain:
– personalized opener
– company-context sentence
– pain-point/value connection
– MCRcore differentiator block
– audit-first or service-fit CTA
– compliance footer

8.2 Template logic

Draft generation should pull from:
– title-aware blocks
– industry-aware blocks
– geo-aware service rules
– package-aware value props
– follow-up stage rules

8.3 Uniqueness enforcement

The system should not send materially repetitive messages.

Use:
– body hash comparison
– semantic similarity threshold
– stage-specific angle switching

End of section.

Compliance architecture

9.1 Required pre-send checks

Before any send:
– suppression check
– opt-out check
– source approval check
– contact validity check
– sender identity check
– subject line check
– footer and address check
– unsubscribe mechanism check
– domain auth check

9.2 Delivery safeguards
– throttle initial sending volume
– monitor bounce rates
– monitor complaint signals
– isolate risky campaigns
– block sending on auth failures

End of section.

Security architecture

10.1 Security requirements
– secrets in managed secret store
– role-based permissions by agent
– encryption at rest for sensitive data
– encryption in transit
– audit logging for all state changes
– restricted access to suppression list
– restricted export rights for lead data

10.2 Human control points

Require human review for:
– source approval exceptions
– escalation inbox routing changes
– outbound campaign policy changes
– deletion of suppression records

End of section.

Deployment architecture

11.1 Environments
– local development
– staging
– production

11.2 Deployment units
– orchestrator service
– agent runtime workers
– API gateway
– database
– queue service
– email integration service
– dashboard service

11.3 Operational requirements
– nightly backups
– queue retry policy
– dead-letter queue
– agent health checks
– dashboard alerts

End of section.

BUILD-READY TASK LIST WITH MILESTONES AND ACCEPTANCE TESTS

Project: MCRcore Growth Engine
Delivery style: phased implementation

PHASE 0 — FOUNDATION AND GOVERNANCE

Goal:
Create the baseline rules, data contracts, and environment.

Tasks:
– Create project repository and environment structure
– Define canonical schemas for Lead, Company, Contact, Source, ScoreSnapshot, OutreachEvent, ReplyEvent, Opportunity
– Create source allowlist and denylist tables
– Create service package definitions
– Create differentiator library
– Create title and industry taxonomies
– Define suppression list model
– Define audit log schema
– Create configuration for ICP rules
– Define routing rules for Midwest, Northern Florida, and North America remote delivery

Milestone:
Foundation approved for build

Acceptance tests:
– Schema files validate without errors
– ICP rules can be loaded from config
– source allowlist supports allow, deny, pending-review states
– service package config includes all MCRcore services
– audit events can be written and queried

End of phase.

PHASE 1 — DATA LAYER AND CORE PLATFORM

Goal:
Stand up the persistent backbone.

Tasks:
– Provision relational database
– Provision queue and scheduler
– Provision metrics store
– Build migration scripts
– Build repositories for core entities
– Build event logger
– Build job tracker
– Build suppression manager
– Build configuration loader
– Build admin seed data loader

Milestone:
Operational backend available

Acceptance tests:
– Database migrations run from clean state
– CRUD works for Lead, Company, Contact, Source, ScoreSnapshot
– queue can schedule and run a test job
– suppression record prevents lookup from returning send-eligible
– audit log stores before/after payloads

End of phase.

PHASE 2 — SOURCE INGESTION AND POLICY CONTROL

Goal:
Allow approved leads into the system safely.

Tasks:
– Build source ingestion interface
– Build CSV/import path for approved source exports
– Build mcrcore.com inbound lead intake
– Build Tallman referral intake
– Build Source Compliance Agent
– Build deduplication pipeline
– Add provenance capture
– Add source risk scoring

Milestone:
Approved leads can enter the system

Acceptance tests:
– approved source record imports successfully
– denied source record is blocked
– pending-review source is flagged and not sent downstream automatically
– duplicate company/contact pairs collapse correctly
– inbound website lead is stored with source type = inbound
– referral lead gets boosted source priority flag

End of phase.

PHASE 3 — ENRICHMENT AND SIGNAL DETECTION

Goal:
Turn raw leads into useful sales intelligence.

Tasks:
– Build Lead Enrichment Agent
– Build company summary generation
– Build contact summary generation
– Build ERP and Industry Signal Agent
– Build evidence storage
– Add confidence scoring
– Add pain-point inference rules
– Add compliance/remote-work/network complexity indicators

Milestone:
Each lead can be enriched and summarized

Acceptance tests:
– enrichment job populates summary fields
– evidence map is stored for each enriched lead
– signal detector flags manufacturing or logistics when supported by input
– ERP detector can assign non-zero signal when Epicor, POR, McLeod, or DAT evidence is present
– low-confidence leads are explicitly marked as low confidence

End of phase.

PHASE 4 — OFFER MATCHING AND SCORING

Goal:
Rank leads intelligently and recommend the best opening motion.

Tasks:
– Build Offer Matching Agent
– Encode audit-first CTA logic
– Encode geo/service routing rules
– Build Scoring Agent
– Implement weighted scoring model
– Implement override rules
– Implement probability banding
– Implement daily ranking query
– Implement top-5 unprocessed lead selector

Milestone:
System can rank and prioritize leads

Acceptance tests:
– Midwest manufacturing lead with ERP evidence gets stronger managed-service package fit than a generic low-fit company
– remote North America infrastructure lead can be matched to virtual servers or network monitoring
– inbound quote lead is promoted to high priority
– opted-out lead cannot appear in top-5 send queue
– daily selector returns 5 or fewer eligible unprocessed leads, sorted by score and tie-break rules

End of phase.

PHASE 5 — OUTREACH GENERATION

Goal:
Generate high-quality personalized outreach.

Tasks:
– Build Outreach Personalization Agent
– Build audit-first-outreach skill
– Build package-specific-email skill
– Build message block libraries by title
– Build message block libraries by industry
– Build differentiator insertion logic
– Add semantic uniqueness checks
– Add template QA tests

Milestone:
System can draft personalized outbound emails

Acceptance tests:
– CEO-targeted email emphasizes business risk and growth
– operations-targeted email emphasizes uptime and process reliability
– CFO-targeted email emphasizes cost predictability and compliance risk
– IT manager-targeted email emphasizes depth, coverage, and escalation relief
– first-touch and 7-day follow-up drafts for same lead are materially different
– generated email includes recommended CTA and required footer fields

End of phase.

PHASE 6 — COMPLIANCE AND DELIVERABILITY GATE

Goal:
Block unsafe sending before launch.

Tasks:
– Build Deliverability and Compliance Agent
– Build compliance-check skill
– Implement suppression checks
– Implement footer validation
– Implement subject-line validation
– Implement sender-auth status integration
– Implement bounce-risk thresholds
– Implement complaint-risk kill switch

Milestone:
Pre-send governance active

Acceptance tests:
– opted-out lead fails pre-send check
– missing postal address fails pre-send check
– missing unsubscribe mechanism fails pre-send check
– invalid sender auth status blocks send
– deceptive or blank subject fails validation
– passing message receives explicit approved state

End of phase.

PHASE 7 — INBOX PROCESSING, REPLY CLASSIFICATION, AND ESCALATION

Goal:
Close the loop on inbound responses.

Tasks:
– Build mailbox listener
– Build thread parser
– Build Reply Classification Agent
– Build reply-intent skill
– Build Opportunity Escalation Agent
– Build escalation-packet skill
– Add opt-out detection
– Add bounce and auto-reply detection
– Add lead-state update logic

Milestone:
Replies can change pipeline state automatically

Acceptance tests:
– positive buying-intent reply is classified as likely opportunity
– opt-out reply writes suppression record
– out-of-office reply does not create opportunity
– bounce reply marks address invalid
– escalation packet includes summary, score, package recommendation, and thread context

End of phase.

PHASE 8 — NURTURE AUTOMATION

Goal:
Run timed follow-up safely and distinctly.

Tasks:
– Build Nurture Cadence Agent
– Build nurture-cadence skill
– Add 7-day timer logic
– Add 30-day timer logic
– Add 90-day timer logic
– Add reply-reset logic
– Add no-repeat and no-send-after-opt-out logic

Milestone:
Nurture engine active

Acceptance tests:
– interested/no-order lead gets a 7-day follow-up scheduled
– 30-day follow-up is not identical to prior messages
– 90-day follow-up is not identical to prior messages
– new reply cancels or re-routes scheduled nurture action
– opted-out lead never receives scheduled nurture

End of phase.

PHASE 9 — DAILY ORCHESTRATION AND KPI REPORTING

Goal:
Automate daily production and visibility.

Tasks:
– Build Daily Orchestrator Agent
– Build analytics-reporting skill
– Build daily runbook execution
– Build KPI aggregation jobs
– Build exception summary
– Build daily email or dashboard digest
– Add backlog and retry monitoring

Milestone:
System runs daily end-to-end

Acceptance tests:
– daily run can import, enrich, score, rank, and process replies in sequence
– daily summary includes leads added, messages sent, replies, opt-outs, escalations, and top-5 queue
– failure in one job does not silently skip audit logging
– dead-letter or failed jobs appear in monitoring view

End of phase.

PHASE 10 — STAGING VALIDATION AND PILOT LAUNCH

Goal:
Prove the system before full rollout.

Tasks:
– Run staging data tests
– Run synthetic lead tests
– Run reply-classification test corpus
– Run compliance test suite
– Validate top-5 ranking quality with human review
– Launch low-volume pilot
– Collect operator feedback
– tune rules and prompts

Milestone:
Pilot approved for controlled production use

Acceptance tests:
– test corpus passes scoring and classification thresholds
– human reviewers approve majority of top-5 selections as reasonable
– all pilot sends pass compliance gate
– no opted-out address is contacted in pilot
– escalation packets are judged usable by sales team

End of phase.

PHASE 11 — PRODUCTION HARDENING

Goal:
Make the system reliable and supportable.

Tasks:
– add retry tuning
– add queue dead-letter handling
– add incident alerts
– add backup verification
– add admin override UI or workflow
– add source-approval admin tooling
– add model and prompt versioning
– add change log for scoring rules

Milestone:
Production-ready system

Acceptance tests:
– failed job retries respect retry policy
– dead-letter queue captures unrecoverable jobs
– backup restore test succeeds
– admin can override source status and lead state with audit entry
– scoring rule changes are versioned and traceable

End of phase.

RELEASE READINESS CHECKLIST

Required before production outreach:
– approved-source list signed off by owner
– sender domain authentication verified
– suppression workflow tested
– postal address/footer verified
– escalation inbox verified
– hourly break/fix pricing decision documented or excluded from auto-priority logic
– core case studies and proof blocks approved
– KPI thresholds approved

End of section.

MINIMUM VIABLE RELEASE

Recommended MVP scope:
– phases 0 through 7
– manual review before actual send
– low-volume pilot only
– audit-first messaging only
– limited source set: inbound, referrals, one approved outbound source

Reason:
This gets the core loop working without overextending risk.

End of section.

RECOMMENDED TEAM SPLIT
– Platform engineer: data layer, queue, integrations
– AI engineer: agents, prompts, scoring, classification
– Growth ops lead: ICP tuning, package logic, source governance
– Sales stakeholder: escalation quality review
– compliance owner: final send policy signoff

End of section.

Clear recommendation

Build in this order:
– foundation
– ingestion and enrichment
– scoring and offer matching
– compliance gate
– reply loop
– nurture
– reporting
– pilot
