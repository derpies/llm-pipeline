# Suppression List Management

## Overview

A suppression list is a set of email addresses that your sending infrastructure must never attempt to deliver to, regardless of whether those addresses appear in active campaign lists, transactional triggers, or any other sending queue. Suppression is not the same as unsubscription — it is a broader, more protective mechanism that prevents mail from being generated or transmitted to addresses that would damage your sender reputation, violate compliance requirements, or waste resources on undeliverable mail.

Suppression lists are the single most important defensive data structure in email operations. A sender with a well-maintained suppression list can survive list imports, system migrations, and accidental re-sends without reputational damage. A sender without one — or with one that leaks — will eventually hit spam traps, generate excessive bounces, and accumulate complaints that degrade inbox placement across all campaigns.

Critically, a well-maintained suppression list must also avoid over-suppression — permanently removing valid addresses because a bounce was misclassified. The most common over-suppression error is treating block/policy bounces (where the address is valid but the sender is being rejected) as address-level failures. This article covers the three-category bounce model that prevents this error, along with implementation patterns, retention policies, and the operational risks of suppression failures.

## Categories of Addresses That Require Suppression

Not all suppressions are equivalent. Different address categories enter your suppression list through different mechanisms, carry different risk profiles, and require different retention durations.

### Hard Bounce Addresses (Address-Level Permanent Failures)

An address that returns a permanent failure indicating the address itself is invalid must be suppressed immediately after the first occurrence. The critical distinction is that the bounce codes must indicate an address-level problem — a mailbox that does not exist, a domain that cannot receive mail, or an account that has been permanently disabled. Not all 5xx responses are address-level failures (see "Block/Policy Bounces" below).

The address-level hard bounce codes that trigger immediate suppression are:

- `550 5.1.1 User unknown` — mailbox does not exist
- `550 5.1.2 Bad destination mailbox address` — domain-level failure
- `553 5.1.3 Invalid address format` — address syntax is permanently invalid
- `550 5.2.1 Mailbox disabled` — account deactivated by the provider
- `551 5.1.6 Recipient has moved` — address no longer valid at this domain
- `556 5.1.10 Recipient address has null MX` — domain explicitly does not accept email (RFC 7505)

**Fact (RFC 5321):** A 5xx response is a permanent failure. The sending MTA should not retry delivery. However, the suppression decision must be based on the enhanced status code (the `x.y.z` portion), not just the 5xx reply code class, because many 5xx responses indicate sender-side problems rather than invalid addresses.

**Best practice:** Suppress on first address-level hard bounce. Some senders implement a "confirm on second bounce" policy for `5.2.1` (mailbox disabled), but Gmail and Microsoft both interpret repeated delivery attempts to non-existent mailboxes as a strong negative signal. The marginal value of one extra attempt is far outweighed by the reputational cost if the address remains invalid.

### Block/Policy Bounces (Sender-Level Rejections — Do NOT Suppress)

A block or policy bounce occurs when the receiving MTA rejects the message because of a problem with the sender — not the recipient address. The address is valid; the recipient's mailbox exists and could receive mail from other senders. The rejection targets your sending infrastructure: your IP reputation, your authentication configuration, your content, or your blocklist status.

These bounces use 5xx response codes (making them look like hard bounces) but must NOT trigger address suppression:

- `550 5.7.1 Service unavailable; client host blocked` — IP or domain blocklisted or policy-rejected
- `550 5.7.23 SPF validation failed` — sending IP not authorized in SPF record
- `550 5.7.25 Reverse DNS validation failed` — sending IP lacks proper rDNS
- `550 5.7.26 Unauthenticated mail rejected` — SPF and DKIM both failed
- `550 5.7.27 Sender address does not pass DMARC validation` — DMARC policy failure

**Why suppressing these addresses is wrong:** If your IP is listed on Spamhaus and Outlook returns `550 5.7.1` for every message you send to `@outlook.com`, suppressing those addresses means you permanently lose your entire Outlook audience. Once you delist, those addresses would accept your mail — but they are now on your suppression list. You have converted a temporary infrastructure problem into permanent list damage.

