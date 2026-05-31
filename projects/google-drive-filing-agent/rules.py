"""Filing rules and folder configuration — edit this file to add or change rules."""

import re
from dataclasses import dataclass
from typing import Optional


# ── Folder IDs ────────────────────────────────────────────────────────────────

FOLDER_IDS = {
    "home_budgeting":       "1ktUUf-9cqaxDFII_KBzEh4xQ1DG8KUaK",
    "abdul_doa":            "1aZaZmbPRnqPdN1eXl95WJuaYhuDsPRdj",
    "extended_fam":         "1EHH8t3L2JTeOzfAEp1IHiPTmt20_RhsW",
    "data_analytics":       "1YwfqfsdvWbFXPe4vYQmvkzLMRkUDBS9h",
    "abdul_data":           "1MIBgN7SI6zttBNwq8SzIuhn5zfIQn9hk",
    "license_certs":        "1olQ4jfQ9H0QewrAJjLfF_no0WYmT50f3",
    "financial_statements": "13bKsZxCJwQFQ7Eb2vcbtMq7e1XBRCZ51",
}

# ── Protected patterns — never touch these ────────────────────────────────────

PROTECTED_PATTERNS = [
    r"step father",
    r"halefom",
    r"^epp1-",
    r"^fd-258",
    r"^fd-1164",
    r"^form 888",
    r"lost passport",
]

PROTECTED_MIME_TYPES = set()  # extend if needed


# ── Filing rule definition ────────────────────────────────────────────────────

@dataclass
class FilingRule:
    name: str
    pattern: str           # regex applied to filename (case-insensitive)
    workstream: str        # finance | learning | legal
    dest_parent_key: str   # key in FOLDER_IDS for the fixed parent
    dest_subpath: list     # additional subfolder segments (may contain {year}/{month})
    rename_template: Optional[str] = None  # None = keep original name
    needs_pdf_analysis: bool = False       # spawn Haiku subagent to extract vendor/date
    mime_filter: Optional[str] = None     # restrict to specific mimeType


RULES: list[FilingRule] = [

    # ── Finance ──────────────────────────────────────────────────────────────

    FilingRule(
        name="bank_csv",
        pattern=r"^Csv20(\d{2})(\d{2})\d{2}.*\.csv$",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Bank-Exports", "{year}", "{month}"],
    ),
    FilingRule(
        name="bank_ofx",
        pattern=r"^Ofx20(\d{2})(\d{2})\d{2}.*\.ofx$",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Bank-Exports", "{year}", "{month}"],
    ),
    FilingRule(
        name="betashares",
        pattern=r"^betashares-transactions_(\d{4})-",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Brokerage", "Betashares", "{year}"],
    ),
    FilingRule(
        name="portfolio_holdings",
        pattern=r"_Portfolio_Holdings\.csv$",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Brokerage", "Portfolio-Holdings"],
    ),
    FilingRule(
        name="ato_dispute",
        pattern=r"^Form-16-Dispute-resolution-request",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Tax", "Disputes"],
        rename_template="{date}_Form-16-Dispute_{original}",
    ),
    FilingRule(
        name="invoice",
        pattern=r"^Invoice-.*\.pdf$",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Invoices", "{vendor}", "{year}"],
        rename_template="{date}_{vendor}_{original}",
        needs_pdf_analysis=True,
    ),
    FilingRule(
        name="receipt",
        pattern=r"^Receipt-.*\.pdf$",
        workstream="finance",
        dest_parent_key="abdul_doa",
        dest_subpath=["Receipts", "{vendor}", "{year}"],
        rename_template="{date}_{vendor}_{original}",
        needs_pdf_analysis=True,
    ),
    FilingRule(
        name="cashflow",
        pattern=r"(CASHFLOW|Cashflow)",
        workstream="finance",
        dest_parent_key="extended_fam",
        dest_subpath=["Cashflow"],
    ),

    # ── Learning ─────────────────────────────────────────────────────────────

    FilingRule(
        name="reference_guide",
        pattern=r"^Reference guide:",
        workstream="learning",
        dest_parent_key="data_analytics",
        dest_subpath=["Reference-Guides"],
        mime_filter="application/vnd.google-apps.document",
    ),
    FilingRule(
        name="bellabeat_data",
        pattern=r"^(dailyActivity|sleepDay|weightLogInfo|hourlyCalories|hourlySteps|minuteCalories|minuteSteps).*_merged\.csv$",
        workstream="learning",
        dest_parent_key="data_analytics",
        dest_subpath=["Case-Studies", "Bellabeat"],
    ),
    FilingRule(
        name="bellabeat_slides",
        pattern=r"^Bella?beat",
        workstream="learning",
        dest_parent_key="data_analytics",
        dest_subpath=["Case-Studies", "Bellabeat"],
        mime_filter="application/vnd.google-apps.presentation",
    ),
    FilingRule(
        name="cyclistic_data",
        pattern=r"^\d{6}-divvy-tripdata\.csv$",
        workstream="learning",
        dest_parent_key="data_analytics",
        dest_subpath=["Case-Studies", "Cyclistic"],
    ),
    FilingRule(
        name="cyclistic_docs",
        pattern=r"^Cyclistic",
        workstream="learning",
        dest_parent_key="data_analytics",
        dest_subpath=["Case-Studies", "Cyclistic"],
    ),
    FilingRule(
        name="coursera_dataset",
        pattern=r"^[A-Za-z0-9_-]{22}_[a-f0-9]{32}_",
        workstream="learning",
        dest_parent_key="data_analytics",
        dest_subpath=["Course-Datasets"],
    ),

    # ── Legal ─────────────────────────────────────────────────────────────────

    FilingRule(
        name="legal_notice",
        pattern=r"^notice-of-legal-effect",
        workstream="legal",
        dest_parent_key="license_certs",
        dest_subpath=["Legal"],
    ),
]


# ── Scan locations ────────────────────────────────────────────────────────────

SCAN_LOCATIONS = [
    {"name": "Drive root",               "query_prefix": "'root' in parents"},
    {"name": "Extended Fam",             "folder_id": FOLDER_IDS["extended_fam"]},
    {"name": "Financial Statements",     "folder_id": FOLDER_IDS["financial_statements"]},
    {"name": "Abdul Data (subfolders)",  "parent_id": FOLDER_IDS["abdul_data"],
     "subfolder_names": ["csv Files", "Downloads", "pdf", "G-Docx"]},
]

DEDUP_PATTERNS = ["Csv202", "Invoice-", "Receipt-", "betashares-transactions"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_protected(filename: str) -> bool:
    name_lower = filename.lower()
    return any(re.search(p, name_lower) for p in PROTECTED_PATTERNS)


def match_rule(file: dict, workstream_filter: str = "all") -> Optional[FilingRule]:
    name = file.get("name", "")
    mime = file.get("mimeType", "")

    for rule in RULES:
        if workstream_filter != "all" and rule.workstream != workstream_filter:
            continue
        if rule.mime_filter and rule.mime_filter != mime:
            continue
        if re.search(rule.pattern, name, re.IGNORECASE):
            return rule

    return None
