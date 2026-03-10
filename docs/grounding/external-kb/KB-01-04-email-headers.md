# Email Headers and What They Reveal

Email headers are the primary diagnostic artifact for tracing delivery problems. Every message carries a block of headers that records its path from origination to final delivery, including authentication verdicts, spam filter scores, routing decisions, and encryption status. Reading headers systematically turns a black-box delivery failure into a traceable sequence of events with actionable root causes.

This article covers how to read headers, what specific headers mean, how to correlate header data with delivery problems, and what to look for when triaging issues across different receiving environments.

## Header Order and Reading Direction

RFC 5322 requires each Mail Transfer Agent (MTA) in the delivery chain to prepend -- not append -- headers to the message. This means the **bottom** of the header block represents the originating system, and the **top** represents the final receiving MTA. To trace a message chronologically, read from bottom to top.

Each `Received:` header includes a timestamp. Calculating the delta between consecutive `Received:` headers reveals per-hop latency:

- **Under 2 seconds per hop**: Normal transit through a well-connected MTA.
- **5-30 seconds**: Possible DNS lookup delays, brief queue processing, or minor congestion. Not concerning on its own.
- **30-120 seconds**: Indicates queuing at the receiving server. This may reflect greylisting (where the receiving MTA temporarily rejects the first connection with a `450` or `451` code and expects a retry). Greylisting delays typically fall in the 60-300 second range.
- **300-900 seconds (5-15 minutes)**: Strongly suggests a deliberate `4xx` temporary rejection. The sending MTA queued the message and retried after its configured retry interval. Check the sending MTA's logs for a corresponding `450`/`451`/`452` response on the first attempt.
- **Over 3,600 seconds (1+ hours)**: The message was deferred, likely due to rate limiting or throttling by the receiver. This pattern is common when sending to Gmail, Microsoft, or Yahoo at volumes that exceed their per-IP or per-domain rate limits.

Note that timestamps across different MTAs may be slightly out of sync if NTP is not properly configured. Clock skew of a few seconds is common; skew of minutes or more indicates an infrastructure problem on one of the hops.

## The Received Header in Detail

The `Received:` header is defined by RFC 5321 and is the most structurally complex header you will routinely read. A typical example:

```
Received: from mail-out.example.com (mail-out.example.com [198.51.100.25])
        by mx.recipient.com (Postfix) with ESMTPS id 4ABC123DEF
        for <user@recipient.com>; Tue, 14 Jan 2025 09:23:45 -0500 (EST)
```

The components to extract:

- **`from` clause**: The sending server's self-reported HELO/EHLO hostname (`mail-out.example.com`) and the actual connecting IP in brackets (`198.51.100.25`). A mismatch between these -- for example, a HELO of `mail-out.example.com` but a reverse DNS lookup of the IP resolving to `unrelated-host.provider.net` -- is a signal of misconfiguration that can negatively affect spam scoring.
- **`by` clause**: The receiving server's hostname and MTA software (here, Postfix). This identifies which hop you are examining.
- **`with` clause**: The protocol used. `ESMTP` means unencrypted SMTP with extensions. `ESMTPS` means STARTTLS was negotiated. `ESMTPSA` means SMTP with both STARTTLS and authentication (typically a client submitting mail). `LMTP` indicates local delivery between components within the same mail system.
- **`id` clause**: The receiving MTA's internal queue ID. This is the key to correlating the header with the receiving server's logs.
- **`for` clause**: The envelope recipient. This may be absent in multi-recipient messages to protect recipient privacy.
- **Timestamp**: The date, time, and timezone when the receiving MTA accepted the message.

**TLS status is diagnostic.** Gmail displays a red unlocked padlock icon for messages received without TLS. Microsoft and Yahoo also factor TLS usage into their filtering. If you see `ESMTP` (no S) on the final hop to a major mailbox provider, your sending MTA is not negotiating STARTTLS, which may contribute to spam classification. RFC 8314 (documented standard) recommends TLS for all SMTP connections, and major providers penalize its absence (industry-confirmed behavior by Google, Microsoft, and Yahoo).

## Authentication-Results

This is the single most important header for deliverability diagnostics. Defined in RFC 8601, it is added by the receiving MTA and consolidates SPF, DKIM, and DMARC verdicts into one location. A complete example:

