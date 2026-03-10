# Email Delivery Log Field Reference

This document defines the structure and operational meaning of each field in the raw email delivery logs. It serves as the grounding reference for the ML pipeline and downstream LLM summarization — every field description here answers "what does this tell you about what's happening?"

## System Context

These logs come from a high-volume email delivery (ED) platform. Each record represents a single **delivery attempt** — the platform tried to hand an email to a recipient's mail server, and this is what happened. The platform processes hundreds of millions of delivery attempts per day across multiple sending infrastructure nodes.

### Architecture

```
Client system (campaign/automation triggers send)
  → op-queue-time: client schedules the email
    → Email enters the ED system
      → injected_time: email reaches the delivery edge (last hop we control)
        → Outbound MTA (edge server with its own IP) connects to recipient MX
          → timestamp: delivery attempt result logged (success / failure / deferral)
```

### Key Concepts

- **Engagement segments** route through **isolated IP pools**. VH traffic uses different IPs than RO traffic. Pool isolation is mechanically enforced — this prevents low-engagement traffic from contaminating high-engagement pools.
- **Deliverability should follow engagement segment, but may not.** Mailbox Providers (MBPs) have their own view of recipient activity through signals we don't see.
- **Data completeness varies.** Some records have zero-value fields where tracking data was unavailable at email creation time. These are real traffic, not errors — see the Zero Values section.

---

## Core Event Fields

### `timestamp` (float — unix epoch)
The timestamp of the **log event** — when a delivery attempt was made, regardless of outcome. This is the moment the platform got a response from the remote server, or decided the attempt was done.

**Operational meaning**: Primary time axis. The difference between `injected_time` and `timestamp` is the delivery attempt latency.

### `status` (string)
The raw outcome of this delivery attempt:

| Raw Value | Canonical | What Actually Happened |
|-----------|-----------|----------------------|
| `success` | DELIVERED | The recipient's mail server accepted the message. **This does NOT mean the recipient saw it** — it means the receiving server took responsibility for it. It could land in spam, be silently discarded, or sit in a queue. |
| `failure` | BOUNCED | The recipient's server permanently rejected the message. The platform will **not** retry. Common reasons: invalid address, blocked IP, content rejection. |
| `failure_toolong` | BOUNCED | The message was in the retry queue for too long and the platform gave up. Usually means the recipient domain was unreachable or consistently throttling for an extended period. |
| `deferral` | DEFERRED | The recipient's server temporarily rejected the message (4xx SMTP code). The platform **will** retry later. Common reasons: rate limiting, temporary blocks, server overload. |
| `connmaxout` | DEFERRED | The platform hit its own connection limit to the destination domain. The message stays in queue. This is an internal throttling mechanism, not a remote rejection. |

### `message` (string)
The full SMTP response from the recipient's mail server, or an internal platform message explaining what happened. **This is the single most information-rich field in the log.**

Contains:
- **SMTP codes** (e.g., `250`, `550`, `451`): 3-digit response category
- **Enhanced status codes** (e.g., `5.7.1`, `4.7.650`): More specific classification
- **Provider-specific error text**: Gmail, Outlook, Yahoo, Comcast each have distinctive error messages
- **Block list references**: URLs pointing to postmaster pages or blocklist lookups
- **Rate limit indicators**: "throttled", "rate limited", "try again later"
- **Internal platform messages**: e.g., "All connection backlog slots used up" or "Sorry, I wasn't able to establish an SMTP connection" — these are from the sending platform, not the remote server

This field is the primary input for the SMTP classifier. Two failures to the same domain might have completely different root causes visible only here.

### `channel` (string)
The delivery channel. Almost always `"remote"` (SMTP to an external mail server). Safe to deprioritize in analysis.

---

## Identity Fields

### `sender` (string)
The envelope sender (MAIL FROM) — the technical sending identity. Format: `{accountid}@{platform-domain}`. Example: `266907@ontramail.com`.

This is the **technical** sender, not the human-facing "From" address. The numeric prefix is the account ID within the platform. This is what receiving servers evaluate for SPF alignment.

### `from_address` (string)
The human-facing "From:" header address — what the recipient sees in their inbox. Example: `support@transformationinsider.com`.

This is the **brand identity**. Different from `sender`. Multiple campaigns may share the same `from_address`. Reputation problems can attach to either the envelope sender or the from address.

### `recipient` (string)
The target email address. The domain portion (`recipient_domain`, computed) is the primary dimension for deliverability analysis — most reputation and policy decisions happen at the domain level.

