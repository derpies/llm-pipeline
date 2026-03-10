# Hard Bounces, Block/Policy Bounces, and Soft Bounces

## Overview

Every email that a receiving MTA refuses to accept generates a bounce — a non-delivery report (NDR) containing an SMTP response code and a diagnostic string. The traditional model classifies bounces into two categories: 5xx = hard (permanent), 4xx = soft (temporary). This two-category model is incomplete — it groups sender-level rejections (IP blocklists, authentication failures, reputation blocks) with address-level failures (nonexistent mailboxes, invalid domains), even though they require opposite operational responses.

This article uses a **three-category bounce model** that eliminates this ambiguity:

| Category | What It Means | SMTP Signals | Action |
|---|---|---|---|
| **Hard bounce** | The recipient address is permanently unreachable: mailbox does not exist, domain is invalid, account is disabled | `5.1.1`, `5.1.2`, `5.1.3`, `5.2.1`, `5.1.6`, `5.1.10`, `5.7.13` | Suppress address immediately |
| **Block/Policy bounce** | The sender is unwelcome: IP/domain reputation block, authentication failure, content rejection, blocklist hit | `5.7.1`, `5.7.23`, `5.7.25`, `5.7.26`, `5.7.27`, `4.7.x` policy deferrals | Do NOT suppress address; fix sending infrastructure |
| **Soft bounce** | Transient failure: mailbox full, server down, greylisting, rate limiting | `4.2.2`, `4.3.2`, `4.7.1` (rate limiting), greylisting `450` | Retry; suppress after repeated failures across sends |

The key insight: **hard bounces say "this recipient is unreachable"** while **block/policy bounces say "this sender is unwelcome."** Both can carry 5xx SMTP codes, but they demand fundamentally different responses. Suppressing addresses for block/policy bounces destroys your list without fixing the actual problem.

## Hard Bounces: Address-Level Permanent Failures

A hard bounce means the **recipient address itself** is permanently invalid — the mailbox does not exist, the domain cannot be resolved, or the account has been disabled. No change to your sending infrastructure will make this address deliverable.

Per RFC 5321, a 5xx response indicates permanent failure. But the 5xx code alone is not sufficient to classify a hard bounce — you must confirm the failure is address-level, not sender-level. The enhanced status code (RFC 3463) provides this distinction.

### Common Hard Bounce Scenarios

| Scenario | Typical SMTP Code | Enhanced Status Code | Diagnostic Example |
|---|---|---|---|
| Mailbox does not exist | `550` | `5.1.1` | `550 5.1.1 The email account that you tried to reach does not exist` |
| Domain does not exist | `550` | `5.1.2` | `550 5.1.2 We weren't able to find the recipient domain` |
| Address syntax invalid | `553` | `5.1.3` | `553 5.1.3 Invalid address format` |
| Mailbox disabled/suspended | `550` | `5.2.1` | `550 5.2.1 This mailbox has been disabled` |
| User account disabled | `550` | `5.7.13` | `550 5.7.13 User account disabled` |
| No such recipient (address format) | `550` | `5.1.6` | `550 5.1.6 Recipient address is not a valid address` |

The defining characteristic: **the problem is with the address, not the sender**. Changing your sending IP, fixing authentication, or modifying content will not help. The `x.1.y` enhanced status code family (RFC 3463) specifically indicates address-related failures and provides the canonical hard bounce signals.

### Operational Response

**Immediate suppression.** When an address produces a confirmed hard bounce (`5.1.1`, `5.1.2`, `5.1.3`, `5.2.1`, `5.7.13`), suppress it immediately. "Immediately" means the address should not receive another send attempt, even if another campaign is queued within minutes.

**Never re-add without verification.** A hard-bounced address should remain suppressed indefinitely unless the address owner confirms it is working, you verify deliverability via SMTP handshake (not just syntax/DNS), or 6+ months have passed with reason to believe re-activation. Even then, send a single confirmation message first.

**Risk:** Addresses that previously hard-bounced as "user unknown" can be repurposed as recycled spam traps. Re-mailing without verification risks severe reputation damage.