```
Authentication-Results: mx.google.com;
    dkim=pass header.i=@example.com header.s=sel1 header.b=aBcDeFgH;
    spf=pass (google.com: domain of bounce+tag@example.com designates 198.51.100.25 as permitted sender) smtp.mailfrom=bounce+tag@example.com;
    dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=example.com
```

### SPF Result Fields

The `spf=` result tells you whether the sending IP was authorized by the envelope sender's SPF record:

| Result | Meaning | Implication |
|---|---|---|
| `pass` | Sending IP is in the SPF record | Positive signal. No action needed. |
| `neutral` | SPF record uses `?all` | Equivalent to no SPF policy. Weak negative. |
| `softfail` | SPF record uses `~all` | The IP is not authorized but the domain owner has not committed to a hard failure. Most receivers treat this as a minor negative signal; it will not cause rejection on its own but contributes to spam scoring. |
| `fail` | SPF record uses `-all` | The IP is explicitly unauthorized. Strong negative signal. Some receivers reject outright on `spf=fail`; others use it as a heavy negative factor. |
| `temperror` | DNS timeout or lookup failure | Transient. The message may be deferred. Check whether the SPF record's DNS is responsive. |
| `permerror` | SPF record is syntactically invalid | The SPF record itself is broken (e.g., exceeding the 10 DNS lookup limit, invalid syntax). This requires immediate remediation of the DNS record. |

The `smtp.mailfrom=` field shows the envelope sender (RFC 5321 MAIL FROM), which is the identity SPF evaluates. This is distinct from the `From:` header the user sees. When these two domains differ, SPF may pass but DMARC alignment may fail.

### DKIM Result Fields

The `dkim=` result reports whether the DKIM signature was cryptographically valid:

| Result | Meaning | Common Cause |
|---|---|---|
| `pass` | Signature verified successfully | Normal. The `header.s=` field shows which selector was used; `header.i=` shows the signing identity. |
| `fail` | Signature verification failed | Body or signed headers were modified in transit. Common causes: mailing list software adding footers, forwarding services rewriting headers, content-inspection gateways altering the message body. The detail field often specifies `body hash did not verify` (body was changed) or `signature verification failed` (header was changed or key mismatch). |
| `neutral` | Signature exists but cannot be evaluated | Rare. Usually indicates the public key in DNS is missing or unparseable. |
| `temperror` | DNS lookup for the public key timed out | Transient. Check DNS availability for the selector record (`sel1._domainkey.example.com`). |
| `permerror` | Permanent error in DKIM evaluation | The selector record exists but is malformed, or the signing algorithm is unsupported. |