### `subject` (string)
The email subject line, extracted from headers. May contain MIME-encoded characters (e.g., `=?UTF-8?Q?...?=`). Content signal — patterns in subject lines that correlate with higher bounce/complaint rates indicate content-based filtering.

---

## Infrastructure Fields — The Sending Path

These fields describe **which piece of sending infrastructure** handled this message. Critical for diagnosing IP reputation problems.

### `mtaid` (string)
Internal Mail Transfer Agent ID — which MTA node initially processed the message. Example: `"151"`. The first-hop server. Multiple MTAs exist for load distribution.

### `outmtaid` (string)
Outbound/relay MTA ID — which edge server actually made the SMTP connection to the recipient. Example: `"146"`. This is the server that the recipient's mail server "sees."

### `outmtaid_ip` (string)
IP address of the outbound MTA. Example: `"75.119.179.23"`.

**This is the single most important infrastructure field.** IP reputation is the primary mechanism receiving servers use to decide whether to accept mail. Correlating bounce/deferral rates by `outmtaid_ip` is the fastest way to identify reputation problems.

### `outmtaid_hostname` (string)
Hostname of the outbound MTA. Example: `"mail23.ul.emldlv.net"`.

Reveals the sending infrastructure topology. Three naming patterns observed:
- `mail{N}.ul.emldlv.net` (75.119.179.x) — dedicated sending infrastructure
- `mail{N}.ontramail.com` (209.237.x.x) — platform-branded infrastructure
- `mail{N}.moon-ray.com` — another infrastructure pool

Different pools may have different reputation profiles.

### `mx_hostname` (string)
The recipient's MX (Mail Exchange) server hostname. Example: `"mx2.mxge.comcast.net"`.

Used for provider identification:
- `aspmx.l.google.com` = Gmail
- `*.olc.protection.outlook.com` = Microsoft
- `*.yahoodns.net` = Yahoo/AOL
- `*-vadesecure.net` = Vade Secure filtering
- Empty = DNS resolution failed or MX lookup failed

### `mx_ip` (string)
IP address of the recipient's MX server. Less actionable than `mx_hostname` for most analyses.

---

## Segment and Campaign Fields

### `listid` (string) — PRIMARY GROUPING KEY
The stable, non-dated segment identifier. Example: `"SEG_E_H"`.

**This is the most valuable mechanism for grouping traffic.** Each listid represents a mechanically isolated sending pool with its own IPs. ML should aggregate on `listid`, not `sendid`.

#### listid Taxonomy

| Prefix | Type | Description |
|--------|------|-------------|
| `SEG_E_*` | Engagement segments | Shared IP pools, engagement-segmented. Each suffix routes to its own isolated pool. |
| `PRIVATE_*` | Private IP senders | Dedicated IPs, NO engagement segmentation. Not on public sending pools. |
| `ISO*` | Isolation pool | Manual intervention by the ED team — testing, or traffic that doesn't qualify for public pools. |
| *(anything else)* | Bespoke | Custom routing, human-named (client name, account ID, etc). No naming pattern. Treat as first-class segments like any other. |

#### Engagement Segment Definitions (SEG_E_*)

Segmentation is based on **activity age** — days since last confirmed engagement.

| Suffix | Meaning | Activity Age (days) |
|--------|---------|---------------------|
| UK | Unknown quality (treat as medium) | Unknown/None |
| VH | Very High engagement | 0–7 |
| H | High engagement | 8–30 |
| M | Medium engagement | 31–60 |
| L | Low engagement | 61–90 |
| VL | Very Low engagement | 91–120 |
| RO | Re-engagement Only | 121–365 |
| NM | No Marketing | 366–540 |
| DS | Drop Send (suppressible in future) | 541+ |

**"Confirmed engagement"** means: a confirmed open (NOT anonymized/Apple MPP), a link click, a website visit while cookied/logged in, a form fill, or a purchase — all within the sending account's ecosystem.

**Pool isolation is enforced** — each segment routes through its own IP pool. A delivery rate drop on SEG_E_VH means the VH pool's IPs are having problems, not just "low-quality contacts bouncing."

**Suppression is NOT yet enforced** — NM and DS contacts still receive emails today. Enforcement (blocking sends) is planned for the future.

### `sendid` (string)
Format: `{listid}{YYMMDD}`. Example: `"SEG_E_H260218"` = listid `SEG_E_H` + date `260218` (Feb 18, 2026). Changes daily. **Use `listid` instead for stable grouping across time.**