**Industry threshold:** Hard bounce rate should remain below **2%** per campaign; well-maintained lists stay below 0.5%. Rates above 5% trigger ISP deferrals and ESP account suspensions (SES and SendGrid both suspend around 5%). Spamhaus uses high bounce rates as one input signal for SBL listings.

**RFC fact:** RFC 5321 Section 6.1 states that a sender MUST NOT retry after a permanent (5xx) failure and SHOULD NOT continue sending to addresses determined to be invalid.

## Block/Policy Bounces: Sender-Level Rejections

A block/policy bounce means the **sending infrastructure or message** has been rejected — the recipient address is perfectly valid, but the receiving server refuses to accept mail from you. Many block/policy rejections use 5xx SMTP codes, which naive classification engines label as "hard bounces," leading to incorrect address suppression.

### Common Block/Policy Bounce Scenarios

| Scenario | Typical SMTP Code | Enhanced Status Code | Diagnostic Example |
|---|---|---|---|
| IP blocklist hit | `550` | `5.7.1` | `550 5.7.1 Service unavailable; client host blocked using Spamhaus` |
| Domain reputation block | `550` | `5.7.1` | `550 5.7.1 Message rejected due to domain policy` |
| SPF validation failed | `550` | `5.7.23` | `550 5.7.23 SPF validation failed` |
| Reverse DNS failure | `550` | `5.7.25` | `550 5.7.25 Reverse DNS validation failed` |
| DMARC/auth failure | `550` | `5.7.26` | `550 5.7.26 This message does not pass authentication checks (SPF and DKIM)` |
| DKIM signature failure | `550` | `5.7.27` | `550 5.7.27 Sender not authorized by DKIM` |
| Relay denied | `550` | `5.7.1` | `550 5.7.1 Relaying denied` |
| Reputation-based deferral | `421` | `4.7.0` | `421 4.7.0 Try again later, closing connection` |
| Policy-based throttling | `451` | `4.7.1` | `451 4.7.1 Temporarily rejected. Try again later.` |

The defining characteristic: **the problem is with the sender, not the address**. Fix authentication, get delisted, repair IP reputation, or modify content — and the same address will accept your mail.

This is why suppressing addresses on block/policy bounces is wrong. If your IP is on a Spamhaus blocklist and Outlook returns `550 5.7.1` for every recipient, suppressing all those addresses destroys your Outlook segment entirely. The correct response is to get delisted.

The 5xx SMTP code means permanent from the protocol's perspective — do not retry this delivery. But it does not tell you whether the failure is address-level or sender-level. That distinction comes from the enhanced status code: `5.1.x` = address problem (suppress); `5.7.x` = policy/auth problem (do not suppress; fix infrastructure); `5.2.1` = mailbox disabled (suppress); `5.2.2` = mailbox full (see "Gray Areas").

### Operational Response

**Do NOT suppress recipient addresses.** Track these bounces separately from address-level hard bounces.

**Diagnose the root cause:**
- For blocklist rejections: identify which blocklist, request delisting, and address the underlying cause (compromised account, poor list hygiene, spam trap hits).
- For authentication failures: fix SPF, DKIM, and DMARC records. See KB-02-05 through KB-02-07.
- For reputation-based deferrals (4.7.x): reduce sending volume to the affected domain, improve engagement metrics, and wait for reputation recovery.

**Monitor for domain-wide patterns.** If a specific ISP domain (e.g., all `@outlook.com` addresses) starts returning 5xx reputation blocks, this is an infrastructure problem, not a list hygiene problem. Suppressing individual addresses would be destructive.

### Provider-Specific Patterns

**Gmail:** `421 4.7.0` / `4.7.28` for rate limiting; `550 5.7.26` for auth failure — fix authentication, do not suppress.

**Microsoft:** `421 4.7.500` through `4.7.899` for policy/reputation deferrals (resolve in minutes to hours); `550 5.7.1` for blocklist rejections.

