"""
MCRcore Growth Engine - Reply Intent Skill

Intent taxonomy, objection taxonomy, regex pattern lists for
opt-out detection, buying signals, referral detection, auto-response/OOO,
and bounce (NDR) detection. Pure functions and data — no DB dependency.
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Intent Taxonomy
# ---------------------------------------------------------------------------

class IntentCategory(str, Enum):
    LIKELY_ORDER = "likely_order"
    INTERESTED_NOT_READY = "interested_not_ready"
    NEUTRAL = "neutral"
    NOT_INTERESTED = "not_interested"
    OPT_OUT = "opt_out"
    BOUNCE = "bounce"
    AUTO_RESPONSE = "auto_response"
    REFERRAL = "referral"


INTENT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "likely_order": {
        "description": "Prospect is ready to buy or very close to buying",
        "examples": [
            "Can you send me pricing for the Total Plan?",
            "Let's schedule a meeting to discuss next steps",
            "We're ready to move forward — what do we need to sign?",
            "Can you send over a proposal?",
            "I'd like to set up a demo for our team",
            "What's the cost for 50 users?",
        ],
        "status_mapping": "qualified",
        "escalation_required": True,
    },
    "interested_not_ready": {
        "description": "Prospect shows interest but is not ready to commit",
        "examples": [
            "This sounds interesting, but we're in the middle of a project right now",
            "Can you follow up in Q2?",
            "We might be interested after our budget cycle",
            "Not right now but keep us in mind",
            "Could you send some more information?",
        ],
        "status_mapping": "nurturing",
        "escalation_required": False,
    },
    "neutral": {
        "description": "Non-committal reply that neither advances nor closes the opportunity",
        "examples": [
            "Thanks for reaching out",
            "Got it",
            "OK",
            "Thanks for the information",
        ],
        "status_mapping": "contacted",
        "escalation_required": False,
    },
    "not_interested": {
        "description": "Prospect is not interested but has not opted out",
        "examples": [
            "We're not interested at this time",
            "We already have an IT provider",
            "This isn't relevant to us",
            "Not for us, thanks",
            "We handle IT internally",
        ],
        "status_mapping": "closed_not_interested",
        "escalation_required": False,
    },
    "opt_out": {
        "description": "Prospect explicitly requests removal from communications",
        "examples": [
            "Please remove me from your mailing list",
            "Unsubscribe",
            "Stop emailing me",
            "Do not contact me again",
            "Take me off your list",
        ],
        "status_mapping": "suppressed",
        "escalation_required": False,
    },
    "bounce": {
        "description": "Non-delivery report or mailbox error",
        "examples": [
            "Mail delivery failed: returning message to sender",
            "The email account does not exist",
            "Mailbox unavailable",
            "550 User unknown",
        ],
        "status_mapping": "bounced",
        "escalation_required": False,
    },
    "auto_response": {
        "description": "Automated reply — out of office, auto-acknowledgement",
        "examples": [
            "I'm currently out of the office and will return on Monday",
            "This is an automated response",
            "Thank you for your email. I am currently away",
            "I will respond to your email when I return",
        ],
        "status_mapping": None,  # Do not change lead status
        "escalation_required": False,
    },
    "referral": {
        "description": "Prospect forwards or refers the conversation to another person",
        "examples": [
            "You should talk to our IT director, John Smith — john@company.com",
            "I'm not the right person. Try reaching out to Sarah in operations",
            "Forwarding this to my colleague who handles IT procurement",
            "CC'ing our CTO who would be better suited to discuss this",
        ],
        "status_mapping": "contacted",
        "escalation_required": True,
    },
}


# ---------------------------------------------------------------------------
# Objection Taxonomy
# ---------------------------------------------------------------------------

class ObjectionType(str, Enum):
    TIMING = "timing"
    BUDGET = "budget"
    COMPETITION = "competition"
    AUTHORITY = "authority"
    NEED = "need"
    TRUST = "trust"


OBJECTION_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "timing": {
        "description": "Not the right time — busy, mid-project, budget cycle",
        "patterns": [
            r"not\s+(right\s+)?now",
            r"bad\s+time",
            r"too\s+busy",
            r"mid(dle\s+of\s+a)?\s*project",
            r"follow\s+up\s+(in|next|later)",
            r"after\s+(our|the)\s+(budget|fiscal|planning)",
            r"(q[1-4]|next\s+(quarter|year|month))",
            r"circle\s+back",
            r"revisit\s+(this\s+)?(later|next)",
        ],
        "nurture_action": "schedule_follow_up",
    },
    "budget": {
        "description": "Cost or budget concerns",
        "patterns": [
            r"too\s+expensive",
            r"(out\s+of|over|above|beyond)\s+(our\s+)?budget",
            r"can'?t\s+afford",
            r"cost(s)?\s+(too\s+)?(much|high)",
            r"price\s+(is\s+)?(too\s+)?(high|steep)",
            r"cheaper\s+option",
            r"no\s+budget",
            r"budget\s+(constraint|limitation|issue)",
        ],
        "nurture_action": "send_roi_materials",
    },
    "competition": {
        "description": "Already using a competitor or alternative solution",
        "patterns": [
            r"already\s+(have|use|using|work\s+with)",
            r"(happy|satisfied)\s+with\s+(our|current)",
            r"under\s+contract",
            r"signed\s+with",
            r"switched\s+to",
            r"went\s+with\s+(another|a\s+different)",
            r"current\s+(provider|vendor|partner)",
        ],
        "nurture_action": "send_competitive_comparison",
    },
    "authority": {
        "description": "Not the decision maker or needs approval from others",
        "patterns": [
            r"(not|wrong)\s+(the\s+)?(right|correct)\s+person",
            r"(need|have)\s+to\s+(check|ask|consult|talk)",
            r"(not\s+)?my\s+(decision|call|responsibility|department)",
            r"need\s+(to\s+get\s+)?approval",
            r"run\s+(it|this)\s+(by|past)",
            r"decision\s+maker",
            r"(boss|manager|director|ceo|owner)\s+(needs|has)\s+to",
        ],
        "nurture_action": "request_intro_to_dm",
    },
    "need": {
        "description": "Does not perceive a need for the solution",
        "patterns": [
            r"don'?t\s+(need|see\s+the\s+need)",
            r"(not\s+)?(relevant|applicable)\s+(to|for)\s+us",
            r"handle\s+(it|this|everything)\s+(in-?house|internally|ourselves)",
            r"(we'?re|we\s+are)\s+(good|fine|set|covered)",
            r"no\s+(need|use|requirement)",
            r"not\s+(a\s+)?(fit|match)",
        ],
        "nurture_action": "send_pain_point_content",
    },
    "trust": {
        "description": "Skepticism about the company, product, or approach",
        "patterns": [
            r"(never|haven'?t)\s+heard\s+of",
            r"(sounds?\s+)?(too\s+good|like\s+a\s+scam)",
            r"(not\s+)?(sure|confident)\s+(about|if)",
            r"how\s+do\s+(i|we)\s+know",
            r"(references|testimonials|case\s+studies|proof)",
            r"who\s+else\s+(do\s+you|have\s+you)",
        ],
        "nurture_action": "send_case_studies",
    },
}


# ---------------------------------------------------------------------------
# Opt-Out Detection Patterns (regex, case-insensitive)
# ---------------------------------------------------------------------------

OPT_OUT_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bunsubscribe\b",
        r"\bremove\s+me\b",
        r"\bstop\s+email(ing|s)?\b",
        r"\bopt\s*[-_]?\s*out\b",
        r"\bdo\s+not\s+contact\b",
        r"\bdon'?t\s+(contact|email|message)\s+me\b",
        r"\btake\s+me\s+off\b",
        r"\bremove\s+(me\s+)?from\s+(your|the|this)\s+(list|mailing|email)",
        r"\bno\s+more\s+emails?\b",
        r"\bstop\s+(sending|contacting)\b",
        r"\bleave\s+me\s+alone\b",
        r"\bplease\s+delete\s+(my|me|this)\b",
    ]
]


# ---------------------------------------------------------------------------
# Buying Signal Patterns (regex, case-insensitive)
# ---------------------------------------------------------------------------

BUYING_SIGNAL_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(interested|interest)\s+(in|to)\b",
        r"\b(pricing|price|cost|quote|proposal)\b",
        r"\bschedule\s+(a\s+)?(call|meeting|demo|time)\b",
        r"\blet'?s\s+(talk|chat|discuss|connect|meet|set\s+up)\b",
        r"\bbudget\s+(for|to|is)\b",
        r"\bready\s+to\s+(move|proceed|go|start|sign|begin)\b",
        r"\bnext\s+steps?\b",
        r"\bsend\s+(me|us|over)\s+(a\s+)?(proposal|contract|agreement|sow|pricing)\b",
        r"\bhow\s+(much|soon|quickly)\b",
        r"\bwhat\s+(do|would|does)\s+(it|this)\s+(cost|run|involve)\b",
        r"\bsign\s+(up|the)\b",
        r"\bget\s+started\b",
        r"\btimeline\s+(for|to)\b",
        r"\bonboard(ing)?\b",
        r"\bdemo\b",
    ]
]


# ---------------------------------------------------------------------------
# Referral Detection Patterns (regex, case-insensitive)
# ---------------------------------------------------------------------------

REFERRAL_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(talk|speak|reach\s+out|contact|email)\s+(to|with)\s+\w+",
        r"\bforward(ing|ed)?\s+(this|your|the)\b",
        r"\bcc'?i?n?g?\s+(my|our|the)\b",
        r"\b(not|wrong)\s+(the\s+)?(right|correct)\s+person\b",
        r"\btry\s+(reaching|contacting|emailing|calling)\b",
        r"\bintroduc(e|ing)\s+(you\s+)?to\b",
        r"\bloop(ing|ed)?\s+in\b",
        r"\bput\s+(you\s+)?in\s+touch\b",
        r"\bbetter\s+(person|contact|suited)\b",
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\s*[-—–]\s*\S+@\S+\b",  # Name — email pattern
    ]
]


# ---------------------------------------------------------------------------
# Auto-Response / Out-of-Office Detection Patterns
# ---------------------------------------------------------------------------

AUTO_RESPONSE_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bout\s+of\s+(the\s+)?office\b",
        r"\bOOO\b",
        r"\bauto(matic|mated)?\s*(reply|response|responder)\b",
        r"\bcurrently\s+(away|out|on\s+(leave|vacation|holiday|pto))\b",
        r"\bwill\s+(return|respond|be\s+back)\s+(on|when|after)\b",
        r"\blimited\s+access\s+to\s+email\b",
        r"\baway\s+from\s+(the\s+)?office\b",
        r"\bthank\s+you\s+for\s+(your|the)\s+(email|message|inquiry)\.?\s+i\s+(will|am)\b",
        r"\bdo\s+not\s+reply\s+to\s+this\s+(email|message)\b",
        r"\bunmonitored\s+(mailbox|inbox|email)\b",
        r"\bthis\s+(is\s+)?an?\s+auto(matic|mated)\b",
    ]
]


# ---------------------------------------------------------------------------
# Bounce / NDR Detection Patterns
# ---------------------------------------------------------------------------

BOUNCE_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bmail\s+delivery\s+(failed|failure|subsystem)\b",
        r"\bundeliverable\b",
        r"\bundelivered\s+mail\b",
        r"\b(email\s+)?(account|address)\s+(does\s+not|doesn'?t)\s+exist\b",
        r"\bmailbox\s+(unavailable|full|not\s+found|does\s+not\s+exist)\b",
        r"\b550\s+\d",
        r"\b551\s+\d",
        r"\b552\s+\d",
        r"\b553\s+\d",
        r"\b554\s+\d",
        r"\buser\s+unknown\b",
        r"\bno\s+such\s+user\b",
        r"\brecipient\s+rejected\b",
        r"\bmessage\s+not\s+delivered\b",
        r"\bdelivery\s+status\s+notification\b",
        r"\bpermanent\s+(failure|error)\b",
        r"\bmailer-?daemon\b",
        r"\bpostmaster\b",
        r"\breturn(ed|ing)\s+(message|mail)\s+to\s+sender\b",
    ]
]


# ---------------------------------------------------------------------------
# Pattern Matching Functions
# ---------------------------------------------------------------------------

def match_opt_out(text: str) -> Tuple[bool, List[str]]:
    """Check if text contains opt-out language. Returns (matched, pattern_labels)."""
    matches = []
    for pattern in OPT_OUT_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return bool(matches), matches


def match_buying_signals(text: str) -> Tuple[bool, List[str]]:
    """Check if text contains buying signals. Returns (matched, pattern_labels)."""
    matches = []
    for pattern in BUYING_SIGNAL_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return bool(matches), matches


def match_referral(text: str) -> Tuple[bool, List[str]]:
    """Check if text contains referral indicators. Returns (matched, pattern_labels)."""
    matches = []
    for pattern in REFERRAL_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return bool(matches), matches


def match_auto_response(text: str) -> Tuple[bool, List[str]]:
    """Check if text is an auto-response/OOO. Returns (matched, pattern_labels)."""
    matches = []
    for pattern in AUTO_RESPONSE_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return bool(matches), matches


def match_bounce(text: str) -> Tuple[bool, List[str]]:
    """Check if text is a bounce/NDR. Returns (matched, pattern_labels)."""
    matches = []
    for pattern in BOUNCE_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern)
    return bool(matches), matches


def detect_objections(text: str) -> List[Dict[str, Any]]:
    """
    Detect objection types in text.

    Returns list of dicts: {type, description, matched_pattern, nurture_action}
    """
    detected = []
    text_lower = text.lower()
    for obj_type, config in OBJECTION_TAXONOMY.items():
        for pattern_str in config["patterns"]:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            match = pattern.search(text_lower)
            if match:
                detected.append({
                    "type": obj_type,
                    "description": config["description"],
                    "matched_text": match.group(),
                    "nurture_action": config["nurture_action"],
                })
                break  # One match per objection type is enough
    return detected


def keyword_pre_filter(text: str) -> Dict[str, Any]:
    """
    Fast keyword pre-filter before LLM classification.

    Returns a dict of detected signal categories with confidence hints
    to guide (and potentially skip) the LLM call.
    """
    result = {
        "opt_out_detected": False,
        "buying_signals_detected": False,
        "referral_detected": False,
        "auto_response_detected": False,
        "bounce_detected": False,
        "objections_detected": [],
        "suggested_category": None,
        "skip_llm": False,
    }

    opt_out_match, _ = match_opt_out(text)
    buying_match, buying_patterns = match_buying_signals(text)
    referral_match, _ = match_referral(text)
    auto_match, _ = match_auto_response(text)
    bounce_match, _ = match_bounce(text)
    objections = detect_objections(text)

    result["opt_out_detected"] = opt_out_match
    result["buying_signals_detected"] = buying_match
    result["referral_detected"] = referral_match
    result["auto_response_detected"] = auto_match
    result["bounce_detected"] = bounce_match
    result["objections_detected"] = objections

    # High-confidence keyword-only classifications (skip LLM)
    if bounce_match:
        result["suggested_category"] = "bounce"
        result["skip_llm"] = True
    elif opt_out_match:
        result["suggested_category"] = "opt_out"
        result["skip_llm"] = True
    elif auto_match:
        result["suggested_category"] = "auto_response"
        result["skip_llm"] = True
    elif buying_match and len(buying_patterns) >= 2:
        result["suggested_category"] = "likely_order"
        result["skip_llm"] = False  # LLM confirms buying intent
    elif referral_match:
        result["suggested_category"] = "referral"
        result["skip_llm"] = False  # LLM confirms referral
    elif objections:
        result["suggested_category"] = "not_interested"
        result["skip_llm"] = False  # LLM refines

    return result
