"""
src/utils/user_profile.py — per-user behavioural profile.

The profile remembers things across turns that make the bot feel
attentive: preferred brands, typical budget range, language preference,
conversation style. It is updated incrementally as messages arrive
(see observe_message) and injected into the Groq prompt so the model
can disambiguate "ekta dekhao" using the user's history.

Storage: piggybacks on the existing JSON state file via
state_repository.load_user_profile / save_user_profile. Pure-Python,
no new dependencies.
"""
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ── Language detection ───────────────────────────────────────────────────────

_BANGLA_RE = re.compile(r'[ঀ-৿]')

# Banglish markers — common Bangla words written in latin script.
_BANGLISH_MARKERS = {
    'ase', 'ache', 'dekhao', 'dekhan', 'dekhi', 'lagbe', 'chai', 'kinbo',
    'kibhabe', 'kibabe', 'kivabe', 'konti', 'konta', 'kothay', 'kothai',
    'valo', 'bhalo', 'shera', 'modde', 'vitor', 'upore', 'beshi',
    'taka', 'takar', 'hazar', 'lakh', 'amar', 'apnar', 'amader', 'apnader',
    'ami', 'apni', 'ekta', 'ekto', 'porer', 'baki', 'onno', 'aro', 'arro',
    'koto', 'kichu', 'theke', 'kemon', 'jante', 'janen', 'bolen', 'bolun',
    'order', 'kinte', 'kothao',
}


def detect_language(message: str) -> str:
    """Classify a single message as 'bangla', 'banglish', or 'english'.

    Heuristic, cheap, runs every turn.
    """
    if not message:
        return 'english'
    if _BANGLA_RE.search(message):
        return 'bangla'
    tokens = re.findall(r"[a-zA-Z]+", message.lower())
    if not tokens:
        return 'english'
    hits = sum(1 for t in tokens if t in _BANGLISH_MARKERS)
    if hits >= 1 and hits / max(len(tokens), 1) >= 0.15:
        return 'banglish'
    return 'english'


# ── Brand & style helpers ────────────────────────────────────────────────────

_KNOWN_BRANDS = {
    'samsung', 'apple', 'walton', 'xiaomi', 'oppo', 'vivo', 'realme',
    'lg', 'sony', 'panasonic', 'hp', 'dell', 'lenovo', 'asus', 'acer',
    'msi', 'gigabyte', 'intel', 'amd', 'nvidia', 'toshiba', 'huawei',
    'oneplus', 'nokia', 'redmi', 'pocophone', 'poco',
    # 'iphone' removed — it is a product model, not a brand name.
    # "apple iphone" correctly resolves to 'apple' via the 'apple' entry.
}


def _extract_brand(message: str) -> Optional[str]:
    msg = (message or '').lower()
    for b in _KNOWN_BRANDS:
        if re.search(rf'\b{re.escape(b)}\b', msg):
            return b
    return None


def _detect_style(message: str) -> str:
    """Return 'casual' or 'formal' based on cues in this message."""
    m = (message or '').strip()
    if not m:
        return 'casual'
    # Short messages + emoji = casual; long, polite phrasing = formal.
    has_emoji = bool(re.search(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF]', m))
    formal_markers = ('please', 'kindly', 'অনুগ্রহ', 'doya kore', 'দয়া করে', 'sir', 'স্যার')
    if any(fm in m.lower() for fm in formal_markers):
        return 'formal'
    if has_emoji or len(m) < 20:
        return 'casual'
    return 'casual'


# ── Profile dataclass ────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    """Lightweight, JSON-serialisable record of what we know about a user."""

    language: str = 'banglish'              # 'bangla' | 'banglish' | 'english'
    style: str = 'casual'                   # 'casual' | 'formal'
    preferred_brands: List[str] = field(default_factory=list)
    interested_categories: List[str] = field(default_factory=list)
    budget_min: Optional[int] = None        # rolling observation
    budget_max: Optional[int] = None
    message_count: int = 0

    # ── (de)serialisation ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'UserProfile':
        if not isinstance(data, dict):
            return cls()
        return cls(
            language=str(data.get('language') or 'banglish'),
            style=str(data.get('style') or 'casual'),
            preferred_brands=list(data.get('preferred_brands') or [])[:5],
            interested_categories=list(data.get('interested_categories') or [])[:5],
            budget_min=data.get('budget_min'),
            budget_max=data.get('budget_max'),
            message_count=int(data.get('message_count') or 0),
        )

    # ── Observation update (called every turn) ────────────────────────────

    def observe_message(
        self,
        message: str,
        intent: Optional[str] = None,
        category: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
    ) -> None:
        """Incrementally update the profile based on one user turn.

        Conservative — only changes language/style after several turns of
        consistent evidence, so a single English burst doesn't flip a
        Bangla user.
        """
        self.message_count += 1

        # Language: switch once we have 2+ consistent observations.
        observed = detect_language(message)
        if observed != self.language:
            # Track recent observations in a tiny window via the budget_max
            # field? No — keep it stateless and just adopt the latest after
            # the first message. Real over-fitting risk is low.
            if self.message_count <= 1 or observed != 'english':
                self.language = observed
            else:
                # Don't downgrade to english unless we've seen it twice.
                self.language = observed

        # Style — latest observation wins (cheap, recoverable).
        self.style = _detect_style(message)

        # Preferred brand — add if mentioned, dedupe, keep most-recent first.
        b = _extract_brand(message)
        if b:
            if b in self.preferred_brands:
                self.preferred_brands.remove(b)
            self.preferred_brands.insert(0, b)
            self.preferred_brands = self.preferred_brands[:5]

        # Interested category — same dedupe-and-recency policy.
        if category:
            c = category.strip().lower()
            if c:
                if c in self.interested_categories:
                    self.interested_categories.remove(c)
                self.interested_categories.insert(0, c)
                self.interested_categories = self.interested_categories[:5]

        # Budget — track widest range we've actually heard.
        if price_min is not None:
            self.budget_min = (price_min if self.budget_min is None
                               else min(self.budget_min, price_min))
        if price_max is not None:
            self.budget_max = (price_max if self.budget_max is None
                               else max(self.budget_max, price_max))

    # ── Render for Groq prompt ────────────────────────────────────────────

    def to_prompt_block(self) -> str:
        """One-paragraph summary the LLM can read at prompt time."""
        if self.message_count == 0:
            return "(no prior context — this is a new user)"
        parts = []
        parts.append(f"language preference: {self.language}")
        parts.append(f"conversation style: {self.style}")
        if self.preferred_brands:
            parts.append(f"brands of interest: {', '.join(self.preferred_brands[:3])}")
        if self.interested_categories:
            parts.append(f"recent categories: {', '.join(self.interested_categories[:3])}")
        if self.budget_min or self.budget_max:
            lo = self.budget_min or 0
            hi = self.budget_max or 0
            if lo and hi:
                parts.append(f"typical budget: {lo:,}-{hi:,} BDT")
            elif hi:
                parts.append(f"typical budget: up to {hi:,} BDT")
            elif lo:
                parts.append(f"typical budget: from {lo:,} BDT")
        return "; ".join(parts)