**Yahoo/AOL:** `421 4.7.0 [TSS04]` for reputation throttling; `553 5.7.1 [BL21]` / `554 5.7.9` for blocklist blocks. Bracketed tags encode Yahoo's internal reason codes.

Maintain a lookup table of provider-specific patterns — the SMTP code alone is not always sufficient.

## Soft Bounces: Transient Failures

A soft bounce is a **temporary delivery failure**. The receiving MTA has refused the message for now but indicates that the condition may be transient. The server communicates this with a **4xx SMTP reply code** (codes in the 400-499 range), and the sending MTA should queue the message and retry.

### Common Soft Bounce Scenarios

| Scenario | Typical SMTP Code | Enhanced Status Code | Diagnostic Example |
|---|---|---|---|
| Mailbox full | `452` | `4.2.2` | `452 4.2.2 Over quota` |
| Server temporarily unavailable | `421` | `4.3.2` | `421 4.3.2 Service not available, closing transmission channel` |
| Greylisting | `450` | `4.2.0` | `450 4.2.0 Recipient verification failed, try again later` |
| Message too large | `452` | `4.3.1` | `452 4.3.1 Insufficient system storage` |
| DNS temporary failure | `451` | `4.4.3` | `451 4.4.3 Temporary DNS resolution failure` |
| Server busy | `450` | `4.3.2` | `450 4.3.2 Please try again later` |
| Connection timeout | (no code) | --- | Connection timed out before server responded |

Note: Rate limiting (`4.7.1`) and reputation deferrals (`4.7.0`, `4.7.x`) are classified as block/policy bounces, not soft bounces, even though they use 4xx codes. Those reflect sender-side problems. True soft bounces are **transient conditions on the recipient side** — the mailbox will be emptied, the server will come back online, the greylisting window will pass.

### Operational Response

**Let the MTA retry (initially).** For the first occurrence, let your MTA retry per its configured schedule. Standard configurations: Postfix retries for 5 days with exponential backoff; PowerMTA commonly retries for 72 hours; Amazon SES retries for up to 14 hours. Most legitimate soft bounces resolve within 1-4 hours.

**Track consecutive soft bounces across sends.** Suppress an address after **3 to 5 consecutive soft bounces across separate send events** (not retry attempts within a single send). If a message soft-bounces 4 times during its retry cycle but eventually delivers, that counts as zero consecutive soft bounces. But if three different campaigns over three weeks each fail to deliver, suppress the address.

Industry suppression thresholds:

| Platform/Convention | Consecutive Soft Bounce Threshold | Time Window |
|---|---|---|
| Mailchimp | 7 soft bounces | Across any sends |
| HubSpot | Varies; escalates to hard after pattern | Rolling window |
| SendGrid | Configurable; default 3 | Per campaign cycle |
| General best practice | 3-5 across separate sends | Within 30 days |

## Gray Areas and Misclassification Traps

The three-category model resolves the largest source of bounce misclassification (conflating block/policy rejections with hard bounces), but some ambiguities remain.

### Mailbox Full: `5.2.2` vs. `4.2.2`

Mailbox-full bounces sit between hard and soft in practice. Some servers correctly return `452 4.2.2`; others return `550 5.2.2`. The enhanced code `x.2.2` always means "mailbox full," regardless of the SMTP reply code.

**Best practice:** Many ESPs special-case `x.2.2` regardless of whether the SMTP code is 4xx or 5xx. They treat it as a soft bounce for the first 1-3 occurrences, converting to a hard-bounce suppression only after repeated failures over 14-30 days. This is not RFC-compliant but reflects operational reality: a mailbox that is full today may be emptied tomorrow, but a mailbox that has been full for 30+ days is effectively abandoned and a prime candidate for spam trap conversion.

### ISPs Returning Wrong Code Classes

- **4xx for permanent conditions:** Some servers return `450 User not found` when the user genuinely does not exist (e.g., recipient verification via callout). If an address consistently returns `4xx` across 3+ retry cycles spanning 72+ hours, reclassify as a hard bounce and suppress.

