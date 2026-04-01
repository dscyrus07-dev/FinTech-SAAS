"""
ICICI Bank Transaction Report Generator
=======================================
Deterministic financial report generator using:
- pandas (calculation)
- xlsxwriter (formatting)
- strict rule engine (classification)

Generates 9-sheet Excel report:
1. Summary - Monthly aggregations
2. Category Analysis - Credit/Debit category breakdown
3. Weekly Analysis - Weekly credit/debit totals
4. Recurring Analysis - Recurring vs non-recurring
5. Bounces & Penal - Bounce and penalty analysis
6. Funds Received - Top inflows per month
7. Funds Remittance - Top outflows per month
8. Raw Transaction - All transactions with Category, Confidence, Recurring
9. Finbit - Monthly Finbit metrics (30 financial indicators)

No AI. No fuzzy logic. No probability scoring.
Every output cell traceable to an exact rule.
"""

import logging
import os
import re
from collections import Counter, OrderedDict
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd
from .icici_classifier import ICICIClassifier
from ...intelligence import LearningStore

logger = logging.getLogger(__name__)

# Initialize the unified ICICI classifier (singleton)
_classifier = None
_learning_store = None

def get_classifier() -> ICICIClassifier:
    """Get or create the unified ICICI classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = ICICIClassifier()
        logger.info("ICICI classifier initialized: %s", _classifier.get_category_stats())
    return _classifier

def classify(row) -> Tuple[str, int]:
    """
    Advanced classification using comprehensive keyword database.
    Uses entity interpretation with direction awareness.
    """
    global _learning_store
    description = str(row.get("Description", ""))
    if _learning_store is None:
        _learning_store = LearningStore()
    learned = _learning_store.lookup(description, bank_name="ICICI")
    if learned:
        return {
            "internal_category": learned.get("category", "UNCATEGORIZED"),
            "display_category": learned.get("category", "Uncategorised"),
            "confidence_score": int(max(float(learned.get("confidence", 0.9)) * 100, 90)),
            "matched_rule": "learning_memory",
            "matched_token": learned.get("normalized_entity", ""),
        }

    classifier = get_classifier()
    result = classifier.classify(row)
    try:
        category = str(result.get("display_category") or result.get("internal_category") or "")
        confidence = float(result.get("confidence_score") or 0)
        if category and confidence >= 80 and category not in {"Uncategorised", "UNCATEGORIZED", "Others", "Others Debit", "Others Credit"}:
            if _learning_store is None:
                _learning_store = LearningStore()
            _learning_store.record_observation(
                description=row.get("Description", ""),
                category=category,
                confidence=confidence / 100.0,
                source="rule",
                bank_name="ICICI",
                account_type="",
                metadata={
                    "matched_rule": result.get("matched_rule", ""),
                    "matched_token": result.get("matched_token", ""),
                },
            )
    except Exception:
        logger.debug("ICICI learning-store update skipped", exc_info=True)
    return result


def detect_recurring(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect recurring transactions.
    Recurring = same description (case-insensitive) AND same amount appears >= 3 times.
    """
    df = df.copy()
    desc_norm = df["Description"].str.lower().str.strip()

    def make_key(idx):
        amt = df.at[idx, "Debit"] if df.at[idx, "Debit"] > 0 else df.at[idx, "Credit"]
        # 5% tolerance band
        band = round(amt / max(amt * 0.05, 1)) if amt > 0 else 0
        return (desc_norm.at[idx], band)

    keys = [make_key(i) for i in df.index]
    key_counts = Counter(keys)
    df["Recurring"] = ["Yes" if key_counts[k] >= 3 else "No" for k in keys]
    return df


def get_week_bucket(d) -> str:
    """Assign transaction to week bucket based on day of month (5-day gap)."""
    day = d.day
    if 1 <= day <= 5:
        return "Week 1 (1-5)"
    if 6 <= day <= 10:
        return "Week 2 (6-10)"
    if 11 <= day <= 15:
        return "Week 3 (11-15)"
    if 16 <= day <= 20:
        return "Week 4 (16-20)"
    if 21 <= day <= 25:
        return "Week 5 (21-25)"
    return "Week 6 (26-end)"


# Cheque detection tokens for description-level matching
CHEQUE_TOKENS = [
    "clg chq", "chq dep", "cheque deposit", "cheque issued",
    "chq paid", "chq no", "cheque no", "by chq",
    "cheque", "clg", "chq",
]


