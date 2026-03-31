"""
MCRcore Growth Engine - SQLAlchemy ORM Models

All entities for the lead-to-opportunity pipeline:
Lead, Company, Contact, Source, EnrichmentProfile, SignalProfile,
ScoreSnapshot, OutreachEvent, ReplyEvent, Opportunity,
SuppressionRecord, AuditEvent, WorkflowJob, NurtureSchedule.

Uses UUIDs for all primary keys. SQLite-compatible via String(36) columns.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    """Generate a new UUID4 string for default primary-key values."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------
class Company(Base):
    __tablename__ = "companies"

    company_id = Column(String(36), primary_key=True, default=_uuid)
    company_name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), unique=True, index=True)
    industry = Column(String(128))
    employee_band = Column(String(32))  # e.g. "50-200", "200-500"
    geography = Column(String(128))
    summary = Column(Text)
    website_url = Column(String(512))

    # Relationships
    leads = relationship("Lead", back_populates="company", lazy="dynamic")
    contacts = relationship("Contact", back_populates="company", lazy="dynamic")

    __table_args__ = (
        Index("ix_companies_industry_geo", "industry", "geography"),
    )

    def __repr__(self):
        return f"<Company {self.company_name} ({self.domain})>"


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------
class Contact(Base):
    __tablename__ = "contacts"

    contact_id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.company_id"), index=True)
    full_name = Column(String(255), nullable=False)
    title = Column(String(255))
    email = Column(String(255), index=True)
    profile_url = Column(String(512))  # LinkedIn / other
    role_priority = Column(Integer, default=0)  # 0=unknown, 1=primary, 2=secondary …
    do_not_contact = Column(Boolean, default=False)

    # Relationships
    company = relationship("Company", back_populates="contacts")
    leads = relationship("Lead", back_populates="contact", lazy="dynamic")

    __table_args__ = (
        Index("ix_contacts_email_dnc", "email", "do_not_contact"),
    )

    def __repr__(self):
        return f"<Contact {self.full_name} ({self.email})>"


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------
class Source(Base):
    __tablename__ = "sources"

    source_id = Column(String(36), primary_key=True, default=_uuid)
    source_name = Column(String(128), nullable=False, unique=True)
    source_type = Column(String(64))  # 'scraper', 'referral', 'purchased', 'event' …
    approved_flag = Column(Boolean, default=False)
    risk_level = Column(String(16), default="medium")  # low / medium / high
    provenance_ref = Column(String(512))

    leads = relationship("Lead", back_populates="source", lazy="dynamic")

    def __repr__(self):
        return f"<Source {self.source_name} approved={self.approved_flag}>"


# ---------------------------------------------------------------------------
# Lead  (central entity)
# ---------------------------------------------------------------------------
class Lead(Base):
    __tablename__ = "leads"

    lead_id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(String(36), ForeignKey("companies.company_id"), index=True)
    contact_id = Column(String(36), ForeignKey("contacts.contact_id"), index=True)
    source_id = Column(String(36), ForeignKey("sources.source_id"), index=True)

    status = Column(String(32), nullable=False, default="new", index=True)
    substatus = Column(String(64))
    recommended_offer = Column(String(128))
    recommended_entry_cta = Column(String(255))
    owner_agent = Column(String(64), index=True)
    duplicate_hash = Column(String(64), index=True)
    opt_out_flag = Column(Boolean, default=False)
    do_not_contact_reason = Column(String(255))

    last_processed_at = Column(DateTime)
    next_action_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    company = relationship("Company", back_populates="leads")
    contact = relationship("Contact", back_populates="leads")
    source = relationship("Source", back_populates="leads")
    enrichment_profiles = relationship("EnrichmentProfile", back_populates="lead", lazy="dynamic")
    signal_profiles = relationship("SignalProfile", back_populates="lead", lazy="dynamic")
    score_snapshots = relationship("ScoreSnapshot", back_populates="lead", lazy="dynamic")
    outreach_events = relationship("OutreachEvent", back_populates="lead", lazy="dynamic")
    reply_events = relationship("ReplyEvent", back_populates="lead", lazy="dynamic")
    opportunities = relationship("Opportunity", back_populates="lead", lazy="dynamic")
    nurture_schedules = relationship("NurtureSchedule", back_populates="lead", lazy="dynamic")

    __table_args__ = (
        Index("ix_leads_status_next_action", "status", "next_action_at"),
        Index("ix_leads_owner_status", "owner_agent", "status"),
    )

    def __repr__(self):
        return f"<Lead {self.lead_id[:8]}… status={self.status}>"


