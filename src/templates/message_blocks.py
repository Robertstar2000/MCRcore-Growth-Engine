"""
MCRcore Growth Engine - Reusable Message Building Blocks

Pre-built content blocks for outreach generation, organized by:
  TITLE_BLOCKS         – Pain/value framing by buyer persona
  INDUSTRY_BLOCKS      – Vertical-specific context and proof
  PACKAGE_BLOCKS       – Service-level value props, proof points, CTAs
  DIFFERENTIATOR_BLOCKS – Email-ready versions of 8 differentiators
  COMPLIANCE_FOOTER    – CAN-SPAM compliant footer with MCRcore address
"""

from typing import Dict, List

# ===================================================================
# Compliance Footer (CAN-SPAM)
# ===================================================================

COMPLIANCE_FOOTER = (
    "\n---\n"
    "MCRcore | Managed IT & Cybersecurity\n"
    "136 W. Official Road, Addison, IL 60101\n"
    "If you'd prefer not to receive these emails, reply STOP or "
    "click here to unsubscribe: {{ unsubscribe_url }}\n"
)


# ===================================================================
# Title Blocks – Buyer Persona Messaging
# ===================================================================

TITLE_BLOCKS: Dict[str, Dict] = {

    "ceo_owner": {
        "label": "CEO / Owner / President",
        "match_titles": [
            "ceo", "chief executive", "owner", "president", "founder",
            "managing partner", "principal", "general manager",
        ],
        "pain_themes": [
            "growth constrained by unreliable technology",
            "carrying risk that one IT failure could halt operations",
            "paying full-time overhead for inconsistent IT results",
        ],
        "value_props": [
            "IT that accelerates growth instead of slowing it down",
            "Reduce operational risk without adding headcount",
            "Predictable IT spend that scales with your business",
        ],
        "openers": [
            "{{ first_name }}, growing {{ company_name }} means your technology has to keep up — or it becomes the bottleneck.",
            "Most {{ industry }} businesses at {{ company_name }}'s stage hit a wall where their IT can't scale with them.",
            "{{ first_name }}, I work with {{ industry }} leaders who refuse to let technology be the reason they miss a growth target.",
        ],
        "hooks": [
            "What would it mean for {{ company_name }} if you never worried about IT again?",
            "The cost of a single day of downtime at your scale is more than a year of proactive management.",
            "Your competitors are investing in IT strategy. The question is whether {{ company_name }} is keeping pace.",
        ],
    },

    "operations": {
        "label": "VP Operations / COO / Director of Operations",
        "match_titles": [
            "operations", "coo", "vp ops", "director of operations",
            "plant manager", "operations manager", "production manager",
        ],
        "pain_themes": [
            "unplanned downtime disrupting production or delivery schedules",
            "process friction from disconnected or unreliable systems",
            "ERP reliability issues affecting order flow and reporting",
        ],
        "value_props": [
            "Near-zero unplanned downtime through proactive monitoring",
            "Smoother operations by eliminating IT-related process friction",
            "ERP systems that are fast, stable, and always available",
        ],
        "openers": [
            "{{ first_name }}, when your systems go down at {{ company_name }}, your entire operation feels it — from the floor to the customer.",
            "I've talked with operations leaders at other {{ industry }} companies your size, and the same issue keeps coming up: IT interruptions they can't predict or prevent.",
            "{{ first_name }}, the gap between 'our systems are fine' and 'our systems never slow us down' is where most {{ industry }} companies lose margin.",
        ],
        "hooks": [
            "If your ERP went offline for four hours tomorrow, what would the downstream cost be?",
            "We find that most operations teams are working around IT issues they've stopped reporting.",
            "There's a measurable difference between 'keeping the lights on' and proactive IT management — and it shows up in throughput.",
        ],
    },

    "cfo_controller": {
        "label": "CFO / Controller / VP Finance",
        "match_titles": [
            "cfo", "chief financial", "controller", "comptroller",
            "vp finance", "finance director", "treasurer",
        ],
        "pain_themes": [
            "unpredictable IT costs and surprise invoices",
            "downtime cost that doesn't show up on the P&L until it's too late",
            "compliance risk exposure from undocumented IT posture",
        ],
        "value_props": [
            "Flat, predictable IT spend — no surprise invoices",
            "Reduced downtime cost translating directly to margin protection",
            "Compliance-ready documentation for auditors and cyber insurers",
        ],
        "openers": [
            "{{ first_name }}, the hidden cost of reactive IT at {{ company_name }} isn't the repair bill — it's the revenue you lose while waiting.",
            "Most {{ industry }} CFOs I talk to are surprised when they calculate what unplanned downtime actually costs per hour.",
            "{{ first_name }}, if {{ company_name }}'s IT spend is unpredictable quarter to quarter, there's a structural problem worth examining.",
        ],
        "hooks": [
            "We turn IT from a variable cost into a predictable operating expense — no surprises.",
            "Cyber insurance carriers are tightening requirements. Can {{ company_name }} document its security posture today?",
            "The ROI on proactive IT isn't theoretical — our clients measure it in avoided downtime and reduced incident cost.",
        ],
    },

    "it_manager": {
        "label": "IT Manager / IT Director / Sysadmin",
        "match_titles": [
            "it manager", "it director", "systems administrator",
            "network administrator", "infrastructure manager",
            "technology manager", "it lead", "sysadmin",
        ],
        "pain_themes": [
            "stretched thin across too many systems with no backup",
            "lacking specialist depth in cybersecurity or cloud",
            "no escalation path when critical issues exceed in-house capability",
        ],
        "value_props": [
            "Co-managed support that extends your team, not replaces it",
            "Specialist depth in security, cloud, and ERP you can call on instantly",
            "A reliable escalation path so you're never stuck alone on a critical issue",
        ],
        "openers": [
            "{{ first_name }}, running IT solo at {{ company_name }} means you're the helpdesk, the security team, and the CIO all at once — and something always slips.",
            "I talk to IT managers at {{ industry }} companies every week who say the same thing: they need a partner, not a replacement.",
            "{{ first_name }}, when the firewall goes down at 2 AM, you shouldn't be the only person who gets the call.",
        ],
        "hooks": [
            "Co-managed IT means you keep control — and get a team behind you for the hard stuff.",
            "Our SOC and NOC become your escalation path. You focus on the projects that move the business.",
            "We don't compete with internal IT — we make internal IT heroes.",
        ],
    },
}


