"""
Airco Insights — ICICI Bank AI Fallback
========================================
AI classification stub for unresolved ICICI Bank transactions.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ...intelligence import GroqIntelligenceLayer, LearningStore

logger = logging.getLogger(__name__)


@dataclass
class AIClassificationResult:
    classified_count: int
    total_sent: int
    api_calls: int
    estimated_cost_usd: float
    estimated_cost_inr: float


class ICICIAIFallback:
    """AI fallback stub for ICICI Bank transactions."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.logger  = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.learning_store = LearningStore()
        self.intelligence = GroqIntelligenceLayer(
            api_key=api_key,
            bank_name="ICICI",
            learning_store=self.learning_store,
        )

    def classify_unclassified(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "ICICI",
        account_type: str = "Salaried",
    ) -> List[Dict[str, Any]]:
        classified, _ = self.classify(transactions, bank_name=bank_name, account_type=account_type)
        return classified

    def classify(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "ICICI",
        account_type: str = "Salaried",
    ) -> Tuple[List[Dict[str, Any]], AIClassificationResult]:
        result, stats = self.intelligence.classify(
            transactions=transactions,
            bank_name=bank_name,
            account_type=account_type,
            allowed_categories=[
                "ATM Withdrawal", "Food", "Shopping", "Transport", "Bills",
                "Entertainment", "Health", "Education", "EMI", "Investment",
                "Transfer", "Salary", "Interest", "Refund", "Transfer In",
                "Others Debit", "Others Credit",
            ],
        )
        return result, AIClassificationResult(
            classified_count=stats.classified_count,
            total_sent=stats.total_sent,
            api_calls=stats.api_calls,
            estimated_cost_usd=stats.estimated_cost_usd,
            estimated_cost_inr=stats.estimated_cost_inr,
        )