### `accountid` (string)
The platform account that owns this send. May be empty — also available via XMRID in `clicktrackingid`.

### `jobid` (string)
Internal job identifier. Often empty. Lower-level batch tracking.

---

## clicktrackingid — Composite Field

This field encodes subscriber-level engagement data and send metadata. It is **semicolon-delimited with 6 fields**, and the first field (XMRID) is itself **dot-delimited with 7 sub-fields**.

Example: `0.266907.69781.478016969.1342.104.0;1770154650;1755011403;1771487908;303835594.3662783;1`

### Top-level Structure (semicolon-delimited)

| Index | Name | Type | Description |
|-------|------|------|-------------|
| 0 | XMRID | composite | Dot-delimited sub-field (see below) |
| 1 | last-active | unix timestamp | Last time contact was meaningfully active. `0` = unknown — treat as `contact-added + 15 days`. |
| 2 | contact-added | unix timestamp | When the contact was added to the account. |
| 3 | op-queue-time | unix timestamp | When the client *wanted* the email sent. Useful for computing pre-edge latency. |
| 4 | op-queue-id | opaque string | Internal queue ID linking to database. Not useful for ML/LLM. May contain a dot (e.g., `303835594.3662783`) — this is not a sub-delimiter. |
| 5 | marketing | int | `0` = transactional, `1` = marketing. |

### XMRID Sub-structure (dot-delimited within index 0)

| Index | Name | ML/LLM Useful? | Description |
|-------|------|----------------|-------------|
| 0 | object-id | No | Internal |
| 1 | account-id | **Yes** | The sending account. Key dimension for compliance tracking. |
| 2 | contact-id | **Yes** | ID of the contact within the sending account. |
| 3 | log-id | No | Internal DB link |
| 4 | message-id | **Yes** | ID associated with the *content* of the send. |
| 5 | drip-id | **Yes** | Automation entry point (campaign) that triggered the send. `0` = manual/bulk send or unknown. |
| 6 | step-id | **Yes** | Specific step/node within an automation. `0` = manual/bulk send or unknown. |

---

## The Timing Chain

Three timestamps form a latency chain:

```
op-queue-time (clicktrackingid[3])  — client says "send this"
  → injected_time (top-level)       — email reaches delivery edge (last hop we control)
    → timestamp (top-level)          — delivery attempt result logged
```

Two computable latency segments:
1. **Pre-edge latency**: `injected_time - op-queue-time` — everything between "client wants it sent" and "it's at the delivery edge." Delays here are upstream of the ED system.
2. **Delivery attempt time**: `timestamp - injected_time` — edge to resolution. Delays here are external (remote server slow, connection issues, retries).

---

## Retry and Message Identity Fields

### `is_retry` (int — 0 or 1)
Whether this is a retry (`1`) or first attempt (`0`).

- `is_retry=0`: First attempt. If it fails, the message goes into the retry queue.
- `is_retry=1`: Previously failed or deferred, now being retried.

High retry rates to a specific domain or IP indicate sustained delivery problems.

### `msguid` (string)
Unique message identifier. Example: `"1771487906.78554535"`.

Links multiple delivery attempts for the same message. If deferred and retried, both attempts share the same `msguid`. Essential for deduplication.

