"""
Airco Insights — HDFC AI Fallback
==================================
AI classification for unresolved transactions.
Uses Claude API as LAST RESORT only.

Design Principles:
1. AI is NOT primary - only for unclassified transactions
2. Batch processing to minimize API calls
3. Cost estimation before execution
4. Confidence scoring on AI results
5. Learning from AI classifications for rule improvement

Categories must match HDFC rule engine categories.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ...intelligence import GroqIntelligenceLayer, LearningStore

logger = logging.getLogger(__name__)


@dataclass
class AIClassificationResult:
    """Result of AI classification."""
    classified_count: int
    total_sent: int
    api_calls: int
    estimated_cost_usd: float
    estimated_cost_inr: float


class HDFCAIFallback:
    """
    AI fallback classifier for HDFC transactions.
    """
    
    # Valid categories (must match rule engine)
    DEBIT_CATEGORIES = [
        "ATM", "Food", "Shopping", "Transport", "Bills", "Entertainment",
        "Health", "Education", "EMI", "Investment", "Transfer", "Others Debit"
    ]
    
    CREDIT_CATEGORIES = [
        "Salary", "Interest", "Refund", "Transfer In", "Others Credit"
    ]
    
    # Cost estimation (Claude Sonnet)
    COST_PER_1K_INPUT = 0.003
    COST_PER_1K_OUTPUT = 0.015
    AVG_TOKENS_PER_TXN = 50
    AVG_OUTPUT_TOKENS = 20
    MAX_BATCH_SIZE = 20
    
    # INR conversion (approximate)
    USD_TO_INR = 83
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI fallback.
        
        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.learning_store = LearningStore()
        self.intelligence = GroqIntelligenceLayer(
            api_key=api_key,
            bank_name="HDFC",
            learning_store=self.learning_store,
        )
    
    def estimate_cost(self, transaction_count: int) -> Dict[str, Any]:
        """
        Estimate API cost for classifying transactions.
        
        Args:
            transaction_count: Number of transactions to classify
            
        Returns:
            Cost estimation dict
        """
        batches = (transaction_count + self.MAX_BATCH_SIZE - 1) // self.MAX_BATCH_SIZE
        
        input_tokens = transaction_count * self.AVG_TOKENS_PER_TXN + batches * 500  # System prompt
        output_tokens = transaction_count * self.AVG_OUTPUT_TOKENS
        
        cost_usd = (
            (input_tokens / 1000) * self.COST_PER_1K_INPUT +
            (output_tokens / 1000) * self.COST_PER_1K_OUTPUT
        )
        
        return {
            "transaction_count": transaction_count,
            "estimated_batches": batches,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_cost_usd": round(cost_usd, 4),
            "estimated_cost_inr": round(cost_usd * self.USD_TO_INR, 2),
        }
    
    def classify(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "HDFC",
        account_type: str = "Salaried",
    ) -> Tuple[List[Dict[str, Any]], AIClassificationResult]:
        if not transactions:
            return [], AIClassificationResult(0, 0, 0, 0, 0)

        classified, stats = self.intelligence.classify(
            transactions=transactions,
            bank_name=bank_name,
            account_type=account_type,
            allowed_categories=self.DEBIT_CATEGORIES + self.CREDIT_CATEGORIES,
        )
        return classified, AIClassificationResult(
            classified_count=stats.classified_count,
            total_sent=stats.total_sent,
            api_calls=stats.api_calls,
            estimated_cost_usd=stats.estimated_cost_usd,
            estimated_cost_inr=stats.estimated_cost_inr,
        )
    
    def _classify_batch(
        self,
        batch: List[Dict[str, Any]],
        bank_name: str,
        account_type: str,
    ) -> List[Dict[str, Any]]:
        """Classify a batch of transactions using Claude."""
        try:
            import anthropic
        except ImportError:
            self.logger.error("anthropic library not installed")
            return self._fallback_to_others(batch)
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        # Build prompt
        transactions_text = []
        for i, txn in enumerate(batch):
            is_debit = txn.get("debit") is not None
            amount = txn.get("debit") or txn.get("credit") or 0
            transactions_text.append(
                f"{i+1}. [{txn.get('date')}] {txn.get('description', '')[:100]} | "
                f"{'DEBIT' if is_debit else 'CREDIT'}: ₹{amount:,.2f}"
            )
        
        debit_cats = ", ".join(self.DEBIT_CATEGORIES)
        credit_cats = ", ".join(self.CREDIT_CATEGORIES)
        
        prompt = f"""Classify these {bank_name} bank transactions for a {account_type} account.

DEBIT categories: {debit_cats}
CREDIT categories: {credit_cats}

Transactions:
{chr(10).join(transactions_text)}

Respond with JSON array only, each object having:
- "index": transaction number (1-based)
- "category": one of the categories above
- "confidence": 0.5 to 1.0

Example: [{{"index": 1, "category": "Food", "confidence": 0.85}}]

JSON response:"""

        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse JSON response
            # Handle potential markdown code blocks
            if "```" in response_text:
                json_match = response_text.split("```")[1]
                if json_match.startswith("json"):
                    json_match = json_match[4:]
                response_text = json_match.strip()
            
            results = json.loads(response_text)
            
            # Apply results to transactions
            result_map = {r["index"]: r for r in results}
            
            classified = []
            for i, txn in enumerate(batch):
                txn_copy = dict(txn)
                ai_result = result_map.get(i + 1, {})
                
                category = ai_result.get("category", "")
                confidence = ai_result.get("confidence", 0.5)
                
                # Validate category
                is_debit = txn.get("debit") is not None
                valid_cats = self.DEBIT_CATEGORIES if is_debit else self.CREDIT_CATEGORIES
                
                if category not in valid_cats:
                    category = "Others Debit" if is_debit else "Others Credit"
                    confidence = 0.5
                
                txn_copy["category"] = category
                txn_copy["confidence"] = confidence
                txn_copy["source"] = "ai_classifier"
                
                classified.append(txn_copy)
            
            return classified
            
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse AI response: %s", str(e))
            return self._fallback_to_others(batch)
        except Exception as e:
            self.logger.error("AI API call failed: %s", str(e))
            return self._fallback_to_others(batch)
    
    def _fallback_to_others(
        self,
        transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fallback: tag all as Others."""
        result = []
        for txn in transactions:
            txn_copy = dict(txn)
            is_debit = txn.get("debit") is not None
            txn_copy["category"] = "Others Debit" if is_debit else "Others Credit"
            txn_copy["confidence"] = 0.5
            txn_copy["source"] = "ai_fallback_default"
            result.append(txn_copy)
        return result