# ---------------------------------------------------------------------------
# EnrichmentProfile
# ---------------------------------------------------------------------------
class EnrichmentProfile(Base):
    __tablename__ = "enrichment_profiles"

    enrichment_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)

    operational_pain_summary = Column(Text)
    it_pain_points = Column(Text)
    erp_signals = Column(Text)
    compliance_signals = Column(Text)
    remote_work_signals = Column(Text)
    infrastructure_signals = Column(Text)
    evidence_json = Column(Text)  # JSON blob
    research_confidence = Column(Float, default=0.0)
    company_summary = Column(Text)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    lead = relationship("Lead", back_populates="enrichment_profiles")

    def __repr__(self):
        return f"<EnrichmentProfile lead={self.lead_id[:8]}… conf={self.research_confidence}>"


# ---------------------------------------------------------------------------
# SignalProfile
# ---------------------------------------------------------------------------
class SignalProfile(Base):
    __tablename__ = "signal_profiles"

    signal_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)

    epicor_signal = Column(Float, default=0.0)
    por_signal = Column(Float, default=0.0)
    mcleod_signal = Column(Float, default=0.0)
    dat_keypoint_signal = Column(Float, default=0.0)
    manufacturing_signal = Column(Float, default=0.0)
    logistics_signal = Column(Float, default=0.0)
    insurance_signal = Column(Float, default=0.0)
    scaling_signal = Column(Float, default=0.0)

    lead = relationship("Lead", back_populates="signal_profiles")

    def __repr__(self):
        return f"<SignalProfile lead={self.lead_id[:8]}…>"


# ---------------------------------------------------------------------------
# ScoreSnapshot
# ---------------------------------------------------------------------------
class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    score_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)

    fit_score = Column(Float, default=0.0)
    need_score = Column(Float, default=0.0)
    engagement_score = Column(Float, default=0.0)
    package_fit_score = Column(Float, default=0.0)
    margin_band = Column(String(32))
    sales_probability = Column(Float, default=0.0)
    priority_tier = Column(String(16), index=True)  # A / B / C / D
    recommended_action = Column(String(128))
    scored_at = Column(DateTime, default=_utcnow, index=True)

    lead = relationship("Lead", back_populates="score_snapshots")

    __table_args__ = (
        Index("ix_scores_tier_prob", "priority_tier", "sales_probability"),
    )

    def __repr__(self):
        return f"<ScoreSnapshot lead={self.lead_id[:8]}… tier={self.priority_tier}>"


# ---------------------------------------------------------------------------
# OutreachEvent
# ---------------------------------------------------------------------------
class OutreachEvent(Base):
    __tablename__ = "outreach_events"

    outreach_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)

    stage = Column(String(32))  # e.g. cold_1, cold_2, nurture_1
    package_angle = Column(String(128))
    subject = Column(String(512))
    body_hash = Column(String(64))
    sent_at = Column(DateTime, index=True)
    delivery_status = Column(String(32), default="pending")
    click_status = Column(Boolean, default=False)
    open_status = Column(Boolean, default=False)
    reply_status = Column(Boolean, default=False)
    compliance_passed = Column(Boolean, default=True)

    lead = relationship("Lead", back_populates="outreach_events")

    __table_args__ = (
        Index("ix_outreach_lead_stage", "lead_id", "stage"),
    )

    def __repr__(self):
        return f"<OutreachEvent lead={self.lead_id[:8]}… stage={self.stage}>"