### `injected_time` (float — unix epoch)
When the email reached the **delivery edge** — the last point in our systems before handoff to an external MX server. This is NOT when the client triggered the send (that's `op-queue-time` in `clicktrackingid`).

The gap between `injected_time` and `timestamp`:
- **< 2 seconds**: Normal first-attempt delivery
- **Minutes to hours**: Message was deferred and retried
- **Many hours**: Persistent delivery problems

---

## Throttling and Rate Control

### `throttleid` (string or null)
Identifies the throttle group. Example: `"1491"`, or `null` if unthrottled.

Messages with the same `throttleid` share a rate limit. Non-null means the platform is actively managing sending rate to avoid overwhelming the destination.

- `connmaxout` + `throttleid` = throttle wasn't aggressive enough
- Clean delivery + `throttleid` = throttle is working

### `sendsliceid` (string)
Batch slice identifier. Usually empty. For phased delivery of very large sends.

---

## Headers

### `headers.Subject` (array)
The email subject line in original MIME encoding. Typically single element. Same content as the `subject` field.

### `headers.Reply-To` (array)
The Reply-To address. Reveals the customer's actual communication address.

### `headers.x-op-mail-domains` (string) — COMPLIANCE ANNOTATION

Represents **SPF + DKIM + DMARC compliance** at the time of email creation. This is a **first-class risk dimension** for aggregation.

Two states:

| Pattern | Meaning | Implication |
|---------|---------|-------------|
| `"compliant-from:...; compliant-mailfrom:...;"` | Sender has proper SPF + DKIM + DMARC | Email goes out as their domain. Best practice. |
| `"no-compliant-check: ontramail or opmailer"` | Sender lacks proper authentication | Platform substitutes its own compliant domain. Shows as "VIA" in Gmail. **Risk segment** — non-compliant senders on shared pools can drag down pool reputation for everyone. |

**Aggregation approach**: Anchor compliance tracking on `accountid` (from XMRID). The key question is: "when non-compliant account X sends volume, does it degrade the pool for everyone?" This enables cohort analysis correlating non-compliant sender volume with pool-wide deliverability.

---

## Computed Fields (Derived by the Pipeline)

These don't exist in the raw logs — they're computed by the `DeliveryEvent` model:

- **`normalized_status`** → `DeliveryStatus` enum (DELIVERED, BOUNCED, DEFERRED, DROPPED, COMPLAINT, UNKNOWN)
- **`recipient_domain`** → Extracted from `recipient` (everything after `@`, lowercased). Primary dimension for deliverability analysis.
- **`event_time`** → Converts `timestamp` to timezone-aware datetime.

---

## Zero Values — Data Completeness

When a field in XMRID or clicktrackingid is `0` and that doesn't make semantic sense (there is no contact-id 0, account-id 0, etc.), it means **the data was unavailable at email creation time**. The system uses `0` as a placeholder because nulls aren't allowed.

**Origin**: Scattered across many sources, mostly system-generated emails (signup confirmations, password resets, etc.) where the backend either doesn't have the data yet or hasn't been wired to include it. Hypothesis: transactional sends (`marketing=0`) are disproportionately affected — unconfirmed, the ML should help identify this.

**Rules for handling:**
- Don't silently drop zero-value records — they're real traffic
- Group them as their own cohort for analysis
- Call them out distinctly in ML output
- Don't mix them into real account/contact-level analysis

**Data completeness is a first-class ML output.** Each run should surface completeness metrics alongside deliverability metrics. This enables a feedback loop:

```
ML identifies data gaps → humans verify → engineering fixes plumbing → ML sees cleaner data → repeat
```

Don't hardcode assumptions about which fields will be zero together. Report what the data shows — completeness metrics become a progress tracker as fixes ship.

**Applies to**: account-id, contact-id, drip-id, step-id, last-active, and potentially others.

**Exception**: `last-active = 0` has a specific handling rule — the platform treats it as `contact-added + 15 days` of assumed no-engagement. This ensures unknown contacts stay off high-priority pools. The ML should apply the same transformation.

---

## ML Guidance

### Critical Aggregation Dimensions
1. **`listid`** — Primary grouping key. Mechanically isolated pools. Use instead of `sendid`.
2. **`recipient_domain`** — Gmail, Outlook, Yahoo, Comcast each behave completely differently.
3. **`outmtaid_ip`** — IP reputation is the #1 deliverability factor. Problems on specific IPs = infrastructure problems.
4. **`accountid`** (from XMRID) — Especially for compliance tracking. Non-compliant accounts are a pool-wide risk.
5. **`provider_hint`** (from SMTP classifier) — Normalizes `mx_hostname` variations into provider buckets.

### Interpreting Segment Performance
Because pools are isolated, segment-level delivery changes are **infrastructure signals**:
- A delivery rate drop on SEG_E_VH means the VH pool's IPs are having problems — that's acute
- Higher bounce rates on SEG_E_DS are expected but still worth tracking for magnitude
- Cross-segment delivery drops to the same provider suggest a provider-side issue, not a pool issue

### Common Failure Patterns
- **IP blocklisting**: Failures concentrated on specific `outmtaid_ip` values, `message` referencing blocklists
- **Domain reputation**: Failures across all IPs to a specific provider
- **Content filtering**: Failures with `message` referencing spam/content policy, often specific campaigns
- **Rate limiting**: Deferrals (not failures) with throttling language, typically to major providers during volume sends
- **List hygiene**: High bounce rates in specific segments, indicating stale addresses
- **Compliance risk**: Non-compliant sender volume correlating with pool-wide deliverability drops