# ===================================================================
# Industry Blocks – Vertical-Specific Messaging
# ===================================================================

INDUSTRY_BLOCKS: Dict[str, Dict] = {

    "manufacturing": {
        "label": "Manufacturing",
        "match_keywords": [
            "manufacturing", "manufacturer", "fabrication", "machining",
            "assembly", "production", "plant", "industrial",
        ],
        "pain_themes": [
            "production uptime directly tied to revenue",
            "ERP reliability (Epicor P21, Prophet 21) critical to order flow",
            "aging infrastructure and deferred system modernization",
        ],
        "value_props": [
            "24/7 monitoring that catches problems before they stop your line",
            "ERP expertise — we actually know P21, not just 'we can remote in'",
            "Infrastructure modernization roadmap without disrupting production",
        ],
        "proof_points": [
            "Hands-on Epicor P21 administration and performance tuning",
            "Manufacturing clients with 99.9%+ ERP uptime year over year",
            "Phased migration plans that keep production running during upgrades",
        ],
        "context_line": "In manufacturing, a system that's down is a line that's down — and every hour costs real money.",
    },

    "logistics": {
        "label": "Logistics / Freight / Supply Chain",
        "match_keywords": [
            "logistics", "freight", "trucking", "supply chain",
            "3pl", "warehouse", "distribution", "shipping", "carrier",
        ],
        "pain_themes": [
            "fleet and dispatch systems (McLeod, DAT) must be always-on",
            "tracking and visibility gaps creating customer friction",
            "operational scale outpacing IT infrastructure capacity",
        ],
        "value_props": [
            "Always-on support for McLeod, DAT Keypoint, and fleet systems",
            "End-to-end visibility so your dispatch and tracking never go dark",
            "IT infrastructure that scales as you add trucks, lanes, and locations",
        ],
        "proof_points": [
            "Direct experience managing McLeod LoadMaster/PowerBroker environments",
            "DAT Keypoint integration, connectivity, and uptime management",
            "Multi-site logistics operations supported with dual delivery model",
        ],
        "context_line": "When your load board goes down, loads don't move — and your customers call someone else.",
    },

    "insurance": {
        "label": "Insurance / Financial Services",
        "match_keywords": [
            "insurance", "underwriting", "brokerage", "claims",
            "financial services", "risk management", "agency",
        ],
        "pain_themes": [
            "compliance and regulatory requirements demanding documented IT posture",
            "data security obligations for sensitive client information",
            "policy administration systems that must stay online and performant",
        ],
        "value_props": [
            "Compliance-ready IT documentation for regulators and auditors",
            "Enterprise-grade data security at a fraction of enterprise cost",
            "Reliable hosting and support for policy admin and claims systems",
        ],
        "proof_points": [
            "Security frameworks mapped to insurance industry compliance requirements",
            "Endpoint protection and email security that satisfies cyber insurers",
            "Documented incident response plans ready for regulatory review",
        ],
        "context_line": "Insurance companies hold sensitive data under regulatory scrutiny — your IT posture has to be audit-ready at all times.",
    },

    "smb": {
        "label": "Scaling SMB (General)",
        "match_keywords": [
            "small business", "smb", "growing", "startup",
            "mid-market", "scaling", "emerging",
        ],
        "pain_themes": [
            "growth outpacing current IT capability and support",
            "no dedicated IT staff or a single overwhelmed IT person",
            "technology decisions being made without strategic guidance",
        ],
        "value_props": [
            "An IT partner that grows with you — from 20 seats to 200",
            "IT strategy and execution without the overhead of a full department",
            "Technology that enables growth instead of constraining it",
        ],
        "proof_points": [
            "Clients scaled from startup-stage IT to enterprise-ready infrastructure",
            "Fractional CIO guidance that aligns IT investment with business milestones",
            "Flat per-seat pricing that makes IT costs predictable as you grow",
        ],
        "context_line": "At your stage, every dollar and every hour counts — your IT should be an accelerant, not a drag.",
    },
}


