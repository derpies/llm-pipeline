"""Tests for the HTTP request/UA/host classifiers."""

from llm_pipeline.http_analytics.classifier import (
    classify_host,
    classify_request,
    classify_useragent,
)
from llm_pipeline.http_analytics.models import (
    HostCategory,
    RequestCategory,
    UaCategory,
)


class TestClassifyRequest:
    def test_php_probe(self):
        m, p, cat = classify_request("GET /wp-login.php HTTP/1.1")
        assert cat == RequestCategory.PHP_PROBE
        assert m == "GET"
        assert p == "/wp-login.php"

    def test_tracking_pixel(self):
        _, _, cat = classify_request("GET /o?abc123 HTTP/1.1")
        assert cat == RequestCategory.TRACKING_PIXEL

    def test_click_tracking(self):
        _, _, cat = classify_request("GET /c/some-link HTTP/1.1")
        assert cat == RequestCategory.CLICK_TRACKING

    def test_api_call(self):
        _, _, cat = classify_request("POST /api/v1/data HTTP/1.1")
        assert cat == RequestCategory.API_CALL

    def test_websocket(self):
        _, _, cat = classify_request("GET /ws HTTP/1.1")
        assert cat == RequestCategory.WEBSOCKET

    def test_static_asset_css(self):
        _, _, cat = classify_request("GET /assets/style.css HTTP/1.1")
        assert cat == RequestCategory.STATIC_ASSET

    def test_static_asset_js(self):
        _, _, cat = classify_request("GET /bundle.js?v=123 HTTP/1.1")
        assert cat == RequestCategory.STATIC_ASSET

    def test_static_asset_image(self):
        _, _, cat = classify_request("GET /logo.png HTTP/1.1")
        assert cat == RequestCategory.STATIC_ASSET

    def test_static_asset_font(self):
        _, _, cat = classify_request("GET /fonts/roboto.woff2 HTTP/1.1")
        assert cat == RequestCategory.STATIC_ASSET

    def test_page_load_root(self):
        _, _, cat = classify_request("GET / HTTP/1.1")
        assert cat == RequestCategory.PAGE_LOAD

    def test_page_load_path(self):
        _, _, cat = classify_request("GET /dashboard/settings HTTP/1.1")
        assert cat == RequestCategory.PAGE_LOAD

    def test_page_load_html(self):
        _, _, cat = classify_request("GET /index.html HTTP/1.1")
        assert cat == RequestCategory.PAGE_LOAD

    def test_empty_request(self):
        m, p, cat = classify_request("")
        assert cat == RequestCategory.OTHER
        assert m == ""
        assert p == ""

    def test_post_non_api(self):
        _, _, cat = classify_request("POST /submit HTTP/1.1")
        assert cat == RequestCategory.OTHER

    def test_php_takes_precedence_over_path(self):
        """PHP probe should be detected even in a subpath."""
        _, _, cat = classify_request("GET /admin/config.php HTTP/1.1")
        assert cat == RequestCategory.PHP_PROBE

    def test_case_insensitive_php(self):
        _, _, cat = classify_request("GET /Admin.PHP HTTP/1.1")
        assert cat == RequestCategory.PHP_PROBE


class TestClassifyUseragent:
    def test_empty(self):
        assert classify_useragent("") == UaCategory.EMPTY

    def test_whitespace_only(self):
        assert classify_useragent("   ") == UaCategory.EMPTY

    def test_apple_mpp(self):
        assert classify_useragent("Mozilla/5.0 Safari", True) == UaCategory.APPLE_MPP

    def test_scanner_zgrab(self):
        assert classify_useragent("zgrab/0.x") == UaCategory.SCANNER

    def test_scanner_nikto(self):
        assert classify_useragent("Nikto/2.1.6") == UaCategory.SCANNER

    def test_scanner_sqlmap(self):
        assert classify_useragent("sqlmap/1.5.2") == UaCategory.SCANNER

    def test_curl(self):
        assert classify_useragent("curl/7.81.0") == UaCategory.CURL

    def test_wget(self):
        assert classify_useragent("wget/1.21") == UaCategory.CURL

    def test_python_requests(self):
        assert classify_useragent("python-requests/2.28.1") == UaCategory.CURL

    def test_bot_googlebot(self):
        assert classify_useragent("Googlebot/2.1 (+http://google.com/bot.html)") == UaCategory.BOT_CRAWLER

    def test_bot_facebook(self):
        assert classify_useragent("facebookexternalhit/1.1") == UaCategory.BOT_CRAWLER

    def test_email_client_thunderbird(self):
        assert classify_useragent("Thunderbird/91.0") == UaCategory.EMAIL_CLIENT

    def test_real_browser_chrome(self):
        assert classify_useragent(
            "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0.0.0 Safari/537.36"
        ) == UaCategory.REAL_BROWSER

    def test_real_browser_firefox(self):
        assert classify_useragent(
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Firefox/121.0"
        ) == UaCategory.REAL_BROWSER

    def test_unknown_ua(self):
        assert classify_useragent("CustomAgent/1.0") == UaCategory.OTHER

    def test_scanner_before_bot(self):
        """Scanner pattern should take precedence over bot-like patterns."""
        assert classify_useragent("masscan-bot/1.0") == UaCategory.SCANNER


class TestClassifyHost:
    def test_ontraport_com(self):
        assert classify_host("app.ontraport.com") == HostCategory.ONTRAPORT_COM

    def test_ontraport_com_bare(self):
        assert classify_host("ontraport.com") == HostCategory.ONTRAPORT_COM

    def test_ontralink_com(self):
        assert classify_host("track.ontralink.com") == HostCategory.ONTRALINK_COM

    def test_ontraport_net(self):
        assert classify_host("cdn.ontraport.net") == HostCategory.ONTRAPORT_NET

    def test_custom_domain(self):
        assert classify_host("example.com") == HostCategory.CUSTOM_DOMAIN

    def test_empty_host(self):
        assert classify_host("") == HostCategory.CUSTOM_DOMAIN

    def test_trailing_dot(self):
        assert classify_host("app.ontraport.com.") == HostCategory.ONTRAPORT_COM

    def test_case_insensitive(self):
        assert classify_host("APP.ONTRAPORT.COM") == HostCategory.ONTRAPORT_COM
