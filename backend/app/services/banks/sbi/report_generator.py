"""
SBI Bank Transaction Report Generator
======================================
Deterministic financial report generator using:
- pandas (calculation)
- xlsxwriter (formatting)
- strict rule engine (classification)

Generates 9-sheet Excel report:
1. Summary - Monthly aggregations
2. Category Analysis - Credit/Debit category breakdown
3. Weekly Analysis - Weekly credit/debit totals
4. Recurring Analysis - Recurring vs non-recurring
5. Raw Transactions - All transactions with Category, Confidence, Recurring
6. Monthly Stats
7. Funds Remittance
8. Raw Transaction
9. Finbit - Finbit-specific monthly metrics

No AI. No fuzzy logic. No probability scoring.
Every output cell traceable to an exact rule.
"""

import logging
import os
import re
from collections import Counter, OrderedDict
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd
from .sbi_classifier import SBIClassifier
from ...intelligence import LearningStore

logger = logging.getLogger(__name__)

# Initialize the unified SBI classifier (singleton)
_classifier = None
_learning_store = None

def get_classifier() -> SBIClassifier:
    """Get or create the unified SBI classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = SBIClassifier()
        logger.info("SBI classifier initialized: %s", _classifier.get_category_stats())
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
    learned = _learning_store.lookup(description, bank_name="SBI")
    if learned:
        return (str(learned.get("category", "Others")), int(max(float(learned.get("confidence", 0.9)) * 100, 90)))

    classifier = get_classifier()
    result = classifier.classify(row)
    try:
        category = str(result[0] if isinstance(result, tuple) else result.get("display_category") or result.get("internal_category") or "")
        confidence = float(result[1] if isinstance(result, tuple) else result.get("confidence_score") or 0)
        if category and confidence >= 80 and category not in {"Others", "Others Debit", "Others Credit"}:
            if _learning_store is None:
                _learning_store = LearningStore()
            _learning_store.record_observation(
                description=row.get("Description", ""),
                category=category,
                confidence=confidence / 100.0,
                source="rule",
                bank_name="SBI",
                account_type="",
                metadata={
                    "matched_rule": result.get("matched_rule", "") if isinstance(result, dict) else "",
                    "matched_token": result.get("matched_token", "") if isinstance(result, dict) else "",
                },
            )
    except Exception:
        logger.debug("SBI learning-store update skipped", exc_info=True)
    return result


def detect_recurring(df: pd.DataFrame) -> pd.DataFrame:
    """Detect recurring transactions."""
    df = df.copy()
    df["Recurring"] = "No"
    
    # Group by description and count
    desc_counts = df.groupby("Description").size()
    recurring_descs = desc_counts[desc_counts >= 2].index
    
    # Mark as recurring
    df.loc[df["Description"].isin(recurring_descs), "Recurring"] = "Yes"
    
    return df


def generate_report(
    transactions: List[Dict[str, Any]],
    output_path: str,
    user_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate comprehensive Excel report for SBI Bank statement.
    
    Args:
        transactions: List of transaction dictionaries
        output_path: Path to save Excel file
        opening_balance: Opening balance for the period
        
    Returns:
        Dictionary with report statistics
    """
    logger.info("Generating SBI report with %d transactions", len(transactions))
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    # Ensure required columns
    required_cols = ["date", "description", "debit", "credit", "balance"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Rename for consistency
    df = df.rename(columns={
        "date": "Date",
        "description": "Description",
        "debit": "Debit",
        "credit": "Credit",
        "balance": "Balance",
        "ref_no": "Ref_No",
    })
    
    # Fill NaN values
    df["Debit"] = df["Debit"].fillna(0)
    df["Credit"] = df["Credit"].fillna(0)
    df["Ref_No"] = df.get("Ref_No", "").fillna("")
    
    # Convert date to datetime
    df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y", errors="coerce")
    
    # Classify transactions
    df[["Category", "Confidence"]] = df.apply(
        lambda row: pd.Series(classify(row)), axis=1
    )
    
    # Detect recurring
    df = detect_recurring(df)
    
    # Add month column
    df["Month"] = df["Date"].dt.to_period("M")
    
    # Sort by date
    df = df.sort_values("Date").reset_index(drop=True)
    
    # Generate Excel with xlsxwriter
    from pandas import ExcelWriter
    
    writer = ExcelWriter(output_path, engine="xlsxwriter")
    workbook = writer.book
    
    # ── FORMATS ──────────────────────────────────────────────────────────────
    fmt_header = workbook.add_format({
        "bold": True, "bg_color": "#1F4E79", "font_color": "white",
        "border": 1, "align": "center", "valign": "vcenter"
    })
    fmt_currency = workbook.add_format({"num_format": "₹#,##0.00", "border": 1})
    fmt_date = workbook.add_format({"num_format": "dd-mmm-yyyy", "border": 1})
    fmt_text = workbook.add_format({"border": 1, "align": "left"})
    fmt_integer = workbook.add_format({"num_format": "#,##0", "border": 1, "align": "center"})
    fmt_percent = workbook.add_format({"num_format": "0%", "border": 1})
    fmt_month_header = workbook.add_format({
        "bold": True, "bg_color": "#D9E1F2", "border": 1,
        "align": "center", "valign": "vcenter"
    })
    fmt_sub_header = workbook.add_format({
        "bold": True, "bg_color": "#E7E6E6", "border": 1
    })
    fmt_section_title = workbook.add_format({
        "bold": True, "font_size": 14, "bg_color": "#1F4E79",
        "font_color": "white", "border": 1, "align": "center"
    })
    
    months = df["Month"].unique()
    months_list = sorted(months)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 1 — Summary
    # ══════════════════════════════════════════════════════════════════════════
    ws1 = workbook.add_worksheet("Summary")
    ws1.set_column(0, 0, 18)
    ws1.set_column(1, 4, 16)
    
    ws1.merge_range(0, 0, 0, 4, "Monthly Transaction Summary", fmt_section_title)
    headers = ["Month", "Credits (₹)", "Debits (₹)", "Net (₹)", "Transactions"]
    for c, h in enumerate(headers):
        ws1.write(1, c, h, fmt_header)
    
    row = 2
    for m in months_list:
        month_df = df[df["Month"] == m]
        credits = month_df["Credit"].sum()
        debits = month_df["Debit"].sum()
        net = credits - debits
        count = len(month_df)
        
        ws1.write(row, 0, m.strftime("%b-%y"), fmt_text)
        ws1.write_number(row, 1, credits, fmt_currency)
        ws1.write_number(row, 2, debits, fmt_currency)
        ws1.write_number(row, 3, net, fmt_currency)
        ws1.write_number(row, 4, count, fmt_text)
        row += 1
    
    ws1.freeze_panes(2, 0)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 2 — Category Analysis
    # ══════════════════════════════════════════════════════════════════════════
    ws2 = workbook.add_worksheet("Category Analysis")
    ws2.set_column(0, 0, 22)
    ws2.set_column(1, 3, 16)
    
    ws2.merge_range(0, 0, 0, 3, "Category-wise Analysis", fmt_section_title)
    cat_headers = ["Category", "Credit (₹)", "Debit (₹)", "Count"]
    for c, h in enumerate(cat_headers):
        ws2.write(1, c, h, fmt_header)
    
    cat_summary = df.groupby("Category").agg({
        "Credit": "sum",
        "Debit": "sum",
        "Category": "count"
    }).rename(columns={"Category": "Count"})
    cat_summary = cat_summary.sort_values("Count", ascending=False)
    
    row = 2
    for cat, data in cat_summary.iterrows():
        ws2.write(row, 0, cat, fmt_text)
        ws2.write_number(row, 1, data["Credit"], fmt_currency)
        ws2.write_number(row, 2, data["Debit"], fmt_currency)
        ws2.write_number(row, 3, int(data["Count"]), fmt_text)
        row += 1
    
    ws2.freeze_panes(2, 0)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 3 — Weekly Analysis
    # ══════════════════════════════════════════════════════════════════════════
    ws3 = workbook.add_worksheet("Weekly Analysis")
    ws3.set_column(0, 0, 18)
    ws3.set_column(1, 2, 16)
    
    ws3.merge_range(0, 0, 0, 2, "Weekly Analysis", fmt_section_title)
    week_headers = ["Week", "Credits (₹)", "Debits (₹)"]
    for c, h in enumerate(week_headers):
        ws3.write(1, c, h, fmt_header)
    
    df["Week"] = df["Date"].dt.to_period("W")
    weekly = df.groupby("Week").agg({"Credit": "sum", "Debit": "sum"})
    
    row = 2
    for week, data in weekly.iterrows():
        ws3.write(row, 0, str(week), fmt_text)
        ws3.write_number(row, 1, data["Credit"], fmt_currency)
        ws3.write_number(row, 2, data["Debit"], fmt_currency)
        row += 1
    
    ws3.freeze_panes(2, 0)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 4 — Recurring Analysis
    # ══════════════════════════════════════════════════════════════════════════
    ws4 = workbook.add_worksheet("Recurring Analysis")
    ws4.set_column(0, 0, 45)
    ws4.set_column(1, 3, 16)
    
    ws4.merge_range(0, 0, 0, 3, "Recurring Transactions", fmt_section_title)
    rec_headers = ["Description", "Occurrences", "Total Credit", "Total Debit"]
    for c, h in enumerate(rec_headers):
        ws4.write(1, c, h, fmt_header)
    
    recurring = df[df["Recurring"] == "Yes"].groupby("Description").agg({
        "Description": "count",
        "Credit": "sum",
        "Debit": "sum",
    }).rename(columns={"Description": "Count"})
    recurring = recurring.sort_values("Count", ascending=False)
    
    row = 2
    for desc, data in recurring.iterrows():
        ws4.write(row, 0, desc, fmt_text)
        ws4.write_number(row, 1, int(data["Count"]), fmt_text)
        ws4.write_number(row, 2, data["Credit"], fmt_currency)
        ws4.write_number(row, 3, data["Debit"], fmt_currency)
        row += 1
    
    ws4.freeze_panes(2, 0)
    
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 5 — Raw Transactions (first 5 sheets legacy format)
    # ══════════════════════════════════════════════════════════════════════════
    ws5 = workbook.add_worksheet("Transactions")
    ws5.set_column(0, 0, 14)
    ws5.set_column(1, 1, 60)
    ws5.set_column(2, 6, 16)
    
    txn_headers = ["Date", "Description", "Debit", "Credit", "Balance", "Category", "Recurring"]
    for c, h in enumerate(txn_headers):
        ws5.write(0, c, h, fmt_header)
    
    for ri in range(len(df)):
        row_num = ri + 1
        r = df.iloc[ri]
        if pd.notna(r["Date"]):
            ws5.write_datetime(row_num, 0, r["Date"].to_pydatetime(), fmt_date)
        else:
            ws5.write(row_num, 0, "", fmt_text)
        ws5.write(row_num, 1, str(r["Description"]), fmt_text)
        if r["Debit"] > 0:
            ws5.write_number(row_num, 2, r["Debit"], fmt_currency)
        else:
            ws5.write(row_num, 2, "", fmt_text)
        if r["Credit"] > 0:
            ws5.write_number(row_num, 3, r["Credit"], fmt_currency)
        else:
            ws5.write(row_num, 3, "", fmt_text)
        ws5.write_number(row_num, 4, r["Balance"], fmt_currency)
        ws5.write(row_num, 5, str(r["Category"]), fmt_text)
        ws5.write(row_num, 6, str(r["Recurring"]), fmt_text)
    
    ws5.freeze_panes(1, 0)
    ws5.autofilter(0, 0, len(df), len(txn_headers) - 1)
    
    # Additional sheets 6-8 (Monthly Stats, Funds Remittance, Raw Transaction) - simplified versions
    
    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 9 — Source Analysis
    # ══════════════════════════════════════════════════════════════════════════
    source_df = df.copy()
    if "Description" not in source_df.columns:
        source_df["Description"] = ""
    if "Date" not in source_df.columns:
        source_df["Date"] = pd.NaT
    if "Credit" not in source_df.columns:
        source_df["Credit"] = 0
    if "Debit" not in source_df.columns:
        source_df["Debit"] = 0
    if "Balance" not in source_df.columns:
        source_df["Balance"] = 0
    if "Category" not in source_df.columns:
        source_df["Category"] = "Others"

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
        for token in ["NEFT", "NEFTDR", "NEFT CR", "NEFT DR", "RTGS", "IMPS", "UPI", "ACH", "NACH", "ECS", "ATM", "ATW", "POS", "CARD", "SETTLEMENT", "CASH", "DEPOSIT", "WITHDRAWAL", "WITHDRWL", "TRF", "TRANSFER", "PAYMENT", "DR", "CR", "TO", "FROM", "BY", "SELF", "CHQ", "CHEQUE", "CLG", "REF", "TXN", "TRANSACTION", "NO", "NUMBER"]:
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

    source_df["TransactionMode"] = source_df["Description"].apply(_detect_transaction_mode)
    source_df["Source"] = [_extract_source(desc, mode) for desc, mode in zip(source_df["Description"], source_df["TransactionMode"])]
    source_df["IsCredit"] = source_df["Credit"].fillna(0) > 0
    source_df["TxnAmount"] = source_df["Credit"].where(source_df["Credit"].fillna(0) > 0, source_df["Debit"].fillna(0))
    recurring_keys = set()
    source_groups = source_df.groupby(source_df["Source"].str.lower().fillna("unknown"))
    for key, group in source_groups:
        if key == "unknown" or len(group) < 3:
            continue
        month_count = group["Date"].dt.to_period("M").nunique() if "Date" in group else 0
        if month_count >= 2:
            recurring_keys.add(key)
    source_df["IsRecurring"] = source_df["Source"].str.lower().fillna("unknown").isin(recurring_keys)
    source_df["IdentifiedCategory"] = [
        _map_identified_category(source, mode, desc, cat, is_credit)
        for source, mode, desc, cat, is_credit in zip(
            source_df["Source"], source_df["TransactionMode"], source_df["Description"], source_df["Category"], source_df["IsCredit"]
        )
    ]
    source_df["Flag"] = [
        _flag_transaction(amount, source, recurring, mode)
        for amount, source, recurring, mode in zip(
            source_df["TxnAmount"].fillna(0), source_df["Source"], source_df["IsRecurring"], source_df["TransactionMode"]
        )
    ]
    source_df["Month"] = source_df["Date"].dt.to_period("M").astype(str)
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
    source_headers = ["Transaction Mode", "Source", "Identified Category", "Flag", "Date", "Description", "Credit", "Debit", "Balance"]
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
        ws9.write_number(ri, 6, credit, fmt_currency) if credit > 0 else ws9.write(ri, 6, "", fmt_text)
        ws9.write_number(ri, 7, debit, fmt_currency) if debit > 0 else ws9.write(ri, 7, "", fmt_text)
        ws9.write_number(ri, 8, balance, fmt_currency)
    ws9.freeze_panes(2, 0)
    if len(source_df) > 0:
        ws9.autofilter(1, 0, len(source_df) + 1, len(source_headers) - 1)

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 10 — Category Outcome
    # ══════════════════════════════════════════════════════════════════════════
    frame = source_df.copy()
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
        base["MetricValue"] = 1 if agg_kind == "count" else base[value_col]
        grouped = base.groupby(["Category", "Source", "MonthKey"], dropna=False)["MetricValue"].sum().reset_index()
        pivot = grouped.pivot_table(index=["Category", "Source"], columns="MonthKey", values="MetricValue", aggfunc="sum", fill_value=0)
        pivot = pivot.reindex(columns=month_keys, fill_value=0).reset_index().rename(columns=month_lookup)
        for label in month_labels:
            if label not in pivot.columns:
                pivot[label] = 0
        return pivot[["Category", "Source", *month_labels]]

    credit_mask = frame["Credit"] > 0
    debit_mask = frame["Debit"] > 0
    credit_count = _pivot_metric("Credit", credit_mask, "count")
    debit_count = _pivot_metric("Debit", debit_mask, "count")
    credit_amount = _pivot_metric("Credit", credit_mask, "amount")
    debit_amount = _pivot_metric("Debit", debit_mask, "amount")

    def _sort_table(table: pd.DataFrame) -> pd.DataFrame:
        if table.empty:
            return table
        return table.sort_values(["Category", "Source"], kind="stable").reset_index(drop=True)

    outcome_tables = {
        "month_labels": month_labels,
        "credit_count": _sort_table(credit_count),
        "debit_count": _sort_table(debit_count),
        "credit_amount": _sort_table(credit_amount),
        "debit_amount": _sort_table(debit_amount),
    }

    ws10 = workbook.add_worksheet("Category Outcome")
    ws10.set_column(0, 0, 22)
    ws10.set_column(1, 1, 24)
    for col_idx in range(2, 2 + len(month_labels)):
        ws10.set_column(col_idx, col_idx, 14)
    outcome_headers = ["Category", "Source", *month_labels]

    def _write_table(start_row: int, title: str, table_df: pd.DataFrame) -> int:
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
                        ws10.write_blank(current_row, mi, None, fmt_text)
                ws10.set_row(current_row, None, None, {"level": 1, "hidden": True})
                current_row += 1
        ws10.freeze_panes(2, 0)
        return current_row

    next_row = 0
    next_row = _write_table(next_row, "CATEGORY OUTCOME  Credit Count", outcome_tables.get("credit_count", pd.DataFrame()))
    next_row += 1
    next_row = _write_table(next_row, "CATEGORY OUTCOME  Debit Count", outcome_tables.get("debit_count", pd.DataFrame()))
    next_row += 1
    next_row = _write_table(next_row, "CATEGORY OUTCOME  Credit Amount", outcome_tables.get("credit_amount", pd.DataFrame()))
    next_row += 1
    _write_table(next_row, "CATEGORY OUTCOME  Debit Amount", outcome_tables.get("debit_amount", pd.DataFrame()))

    # ══════════════════════════════════════════════════════════════════════════
    # SHEET 11 — Finbit
    # ══════════════════════════════════════════════════════════════════════════
    ws11 = workbook.add_worksheet("Finbit")

    opening_balance = 0
    if len(df) > 0:
        first = df.iloc[0]
        opening_balance = first["Balance"] - first["Credit"] + first["Debit"]

    finbit_months, finbit_data = _compute_finbit_monthly(df, opening_balance)

    finbit_metrics = [
        ("monthlyAvgBal", "Monthly Avg Balance"),
        ("maxBalance", "Max Balance"),
        ("minBalance", "Min Balance"),
        ("cashDeposit", "Cash Deposit"),
        ("cashWithdrawals", "Cash Withdrawals"),
        ("chqDeposit", "Cheque Deposit"),
        ("chqIssues", "Cheque Issues"),
        ("credits", "Total Credits"),
        ("debits", "Total Debits"),
        ("inwBounce", "Inward Bounce Count"),
        ("outwBounce", "Outward Bounce Count"),
        ("penaltyCharges", "Penalty Charges"),
        ("ecsNach", "ECS/NACH Debits"),
        ("totalNetDebit", "Total Net Debit"),
        ("totalNetCredit", "Total Net Credit"),
        ("selfWithdraw", "Self Withdrawals"),
        ("selfDeposit", "Self Deposits"),
        ("loanRepayment", "Loan Repayment"),
        ("loanCredit", "Loan Credit"),
        ("creditCardPayment", "Credit Card Payment"),
        ("minCredits", "Min Credit Transaction"),
        ("maxCredits", "Max Credit Transaction"),
        ("salary", "Salary Credits"),
        ("bankCharges", "Bank Charges"),
        ("balanceOpening", "Opening Balance"),
        ("balanceClosing", "Closing Balance"),
        ("salaryMonth", "Salary This Month"),
        ("ccPayment", "CC Payment"),
        ("eodMinBalance", "EOD Min Balance"),
        ("eodMaxBalance", "EOD Max Balance"),
    ]

    ws11.set_column(0, 0, 28)
    for c in range(1, len(finbit_months) + 1):
        ws11.set_column(c, c, 15)

    ws11.write(0, 0, "Metric", fmt_header)
    for c_idx, m_label in enumerate(finbit_months, 1):
        ws11.write(0, c_idx, m_label, fmt_header)

    for r_idx, (metric_key, metric_label) in enumerate(finbit_metrics, 1):
        ws11.write(r_idx, 0, metric_label, fmt_sub_header)
        for c_idx, m_label in enumerate(finbit_months, 1):
            val = finbit_data.get(m_label, {}).get(metric_key, 0)
            if isinstance(val, (int, float)):
                if metric_key in ["inwBounce", "outwBounce"]:
                    ws11.write_number(r_idx, c_idx, val, fmt_text)
                else:
                    ws11.write_number(r_idx, c_idx, val, fmt_currency)
            else:
                ws11.write(r_idx, c_idx, val, fmt_text)

    ws11.freeze_panes(1, 1)

    # ── GLOBAL STYLE ─────────────────────────────────────────────────────────
    for ws in [ws1, ws2, ws3, ws4, ws5, ws9, ws10, ws11]:
        ws.hide_gridlines(2)
        ws.set_default_row(18)

    writer.close()

    # Build stats
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
        "SBI report generated: %d transactions, %s to %s, %d months, %d recurring (11 sheets)",
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
    def _kw(desc: str, keywords: list) -> bool:
        """Case-insensitive keyword match."""
        d = str(desc).upper()
        return any(k.upper() in d for k in keywords)
    
    # Keyword lists
    KW_CASH_DEP = ["CASH DEPOSIT", "CASHDEP", "CDM", "CASHDEPOSITBY", "CASH DEP", "BY CASH", 
                   "CASH/DEP", "DEP BY CASH"]
    KW_CASH_WDL = ["ATW", "ATM WDL", "ATM CASH", "ATMWDL", "CASH WITHDRAWAL", "CASHWITHDRAWAL", 
                   "NFS ATM", "ATM-WDL", "ATM/CASH", "CASH W/D", "ATM/WDL", "NFS/ATM", 
                   "NFS WDL", "VISA ATM", "SELF WDL", "AWL/"]
    KW_CHQ_DEP = ["CHQ DEP", "CHEQUE DEP", "CLG CR", "I/WCLG", "INWARD CLG", "IW CLR", "CHQDEP",
                  "CLG/CR", "INWARD CLEARING"]
    KW_CHQ_ISS = ["CHQPAID", "CHQ PAID", "SELF-CHQ", "CLG DR", "O/WCLG", "OUTWARD CLG", "CHEQUE PAID",
                  "CLG/DR", "OUTWARD CLEARING"]
    KW_INW_BOUNCE = ["I/WCHQRET", "INWARD RETURN", "INW BOUNCE", "INW RET", "INWARD BOUNCE", "CHQ RET"]
    KW_OUTW_BOUNCE = ["O/WCHQRET", "OUTWARD RETURN", "OUTW BOUNCE", "O/W RETURN", "OUTWARD BOUNCE"]
    KW_PENALTY = ["PENALTY", "PENAL CHARGE", "PENAL INT", "MIN BAL CHARGE", "NON-MAINT", "MINIMUM BALANCE",
                  "RETURNCHARGES", "RETURN CHARGES", "DEBIT RETURN", "BOUNCE CHARGE", "DISHONOUR",
                  "LATE FEE", "OVERDUE", "DELAYED PAYMENT"]
    KW_ECS_NACH = ["ACHD-", "ACH D-", "ECS/", "ECS ", "NACH/", "NACH ", "AUTOPAYSI", "SI-", "AUTO DEBIT", "SI /",
                   "ACH D ", "ACH DR", "E-MANDATE", "EMANDATE"]
    KW_SELF = ["SELF-", "/SELF", " SELF ", "SELF CHQ", "SELF TRF"]
    KW_LOAN_REP = ["EMI", "LOAN REPAY", "LOAN EMI", "BAJAJ FINANCE", "BAJAJFINANCE", "BAJAJ FIN",
                   "TATA CAPITAL", "TATACAPITAL", "DMI FINANCE", "DMIFINANCE", "HOME CREDIT",
                   "HOMECREDIT", "IDFC FIRST", "IDFCFIRST", "HDFC LTD", "FINANCE LTD", "FINANCELTD",
                   "CAPITAL FIRST", "CAPITALFIRST", "FULLERTON", "MUTHOOT", "SHRIRAM",
                   "MAHINDRA FIN", "CHOLAMANDALAM", "SUNDARAM", "LENDINGKART", "PAYSENSE"]
    KW_LOAN_CR = ["LOAN DISBURSE", "LOAN CR", "LOAN SANCTION", "LOAN CREDIT"]
    KW_CC_PAY = ["CC PAYMENT", "CREDIT CARD", "CC000", "RAZPCREDCLUB", "CRED CLUB", "CREDITCARD", "CCPAY",
                 "CRED BILL", "ONECARD", "SLICE", "SIMPL", "LAZYPAY", "POSTPE", "AMAZONPAY LATER",
                 "SBICREDITCARD", "SBI CARD", "HDFCCARD", "ICICICARD", "AXISCARD", "KOTAKCARD",
                 "CARD BILL", "CARDBILL", "CC BILL", "CCBILL"]
    KW_SALARY = ["SALARY", "SAL CR", "PAYROLL", "WAGES", "STIPEND", "SAL-", "SALARY-"]
    KW_BANK_CHG = ["CHARGES", "FEE-", "LOWUSAGECHARGES", "SETTLEMENTCHARGE", "EDC RENTAL", "EDCRENTAL",
                   "SERVICE CHARGE", "BANK CHARGE", "SMS ALERT", "MAINTENANCE CHARGE", "FEE-ATMCASH",
                   "INSTA ALERT", "INSTAALERT", "GST ON", "ALERT CHG"]
    
    df = df.copy()
    df["Month"] = df["Date"].dt.to_period("M")
    months_list = sorted(df["Month"].unique())
    month_keys = [m.strftime("%b-%y") for m in months_list]
    
    result = OrderedDict()
    prev_closing = opening_balance
    
    for month_idx, month in enumerate(months_list):
        month_df = df[df["Month"] == month].copy()
        if len(month_df) == 0:
            continue
        
        month_key = month.strftime("%b-%y")
        
        cr_vals = month_df[month_df["Credit"] > 0]["Credit"].tolist()
        dr_vals = month_df[month_df["Debit"] > 0]["Debit"].tolist()
        total_cr = sum(cr_vals)
        total_dr = sum(dr_vals)
        
        balances = month_df["Balance"].tolist()
        eod = month_df.groupby(month_df["Date"].dt.date)["Balance"].last()
        eod_vals = eod.tolist() if len(eod) > 0 else [0]
        
        if month_idx == 0 and len(month_df) > 0:
            first = month_df.iloc[0]
            start_bal = first["Balance"] - first["Credit"] + first["Debit"]
        else:
            start_bal = prev_closing
        end_bal = balances[-1] if balances else prev_closing
        
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