**Correct handling:** Track block/policy bounces separately from address-level bounces. Diagnose the root cause from the enhanced status code: blocklist delisting for `5.7.1`, SPF correction for `5.7.23`, DKIM repair for `5.7.25`/`5.7.26`, DMARC alignment for `5.7.27`. Alert on volume — a sudden spike in `5.7.x` rejections concentrated on a single ISP domain is an infrastructure problem. Route these alerts to your deliverability team, not your list hygiene process. See KB-04-15 for the four-category bounce model.

**The 5.7.1 catch-all problem:** Enhanced code `5.7.1` is the most overloaded code in practice. It can mean blocklisting, content filtering, authentication failure, or blanket policy rejection. Always read the diagnostic text. None of these meanings indicate an invalid address.

### Soft Bounce Addresses

Addresses that return temporary failures (4xx SMTP responses) should be retried by the MTA, not immediately suppressed. Common codes include `4.2.2` (mailbox full), `4.3.2` (service temporarily unavailable), `4.7.0`/`4.7.1` (rate limiting or throttling), and `4.2.0` (greylisting).

**Promotion to suppression:** If an address soft-bounces on 3-5 consecutive separate sends across at least 7-14 days with no successful delivery, promote it to suppression. Multiple retry attempts within a single send do not count as separate failures.

**Special case (5.2.2 mailbox full):** Some providers return `552 5.2.2` (5xx code for a mailbox-full condition). Despite the 5xx code, treat this as a soft bounce for the first 1-3 occurrences over 14+ days, then suppress. A persistently full mailbox is effectively abandoned.

### Complaint Addresses (FBL)

When a recipient clicks "Report Spam," the ISP sends a complaint notification via a Feedback Loop (FBL). The ARF (Abuse Reporting Format, RFC 5965) message identifies the recipient. That address must be suppressed immediately and permanently.

**Fact (ISP-documented):** Microsoft's JMRP, Yahoo's CFL, and other FBL providers explicitly state that continued mailing to recipients who have filed complaints constitutes abuse. Gmail does not provide a per-message FBL — it only offers aggregate complaint data via Postmaster Tools.

### Unsubscribe Requests

Addresses that have opted out via any unsubscribe mechanism — List-Unsubscribe header (RFC 8058 one-click), preference center, reply-based, or manual request — must be suppressed from the relevant mail streams. CAN-SPAM requires honoring opt-out requests within 10 business days; CASL requires it effectively immediately. Unsubscribe suppression is typically scoped — a user who unsubscribes from marketing may still receive transactional mail.

### Role Accounts, Spam Traps, and Legal Suppressions

**Role accounts** (`abuse@`, `postmaster@`, `admin@`, `noreply@`, `info@`, `sales@`, `support@`, `webmaster@`, `billing@`, `compliance@`, `security@`, `mailer-daemon@`, `root@`) route to shared inboxes, not individual humans. Suppress these by pattern.

**Spam traps** — pristine, recycled, or typo — should be suppressed permanently on identification and never removed.

**Legal and compliance suppressions** from court orders, cease-and-desist letters, or regulatory enforcement must never expire and must survive system migrations.

## Implementation Architecture

### Suppression as a Pre-Send Gate

Suppression must be enforced at the point of mail generation or injection, before the message enters the MTA queue. The typical architecture:

1. Campaign or transactional trigger generates a list of recipient addresses.
2. The sending application queries the suppression store and removes matching addresses.
3. Only non-suppressed addresses are injected into the MTA for delivery.
4. Post-delivery, bounce and FBL processors classify bounces into categories (address-level hard bounce, block/policy bounce, soft bounce) and add addresses to the suppression store only for address-level failures and complaint events.

The suppression check must be the last step before injection, not an early filter that can be bypassed by downstream deduplication, segmentation, or enrichment stages.

### Bounce Classification Before Suppression

Your bounce processing pipeline must classify bounces before making suppression decisions. Feeding unclassified 5xx bounces directly into the suppression store is the root cause of over-suppression errors. Classification priority:

