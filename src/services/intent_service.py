"""
Intent extraction (Groq), context merge, and intent_content normalisation.
Rules 5, 6, 7, 10, 12, 14.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from models.chatbot_config import VALID_INTENTS, CONTEXT_TTL_SECONDS, GROQ_SYSTEM_PROMPT_TEMPLATE
from utils.flow_helpers import extract_budget_range

logger = logging.getLogger(__name__)


class IntentProcessor:
    """Groq-based intent extraction and context merge logic."""

    def __init__(self, groq_client, groq_model: str, groq_answer_model: str,
                 category_validator) -> None:
        self.groq_client = groq_client
        self.groq_model = groq_model
        self.groq_answer_model = groq_answer_model
        self.category_validator = category_validator

    # ─────────────────────────────────────────────────────────────
    # Previous intent from DB (Rule 14)
    # ─────────────────────────────────────────────────────────────
    def load_previous_intent(self, user_id: str, fetch_fn) -> Dict:
        """Always fetch from DB — API context is source of truth."""
        try:
            prev = dict(fetch_fn(user_id) or {})
        except Exception as e:
            logger.warning("load_previous_intent failed: %s", e)
            return {}

        if not prev:
            return {}

        if not prev.get('cat') and not prev.get('category'):
            updated_at = prev.get('updated_at')
            if updated_at:
                try:
                    age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds()
                    if age > CONTEXT_TTL_SECONDS:
                        logger.info("Context expired for %s (age=%.0fs)", user_id, age)
                        return {}
                except Exception:
                    pass

        if prev.get('cat') and not prev.get('category'):
            prev['category'] = prev['cat']

        prev['prev_cat'] = prev.get('cat', '')
        prev['prev_brand'] = prev.get('brand', '')
        prev['prev_title'] = prev.get('title', '')

        for field in ('price_max', 'price_min'):
            try:
                v = int(prev[field]) if field in prev else None
                prev[field] = v if v and v > 0 else None
                prev[f'prev_{field}'] = prev[field]
            except (ValueError, TypeError):
                prev[field] = None
                prev[f'prev_{field}'] = None

        return prev

    # ─────────────────────────────────────────────────────────────
    # Groq extraction
    # ─────────────────────────────────────────────────────────────
    def step1_groq_extract(self, message: str, conversation_context: str,
                           previous_intent: Dict) -> Dict[str, Any]:
        if not self.groq_client:
            return self._minimal_fallback(message)

        sample_str = ", ".join(self.category_validator.names_english()[:30]) or "(none loaded yet)"
        system_prompt = GROQ_SYSTEM_PROMPT_TEMPLATE.format(
            sample_str=sample_str,
            previous_intent=json.dumps(previous_intent or {}, ensure_ascii=False)
        )
        user_prompt = (
            f"Recent conversation:\n{conversation_context or 'N/A'}\n\n"
            f"Current user message:\n{message}\n\nReturn ONLY the JSON object."
        )

        try:
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            return self._validate_groq_schema(parsed)
        except json.JSONDecodeError as e:
            logger.warning("Groq JSON parse failed: %s", e)
            return self._minimal_fallback(message)
        except Exception as e:
            logger.warning("Groq call failed: %s", e)
            return self._minimal_fallback(message)

    def _validate_groq_schema(self, parsed: Dict) -> Dict[str, Any]:
        intent = str(parsed.get('intent', 'unknown')).lower().strip()
        if intent not in VALID_INTENTS:
            intent = 'unknown'

        entities = parsed.get('entities') or {}

        def _coerce_price(v):
            if v is None or v == '':
                return None
            try:
                n = int(float(v))
                return n if 0 < n < 100_000_000 else None
            except (ValueError, TypeError):
                return None

        return {
            'intent': intent,
            'entities': {
                'category': str(entities.get('category') or '').strip(),
                'brand': str(entities.get('brand') or '').strip().lower(),
                'title': str(entities.get('title') or '').strip(),
                'price_max': _coerce_price(entities.get('price_max')),
                'price_min': _coerce_price(entities.get('price_min')),
            },
            'missing': [str(m) for m in (parsed.get('missing') or []) if isinstance(m, str)],
            'is_followup': bool(parsed.get('is_followup', False)),
            'confidence': max(0.0, min(1.0, float(parsed.get('confidence', 0.5)))),
        }

    def _minimal_fallback(self, message: str) -> Dict[str, Any]:
        budget = extract_budget_range(message)
        return {
            'intent': 'unknown',
            'entities': {
                'category': '', 'brand': '', 'title': '',
                'price_max': budget.get('max_price'),
                'price_min': budget.get('min_price'),
            },
            'missing': [],
            'is_followup': False,
            'confidence': 0.0,
        }

    # ─────────────────────────────────────────────────────────────
    # Context merge (Rules 6, 7, 10)
    # ─────────────────────────────────────────────────────────────
    def merge_intent_context(self, user_id: str, groq_result: Dict,
                             previous: Dict, intent: str,
                             clear_cache_fn) -> Dict:
        new_entities = groq_result['entities']
        new_category = new_entities.get('category', '')
        is_followup = groq_result.get('is_followup', False)

        prev_category = previous.get('category', '') or previous.get('cat', '')
        prev_brand = previous.get('brand', '')
        prev_title = previous.get('title', '')
        prev_price_max = previous.get('price_max')
        prev_price_min = previous.get('price_min')

        # Rule 6: category switch → FULL reset
        if new_category and prev_category and new_category.lower() != prev_category.lower():
            logger.info("🔄 Category switch %s → %s. Full reset.", prev_category, new_category)
            clear_cache_fn(user_id, clear_pending=True)
            return {
                'category': new_category, 'prev_cat': prev_category,
                'brand': new_entities.get('brand', ''), 'prev_brand': '',
                'title': new_entities.get('title', ''), 'prev_title': '',
                'price_max': new_entities.get('price_max'), 'prev_price_max': None,
                'price_min': new_entities.get('price_min'), 'prev_price_min': None,
                'updated_at': datetime.now().isoformat(),
            }

        has_only_refinement = (
            not new_category and (
                new_entities.get('price_max') is not None
                or new_entities.get('price_min') is not None
                or new_entities.get('brand')
                or new_entities.get('title')
            )
        )
        if has_only_refinement:
            is_followup = True

        if new_category:
            effective_category = new_category
        elif prev_category:
            effective_category = prev_category
        else:
            effective_category = ''

        if prev_category and not effective_category:
            clear_cache_fn(user_id, clear_pending=False)

        return {
            'category': effective_category,
            'prev_cat': prev_category,
            'brand': new_entities.get('brand') or prev_brand,
            'prev_brand': prev_brand,
            'title': new_entities.get('title') or prev_title,
            'prev_title': prev_title,
            'price_max': (new_entities.get('price_max')
                          if new_entities.get('price_max') is not None else prev_price_max),
            'prev_price_max': prev_price_max,
            'price_min': (new_entities.get('price_min')
                          if new_entities.get('price_min') is not None else prev_price_min),
            'prev_price_min': prev_price_min,
            'updated_at': datetime.now().isoformat(),
        }

    # ─────────────────────────────────────────────────────────────
    # intent_content normalisation (Rule 12)
    # ─────────────────────────────────────────────────────────────
    def intent_to_normalized(self, merged: Dict, message: str) -> Dict[str, Any]:
        new_cat = str(merged.get('category') or '').strip()
        effective_cat = new_cat or str(merged.get('prev_cat') or '').strip()
        new_brand = str(merged.get('brand') or '').strip().lower()
        effective_brand = new_brand or str(merged.get('prev_brand') or '').strip().lower()
        new_title = str(merged.get('title') or '').strip()
        effective_title = new_title or str(merged.get('prev_title') or '').strip()

        pm = merged.get('price_max')
        effective_price_max = pm if pm is not None and pm > 0 else (merged.get('prev_price_max') or 0)
        pn = merged.get('price_min')
        effective_price_min = pn if pn is not None and pn > 0 else (merged.get('prev_price_min') or 0)

        return {
            'title': effective_title, 'cat': effective_cat, 'brand': effective_brand,
            'price_max': effective_price_max, 'price_min': effective_price_min,
            'compare': '', 'buy': '',
            'updated_at': merged.get('updated_at', datetime.now().isoformat()),
        }

    def normalize_intent_content_payload(self, payload: Optional[Dict] = None) -> Dict[str, Any]:
        default: Dict[str, Any] = {
            'title': '', 'cat': '', 'brand': '',
            'price_max': 0, 'price_min': 0,
            'compare': '', 'buy': '',
        }
        if not isinstance(payload, dict):
            return default
        out = dict(default)
        out['title'] = str(payload.get('title') or '').strip()
        out['cat'] = str(payload.get('cat') or payload.get('category') or '').strip()
        out['brand'] = str(payload.get('brand') or '').strip().lower()
        try:
            out['price_max'] = int(payload.get('price_max') or 0)
        except (ValueError, TypeError):
            out['price_max'] = 0
        try:
            out['price_min'] = int(payload.get('price_min') or 0)
        except (ValueError, TypeError):
            out['price_min'] = 0
        out['compare'] = str(payload.get('compare') or '').strip()
        out['buy'] = str(payload.get('buy') or '').strip()
        if 'complain' in payload:
            out['complain'] = bool(payload['complain'])
        if 'exit' in payload:
            try:
                out['exit'] = 1 if int(payload['exit']) else 0
            except Exception:
                out['exit'] = 0
        if payload.get('product_url'):
            out['product_url'] = str(payload['product_url'])
        return out

    # ─────────────────────────────────────────────────────────────
    # Technical advice via Groq
    # ─────────────────────────────────────────────────────────────
    def get_technical_advice(self, message: str) -> Optional[str]:
        if not (self.groq_client and self.groq_answer_model):
            return None
        system_prompt = (
            "You are a helpful technical assistant for BDStall.com, a Bangladeshi e-commerce platform.\n"
            "Answer the user's technical question about product suitability or compatibility in 2-3 sentences.\n"
            "The user may write in English, Bangla, or Banglish. Always reply in the SAME language the user used.\n"
            "Be direct and helpful. Do NOT add disclaimers or recommend specific models or prices."
        )
        try:
            response = self.groq_client.chat.completions.create(
                model=self.groq_answer_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.2,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("technical_advice Groq call failed: %s", e)
            return None
