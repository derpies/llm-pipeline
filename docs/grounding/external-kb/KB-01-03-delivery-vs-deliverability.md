# The Difference Between Delivery and Deliverability

## Core Definitions

**Delivery** is whether the receiving mail transfer agent (MTA) accepted the message during the SMTP transaction. A message is "delivered" when the receiving server returns a `250 OK` response after the `DATA` command completes. Delivery is binary at the transaction level: the server either accepted the message or it did not.

**Deliverability** is what happens after acceptance — whether the message is placed in the recipient's inbox, routed to the spam/junk folder, or placed in a secondary tab (e.g., Gmail's Promotions or Updates tabs). Deliverability is determined by the receiving system's content filters, reputation scoring, and user-level engagement signals, all of which operate after the SMTP transaction has concluded and the `250` response has already been issued.

The critical implication: a sender can achieve a 99.5% delivery rate while simultaneously having 40% or more of accepted messages routed to spam. SMTP logs will show near-perfect delivery. Recipient experience will be that nearly half of messages are invisible. These are independent metrics driven by different mechanisms, and conflating them is the single most common diagnostic error in email operations.

## The SMTP Transaction and Where Delivery Ends

Understanding exactly where delivery ends and deliverability begins requires clarity on the SMTP transaction sequence. Per RFC 5321, a typical successful transaction proceeds as follows:

1. **Connection establishment** — TCP connection to port 25 (or 587 for submission).
2. **EHLO/HELO** — Sender identifies itself.
3. **MAIL FROM** — Sender specifies the envelope sender (RFC 5321.MailFrom).
4. **RCPT TO** — Sender specifies the envelope recipient(s).
5. **DATA** — Sender transmits the message headers and body, terminated by `<CRLF>.<CRLF>`.
6. **Server response** — The receiving MTA responds with a status code.

A `250` response to the `DATA` command means the receiving server has accepted responsibility for the message. This is the point at which "delivery" is complete. Everything that happens to the message after this point — spam filtering, tab categorization, content scanning, quarantining — falls under "deliverability" and produces no SMTP-level signal back to the sender.

Some servers perform partial filtering before issuing the `250`. For example, a server might reject at `RCPT TO` (producing a `550 5.1.1 User unknown`) or reject after `DATA` but before issuing the `250` (producing a `554 5.7.1 Message rejected`). These pre-acceptance rejections are delivery failures, not deliverability failures, because the server never accepted the message.

**Fact (RFC 5321):** The `250` response to `DATA` means the receiving server has accepted the message and taken responsibility for it. The RFC does not guarantee inbox placement — only that the server will attempt to deliver to the recipient's mailbox or generate a non-delivery notification.

## What Delivery Problems Look Like in Logs

Delivery failures are explicit and observable. The receiving server communicates the problem through SMTP response codes defined in RFC 5321 (basic codes) and RFC 3463 (enhanced status codes). These appear directly in MTA logs and bounce messages.

### Permanent Failures (5xx)

Permanent failures indicate the server will not accept this message regardless of retry. The sender should not reattempt delivery for the same message to the same recipient.

| Code | Enhanced Code | Meaning | Typical Cause |
|------|--------------|---------|---------------|
| `550` | `5.1.1` | User unknown | Invalid recipient address; hard bounce. Remove from list immediately. |
| `550` | `5.7.1` | Message rejected (policy) | Content policy, authentication failure, or sender reputation block. |
| `551` | `5.1.6` | Destination mailbox moved | Address has been redirected (rare in practice). |
| `553` | `5.1.3` | Invalid address format | Malformed email address syntax. |
| `554` | `5.7.1` | Service unavailable / blocked | IP or domain blocklisted. Typically references a specific blocklist (e.g., "blocked using Spamhaus SBL"). |
| `556` | `5.1.10` | Recipient not accepting mail | Permanent rejection at the recipient level (RFC 7504). |
| `550` | `5.7.26` | Authentication failure | DMARC or authentication policy rejection (RFC 7489). The receiving server's DMARC verification failed and the domain policy specifies `p=reject`. |

### Temporary Failures (4xx)