The `header.b=` field contains the first 8 characters of the DKIM signature, useful for identifying which specific signature was evaluated when a message carries multiple DKIM signatures (common with ESPs that sign with both their own domain and the customer's domain).

### DMARC Result Fields

DMARC evaluation combines SPF and DKIM results with an alignment check against the `From:` header domain:

- **`dmarc=pass`**: At least one of SPF or DKIM both passed and aligned with the `From:` domain.
- **`dmarc=fail`**: Neither SPF nor DKIM passed with alignment. The `p=` value in parentheses shows the domain's published DMARC policy (`NONE`, `QUARANTINE`, or `REJECT`). The `dis=` value shows the action the receiver actually took (`NONE`, `QUARANTINE`, or `REJECT`). Note: receivers are not obligated to enforce the published policy. Google, for example, may quarantine a message even when `p=REJECT` during their initial rollout phase for a domain.

**Alignment matters.** SPF alignment requires the domain in `smtp.mailfrom` to match the domain in the `From:` header (or be a subdomain of it, under relaxed alignment). DKIM alignment requires the `d=` domain in the DKIM signature to match the `From:` header domain. A common failure pattern: SPF passes for the ESP's bounce domain (e.g., `bounce.esp-provider.com`) but the `From:` header is `marketing@yourdomain.com`. SPF passed but SPF alignment failed. If DKIM is also not signing with `yourdomain.com`, DMARC fails.

## ARC (Authenticated Received Chain) Headers

Defined in RFC 8617, ARC headers preserve authentication results across message forwarding. When a mailing list or forwarding service modifies a message (breaking DKIM) and relays it from an IP not in the original sender's SPF record, authentication fails at the final destination. ARC provides a chain of custody so the final receiver can evaluate whether the intermediary was trustworthy.

ARC adds three headers per hop:

- **`ARC-Authentication-Results`**: The authentication results as seen by the intermediary before it modified the message.
- **`ARC-Message-Signature`**: A DKIM-like signature over the message as the intermediary received it.
- **`ARC-Seal`**: A signature over the ARC headers themselves, preventing tampering with the chain.

Each set is numbered with `i=1`, `i=2`, etc., incrementing at each ARC-participating hop. If the final `ARC-Seal` is `cv=pass` (chain valid), the receiving MTA can trust the chain. If `cv=fail`, the chain has been tampered with or a non-ARC-aware intermediary broke it.

**Practical relevance:** Gmail is the primary consumer of ARC data (documented in Google's support pages). When a message arrives at Gmail with `dmarc=fail` but a valid ARC chain showing `dmarc=pass` at an earlier hop from a trusted intermediary, Gmail may override the DMARC failure. This is particularly important for university and corporate environments that use mailing lists.

## Spam Filter Verdict Headers

### X-Spam-Status and X-Spam-Score (SpamAssassin)

SpamAssassin and its derivatives write their verdicts into headers:

```
X-Spam-Status: No, score=2.3 required=5.0 tests=BAYES_20,DKIM_SIGNED,
    DKIM_VALID,DKIM_VALID_AU,SPF_PASS,HTML_MESSAGE,MAILING_LIST_MULTI
X-Spam-Score: 2.3
```

Key diagnostics:

- **`score` vs. `required`**: The message's spam score relative to the classification threshold. A score of 2.3 with a threshold of 5.0 has 2.7 points of headroom. Scores within 1.5-2.0 points of the threshold are at risk -- minor changes in content, reputation, or sending patterns could push future messages over.
- **`tests` list**: Each rule that fired, directly identifying what triggered scoring. Common actionable rules:
  - `BAYES_50` through `BAYES_99`: Bayesian classifier confidence. `BAYES_99` adds approximately 3.5 points and indicates the content strongly resembles previously identified spam.
  - `RDNS_NONE`: No reverse DNS for the sending IP. Adds approximately 1.3 points. Fix by configuring proper PTR records.
  - `SPF_FAIL`: SPF hard failure. Adds approximately 1.0 points.
  - `DKIM_ADSP_DISCARD`: The sender's DKIM policy says unsigned messages should be discarded. Adds approximately 2.0+ points.
  - `URIBL_BLOCKED` or `URIBL_BLACK`: URLs in the message body appear on a URI-based blocklist. Adds approximately 1.7-3.0 points.
  - `HTML_IMAGE_RATIO_02`: Images constitute more than 80% of the HTML content. Adds approximately 0.5-1.5 points depending on configuration.

### X-MS-Exchange-Organization-SCL (Microsoft)

Microsoft Exchange and Microsoft 365 use the Spam Confidence Level (SCL), an integer ranging from -1 to 9:

| SCL Value | Meaning | Typical Action |
|---|---|---|
| -1 | Filtering bypassed | Message from a trusted sender, internal relay, or transport rule exemption |
| 0-1 | Not spam | Inbox delivery |
| 2-4 | Low probability of spam | Inbox delivery in most configurations |
| 5-6 | Spam | Delivered to Junk Email folder |
| 7-8 | High-confidence spam | Delivered to Junk Email folder or quarantined (depending on admin policy) |
| 9 | High-confidence phishing | Quarantined; not delivered to user at all |

This header is the fastest way to diagnose junk placement in Exchange/Microsoft 365 environments. If you see `SCL: 5` or above, the message was flagged by Microsoft's filtering stack. Note that SCL is an internal Microsoft value -- it is not part of any RFC standard and its interpretation is specific to Microsoft environments.

Microsoft also adds `X-Forefront-Antispam-Report` with detailed filtering metadata, including `SFV` (Spam Filter Verdict), `IPV` (IP reputation verdict), and `CIP` (connecting IP). The `SFV=SPM` value means the message was classified as spam; `SFV=SKS` means it was marked as spam by a transport rule; `SFV=NSPM` means not spam.

### X-Google-DKIM-Signature and Google-Specific Headers

Gmail adds its own DKIM signature (`X-Google-DKIM-Signature`) to outbound and internally processed messages. This is Google's internal integrity mechanism and is not relevant to your sending authentication. Do not confuse it with your own DKIM signature.

Gmail does not expose a spam score header to end users. Filtering decisions are opaque in message headers. Diagnostics for Gmail delivery must rely on `Authentication-Results`, Google Postmaster Tools data, and observed placement behavior rather than any score-based header.

## Envelope vs. Header Identities

A persistent source of confusion in header analysis is the distinction between envelope and header identities. Understanding this distinction is essential for diagnosing authentication alignment failures.

| Identity | Where It Appears | Protocol Role |
|---|---|---|
| Envelope sender (MAIL FROM) | `Return-Path:` header (added by receiving MTA) and `smtp.mailfrom` in `Authentication-Results` | Used for SPF evaluation and bounce delivery |
| Header From | `From:` header | Displayed to the end user; used for DMARC alignment |
| Envelope recipient (RCPT TO) | `Delivered-To:` or `X-Original-To:` headers (MTA-dependent) | Determines routing; not visible in all header sets |

**Common diagnostic scenario:** A message shows `spf=pass` in `Authentication-Results` but `dmarc=fail`. The explanation is almost always an alignment mismatch: the `Return-Path` domain (which SPF evaluated) does not match the `From:` header domain. This occurs when an ESP uses its own bounce domain for MAIL FROM (e.g., `bounces.esp-provider.com`) rather than the customer's domain. The fix is to configure custom return-path/bounce domain alignment at the ESP, or ensure DKIM is signing with the customer's domain so DMARC can pass via DKIM alignment instead.

## List-Unsubscribe and List-Unsubscribe-Post

RFC 2369 defines `List-Unsubscribe` and RFC 8058 defines `List-Unsubscribe-Post` for one-click unsubscribe:

```
List-Unsubscribe: <https://example.com/unsub?id=abc123>, <mailto:unsub@example.com?subject=unsubscribe>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

As of February 2024, Gmail and Yahoo require bulk senders (those sending more than 5,000 messages per day to their domains) to include both headers. This is a documented requirement published by both providers, not merely a best practice. Absence of these headers on bulk commercial mail is a confirmed negative filtering signal.

Requirements specifics:

- The `List-Unsubscribe` header must contain an HTTPS URL (not just a mailto link) for Gmail's one-click mechanism.
- The `List-Unsubscribe-Post` header must contain exactly `List-Unsubscribe=One-Click`.
- The unsubscribe endpoint must process the request within 2 days (Google's stated requirement).
- Transactional messages (order confirmations, password resets) are exempt, but there is no header-based mechanism to declare a message as transactional. The distinction is based on content and sending behavior.

## Received-SPF

An older header format for SPF results, predating the consolidation into `Authentication-Results`. Defined in RFC 7208, it is still added by some MTAs alongside `Authentication-Results`:

```
Received-SPF: pass (google.com: domain of user@example.com designates 198.51.100.25 as permitted sender) client-ip=198.51.100.25;
```

This header is useful as a cross-reference when the `Authentication-Results` header is truncated, overwritten by an intermediate gateway, or absent. The information is redundant when `Authentication-Results` is present and complete.

## What Problems Look Like in Headers

### SPF Failure Due to Unauthorized IP

```
Authentication-Results: mx.google.com;
    spf=fail (google.com: domain of user@example.com does not designate
    203.0.113.50 as permitted sender) smtp.mailfrom=user@example.com
```

The IP `203.0.113.50` is not in the SPF record for `example.com`. Remediation: add the IP (or its range) to the domain's SPF record via an `include:` or `ip4:`/`ip6:` mechanism.

### DKIM Broken by Forwarding or Content Modification

```
Authentication-Results: mx.google.com;
    dkim=fail (body hash did not verify) header.i=@example.com header.s=sel1
```

The `body hash did not verify` detail means the message body was altered after signing. Common causes: mailing list footers appended by list software (Mailman, Listserv), email security gateways inserting disclaimers, forwarding services rewriting URLs for click tracking.

### DMARC Alignment Failure

```
Authentication-Results: mx.google.com;
    dkim=pass header.i=@esp-provider.com header.s=s1;
    spf=pass smtp.mailfrom=bounces@esp-provider.com;
    dmarc=fail header.from=yourdomain.com
```

Both SPF and DKIM passed, but neither aligned with the `From:` domain `yourdomain.com`. DKIM signed with `esp-provider.com`; SPF passed for `esp-provider.com`. Neither matches `yourdomain.com`. Fix: configure the ESP to DKIM-sign with `yourdomain.com` and/or use a custom bounce domain under `yourdomain.com`.

### Message Narrowly Escaping Spam Classification

```
X-Spam-Status: No, score=4.2 required=5.0 tests=BAYES_50,HTML_IMAGE_RATIO_02,
    MIME_HTML_ONLY,RDNS_NONE
```

Score is 4.2 against a 5.0 threshold -- only 0.8 points of headroom. The `RDNS_NONE` rule (no reverse DNS, typically worth 1.3 points) combined with `HTML_IMAGE_RATIO_02` (heavy image content) puts this message at immediate risk. A minor reputation shift or additional content trigger will push it over. Remediate by configuring reverse DNS for the sending IP and reducing the image-to-text ratio in the HTML content.

### Greylisting Delay

```
Received: from sender.example.com (sender.example.com [198.51.100.25])
    by mx.recipient.com with ESMTPS; Tue, 14 Jan 2025 09:28:12 -0500
Received: from internal.example.com (internal.example.com [10.0.0.5])
    by sender.example.com with ESMTP; Tue, 14 Jan 2025 09:22:45 -0500
```

The 327-second gap (5 minutes 27 seconds) between the second and first `Received:` headers on a single hop indicates the first connection was rejected with a `4xx` code and the sending MTA retried after its queue interval. The sending MTA's logs will show a `450` or `451` response on the initial attempt.

### Missing TLS on Final Hop

```
Received: from sender.example.com (sender.example.com [198.51.100.25])
    by mx.google.com with ESMTP id abc123;
    Tue, 14 Jan 2025 09:23:45 -0800
```

The `with ESMTP` (not `ESMTPS`) on a hop to `mx.google.com` means TLS was not negotiated. Gmail will display an "unencrypted" warning to the recipient. This may also contribute to negative spam scoring. The sending MTA should be configured to support STARTTLS and present a valid certificate. Check that the sending server's TLS libraries are up to date and that STARTTLS is enabled in its configuration (e.g., `smtpd_tls_security_level = may` in Postfix).

## Practical Header Extraction

### From Gmail

In Gmail's web interface: open the message, click the three-dot menu, select "Show original." This displays the full headers plus a summary of SPF, DKIM, and DMARC results. The "Download original" option provides the complete `.eml` file.

### From Microsoft 365/Outlook

In Outlook on the web: open the message, click the three-dot menu, select "View message details" (or "View message source" depending on version). In the Outlook desktop client: open the message, go to File > Properties, and the headers appear in the "Internet headers" text box.

### Programmatic Extraction

Most MTAs can be configured to store headers in logs or databases. Postfix logs queue IDs that can be matched to `Received:` header IDs. For programmatic analysis at scale, parse headers using libraries such as Python's `email.parser` module, which correctly handles header folding and multi-line values per RFC 5322.

### Header Analysis Tools

MXToolbox Header Analyzer (`mxtoolbox.com/EmailHeaders.aspx`) and Google's Admin Toolbox Messageheader tool (`toolbox.googleapps.com/apps/messageheader/`) parse raw headers into a visual hop-by-hop timeline with latency calculations. These are useful for quick visual inspection but do not replace the ability to read headers directly for complex diagnostics.

## Key Takeaways

- **Read `Received:` headers bottom-to-top** to trace the message path chronologically. Timestamp gaps over 300 seconds between hops strongly indicate greylisting or throttling-induced deferrals; gaps over 3,600 seconds suggest rate limiting by the receiving ISP.
- **`Authentication-Results` is the single most important diagnostic header.** It consolidates SPF, DKIM, and DMARC verdicts in one place. Pay particular attention to alignment: SPF and DKIM can both pass while DMARC fails if neither result aligns with the `From:` header domain.
- **Distinguish envelope vs. header identities.** The `Return-Path` (envelope sender) is what SPF checks; the `From:` header is what the user sees and what DMARC aligns against. Mismatches between these are the most common cause of DMARC failure when SPF itself passes.
- **`List-Unsubscribe-Post` is a hard requirement, not a best practice**, for bulk senders exceeding 5,000 messages per day to Gmail and Yahoo domains, enforced since February 2024. Absence is a documented negative filtering signal.
- **Microsoft SCL values of 5 or above indicate junk folder placement.** Combined with the `X-Forefront-Antispam-Report` header, SCL is the fastest diagnostic path for Exchange and Microsoft 365 delivery issues. SpamAssassin's `X-Spam-Status` provides equivalent detail in non-Microsoft environments, including the specific rules that contributed to the score.