- **5xx for transient conditions:** Misconfigured servers return `550 5.2.2 Mailbox full` instead of `452 4.2.2`. Always check the enhanced status code — `x.2.2` should override the SMTP class for classification.

### Provider-Specific Hard Bounce Patterns

**Gmail:** `550 5.1.1` for nonexistent users. **Microsoft:** `550 5.5.0 Requested action not taken: mailbox unavailable` for nonexistent users — distinguish from Microsoft's `550 5.7.1` policy rejections, which are block/policy bounces.

## SMTP Response Code Classification Rules

### Enhanced Status Codes Reference

RFC 3463 and RFC 5248 define enhanced status codes in the format `x.y.z`. The first digit should match the SMTP reply code class, but in practice this is not always true (see gray areas above).

Key enhanced status code families for bounce classification:

| Enhanced Code | Meaning | Category |
|---|---|---|
| `x.1.1` | Bad destination mailbox address | Hard bounce |
| `x.1.2` | Bad destination system address (domain) | Hard bounce |
| `x.1.3` | Bad destination mailbox address syntax | Hard bounce |
| `x.1.6` | Destination mailbox has moved | Hard bounce |
| `x.1.10` | Recipient address is null | Hard bounce |
| `x.2.1` | Mailbox disabled, not accepting messages | Hard bounce |
| `x.2.2` | Mailbox full | Soft bounce (special handling) |
| `x.3.x` | Mail system status | Soft bounce (usually transient) |
| `x.4.x` | Network or routing status | Soft bounce (usually transient) |
| `x.7.1` | Delivery not authorized, message refused | Block/Policy bounce |
| `x.7.13` | User account disabled | Hard bounce |
| `x.7.23` | SPF validation failed | Block/Policy bounce |
| `x.7.24` | SPF validation error | Block/Policy bounce (usually transient) |
| `x.7.25` | Reverse DNS validation failed | Block/Policy bounce |
| `x.7.26` | Multiple authentication checks failed | Block/Policy bounce |
| `x.7.27` | Sender not authorized by DKIM | Block/Policy bounce |

### Parsing DSNs

When you only have a DSN (not a live SMTP session), extract the enhanced status code from the `Status` field and the full SMTP response from the `Diagnostic-Code` field. Parse `Diagnostic-Code` first — some MTAs set `Status` generically (e.g., `5.0.0`) while the diagnostic text contains the remote server's specific codes. The `Action` field (`failed` or `delayed`) provides an additional signal.

## Bounce Classification in Log Data

### What to Look For in Raw SMTP Logs

A bounce event in your MTA logs typically contains these fields:

```
status=bounced (host mx.example.com[198.51.100.1] said:
  550 5.1.1 <user@example.com>... User unknown
  (in reply to RCPT TO command))
```

Extract and store:
1. **SMTP reply code:** `550` — first digit indicates permanence (5) or transience (4).
2. **Enhanced status code:** `5.1.1` — provides the specific reason and determines the bounce category.
3. **Diagnostic text:** `User unknown` — human-readable explanation; essential for edge cases and provider-specific patterns.
4. **SMTP verb phase:** `RCPT TO` — indicates at what point in the SMTP transaction the rejection occurred.

### Bounce Phase Matters

The phase of the SMTP transaction where the rejection occurs helps determine the bounce category:

| Phase | SMTP Command | What's Being Evaluated | Likely Category |
|---|---|---|---|
| Connection | (connect) | IP reputation, rDNS, blocklist checks | Block/Policy |
| EHLO/HELO | `EHLO` | Hostname validity, basic policy | Block/Policy |
| MAIL FROM | `MAIL FROM` | Sender domain/address policy, SPF (some servers) | Block/Policy |
| RCPT TO | `RCPT TO` | Recipient validity, per-recipient policy | Hard bounce (address) |
| DATA | `DATA` / `end-of-data` | Content, authentication results (DKIM/DMARC), overall policy | Block/Policy |

Rejections during `RCPT TO` are most commonly address-level hard bounces. Rejections at connection, `MAIL FROM`, or `DATA` are typically block/policy bounces.

### Structured Bounce Logging

