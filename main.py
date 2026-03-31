#!/usr/bin/env python3
"""
MCRcore Growth Engine - CLI Entry Point

Commands:
    python main.py run-daily        Full daily pipeline orchestration
    python main.py discover         Lead discovery only
    python main.py enrich           Lead enrichment only
    python main.py score            Scoring + offer matching + daily ranking
    python main.py outreach         Outreach personalization + compliance
    python main.py process-replies  Mailbox processing + reply classification
    python main.py nurture          Nurture cadence processing
    python main.py import-csv FILE  Import leads from a CSV file
    python main.py init-db          Run migrations and seed data
    python main.py kpi              Calculate and print daily KPIs
    python main.py schedule         Start the daily scheduler daemon
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from src.utils.logger import setup_logger

logger = setup_logger("mcr_growth_engine.cli")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _init_db():
    """Initialize the database (create tables)."""
    from db.database import init_db
    init_db()
    logger.info("Database tables created / verified.")


def _get_session():
    """Return a database session context manager."""
    from db.database import get_session
    return get_session()


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_init_db(args):
    """Run database migration and seed data."""
    logger.info("Initializing database ...")
    _init_db()

    logger.info("Running seed data ...")
    from db.seeds.seed_data import run_seed
    run_seed()
    logger.info("Database initialization complete.")


def cmd_discover(args):
    """Run the Lead Discovery Agent."""
    _init_db()
    from src.agents.lead_discovery_agent import LeadDiscoveryAgent

    logger.info("Starting lead discovery ...")
    with _get_session() as session:
        agent = LeadDiscoveryAgent(session)
        result = agent.run()
        logger.info(f"Discovery result: {json.dumps(result, indent=2, default=str)}")
    print("Lead discovery complete.")


def cmd_enrich(args):
    """Run the Lead Enrichment Agent on all un-enriched leads."""
    _init_db()
    from src.agents.lead_enrichment_agent import LeadEnrichmentAgent
    from db.repositories import LeadRepository

    logger.info("Starting lead enrichment ...")
    with _get_session() as session:
        agent = LeadEnrichmentAgent(session)
        lead_repo = LeadRepository(session)

        # Find leads that need enrichment (status = 'new')
        leads = lead_repo.find_by_status("new")
        if not leads:
            logger.info("No leads pending enrichment.")
            print("No leads to enrich.")
            return

        enriched = 0
        errors = 0
        for lead in leads:
            try:
                result = agent.run(lead_id=lead.lead_id)
                if result.get("error"):
                    logger.warning(f"Enrichment error for {lead.lead_id}: {result['error']}")
                    errors += 1
                else:
                    enriched += 1
            except Exception as exc:
                logger.error(f"Failed to enrich lead {lead.lead_id}: {exc}")
                errors += 1

        logger.info(f"Enrichment complete: {enriched} enriched, {errors} errors.")
        print(f"Enrichment complete: {enriched} enriched, {errors} errors.")


def cmd_score(args):
    """Run Scoring, Offer Matching, and Daily Ranking agents."""
    _init_db()
    from src.agents.scoring_agent import ScoringAgent
    from src.agents.offer_matching_agent import OfferMatchingAgent
    from src.agents.daily_ranking_agent import DailyRankingAgent
    from db.repositories import LeadRepository

    logger.info("Starting scoring pipeline ...")
    with _get_session() as session:
        lead_repo = LeadRepository(session)
        scoring_agent = ScoringAgent()
        offer_agent = OfferMatchingAgent()
        ranking_agent = DailyRankingAgent()

        # Score all enriched leads
        leads = lead_repo.find_by_status("enriched")
        scored = 0
        errors = 0
        for lead in leads:
            try:
                scoring_agent.run(lead_id=lead.lead_id, session=session)
                offer_agent.run(lead_id=lead.lead_id, session=session)
                scored += 1
            except Exception as exc:
                logger.error(f"Scoring/offer error for {lead.lead_id}: {exc}")
                errors += 1

        logger.info(f"Scored {scored} leads ({errors} errors).")

        # Daily ranking
        try:
            top_leads = ranking_agent.run(session=session)
            logger.info(f"Daily top leads: {len(top_leads)} returned.")
            print("\n=== Daily Top Leads ===")
            for i, lead_info in enumerate(top_leads, 1):
                company = lead_info.get("company_name", "Unknown")
                prob = lead_info.get("sales_probability", 0)
                tier = lead_info.get("priority_tier", "?")
                print(f"  {i}. {company} - probability={prob:.2f}, tier={tier}")
        except Exception as exc:
            logger.error(f"Daily ranking failed: {exc}")
            print(f"Daily ranking error: {exc}")

    print("Scoring pipeline complete.")


def cmd_outreach(args):
    """Run Outreach Personalization and Compliance agents."""
    _init_db()
    from src.agents.outreach_personalization_agent import OutreachPersonalizationAgent
    from src.agents.compliance_agent import ComplianceAgent
    from db.repositories import LeadRepository

    logger.info("Starting outreach generation ...")
    with _get_session() as session:
        lead_repo = LeadRepository(session)
        outreach_agent = OutreachPersonalizationAgent()
        compliance_agent = ComplianceAgent(db_session=session)

        # Find leads ready for outreach (scored)
        leads = lead_repo.find_by_status("scored")
        generated = 0
        errors = 0
        for lead in leads:
            try:
                result = outreach_agent.run(
                    lead_id=lead.lead_id,
                    stage="first_touch",
                    session=session,
                )
                if result.get("status") == "generated":
                    generated += 1
                else:
                    logger.warning(f"Outreach not generated for {lead.lead_id}: {result.get('error', 'unknown')}")
            except Exception as exc:
                logger.error(f"Outreach error for {lead.lead_id}: {exc}")
                errors += 1

        logger.info(f"Outreach complete: {generated} generated, {errors} errors.")
        print(f"Outreach complete: {generated} emails generated, {errors} errors.")


def cmd_process_replies(args):
    """Run Mailbox Processor and Reply Classification."""
    _init_db()
    from src.services.mailbox_processor import MailboxProcessorService

    logger.info("Starting reply processing ...")
    with _get_session() as session:
        processor = MailboxProcessorService(session)
        result = processor.process_inbox()
        logger.info(f"Reply processing result: {json.dumps(result, indent=2, default=str)}")
        print(f"Reply processing complete:")
        print(f"  Fetched:    {result.get('fetched', 0)}")
        print(f"  Matched:    {result.get('matched', 0)}")
        print(f"  Classified: {result.get('classified', 0)}")
        print(f"  Escalated:  {result.get('escalated', 0)}")
        print(f"  Unmatched:  {result.get('unmatched', 0)}")
        if result.get("errors"):
            print(f"  Errors:     {len(result['errors'])}")


def cmd_nurture(args):
    """Run the Nurture Cadence Agent."""
    _init_db()
    logger.info("Starting nurture cadence processing ...")

    # NurtureCadenceAgent may not exist yet - handle gracefully
    try:
        from src.agents.nurture_cadence_agent import NurtureCadenceAgent
        with _get_session() as session:
            agent = NurtureCadenceAgent(session)
            result = agent.run()
            logger.info(f"Nurture result: {json.dumps(result, indent=2, default=str)}")
            print(f"Nurture cadence processing complete.")
    except ImportError:
        logger.warning("NurtureCadenceAgent not yet implemented. Skipping.")
        print("NurtureCadenceAgent not yet implemented. Skipping nurture step.")


def cmd_import_csv(args):
    """Import leads from a CSV file."""
    _init_db()
    from src.agents.lead_discovery_agent import LeadDiscoveryAgent

    filepath = args.filepath
    logger.info(f"Importing CSV: {filepath}")

    with _get_session() as session:
        discovery_agent = LeadDiscoveryAgent(session)
        result = discovery_agent.discover_from_csv(filepath)

        print(f"\nCSV Import Results:")
        print(f"  File:     {result.get('filepath', filepath)}")
        print(f"  Total:    {result.get('total_rows', 0)}")
        print(f"  Imported: {result.get('imported', 0)}")
        print(f"  Skipped:  {result.get('skipped', 0)}")
        print(f"  Errors:   {result.get('errors', 0)}")

        if result.get("error_details"):
            print(f"\n  Error details (first 10):")
            for detail in result["error_details"][:10]:
                print(f"    Row {detail.get('row', '?')}: {detail.get('error', '?')}")


def cmd_kpi(args):
    """Calculate and print daily KPIs."""
    _init_db()
    logger.info("Calculating daily KPIs ...")

    try:
        from src.skills.analytics_reporting import calculate_daily_kpis
        with _get_session() as session:
            kpis = calculate_daily_kpis(session)
            print("\n=== MCRcore Growth Engine - Daily KPIs ===")
            print(f"  Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
            print(f"  ---")
            for key, value in kpis.items():
                label = key.replace("_", " ").title()
                if isinstance(value, float):
                    print(f"  {label}: {value:.2f}")
                else:
                    print(f"  {label}: {value}")
            print("=" * 44)
    except ImportError:
        logger.warning("analytics_reporting module not yet implemented.")
        # Fallback: manual KPI calculation from DB
        _print_fallback_kpis()


def _print_fallback_kpis():
    """Print basic KPIs by querying the database directly."""
    from db.repositories import LeadRepository, OutreachRepository, ReplyRepository

    with _get_session() as session:
        lead_repo = LeadRepository(session)
        outreach_repo = OutreachRepository(session)
        reply_repo = ReplyRepository(session)

        # Count leads by status
        statuses = ["new", "enriched", "scored", "outreach_sent", "replied", "escalated"]
        print("\n=== MCRcore Growth Engine - Daily KPIs (fallback) ===")
        print(f"  Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
        print(f"  ---")
        for status in statuses:
            try:
                leads = lead_repo.find_by_status(status)
                count = len(leads) if leads else 0
                print(f"  Leads ({status}): {count}")
            except Exception:
                print(f"  Leads ({status}): N/A")
        print("=" * 52)


def cmd_run_daily(args):
    """Run the full daily pipeline orchestration."""
    _init_db()
    logger.info("=" * 60)
    logger.info("Starting MCRcore Growth Engine - Daily Pipeline")
    logger.info("=" * 60)

    # Try the DailyOrchestratorAgent first
    try:
        from src.agents.daily_orchestrator_agent import DailyOrchestratorAgent
        with _get_session() as session:
            orchestrator = DailyOrchestratorAgent(session)
            result = orchestrator.run()
            logger.info(f"Daily orchestration result: {json.dumps(result, indent=2, default=str)}")
            print("Daily pipeline complete.")
            return
    except ImportError:
        logger.info("DailyOrchestratorAgent not found, running steps manually.")

    # Manual orchestration: run each step in order
    steps = [
        ("1. Lead Discovery", cmd_discover),
        ("2. Lead Enrichment", cmd_enrich),
        ("3. Scoring + Ranking", cmd_score),
        ("4. Outreach Generation", cmd_outreach),
        ("5. Reply Processing", cmd_process_replies),
        ("6. Nurture Cadence", cmd_nurture),
    ]

    results = {}
    for step_name, step_fn in steps:
        logger.info(f"--- {step_name} ---")
        print(f"\n--- {step_name} ---")
        try:
            step_fn(args)
            results[step_name] = "OK"
        except Exception as exc:
            logger.error(f"{step_name} failed: {exc}")
            results[step_name] = f"ERROR: {exc}"
            print(f"  {step_name} failed: {exc}")

    print("\n=== Daily Pipeline Summary ===")
    for step_name, status in results.items():
        print(f"  {step_name}: {status}")
    print("==============================")
    logger.info("Daily pipeline complete.")


def cmd_schedule(args):
    """Start the scheduler daemon for automated daily runs."""
    import schedule as sched

    _init_db()

    run_time = args.time if hasattr(args, "time") and args.time else "06:00"
    logger.info(f"Starting scheduler. Daily run at {run_time} UTC.")
    print(f"MCRcore Growth Engine scheduler started.")
    print(f"Daily pipeline scheduled at {run_time} UTC.")
    print(f"Press Ctrl+C to stop.\n")

    def _daily_job():
        logger.info("Scheduler triggered daily pipeline.")
        print(f"\n[{datetime.now(timezone.utc).isoformat()}] Running daily pipeline ...")
        try:
            cmd_run_daily(argparse.Namespace())
        except Exception as exc:
            logger.error(f"Scheduled daily run failed: {exc}")
            print(f"Scheduled run failed: {exc}")

    sched.every().day.at(run_time).do(_daily_job)

    try:
        while True:
            sched.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
        print("\nScheduler stopped.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="mcr-growth-engine",
        description="MCRcore Growth Engine - Automated B2B Lead Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-daily
    sp = subparsers.add_parser("run-daily", help="Run the full daily pipeline")
    sp.set_defaults(func=cmd_run_daily)

    # discover
    sp = subparsers.add_parser("discover", help="Run lead discovery only")
    sp.set_defaults(func=cmd_discover)

    # enrich
    sp = subparsers.add_parser("enrich", help="Run lead enrichment only")
    sp.set_defaults(func=cmd_enrich)

    # score
    sp = subparsers.add_parser("score", help="Run scoring + offer matching + ranking")
    sp.set_defaults(func=cmd_score)

    # outreach
    sp = subparsers.add_parser("outreach", help="Run outreach personalization + compliance")
    sp.set_defaults(func=cmd_outreach)

    # process-replies
    sp = subparsers.add_parser("process-replies", help="Process inbox replies")
    sp.set_defaults(func=cmd_process_replies)

    # nurture
    sp = subparsers.add_parser("nurture", help="Run nurture cadence agent")
    sp.set_defaults(func=cmd_nurture)

    # import-csv
    sp = subparsers.add_parser("import-csv", help="Import leads from CSV file")
    sp.add_argument("filepath", type=str, help="Path to the CSV file")
    sp.set_defaults(func=cmd_import_csv)

    # init-db
    sp = subparsers.add_parser("init-db", help="Initialize database and seed data")
    sp.set_defaults(func=cmd_init_db)

    # kpi
    sp = subparsers.add_parser("kpi", help="Calculate and display daily KPIs")
    sp.set_defaults(func=cmd_kpi)

    # schedule
    sp = subparsers.add_parser("schedule", help="Start the daily scheduler daemon")
    sp.add_argument(
        "--time", type=str, default="06:00",
        help="UTC time for daily run (HH:MM, default: 06:00)"
    )
    sp.set_defaults(func=cmd_schedule)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except Exception as exc:
        logger.error(f"Command '{args.command}' failed: {exc}", exc_info=True)
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
