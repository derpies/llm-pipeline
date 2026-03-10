# Bounce Rate Thresholds and Their Impact

## Overview

Bounce rate is one of the primary signals ISPs and mailbox providers use to evaluate sender reputation. Unlike complaint rates or engagement metrics, bounce rate is directly observable by both the sender and the receiver during the SMTP transaction itself — every bounce produces a concrete DSN (Delivery Status Notification) code that both sides can log and analyze. When bounce rates exceed provider-specific thresholds, the consequences range from temporary throttling to permanent blocklisting of sending IPs and domains. This article covers what those thresholds are, how the three distinct bounce categories are weighted differently, what the log-level indicators look like, and how bounce rates interact with broader reputation scoring.

## Bounce Classification: The Three-Category Model

Before discussing thresholds, bounce classification must be precise. The common "hard vs. soft" binary is insufficient because it conflates two fundamentally different types of permanent (5xx) failure — address-level failures and policy/block failures — that have very different causes, reputation impacts, and remediation paths. ISPs weight these categories differently, and treating them identically leads to misdiagnosis and incorrect remediation.

### Hard Bounces (Address-Level Failures)

A hard bounce is a permanent delivery failure caused by the recipient address itself being invalid, nonexistent, or disabled. The receiving MTA returns a 5xx SMTP response indicating the mailbox or domain cannot receive mail now or in the future. These bounces reflect list quality and are the most damaging category to sender reputation because they signal to ISPs that the sender is mailing to unvalidated, stale, or purchased lists.

Common hard bounce codes:

- `550 5.1.1 User unknown` — the mailbox does not exist at this domain. This is the single most damaging bounce type for sender reputation and the primary signal ISPs use to assess list quality.
- `550 5.1.2 Bad destination mailbox address` — the domain itself is invalid or has no MX/A record.
- `550 5.1.3 Bad destination mailbox address syntax` — the address is malformed.
- `550 5.2.1 Mailbox disabled` — the account has been disabled or suspended by the provider.
- `550 5.1.10 Recipient address has null MX` — the domain explicitly refuses email (RFC 7505).
- `551 5.1.6 Recipient has moved` — rare but permanent.

**Action:** Suppress the address immediately on first occurrence. There is no valid reason to retry a confirmed address-level failure.

### Block/Policy Bounces (Sender-Level Rejections)

A block or policy bounce is a rejection caused by the sender's reputation, authentication configuration, content, or blocklist status — not by the recipient address being invalid. The address itself is perfectly valid; the ISP is refusing mail from this particular sender. These bounces use 5xx codes (making them look "permanent" by RFC definition) but suppressing the recipient address would be incorrect because the problem is with the sender, not the recipient.

Common block/policy bounce codes:

- `550 5.7.1 Message rejected` — policy-based rejection, often due to IP or domain reputation. This is the most commonly misclassified code: it does not mean the address is invalid.
- `550 5.7.23 Message blocked due to SPF failure` — SPF authentication check failed.
- `550 5.7.25 Reverse DNS validation failed` — sending IP lacks valid PTR record.
- `550 5.7.26 Message rejected due to DMARC policy` — the sender's DMARC record specifies p=reject and authentication failed.
- `550 5.7.27 Sender address has null MX` — the sender's domain refuses return-path mail.
- `421 4.7.x` policy deferrals — temporary reputation-based throttling that indicates growing sender-level problems.

**RFC fact:** RFC 3463 defines the enhanced status code taxonomy. The first digit determines permanence: `5.x.x` is permanent, `4.x.x` is transient. However, many block/policy bounces use `5.7.1` for conditions that are effectively temporary from the sender's perspective — a blocklist entry that clears after behavioral improvement, a content filter triggering on a specific campaign, or a reputation dip that recovers with clean sending. The `5.7.x` subclass specifically denotes security or policy status, not address validity.

**Action:** Do NOT suppress the recipient address. The fix is infrastructure-level: repair authentication (SPF, DKIM, DMARC), resolve blocklist entries, improve sender reputation, or fix content issues. Suppressing addresses based on policy bounces causes permanent list erosion without addressing the actual problem.

**Why this distinction matters:** A sender who misclassifies `5.7.1` policy blocks as hard bounces will steadily suppress valid, engaged subscribers every time they experience a temporary reputation dip or blocklist hit. Over months, this silently destroys list value. Meanwhile, the infrastructure problem that caused the blocks goes unaddressed.