Temporary failures indicate the server may accept the message later. The sending MTA should retry according to its queue configuration. Most MTAs retry on an exponential backoff schedule (e.g., 15 min, 30 min, 1 hr, 2 hr, 4 hr) for up to 72 hours before converting to a permanent failure.

| Code | Enhanced Code | Meaning | Typical Cause |
|------|--------------|---------|---------------|
| `421` | `4.7.0` | Try again later | Rate limiting, greylisting, or temporary server load. |
| `450` | `4.2.1` | Mailbox temporarily unavailable | Recipient's mailbox is locked or at quota temporarily. |
| `451` | `4.7.1` | Temporary policy rejection | Greylisting (server rejects first attempt from unknown sender/IP pair, expects retry). |
| `452` | `4.5.3` | Too many recipients | Per-connection or per-session recipient limit exceeded. Typical limits: 100 recipients per connection (Gmail), 50 per transaction (some corporate servers). |
| `452` | `4.2.2` | Mailbox full | Recipient's mailbox has exceeded its storage quota. |

### Connection-Level Failures

These occur before the SMTP conversation begins and appear in logs as connection errors, not SMTP codes:

- **Connection refused (TCP RST or ECONNREFUSED):** The receiving server's port 25 is not listening, often due to server misconfiguration, firewall rules, or intentional blocking of the sender's IP range.
- **Connection timeout:** No response within the timeout window (RFC 5321 recommends 5 minutes for the initial greeting). May indicate network issues, firewall silently dropping packets, or deliberate throttling.
- **TLS handshake failure:** If the sender requires TLS (e.g., via DANE/TLSA or MTA-STS policy) and the handshake fails, the connection drops. Logs show OpenSSL or TLS library errors rather than SMTP codes.
- **DNS resolution failure:** MX lookup returns NXDOMAIN or SERVFAIL. The message cannot be routed at all.

### Delivery Rate Benchmarks

**Industry best practice:** A healthy sender should maintain delivery rates above 97% for opted-in, regularly maintained lists. The breakdown of expected rates:

- **97–99.5%:** Normal range for well-maintained lists with proper authentication. The gap from 100% accounts for natural recipient churn (abandoned mailboxes, changed addresses).
- **95–97%:** Marginal. Investigate whether list hygiene is lagging. Check for increases in `550 5.1.1` (unknown user) bounces, which indicate stale addresses.
- **90–95%:** Problem state. Likely causes include a partial blocklist hit (affecting delivery to specific ISPs), an authentication misconfiguration (e.g., SPF record exceeding the 10-lookup limit, causing `permerror`), or a significant list quality degradation.
- **Below 90%:** Severe problem. Common causes: full blocklist listing on a major list (Spamhaus SBL/CBL, Barracuda BRBL), DNS misconfiguration making the domain or IP fail verification, or catastrophic list issue (purchased/scraped addresses, reactivated old list without validation).

**Community observation:** Large-volume senders (1M+ messages/day) often see slightly lower delivery rates (96–98%) due to the statistical inevitability of encountering some fraction of unreachable servers and mailboxes across the long tail of receiving domains.

## What Deliverability Problems Look Like

Deliverability problems are fundamentally different from delivery problems: they are invisible in SMTP logs. The receiving server accepted the message — it returned `250 OK` — and then its internal filtering systems routed the message somewhere other than the inbox. The sender receives no direct notification that this occurred.

### Engagement-Based Indicators

The most common way to detect deliverability problems in the absence of direct inbox placement data is through changes in engagement metrics:

**Open rate decline without delivery rate change.** If a segment that historically shows 20–30% unique open rates suddenly drops to 5–10% while bounce rates remain stable, this strongly suggests spam folder placement. The messages were accepted (delivery succeeded) but recipients are not seeing them (deliverability failed).

Caveats on open rate reliability:
- Apple Mail Privacy Protection (MPP), introduced in iOS 15 / macOS Monterey (September 2021), prefetches tracking pixels for all messages, inflating open rates for Apple Mail users. As of 2024–2025, approximately 50–60% of consumer email opens are attributed to Apple devices (Litmus Email Client Market Share reports). This means raw open rates for consumer-facing senders are systematically inflated, and a drop despite MPP inflation is an even stronger signal of deliverability problems.
- Bot and security scanner prefetching by corporate email gateways (Barracuda, Mimecast, Proofpoint) can inflate open rates for B2B sends. These typically fire within 0–5 seconds of delivery and can be partially filtered by excluding opens that occur within the first 1–2 seconds of send.
- Open rate is a directional indicator, not a precise measurement. Use it to detect shifts and trends, not as an absolute deliverability score.

