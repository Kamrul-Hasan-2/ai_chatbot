"""
src/services/humanizer_service.py — make canned replies sound human.

Wraps a Groq call that rewrites a template response in the user's
detected language and conversation style. The template is the source
of truth (links, prices, product titles); the humanizer only varies
the *chatty* surface around it.

Falls back to the original template on ANY failure — never raises.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# Patterns that must survive humanization untouched.
_PRESERVE_PATTERNS = (
    re.compile(r'https?://\S+'),                  # URLs
    re.compile(r'৳\s?\d[\d,]*'),                  # BDT prices like ৳20,000
    re.compile(r'\b\d{4,}\b'),                    # bare numbers (prices/IDs)
    re.compile(r'\bwww\.[\w.-]+'),                # bare www links
)


def _has_protected_payload(template: str) -> bool:
    """A template carrying URLs, prices, or numbered listings is
    structured — humanizing risks breaking it. Skip in that case."""
    return any(p.search(template) for p in _PRESERVE_PATTERNS)


def humanize(
    template: str,
    language: str = 'banglish',
    style: str = 'casual',
    user_message: str = '',
    groq_client=None,
    groq_model: str = '',
    *,
    force: bool = False,
    max_tokens: int = 120,
) -> str:
    """Rewrite a template warmly in the user's language.

    Args:
      template: the original canned response.
      language: 'bangla' | 'banglish' | 'english' (from UserProfile).
      style:    'casual' | 'formal'.
      user_message: what the user just said (gives Groq context).
      groq_client / groq_model: same Groq objects used elsewhere.
      force: rewrite even if the template contains URLs/prices/numbers.
             Off by default because rewriting structured content is risky.

    Returns:
      Humanized text on success, ORIGINAL template on any failure.
    """
    # Hard skips — never humanize empty or structured content unless forced.
    if not template or not template.strip():
        return template
    if not groq_client or not groq_model:
        return template
    if not force and _has_protected_payload(template):
        return template

    lang_name = {
        'bangla':   'Bangla (Bengali script)',
        'banglish': 'Banglish (Bangla in Latin script)',
        'english':  'English',
    }.get(language, 'Banglish')

    style_hint = ('casual and friendly — short sentences, warm tone'
                  if style == 'casual'
                  else 'polite and respectful — use স্যার or Sir')

    system = (
        "You are a warm BDStall customer support agent. Rewrite the AGENT_REPLY "
        "below so it sounds natural and human, NOT like a script.\n"
        f"- Reply in {lang_name}. Match the user's language exactly.\n"
        f"- Tone: {style_hint}.\n"
        "- Keep it concise — one or two short sentences max.\n"
        "- Preserve every fact, link, price, and number EXACTLY.\n"
        "- Do not add new offers, products, or promises.\n"
        "- Do not add a greeting if the user didn't greet.\n"
        "- Return ONLY the rewritten reply text. No quotes, no labels, no prose."
    )
    user_block = (
        f"USER_MESSAGE: {user_message or '(none)'}\n\n"
        f"AGENT_REPLY: {template}"
    )

    try:
        resp = groq_client.chat.completions.create(
            model=groq_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_block},
            ],
            temperature=0.6,
            max_tokens=max_tokens,
            timeout=4,
        )
        rewritten = (resp.choices[0].message.content or '').strip()
    except Exception as e:
        logger.warning("humanize failed (%s) — using template", e)
        return template

    # Safety net — if rewrite is empty, way too long, or stripped a URL the
    # template carried, fall back to the template.
    if not rewritten:
        return template
    if len(rewritten) > len(template) * 3 + 200:
        return template
    if 'http' in template and 'http' not in rewritten:
        return template

    return rewritten


def humanize_if_short(
    template: str,
    language: str = 'banglish',
    style: str = 'casual',
    user_message: str = '',
    groq_client=None,
    groq_model: str = '',
) -> str:
    """Humanize only short conversational replies (<200 chars, no URLs).

    Used for greetings, thanks, goodbyes, fallbacks — places where
    variety matters most and risk of breaking structure is lowest.
    """
    if not template or len(template) > 250:
        return template
    return humanize(
        template,
        language=language,
        style=style,
        user_message=user_message,
        groq_client=groq_client,
        groq_model=groq_model,
        max_tokens=80,
    )