### Soft Bounces (Transient Failures)

A soft bounce is a transient failure where the receiving MTA returns a 4xx code, indicating the message might be deliverable on a subsequent attempt. These typically reflect temporary conditions at the receiving server or mailbox.

Common soft bounce codes:

- `421 4.7.0 Try again later` — generic rate-limiting or greylisting.
- `450 4.2.2 Mailbox full` — recipient's mailbox has exceeded its storage quota.
- `451 4.3.2 System not accepting messages` — receiving server is temporarily unavailable.
- `451 4.7.1 Greylisting in effect` — deliberate delay for first-time sender/recipient pairs.
- `452 4.5.3 Too many recipients` — per-connection recipient limit exceeded.

**Operational distinction:** Soft bounces become operationally equivalent to hard bounces when the same address soft-bounces consistently across multiple send attempts over an extended period. Industry best practice is to treat an address as invalid after 3-5 consecutive soft bounces spanning at least 72 hours (to account for temporary outages). Many ESPs (Mailchimp, SendGrid, Braze) automatically suppress addresses after 3 consecutive soft bounces within a 7-day window.

**Action:** Retry according to your MTA's backoff schedule. Suppress the address only after repeated failures (3-5 consecutive soft bounces over 72+ hours).

### Summary: Three-Category Reference

| Category | Cause | Key Codes | Reputation Impact | Action |
|---|---|---|---|---|
| **Hard bounce** | Address-level: mailbox does not exist, domain invalid, account disabled | `5.1.1`, `5.1.2`, `5.1.3`, `5.2.1`, `5.1.6`, `5.1.10` | Severe — indicates list quality problems | Suppress address immediately |
| **Block/Policy bounce** | Sender-level: reputation block, auth failure, content rejection, blocklist | `5.7.1`, `5.7.23`, `5.7.25`, `5.7.26`, `5.7.27`, `4.7.x` policy | Moderate — indicates infrastructure problems | Do NOT suppress address; fix sender infrastructure |
| **Soft bounce** | Transient: mailbox full, server down, greylisting, rate limiting | `4.2.2`, `4.3.2`, `4.7.1` rate limit, `450` greylisting | Low — unless persistent | Retry; suppress after repeated failures |

## ISP-Specific Bounce Rate Thresholds

No single universal bounce rate threshold exists. Each major mailbox provider sets its own acceptable limits, and most do not publish exact numbers. The following thresholds are derived from published guidelines, postmaster documentation, and documented community observations.

**Critical distinction for thresholds:** ISPs primarily evaluate unknown-user bounce rate (5.1.1 and related address-level codes) when assessing list quality. Block/policy bounces (5.7.x) are evaluated separately as infrastructure or compliance issues. When ISPs refer to "bounce rate" in their sender guidelines, they are most concerned with address-level failures, because those directly indicate whether a sender is maintaining a clean, validated list.

### Google (Gmail / Google Workspace)

Google's published Bulk Sender Guidelines (updated February 2024, enforced from June 2024) are the most explicit:

- **Hard bounce rate must stay below 2%** as calculated on a rolling basis. Google does not specify the exact rolling window publicly, but postmaster tool data updates daily and reputation shifts are observable within 24-48 hours.
- Google Postmaster Tools reports bounce rate as a percentage of total messages sent to Gmail recipients.
- Exceeding 2% hard bounce rate triggers reputation degradation visible in Postmaster Tools as a shift from "High" to "Medium" or "Low" domain/IP reputation.
- Sustained rates above 5% can result in outright blocks: `421-4.7.28 Our system has detected an unusual rate of unsolicited mail originating from your IP address` or `550-5.7.1 Our system has detected that this message is likely unsolicited mail`.

**Best practice:** Google recommends maintaining hard bounce rates well under 2% — aiming for under 0.5% is a safer operational target, because the 2% figure represents a ceiling, not a comfortable operating range. Note that Google's `550-5.7.1` block response is itself a policy bounce from Google to you — it should not be confused with a 5.1.1 address-level bounce in your classification logic.

### Microsoft (Outlook.com / Office 365 / Hotmail)