Store bounce events with at minimum: timestamp, recipient address, sender address (envelope), remote MTA hostname/IP, SMTP reply code (3-digit), enhanced status code (x.y.z), full diagnostic text, SMTP phase, and three-category classification (hard / block-policy / soft).

## Building a Bounce Classification Engine

If you process bounces programmatically, apply rules in this priority order:

1. **Check enhanced status code for address-level signals.** `x.1.1`, `x.1.2`, `x.1.3`, `x.1.6`, `x.1.10`, `x.2.1`, `x.7.13` = **hard bounce**. Suppress.
2. **Check for policy/auth signals.** `x.7.1`, `x.7.23`, `x.7.25`, `x.7.26`, `x.7.27` = **block/policy bounce**. Do not suppress.
3. **Special cases.** `x.2.2` = **soft bounce** regardless of SMTP code class.
4. **Provider-specific diagnostic patterns.** Yahoo's bracketed codes, Microsoft's `5.7.xxx` sub-codes, Gmail's support page URLs.
5. **Fall back to SMTP reply code.** If enhanced code is generic (`x.0.0`) or absent: `5xx` without address-level code = block/policy (conservative); `4xx` = soft.
6. **Default conservatively.** When in doubt, do not suppress. Wrong suppression is more costly than one extra send to a dead address.

In practice, ~85-90% of bounces classify unambiguously from the enhanced status code alone. The remaining 10-15% require diagnostic text parsing or provider-specific pattern matching.

## Impact of Misclassification

Each direction of misclassification causes distinct damage:

- **Under-suppression (treating hard as soft):** Continuing to mail dead addresses inflates bounce rates, degrades sender reputation at Gmail/Microsoft/Yahoo, risks Spamhaus SBL listings, and triggers ESP account suspensions (most ESPs suspend above 5% bounce rates).

- **Wrong suppression (treating block/policy as hard):** This is the most damaging error. If your IP lands on a blocklist and a major ISP returns `550 5.7.1` for every recipient, naive classification suppresses your entire segment at that ISP. The addresses are valid — you have destroyed your list while the actual problem (blocklisting, authentication failure) remains unfixed. Recovering thousands of incorrectly suppressed addresses is operationally painful, as most ESPs require manual override.

- **Over-suppression (treating soft as hard):** Suppressing addresses on the first soft bounce loses valid subscribers whose mailbox was temporarily full or whose server was briefly down. At scale, even a 1% over-suppression rate represents significant lost reach and revenue.

## Key Takeaways

- **Use three categories, not two.** The traditional hard/soft binary conflates address-level failures with sender-level rejections. Classify bounces as hard (address problem), block/policy (sender problem), or soft (transient problem). Each requires a different operational response.

- **Hard bounces require immediate address suppression.** The enhanced status codes `5.1.1`, `5.1.2`, `5.1.3`, `5.2.1`, and `5.7.13` indicate the address itself is invalid. Suppress immediately, do not retry, and do not re-add without independent verification. Keep hard bounce rates below 2%.

- **Block/policy bounces require infrastructure fixes, not address suppression.** Codes like `5.7.1`, `5.7.26`, and `4.7.x` deferrals indicate your sending infrastructure, authentication, or reputation is the problem. The recipient addresses are valid. Fix SPF/DKIM/DMARC, request blocklist delisting, or repair IP reputation.

- **Soft bounces should be retried, then suppressed after persistent failure.** Suppress after 3-5 consecutive soft bounces across separate send events within a 30-day window. A single soft bounce is normal and expected.

- **The enhanced status code (`x.y.z`) determines the category, not the 3-digit SMTP code.** A `550` can be a hard bounce (`5.1.1` — user unknown) or a block/policy bounce (`5.7.1` — blocklist hit). Parse the enhanced code and diagnostic text to classify correctly.

- **Track bounces per recipient across sends, not just per campaign.** The pattern of repeated bounces to the same address over time is what converts a soft bounce into a suppression decision. Single-campaign bounce rates tell you about list quality; per-recipient bounce histories tell you about individual address validity.
