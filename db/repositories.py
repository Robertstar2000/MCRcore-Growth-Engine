"""
MCRcore Growth Engine - Repository Layer

Thin repository classes wrapping SQLAlchemy CRUD for every entity.
Each repository accepts a Session and provides:
  create, get_by_id, update, list_all, delete  (generic)
  + entity-specific query methods
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from db.models import (
    AuditEvent,
    Base,
    Company,
    Contact,
    EnrichmentProfile,
    Lead,
    NurtureSchedule,
    Opportunity,
    OutreachEvent,
    ReplyEvent,
    ScoreSnapshot,
    SignalProfile,
    Source,
    SuppressionRecord,
    WorkflowJob,
)

T = TypeVar("T", bound=Base)


# ===================================================================
# Generic base repository
# ===================================================================
class _BaseRepository:
    """Common CRUD shared by all entity repositories."""

    model: Type[T] = None  # set in subclasses
    pk_field: str = None  # primary key column name

    def __init__(self, session: Session):
        self.session = session

    # -- Generic CRUD ------------------------------------------------

    def create(self, **kwargs) -> T:
        obj = self.model(**kwargs)
        self.session.add(obj)
        self.session.flush()
        return obj

    def get_by_id(self, entity_id: str) -> Optional[T]:
        return self.session.query(self.model).get(entity_id)

    def update(self, entity_id: str, **kwargs) -> Optional[T]:
        obj = self.get_by_id(entity_id)
        if obj is None:
            return None
        for k, v in kwargs.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        self.session.flush()
        return obj

    def delete(self, entity_id: str) -> bool:
        obj = self.get_by_id(entity_id)
        if obj is None:
            return False
        self.session.delete(obj)
        self.session.flush()
        return True

    def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        return (
            self.session.query(self.model)
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count(self) -> int:
        return self.session.query(func.count()).select_from(self.model).scalar()


# ===================================================================
# Lead
# ===================================================================
class LeadRepository(_BaseRepository):
    model = Lead
    pk_field = "lead_id"

    def get_top_unprocessed(self, limit: int = 50) -> List[Lead]:
        """Leads with status='new' that have not been processed, oldest first."""
        return (
            self.session.query(Lead)
            .filter(Lead.status == "new", Lead.last_processed_at.is_(None))
            .order_by(Lead.created_at.asc())
            .limit(limit)
            .all()
        )

    def get_by_status(self, status: str, limit: int = 100) -> List[Lead]:
        return (
            self.session.query(Lead)
            .filter(Lead.status == status)
            .limit(limit)
            .all()
        )

    def get_actionable(self, before: Optional[datetime] = None, limit: int = 50) -> List[Lead]:
        """Leads whose next_action_at is in the past (or before a given time)."""
        cutoff = before or datetime.now(timezone.utc)
        return (
            self.session.query(Lead)
            .filter(
                Lead.next_action_at.isnot(None),
                Lead.next_action_at <= cutoff,
                Lead.opt_out_flag == False,  # noqa: E712
            )
            .order_by(Lead.next_action_at.asc())
            .limit(limit)
            .all()
        )

    def find_by_duplicate_hash(self, dup_hash: str) -> Optional[Lead]:
        return (
            self.session.query(Lead)
            .filter(Lead.duplicate_hash == dup_hash)
            .first()
        )

    def get_by_owner(self, owner_agent: str, limit: int = 100) -> List[Lead]:
        return (
            self.session.query(Lead)
            .filter(Lead.owner_agent == owner_agent)
            .limit(limit)
            .all()
        )


# ===================================================================
# Company
# ===================================================================
class CompanyRepository(_BaseRepository):
    model = Company
    pk_field = "company_id"

    def find_by_domain(self, domain: str) -> Optional[Company]:
        return (
            self.session.query(Company)
            .filter(Company.domain == domain)
            .first()
        )

    def search_by_name(self, name_fragment: str, limit: int = 20) -> List[Company]:
        return (
            self.session.query(Company)
            .filter(Company.company_name.ilike(f"%{name_fragment}%"))
            .limit(limit)
            .all()
        )

    def get_by_industry(self, industry: str, limit: int = 100) -> List[Company]:
        return (
            self.session.query(Company)
            .filter(Company.industry == industry)
            .limit(limit)
            .all()
        )


# ===================================================================
# Contact
# ===================================================================
class ContactRepository(_BaseRepository):
    model = Contact
    pk_field = "contact_id"

    def find_by_email(self, email: str) -> Optional[Contact]:
        return (
            self.session.query(Contact)
            .filter(Contact.email == email)
            .first()
        )

    def get_by_company(self, company_id: str) -> List[Contact]:
        return (
            self.session.query(Contact)
            .filter(Contact.company_id == company_id)
            .order_by(Contact.role_priority.asc())
            .all()
        )

    def get_contactable(self, company_id: str) -> List[Contact]:
        """Non-DNC contacts for a company, highest priority first."""
        return (
            self.session.query(Contact)
            .filter(
                Contact.company_id == company_id,
                Contact.do_not_contact == False,  # noqa: E712
            )
            .order_by(Contact.role_priority.asc())
            .all()
        )


# ===================================================================
# Source
# ===================================================================
class SourceRepository(_BaseRepository):
    model = Source
    pk_field = "source_id"

    def find_by_name(self, name: str) -> Optional[Source]:
        return (
            self.session.query(Source)
            .filter(Source.source_name == name)
            .first()
        )

    def get_approved(self) -> List[Source]:
        return (
            self.session.query(Source)
            .filter(Source.approved_flag == True)  # noqa: E712
            .all()
        )

    def get_by_risk(self, risk_level: str) -> List[Source]:
        return (
            self.session.query(Source)
            .filter(Source.risk_level == risk_level)
            .all()
        )


# ===================================================================
# EnrichmentProfile
# ===================================================================
class EnrichmentRepository(_BaseRepository):
    model = EnrichmentProfile
    pk_field = "enrichment_id"

    def get_by_lead(self, lead_id: str) -> Optional[EnrichmentProfile]:
        return (
            self.session.query(EnrichmentProfile)
            .filter(EnrichmentProfile.lead_id == lead_id)
            .order_by(EnrichmentProfile.updated_at.desc())
            .first()
        )

    def get_low_confidence(self, threshold: float = 0.5, limit: int = 50) -> List[EnrichmentProfile]:
        return (
            self.session.query(EnrichmentProfile)
            .filter(EnrichmentProfile.research_confidence < threshold)
            .order_by(EnrichmentProfile.research_confidence.asc())
            .limit(limit)
            .all()
        )


# ===================================================================
# SignalProfile
# ===================================================================
class SignalRepository(_BaseRepository):
    model = SignalProfile
    pk_field = "signal_id"

    def get_by_lead(self, lead_id: str) -> Optional[SignalProfile]:
        return (
            self.session.query(SignalProfile)
            .filter(SignalProfile.lead_id == lead_id)
            .first()
        )

    def get_with_epicor_signal(self, threshold: float = 0.5, limit: int = 50) -> List[SignalProfile]:
        return (
            self.session.query(SignalProfile)
            .filter(SignalProfile.epicor_signal >= threshold)
            .limit(limit)
            .all()
        )

    def get_with_manufacturing_signal(self, threshold: float = 0.5, limit: int = 50) -> List[SignalProfile]:
        return (
            self.session.query(SignalProfile)
            .filter(SignalProfile.manufacturing_signal >= threshold)
            .limit(limit)
            .all()
        )


# ===================================================================
# ScoreSnapshot
# ===================================================================
class ScoreRepository(_BaseRepository):
    model = ScoreSnapshot
    pk_field = "score_id"

    def get_latest_for_lead(self, lead_id: str) -> Optional[ScoreSnapshot]:
        return (
            self.session.query(ScoreSnapshot)
            .filter(ScoreSnapshot.lead_id == lead_id)
            .order_by(ScoreSnapshot.scored_at.desc())
            .first()
        )

    def get_by_tier(self, tier: str, limit: int = 100) -> List[ScoreSnapshot]:
        return (
            self.session.query(ScoreSnapshot)
            .filter(ScoreSnapshot.priority_tier == tier)
            .order_by(ScoreSnapshot.sales_probability.desc())
            .limit(limit)
            .all()
        )

    def get_top_prospects(self, limit: int = 25) -> List[ScoreSnapshot]:
        """Highest sales_probability across all tiers."""
        return (
            self.session.query(ScoreSnapshot)
            .order_by(ScoreSnapshot.sales_probability.desc())
            .limit(limit)
            .all()
        )

    def get_history_for_lead(self, lead_id: str) -> List[ScoreSnapshot]:
        return (
            self.session.query(ScoreSnapshot)
            .filter(ScoreSnapshot.lead_id == lead_id)
            .order_by(ScoreSnapshot.scored_at.asc())
            .all()
        )


# ===================================================================
# OutreachEvent
# ===================================================================
class OutreachRepository(_BaseRepository):
    model = OutreachEvent
    pk_field = "outreach_id"

    def get_by_lead(self, lead_id: str) -> List[OutreachEvent]:
        return (
            self.session.query(OutreachEvent)
            .filter(OutreachEvent.lead_id == lead_id)
            .order_by(OutreachEvent.sent_at.desc())
            .all()
        )

    def get_pending_delivery(self, limit: int = 100) -> List[OutreachEvent]:
        return (
            self.session.query(OutreachEvent)
            .filter(OutreachEvent.delivery_status == "pending")
            .limit(limit)
            .all()
        )

    def count_sent_for_lead(self, lead_id: str) -> int:
        return (
            self.session.query(func.count())
            .select_from(OutreachEvent)
            .filter(
                OutreachEvent.lead_id == lead_id,
                OutreachEvent.delivery_status == "delivered",
            )
            .scalar()
        )

    def get_by_stage(self, stage: str, limit: int = 100) -> List[OutreachEvent]:
        return (
            self.session.query(OutreachEvent)
            .filter(OutreachEvent.stage == stage)
            .limit(limit)
            .all()
        )


# ===================================================================
# ReplyEvent
# ===================================================================
class ReplyRepository(_BaseRepository):
    model = ReplyEvent
    pk_field = "reply_id"

    def get_by_lead(self, lead_id: str) -> List[ReplyEvent]:
        return (
            self.session.query(ReplyEvent)
            .filter(ReplyEvent.lead_id == lead_id)
            .order_by(ReplyEvent.received_at.desc())
            .all()
        )

    def get_unclassified(self, limit: int = 50) -> List[ReplyEvent]:
        return (
            self.session.query(ReplyEvent)
            .filter(ReplyEvent.classified_as.is_(None))
            .order_by(ReplyEvent.received_at.asc())
            .limit(limit)
            .all()
        )

    def get_escalations(self, limit: int = 50) -> List[ReplyEvent]:
        return (
            self.session.query(ReplyEvent)
            .filter(ReplyEvent.escalation_flag == True)  # noqa: E712
            .order_by(ReplyEvent.received_at.desc())
            .limit(limit)
            .all()
        )

    def get_opt_outs(self, limit: int = 100) -> List[ReplyEvent]:
        return (
            self.session.query(ReplyEvent)
            .filter(ReplyEvent.opt_out_flag == True)  # noqa: E712
            .limit(limit)
            .all()
        )


# ===================================================================
# Opportunity
# ===================================================================
class OpportunityRepository(_BaseRepository):
    model = Opportunity
    pk_field = "opportunity_id"

    def get_by_lead(self, lead_id: str) -> List[Opportunity]:
        return (
            self.session.query(Opportunity)
            .filter(Opportunity.lead_id == lead_id)
            .all()
        )

    def get_open(self, limit: int = 100) -> List[Opportunity]:
        return (
            self.session.query(Opportunity)
            .filter(Opportunity.status == "open")
            .limit(limit)
            .all()
        )

    def get_escalated(self, limit: int = 50) -> List[Opportunity]:
        return (
            self.session.query(Opportunity)
            .filter(Opportunity.escalated_at.isnot(None))
            .order_by(Opportunity.escalated_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_package(self, package: str, limit: int = 50) -> List[Opportunity]:
        return (
            self.session.query(Opportunity)
            .filter(Opportunity.recommended_package == package)
            .limit(limit)
            .all()
        )


# ===================================================================
# SuppressionRecord
# ===================================================================
class SuppressionRepository(_BaseRepository):
    model = SuppressionRecord
    pk_field = "suppression_id"

    def is_suppressed(self, email: str) -> bool:
        """Return True if the email is on the suppression list."""
        return (
            self.session.query(SuppressionRecord)
            .filter(SuppressionRecord.email == email.lower())
            .first()
        ) is not None

    def find_by_email(self, email: str) -> List[SuppressionRecord]:
        return (
            self.session.query(SuppressionRecord)
            .filter(SuppressionRecord.email == email.lower())
            .all()
        )

    def suppress(self, email: str, reason: str, source: str) -> SuppressionRecord:
        """Add an email to the suppression list (idempotent-ish)."""
        return self.create(email=email.lower(), reason=reason, source=source)


# ===================================================================
# AuditEvent
# ===================================================================
class AuditRepository(_BaseRepository):
    model = AuditEvent
    pk_field = "audit_id"

    def log(self, actor: str, entity_type: str, entity_id: str,
            action: str, before_json: str = None, after_json: str = None) -> AuditEvent:
        return self.create(
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=before_json,
            after_json=after_json,
        )

    def get_for_entity(self, entity_type: str, entity_id: str) -> List[AuditEvent]:
        return (
            self.session.query(AuditEvent)
            .filter(
                AuditEvent.entity_type == entity_type,
                AuditEvent.entity_id == entity_id,
            )
            .order_by(AuditEvent.timestamp.desc())
            .all()
        )

    def get_by_actor(self, actor: str, limit: int = 100) -> List[AuditEvent]:
        return (
            self.session.query(AuditEvent)
            .filter(AuditEvent.actor == actor)
            .order_by(AuditEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_recent(self, limit: int = 50) -> List[AuditEvent]:
        return (
            self.session.query(AuditEvent)
            .order_by(AuditEvent.timestamp.desc())
            .limit(limit)
            .all()
        )


# ===================================================================
# WorkflowJob
# ===================================================================
class WorkflowJobRepository(_BaseRepository):
    model = WorkflowJob
    pk_field = "job_id"

    def get_pending(self, limit: int = 50) -> List[WorkflowJob]:
        return (
            self.session.query(WorkflowJob)
            .filter(WorkflowJob.status == "pending")
            .order_by(WorkflowJob.scheduled_at.asc())
            .limit(limit)
            .all()
        )

    def get_running(self) -> List[WorkflowJob]:
        return (
            self.session.query(WorkflowJob)
            .filter(WorkflowJob.status == "running")
            .all()
        )

    def get_failed(self, limit: int = 50) -> List[WorkflowJob]:
        return (
            self.session.query(WorkflowJob)
            .filter(WorkflowJob.status == "failed")
            .order_by(WorkflowJob.completed_at.desc())
            .limit(limit)
            .all()
        )

    def mark_running(self, job_id: str) -> Optional[WorkflowJob]:
        return self.update(job_id, status="running", started_at=datetime.now(timezone.utc))

    def mark_completed(self, job_id: str, result_json: str = None) -> Optional[WorkflowJob]:
        return self.update(
            job_id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            result_json=result_json,
        )

    def mark_failed(self, job_id: str, error_message: str) -> Optional[WorkflowJob]:
        return self.update(
            job_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error_message=error_message,
        )


# ===================================================================
# NurtureSchedule
# ===================================================================
class NurtureRepository(_BaseRepository):
    model = NurtureSchedule
    pk_field = "nurture_id"

    def get_due(self, before: Optional[datetime] = None, limit: int = 50) -> List[NurtureSchedule]:
        """Unsent, non-cancelled nurture items due before a cutoff."""
        cutoff = before or datetime.now(timezone.utc)
        return (
            self.session.query(NurtureSchedule)
            .filter(
                NurtureSchedule.sent == False,  # noqa: E712
                NurtureSchedule.cancelled == False,  # noqa: E712
                NurtureSchedule.scheduled_at <= cutoff,
            )
            .order_by(NurtureSchedule.scheduled_at.asc())
            .limit(limit)
            .all()
        )

    def get_by_lead(self, lead_id: str) -> List[NurtureSchedule]:
        return (
            self.session.query(NurtureSchedule)
            .filter(NurtureSchedule.lead_id == lead_id)
            .order_by(NurtureSchedule.scheduled_at.asc())
            .all()
        )

    def cancel_for_lead(self, lead_id: str) -> int:
        """Cancel all pending nurture items for a lead. Returns count."""
        count = (
            self.session.query(NurtureSchedule)
            .filter(
                NurtureSchedule.lead_id == lead_id,
                NurtureSchedule.sent == False,  # noqa: E712
                NurtureSchedule.cancelled == False,  # noqa: E712
            )
            .update({"cancelled": True})
        )
        self.session.flush()
        return count

    def mark_sent(self, nurture_id: str, message_id: str = None) -> Optional[NurtureSchedule]:
        return self.update(nurture_id, sent=True, message_id=message_id)