# ===================================================================
# Package Blocks – Service-Specific Messaging
# ===================================================================

PACKAGE_BLOCKS: Dict[str, Dict] = {

    "essential_cybersecurity": {
        "name": "Essential Cybersecurity",
        "value_prop": (
            "Endpoint protection, email security, DNS filtering, and security "
            "awareness training — the minimum viable cybersecurity posture every "
            "business needs, at a price point that eliminates excuses."
        ),
        "proof_point": (
            "Our Essential Cybersecurity clients block thousands of threats per "
            "month that would have reached their users. Most didn't know they "
            "were exposed until we showed them."
        ),
        "cta_variants": [
            "Let us run a quick threat exposure scan — takes 15 minutes and costs nothing.",
            "Reply here and I'll send a sample threat report from a similar {{ industry }} company.",
            "Can I show you what your threat surface looks like right now? No commitment.",
        ],
        "title_angles": {
            "ceo_owner": "Protect {{ company_name }}'s reputation and revenue from a breach that could cost 10x what prevention does.",
            "cfo_controller": "At $25/endpoint/month, cybersecurity becomes a rounding error compared to the cost of a single incident.",
            "it_manager": "Layer enterprise-grade protection over your existing setup — we integrate, not replace.",
            "operations": "Keep your team productive and your data safe without slowing anyone down.",
        },
    },

    "proactive_monitoring": {
        "name": "Proactive Network Monitoring",
        "value_prop": (
            "24/7 monitoring of your servers, firewalls, switches, and critical "
            "endpoints — with automated alerting and proactive remediation before "
            "problems become outages."
        ),
        "proof_point": (
            "Our monitoring catches an average of 12 issues per client per month "
            "that would have become user-impacting incidents. Most clients had no "
            "idea these problems were brewing."
        ),
        "cta_variants": [
            "I'd like to show you what 24/7 monitoring reveals in the first 30 days — interested?",
            "Let us shadow-monitor your environment for a week at no cost. The report alone is worth it.",
            "Can we run a network health snapshot? It takes minutes and tells you exactly where you stand.",
        ],
        "title_angles": {
            "ceo_owner": "Stop finding out about IT problems from frustrated employees. Know before they do.",
            "operations": "Eliminate unplanned downtime with monitoring that catches issues before your team feels them.",
            "it_manager": "Extend your visibility to 24/7 without extending your hours. Our NOC watches while you sleep.",
            "cfo_controller": "The math is simple: the cost of monitoring is a fraction of the cost of one unplanned outage.",
        },
    },

    "total_plan": {
        "name": "Total Plan (Managed IT)",
        "value_prop": (
            "A complete IT department — helpdesk, on-site support, monitoring, "
            "cybersecurity, vendor management, and strategic planning — at a "
            "flat per-seat monthly cost with no surprises."
        ),
        "proof_point": (
            "Total Plan clients report 60%+ reduction in IT-related disruptions "
            "within the first quarter. Most say they finally stopped thinking "
            "about IT and started thinking about growth."
        ),
        "cta_variants": [
            "Worth a 20-minute call to see if the Total Plan math works for {{ company_name }}?",
            "I'll put together a side-by-side: what you're spending now vs. what Total Plan looks like.",
            "Let me send you a one-page overview. If the numbers make sense, we'll talk.",
        ],
        "title_angles": {
            "ceo_owner": "Your complete IT department — without the $400K+ payroll of building one in-house.",
            "operations": "One partner, one number to call, one team that knows your systems inside and out.",
            "cfo_controller": "Flat per-seat pricing. No surprise invoices. IT becomes a predictable operating expense.",
            "it_manager": "Co-managed model: you keep control of strategy, we handle the heavy lifting and 24/7 coverage.",
        },
    },

    "virtual_servers": {
        "name": "Virtual Servers (Cloud Hosting)",
        "value_prop": (
            "Replace aging on-prem hardware with scalable, managed cloud "
            "infrastructure — including backups, disaster recovery, and 24/7 "
            "monitoring. Your servers, without the server closet."
        ),
        "proof_point": (
            "We've migrated ERP environments (P21, McLeod) to cloud hosting "
            "with zero unplanned downtime during transition and measurable "
            "performance improvement afterward."
        ),
        "cta_variants": [
            "When's your next server refresh? Let me show you the cloud alternative before you buy hardware.",
            "I'll build a quick TCO comparison: on-prem refresh vs. hosted. No strings.",
            "Interested in seeing how other {{ industry }} companies your size have moved to cloud? I'll share a case study.",
        ],
        "title_angles": {
            "ceo_owner": "Eliminate the capital expense of hardware refresh and get better performance in the cloud.",
            "operations": "ERP in the cloud means faster, more reliable, and accessible from every location.",
            "cfo_controller": "Move from CapEx hardware cycles to predictable OpEx cloud hosting — your CFO peers love this.",
            "it_manager": "We handle the infrastructure. You keep the admin access. Best of both worlds.",
        },
    },

    "fractional_cio": {
        "name": "Fractional CIO",
        "value_prop": (
            "Strategic IT leadership — budgeting, vendor management, technology "
            "roadmapping, and board-ready reporting — without the $200K+ salary "
            "of a full-time CIO."
        ),
        "proof_point": (
            "Our Fractional CIO clients make better technology decisions, avoid "
            "costly vendor lock-in, and have a clear 3-year IT roadmap. Most say "
            "they should have done this years earlier."
        ),
        "cta_variants": [
            "If {{ company_name }} is making six-figure technology decisions without a CIO, let's fix that.",
            "Can I show you what a quarterly IT scorecard and roadmap look like? It might change how you think about IT.",
            "20 minutes — I'll walk you through what Fractional CIO looks like for a {{ industry }} company your size.",
        ],
        "title_angles": {
            "ceo_owner": "You have a CFO for your finances. This is the CIO equivalent for your technology.",
            "operations": "IT decisions that align with operational goals instead of reacting to the latest fire.",
            "cfo_controller": "Strategic IT planning that ties every dollar to business outcomes — not just keeping the lights on.",
            "it_manager": "A strategic layer above day-to-day IT. You execute the plan — we help you build it.",
        },
    },

    "it_process_automation": {
        "name": "IT Process Automation",
        "value_prop": (
            "Automate the repetitive IT and business processes that eat your "
            "team's time: user provisioning, reporting, data flows between "
            "systems, and approval workflows."
        ),
        "proof_point": (
            "Our automation clients reclaim 20+ hours per month on employee "
            "onboarding/offboarding alone. One client eliminated 3 days of "
            "manual reporting with a single workflow."
        ),
        "cta_variants": [
            "What's the most time-consuming manual process at {{ company_name }}? I bet we can automate it.",
            "I'll map one process for free — just to show you what's possible. Sound fair?",
            "Reply with your biggest data-entry bottleneck and I'll sketch an automation in 48 hours.",
        ],
        "title_angles": {
            "ceo_owner": "Free your team from repetitive work so they can focus on growing {{ company_name }}.",
            "operations": "Eliminate manual handoffs between systems. Fewer errors, faster cycle times.",
            "cfo_controller": "Reduce labor cost on routine processes and redeploy that headcount to revenue work.",
            "it_manager": "Stop spending weekends on provisioning scripts. Let us build automations that just work.",
        },
    },

    "wfh_implementation": {
        "name": "Work From Home Implementation",
        "value_prop": (
            "Secure, productive remote and hybrid work — VPN or Zero Trust setup, "
            "endpoint hardening, collaboration tools, and security policies for "
            "distributed teams."
        ),
        "proof_point": (
            "We've enabled fully secure remote work for companies with 25-300 "
            "employees, including secure access to on-prem ERP systems from "
            "home offices nationwide."
        ),
        "cta_variants": [
            "Are your remote employees connecting securely — or just conveniently? Let's check.",
            "I'll run a quick remote access security assessment for {{ company_name }}. Takes 15 minutes.",
            "Hybrid work is here to stay. Is {{ company_name }}'s infrastructure set up for it? Let's find out.",
        ],
        "title_angles": {
            "ceo_owner": "Enable your team to work from anywhere without compromising security or productivity.",
            "operations": "Remote access to ERP and LOB applications — fast, secure, and reliable from any location.",
            "cfo_controller": "Reduce office footprint costs while keeping your team fully productive and secure.",
            "it_manager": "We handle the VPN/ZTNA architecture. You get a secure, managed remote workforce.",
        },
    },

    "technical_audit": {
        "name": "Technical Audit",
        "value_prop": (
            "A comprehensive, no-obligation assessment of your IT infrastructure, "
            "security posture, and operational maturity — delivered as a scored "
            "report with prioritized recommendations."
        ),
        "proof_point": (
            "Every audit we run uncovers at least 3-5 critical risks the "
            "current provider missed. Clients call it the most useful IT "
            "document they've ever received."
        ),
        "cta_variants": [
            "What would a 50-point IT inspection reveal about {{ company_name }}? Let's find out — no cost, no obligation.",
            "I'd like to run a complimentary Technical Audit for {{ company_name }}. Worth 30 minutes of your time?",
            "Let the audit speak for itself. If we don't find anything worth fixing, you've lost nothing.",
        ],
        "title_angles": {
            "ceo_owner": "Know exactly where {{ company_name }} stands before making your next IT investment.",
            "operations": "A scored report that shows which systems are solid and which are one failure away from stopping your operation.",
            "cfo_controller": "Prioritized recommendations with cost estimates — so you can budget IT fixes by business impact.",
            "it_manager": "An independent second opinion on your infrastructure. Use it to get budget approval for what you already know needs fixing.",
        },
    },

    "voip": {
        "name": "VOIP Phone Systems",
        "value_prop": (
            "Modern cloud-based phone systems with auto-attendant, call routing, "
            "voicemail-to-email, mobile apps, and CRM/ERP integration — replacing "
            "legacy PBX with scalable UCaaS."
        ),
        "proof_point": (
            "Clients who move to our VOIP solution typically cut telecom costs "
            "by 30-40% while gaining features their old PBX couldn't provide, "
            "including mobile integration and multi-site unification."
        ),
        "cta_variants": [
            "Is your PBX end-of-life or just overpriced? Let me run a quick comparison.",
            "I'll pull a VOIP cost analysis vs. your current phone bill. Takes one call.",
            "Modern phone systems do more than ring. Let me show you what you're missing.",
        ],
        "title_angles": {
            "ceo_owner": "Unified communications across every location — one system, one bill, zero legacy headaches.",
            "operations": "Multi-site call routing, mobile integration, and CRM-connected calls for your team.",
            "cfo_controller": "Replace your legacy PBX bill with a lower, predictable per-seat VOIP cost.",
            "it_manager": "Cloud-managed phone system. No on-prem PBX to babysit. Full admin portal for you.",
        },
    },

    "on_demand_break_fix": {
        "name": "On-Demand / Break & Fix",
        "value_prop": (
            "Expert IT support on an as-needed basis — troubleshooting, repairs, "
            "moves, and project work. No contract required. A low-risk way to "
            "experience MCRcore's quality before committing to a managed plan."
        ),
        "proof_point": (
            "80% of our break-fix clients move to a managed plan within 6 months — "
            "not because we push them, but because they see the difference between "
            "reactive and proactive IT."
        ),
        "cta_variants": [
            "Got a nagging IT issue no one's been able to fix? Let us take a look.",
            "No contract, no commitment. Just expert help when you need it. Reply and I'll get someone on it.",
            "Sometimes you just need someone good to call. That's what On-Demand is for.",
        ],
        "title_angles": {
            "ceo_owner": "Try MCRcore risk-free. One project, one issue — see the quality before you commit.",
            "operations": "Fast, expert resolution for the IT issues slowing your team down. Call us once, see the difference.",
            "cfo_controller": "Pay only for what you use. No retainer, no seat fee. Just expert help at a fair hourly rate.",
            "it_manager": "An escalation partner for the stuff that's over your head or under your time. We get it.",
        },
    },
}


