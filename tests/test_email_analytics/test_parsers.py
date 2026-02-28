"""Tests for composite field parsing (clicktrackingid, listid, compliance)."""

from llm_pipeline.email_analytics.parsers import (
    ComplianceStatus,
    ListIdType,
    classify_listid,
    parse_clicktrackingid,
    parse_compliance_header,
)


class TestParseClicktrackingid:
    VALID = (
        "0.266907.69781.478016969.1342.104.0"
        ";1770154650;1755011403;1771487908;303835594.3662783;1"
    )

    def test_valid_parse(self):
        result = parse_clicktrackingid(self.VALID)
        assert result is not None
        assert result.xmrid.account_id == "266907"
        assert result.xmrid.contact_id == "69781"
        assert result.xmrid.drip_id == "104"
        assert result.xmrid.step_id == "0"
        assert result.xmrid.is_zero_cohort is False
        assert result.last_active == 1770154650
        assert result.contact_added == 1755011403
        assert result.op_queue_time == 1771487908
        assert result.op_queue_id == "303835594.3662783"
        assert result.marketing == 1
        # last_active != 0, so adjusted == raw
        assert result.last_active_adjusted == 1770154650

    def test_empty_string(self):
        assert parse_clicktrackingid("") is None

    def test_wrong_field_count(self):
        assert parse_clicktrackingid("a;b;c") is None

    def test_wrong_xmrid_field_count(self):
        assert parse_clicktrackingid("bad;1;2;3;4;5") is None

    def test_zero_cohort(self):
        raw = "0.0.69781.478016969.1342.104.0;100;200;300;q;0"
        result = parse_clicktrackingid(raw)
        assert result is not None
        assert result.xmrid.is_zero_cohort is True
        assert result.xmrid.account_id == "0"

    def test_last_active_zero_adjustment(self):
        raw = "0.266907.69781.478016969.1342.104.0;0;1755011403;1771487908;q;1"
        result = parse_clicktrackingid(raw)
        assert result is not None
        assert result.last_active == 0
        expected = 1755011403 + 15 * 24 * 3600
        assert result.last_active_adjusted == expected

    def test_last_active_zero_with_zero_contact_added(self):
        raw = "0.266907.69781.478016969.1342.104.0;0;0;1771487908;q;1"
        result = parse_clicktrackingid(raw)
        assert result is not None
        # Both zero — can't compute, stays at 0
        assert result.last_active_adjusted == 0

    def test_non_numeric_fields(self):
        assert parse_clicktrackingid("0.1.2.3.4.5.6;bad;2;3;q;0") is None

    def test_transactional_flag(self):
        raw = "0.266907.69781.478016969.1342.104.0;100;200;300;q;0"
        result = parse_clicktrackingid(raw)
        assert result is not None
        assert result.marketing == 0


class TestClassifyListid:
    def test_engagement_segments(self):
        for seg in ("VH", "H", "M", "L", "VL", "RO", "NM", "DS", "UK"):
            lid_type, code = classify_listid(f"SEG_E_{seg}")
            assert lid_type == ListIdType.ENGAGEMENT
            assert code == seg

    def test_private(self):
        lid_type, code = classify_listid("PRIVATE_acme")
        assert lid_type == ListIdType.PRIVATE
        assert code == ""

    def test_isolation(self):
        lid_type, code = classify_listid("ISO123")
        assert lid_type == ListIdType.ISOLATION
        assert code == ""

    def test_bespoke(self):
        lid_type, code = classify_listid("ClientXYZ")
        assert lid_type == ListIdType.BESPOKE
        assert code == ""

    def test_empty(self):
        lid_type, code = classify_listid("")
        assert lid_type == ListIdType.UNKNOWN
        assert code == ""

    def test_unknown_seg_e_suffix(self):
        lid_type, code = classify_listid("SEG_E_NEWFOO")
        assert lid_type == ListIdType.ENGAGEMENT
        assert code == "NEWFOO"


class TestParseComplianceHeader:
    def test_compliant(self):
        header = "compliant-from:example.com; compliant-mailfrom:mail.example.com;"
        assert parse_compliance_header(header) == ComplianceStatus.COMPLIANT

    def test_not_checked(self):
        header = "no-compliant-check: ontramail or opmailer"
        assert parse_compliance_header(header) == ComplianceStatus.NOT_CHECKED

    def test_empty(self):
        assert parse_compliance_header("") == ComplianceStatus.UNKNOWN

    def test_none(self):
        assert parse_compliance_header(None) == ComplianceStatus.UNKNOWN

    def test_garbage(self):
        assert parse_compliance_header("random-value") == ComplianceStatus.UNKNOWN

    def test_case_insensitive(self):
        header = "Compliant-From:example.com; Compliant-Mailfrom:mail.example.com;"
        assert parse_compliance_header(header) == ComplianceStatus.COMPLIANT
