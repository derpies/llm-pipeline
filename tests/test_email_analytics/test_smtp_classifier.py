"""Tests for the SMTP response classifier."""


from llm_pipeline.email_analytics.models import SmtpCategory
from llm_pipeline.email_analytics.smtp_classifier import (
    classify_smtp_response,
    detect_provider,
    extract_smtp_code,
)


class TestSmtpCodeExtraction:
    def test_standard_code(self):
        assert extract_smtp_code("550 5.1.1 User unknown") == "550"

    def test_code_with_dash(self):
        assert extract_smtp_code("421-4.7.28 message") == "421"

    def test_code_with_dot(self):
        assert extract_smtp_code("250.2.0.0 OK") == "250"

    def test_no_code(self):
        assert extract_smtp_code("some random text") == ""

    def test_empty_message(self):
        assert extract_smtp_code("") == ""


class TestProviderDetection:
    def test_yahoo(self):
        assert detect_provider("mta7.am0.yahoodns.net") == "yahoo"

    def test_gmail(self):
        assert detect_provider("gmail-smtp-in.l.google.com") == "gmail"

    def test_microsoft(self):
        assert detect_provider("protection.outlook.com") == "microsoft"

    def test_unknown(self):
        assert detect_provider("mail.example.com") == ""


class TestClassifySmtpResponse:
    def test_throttling(self):
        result = classify_smtp_response("421 Too many connections from your IP")
        assert result.category == SmtpCategory.THROTTLING
        assert result.confidence >= 0.85
        assert result.smtp_code == "421"

    def test_yahoo_throttle(self):
        result = classify_smtp_response(
            "421 4.7.0 [TSS04] Messages from 10.0.0.1 temporarily deferred "
            "due to user complaints - mta7.am0.yahoodns.net"
        )
        assert result.category == SmtpCategory.THROTTLING
        assert result.provider_hint == "yahoo"

    def test_blacklist(self):
        result = classify_smtp_response("550 IP 10.0.0.1 is listed on Spamhaus")
        assert result.category == SmtpCategory.BLACKLIST

    def test_reputation(self):
        result = classify_smtp_response("550 Poor sender reputation")
        assert result.category == SmtpCategory.REPUTATION

    def test_auth_failure(self):
        result = classify_smtp_response("550 5.7.1 SPF fail: domain does not authorize sending IP")
        assert result.category == SmtpCategory.AUTH_FAILURE

    def test_content_rejection(self):
        result = classify_smtp_response("550 Content rejected due to policy violation")
        assert result.category == SmtpCategory.CONTENT_REJECTION

    def test_recipient_unknown(self):
        result = classify_smtp_response("550 5.1.1 The email account does not exist")
        assert result.category == SmtpCategory.RECIPIENT_UNKNOWN
        assert result.smtp_code == "550"

    def test_no_such_user(self):
        result = classify_smtp_response("550 No such user here")
        assert result.category == SmtpCategory.RECIPIENT_UNKNOWN

    def test_network_timeout(self):
        result = classify_smtp_response("Connection timed out")
        assert result.category == SmtpCategory.NETWORK

    def test_success(self):
        result = classify_smtp_response("250 OK id=abc123")
        assert result.category == SmtpCategory.SUCCESS

    def test_empty_message(self):
        result = classify_smtp_response("")
        assert result.category == SmtpCategory.OTHER
        assert result.confidence == 0.0

    def test_unknown_message(self):
        result = classify_smtp_response("something completely unrecognized xyz123")
        assert result.category == SmtpCategory.OTHER
        assert result.matched_pattern == "no_match"

    def test_gmail_dmarc(self):
        result = classify_smtp_response("550-5.7.26 This mail is not authenticated")
        assert result.category == SmtpCategory.AUTH_FAILURE
        assert result.provider_hint == "gmail"

    def test_rate_limit(self):
        result = classify_smtp_response("Please retry, rate limit exceeded")
        assert result.category == SmtpCategory.THROTTLING

    def test_mailbox_full(self):
        result = classify_smtp_response("452 Mailbox full, quota exceeded")
        assert result.category == SmtpCategory.POLICY