1. Parse the enhanced status code. If the subject digit is `1` (addressing) or the code is `5.2.1` (mailbox disabled) — suppress.
2. If the subject digit is `7` (security/policy) — do NOT suppress. Route to infrastructure alerting.
3. If the enhanced code is `5.2.2` (mailbox full) — treat as soft bounce despite the 5xx class.
4. For ambiguous `5.7.1`, parse the diagnostic text for blocklist references, authentication failure language, or content rejection indicators.
5. Default: if you cannot classify a 5xx bounce, err toward NOT suppressing and flag for manual review.

### Data Store Requirements

At scale (5-20 million suppressed addresses), the suppression store must support O(1) or O(log n) lookups, atomic writes (to prevent race conditions between bounce events and subsequent sends), and append-only semantics for safety-critical categories. Each suppressed address should carry metadata: suppression reason, date, source event, original bounce code and diagnostic text, and applicable mail streams.

### Handling Address Variants

Normalize addresses before suppression lookup: lowercase the entire address. For Gmail-heavy audiences, consider dot-normalization and plus-stripping. Be aware of domain aliases (`@googlemail.com` = `@gmail.com`; Microsoft operates `@hotmail.com`, `@outlook.com`, `@live.com` as interconnected systems). Document your normalization rules so lookups are consistent with writes.

## Suppression Retention Policies

### Permanent Suppressions (No Expiry)

FBL complaints, legal/compliance suppressions, known spam traps, and explicit "do not email" requests should never be removed. Gmail's Postmaster Tools flags complaint rates above 0.10% as problematic and above 0.30% as critical.

### Long-Duration Suppressions (12-36 Months)

Address-level hard bounces should be retained for at least 12 months, with many large senders retaining them for 24-36 months or permanently. Some senders re-verify hard-bounced addresses after 12 months using real-time SMTP handshake verification services, but this should be applied conservatively — re-verify no more than once, and re-suppress immediately on any subsequent bounce.

### Medium-Duration Suppressions (6-12 Months)

Soft bounces promoted to suppression (3-5 consecutive failures over 7-14 days) and engagement-based suppressions (no opens/clicks for 180+ days) can be re-evaluated after 6-12 months through controlled re-engagement, not by simply adding them back to active sends.

### Stream-Specific Suppressions (Indefinite Until Re-Opt-In)

Unsubscribes from specific mail streams persist until the recipient explicitly re-subscribes through confirmed opt-in. Time-based expiration of unsubscribes is a compliance violation.

## What Suppression Failures Look Like in Log Data

### Under-Suppression: Addresses That Should Have Been Suppressed

A spike in `5.1.1` bounces after a list import or migration strongly suggests suppression leakage. Look for: elevated `5.1.1` rate within 1-4 hours of a send; hard bounce rate exceeding 2% when your baseline is below 0.5%; repeated `5.1.1` bounces to the same addresses across multiple sends (indicating the bounce-to-suppression pipeline is broken). Complaint rate spikes above 0.10% after sending to segments that include previously-complained addresses, or ARF reports containing addresses already in your complaint log, are definitive indicators of suppression failure.

### Over-Suppression: Valid Addresses Incorrectly Removed

Over-suppression is harder to detect because the symptom is absence — valid addresses silently stop receiving mail. The most common cause is feeding unclassified 5xx bounces into the suppression store. Indicators:

- **Sudden list shrinkage correlated with infrastructure events.** If suppressions spike by 50,000 on the same day your IP was blocklisted, and the bounce codes are predominantly `5.7.x`, those are valid addresses incorrectly suppressed.
- **Domain-concentrated suppression spikes.** If 80% of new suppressions in a single day are `@outlook.com` addresses, this is a block/policy event, not a wave of invalid addresses.
- **Post-fix delivery gap.** After resolving an infrastructure issue, delivery should resume to the affected ISP. If it does not, check whether addresses were incorrectly suppressed during the incident.

**Best practice:** Run a weekly report on suppression additions grouped by enhanced status code. Any significant volume of `5.7.x` codes in your suppression additions indicates a classification bug.

## Common Causes of Suppression Failure

**Database migrations and platform changes** are the most frequent cause of mass suppression failure. Export your full suppression list with metadata (reason, date, source, bounce code) before any migration and import it into the new platform before importing active addresses. Verify record counts match.