Microsoft does not publish a specific numeric bounce rate threshold but enforces reputation through its Smart Network Data Services (SNDS) platform:

- SNDS classifies sending IPs with a traffic-light system: green (normal), yellow (concerning), red (poor).
- **Community observation:** IPs consistently generating hard bounce rates above 5% on Microsoft domains trend toward yellow/red SNDS status within 3-5 days.
- Microsoft's primary enforcement mechanism is Junk Mail Reporting Program (JMRP) feedback loops and their internal reputation scoring (which weighs bounces, complaints, and spamtrap hits). Bounce rate alone is less decisive at Microsoft than at Google — Microsoft places relatively more weight on complaint rate and spamtrap data.
- Block responses from Microsoft typically look like: `550 5.7.606 Access denied, banned sending IP [x.x.x.x]` or `421 RP-001 (SNT004) Unfortunately, some messages from x.x.x.x weren't sent. Please try again.`

**Best practice:** Keep hard bounce rates under 2% for Microsoft domains. While Microsoft may tolerate slightly higher rates than Google before blocking, the reputation damage accumulates and is harder to reverse at Microsoft because their delisting process (via https://sender.office.com) requires manual review.

### Yahoo / AOL (Yahoo Mail)

Yahoo's Postmaster resources indicate:

- Yahoo uses a composite reputation score that factors in bounces, complaints, authentication, and engagement.
- **Community observation:** Hard bounce rates above 3% directed at Yahoo domains correlate with throttling (421 responses with `[TS03]` or `[TS04]` error codes).
- Yahoo's error codes for bounce-related throttling: `421 4.7.0 [TSS04] Messages from x.x.x.x temporarily deferred due to unexpected volume or user complaints`.
- Hard blocks for severe cases: `553 5.7.1 [BL21] Connections will not be accepted from x.x.x.x, because the ip is in Spamhaus's list`.

### Apple (iCloud Mail)

Apple provides minimal public documentation on thresholds:

- **Community observation:** Apple iCloud appears to tolerate somewhat higher bounce rates than Google or Microsoft before imposing blocks, but their blocking is abrupt — there is typically little warning before an IP is blocked entirely.
- Block responses: `550 5.7.1 Your message was rejected due to example.com's DMARC policy` (authentication) or `554 5.7.1 Your IP has been blocked` (reputation).
- Apple does not offer a postmaster tools portal, making bounce rate monitoring for Apple-specific traffic dependent entirely on your own SMTP log analysis.

### General Industry Thresholds

Aggregating across providers and industry guidance from organizations like M3AAWG (Messaging, Malware and Mobile Anti-Abuse Working Group):

| Metric | Acceptable | Concerning | Critical |
|---|---|---|---|
| Overall hard bounce rate (address-level) | < 2% | 2-5% | > 5% |
| Unknown-user bounce rate (5.1.1 specifically) | < 1% | 1-3% | > 3% |
| Block/policy bounce rate (5.7.x) | < 5% | 5-10% | > 10% |
| Soft bounce rate | < 5% | 5-10% | > 10% |
| Single-campaign hard bounce rate | < 3% | 3-8% | > 8% |

**Important nuance:** These thresholds apply per mailbox provider domain, not as a global average. A sender with 0.5% hard bounces at Gmail but 12% hard bounces at a small regional ISP still has a serious problem at that ISP — and cross-ISP reputation services like Spamhaus, Barracuda, and Validity (Return Path) aggregate signals across providers, so localized problems can propagate.

**Note on block/policy bounce thresholds:** A high block/policy bounce rate is a serious operational problem, but it is evaluated differently by ISPs than address-level bounces. A spike in 5.7.1 rejections from Gmail means Google is blocking you — it does not mean your list is dirty. The remediation path (fix authentication, resolve blocklist entry, improve reputation through clean sending) is entirely different from the remediation for address-level bounces (clean the list).

## How Bounce Rate Is Calculated

The specific denominator matters. Different contexts use different calculations, and confusion between them causes misdiagnosis.

### Per-Campaign Bounce Rate

```
hard_bounce_rate = (address_level_hard_bounces / total_messages_attempted) * 100
block_bounce_rate = (policy_bounces / total_messages_attempted) * 100
```

These should be tracked as separate metrics. "Total messages attempted" means messages that reached the SMTP handshake stage — not messages queued, not messages that failed at the submission stage due to rate limits or authentication errors.

### Rolling Bounce Rate (ISP Perspective)

ISPs calculate bounce rate over a rolling window, typically 1-7 days, weighted toward recent traffic. Google's Postmaster Tools appears to use a roughly 7-day rolling window with heavier weighting on the most recent 24-48 hours. This means:

- A single bad campaign can spike your bounce rate even if your historical average is low.
- Recovery after a spike takes 5-14 days of clean sending before the rolling rate returns to acceptable levels.
- Low-volume senders are more vulnerable to rate spikes because each individual bounce has a larger proportional impact.

### Volume-Adjusted Sensitivity

ISPs apply bounce rate thresholds with volume context. A sender delivering 100 messages with 3 bounces (3% rate) is evaluated differently from a sender delivering 1,000,000 messages with 30,000 bounces (also 3% rate). The high-volume sender generating 30,000 invalid-recipient transactions consumes real server resources at the ISP and will attract attention faster. **Community observation:** High-volume senders (> 100,000 messages/day) to Gmail typically see reputation impacts at lower bounce rate percentages than the published 2% threshold suggests, sometimes at rates as low as 1-1.5%.

## Consequences of Exceeding Thresholds

The consequences follow a predictable escalation path. Understanding the stages helps you diagnose where you are and how urgently you need to act.

### Stage 1: Throttling (4xx Deferrals)

The first sign of bounce-rate-driven reputation problems is typically throttling. The ISP starts returning 4xx codes to slow your delivery rate:

- Gmail: `421-4.7.28 Our system has detected an unusual rate of unsolicited mail originating from your IP address. To protect our users from spam, mail sent from your IP address has been temporarily rate limited.`
- Microsoft: `421 RP-001 (BAY004) Unfortunately, some messages from x.x.x.x weren't sent. Please try again.`
- Yahoo: `421 4.7.0 [TSS04] Messages from x.x.x.x temporarily deferred.`

**Log pattern:** A sudden increase in 4xx responses where previously you saw mostly 250 (accepted) responses. Your MTA queue depth grows as messages pile up waiting for retry. In Postfix, look for a surge in `status=deferred` entries; in PowerMTA, watch the `vmta` queue counters.

**Timeframe:** Throttling typically begins within 12-24 hours of the bounce rate exceeding the provider's threshold. It may resolve within 24-48 hours if the underlying cause is corrected and sending volume is reduced.

### Stage 2: Junk Folder Placement

Concurrent with or shortly after throttling, the ISP may begin routing accepted messages to the spam/junk folder rather than the inbox. This is not directly visible in SMTP logs — your MTA sees a `250 OK` response, but the message is silently filed into spam. Detection requires:

- Monitoring inbox placement rates via seed-list testing (tools: Validity Everest, GlockApps, InboxMonitor).
- Watching for drops in open rates and click rates in your campaign analytics.
- Checking Google Postmaster Tools for spam rate increases.

**Operational note:** Junk folder placement due to elevated bounce rates often co-occurs with complaint-rate issues, because users who do receive messages from a sender with poor list hygiene are more likely to mark them as spam.

### Stage 3: Blocks (5xx Rejections)

If bounce rates remain elevated or worsen, ISPs escalate to outright blocks:

- Gmail: `550-5.7.1 [x.x.x.x] Our system has detected that this message is likely unsolicited mail. To reduce the amount of spam sent to Gmail, this message has been blocked.`
- Microsoft: `550 5.7.606 Access denied, banned sending IP [x.x.x.x].`
- Yahoo: `553 5.7.1 [BL21] Connections will not be accepted from x.x.x.x.`

**Log pattern:** A shift from 4xx to 5xx responses for the same destination domain. Your queue drains (because messages bounce out) but no mail is being delivered.

**Timeframe:** Blocks typically follow 3-7 days of sustained threshold violations. Remediation requires:

1. Stopping all sending to the affected provider.
2. Diagnosing the bounce category — list quality problem or infrastructure/reputation problem (see below).
3. Submitting delisting requests where applicable (Google: automatic after behavioral improvement; Microsoft: https://sender.office.com; Yahoo: https://postmaster.yahooinc.com).
4. Resuming with reduced volume and monitoring closely.

Recovery from a full block typically takes 7-30 days depending on the provider and the severity of the violation.

### Stage 4: Blocklist Inclusion

In severe or prolonged cases, sending IPs or domains may be added to third-party blocklists (Spamhaus SBL/XBL, Barracuda BRBL, SORBS, etc.). This propagates the reputation damage beyond a single ISP:

- Spamhaus SBL listings are triggered by a combination of signals including high bounce rates to spamtraps (which are a subset of bounces from the ISP's perspective).
- A Spamhaus listing can cascade to hundreds of ISPs that query Spamhaus in their mail flow.
- Delisting from Spamhaus requires demonstrating the underlying cause has been resolved and typically takes 24 hours to 2 weeks.

## Bounce Rates and Reputation: The Interaction Model

Bounce rate does not exist in isolation. ISPs use it as one input in a multi-signal reputation model. Understanding the interactions helps explain why two senders with identical bounce rates can experience very different outcomes.

### Bounce Rate + Complaint Rate

This is the most dangerous combination. A sender with a 3% bounce rate and a 0.1% complaint rate will be treated far more harshly than a sender with a 3% bounce rate and a 0.01% complaint rate. Google's Bulk Sender Guidelines explicitly state that senders must maintain a spam complaint rate below 0.3% (measured via Gmail's Feedback Loop / Postmaster Tools). When both bounce rate and complaint rate are elevated, reputation degradation accelerates — the effects are not merely additive but compound.

### Bounce Rate + Sending Volume

Higher sending volumes amplify the impact of elevated bounce rates. A sender dispatching 50,000 messages per day with a 4% hard bounce rate is generating 2,000 invalid-recipient SMTP transactions per day at a single ISP. This is operationally significant to the ISP and triggers scrutiny faster than a sender generating 10 bounces per day even at a higher percentage rate.

### Bounce Rate + IP Age / Warm-Up Status

New IPs and domains have no established reputation. ISPs give new senders a limited initial trust budget. Burning through this budget with high bounce rates during warm-up is particularly damaging because there is no positive history to counterbalance the negative signal. A bounce rate of 3% during IP warm-up is far more damaging than 3% on a well-established IP with years of clean sending history.

**Best practice:** During IP warm-up, keep hard bounce rates below 0.5%. If a warm-up campaign produces bounces above 1%, pause and clean the list before continuing. Warm-up volumes should start at 50-200 messages per day per ISP and double every 2-3 days only if bounce and complaint rates remain within acceptable ranges.

### Bounce Rate + Authentication

Proper SPF, DKIM, and DMARC alignment does not excuse a high bounce rate, but the absence of authentication worsens the impact. An unauthenticated sender with a 2% bounce rate will be treated more harshly than an authenticated sender with the same rate, because the ISP cannot confidently attribute the traffic to a known entity. Furthermore, authentication failures generate their own category of policy bounces (5.7.23, 5.7.25, 5.7.26) that compound the problem.

## Identifying Bounce Rate Problems in Log Data

Effective monitoring requires parsing SMTP logs for specific patterns and correctly classifying each bounce into the three categories. Here is what to look for across common MTA platforms.

### Postfix

Relevant log entries in `/var/log/mail.log`:

```
Feb 21 14:23:01 mail postfix/smtp[12345]: A1B2C3D4E5: to=<user@gmail.com>,
  relay=gmail-smtp-in.l.google.com[142.250.x.x]:25, delay=1.2,
  delays=0.1/0/0.8/0.3, dsn=5.1.1, status=bounced
  (host gmail-smtp-in.l.google.com[142.250.x.x] said:
  550-5.1.1 The email account that you tried to reach does not exist.)
```

Key fields to aggregate:
- `dsn=5.1.1` — extract the enhanced status code. Classify by subcode: `5.1.x` and `5.2.1` are address-level hard bounces; `5.7.x` are policy bounces.
- `status=bounced` — confirms permanent failure.
- `relay=` — identifies the destination ISP.

Useful one-liner for bounce rate calculation over the last 24 hours:

```bash
# Count hard bounces vs. total delivery attempts to Gmail
grep "relay=gmail-smtp-in" /var/log/mail.log | \
  awk '{print ($NF ~ /status=bounced/) ? "bounce" : "other"}' | \
  sort | uniq -c
```

### PowerMTA

PowerMTA's accounting files (`acct/` directory) contain structured delivery records:

```
type=b,timeQueued=2026-02-21 14:23:01,orig=sender@example.com,
  rcpt=user@gmail.com,dsnStatus=5.1.1,dsnDiag="550 5.1.1 User unknown",
  vmta=vmta1,srcIp=203.0.113.10
```

Filter for `type=b` (bounce) records and aggregate by `dsnStatus` and destination domain. Separate `5.1.x` records (address-level) from `5.7.x` records (policy) in your reporting — these require different operational responses.

### SendGrid / ESP Webhook Data

ESPs typically deliver bounce events via webhooks with structured JSON:

```json
{
  "event": "bounce",
  "type": "hard",
  "email": "user@gmail.com",
  "smtp-id": "<abc123@example.com>",
  "reason": "550 5.1.1 The email account does not exist",
  "status": "5.1.1",
  "timestamp": 1771689600
}
```

Monitor the ratio of `"event": "bounce"` against `"event": "delivered"` events per destination domain per day. **Important:** Most ESPs classify all 5xx bounces as `"type": "hard"` without distinguishing address-level from policy bounces. Parse the `"status"` field yourself: `5.1.x` codes should trigger address suppression, while `5.7.x` codes should trigger infrastructure investigation, not suppression.

## Reducing Bounce Rates: Operational Practices

Because address-level bounces and block/policy bounces have entirely different root causes, they require different remediation strategies. Conflating them leads to the common mistake of suppressing valid addresses when the real problem is infrastructure.

### Reducing Address-Level Hard Bounces (List Quality)

Address-level bounces (5.1.1, 5.1.2, 5.1.3, 5.2.1, 5.1.6, 5.1.10) are a list quality problem. Every one of these bounces indicates an address that should never have been in your send list, or an address that has become invalid since acquisition.

- **Suppress address-level hard bounces immediately.** Any address returning a 5.1.1 should be suppressed on the first occurrence. There is no valid reason to retry a confirmed unknown-user address.
- **Validate at acquisition.** Use real-time email validation APIs (ZeroBounce, NeverBounce, Kickbox) at the point of signup. These services check MX records, SMTP mailbox existence (via RCPT TO verification where supported), and known disposable/role-based address databases.
- **Re-validate dormant lists.** Any list segment that has not been mailed in 90+ days should be re-validated before sending. Address validity decays at approximately 2-3% per month due to employee turnover, abandoned accounts, and domain changes.
- **Implement double opt-in (confirmed opt-in).** This eliminates typo-based bounces and fake signups entirely. It reduces list growth rate by 20-40% compared to single opt-in, but the resulting list has near-zero bounce rates.

### Reducing Block/Policy Bounces (Infrastructure Quality)

Block/policy bounces (5.7.1, 5.7.23, 5.7.25, 5.7.26, 5.7.27) are a sender infrastructure problem. The addresses are valid; the ISP is rejecting mail from you specifically.

- **Audit authentication.** Verify SPF records include all legitimate sending IPs, DKIM signatures are valid and properly aligned, and DMARC policy is correctly configured. A `5.7.26` response means DMARC is failing — check alignment between your From domain, SPF domain, and DKIM d= domain.
- **Check blocklists.** Query Spamhaus, Barracuda, SORBS, and other DNSBLs for your sending IPs and domains. A `5.7.1` rejection often means the receiving ISP found your IP on a blocklist. Resolve the listing before resuming volume.
- **Review sending reputation.** Use Google Postmaster Tools, Microsoft SNDS, and Yahoo Postmaster to assess your current reputation. Policy bounces correlate with "Low" or "Poor" reputation classifications.
- **Fix content issues.** Some `5.7.1` rejections are content-triggered. Review message content, URLs, and attachments for patterns that trigger content filters.
- **Do NOT suppress addresses based on policy bounces.** This is the most common mistake. Suppressing 10,000 valid subscribers because Gmail returned `5.7.1` for a day due to a blocklist hit permanently damages your list for no reason. Fix the infrastructure; the addresses will accept mail once the block clears.

### Suppression List Management

Maintain a global suppression list that is checked before every send. This list should include:

- All addresses that have returned address-level hard bounces (5.1.x, 5.2.1 — permanent suppression).
- Addresses that have soft-bounced 3+ times within 7 days (temporary suppression; re-enable after 30 days and re-test).
- Known spamtrap addresses (if identified through feedback loops or list validation services).
- Role-based addresses (postmaster@, abuse@, info@) unless specifically opted in — these addresses frequently rotate handlers and have higher complaint rates.

**Explicitly excluded from suppression:** Addresses that returned only block/policy bounces (5.7.x). These should be flagged for infrastructure investigation, not suppressed.

### Segmented Sending by Engagement

Sending to engaged recipients first provides a reputation buffer:

1. Send to recipients who opened or clicked within the last 30 days.
2. Then send to 30-90 day engaged recipients.
3. Finally, cautiously send to 90-180 day recipients in small batches with close monitoring.
4. Recipients with no engagement in 180+ days should be re-confirmed or removed.

This approach ensures that your initial sending batches generate high engagement signals and low bounce rates, establishing positive reputation before sending to riskier segments.

### Real-Time Monitoring and Alerting

Set up automated alerts for:

- **Per-campaign address-level hard bounce rate exceeding 1%.** Investigate immediately — possible list quality issue or data import error.
- **Per-ISP address-level hard bounce rate exceeding 2%.** Pause sending to that ISP and analyze bounce reasons.
- **Spike in 5.7.x policy bounces from a single provider.** This is an infrastructure alert, not a list quality alert. Check authentication, blocklists, and reputation dashboards.
- **Sudden spike in 4xx deferrals from a single provider.** This is the early warning of reputation-driven throttling.
- **Queue depth growing for a specific destination domain.** Indicates the ISP is not accepting your traffic at normal rates.

### Post-Incident Recovery

If you have already exceeded thresholds and are experiencing blocks:

1. **Stop sending immediately** to the affected ISP domain(s).
2. **Classify the bounce type.** Determine whether you are seeing address-level bounces (list quality problem) or policy bounces (infrastructure problem). The remediation path depends entirely on this classification.
3. **For address-level bounce spikes:** Audit the list that caused the spike. Identify the source of invalid addresses (purchased list, old import, compromised signup form, bot-generated signups). Remove all hard-bounced addresses from your active lists and add them to your global suppression list. Run the remaining list through a validation service before attempting to resume.
4. **For policy bounce spikes:** Check authentication records, query blocklists, review Google Postmaster Tools and SNDS reputation data. Fix the root cause before resuming. Do not suppress the affected addresses.
5. **Resume at reduced volume** — start at 10-20% of your normal daily volume to that ISP and increase gradually over 7-14 days.
6. **Submit delisting requests** where applicable, but only after you have addressed the root cause. Delisting without behavioral change results in re-listing within days.

## Key Takeaways

- **Classify bounces into three categories, not two.** Address-level hard bounces (5.1.x) indicate list quality problems and require address suppression. Block/policy bounces (5.7.x) indicate infrastructure problems and require sender-side fixes — never suppress addresses based on policy bounces. Soft bounces (4.x.x) are transient and require retry with eventual suppression after repeated failures.
- **ISPs primarily evaluate unknown-user bounces (5.1.1) for list quality assessment.** This is the single most damaging bounce code because it signals to ISPs that the sender is mailing to unvalidated or purchased lists. Policy bounces are evaluated separately as infrastructure compliance issues.
- **Keep address-level hard bounce rates below 2% per ISP domain as an absolute ceiling; target under 0.5% for safe operation.** Google enforces the 2% threshold explicitly; other major providers use similar ranges but with less public documentation.
- **Bounce rate thresholds are evaluated per ISP, not globally, and are volume-weighted.** A 3% bounce rate generating 30,000 bounces per day triggers consequences faster than the same percentage at lower volumes.
- **Consequences escalate predictably: throttling (4xx deferrals), then junk folder placement, then blocks (5xx rejections), then third-party blocklist inclusion.** Catching the problem at the throttling stage and acting immediately avoids the more severe and slower-to-recover-from later stages.
- **Address bounces and policy bounces have completely different remediation paths.** Address bounces need list cleaning, validation, and suppression. Policy bounces need authentication fixes, blocklist resolution, and reputation recovery. Applying the wrong fix wastes time and can make the problem worse.
