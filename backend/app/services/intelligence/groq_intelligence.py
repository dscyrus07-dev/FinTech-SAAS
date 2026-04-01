"""Groq-powered intelligence layer for selective transaction enrichment and learning."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .learning_store import LearningStore

logger = logging.getLogger(__name__)


@dataclass
class GroqClassificationStats:
    classified_count: int
    total_sent: int
    api_calls: int
    estimated_cost_usd: float
    estimated_cost_inr: float


class GroqIntelligenceLayer:
    """Selective Groq layer that only handles unresolved or ambiguous transactions."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        bank_name: str = "",
        model: Optional[str] = None,
        learning_store: Optional[LearningStore] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.bank_name = bank_name
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        self.learning_store = learning_store or LearningStore()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @staticmethod
    def _safe_amount(txn: Dict[str, Any]) -> float:
        credit = txn.get("credit") or txn.get("Credit") or 0
        debit = txn.get("debit") or txn.get("Debit") or 0
        try:
            credit = float(credit or 0)
        except (TypeError, ValueError):
            credit = 0.0
        try:
            debit = float(debit or 0)
        except (TypeError, ValueError):
            debit = 0.0
        return credit if credit > 0 else debit

    @staticmethod
    def _is_debit(txn: Dict[str, Any]) -> bool:
        debit = txn.get("debit") or txn.get("Debit") or 0
        try:
            return float(debit or 0) > 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _normalize_description(description: Any) -> str:
        text = str(description or "").upper()
        text = re.sub(r"[^A-Z0-9\s/\-_.]", " ", text)
        text = re.sub(r"\b(NEFT\s+CR|NEFT\s+DR|IMPS\s+CR|IMPS\s+DR|UPI\s+CR|UPI\s+DR|ATM\s+WDL|ATM\s+CASH|ATW|POS|ECOM|NACH|ACH\s+DR|ACH\s+CR)\b", " ", text)
        text = re.sub(r"\b\d{6,}\b", " ", text)
        text = re.sub(r"\b[A-Z]{2,}\d+[A-Z0-9]*\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _build_prompt(
        self,
        transactions: Sequence[Dict[str, Any]],
        bank_name: str,
        account_type: str,
        allowed_categories: Sequence[str],
        recent_learnings: Sequence[Dict[str, Any]],
    ) -> str:
        payload = {
            "bank_name": bank_name,
            "account_type": account_type,
            "allowed_categories": list(allowed_categories),
            "transactions": [
                {
                    "index": i + 1,
                    "description": str(txn.get("description") or txn.get("Description") or "")[:180],
                    "clean_description": self._normalize_description(txn.get("description") or txn.get("Description") or "")[:180],
                    "amount": round(self._safe_amount(txn), 2),
                    "type": "debit" if self._is_debit(txn) else "credit",
                    "date": str(txn.get("date") or txn.get("Date") or ""),
                    "current_category": txn.get("category") or txn.get("Category") or "",
                    "current_confidence": float(txn.get("confidence") or txn.get("Confidence") or 0),
                }
                for i, txn in enumerate(transactions)
            ],
            "recent_learning_examples": [
                {
                    "entity": item.get("entity", ""),
                    "normalized_entity": item.get("normalized_entity", ""),
                    "category": item.get("category", ""),
                    "pattern": item.get("pattern", ""),
                    "recurring_type": item.get("recurring_type", ""),
                }
                for item in recent_learnings
            ],
        }

        return (
            "You are the intelligence layer for Airco Insights. "
            "Classify only ambiguous or unresolved bank transactions. "
            "Return strict JSON only with an array named results. "
            "Use only allowed categories. "
            "If the entity looks like a salary/employer/merchant/subscription/EMI pattern, label accordingly.\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        text = response_text.strip()
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
        data = json.loads(text)
        if isinstance(data, dict):
            if isinstance(data.get("results"), list):
                return data["results"]
            if isinstance(data.get("items"), list):
                return data["items"]
            return [data]
        if isinstance(data, list):
            return data
        raise ValueError("Groq response was not JSON array/object")

    @staticmethod
    def _cost_estimate(transaction_count: int) -> Tuple[float, float]:
        # Light-touch cost estimate for budgeting only; adjust as needed.
        estimated_usd = round(transaction_count * 0.0009, 4)
        estimated_inr = round(estimated_usd * 83, 2)
        return estimated_usd, estimated_inr

    def classify(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str,
        account_type: str,
        allowed_categories: Sequence[str],
    ) -> Tuple[List[Dict[str, Any]], GroqClassificationStats]:
        if not transactions:
            return [], GroqClassificationStats(0, 0, 0, 0.0, 0.0)

        bank_name = bank_name or self.bank_name or ""
        allowed = [str(cat) for cat in allowed_categories if str(cat).strip()]
        recent = self.learning_store.recent_learnings(bank_name=bank_name, limit=8)

        output: List[Dict[str, Any]] = []
        pending: List[Tuple[int, Dict[str, Any], Optional[Dict[str, Any]]]] = []

        for idx, txn in enumerate(transactions):
            txn_copy = dict(txn)
            cache_hit = self.learning_store.lookup(
                txn_copy.get("description") or txn_copy.get("Description") or "",
                bank_name=bank_name,
                account_type=account_type,
            )
            if cache_hit:
                txn_copy["category"] = cache_hit["category"]
                txn_copy["confidence"] = max(float(cache_hit.get("confidence", 0.9)), float(txn_copy.get("confidence") or txn_copy.get("Confidence") or 0.0))
                txn_copy["source"] = "learning_store"
                txn_copy["matched_rule"] = "learning_cache"
                output.append(txn_copy)
                continue
            pending.append((idx, txn_copy, cache_hit))
            output.append(txn_copy)

        if not pending:
            return output, GroqClassificationStats(len(output), len(transactions), 0, 0.0, 0.0)

        if not self.api_key:
            self.logger.warning("Groq API key not configured; using fallback classifications only.")
            for _, txn_copy, _ in pending:
                is_debit = self._is_debit(txn_copy)
                txn_copy["category"] = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
                txn_copy["confidence"] = float(txn_copy.get("confidence") or txn_copy.get("Confidence") or 0.5)
                txn_copy["source"] = txn_copy.get("source") or "groq_disabled"
            usd, inr = self._cost_estimate(len(pending))
            return output, GroqClassificationStats(len(output) - len(pending), len(transactions), 0, usd, inr)

        try:
            from groq import Groq
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.logger.error("Groq SDK unavailable: %s", exc)
            for _, txn_copy, _ in pending:
                is_debit = self._is_debit(txn_copy)
                txn_copy["category"] = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
                txn_copy["confidence"] = float(txn_copy.get("confidence") or txn_copy.get("Confidence") or 0.5)
                txn_copy["source"] = txn_copy.get("source") or "groq_unavailable"
            usd, inr = self._cost_estimate(len(pending))
            return output, GroqClassificationStats(len(output) - len(pending), len(transactions), 0, usd, inr)

        client = Groq(api_key=self.api_key)
        prompt = self._build_prompt([txn for _, txn, _ in pending], bank_name, account_type, allowed, recent)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return strict JSON only. No markdown, no explanations."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=1200,
            )
            response_text = response.choices[0].message.content or ""
            results = self._parse_response(response_text)
        except Exception as exc:
            self.logger.error("Groq classification failed: %s", exc)
            results = []

        result_map: Dict[int, Dict[str, Any]] = {}
        for item in results:
            if not isinstance(item, dict):
                continue
            try:
                result_map[int(item.get("index"))] = item
            except Exception:
                continue

        classified_now = 0
        for rel_idx, (orig_idx, txn_copy, _) in enumerate(pending, start=1):
            ai_result = result_map.get(rel_idx, {})
            is_debit = self._is_debit(txn_copy)
            category = str(ai_result.get("category") or "").strip()
            confidence = ai_result.get("confidence", 0.5)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.5
            reason = str(ai_result.get("reason") or "")
            entity = str(ai_result.get("entity") or ai_result.get("normalized_entity") or "")
            recurring_type = str(ai_result.get("recurring_type") or "")
            pattern = str(ai_result.get("pattern") or "")
            should_learn = bool(ai_result.get("should_learn", confidence >= 0.85))

            if allowed and category not in allowed:
                category = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")
                confidence = min(confidence, 0.6)

            if not category:
                category = txn_copy.get("category") or ("Others Debit" if is_debit else "Others Credit")

            txn_copy["category"] = category
            txn_copy["confidence"] = confidence
            txn_copy["source"] = "groq_llm"
            txn_copy["matched_rule"] = reason or "groq"
            if entity:
                txn_copy["matched_token"] = entity
            if recurring_type:
                txn_copy["recurring_type"] = recurring_type
            if ai_result.get("is_recurring") is not None:
                txn_copy["is_recurring"] = bool(ai_result.get("is_recurring"))

            if should_learn and confidence >= 0.85:
                self.learning_store.record_observation(
                    description=txn_copy.get("description") or txn_copy.get("Description") or entity or "",
                    category=category,
                    confidence=confidence,
                    source="llm",
                    bank_name=bank_name,
                    account_type=account_type,
                    pattern=pattern,
                    recurring_type=recurring_type,
                    metadata={
                        "reason": reason,
                        "entity": entity,
                    },
                )
            classified_now += 0 if category.startswith("Others") else 1

        usd, inr = self._cost_estimate(len(pending))
        return output, GroqClassificationStats(classified_now, len(transactions), 1 if pending else 0, usd, inr)