**Click rate decline with stable open rates.** If open rates appear stable (possibly due to MPP inflation) but click rates drop, this may indicate either deliverability problems (messages in spam, where some engaged users still check) or content relevance issues. Cross-reference with complaint data and postmaster tools before attributing to deliverability.

### Complaint Rate Data

ISP feedback loops (FBLs) report when recipients click "Report Spam" or "Mark as Junk." This is the most actionable deliverability signal available to senders.

**Fact (Google/Yahoo Sender Requirements, February 2024):**
- Google requires bulk senders to maintain a spam complaint rate below **0.10%** (1 in 1,000 messages) as measured in Google Postmaster Tools. Exceeding 0.10% triggers increased filtering.
- Google states that senders should **never exceed 0.30%** (3 in 1,000). Exceeding this threshold results in aggressive spam placement and can be difficult to recover from.
- Yahoo published similar requirements in the same timeframe, aligning on the 0.30% hard threshold.

**Best practice:** Monitor complaint rates daily, segmented by sending domain and major receiving domain. A sudden spike from 0.05% to 0.15% warrants immediate investigation — typically caused by a problematic campaign, list segment, or content change. Do not wait for it to reach 0.30%; by that point, reputation damage is already accumulating.

FBL enrollment is ISP-specific. Major FBL programs:
- **Yahoo/AOL:** ARF-format FBL. Requires enrollment at the Yahoo Postmaster site. Reports complaints for Yahoo Mail, AOL, and Verizon Media properties.
- **Microsoft/Outlook.com:** JMRP (Junk Mail Reporting Program) and SNDS (Smart Network Data Services). Requires enrollment. Reports complaints from Outlook.com, Hotmail, Live, and MSN domains.
- **Gmail:** Does not operate a traditional FBL. Complaint data is available only through Google Postmaster Tools as an aggregate percentage. Individual complaint addresses are not disclosed. Gmail reports complaints against the `d=` domain in the DKIM signature, not the envelope sender.

### Postmaster Tools and Reputation Dashboards

**Google Postmaster Tools (GPT)** is the most direct deliverability visibility tool for Gmail, which represents approximately 30–40% of consumer email volume in the United States (various industry estimates, 2024–2025):