def _normalize_text(value: Any) -> str:
    text = str(value or "").upper()
    text = re.sub(r"[^A-Z0-9\s/\-_.]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_transaction_mode(description: Any) -> str:
    desc = _normalize_text(description)
    mode_patterns = [
        ("Cash Deposit", ["CASH DEPOSIT", "CASH DEP", "CDM", "CASHDEP", "DEP BY CASH", "BY CASH"]),
        ("Cash Withdrawal", ["CASH WITHDRAWAL", "CASH WDL", "CASH W/D", "CASHWITHDRAWAL"]),
        ("ATM Withdrawal", ["ATM", "ATW", "ATM WDL", "ATM WITHDRAWAL", "ATM CASH", "VISA ATM", "NFS ATM"]),
        ("UPI", ["UPI"]),
        ("IMPS", ["IMPS"]),
        ("NEFT", ["NEFT", "NEFTDR", "NEFT CR", "NEFT DR", "RTGS"]),
        ("ACH", ["ACH", "ACH D", "ACH DR", "ACH CR", "NACH", "ECS", "E-MANDATE", "AUTOPAY"]),
        ("Cheque", ["CHEQUE", "CHQ", "CLG"]),
        ("Card Settlement", ["POS", "CARD SETTLEMENT", "VISA", "MASTER", "RUPAY"]),
    ]
    for mode, patterns in mode_patterns:
        if any(p in desc for p in patterns):
            return mode
    return "Other"


def _extract_source(description: Any, mode: str) -> str:
    desc = _normalize_text(description)

    source_rules = [
        (r"\bMAKE ?MY ?TRIP\b|\bMMT\b", "MakeMyTrip"),
        (r"\bAGODA\b", "Agoda"),
        (r"\bAIRBNB\b", "Airbnb"),
        (r"\bBOOKING\.COM\b|\bBOOKING\b", "Booking.com"),
        (r"\bUBER\b|\bOLA\b|\bRAPIDO\b", "Cab Service"),
        (r"\bZOMATO\b", "Zomato"),
        (r"\bSWIGGY\b", "Swiggy"),
        (r"\bNETFLIX\b", "Netflix"),
        (r"\bSPOTIFY\b", "Spotify"),
        (r"\bAMAZON PRIME\b|\bPRIME VIDEO\b|\bPRIMEVIDEO\b", "Amazon Prime"),
        (r"\bDISNEY\+?\b|\bHOTSTAR\b", "Disney+ Hotstar"),
        (r"\bPHONEPE\b", "PhonePe"),
        (r"\bPAYTM\b", "Paytm"),
        (r"\bGOOGLE PAY\b|\bGPAY\b", "Google Pay"),
        (r"\bAMAZON\b", "Amazon"),
        (r"\bFLIPKART\b", "Flipkart"),
        (r"\bRENT\b|\bLANDLORD\b", "Landlord"),
        (r"\bSALARY\b|\bPAYROLL\b|\bSTIPEND\b|\bWAGES\b", "Employer"),
        (r"\bEMI\b|\bLOAN\b|\bFINANCE\b|\bNACH\b|\bACH\b", "Bank/Loan Provider"),
        (r"\bENTERPRISES?\b", "Enterprise"),
        (r"\bGST\b|\bCBDT\b|\bTAX\b", "Government / Tax Authority"),
    ]

    for pattern, source_name in source_rules:
        if re.search(pattern, desc):
            return source_name

    cleaned = desc
    remove_tokens = [
        "NEFT", "NEFTDR", "NEFT CR", "NEFT DR", "RTGS", "IMPS", "UPI", "ACH", "NACH", "ECS",
        "ATM", "ATW", "POS", "CARD", "SETTLEMENT", "CASH", "DEPOSIT", "WITHDRAWAL", "WITHDRWL",
        "TRF", "TRANSFER", "PAYMENT", "DR", "CR", "TO", "FROM", "BY", "SELF", "CHQ", "CHEQUE",
        "CLG", "REF", "TXN", "TRANSACTION", "NO", "NUMBER",
    ]
    for token in remove_tokens:
        cleaned = re.sub(rf"\b{re.escape(token)}\b", " ", cleaned)

    cleaned = re.sub(r"\b\d{2}[/-]\d{2}[/-]\d{2,4}\b", " ", cleaned)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_./")
    if not cleaned:
        return "Unknown"

    tokens = [tok for tok in cleaned.split() if len(tok) > 2]
    if not tokens:
        return "Unknown"

    return " ".join(tokens[:4]).title()


def _map_identified_category(source: str, mode: str, description: Any, existing_category: str, is_credit: bool) -> str:
    desc = _normalize_text(description)
    src = _normalize_text(source)

    if any(k in src for k in ["SALARY", "EMPLOYER"]):
        return "Salary"
    if any(k in src for k in ["LANDLORD", "RENT"]):
        return "Rent"
    if any(k in src for k in ["NETFLIX", "SPOTIFY", "PRIME", "HOTSTAR", "DISNEY"]):
        return "Subscription"
    if any(k in src for k in ["ZOMATO", "SWIGGY"]):
        return "Food"
    if any(k in src for k in ["MAKEMYTRIP", "AGODA", "AIRBNB", "BOOKING.COM", "CAB SERVICE"]):
        return "Travel"
    if any(k in src for k in ["PHONEPE", "PAYTM", "GOOGLE PAY"]):
        return "Digital Wallet"
    if any(k in src for k in ["ENTERPRISE", "BUSINESS INCOME"]):
        return "Business Income" if is_credit else "Business Expense"
    if any(k in src for k in ["BANK/LOAN PROVIDER", "EMI", "LOAN", "FINANCE"]):
        return "EMI / Loan"
    if any(k in src for k in ["GOVERNMENT", "TAX"]):
        return "Tax"
    if any(k in desc for k in ["ELECTRICITY", "WATER", "BILL", "GAS", "BROADBAND", "RECHARGE"]):
        return "Utilities"
    if mode == "Cash Deposit":
        return "Cash Deposit"
    if mode == "Cash Withdrawal":
        return "Cash Withdrawal"
    if mode == "ATM Withdrawal":
        return "ATM Withdrawal"
    if mode == "UPI":
        return "Transfer" if is_credit else "UPI Payment"
    if mode in {"IMPS", "NEFT", "ACH"}:
        return "Transfer" if is_credit else (existing_category if existing_category and existing_category != "Others" else "Transfer Out")

    if existing_category and existing_category != "Others":
        return existing_category

    return "Others"


def _flag_transaction(amount: float, source: str, recurring: bool, mode: str) -> str:
    flags = []
    if amount >= 100000:
        flags.append("High Value")
    if recurring:
        flags.append("Recurring")
    if source == "Unknown" and amount >= 50000:
        flags.append("Suspicious")
    if mode == "Other" and source == "Unknown" and amount >= 25000:
        flags.append("Review")
    return ", ".join(flags)


def _build_source_analysis_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    if "Description" not in frame.columns:
        frame["Description"] = ""
    if "Date" not in frame.columns:
        frame["Date"] = pd.NaT
    if "Credit" not in frame.columns:
        frame["Credit"] = 0
    if "Debit" not in frame.columns:
        frame["Debit"] = 0
    if "Balance" not in frame.columns:
        frame["Balance"] = 0
    if "Category" not in frame.columns:
        frame["Category"] = "Others"

    frame["TransactionMode"] = frame["Description"].apply(_detect_transaction_mode)
    frame["Source"] = [_extract_source(desc, mode) for desc, mode in zip(frame["Description"], frame["TransactionMode"])]
    frame["IsCredit"] = frame["Credit"].fillna(0) > 0
    frame["TxnAmount"] = frame["Credit"].where(frame["Credit"].fillna(0) > 0, frame["Debit"].fillna(0))

    recurring_keys = set()
    source_groups = frame.groupby(frame["Source"].str.lower().fillna("unknown"))
    for key, group in source_groups:
        if key == "unknown" or len(group) < 3:
            continue
        month_count = group["Date"].dt.to_period("M").nunique() if "Date" in group else 0
        if month_count >= 2:
            recurring_keys.add(key)

    frame["IsRecurring"] = frame["Source"].str.lower().fillna("unknown").isin(recurring_keys)
    frame["IdentifiedCategory"] = [
        _map_identified_category(source, mode, desc, cat, is_credit)
        for source, mode, desc, cat, is_credit in zip(
            frame["Source"],
            frame["TransactionMode"],
            frame["Description"],
            frame["Category"],
            frame["IsCredit"],
        )
    ]
    frame["Flag"] = [
        _flag_transaction(amount, source, recurring, mode)
        for amount, source, recurring, mode in zip(
            frame["TxnAmount"].fillna(0),
            frame["Source"],
            frame["IsRecurring"],
            frame["TransactionMode"],
        )
    ]
    frame["Month"] = frame["Date"].dt.to_period("M").astype(str)
    return frame


def _build_category_outcome_tables(source_frame: pd.DataFrame) -> Dict[str, Any]:
    frame = source_frame.copy()

    if "IdentifiedCategory" not in frame.columns:
        frame["IdentifiedCategory"] = "Others"

    frame["Category"] = frame["IdentifiedCategory"].fillna("").astype(str).str.strip()
    frame.loc[frame["Category"] == "", "Category"] = "Others"
    frame["Source"] = frame["Source"].fillna("").astype(str).str.strip()
    frame.loc[frame["Source"] == "", "Source"] = "Unknown"
    frame["Month"] = frame["Month"].fillna("").astype(str).str.strip()
    frame["Credit"] = pd.to_numeric(frame["Credit"], errors="coerce").fillna(0)
    frame["Debit"] = pd.to_numeric(frame["Debit"], errors="coerce").fillna(0)
    frame["Flag"] = frame.get("Flag", "")
    frame["Flag"] = frame["Flag"].fillna("").astype(str).str.strip()

    month_dt = pd.to_datetime(frame["Month"], errors="coerce")
    frame["MonthKey"] = month_dt.dt.to_period("M").astype(str)
    month_periods = []
    for period in month_dt.dropna().dt.to_period("M").tolist():
        if period not in month_periods:
            month_periods.append(period)
    month_periods = sorted(month_periods)[:6]
    month_keys = [period.strftime("%Y-%m") for period in month_periods]
    month_labels = [period.strftime("%B %Y") for period in month_periods]
    month_lookup = dict(zip(month_keys, month_labels))

    def _pivot_metric(value_col: str, filter_mask: pd.Series, agg_kind: str) -> pd.DataFrame:
        base = frame.loc[filter_mask, ["Category", "Source", "MonthKey", value_col]].copy()
        if base.empty:
            return pd.DataFrame(columns=["Category", "Source", *month_labels])

        if agg_kind == "count":
            base["MetricValue"] = 1
        else:
            base["MetricValue"] = base[value_col]

        grouped = (
            base.groupby(["Category", "Source", "MonthKey"], dropna=False)["MetricValue"]
            .sum()
            .reset_index()
        )
        pivot = grouped.pivot_table(
            index=["Category", "Source"],
            columns="MonthKey",
            values="MetricValue",
            aggfunc="sum",
            fill_value=0,
        )

        pivot = pivot.reindex(columns=month_keys, fill_value=0).reset_index()
        pivot = pivot.rename(columns=month_lookup)
        for label in month_labels:
            if label not in pivot.columns:
                pivot[label] = 0
        return pivot[["Category", "Source", *month_labels]]

    regular_categories = frame["Category"].ne("Flag")
    credit_rows = frame["Credit"] > 0
    debit_rows = frame["Debit"] > 0
    flagged_rows = frame["Flag"].ne("")

    credit_count = _pivot_metric("Credit", regular_categories & credit_rows, "count")
    debit_count = _pivot_metric("Debit", regular_categories & debit_rows, "count")
    credit_amount = _pivot_metric("Credit", regular_categories & credit_rows, "sum")
    debit_amount = _pivot_metric("Debit", regular_categories & debit_rows, "sum")

    flag_rows = frame.loc[flagged_rows, ["MonthKey", "Credit", "Debit"]].copy()
    if not flag_rows.empty:
        flag_agg = flag_rows.groupby("MonthKey", dropna=False).agg(
            CreditCount=("Credit", lambda s: int((s.fillna(0) > 0).sum())),
            DebitCount=("Debit", lambda s: int((s.fillna(0) > 0).sum())),
            CreditAmount=("Credit", lambda s: float(s.fillna(0).sum())),
            DebitAmount=("Debit", lambda s: float(s.fillna(0).sum())),
        )
        flag_row_count = {"Category": "Flag", "Source": ""}
        flag_row_debit_count = {"Category": "Flag", "Source": ""}
        flag_row_credit_amt = {"Category": "Flag", "Source": ""}
        flag_row_debit_amt = {"Category": "Flag", "Source": ""}
        for month_key, label in month_lookup.items():
            flag_row_count[label] = int(flag_agg.loc[month_key, "CreditCount"]) if month_key in flag_agg.index else 0
            flag_row_debit_count[label] = int(flag_agg.loc[month_key, "DebitCount"]) if month_key in flag_agg.index else 0
            flag_row_credit_amt[label] = float(flag_agg.loc[month_key, "CreditAmount"]) if month_key in flag_agg.index else 0
            flag_row_debit_amt[label] = float(flag_agg.loc[month_key, "DebitAmount"]) if month_key in flag_agg.index else 0

        flag_credit_count = pd.DataFrame([flag_row_count])
        flag_debit_count = pd.DataFrame([flag_row_debit_count])
        flag_credit_amount = pd.DataFrame([flag_row_credit_amt])
        flag_debit_amount = pd.DataFrame([flag_row_debit_amt])

        def _append_flag_row(table: pd.DataFrame) -> pd.DataFrame:
            table = table.copy()
            for label in month_labels:
                if label not in table.columns:
                    table[label] = 0
            ordered = table[["Category", "Source", *month_labels]] if not table.empty else pd.DataFrame(columns=["Category", "Source", *month_labels])
            return ordered

        credit_count = pd.concat([_append_flag_row(credit_count), flag_credit_count], ignore_index=True, sort=False)
        debit_count = pd.concat([_append_flag_row(debit_count), flag_debit_count], ignore_index=True, sort=False)
        credit_amount = pd.concat([_append_flag_row(credit_amount), flag_credit_amount], ignore_index=True, sort=False)
        debit_amount = pd.concat([_append_flag_row(debit_amount), flag_debit_amount], ignore_index=True, sort=False)

    def _sort_table(table: pd.DataFrame) -> pd.DataFrame:
        if table.empty:
            return table

        table = table.copy()
        table["_rank"] = table["Category"].map(lambda value: 2 if value == "Flag" else (1 if value == "Others" else 0))
        table["_source_sort"] = table["Source"].fillna("").astype(str)
        table = table.sort_values(["_rank", "Category", "_source_sort"], kind="stable").drop(columns=["_rank", "_source_sort"])
        return table.reset_index(drop=True)

    return {
        "month_keys": month_keys,
        "month_labels": month_labels,
        "credit_count": _sort_table(credit_count),
        "debit_count": _sort_table(debit_count),
        "credit_amount": _sort_table(credit_amount),
        "debit_amount": _sort_table(debit_amount),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MAIN REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_report(
    transactions: List[Dict[str, Any]],
    output_path: str,
    user_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate 5-sheet ICICI transaction report.

    Args:
        transactions: List of transaction dicts from the parser.
                      Keys: date, description, ref_no, value_date, debit, credit, balance
        output_path: Full path to output Excel file.
        user_info: Optional dict with full_name, account_type, bank_name.

    Returns:
        Dict with stats about the generated report.
    """
    logger.info("Report generator: building DataFrame from %d transactions", len(transactions))

    # ── STEP 1: Build DataFrame ──────────────────────────────────────────────
    df = pd.DataFrame(transactions)

    # Normalize column names
    col_map = {
        "date": "Date",
        "description": "Description",
        "narration": "Description",
        "ref_no": "RefNo",
        "value_date": "ValueDate",
        "debit": "Debit",
        "credit": "Credit",
        "withdrawal": "Debit",
        "deposit": "Credit",
        "balance": "Balance",
        "closing_balance": "Balance",
        "withdrawals": "Debit",
        "deposits": "Credit",
        "chq_no": "RefNo",
        "mode": "RefNo",
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

    # Ensure required columns exist
    for col in ["Date", "Description", "Debit", "Credit", "Balance"]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Clean data types
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed", errors="coerce")
    df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
    df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)
    df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")
    df["Description"] = df["Description"].fillna("").astype(str).str.strip()

    # Drop rows with no valid date
    df = df[df["Date"].notna()].reset_index(drop=True)

    # ── STEP 2: Validation Gate ──────────────────────────────────────────────
    both_set = df[(df["Debit"] > 0) & (df["Credit"] > 0)]
    if len(both_set) > 0:
        logger.warning("VALIDATION: %d rows have both Debit and Credit set", len(both_set))

    # Drop memo lines (both zero)
    df = df[~((df["Debit"] == 0) & (df["Credit"] == 0))].reset_index(drop=True)

    logger.info("Report generator: %d valid transactions after cleaning", len(df))

    # ── STEP 3: Classify ─────────────────────────────────────────────────────
    results = df.apply(classify, axis=1)
    df["Category"]   = [r["display_category"]  for r in results]
    df["Confidence"] = [r["confidence_score"]   for r in results]

    # ── STEP 3b: Salaried filter — no business categories ────────────────────
    if (user_info or {}).get("account_type", "").lower() == "salaried":
        df.loc[(df["Category"] == "Business Income") & (df["Credit"] > 0), "Category"] = "Bank Transfer"
        df.loc[(df["Category"] == "Business Expense") & (df["Debit"] > 0), "Category"] = "Transfer Out"
        logger.info("Salaried account: remapped Business Income/Expense to generic transfers")

    # ── STEP 4: Detect Recurring ─────────────────────────────────────────────
    df = detect_recurring(df)

    # ── STEP 5: Compute Aggregations ─────────────────────────────────────────
    df["Month"] = df["Date"].dt.to_period("M")
    months = sorted(df["Month"].unique())

    # Monthly aggregations
    monthly = {}
    for m in months:
        mdf = df[df["Month"] == m]
        monthly[m] = {
            "credit_count": int((mdf["Credit"] > 0).sum()),
            "credit_amount": float(mdf["Credit"].sum()),
            "debit_count": int((mdf["Debit"] > 0).sum()),
            "debit_amount": float(mdf["Debit"].sum()),
            "avg_balance": float(mdf["Balance"].mean()) if len(mdf) > 0 else 0,
            "min_balance": float(mdf["Balance"].min()) if len(mdf) > 0 else 0,
            "max_balance": float(mdf["Balance"].max()) if len(mdf) > 0 else 0,
            "start_balance": float(mdf.iloc[0]["Balance"]) if len(mdf) > 0 else 0,
            "end_balance": float(mdf.iloc[-1]["Balance"]) if len(mdf) > 0 else 0,
        }

    # Category aggregations with dynamic category discovery
    credit_df = df[df["Credit"] > 0]
    debit_df = df[df["Debit"] > 0]
    
    # Get all categories that actually appear in the data
    classifier = get_classifier()
    all_categories = classifier.get_all_categories()
    
    # Build credit categories (only include categories with data)
    credit_cats = {}
    for cat in all_categories["credit"]:
        cdf = credit_df[credit_df["Category"] == cat]
        if len(cdf) > 0:  # Only include if there are transactions
            credit_cats[cat] = {"amount": float(cdf["Credit"].sum()), "count": len(cdf)}
    
    # Add any other credit categories found in data but not in predefined list
    for cat in credit_df["Category"].unique():
        if cat not in credit_cats:
            cdf = credit_df[credit_df["Category"] == cat]
            credit_cats[cat] = {"amount": float(cdf["Credit"].sum()), "count": len(cdf)}

    # Build debit categories (only include categories with data)
    debit_cats = {}
    for cat in all_categories["debit"]:
        ddf = debit_df[debit_df["Category"] == cat]
        if len(ddf) > 0:  # Only include if there are transactions
            debit_cats[cat] = {"amount": float(ddf["Debit"].sum()), "count": len(ddf)}
    
    # Add any other debit categories found in data but not in predefined list
    for cat in debit_df["Category"].unique():
        if cat not in debit_cats:
            ddf = debit_df[debit_df["Category"] == cat]
            debit_cats[cat] = {"amount": float(ddf["Debit"].sum()), "count": len(ddf)}

    # Weekly aggregations (5-day gap)
    df["WeekBucket"] = df["Date"].apply(get_week_bucket)
    week_order = [
        "Week 1 (1-5)", "Week 2 (6-10)", "Week 3 (11-15)",
        "Week 4 (16-20)", "Week 5 (21-25)", "Week 6 (26-end)",
    ]

    weekly_credit = {}
    weekly_debit = {}
    for w in week_order:
        wc = df[(df["WeekBucket"] == w) & (df["Credit"] > 0)]
        wd = df[(df["WeekBucket"] == w) & (df["Debit"] > 0)]
        weekly_credit[w] = {"amount": float(wc["Credit"].sum()), "count": len(wc)}
        weekly_debit[w] = {"amount": float(wd["Debit"].sum()), "count": len(wd)}

    # Monthly-weekly aggregations for MOM in Weekly Analysis
    monthly_weekly_credit = {}
    monthly_weekly_debit = {}
    for m in months:
        mdf = df[df["Month"] == m]
        monthly_weekly_credit[m] = {}
        monthly_weekly_debit[m] = {}
        for w in week_order:
            wc = mdf[(mdf["WeekBucket"] == w) & (mdf["Credit"] > 0)]
            wd = mdf[(mdf["WeekBucket"] == w) & (mdf["Debit"] > 0)]
            monthly_weekly_credit[m][w] = {"amount": float(wc["Credit"].sum()), "count": len(wc)}
            monthly_weekly_debit[m][w] = {"amount": float(wd["Debit"].sum()), "count": len(wd)}

    # Cheque detection via description matching
    def _is_cheque(desc: str) -> bool:
        desc_lower = desc.lower()
        return any(tok in desc_lower for tok in CHEQUE_TOKENS)

    df["IsCheque"] = df["Description"].apply(_is_cheque)

    # Recurring aggregations
    rec_credit = df[(df["Credit"] > 0) & (df["Recurring"] == "Yes")]
    nonrec_credit = df[(df["Credit"] > 0) & (df["Recurring"] == "No")]
    rec_debit = df[(df["Debit"] > 0) & (df["Recurring"] == "Yes")]
    nonrec_debit = df[(df["Debit"] > 0) & (df["Recurring"] == "No")]

    # ── STEP 6: Write Excel with xlsxwriter ──────────────────────────────────
    logger.info("Report generator: writing Excel to %s", output_path)

    writer = pd.ExcelWriter(output_path, engine="xlsxwriter")
    workbook = writer.book

    # ── FORMAT DEFINITIONS ───────────────────────────────────────────────────
    fmt_header = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#1F4E79", "font_color": "#FFFFFF",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_header_blue = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#2E75B6", "font_color": "#FFFFFF",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_label = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "align": "left", "valign": "vcenter", "border": 1,
    })
    fmt_text = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "align": "left", "valign": "vcenter", "border": 1,
    })
    fmt_currency = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": u"\u20B9#,##0.00",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_currency_bold = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "num_format": u"\u20B9#,##0.00",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_integer = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": "#,##0",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_total = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#D9E1F2",
        "num_format": u"\u20B9#,##0.00",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_total_count = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#D9E1F2",
        "num_format": "#,##0",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_total_label = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#D9E1F2",
        "align": "left", "valign": "vcenter", "border": 1,
    })
    fmt_date = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": "dd/mm/yyyy",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_percent = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": '0.0"%"',
        "align": "center", "valign": "vcenter", "border": 1,
    })
    
    # ── NEW PROFESSIONAL FORMATS ─────────────────────────────────────────────
    fmt_header_pink = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#FF99CC", "font_color": "#000000",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_wk_section = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 11,
        "bg_color": "#203764", "font_color": "#FFFFFF",
        "align": "left", "valign": "vcenter", "border": 1,
    })
    fmt_wk_mom_positive = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": u"\u20B9#,##0.00",
        "bg_color": "#C6EFCE", "font_color": "#006100",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_wk_mom_negative = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": u"\u20B9#,##0.00",
        "bg_color": "#FFC7CE", "font_color": "#9C0006",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_wk_pct_positive = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": '+0.0"%"',
        "bg_color": "#C6EFCE", "font_color": "#006100",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_wk_pct_negative = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": '0.0"%"',
        "bg_color": "#FFC7CE", "font_color": "#9C0006",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_wk_dash = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "align": "center", "valign": "vcenter", "border": 1,
    })

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 1 — Summary
    # ══════════════════════════════════════════════════════════════════════════
    ws1 = workbook.add_worksheet("Summary")

    # Header block
    ws1.set_column(0, 0, 24)
    ws1.set_column(1, 1, 22)

    ws1.write(0, 0, "Name", fmt_label)
    ws1.write(0, 1, (user_info or {}).get("full_name", ""), fmt_text)
    ws1.write(1, 0, "Account No", fmt_label)
    ws1.write(1, 1, "", fmt_text)
    ws1.write(2, 0, "Statement From", fmt_label)
    ws1.write_datetime(2, 1, df["Date"].min().to_pydatetime(), fmt_date)
    ws1.write(3, 0, "Statement To", fmt_label)
    ws1.write_datetime(3, 1, df["Date"].max().to_pydatetime(), fmt_date)

    # Monthly table header (row 5)
    ws1.write(5, 0, "", fmt_header)
    for ci, m in enumerate(months, 1):
        ws1.write(5, ci, m.strftime("%b %Y"), fmt_header)
        ws1.set_column(ci, ci, 18)

    # Monthly data rows
    row_labels = [
        ("Total Credit Count", "credit_count", fmt_integer),
        ("Total Credit Amount", "credit_amount", fmt_currency),
        ("Total Debit Count", "debit_count", fmt_integer),
        ("Total Debit Amount", "debit_amount", fmt_currency),
        ("Avg Balance", "avg_balance", fmt_currency),
        ("Min Balance", "min_balance", fmt_currency),
        ("Max Balance", "max_balance", fmt_currency),
        ("Start of Month Balance", "start_balance", fmt_currency),
        ("End of Month Balance", "end_balance", fmt_currency),
    ]

    for ri, (label, key, fmt) in enumerate(row_labels, 6):
        ws1.write(ri, 0, label, fmt_label)
        for ci, m in enumerate(months, 1):
            ws1.write(ri, ci, monthly[m][key], fmt)

    summary_row = 6 + len(row_labels)  # next row after data rows

    # ── Total Cheque row ─────────────────────────────────────────────────────
    ws1.write(summary_row, 0, "Total Cheque", fmt_label)
    for ci, m in enumerate(months, 1):
        mdf = df[(df["Month"] == m) & (df["IsCheque"])]
        ws1.write(summary_row, ci, len(mdf), fmt_integer)
    summary_row += 1

    # ── Top 5 credit amt ─────────────────────────────────────────────────────
    ws1.write(summary_row, 0, "Top 5 credit amt", fmt_label)
    for ci, m in enumerate(months, 1):
        mdf = df[(df["Month"] == m) & (df["Credit"] > 0)]
        top5_amt = float(mdf.nlargest(5, "Credit")["Credit"].sum()) if len(mdf) > 0 else 0.0
        ws1.write(summary_row, ci, top5_amt, fmt_currency)
    summary_row += 1

    # ── Top 5 credit % ───────────────────────────────────────────────────────
    ws1.write(summary_row, 0, "Top 5 credit %", fmt_label)
    for ci, m in enumerate(months, 1):
        mdf = df[(df["Month"] == m) & (df["Credit"] > 0)]
        total_cr = float(mdf["Credit"].sum())
        top5_amt = float(mdf.nlargest(5, "Credit")["Credit"].sum()) if len(mdf) > 0 else 0.0
        pct = (top5_amt / total_cr * 100) if total_cr > 0 else 0.0
        ws1.write(summary_row, ci, round(pct, 1), fmt_percent)
    summary_row += 1

    # ── Top 5 debit amt ──────────────────────────────────────────────────────
    ws1.write(summary_row, 0, "Top 5 debit amt", fmt_label)
    for ci, m in enumerate(months, 1):
        mdf = df[(df["Month"] == m) & (df["Debit"] > 0)]
        top5_amt = float(mdf.nlargest(5, "Debit")["Debit"].sum()) if len(mdf) > 0 else 0.0
        ws1.write(summary_row, ci, top5_amt, fmt_currency)
    summary_row += 1

    # ── top 5 debit % ────────────────────────────────────────────────────────
    ws1.write(summary_row, 0, "top 5 debit %", fmt_label)
    for ci, m in enumerate(months, 1):
        mdf = df[(df["Month"] == m) & (df["Debit"] > 0)]
        total_db = float(mdf["Debit"].sum())
        top5_amt = float(mdf.nlargest(5, "Debit")["Debit"].sum()) if len(mdf) > 0 else 0.0
        pct = (top5_amt / total_db * 100) if total_db > 0 else 0.0
        ws1.write(summary_row, ci, round(pct, 1), fmt_percent)
    summary_row += 1

    # ── cnt of cheque bounces ────────────────────────────────────────────────
    ws1.write(summary_row, 0, "cnt of cheque bounces", fmt_label)
    for ci, m in enumerate(months, 1):
        mdf = df[(df["Month"] == m)]
        bounce_count = len(mdf[mdf["Description"].str.lower().str.contains("cheque bounce|chq bounce|clg return|chq return", regex=True, na=False)])
        ws1.write(summary_row, ci, bounce_count, fmt_integer)
    summary_row += 1

    # ── Salary credit rows (only for salaried accounts) ──────────────────────
    is_salaried = (user_info or {}).get("account_type", "").lower() == "salaried"
    if is_salaried:
        # salary credit count
        ws1.write(summary_row, 0, "salary credit count", fmt_label)
        for ci, m in enumerate(months, 1):
            mdf = df[(df["Month"] == m) & (df["Category"] == "Salary") & (df["Credit"] > 0)]
            ws1.write(summary_row, ci, len(mdf), fmt_integer)
        summary_row += 1

        # salary credit amt
        ws1.write(summary_row, 0, "salary credit amt", fmt_label)
        for ci, m in enumerate(months, 1):
            mdf = df[(df["Month"] == m) & (df["Category"] == "Salary") & (df["Credit"] > 0)]
            ws1.write(summary_row, ci, float(mdf["Credit"].sum()), fmt_currency)
        summary_row += 1

    # ── EOD Balance rows ─────────────────────────────────────────────────────
    eod_rows = [
        ("Min EOD Balance", "min_balance"),
        ("Max EOD Balance", "max_balance"),
        ("Average EOD Balance", "avg_balance"),
    ]
    for label, key in eod_rows:
        ws1.write(summary_row, 0, label, fmt_label)
        for ci, m in enumerate(months, 1):
            ws1.write(summary_row, ci, monthly[m][key], fmt_currency)
        summary_row += 1

    # Balance on specific days
    balance_days = [1, 5, 10, 15, 20, 25]
    for bd in balance_days:
        ws1.write(summary_row, 0, f"Balance on {bd}{'st' if bd == 1 else 'th'}", fmt_label)
        for ci, m in enumerate(months, 1):
            mdf = df[df["Month"] == m]
            day_txns = mdf[mdf["Date"].dt.day <= bd]
            bal = float(day_txns.iloc[-1]["Balance"]) if len(day_txns) > 0 else 0.0
            ws1.write(summary_row, ci, bal, fmt_currency)
        summary_row += 1

    # Balance on last day
    ws1.write(summary_row, 0, "Balance on last day", fmt_label)
    for ci, m in enumerate(months, 1):
        ws1.write(summary_row, ci, monthly[m]["end_balance"], fmt_currency)
    summary_row += 1

    # ── Total/Average column ─────────────────────────────────────────────────
    total_col = len(months) + 1
    ws1.set_column(total_col, total_col, 14)

    fmt_header_total = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#203764", "font_color": "#FFFFFF",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    ws1.write(5, total_col, "Total/\nAverage", fmt_header_total)

    # Total/Average for the standard monthly rows
    total_avg_config = [
        ("credit_count", "sum", fmt_integer),
        ("credit_amount", "sum", fmt_currency),
        ("debit_count", "sum", fmt_integer),
        ("debit_amount", "sum", fmt_currency),
        ("avg_balance", "avg", fmt_currency),
        ("min_balance", "min", fmt_currency),
        ("max_balance", "max", fmt_currency),
        ("start_balance", "first", fmt_currency),
        ("end_balance", "last", fmt_currency),
    ]
    for ri, (key, agg_type, fmt) in enumerate(total_avg_config, 6):
        vals = [monthly[m][key] for m in months]
        if agg_type == "sum":
            ws1.write(ri, total_col, sum(vals), fmt)
        elif agg_type == "avg":
            ws1.write(ri, total_col, sum(vals) / len(vals) if vals else 0, fmt)
        elif agg_type == "min":
            ws1.write(ri, total_col, min(vals) if vals else 0, fmt)
        elif agg_type == "max":
            ws1.write(ri, total_col, max(vals) if vals else 0, fmt)
        elif agg_type == "first":
            ws1.write(ri, total_col, vals[0] if vals else 0, fmt)
        elif agg_type == "last":
            ws1.write(ri, total_col, vals[-1] if vals else 0, fmt)

    ws1.set_row(5, 20)
    ws1.freeze_panes(6, 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 2 — Monthly Analysis
    # ══════════════════════════════════════════════════════════════════════════
    ws2 = workbook.add_worksheet("Monthly Analysis")

    fmt_section_title = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 12,
        "bg_color": "#1F4E79", "font_color": "#FFFFFF",
        "align": "left", "valign": "vcenter", "border": 1,
    })
    fmt_mom_positive = workbook.add_format({
        "font_name": "Arial", "font_size": 10, "num_format": u"\u20B9#,##0.00",
        "font_color": "#006100", "bg_color": "#C6EFCE",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_mom_negative = workbook.add_format({
        "font_name": "Arial", "font_size": 10, "num_format": u"-\u20B9#,##0.00",
        "font_color": "#9C0006", "bg_color": "#FFC7CE",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_pct_positive = workbook.add_format({
        "font_name": "Arial", "font_size": 10, "num_format": '0.0"%"',
        "font_color": "#006100", "bg_color": "#C6EFCE",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_pct_negative = workbook.add_format({
        "font_name": "Arial", "font_size": 10, "num_format": '0.0"%"',
        "font_color": "#9C0006", "bg_color": "#FFC7CE",
        "align": "center", "valign": "vcenter", "border": 1,
    })

    months_list = sorted(list(monthly.keys()))
    all_credit_cats = sorted(list(credit_cats.keys()))
    all_debit_cats = sorted(list(debit_cats.keys()))

    ws2.set_column(0, 0, 30)
    for i in range(len(months_list)):
        ws2.set_column(i+1, i+1, 18)

    ws2.write(0, 0, "Metric / Category", fmt_header)
    for i, m in enumerate(months_list):
        ws2.write(0, i+1, m.strftime("%b %Y"), fmt_header)

    row = 1

    # ── CREDIT ANALYSIS ──
    ws2.merge_range(row, 0, row, len(months_list), "CREDIT ANALYSIS", fmt_section_title)
    row += 1
    for cat in all_credit_cats:
        ws2.write(row, 0, cat, fmt_label)
        for i, m in enumerate(months_list):
            mdf = df[(df["Month"] == m) & (df["Category"] == cat) & (df["Credit"] > 0)]
            ws2.write(row, i+1, float(mdf["Credit"].sum()) if len(mdf) > 0 else 0.0, fmt_currency)
        row += 1

    ws2.write(row, 0, "Total Credit Count", fmt_label)
    for i, m in enumerate(months_list): ws2.write(row, i+1, monthly[m]["credit_count"], fmt_integer)
    row += 1
    ws2.write(row, 0, "Total Credit Amount", fmt_label)
    for i, m in enumerate(months_list): ws2.write(row, i+1, monthly[m]["credit_amount"], fmt_currency)
    row += 1

    ws2.write(row, 0, "MoM Credit Change", fmt_label)
    ws2.write(row+1, 0, "MoM Credit %", fmt_label)
    prev_cr = None
    for i, m in enumerate(months_list):
        cur = monthly[m]["credit_amount"]
        if prev_cr is not None:
            ch = cur - prev_cr
            pc = (ch / prev_cr * 100) if prev_cr != 0 else 0
            ws2.write(row, i+1, ch, fmt_mom_positive if ch >= 0 else fmt_mom_negative)
            ws2.write(row+1, i+1, pc, fmt_pct_positive if pc >= 0 else fmt_pct_negative)
        else:
            ws2.write(row, i+1, 0.0, fmt_mom_positive)
            ws2.write(row+1, i+1, 0.0, fmt_pct_positive)
        prev_cr = cur
    row += 3

    # ── DEBIT ANALYSIS ──
    ws2.merge_range(row, 0, row, len(months_list), "DEBIT ANALYSIS", fmt_section_title)
    row += 1
    for cat in all_debit_cats:
        ws2.write(row, 0, cat, fmt_label)
        for i, m in enumerate(months_list):
            mdf = df[(df["Month"] == m) & (df["Category"] == cat) & (df["Debit"] > 0)]
            ws2.write(row, i+1, float(mdf["Debit"].sum()) if len(mdf) > 0 else 0.0, fmt_currency)
        row += 1

    ws2.write(row, 0, "Total Debit Count", fmt_label)
    for i, m in enumerate(months_list): ws2.write(row, i+1, monthly[m]["debit_count"], fmt_integer)
    row += 1
    ws2.write(row, 0, "Total Debit Amount", fmt_label)
    for i, m in enumerate(months_list): ws2.write(row, i+1, monthly[m]["debit_amount"], fmt_currency)
    row += 1

    ws2.write(row, 0, "MoM Debit Change", fmt_label)
    ws2.write(row+1, 0, "MoM Debit %", fmt_label)
    prev_db = None
    for i, m in enumerate(months_list):
        cur = monthly[m]["debit_amount"]
        if prev_db is not None:
            ch = cur - prev_db
            pc = (ch / prev_db * 100) if prev_db != 0 else 0
            ws2.write(row, i+1, ch, fmt_mom_positive if ch >= 0 else fmt_mom_negative)
            ws2.write(row+1, i+1, pc, fmt_pct_positive if pc >= 0 else fmt_pct_negative)
        else:
            ws2.write(row, i+1, 0.0, fmt_mom_positive)
            ws2.write(row+1, i+1, 0.0, fmt_pct_positive)
        prev_db = cur
    row += 3

    # ── CHEQUE ANALYSIS ──
    ws2.merge_range(row, 0, row, len(months_list), "CHEQUE ANALYSIS", fmt_section_title)
    row += 1
    for label, direction, mtype in [
        ("Total No. of Cheque Deposits", "credit", "count"),
        ("Total Amount of Cheque Deposits", "credit", "amount"),
        ("Total No. of Cheque Issues", "debit", "count"),
        ("Total Amount of Cheque Issues", "debit", "amount"),
    ]:
        ws2.write(row, 0, label, fmt_label)
        for i, m in enumerate(months_list):
            if direction == "credit":
                mdf = df[(df["Month"] == m) & (df["IsCheque"]) & (df["Credit"] > 0)]
                ws2.write(row, i+1, len(mdf) if mtype == "count" else float(mdf["Credit"].sum()),
                          fmt_integer if mtype == "count" else fmt_currency)
            else:
                mdf = df[(df["Month"] == m) & (df["IsCheque"]) & (df["Debit"] > 0)]
                ws2.write(row, i+1, len(mdf) if mtype == "count" else float(mdf["Debit"].sum()),
                          fmt_integer if mtype == "count" else fmt_currency)
        row += 1

    ws2.freeze_panes(1, 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 3 — Weekly Analysis (5-day gap + MOM)
    # ══════════════════════════════════════════════════════════════════════════
    ws3 = workbook.add_worksheet("Weekly Analysis")

    # -- Additional MOM formats for weekly sheet --
    fmt_wk_mom_positive = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": u"\u20B9#,##0.00",
        "font_color": "#006100", "bg_color": "#C6EFCE",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_wk_mom_negative = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": u"-\u20B9#,##0.00",
        "font_color": "#9C0006", "bg_color": "#FFC7CE",
        "align": "right", "valign": "vcenter", "border": 1,
    })
    fmt_wk_pct_positive = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": '0.0"%"',
        "font_color": "#006100", "bg_color": "#C6EFCE",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_wk_pct_negative = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "num_format": '0.0"%"',
        "font_color": "#9C0006", "bg_color": "#FFC7CE",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_wk_section = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 12,
        "bg_color": "#1F4E79", "font_color": "#FFFFFF",
        "align": "left", "valign": "vcenter", "border": 1,
    })
    fmt_wk_dash = workbook.add_format({
        "font_name": "Arial", "font_size": 10,
        "align": "center", "valign": "vcenter", "border": 1,
    })

    ws3.set_column(0, 0, 22)
    ws3.set_column(1, 1, 18)
    ws3.set_column(2, 2, 14)
    ws3.set_column(3, 3, 3)  # spacer
    ws3.set_column(4, 4, 22)
    ws3.set_column(5, 5, 18)
    ws3.set_column(6, 6, 14)

    num_weeks = len(week_order)  # 6 weeks
    total_row = num_weeks + 1    # row after all week rows

    # LEFT — Credit
    ws3.write(0, 0, "Week", fmt_header)
    ws3.write(0, 1, "Credit Amount", fmt_header)
    ws3.write(0, 2, "Credit Count", fmt_header)

    total_wc_amt = 0
    total_wc_cnt = 0
    for ri, w in enumerate(week_order, 1):
        ws3.write(ri, 0, w, fmt_label)
        ws3.write(ri, 1, weekly_credit[w]["amount"], fmt_currency)
        ws3.write(ri, 2, weekly_credit[w]["count"], fmt_integer)
        total_wc_amt += weekly_credit[w]["amount"]
        total_wc_cnt += weekly_credit[w]["count"]

    ws3.write(total_row, 0, "Total", fmt_total_label)
    ws3.write(total_row, 1, total_wc_amt, fmt_total)
    ws3.write(total_row, 2, total_wc_cnt, fmt_total_count)

    # RIGHT — Debit
    ws3.write(0, 4, "Week", fmt_header_blue)
    ws3.write(0, 5, "Debit Amount", fmt_header_blue)
    ws3.write(0, 6, "Debit Count", fmt_header_blue)

    total_wd_amt = 0
    total_wd_cnt = 0
    for ri, w in enumerate(week_order, 1):
        ws3.write(ri, 4, w, fmt_label)
        ws3.write(ri, 5, weekly_debit[w]["amount"], fmt_currency)
        ws3.write(ri, 6, weekly_debit[w]["count"], fmt_integer)
        total_wd_amt += weekly_debit[w]["amount"]
        total_wd_cnt += weekly_debit[w]["count"]

    ws3.write(total_row, 4, "Total", fmt_total_label)
    ws3.write(total_row, 5, total_wd_amt, fmt_total)
    ws3.write(total_row, 6, total_wd_cnt, fmt_total_count)

    # ── MOM (Month over Month) Weekly Analysis ───────────────────────────────
    mom_start_row = total_row + 3  # leave a gap
    months_list_wk = sorted(list(monthly.keys()))

    # Section header
    mom_cols = len(months_list_wk) + 1
    ws3.merge_range(mom_start_row, 0, mom_start_row, mom_cols,
                    "MONTH OVER MONTH — WEEKLY CREDIT", fmt_wk_section)
    mom_start_row += 1

    # Column headers: Week | Month1 | Month2 | ...
    ws3.write(mom_start_row, 0, "Week", fmt_header)
    for i, m in enumerate(months_list_wk):
        ws3.write(mom_start_row, i + 1, m.strftime("%b %Y"), fmt_header)
        ws3.set_column(i + 1, i + 1, 18)
    mom_start_row += 1

    for w in week_order:
        ws3.write(mom_start_row, 0, w, fmt_label)
        for i, m in enumerate(months_list_wk):
            ws3.write(mom_start_row, i + 1, monthly_weekly_credit[m][w]["amount"], fmt_currency)
        mom_start_row += 1

    # MOM Credit change row
    ws3.write(mom_start_row, 0, "MoM Credit Change", fmt_label)
    prev_total = None
    for i, m in enumerate(months_list_wk):
        cur_total = sum(monthly_weekly_credit[m][w]["amount"] for w in week_order)
        if prev_total is not None:
            change = cur_total - prev_total
            ws3.write(mom_start_row, i + 1, change,
                      fmt_wk_mom_positive if change >= 0 else fmt_wk_mom_negative)
        else:
            ws3.write(mom_start_row, i + 1, "-", fmt_wk_dash)
        prev_total = cur_total
    mom_start_row += 1

    # MOM Credit % row
    ws3.write(mom_start_row, 0, "MoM Credit %", fmt_label)
    prev_total = None
    for i, m in enumerate(months_list_wk):
        cur_total = sum(monthly_weekly_credit[m][w]["amount"] for w in week_order)
        if prev_total is not None and prev_total != 0:
            pct = (cur_total - prev_total) / prev_total * 100
            ws3.write(mom_start_row, i + 1, pct,
                      fmt_wk_pct_positive if pct >= 0 else fmt_wk_pct_negative)
        else:
            ws3.write(mom_start_row, i + 1, "-", fmt_wk_dash)
        prev_total = cur_total
    mom_start_row += 2

    # ── MOM Debit section ────────────────────────────────────────────────────
    ws3.merge_range(mom_start_row, 0, mom_start_row, mom_cols,
                    "MONTH OVER MONTH — WEEKLY DEBIT", fmt_wk_section)
    mom_start_row += 1

    ws3.write(mom_start_row, 0, "Week", fmt_header_blue)
    for i, m in enumerate(months_list_wk):
        ws3.write(mom_start_row, i + 1, m.strftime("%b %Y"), fmt_header_blue)
    mom_start_row += 1

    for w in week_order:
        ws3.write(mom_start_row, 0, w, fmt_label)
        for i, m in enumerate(months_list_wk):
            ws3.write(mom_start_row, i + 1, monthly_weekly_debit[m][w]["amount"], fmt_currency)
        mom_start_row += 1

    # MOM Debit change row
    ws3.write(mom_start_row, 0, "MoM Debit Change", fmt_label)
    prev_total = None
    for i, m in enumerate(months_list_wk):
        cur_total = sum(monthly_weekly_debit[m][w]["amount"] for w in week_order)
        if prev_total is not None:
            change = cur_total - prev_total
            ws3.write(mom_start_row, i + 1, change,
                      fmt_wk_mom_positive if change >= 0 else fmt_wk_mom_negative)
        else:
            ws3.write(mom_start_row, i + 1, "-", fmt_wk_dash)
        prev_total = cur_total
    mom_start_row += 1

    # MOM Debit % row
    ws3.write(mom_start_row, 0, "MoM Debit %", fmt_label)
    prev_total = None
    for i, m in enumerate(months_list_wk):
        cur_total = sum(monthly_weekly_debit[m][w]["amount"] for w in week_order)
        if prev_total is not None and prev_total != 0:
            pct = (cur_total - prev_total) / prev_total * 100
            ws3.write(mom_start_row, i + 1, pct,
                      fmt_wk_pct_positive if pct >= 0 else fmt_wk_pct_negative)
        else:
            ws3.write(mom_start_row, i + 1, "-", fmt_wk_dash)
        prev_total = cur_total

    ws4 = workbook.add_worksheet("Category Analysis")

    # Credit categories to show (mapped from classifier)
    credit_cat_display = [
        ("UPI", ["UPI Transfer"]),
        ("Loan", ["Loan Disbursal"]),
        ("Salary Credits", ["Salary"]),
        ("Bank Transfer", ["Bank Transfer", "NEFT/RTGS/IMPS"]),
        ("Cash Deposit", ["Cash Deposit"]),
        ("Cheque Deposit", []),  # special: use IsCheque
        ("Others", []),  # special: remainder
    ]
    debit_cat_display = [
        ("Loan Payments", ["Loan Payment / EMI"]),
        ("ATM Withdrawal", ["ATM Withdrawal"]),
        ("Shopping", ["Shopping"]),
        ("Bill Payment", ["Bill Payment", "Bank Charges"]),
        ("Withdrawal", ["Transfer Out", "NEFT/RTGS/IMPS"]),
        ("Investments", ["Investment", "Fixed Deposit"]),
        ("Others", []),  # special: remainder
    ]

    ws4.set_column(0, 0, 22)
    ws4.set_column(1, 1, 16)
    ws4.set_column(2, 2, 10)
    ws4.set_column(3, 3, 3) # spacer
    ws4.set_column(4, 4, 22)
    ws4.set_column(5, 5, 16)
    ws4.set_column(6, 6, 10)

    # 1. Overall Category Summary
    ws4.write(0, 0, "Credit Category", fmt_header)
    ws4.write(0, 1, "Amount", fmt_header)
    ws4.write(0, 2, "Count", fmt_header)
    ws4.write(0, 4, "Debit Category", fmt_header_blue)
    ws4.write(0, 5, "Amount", fmt_header_blue)
    ws4.write(0, 6, "Count", fmt_header_blue)

    cr_row = 1
    known_cr_cats = set()
    total_cr_amt = 0
    total_cr_cnt = 0
    for display_name, cat_keys in credit_cat_display:
        if display_name == "Cheque Deposit":
            cdf = df[(df["IsCheque"]) & (df["Credit"] > 0)]
        elif display_name == "Others":
            cdf = df[(df["Credit"] > 0) & (~df["Category"].isin(known_cr_cats)) & (~df["IsCheque"])]
        else:
            cdf = df[(df["Category"].isin(cat_keys)) & (df["Credit"] > 0)]
            known_cr_cats.update(cat_keys)
        
        amt = float(cdf["Credit"].sum())
        cnt = len(cdf)
        ws4.write(cr_row, 0, display_name, fmt_label)
        ws4.write(cr_row, 1, amt, fmt_currency)
        ws4.write(cr_row, 2, cnt, fmt_integer)
        total_cr_amt += amt
        total_cr_cnt += cnt
        cr_row += 1
    
    ws4.write(cr_row, 0, "Total", fmt_total_label)
    ws4.write(cr_row, 1, total_cr_amt, fmt_total)
    ws4.write(cr_row, 2, total_cr_cnt, fmt_total_count)

    db_row = 1
    known_db_cats = set()
    total_db_amt = 0
    total_db_cnt = 0
    for display_name, cat_keys in debit_cat_display:
        if display_name == "Others":
            ddf = df[(df["Debit"] > 0) & (~df["Category"].isin(known_db_cats))]
        else:
            ddf = df[(df["Category"].isin(cat_keys)) & (df["Debit"] > 0)]
            known_db_cats.update(cat_keys)
        
        amt = float(ddf["Debit"].sum())
        cnt = len(ddf)
        ws4.write(db_row, 4, display_name, fmt_label)
        ws4.write(db_row, 5, amt, fmt_currency)
        ws4.write(db_row, 6, cnt, fmt_integer)
        total_db_amt += amt
        total_db_cnt += cnt
        db_row += 1

    ws4.write(db_row, 4, "Total", fmt_total_label)
    ws4.write(db_row, 5, total_db_amt, fmt_total)
    ws4.write(db_row, 6, total_db_cnt, fmt_total_count)

    # 2. Monthly Balance Summary
    tbl2_start = max(cr_row, db_row) + 3

    for i in range(len(months_list)):
        ws4.set_column(i+1, i+1, 16) 

    for i, m in enumerate(months_list):
        ws4.write(tbl2_start, i+1, m.strftime("%b %Y"), fmt_header)

    labels2 = [
        "Total credit cnt", "Total credit amt",
        "Total debit cnt", "Total debit amt",
        "Avg balance", "Min balance", "Max balance",
        "Start of month bal", "end of month bal"
    ]
    for r, label in enumerate(labels2):
        ws4.write(tbl2_start + 1 + r, 0, label, fmt_label)
        for i, m in enumerate(months_list):
            m_data = monthly[m]
            if label == "Total credit cnt":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["credit_count"], fmt_integer)
            elif label == "Total credit amt":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["credit_amount"], fmt_currency)
            elif label == "Total debit cnt":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["debit_count"], fmt_integer)
            elif label == "Total debit amt":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["debit_amount"], fmt_currency)
            elif label == "Avg balance":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["avg_balance"], fmt_currency)
            elif label == "Min balance":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["min_balance"], fmt_currency)
            elif label == "Max balance":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["max_balance"], fmt_currency)
            elif label == "Start of month bal":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["start_balance"], fmt_currency)
            elif label == "end of month bal":
                ws4.write(tbl2_start + 1 + r, i+1, m_data["end_balance"], fmt_currency)

    # 3. Credit Categories per month
    tbl3_start = tbl2_start + 1 + len(labels2) + 2

    ws4.write(tbl3_start, 0, "", fmt_header)
    ws4.write(tbl3_start+1, 0, "Credit Category", fmt_header)
    for i, m in enumerate(months_list):
        ws4.merge_range(tbl3_start, i*2+1, tbl3_start, i*2+2, m.strftime("%b %Y"), fmt_header)
        ws4.write(tbl3_start+1, i*2+1, "Amount", fmt_header)
        ws4.write(tbl3_start+1, i*2+2, "Count", fmt_header)
        ws4.set_column(i*2+1, i*2+2, 14)

    cr_row_m = tbl3_start + 2
    known_cr_cats = set()
    for display_name, cat_keys in credit_cat_display:
        ws4.write(cr_row_m, 0, display_name.lower(), fmt_label)
        for i, m in enumerate(months_list):
            if display_name == "Cheque Deposit":
                mdf = df[(df["Month"] == m) & (df["IsCheque"]) & (df["Credit"] > 0)]
            elif display_name == "Others":
                mdf = df[(df["Month"] == m) & (df["Credit"] > 0) & (~df["Category"].isin(known_cr_cats)) & (~df["IsCheque"])]
            else:
                mdf = df[(df["Month"] == m) & (df["Category"].isin(cat_keys)) & (df["Credit"] > 0)]
                known_cr_cats.update(cat_keys)
            
            ws4.write(cr_row_m, i*2+1, float(mdf["Credit"].sum()), fmt_currency)
            ws4.write(cr_row_m, i*2+2, len(mdf), fmt_integer)
        cr_row_m += 1

    ws4.write(cr_row_m, 0, "Total credit amt", fmt_total_label)
    for i, m in enumerate(months_list):
        ws4.write(cr_row_m, i*2+1, monthly[m]["credit_amount"], fmt_total)
        ws4.write(cr_row_m, i*2+2, monthly[m]["credit_count"], fmt_total_count)

    # 4. Debit Categories per month
    tbl4_start = cr_row_m + 3
    ws4.write(tbl4_start, 0, "", fmt_header_blue)
    ws4.write(tbl4_start+1, 0, "Debit Categories", fmt_header_blue)
    for i, m in enumerate(months_list):
        ws4.merge_range(tbl4_start, i*2+1, tbl4_start, i*2+2, m.strftime("%b %Y"), fmt_header_blue)
        ws4.write(tbl4_start+1, i*2+1, "Amount", fmt_header_blue)
        ws4.write(tbl4_start+1, i*2+2, "Count", fmt_header_blue)

    db_row_m = tbl4_start + 2
    known_db_cats = set()
    for display_name, cat_keys in debit_cat_display:
        # Match user's typo/naming from mockup where possible
        dname = display_name.lower()
        if dname == "loan payments": dname = "loanpayments"
        elif dname == "atm withdrawal": dname = "atm withdrawa"
        elif dname == "bill payment": dname = "billpayment"
        
        ws4.write(db_row_m, 0, dname, fmt_label)
        for i, m in enumerate(months_list):
            if display_name == "Others":
                mdf = df[(df["Month"] == m) & (df["Debit"] > 0) & (~df["Category"].isin(known_db_cats))]
            else:
                mdf = df[(df["Month"] == m) & (df["Category"].isin(cat_keys)) & (df["Debit"] > 0)]
                known_db_cats.update(cat_keys)
                
            ws4.write(db_row_m, i*2+1, float(mdf["Debit"].sum()), fmt_currency)
            ws4.write(db_row_m, i*2+2, len(mdf), fmt_integer)
        db_row_m += 1

    ws4.write(db_row_m, 0, "Total debit amt", fmt_total_label)
    for i, m in enumerate(months_list):
        ws4.write(db_row_m, i*2+1, monthly[m]["debit_amount"], fmt_total)
        ws4.write(db_row_m, i*2+2, monthly[m]["debit_count"], fmt_total_count)

    # 5. Weekly Credit and Debit side-by-side
    tbl5_start = db_row_m + 3
    ws4.write(tbl5_start, 0, "", fmt_header)
    for i, m in enumerate(months_list):
        ws4.write(tbl5_start, i+1, m.strftime("%b %Y"), fmt_header)

    wr = tbl5_start + 1
    for w in week_order:
        ws4.write(wr, 0, w, fmt_label)
        for i, m in enumerate(months_list):
            ws4.write(wr, i+1, monthly_weekly_credit[m][w]["amount"], fmt_currency)
        wr += 1
    ws4.write(wr, 0, "Total credit amt", fmt_total_label)
    for i, m in enumerate(months_list):
        ws4.write(wr, i+1, monthly[m]["credit_amount"], fmt_total)

    right_wk_start = (len(months_list) * 2) + 2
    ws4.write(tbl5_start, right_wk_start, "", fmt_header_blue)
    for i, m in enumerate(months_list):
        ws4.set_column(right_wk_start+1+i, right_wk_start+1+i, 16)
        ws4.write(tbl5_start, right_wk_start+1+i, m.strftime("%b %Y"), fmt_header_blue)
        
    wr2 = tbl5_start + 1
    for w in week_order:
        ws4.write(wr2, right_wk_start, w, fmt_label)
        for i, m in enumerate(months_list):
            ws4.write(wr2, right_wk_start+1+i, monthly_weekly_debit[m][w]["amount"], fmt_currency)
        wr2 += 1
    ws4.write(wr2, right_wk_start, "Total debit amt", fmt_total_label)
    for i, m in enumerate(months_list):
        ws4.write(wr2, right_wk_start+1+i, monthly[m]["debit_amount"], fmt_total)
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 5 — Bounces & Penal
    # ══════════════════════════════════════════════════════════════════════════
    ws5 = workbook.add_worksheet("Bounces & Penal")

    ws5.set_column(0, 0, 8)    # Sl. No.
    ws5.set_column(1, 1, 16)   # Bank Name
    ws5.set_column(2, 2, 20)   # Account Number
    ws5.set_column(3, 3, 14)   # Date
    ws5.set_column(4, 4, 14)   # Cheque No.
    ws5.set_column(5, 5, 55)   # Description
    ws5.set_column(6, 6, 16)   # Amount
    ws5.set_column(7, 7, 18)   # Category
    ws5.set_column(8, 8, 16)   # Balance

    bounce_headers = ["Sl. No.", "Bank Name", "Account Number", "Date",
                      "Cheque No.", "Description", "Amount", "Category", "Balance"]
    for ci, h in enumerate(bounce_headers):
        ws5.write(0, ci, h, fmt_header)

    # Filter bounce/penal transactions
    bounce_keywords = r"bounce|return|dishon|penalty|penal|charges.*chq|charges.*cheque|unpaid|ecs return"
    bounce_df = df[df["Description"].str.lower().str.contains(bounce_keywords, regex=True, na=False)].copy()
    bounce_df = bounce_df.sort_values("Date")

    bank_name = (user_info or {}).get("bank_name", "ICICI Bank")
    acct_num = (user_info or {}).get("account_number", "")

    for ri, (_, txn) in enumerate(bounce_df.iterrows()):
        rn = ri + 1
        ws5.write(rn, 0, rn, fmt_integer)
        ws5.write(rn, 1, bank_name, fmt_text)
        ws5.write(rn, 2, acct_num, fmt_text)
        if pd.notna(txn["Date"]):
            ws5.write_datetime(rn, 3, txn["Date"].to_pydatetime(), fmt_date)
        else:
            ws5.write(rn, 3, "", fmt_text)
        # Extract cheque number from description if present
        desc_lower = str(txn["Description"]).lower()
        chq_no = ""
        import re as _re
        chq_match = _re.search(r'(?:chq|cheque|clg)\s*(?:no\.?\s*)?(\d{6,})', desc_lower)
        if chq_match:
            chq_no = chq_match.group(1)
        ws5.write(rn, 4, chq_no, fmt_text)
        ws5.write(rn, 5, str(txn["Description"]), fmt_text)
        amt = txn["Debit"] if txn["Debit"] > 0 else txn["Credit"]
        ws5.write_number(rn, 6, amt, fmt_currency)
        ws5.write(rn, 7, str(txn["Category"]), fmt_text)
        ws5.write_number(rn, 8, txn["Balance"], fmt_currency)

    ws5.freeze_panes(1, 0)
    if len(bounce_df) > 0:
        ws5.autofilter(0, 0, len(bounce_df), len(bounce_headers) - 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 6 — Funds Received (Top 5 per month)
    # ══════════════════════════════════════════════════════════════════════════
    ws6 = workbook.add_worksheet("Funds Received")

    fmt_month_header = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 11,
        "bg_color": "#203764", "font_color": "#FFFFFF",
        "align": "center", "valign": "vcenter", "border": 1,
    })
    fmt_sub_header = workbook.add_format({
        "bold": True, "font_name": "Arial", "font_size": 10,
        "bg_color": "#D9E1F2", "font_color": "#000000",
        "align": "center", "valign": "vcenter", "border": 1,
    })

    ws6.set_column(0, 0, 14)   # Date
    ws6.set_column(1, 1, 45)   # Description
    ws6.set_column(2, 2, 18)   # Amount

    ws6.merge_range(0, 0, 0, 2, "Top 5 Funds Received", fmt_section_title)
    fr_row = 1

    for m in months_list:
        m_credits = df[(df["Month"] == m) & (df["Credit"] > 0)].nlargest(5, "Credit")
        ws6.merge_range(fr_row, 0, fr_row, 2, m.strftime("%b-%y"), fmt_month_header)
        fr_row += 1
        ws6.write(fr_row, 0, "Date", fmt_sub_header)
        ws6.write(fr_row, 1, "Description", fmt_sub_header)
        ws6.write(fr_row, 2, "Amount", fmt_sub_header)
        fr_row += 1
        for _, txn in m_credits.iterrows():
            if pd.notna(txn["Date"]):
                ws6.write_datetime(fr_row, 0, txn["Date"].to_pydatetime(), fmt_date)
            else:
                ws6.write(fr_row, 0, "", fmt_text)
            ws6.write(fr_row, 1, str(txn["Description"]), fmt_text)
            ws6.write_number(fr_row, 2, txn["Credit"], fmt_currency)
            fr_row += 1

    ws6.freeze_panes(1, 0)

    # SHEET 7 — Funds Remittance (Top 5 per month)
    # ══════════════════════════════════════════════════════════════════════════
    ws7 = workbook.add_worksheet("Funds Remittance")

    ws7.set_column(0, 0, 14)   # Date
    ws7.set_column(1, 1, 45)   # Description
    ws7.set_column(2, 2, 18)   # Amount

    ws7.merge_range(0, 0, 0, 2, "Top 5 Funds Remittances", fmt_section_title)
    fm_row = 1

    for m in months_list:
        m_debits = df[(df["Month"] == m) & (df["Debit"] > 0)].nlargest(5, "Debit")
        ws7.merge_range(fm_row, 0, fm_row, 2, m.strftime("%b-%y"), fmt_month_header)
        fm_row += 1
        ws7.write(fm_row, 0, "Date", fmt_sub_header)
        ws7.write(fm_row, 1, "Description", fmt_sub_header)
        ws7.write(fm_row, 2, "Amount", fmt_sub_header)
        fm_row += 1
        for _, txn in m_debits.iterrows():
            if pd.notna(txn["Date"]):
                ws7.write_datetime(fm_row, 0, txn["Date"].to_pydatetime(), fmt_date)
            else:
                ws7.write(fm_row, 0, "", fmt_text)
            ws7.write(fm_row, 1, str(txn["Description"]), fmt_text)
            ws7.write_number(fm_row, 2, txn["Debit"], fmt_currency)
            fm_row += 1

    ws7.freeze_panes(1, 0)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 8 — Raw Transaction
    # ══════════════════════════════════════════════════════════════════════════
    ws8 = workbook.add_worksheet("Raw Transaction")

    ws8.set_column(0, 0, 14)   # Date
    ws8.set_column(1, 1, 60)   # Description
    ws8.set_column(2, 2, 18)   # Debit
    ws8.set_column(3, 3, 18)   # Credit
    ws8.set_column(4, 4, 18)   # Balance
    ws8.set_column(5, 5, 22)   # Category
    ws8.set_column(6, 6, 14)   # Confidence
    ws8.set_column(7, 7, 13)   # Recurring

    raw_headers = ["Date", "Description", "Debit", "Credit", "Balance",
                   "Category", "Confidence", "Recurring"]
    for ci, h in enumerate(raw_headers):
        ws8.write(0, ci, h, fmt_header)

    for ri in range(len(df)):
        row_num = ri + 1
        r = df.iloc[ri]
        if pd.notna(r["Date"]):
            ws8.write_datetime(row_num, 0, r["Date"].to_pydatetime(), fmt_date)
        else:
            ws8.write(row_num, 0, "", fmt_text)
        ws8.write(row_num, 1, str(r["Description"]), fmt_text)
        if r["Debit"] > 0:
            ws8.write_number(row_num, 2, r["Debit"], fmt_currency)
        else:
            ws8.write(row_num, 2, "", fmt_text)
        if r["Credit"] > 0:
            ws8.write_number(row_num, 3, r["Credit"], fmt_currency)
        else:
            ws8.write(row_num, 3, "", fmt_text)
        ws8.write_number(row_num, 4, r["Balance"], fmt_currency)
        ws8.write(row_num, 5, str(r["Category"]), fmt_text)
        ws8.write_number(row_num, 6, int(r["Confidence"]), fmt_percent)
        ws8.write(row_num, 7, str(r["Recurring"]), fmt_text)
    ws8.freeze_panes(1, 0)
    ws8.autofilter(0, 0, len(df), len(raw_headers) - 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 9 — Source Analysis
    # ══════════════════════════════════════════════════════════════════════════
    source_df = _build_source_analysis_frame(df)
    source_df = source_df.sort_values(["Date", "Description"], kind="stable").reset_index(drop=True)

    ws9 = workbook.add_worksheet("Source Analysis")
    ws9.set_column(0, 0, 18)
    ws9.set_column(1, 1, 24)
    ws9.set_column(2, 2, 22)
    ws9.set_column(3, 3, 18)
    ws9.set_column(4, 4, 14)
    ws9.set_column(5, 5, 50)
    ws9.set_column(6, 6, 16)
    ws9.set_column(7, 7, 16)
    ws9.set_column(8, 8, 16)

    source_headers = [
        "Transaction Mode",
        "Source",
        "Identified Category",
        "Flag",
        "Date",
        "Description",
        "Credit",
        "Debit",
        "Balance",
    ]
    ws9.merge_range(0, 0, 0, len(source_headers) - 1, "SOURCE ANALYSIS", fmt_section_title)
    for ci, header in enumerate(source_headers):
        ws9.write(1, ci, header, fmt_header)

    for ri, row in enumerate(source_df.itertuples(index=False), 2):
        ws9.write(ri, 0, getattr(row, "TransactionMode", ""), fmt_text)
        ws9.write(ri, 1, getattr(row, "Source", ""), fmt_text)
        ws9.write(ri, 2, getattr(row, "IdentifiedCategory", ""), fmt_text)
        ws9.write(ri, 3, getattr(row, "Flag", ""), fmt_text)

        date_val = getattr(row, "Date", None)
        if pd.notna(date_val):
            ws9.write_datetime(ri, 4, date_val.to_pydatetime(), fmt_date)
        else:
            ws9.write(ri, 4, "", fmt_text)

        ws9.write(ri, 5, getattr(row, "Description", ""), fmt_text)

        credit = float(getattr(row, "Credit", 0) or 0)
        debit = float(getattr(row, "Debit", 0) or 0)
        balance = float(getattr(row, "Balance", 0) or 0)

        if credit > 0:
            ws9.write_number(ri, 6, credit, fmt_currency)
        else:
            ws9.write(ri, 6, "", fmt_text)

        if debit > 0:
            ws9.write_number(ri, 7, debit, fmt_currency)
        else:
            ws9.write(ri, 7, "", fmt_text)

        ws9.write_number(ri, 8, balance, fmt_currency)

    ws9.freeze_panes(2, 0)
    if len(source_df) > 0:
        ws9.autofilter(1, 0, len(source_df) + 1, len(source_headers) - 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 10 — Category Outcome
    # ══════════════════════════════════════════════════════════════════════════
    outcome_tables = _build_category_outcome_tables(source_df)
    month_labels = outcome_tables.get("month_labels", [])

    ws10 = workbook.add_worksheet("Category Outcome")
    ws10.set_column(0, 0, 22)
    ws10.set_column(1, 1, 24)
    for col_idx in range(2, 2 + len(month_labels)):
        ws10.set_column(col_idx, col_idx, 14)

    outcome_headers = ["Category", "Source", *month_labels]

    def _write_outcome_table(start_row: int, title: str, table_df: pd.DataFrame) -> int:
        end_col = len(outcome_headers) - 1
        ws10.merge_range(start_row, 0, start_row, end_col, title, fmt_section_title)
        header_row = start_row + 1
        for ci, header in enumerate(outcome_headers):
            ws10.write(header_row, ci, header, fmt_header)

        data_row = header_row + 1
        if table_df is None or table_df.empty:
            return data_row

        current_row = data_row
        category_order = []
        for category in table_df["Category"].fillna("").astype(str).tolist():
            if category not in category_order:
                category_order.append(category)

        for category in category_order:
            category_rows = table_df[table_df["Category"] == category].copy()
            if category_rows.empty:
                continue

            subtotal_values = {month_label: float(category_rows[month_label].fillna(0).sum()) for month_label in month_labels}

            ws10.write(current_row, 0, category or "Others", fmt_header)
            ws10.write(current_row, 1, "All Sources", fmt_header)
            for mi, month_label in enumerate(month_labels, 2):
                value = subtotal_values.get(month_label, 0)
                if "Amount" in title:
                    ws10.write_number(current_row, mi, float(value or 0), fmt_currency)
                else:
                    ws10.write_number(current_row, mi, int(float(value or 0)), fmt_integer)
            current_row += 1

            for _, row in category_rows.sort_values(["Source"], kind="stable").iterrows():
                ws10.write(current_row, 0, getattr(row, "Category", ""), fmt_text)
                ws10.write(current_row, 1, getattr(row, "Source", ""), fmt_text)
                for mi, month_label in enumerate(month_labels, 2):
                    value = row.get(month_label, 0)
                    if value:
                        if "Amount" in title:
                            ws10.write_number(current_row, mi, float(value), fmt_currency)
                        else:
                            ws10.write_number(current_row, mi, int(float(value)), fmt_integer)
                    else:
                        ws10.write_blank(
                            current_row,
                            mi,
                            None,
                            fmt_text,
                        )
                ws10.set_row(current_row, None, None, {"level": 1, "hidden": True})
                current_row += 1

        ws10.freeze_panes(2, 0)
        return current_row

    next_row = 0
    next_row = _write_outcome_table(next_row, "CATEGORY OUTCOME  Credit Count", outcome_tables.get("credit_count", pd.DataFrame()))
    next_row += 1
    next_row = _write_outcome_table(next_row, "CATEGORY OUTCOME  Debit Count", outcome_tables.get("debit_count", pd.DataFrame()))
    next_row += 1
    next_row = _write_outcome_table(next_row, "CATEGORY OUTCOME  Credit Amount", outcome_tables.get("credit_amount", pd.DataFrame()))
    next_row += 1
    _write_outcome_table(next_row, "CATEGORY OUTCOME  Debit Amount", outcome_tables.get("debit_amount", pd.DataFrame()))

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 11 — Finbit Analysis
    # ══════════════════════════════════════════════════════════════════════════
    ws11 = workbook.add_worksheet("Finbit")

    # Calculate opening balance from first transaction
    opening_balance = 0
    if len(df) > 0:
        first = df.iloc[0]
        opening_balance = first["Balance"] - first["Credit"] + first["Debit"]

    finbit_months, finbit_data = _compute_finbit_monthly(df, opening_balance)

    if finbit_months and finbit_data:
        ws11.merge_range(0, 0, 0, len(finbit_months), "FINBIT ANALYSIS", fmt_section_title)

        ws11.write(1, 0, "Metric", fmt_header)
        for ci, month_key in enumerate(finbit_months, 1):
            ws11.write(1, ci, month_key, fmt_header)

        FINBIT_ROWS = [
            ("monthlyAvgBal",     "Monthly Avg Balance",   True),
            ("maxBalance",        "Max Balance",           True),
            ("minBalance",        "Min Balance",           True),
            ("cashDeposit",       "Cash Deposits",         True),
            ("cashWithdrawals",   "Cash Withdrawals",      True),
            ("chqDeposit",        "Cheque Deposits",       True),
            ("chqIssues",         "Cheques Issued",        True),
            ("credits",           "Total Credits",         True),
            ("debits",            "Total Debits",          True),
            ("inwBounce",         "Inward Bounce",         False),
            ("outwBounce",        "Outward Bounce",        False),
            ("penaltyCharges",    "Penalty Charges",       True),
            ("ecsNach",           "ECS / NACH",            True),
            ("totalNetDebit",     "Total Net Debit",       True),
            ("totalNetCredit",    "Total Net Credit",      True),
            ("selfWithdraw",      "Self Withdrawal",       True),
            ("selfDeposit",       "Self Deposit",          True),
            ("loanRepayment",     "Loan Repayment",        True),
            ("loanCredit",        "Loan Credit",           True),
            ("creditCardPayment", "Credit Card Payment",   True),
            ("minCredits",        "Min Credit Amount",     True),
            ("maxCredits",        "Max Credit Amount",     True),
            ("salary",            "Salary",                True),
            ("bankCharges",       "Bank Charges",          True),
            None,
            ("balanceOpening",    "BALANCE (Opening)",     True),
            ("balanceClosing",    "BALANCE (Closing)",     True),
            ("salaryMonth",       "SALARY (Income/Month)", True),
            ("ccPayment",         "CCPAYMENT",             True),
            ("eodMinBalance",     "EOD MIN BALANCE",       True),
            ("eodMaxBalance",     "EOD MAX BALANCE",       True),
        ]

        r = 2
        for entry in FINBIT_ROWS:
            if entry is None:
                ws11.write(r, 0, "Derived Monthly Metrics", fmt_wk_section)
                for ci in range(1, len(finbit_months) + 1):
                    ws11.write(r, ci, "", fmt_wk_section)
                r += 1
                continue

            key, label, is_cur = entry
            ws11.write(r, 0, label, fmt_label)
            for ci, month_key in enumerate(finbit_months, 1):
                val = finbit_data[month_key].get(key, 0)
                if is_cur:
                    ws11.write_number(r, ci, val, fmt_currency)
                else:
                    ws11.write_number(r, ci, val, fmt_integer)
            r += 1

        ws11.set_column(0, 0, 28)
        for ci in range(1, len(finbit_months) + 1):
            ws11.set_column(ci, ci, 18)
        ws11.freeze_panes(2, 1)

    # ── GLOBAL STYLE ADJUSTMENTS ─────────────────────────────────────────────
    # Hide native gridlines and set premium row height for professional look
    for ws in [ws1, ws2, ws3, ws4, ws5, ws6, ws7, ws8, ws9, ws10, ws11]:
        ws.hide_gridlines(2)
        ws.set_default_row(18)

    # ── SAVE ─────────────────────────────────────────────────────────────────
    writer.close()

    # ── Build stats ──────────────────────────────────────────────────────────
    stats = {
        "total_transactions": len(df),
        "total_credits": float(df["Credit"].sum()),
        "total_debits": float(df["Debit"].sum()),
        "credit_count": int((df["Credit"] > 0).sum()),
        "debit_count": int((df["Debit"] > 0).sum()),
        "date_from": str(df["Date"].min().date()),
        "date_to": str(df["Date"].max().date()),
        "months": len(months),
        "recurring_count": int((df["Recurring"] == "Yes").sum()),
        "categories_used": len(df["Category"].unique()),
        "sheets": 11,
    }

    logger.info(
        "Report generated: %d transactions, %s to %s, %d months, %d recurring (11 sheets)",
        stats["total_transactions"], stats["date_from"], stats["date_to"],
        stats["months"], stats["recurring_count"],
    )

    return stats


def _compute_finbit_monthly(df: pd.DataFrame, opening_balance: float = 0) -> Tuple[List[str], Dict]:
    """
    Compute all Finbit monthly metrics from DataFrame.
    
    Returns:
        (sorted_month_keys, dict of month -> metrics_dict)
    """
    # Use the enhanced Finbit metrics function
    return calculate_finbit_metrics_enhanced(df, opening_balance)

def _kw(description: str, kw_list: List[str]) -> bool:
    """Enhanced keyword matching with multiple patterns and case insensitivity."""
    desc_upper = description.upper()
    return any(kw.upper() in desc_upper for kw in kw_list)

def calculate_finbit_metrics_enhanced(df: pd.DataFrame, opening_balance: float = 0.0) -> Tuple[List[str], Dict]:
    """
    Enhanced Finbit-level analysis with comprehensive metrics for ICICI Bank.
    Uses robust keyword detection and advanced financial analytics.
    """
    
    # Enhanced keyword lists based on Finbit patterns and our 88.9% accuracy testing
    KW_CASH_DEP = ["CASH DEPOSIT", "CASHDEP", "CDM", "CASHDEPOSITBY", "CASH DEP", "BY CASH", 
                   "CASH/DEP", "DEP BY CASH", "CASH RECEIPT", "CASH LODGEMENT", "CASH TENDERED",
                   "CASH PAYIN", "CASH PAY IN", "BRANCH CASH", "COUNTER CASH", "TELLER CASH"]
    
    KW_CASH_WDL = ["ATW", "ATM WDL", "ATM CASH", "ATMWDL", "CASH WITHDRAWAL", "CASHWITHDRAWAL", 
                   "NFS ATM", "ATM-WDL", "ATM/CASH", "CASH W/D", "ATM/WDL", "NFS/ATM", 
                   "NFS WDL", "VISA ATM", "SELF WDL", "AWL/", "ATM-CASH", "ATM WITHDL", 
                   "CASH WDL", "WDL ATM", "CARD WITHDRAWAL", "CASH ADVANCE", "CC CASH ADVANCE",
                   "CREDIT CARD CASH ADVANCE", "NFS/P3", "ATM OFFSITE", "ATM ONSITE", "ATM BRANCH"]
    
    KW_CHQ_DEP = ["CHQ DEP", "CHEQUE DEP", "CLG CR", "I/WCLG", "INWARD CLG", "IW CLR", "CHQDEP",
                  "CLG/CR", "INWARD CLEARING", "CHEQUE DEPOSIT", "CHEQUE CREDIT", "CHEQUE CLEARING"]
    
    KW_CHQ_ISS = ["CHQPAID", "CHQ PAID", "SELF-CHQ", "CLG DR", "O/WCLG", "OUTWARD CLG", "CHEQUE PAID",
                  "CLG/DR", "OUTWARD CLEARING", "CHEQUE ISSUE", "CHEQUE DEBIT"]
    
    KW_INW_BOUNCE = ["I/WCHQRET", "INWARD RETURN", "INW BOUNCE", "INW RET", "INWARD BOUNCE", "CHQ RET",
                     "CHEQUE BOUNCE", "CHEQUE RETURN", "INWARD CHEQUE RETURN", "CLG RETURN", 
                     "CHQ RETURN", "CHEQUE DISHONOUR"]
    
    KW_OUTW_BOUNCE = ["O/WCHQRET", "OUTWARD RETURN", "OUTW BOUNCE", "O/W RETURN", "OUTWARD BOUNCE",
                      "CHEQUE BOUNCE", "CHEQUE RETURN", "OUTWARD CHEQUE RETURN", "CLG RETURN",
                      "CHQ RETURN", "CHEQUE DISHONOUR"]
    
    KW_PENALTY = ["PENALTY", "PENAL CHARGE", "PENAL INT", "MIN BAL CHARGE", "NON-MAINT", "MINIMUM BALANCE",
                  "RETURNCHARGES", "RETURN CHARGES", "DEBIT RETURN", "BOUNCE CHARGE", "DISHONOUR",
                  "LATE FEE", "OVERDUE", "DELAYED PAYMENT", "SMS CHARGE", "LOCKER CHARGE", 
                  "ANNUAL FEE", "CARD FEE", "PROCESSING FEE", "SERVICE CHARGE", "GST CHARGE",
                  "DEMAT CHARGES", "DP CHARGES", "ACCOUNT MAINTENANCE", "AMB CHARGES",
                  "QAB CHARGES", "MONTHLY CHARGES", "ANNUAL CHARGES", "PROCESSING CHARGES",
                  "TRANSACTION CHARGES", "NEFT CHARGES", "RTGS CHARGES", "IMPS CHARGES",
                  "UPI CHARGES", "BRANCH CHARGES", "KYC CHARGES", "DOCUMENT CHARGES",
                  "COURIER CHARGES", "LEGAL CHARGES", "RECOVERY CHARGES", "COLLECTION CHARGES",
                  "CLEARANCE CHARGES", "SETTLEMENT CHARGES", "GATEWAY CHARGES",
                  "PAYMENT GATEWAY CHARGES", "PG CHARGES"]
    
    KW_ECS_NACH = ["ACHD-", "ACH D-", "ECS/", "ECS ", "NACH/", "NACH ", "AUTOPAYSI", "SI-", "AUTO DEBIT", "SI /",
                   "ACH D ", "ACH DR", "E-MANDATE", "EMANDATE", "ACH-DR-", "AUTO PAYMENT", 
                   "MANDATE DEBIT", "ECS DEBIT", "ACH DEBIT", "NACH DR", "AUTO DR", 
                   "SI DR", "STANDING INSTRUCTION DR", "CMS", "AUTO DEBIT", "STANDING INSTRUCTION",
                   "LOAN EMI", "LOAN REPAYMENT", "EMI DEBIT", "EMI PAYMENT", "LOAN REPAY",
                   "NACH DEBIT", "NACH PAYMENT", "MONTHLY INSTALLMENT", "LOAN INSTALLMENT",
                   "EMI DEDUCTION", "BAJAJ", "FULLERTON", "HDB", "TATA CAPITAL", "HDFC LOAN",
                   "ICICI LOAN", "HOME LOAN", "PERSONAL LOAN", "CAR LOAN", "EDUCATION LOAN",
                   "NBFC PAYMENT", "FINANCE PAYMENT", "LENDER PAYMENT"]
    
    KW_SELF = ["SELF-", "/SELF", " SELF ", "SELF CHQ", "SELF TRF", "SELF DEPOSIT", "SELF WITHDRAW",
               "SELF TRANSFER", "SELF PAYMENT"]
    
    KW_LOAN_REP = ["EMI", "LOAN REPAY", "LOAN EMI", "BAJAJ FINANCE", "BAJAJFINANCE", "BAJAJ FIN",
                   "TATA CAPITAL", "TATACAPITAL", "DMI FINANCE", "DMIFINANCE", "HOME CREDIT",
                   "HOMECREDIT", "IDFC FIRST", "IDFCFIRST", "HDFC LTD", "FINANCE LTD", "FINANCELTD",
                   "CAPITAL FIRST", "CAPITALFIRST", "FULLERTON", "MUTHOOT", "SHRIRAM",
                   "MAHINDRA FIN", "CHOLAMANDALAM", "SUNDARAM", "LENDINGKART", "PAYSENSE",
                   "POONAWALLA", "ADITYA BIRLA", "EDELWEISS", "IIFL", "LT FINANCE", "KISSHT",
                   "MONEYTAP", "ZESTMONEY", "KREDITBEE", "NAVI", "UGRO CAPITAL"]
    
    KW_LOAN_CR = ["LOAN DISBURSE", "LOAN CR", "LOAN SANCTION", "LOAN CREDIT", "LOAN DISBURSAL",
                  "LOAN DISBURSED", "DISBURSAL", "DISBURSEMENT", "LOAN CREDIT", "SANCTION"]
    
    KW_CC_PAY = ["CC PAYMENT", "CREDIT CARD", "CC000", "RAZPCREDCLUB", "CRED CLUB", "CREDITCARD", "CCPAY",
                 "CRED BILL", "ONECARD", "SLICE", "SIMPL", "LAZYPAY", "POSTPE", "AMAZONPAY LATER",
                 "SBICREDITCARD", "SBI CARD", "HDFCCARD", "ICICICARD", "AXISCARD", "KOTAKCARD",
                 "CARD BILL", "CARDBILL", "CC BILL", "CCBILL", "BILLDESK", "BIL/", "VISA PAYMENT",
                 "MASTERCARD PAYMENT", "AMEX", "AMERICAN EXPRESS", "ICICI CARD", "HDFC CARD",
                 "SBI CARD", "AXIS CARD", "KOTAK CARD", "CITIBANK CARD", "STANDARD CHARTERED CARD",
                 "HSBC CARD", "CANARA CARD", "PNB CARD", "BOB CARD", "UNION BANK CARD",
                 "BANK OF BARODA CARD", "CREDITCARD PAYMENT", "CREDITCARDPAYMENT", "CCPAYMENT",
                 "CARDPAYMENT", "CREDIT CARD BILL", "CC BILL PAYMENT", "CARD DUES",
                 "CREDIT CARD DUES", "CARD SETTLEMENT", "CREDIT CARD SETTLEMENT",
                 "CARD AUTOPAY", "CREDIT CARD AUTOPAY", "CARD EMI", "CREDIT CARD EMI",
                 "CARD LOAN", "CREDIT CARD LOAN"]
    
    KW_SALARY = ["SALARY", "SAL CR", "PAYROLL", "WAGES", "STIPEND", "SAL-", "SALARY-", "SAL CREDIT",
                 "MONTHLY SAL", "MONTHLY SALARY", "SALARY CREDIT", "PAYROLL CREDIT", "SALARY TRANSFER",
                 "PAYMENT FROM HR", "COMPANY SALARY", "PVT LTD SALARY", "LTD SALARY", "LLP SALARY",
                 "TECHNOLOGIES SALARY", "SOLUTIONS SALARY", "INTERNATIONAL SALARY", "SERVICES SALARY",
                 "NEFT SAL", "NEFT SALARY", "MONTHLY SAL CREDIT", "COMPANY PAYROLL", "EMPLOYEE SALARY",
                 "STAFF SALARY", "OFFICE SALARY", "CORP SALARY", "ANNUAL BONUS", "BONUS", "INCENTIVE",
                 "PERFORMANCE BONUS", "COMMISSION", "SALES COMMISSION", "GRATUITY", "PENSION",
                 "PENSION CREDIT", "DIVIDEND", "DIVIDEND CREDIT", "MF DIVIDEND", "MUTUAL FUND DIVIDEND",
                 "STOCK DIVIDEND"]
    
    KW_BANK_CHG = KW_PENALTY  # Bank charges are the same as penalties
    
    # Enhanced digital transfer patterns
    KW_DIGITAL_CR = ["UPI", "UPI/", "IMPS", "IMPS/", "NEFT", "NEFT/", "RTGS", "RTGS/",
                     "PAYTM", "PHONEPE", "GPAY", "GOOGLEPAY", "BHIM", "MOBIKWIK", "FREECHARGE",
                     "AMAZON PAY", "YBL", "@OKAXIS", "@OKHDFC", "@OKICICI", "@OKSBI", "@PAYTM",
                     "@YBL", "@AXL", "@HDFC", "@ICICI", "@SBI", "@KOTAK", "QR", "QR CODE",
                     "SCAN TO PAY", "CONTACTLESS PAYMENT", "NFC PAYMENT", "WALLET PAYMENT",
                     "MOBILE WALLET", "DIGITAL WALLET", "ONLINE PAYMENT", "INTERNET BANKING",
                     "NET BANKING", "MOBILE BANKING", "APP PAYMENT"]
    
    KW_DIGITAL_DR = KW_DIGITAL_CR  # Same patterns for debits
    
    # Enhanced insurance patterns
    KW_INSURANCE = ["INSURANCE", "INSURE", "POLICY", "PREMIUM", "CLAIM", "LIFE INSURANCE",
                    "HEALTH INSURANCE", "MOTOR INSURANCE", "VEHICLE INSURANCE", "CAR INSURANCE",
                    "BIKE INSURANCE", "TERM INSURANCE", "ENDOWMENT", "LIC", "HDFC LIFE",
                    "ICICI PRUDENTIAL", "MAX LIFE", "SBI LIFE", "BAJAJ ALLIANZ", "STAR HEALTH",
                    "CARE HEALTH", "NIVA BUPA", "RELIGARE", "TATA AIA", "KOTAK LIFE",
                    "BIRLA SUN LIFE", "GENERAL INSURANCE", "MEDICLAIM", "HEALTH COVER",
                    "ACCIDENT INSURANCE", "TRAVEL INSURANCE", "ACKO", "DIGIT INSURANCE"]
    
    # Enhanced bounce detection patterns
    KW_BOUNCE = ["RETURN", "BOUNCE", "CHQ RETURN", "CHEQUE RETURN", "CHEQUE BOUNCE", "ECS RETURN",
                 "NACH RETURN", "AUTO DEBIT RETURN", "SI RETURN", "PAYMENT RETURN", "TRANSACTION RETURN",
                 "FAILED", "FAILURE", "INSUFFICIENT FUNDS", "NSF", "NOT SUFFICIENT FUNDS",
                 "EXCEEDS LIMIT", "ACCOUNT BLOCKED", "ACCOUNT FROZEN", "TECHNICAL REASONS",
                 "INVALID ACCOUNT", "ACCOUNT CLOSED", "ACCOUNT DORMANT"]
    
    df = df.copy()
    df["Month"] = df["Date"].dt.to_period("M")
    months_list = sorted(df["Month"].unique())
    month_keys = [m.strftime("%b-%y") for m in months_list]
    
    result = {}
    result = OrderedDict()
    prev_closing = opening_balance
    
    for month_idx, month in enumerate(months_list):
        month_df = df[df["Month"] == month].copy()
        if len(month_df) == 0:
            continue
        
        month_key = month.strftime("%b-%y")
        
        # Basic aggregates
        cr_vals = month_df[month_df["Credit"] > 0]["Credit"].tolist()
        dr_vals = month_df[month_df["Debit"] > 0]["Debit"].tolist()
        total_cr = sum(cr_vals)
        total_dr = sum(dr_vals)
        
        # Balance analytics
        balances = month_df["Balance"].tolist()
        
        # EOD: last balance per calendar day
        eod = month_df.groupby(month_df["Date"].dt.date)["Balance"].last()
        eod_vals = eod.tolist() if len(eod) > 0 else [0]
        
        # Opening / Closing
        if month_idx == 0 and len(month_df) > 0:
            first = month_df.iloc[0]
            start_bal = first["Balance"] - first["Credit"] + first["Debit"]
        else:
            start_bal = prev_closing
        end_bal = balances[-1] if balances else prev_closing
        
        # Transaction type detection
        def match_rows(kw_list, credit_col=True):
            mask = month_df["Description"].apply(lambda d: _kw(d, kw_list))
            if credit_col:
                return month_df[mask & (month_df["Credit"] > 0)]["Credit"].sum()
            else:
                return month_df[mask & (month_df["Debit"] > 0)]["Debit"].sum()
        
        cash_dep = match_rows(KW_CASH_DEP, True)
        cash_wdl = match_rows(KW_CASH_WDL, False)
        chq_dep = match_rows(KW_CHQ_DEP, True)
        chq_iss = match_rows(KW_CHQ_ISS, False)
        inw_b = len(month_df[month_df["Description"].apply(lambda d: _kw(d, KW_INW_BOUNCE))])
        outw_b = len(month_df[month_df["Description"].apply(lambda d: _kw(d, KW_OUTW_BOUNCE))])
        penalty = match_rows(KW_PENALTY, False)
        ecs_nach = match_rows(KW_ECS_NACH, False)
        self_wdl = match_rows(KW_SELF, False)
        self_dep = match_rows(KW_SELF, True)
        loan_rep = match_rows(KW_LOAN_REP, False)
        loan_crd = match_rows(KW_LOAN_CR, True)
        cc_pay = match_rows(KW_CC_PAY, False)
        sal = match_rows(KW_SALARY, True)
        bank_chg = match_rows(KW_BANK_CHG, False)
        
        result[month_key] = {
            'monthlyAvgBal': round(sum(eod_vals) / len(eod_vals), 2),
            'maxBalance': round(max(balances), 2) if balances else 0,
            'minBalance': round(min(balances), 2) if balances else 0,
            'cashDeposit': round(cash_dep, 2),
            'cashWithdrawals': round(cash_wdl, 2),
            'chqDeposit': round(chq_dep, 2),
            'chqIssues': round(chq_iss, 2),
            'credits': round(total_cr, 2),
            'debits': round(total_dr, 2),
            'inwBounce': inw_b,
            'outwBounce': outw_b,
            'penaltyCharges': round(penalty, 2),
            'ecsNach': round(ecs_nach, 2),
            'totalNetDebit': round(max(total_dr - total_cr, 0), 2),
            'totalNetCredit': round(max(total_cr - total_dr, 0), 2),
            'selfWithdraw': round(self_wdl, 2),
            'selfDeposit': round(self_dep, 2),
            'loanRepayment': round(loan_rep, 2),
            'loanCredit': round(loan_crd, 2),
            'creditCardPayment': round(cc_pay, 2),
            'minCredits': round(min(cr_vals), 2) if cr_vals else 0,
            'maxCredits': round(max(cr_vals), 2) if cr_vals else 0,
            'salary': round(sal, 2),
            'bankCharges': round(bank_chg, 2),
            'balanceOpening': round(start_bal, 2),
            'balanceClosing': round(end_bal, 2),
            'salaryMonth': round(sal, 2),
            'ccPayment': round(cc_pay, 2),
            'eodMinBalance': round(min(eod_vals), 2),
            'eodMaxBalance': round(max(eod_vals), 2),
        }
        prev_closing = end_bal
    
    return month_keys, result