# ---------------------------------------------------------------------------
# ReplyEvent
# ---------------------------------------------------------------------------
class ReplyEvent(Base):
    __tablename__ = "reply_events"

    reply_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)
    thread_id = Column(String(128), index=True)

    received_at = Column(DateTime, default=_utcnow, index=True)
    raw_text = Column(Text)
    classified_as = Column(String(32))  # positive / negative / question / objection / opt_out
    intent_confidence = Column(Float, default=0.0)
    objection_tags = Column(Text)  # JSON array
    escalation_flag = Column(Boolean, default=False)
    opt_out_flag = Column(Boolean, default=False)

    lead = relationship("Lead", back_populates="reply_events")

    def __repr__(self):
        return f"<ReplyEvent lead={self.lead_id[:8]}… cls={self.classified_as}>"


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------
class Opportunity(Base):
    __tablename__ = "opportunities"

    opportunity_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)

    recommended_package = Column(String(128))
    estimated_value_band = Column(String(64))
    estimated_margin_band = Column(String(64))
    summary = Column(Text)
    communication_bundle_ref = Column(String(255))
    escalated_to = Column(String(128))
    escalated_at = Column(DateTime)
    final_outcome = Column(String(64))  # won / lost / stalled
    status = Column(String(32), default="open", index=True)

    lead = relationship("Lead", back_populates="opportunities")

    def __repr__(self):
        return f"<Opportunity {self.opportunity_id[:8]}… status={self.status}>"


# ---------------------------------------------------------------------------
# SuppressionRecord
# ---------------------------------------------------------------------------
class SuppressionRecord(Base):
    __tablename__ = "suppression_records"

    suppression_id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), nullable=False, index=True)
    reason = Column(String(128))
    source = Column(String(128))
    effective_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_suppression_email_effective", "email", "effective_at"),
    )

    def __repr__(self):
        return f"<SuppressionRecord {self.email}>"


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    audit_id = Column(String(36), primary_key=True, default=_uuid)
    actor = Column(String(128), nullable=False)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    action = Column(String(32), nullable=False)  # create / update / delete / status_change
    before_json = Column(Text)
    after_json = Column(Text)
    timestamp = Column(DateTime, default=_utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
    )

    def __repr__(self):
        return f"<AuditEvent {self.action} on {self.entity_type}/{self.entity_id[:8]}…>"


# ---------------------------------------------------------------------------
# WorkflowJob
# ---------------------------------------------------------------------------
class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"

    job_id = Column(String(36), primary_key=True, default=_uuid)
    job_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="pending", index=True)  # pending / running / completed / failed
    scheduled_at = Column(DateTime, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    result_json = Column(Text)

    __table_args__ = (
        Index("ix_jobs_status_scheduled", "status", "scheduled_at"),
    )

    def __repr__(self):
        return f"<WorkflowJob {self.job_type} status={self.status}>"


# ---------------------------------------------------------------------------
# NurtureSchedule
# ---------------------------------------------------------------------------
class NurtureSchedule(Base):
    __tablename__ = "nurture_schedules"

    nurture_id = Column(String(36), primary_key=True, default=_uuid)
    lead_id = Column(String(36), ForeignKey("leads.lead_id"), nullable=False, index=True)
    stage = Column(String(32))
    scheduled_at = Column(DateTime, index=True)
    sent = Column(Boolean, default=False)
    cancelled = Column(Boolean, default=False)
    message_id = Column(String(128))

    lead = relationship("Lead", back_populates="nurture_schedules")

    __table_args__ = (
        Index("ix_nurture_pending", "sent", "cancelled", "scheduled_at"),
    )

    def __repr__(self):
        return f"<NurtureSchedule lead={self.lead_id[:8]}… stage={self.stage}>"