**List re-imports and CRM syncs** may contain previously suppressed addresses. All imports must be filtered against the suppression list as a mandatory, non-bypassable system-level control.

**Bounce misclassification** — suppressing all 5xx bounces without examining the enhanced status code — causes silent over-suppression during every block or policy event. Audit your pipeline to confirm it classifies bounces into at least three categories before suppressing.

**Race conditions** in high-volume transactional systems can allow a send between a bounce event and the suppression write. Implement a short delay (50-200ms) or synchronous suppression check.

**Inconsistent normalization** between suppression writes and send-time lookups causes misses. Define the normalization function once in a shared library and use it everywhere.

## Re-Mailing Suppressed Addresses: Risk Assessment

| Suppression Reason | Risk | Recommendation |
|---|---|---|
| FBL complaint | **Critical** | Never re-mail. Permanent suppression. |
| Legal / compliance | **Critical** | Never re-mail. Legal liability. |
| Known spam trap | **Critical** | Never re-mail. Permanent suppression. |
| Address-level hard bounce (< 12 mo) | **High** | Do not re-mail. Address almost certainly still invalid. |
| Address-level hard bounce (> 12 mo) | **Medium** | Re-verify via SMTP handshake service first. Monitor closely. |
| Block/policy bounce (incorrectly suppressed) | **Low** | Should not have been suppressed. Un-suppress after infrastructure issue is resolved. |
| Soft bounce (promoted) | **Medium** | Re-verify after 6+ months. Test on small segment first. |
| Engagement-based suppression | **Low-Medium** | Controlled re-engagement campaign with confirmed opt-in. |
| Stream-specific unsubscribe | **High** | Only if recipient explicitly re-subscribes. |

**Quantified risk:** Re-mailing 10,000 hard-bounced addresses (address-level failures) will produce approximately 7,000-9,500 bounces. A campaign with a 70% bounce rate will almost certainly trigger automated blocks at major ISPs, with recovery taking days to weeks.

## Auditing and Monitoring Suppression Health

Run a monthly suppression audit: verify total count has not shrunk without documented removals; sample 1,000 recent address-level hard bounces and confirm they appear in the suppression store; sample 100 recent suppression additions and verify the bounce codes are address-level (`5.1.x`, `5.2.1`) not policy-level (`5.7.x`); confirm bounces from the last 24 hours are reflected in the store within 1 hour; review all list imports for suppression filtering.

Track and alert on: suppression addition rate (sudden drops indicate pipeline failure; sudden spikes in `5.7.x` codes indicate misclassification); suppression additions by bounce code (any `5.7.x` codes is a classification error); hard bounce rate per campaign (alert above 2%); complaint rate (alert above 0.08%); re-bounce rate (should be zero — any non-zero value indicates enforcement failure).

## Key Takeaways

- **Distinguish address-level bounces from block/policy bounces before suppressing.** Only address-level hard bounces (`5.1.1`, `5.1.2`, `5.1.3`, `5.2.1`, `5.1.6`, `5.1.10`) trigger immediate suppression. Block/policy bounces (`5.7.1`, `5.7.23`, `5.7.25`, `5.7.26`, `5.7.27`) indicate a sender-side problem — the address is valid, so suppressing it destroys reachable audience. Fix your infrastructure instead.
- **Classify bounces before suppressing.** Your pipeline must route bounces into at least three categories — address-level hard bounce (suppress), block/policy bounce (do not suppress; fix infrastructure), and soft bounce (retry; suppress after repeated failures). Feeding raw 5xx bounces into the suppression store without classification is the most common cause of over-suppression.
- **Suppress FBL complaints immediately and permanently, and honor legal/compliance suppressions forever.** Re-mailing any of these categories carries high reputational and legal risk.
- **Enforce suppression at the point of mail injection** as the last gate before a message enters the MTA queue, mandatory for all mail streams including imports and CRM syncs.
- **Platform migrations are the highest-risk event for suppression data loss.** Export, verify, and import your full suppression list with metadata before sending from a new platform.
- **Monitor for both under-suppression and over-suppression.** A re-bounce rate above zero indicates under-suppression. A spike in `5.7.x` codes in your suppression store indicates over-suppression. Both require immediate investigation.