- **Spam Rate:** Percentage of messages that Gmail recipients reported as spam (or that Gmail placed in spam and users did not rescue). This is the single most important Gmail deliverability metric.
- **Domain Reputation:** Rated as High, Medium, Low, or Bad. Reputation is based on complaint rates, spam trap hits, authentication status, and engagement signals. A shift from High to Medium or Low directly correlates with increased spam placement.
- **IP Reputation:** Same scale as domain reputation but for sending IP addresses. Relevant for senders using dedicated IPs.
- **Authentication:** Shows pass/fail rates for SPF, DKIM, and DMARC. Authentication failures that do not produce SMTP rejections (e.g., when the receiving domain's DMARC policy is `p=none`) still affect reputation scoring and deliverability.

**Microsoft SNDS (Smart Network Data Services):** Provides IP-level data for Outlook.com/Hotmail including message volume, complaint rates, spam trap hits, and a traffic light (green/yellow/red) reputation indicator.

**Best practice:** Check Google Postmaster Tools and Microsoft SNDS at least every 48 hours for any domain sending more than 10,000 messages per day. Set up alerts or automated polling if available through your ESP's integration.

### Inbox Placement Testing

Third-party inbox placement tools (Everest by Validity, GlockApps, InboxMonitor) maintain panels of seed addresses at major ISPs and report whether messages land in inbox, spam, or are missing.

Strengths:
- Provides the most direct measurement of inbox vs. spam placement.
- Covers multiple ISPs in a single test.
- Can be automated to test every campaign before or after deployment.

Limitations:
- Seed accounts lack real engagement history. Since major ISPs (particularly Gmail) use per-recipient engagement signals in filtering decisions, seed results may not perfectly reflect what actual recipients experience.
- Seed panels are typically small (10–50 per ISP), providing directional data, not statistically significant samples.
- Tab placement (Promotions vs. Primary in Gmail) is reported by some tools but is heavily influenced by individual user behavior and may not generalize.

**Best practice:** Use inbox placement testing as a directional early warning system, not as a definitive deliverability score. Cross-reference with postmaster tools and engagement metrics for a complete picture.

## Why This Distinction Matters for Log Interpretation

### The Diagnostic Fork

When someone reports "emails aren't arriving," the first diagnostic question is: **Is this a delivery problem or a deliverability problem?** The answer determines the entire investigation path.

**Step 1: Check delivery.** Pull SMTP logs for the affected recipients or recipient domains. Look for:
- 5xx permanent rejections (hard bounces)
- 4xx temporary rejections that eventually expired (soft bounces that converted to permanent failures)
- Connection-level failures

If the delivery rate for the affected segment is below 95%, you have a delivery problem. The SMTP codes will tell you why. Common causes and their fixes:

| SMTP Signal | Likely Cause | Fix |
|-------------|-------------|-----|
| `554 ... blocked using [blocklist]` | IP or domain on a DNS blocklist | Identify the blocklist from the rejection message, check listing status, follow the blocklist's delisting procedure. |
| `550 5.7.26` or DMARC failure references | Authentication failure | Check SPF alignment, DKIM signing, and DMARC policy. Verify that the `d=` domain in the DKIM signature aligns with the `From:` header domain. |
| `550 5.1.1` spike | Stale list / invalid addresses | Run the recipient list through an email validation service. Implement real-time validation at collection points. |
| `421 4.7.0` with high volume | Rate limiting | Reduce sending rate to the affected domain. Implement per-domain throttling. Check if the receiving domain publishes rate limit guidance. |
| Connection timeouts to specific MXs | Network or DNS issue | Verify MX records resolve correctly. Check for firewall or routing issues. Test connectivity from the sending IP to the receiving MX on port 25. |

**Step 2: If delivery is healthy (>97%), investigate deliverability.** The messages were accepted, so the problem is post-acceptance filtering. Investigation tools:

1. **Google Postmaster Tools:** Check spam rate and domain/IP reputation for the affected sending domain. A spam rate above 0.10% or a reputation drop from High to Medium/Low is a strong signal.
2. **FBL complaint data:** Check if complaint rates spiked around the time the problem was reported. Identify which campaign, segment, or content change coincided.
3. **Engagement metrics:** Compare open and click rates for the affected time period against the prior 30-day baseline. A decline greater than 50% relative to baseline, absent other explanations (seasonality, MPP changes), suggests spam placement.
4. **Inbox placement test:** Send a test to seed addresses at the affected ISP(s) to confirm spam placement.
5. **Message headers from a test send:** Have someone at the affected domain check the headers of a received test message. Gmail's `X-Gm-Spam` and `X-Gm-Phishy` headers, and Microsoft's `X-MS-Exchange-Organization-SCL` (Spam Confidence Level) header, can indicate how the message was scored. An SCL of 5 or above in Microsoft environments typically means spam folder placement.

### Common Misdiagnoses

**Misdiagnosis 1: "Our delivery rate is 99%, so deliverability is fine."** This is the most frequent error. A 99% delivery rate means 99% of messages were accepted by receiving servers. It says nothing about where those messages were placed. A sender can have 99% delivery and 30% inbox placement simultaneously.

**Misdiagnosis 2: "We're getting blocked by Gmail" when the actual issue is spam folder placement.** True blocking means Gmail is returning 4xx or 5xx rejections during the SMTP transaction — a delivery problem. If Gmail accepts the messages but routes them to spam, that is a deliverability problem requiring reputation and content investigation, not IP or infrastructure changes.

**Misdiagnosis 3: Attributing a deliverability problem to a single technical factor.** Deliverability is multi-factorial. A message may land in spam due to a combination of marginal domain reputation, slightly elevated complaint rates, content that triggers heuristic filters, and low recipient engagement. There is rarely a single "fix" for deliverability problems — unlike delivery problems, which often have a clear root cause (blocklist, authentication, invalid address).

**Misdiagnosis 4: "We passed SPF/DKIM/DMARC, so deliverability should be fine."** Authentication is necessary for deliverability but not sufficient. It prevents impersonation-based rejections (a delivery issue) and establishes sender identity for reputation tracking. But authenticated mail from a low-reputation sender will still be filtered to spam. Authentication is the floor, not the ceiling, of deliverability.

## The Feedback Delay Problem

A structural challenge in managing deliverability is the feedback delay. Delivery feedback is immediate — the SMTP response code arrives within the same TCP session, typically within seconds. Deliverability feedback is delayed by hours or days:

- **Google Postmaster Tools:** Data is typically delayed 24–48 hours from the time of sending.
- **FBL complaints:** Arrive asynchronously, usually within 24 hours but sometimes longer.
- **Engagement metrics:** Require enough time for recipients to open (or not open) messages. Meaningful open rate data typically stabilizes 24–48 hours after send for consumer email, longer for B2B.
- **Inbox placement tests:** Results are available within 1–4 hours of the test send, but represent a point-in-time snapshot, not ongoing monitoring.

This delay means deliverability problems are often discovered well after the damage has occurred. A problematic campaign sent on Monday morning may not show up in Postmaster Tools until Tuesday, and by then, the sender may have sent several more campaigns that compounded the reputation damage.

**Best practice:** Establish baseline metrics and automated alerts. If Google Postmaster Tools spam rate exceeds 0.05% (providing a buffer below the 0.10% warning threshold), or if complaint rates from any FBL exceed 0.08%, trigger an investigation before the next scheduled send. This early-warning approach compensates for the inherent feedback delay.

## Metrics Summary: Delivery vs. Deliverability

| Dimension | Delivery | Deliverability |
|-----------|----------|----------------|
| **Definition** | Server accepted the message | Message reached the inbox |
| **Visibility** | Direct — SMTP response codes in logs | Indirect — engagement metrics, postmaster tools, seed tests |
| **Feedback timing** | Immediate (within SMTP session) | Delayed (24–72 hours) |
| **Primary metrics** | Bounce rate, delivery rate (% accepted) | Inbox placement rate, spam rate, complaint rate |
| **Failure signals** | 4xx/5xx codes, connection errors | Open rate drops, complaint rate spikes, GPT reputation changes |
| **Root causes of failure** | Blocklists, authentication errors, invalid recipients, rate limits, DNS issues | Low sender reputation, high complaints, poor engagement, content triggers, spam trap hits |
| **Fix categories** | Infrastructure: DNS, authentication, IP reputation, list validation | Reputation: complaint reduction, list hygiene, engagement targeting, content review, warmup |
| **RFC basis** | RFC 5321 (SMTP), RFC 3463 (enhanced codes), RFC 7208 (SPF), RFC 6376 (DKIM), RFC 7489 (DMARC) | No RFC governs inbox placement; filtering is at ISP discretion |

## Key Takeaways

- **Delivery** is whether the server accepted the message (visible in SMTP logs as 2xx/4xx/5xx codes). **Deliverability** is whether the accepted message reached the inbox (invisible in SMTP logs). A 99% delivery rate can coexist with severe spam folder placement.
- Delivery failures produce explicit, immediate SMTP codes that identify the cause. Deliverability failures are inferred from delayed, indirect signals: engagement metric drops, complaint rate increases, Google Postmaster Tools reputation changes, and inbox placement test results.
- When diagnosing "emails aren't arriving," first check SMTP logs for delivery failures (below 97% delivery rate). Only if delivery is healthy should you investigate deliverability through postmaster tools, FBL data, and engagement analysis. The fixes for each are entirely different — infrastructure changes for delivery, reputation and content strategy for deliverability.
- Google and Yahoo both document a 0.10% complaint rate warning threshold and a 0.30% hard ceiling. Monitor complaint rates daily and investigate any sustained rate above 0.08% to maintain a safety margin, given the 24–48 hour feedback delay in postmaster tools data.
- Authentication (SPF, DKIM, DMARC) is necessary for both delivery and deliverability but is not sufficient for either. It prevents authentication-based rejections (delivery) and establishes identity for reputation tracking (deliverability), but authenticated mail from a low-reputation sender will still be spam-filtered.
