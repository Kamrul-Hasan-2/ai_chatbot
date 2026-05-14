"""
Tests for humanizer_service.

The humanizer's job is to rewrite a template warmly when it can, and
fall back to the original template silently when it can't (Groq down,
template has structured content, rewrite fails sanity checks). These
tests cover the fallback contract — the *rewrite quality* is checked
manually because it depends on a live model.
"""
from services.humanizer_service import humanize, humanize_if_short


class TestFallbackContract:
    def test_no_client_returns_template_unchanged(self):
        out = humanize("Hello sir", groq_client=None, groq_model='x')
        assert out == "Hello sir"

    def test_empty_template_returns_empty(self):
        out = humanize("", groq_client=object(), groq_model='x')
        assert out == ""

    def test_structured_template_with_url_is_skipped(self):
        # URLs MUST be preserved exactly — humanizer skips by default.
        tmpl = "Please visit https://www.bdstall.com/ for details."
        out = humanize(tmpl, groq_client=object(), groq_model='x')
        assert out == tmpl

    def test_structured_template_with_price_is_skipped(self):
        tmpl = "Samsung Galaxy A55 এর মূল্য ৳45,000।"
        out = humanize(tmpl, groq_client=object(), groq_model='x')
        assert out == tmpl

    def test_structured_template_with_long_number_is_skipped(self):
        # Long bare numbers usually mean prices/IDs.
        tmpl = "আপনার অর্ডার নম্বর 12345 কনফার্ম করা হয়েছে।"
        out = humanize(tmpl, groq_client=object(), groq_model='x')
        assert out == tmpl


class TestHumanizeIfShort:
    def test_long_template_skipped(self):
        long_tmpl = "x" * 300
        out = humanize_if_short(long_tmpl, groq_client=object(), groq_model='x')
        assert out == long_tmpl

    def test_empty_template_returns_empty(self):
        assert humanize_if_short("", groq_client=object(), groq_model='x') == ""


class _FakeGroqMessage:
    def __init__(self, content): self.content = content


class _FakeGroqChoice:
    def __init__(self, content): self.message = _FakeGroqMessage(content)


class _FakeGroqCompletion:
    def __init__(self, content): self.choices = [_FakeGroqChoice(content)]


class _FakeGroqClient:
    """Minimal stub matching groq.Groq's API surface used by humanize()."""

    def __init__(self, response_text="", raise_exc=None):
        self._response = response_text
        self._raise = raise_exc

        class _Chat:
            def __init__(self, parent): self._parent = parent
            @property
            def completions(self):
                return self
            def create(self, **kwargs):
                if self._parent._raise:
                    raise self._parent._raise
                return _FakeGroqCompletion(self._parent._response)

        self.chat = _Chat(self)


class TestHumanizeRewriteWithFakeClient:
    def test_groq_failure_falls_back_to_template(self):
        client = _FakeGroqClient(raise_exc=RuntimeError("groq down"))
        tmpl = "আবার আসবেন স্যার"
        out = humanize(tmpl, groq_client=client, groq_model='m')
        assert out == tmpl

    def test_groq_empty_response_falls_back(self):
        client = _FakeGroqClient(response_text="")
        tmpl = "Most welcome!"
        out = humanize(tmpl, groq_client=client, groq_model='m')
        assert out == tmpl

    def test_groq_oversized_response_falls_back(self):
        # Rewrite that explodes in length is suspicious — keep template.
        client = _FakeGroqClient(response_text="x" * 5000)
        tmpl = "hi"
        out = humanize(tmpl, groq_client=client, groq_model='m')
        assert out == tmpl

    def test_groq_clean_rewrite_is_used(self):
        client = _FakeGroqClient(response_text="Welcome back! 😊")
        out = humanize("ধন্যবাদ", groq_client=client, groq_model='m')
        assert out == "Welcome back! 😊"
