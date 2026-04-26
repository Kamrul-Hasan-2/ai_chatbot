"""
Category Validator — fully dynamic, API-driven.
================================================
Single source of truth: BDStall cat_list API.
No hardcoded category list, no hardcoded aliases.
Resolution: exact match, token match, fuzzy match (typos).
"""
import os
import re
import time
import logging
import threading
from difflib import SequenceMatcher
from typing import Optional, Dict, List
import requests

logger = logging.getLogger(__name__)


class CategoryValidator:
    def __init__(
        self,
        cat_list_url: str = "https://www.bdstall.com/api/chatbot/cat_list/",
        api_key: Optional[str] = None,
        refresh_interval_seconds: int = 3600,
        request_timeout: int = 8,
        fuzzy_threshold: float = 0.82,
    ):
        self.cat_list_url = cat_list_url
        self.api_key = api_key or os.getenv('BDSTALL_API_KEY', 'mkh677ddd2sxxkkdjff')
        self.refresh_interval = refresh_interval_seconds
        self.request_timeout = request_timeout
        self.fuzzy_threshold = fuzzy_threshold

        self._lock = threading.Lock()
        self._categories: List[Dict[str, str]] = []
        self._by_name_lower: Dict[str, Dict[str, str]] = {}
        self._by_bn_name: Dict[str, Dict[str, str]] = {}
        self._by_id: Dict[str, Dict[str, str]] = {}
        self._token_index: Dict[str, List[Dict[str, str]]] = {}
        self._bn_full_index: Dict[str, Dict[str, str]] = {}
        self._last_loaded: float = 0.0

        self.refresh(force=True)

    def refresh(self, force: bool = False) -> bool:
        now = time.time()
        if not force and (now - self._last_loaded) < self.refresh_interval and self._categories:
            return True
        with self._lock:
            if not force and (now - self._last_loaded) < self.refresh_interval and self._categories:
                return True
            try:
                response = requests.get(
                    self.cat_list_url,
                    params={'key': self.api_key},
                    timeout=self.request_timeout,
                )
                if response.status_code != 200:
                    logger.warning("[CAT_LIST] non-200: %s", response.status_code)
                    return False
                data = response.json()
                if not isinstance(data, list):
                    logger.warning("[CAT_LIST] bad payload type: %s", type(data))
                    return False

                cleaned = []
                by_name, by_bn, by_id, token_index, bn_full = {}, {}, {}, {}, {}
                for entry in data:
                    if not isinstance(entry, dict):
                        continue
                    cid = str(entry.get('category_id') or '').strip()
                    cname = str(entry.get('category_name') or '').strip()
                    bn = str(entry.get('bn_category_name') or '').strip()
                    if not cid or not cname:
                        continue
                    rec = {'category_id': cid, 'category_name': cname, 'bn_category_name': bn}
                    cleaned.append(rec)
                    by_name[cname.lower()] = rec
                    by_id[cid] = rec
                    if bn:
                        by_bn[bn.lower()] = rec
                        bn_full[bn] = rec
                    for tok in self._tokenize_en(cname):
                        if len(tok) >= 2:
                            token_index.setdefault(tok, []).append(rec)

                if not cleaned:
                    return False

                self._categories = cleaned
                self._by_name_lower = by_name
                self._by_bn_name = by_bn
                self._by_id = by_id
                self._token_index = token_index
                self._bn_full_index = bn_full
                self._last_loaded = now
                logger.info("[CAT_LIST] loaded %d categories", len(cleaned))
                return True
            except Exception as e:
                logger.warning("[CAT_LIST] refresh failed: %s", e)
                return False

    def _maybe_refresh(self) -> None:
        if (time.time() - self._last_loaded) > self.refresh_interval:
            self.refresh(force=False)

    def get_all(self) -> List[Dict[str, str]]:
        self._maybe_refresh()
        return list(self._categories)

    def names_english(self) -> List[str]:
        self._maybe_refresh()
        return [c['category_name'] for c in self._categories]

    def is_valid_name(self, name: str) -> bool:
        if not name:
            return False
        self._maybe_refresh()
        return name.strip().lower() in self._by_name_lower

    def get_by_id(self, cat_id: str) -> Optional[Dict[str, str]]:
        self._maybe_refresh()
        return self._by_id.get(str(cat_id).strip())

    def resolve(self, user_text: str) -> Optional[Dict[str, str]]:
        if not user_text:
            return None
        self._maybe_refresh()
        if not self._categories:
            return None
        text = str(user_text).strip()
        if not text:
            return None
        text_lower = text.lower()

        if text_lower in self._by_name_lower:
            return self._by_name_lower[text_lower]
        if text in self._bn_full_index:
            return self._bn_full_index[text]
        if text_lower in self._by_bn_name:
            return self._by_bn_name[text_lower]
        for bn_name, rec in self._bn_full_index.items():
            if bn_name and bn_name in text:
                return rec

        input_tokens = set(self._tokenize_en(text_lower))
        if input_tokens:
            best, best_score = None, 0
            for rec in self._categories:
                cat_tokens = set(self._tokenize_en(rec['category_name']))
                if not cat_tokens:
                    continue
                overlap = input_tokens & cat_tokens
                if not overlap:
                    continue
                if len(cat_tokens) > 1 and not cat_tokens.issubset(input_tokens):
                    if rec['category_name'].lower() not in text_lower:
                        continue
                score = len(overlap) * 100 + len(rec['category_name'])
                if score > best_score:
                    best_score = score
                    best = rec
            if best:
                return best

        if len(text_lower) <= 30:
            best_ratio, best_rec = 0.0, None
            for cname_lower, rec in self._by_name_lower.items():
                cands = [cname_lower] + self._tokenize_en(cname_lower)
                for cand in cands:
                    if not cand or len(cand) < 3:
                        continue
                    ratio = SequenceMatcher(None, text_lower, cand).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_rec = rec
            if best_rec and best_ratio >= self.fuzzy_threshold:
                return best_rec
        return None

    def resolve_from_message(self, message: str) -> Optional[Dict[str, str]]:
        if not message:
            return None
        self._maybe_refresh()
        if not self._categories:
            return None
        text = str(message)
        text_lower = text.lower()

        for bn_name, rec in self._bn_full_index.items():
            if bn_name and bn_name in text:
                return rec

        best, best_len = None, 0
        for cname_lower, rec in self._by_name_lower.items():
            if not cname_lower:
                continue
            if len(cname_lower) <= 4:
                if not re.search(rf'\b{re.escape(cname_lower)}\b', text_lower):
                    continue
            else:
                if cname_lower not in text_lower:
                    continue
            if len(cname_lower) > best_len:
                best_len = len(cname_lower)
                best = rec
        if best:
            return best

        input_tokens = set(self._tokenize_en(text_lower))
        if input_tokens:
            for tok in input_tokens:
                if len(tok) < 3:
                    continue
                matches = self._token_index.get(tok)
                if matches:
                    return min(matches, key=lambda r: len(r['category_name']))
        return None

    @staticmethod
    def _tokenize_en(text: str) -> List[str]:
        if not text:
            return []
        return re.findall(r'[a-z0-9]+', text.lower())