# ===================================================================
# Differentiator Blocks – Email-Ready Inserts
# ===================================================================

DIFFERENTIATOR_BLOCKS: Dict[str, Dict] = {

    "deep_erp_expertise": {
        "short_insert": (
            "Unlike generic MSPs, MCRcore has hands-on experience with the ERP "
            "systems you actually run — Epicor P21, McLeod, DAT Keypoint, and "
            "Point of Rental. We don't just 'support' your ERP — we know it."
        ),
        "one_liner": "Your MSP says they support P21. We've actually tuned a P21 SQL instance.",
        "proof_line": "Our team has years of direct ERP administration — not just remote access and Google searches.",
        "best_for_titles": ["operations", "it_manager", "ceo_owner"],
        "best_for_industries": ["manufacturing", "logistics"],
    },

    "not_generic_msp": {
        "short_insert": (
            "MCRcore isn't a ticket-and-seat MSP. We start with your business "
            "goals and work backward to the technology — no unnecessary upsells, "
            "no generic playbooks."
        ),
        "one_liner": "We don't sell seats. We solve business problems with technology.",
        "proof_line": "Every engagement starts with understanding your objectives, not installing an RMM agent.",
        "best_for_titles": ["ceo_owner", "cfo_controller"],
        "best_for_industries": ["smb", "manufacturing", "insurance"],
    },

    "dual_delivery_model": {
        "short_insert": (
            "MCRcore combines on-site technicians in the Midwest and Northern "
            "Florida with a 24/7 remote NOC/SOC covering all of North America. "
            "Boots on the ground when you need them. Instant remote help always."
        ),
        "one_liner": "Remote support for speed. On-site support when it matters.",
        "proof_line": "Same-day on-site response in core markets, plus 24/7 remote remediation nationwide.",
        "best_for_titles": ["operations", "it_manager"],
        "best_for_industries": ["manufacturing", "logistics"],
    },

    "fractional_cio_access": {
        "short_insert": (
            "Every MCRcore managed client gets Fractional CIO access — strategic "
            "IT planning, budgeting, vendor negotiation, and quarterly business "
            "reviews. The C-level IT leadership SMBs can't otherwise afford."
        ),
        "one_liner": "You have a CFO. Why not a CIO — at a fraction of the cost?",
        "proof_line": "Dedicated vCIO, quarterly scorecards, and board-ready IT reports — included with every managed plan.",
        "best_for_titles": ["ceo_owner", "cfo_controller"],
        "best_for_industries": ["smb", "manufacturing", "insurance"],
    },

    "business_first_founders": {
        "short_insert": (
            "MCRcore's leadership has 20+ years of experience running businesses "
            "— not just managing networks. We understand P&L pressures, growth "
            "challenges, and what it means to bet your company on a technology decision."
        ),
        "one_liner": "Built by people who've run businesses — not just servers.",
        "proof_line": "Our founders come from manufacturing, logistics, and professional services. We've sat in your chair.",
        "best_for_titles": ["ceo_owner", "operations"],
        "best_for_industries": ["smb", "manufacturing", "logistics"],
    },

    "24_7_monitoring": {
        "short_insert": (
            "MCRcore's NOC and SOC operate 24/7/365 with real-time monitoring, "
            "automated remediation, and human-verified escalation within 15 minutes. "
            "Not a dashboard someone checks Monday morning."
        ),
        "one_liner": "Your firewall logged 10,000 events last night. Who reviewed them?",
        "proof_line": "Automated remediation for common issues. Human escalation within 15 minutes for critical alerts.",
        "best_for_titles": ["operations", "it_manager", "ceo_owner"],
        "best_for_industries": ["manufacturing", "logistics", "insurance"],
    },

    "audit_first_engagement": {
        "short_insert": (
            "MCRcore leads with a Technical Audit, not a sales pitch. We assess "
            "your environment, identify risks, and deliver a scored report with "
            "prioritized recommendations — before asking for a dime."
        ),
        "one_liner": "Don't take our word for it — let the audit speak for itself.",
        "proof_line": "Every audit uncovers 3-5 critical risks the current provider missed. No obligation to act on them with us.",
        "best_for_titles": ["ceo_owner", "cfo_controller", "it_manager"],
        "best_for_industries": ["smb", "insurance", "manufacturing"],
    },

    "tallman_backing": {
        "short_insert": (
            "MCRcore is backed by Tallman Equipment Group — an established, "
            "multi-site business operation. This isn't a two-person garage MSP. "
            "We deploy every solution in our own operations first."
        ),
        "one_liner": "Backed by a real business, not just venture capital.",
        "proof_line": "Every solution we recommend, we've already deployed and operated in our own multi-site environment.",
        "best_for_titles": ["ceo_owner", "cfo_controller"],
        "best_for_industries": ["manufacturing", "logistics", "smb"],
    },
}
