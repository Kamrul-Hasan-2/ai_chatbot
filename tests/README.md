# Tests

Unit tests for the BDStall chatbot.

## Setup

```bash
pip install -r requirements-dev.txt
```

## Run

```bash
# From the project root:
pytest

# Just the override tests:
pytest tests/test_overrides.py -v

# Single test:
pytest tests/test_overrides.py::TestBuyOverride::test_kibhabe_kinbo_overrides_anything -v
```

## What's covered today

- `tests/test_overrides.py` — every rule in `apply_post_groq_overrides()`.
  Each rule has a positive case (rule fires) and a negative case (rule
  does NOT fire) so future keyword/regex tweaks can't silently change
  the override surface.

## What to add next

When you fix a real-world bug — a misclassified Bangla phrase, a budget
parsing miss — add a test for that exact phrase here BEFORE shipping
the fix. That way the override pile stays principled instead of
accreting silently.
