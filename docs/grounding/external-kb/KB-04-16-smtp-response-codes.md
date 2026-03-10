# SMTP Response Codes Reference

## Overview

Every SMTP transaction produces numeric response codes that tell you exactly what happened and why. These codes appear in your MTA logs, bounce messages (DSNs), and ESP dashboards. Correctly interpreting them is the foundation of deliverability troubleshooting — the difference between retrying a message that will never be accepted and suppressing an address that would have resolved on its own.

SMTP response codes come from two distinct systems. The three-digit reply codes (e.g., `550`, `421`) are defined in RFC 5321 and have been part of SMTP since its inception. The extended status codes (e.g., `5.1.1`, `4.7.1`) were introduced by RFC 3463 and expanded by RFC 7504, providing finer-grained classification. Most modern MTAs return both: a three-digit code followed by an enhanced status code and a human-readable explanation. For example:

```
550 5.1.1 The email account that you tried to reach does not exist.
```

The three-digit code (`550`) drives MTA retry logic. The enhanced code (`5.1.1`) provides diagnostic detail. The text string is informational and varies by provider — never parse it programmatically for routing decisions; use the numeric codes.

## Three-Digit Reply Code Structure

The first digit determines the category of response:

| First Digit | Meaning | MTA Behavior |
|---|---|---|
| 2xx | Success | Message accepted; delivery complete at the SMTP level |
| 3xx | Intermediate | Server waiting for more data (e.g., after `DATA` command) |
| 4xx | Transient failure | MTA should retry later; message remains in queue |
| 5xx | Permanent failure | MTA should not retry; generate a bounce (DSN) |

**RFC fact (RFC 5321 Section 4.2.1):** The first digit is the only part of the three-digit code that an MTA is strictly required to act on. A compliant MTA that receives an unrecognized 5xx code must treat it as a permanent failure; an unrecognized 4xx as a temporary failure. In practice, MTAs and ESPs parse the full three-digit code and the enhanced status code for more granular handling.

The second digit indicates the category:

| Second Digit | Category |
|---|---|
| 0 | Syntax |
| 1 | Information / status |
| 2 | Connection / channel |
| 3 | Unspecified mail system |
| 4 | Unspecified (not commonly used in practice) |
| 5 | Mail delivery system |
| 7 | Security / policy |

## Enhanced Status Code Structure

Enhanced status codes follow the format `class.subject.detail` (RFC 3463):

- **Class:** `2` (success), `4` (transient failure), or `5` (permanent failure). This should match the first digit of the three-digit code, though some implementations are inconsistent.
- **Subject:** Broad category (1 = addressing, 2 = mailbox, 3 = mail system, 4 = network/routing, 5 = mail delivery protocol, 6 = message content, 7 = security/policy).
- **Detail:** Specific condition within the subject category.

The IANA maintains the full registry of enhanced status codes. The most operationally relevant ones are documented below.

## 2xx Success Codes

Success codes confirm the receiving MTA has accepted responsibility for delivering the message. Acceptance does not guarantee inbox placement — the message may still be filtered to spam, quarantined, or silently discarded by downstream content filters.

| Code | Enhanced | Meaning | Notes |
|---|---|---|---|
| 220 | — | Service ready | Returned on initial connection; includes the receiving MTA's banner |
| 250 | 2.0.0 | OK / action completed | General success. After `MAIL FROM`, `RCPT TO`, or `DATA` completion |
| 250 | 2.1.0 | Sender OK | `MAIL FROM` accepted |
| 250 | 2.1.5 | Destination address valid | `RCPT TO` accepted |
| 250 | 2.6.0 | Message accepted for delivery | Final acceptance after `DATA` phase |
| 251 | 2.1.5 | User not local; will forward | Receiving server is a relay for this recipient |
| 252 | 2.0.0 | Cannot VRFY user but will accept | Server does not confirm existence but will attempt delivery |

**Operational note (best practice):** A `250` response to `RCPT TO` does not prove the mailbox exists. Many providers (Gmail, Microsoft 365, Yahoo) accept all recipients at SMTP time and generate bounces asynchronously. This is called "accept-then-bounce" behavior, and it means you may see a `250` at SMTP time followed by a DSN bounce minutes later. Your bounce processing pipeline must handle asynchronous bounces, not just synchronous SMTP rejections.

## 4xx Transient Failure Codes (Soft Bounces)

4xx codes indicate temporary conditions. Your MTA should queue the message and retry. Most MTAs use an exponential backoff schedule — a common default is retry at 15 min, 30 min, 1 hr, 2 hr, 4 hr, 8 hr, then every 8 hours until a maximum retry period (typically 72 hours for Postfix, 24 hours for Exchange Online external delivery, configurable in all MTAs).

### 421 — Service Not Available

```
421 4.7.0 [connection.ip] Try again later, closing connection.
421 4.7.28 Our system has detected an unusual rate of unsolicited mail from your IP.
```

| Enhanced Code | Common Cause | Action |
|---|---|---|
| 4.7.0 | Rate limiting, general throttle | Reduce sending speed; wait and retry |
| 4.7.1 | Message refused due to policy | Check content, sender reputation |
| 4.7.28 | Gmail-specific rate limit | Reduce volume to Gmail; warm up slowly |

**Fact (RFC 5321 Section 3.8):** A `421` response can occur at any point in the SMTP conversation, including before the `EHLO`. It signals that the server is closing the connection. The MTA must treat the entire queued transaction as deferred.

**Provider-specific behavior:**
- **Gmail:** Returns `421-4.7.28` when your IP exceeds their inbound connection rate. Typical trigger: more than approximately 60–100 concurrent connections from a single IP to Gmail MXes, or sustained volume above what your IP's reputation supports. Backing off for 15–60 minutes usually resolves it.
- **Microsoft 365 (EOP):** Returns `421 4.7.500 Server busy. Please try again later.` during high load. Also uses `421 4.7.66` for IP or domain blocks — despite being a 4xx, this often persists until you resolve the underlying reputation issue.
- **Yahoo/AOL:** Returns `421 4.7.0 [TSS04]` for rate limiting. Yahoo's rate limits are per-IP and relatively aggressive compared to Gmail — sustained rates above 10–20 messages/second from an unknown IP will trigger deferrals.

### 450 — Mailbox Unavailable (Temporary)

```
450 4.2.1 The user you are trying to contact is receiving mail at a rate that prevents additional messages from being delivered.
450 4.1.8 Sender address rejected: Domain not found
```

| Enhanced Code | Common Cause | Action |
|---|---|---|
| 4.2.1 | Recipient mailbox rate limit / greylisting | Retry; typically clears within 5–30 min |
| 4.1.8 | Sending domain has no DNS records | Verify your domain's DNS (A/MX records) |
| 4.7.1 | Greylisting or policy deferral | Retry in 5–15 min; greylisting expects exactly this |

**Best practice:** Greylisting (RFC 6647) intentionally returns a 4xx on the first delivery attempt from an unknown sender/IP/recipient triple. A legitimate MTA retries and succeeds; spam tools often do not. If you see `450` responses that clear on second attempt (typically after 5–15 minutes), this is greylisting working as designed. No remedial action is needed beyond ensuring your MTA retries.

### 451 — Local Processing Error

```
451 4.3.0 Mail server temporarily rejected message.
451 4.7.24 The SPF record of the sending domain could not be retrieved.
```

| Enhanced Code | Common Cause | Action |
|---|---|---|
| 4.3.0 | General internal error on receiver | Retry; server-side issue |
| 4.7.24 | DNS timeout retrieving sender's SPF record | Check your SPF DNS record; ensure DNS is responsive |
| 4.7.5 | Cryptographic failure (DKIM verification timeout) | Verify your DKIM DNS records are published and responsive |

**Log pattern:** A burst of `451` responses across multiple recipient domains simultaneously usually indicates a problem on your sending infrastructure (DNS resolution failures, network issues) rather than a problem at each individual receiver. A burst of `451` to a single domain indicates an issue on that receiver's side.

### 452 — Insufficient System Storage / Too Many Recipients

```
452 4.5.3 Too many recipients
452 4.3.1 Insufficient system storage
```

| Enhanced Code | Common Cause | Action |
|---|---|---|
| 4.5.3 | Per-message recipient limit exceeded | Reduce recipients per message; RFC 5321 requires supporting at least 100, but many servers cap lower |
| 4.3.1 | Receiver's disk is full | Retry later; receiver-side issue |

**Industry convention:** Most providers accept 100 RCPT TO commands per message per RFC 5321, but some limit to 50 or fewer. Amazon SES limits to 50 per raw `SendRawEmail` call. If you see persistent `452 4.5.3`, split your recipient list into smaller batches.

## 5xx Permanent Failure Codes

5xx codes indicate the receiving MTA considers the failure permanent. Your MTA should not retry and should generate a DSN (bounce notification). However, 5xx codes span two fundamentally different bounce categories that require different responses:

- **Address-level failures (hard bounces):** The recipient address itself is invalid — the mailbox does not exist, the domain is invalid, or the account is disabled. These codes (e.g., `5.1.1`, `5.1.2`, `5.2.1`) mean the address is permanently undeliverable. Suppress immediately.
- **Sender-level failures (block/policy bounces):** The rejection is about your sending infrastructure — your IP is blocklisted, your authentication is broken, or your content triggered a policy filter. These codes (e.g., `5.7.1`, `5.7.26`, `5.7.27`) do not mean the recipient address is bad. Do NOT suppress the address; diagnose and fix the underlying infrastructure or reputation problem.

Failing to distinguish these categories is one of the most common and damaging mistakes in bounce handling. Suppressing addresses on block/policy bounces shrinks your list for no reason. Treating address-level failures as fixable infrastructure issues means you keep mailing dead addresses and degrade your sender reputation.

### 550 — Mailbox Unavailable / Request Not Taken

This is the most common permanent failure code. The enhanced status code differentiates the cause — and critically, determines whether you should suppress the address or investigate your infrastructure.

```
550 5.1.1 The email account that you tried to reach does not exist.
550 5.7.1 Service unavailable, client host [x.x.x.x] blocked using Spamhaus.
550 5.7.26 This mail has been blocked because the sender is unauthenticated. Gmail requires all senders to authenticate with either SPF or DKIM.
```

#### Address-Level Codes (Hard Bounces — Suppress the Address)

These codes indicate the recipient address is permanently invalid. Suppress on first occurrence.

| Enhanced Code | Meaning | Action |
|---|---|---|
| 5.1.0 | Other address status (sender) | Verify your envelope sender address |
| 5.1.1 | Bad destination mailbox / user unknown | Suppress immediately; address does not exist |
| 5.1.2 | Bad destination system / domain not found | Verify recipient domain; suppress if domain is invalid |
| 5.1.3 | Bad destination mailbox address syntax | Check recipient address formatting; suppress if unfixable |
| 5.1.6 | Destination mailbox has moved | Suppress; address is no longer valid at this domain |
| 5.2.1 | Mailbox disabled / inactive | Suppress; the account has been deactivated |
| 5.2.2 | Mailbox full (treated as permanent by some) | See discussion below |

**Critical operational rule (best practice):** Suppress any address that returns an address-level hard bounce on the first occurrence. Continued sending to non-existent addresses is the single fastest way to damage your IP and domain reputation. Major mailbox providers (Gmail, Microsoft, Yahoo) track your hard-bounce rate; exceeding 2% hard bounces consistently will trigger reputation penalties. Many ESPs enforce automatic suppression at the platform level.

**The 5.2.2 (mailbox full) ambiguity:** RFC 3463 defines `5.2.2` as "mailbox full," which sounds temporary. Some providers return `452 4.2.2` (transient), others return `552 5.2.2` (permanent). **Best practice:** If you receive `5.2.2`, retry for 72 hours (treating it like a soft bounce), then suppress if it persists. A permanently full mailbox is effectively an abandoned account.

#### Sender-Level Codes (Block/Policy Bounces — Fix Infrastructure, Do NOT Suppress)

These codes mean the receiving server rejected the message because of a problem with your sending reputation, authentication, or content. The recipient address itself may be perfectly valid. Suppressing these addresses is incorrect and will silently shrink your reachable audience.

| Enhanced Code | Meaning | Action |
|---|---|---|
| 5.7.1 | Message rejected due to policy (blocklist, content, auth) | Investigate — could be blocklist, content filter, or authentication failure |
| 5.7.23 | SPF validation failed | Fix your SPF record; ensure sending IP is authorized |
| 5.7.25 | DKIM validation failed | Verify DKIM signing configuration and DNS records |
| 5.7.26 | Unauthenticated mail (DMARC or general auth) | Ensure SPF and DKIM are configured and aligned |
| 5.7.27 | Sender address does not pass DMARC validation | Fix DMARC alignment — your From domain's DMARC policy is failing |

**The 5.7.1 catch-all problem:** Enhanced code `5.7.1` is the most overloaded code in practice. It can mean:

- Your IP is on a DNS blocklist (Spamhaus, Barracuda, etc.)
- Your content triggered a filter
- You failed an authentication check
- The receiver has a blanket policy rejection

When you see `5.7.1`, read the human-readable text carefully. Examples:

| Text Pattern | Likely Cause | Action |
|---|---|---|
| "blocked using Spamhaus" / "listed by" | IP or domain blocklisted | Check blocklists (Spamhaus, Barracuda, SORBS); request delisting |
| "sender is unauthenticated" | SPF/DKIM/DMARC failure | Fix authentication records |
| "message content rejected" / "spam" | Content filter hit | Review message content, URLs, attachments |
| "policy reason" / "administrative prohibition" | Receiver-specific block | Contact receiver's postmaster |

**Key point:** Once you resolve the infrastructure issue (delisting, authentication fix, content change), previously bouncing addresses at that domain will become deliverable again. Do not suppress them.

### 551 — User Not Local

```
551 5.1.6 User not local; please try <forward-address>
```

Rarely seen in practice. The receiver is suggesting the message be sent to a different address. MTAs generally do not auto-redirect. Suppress the original address; if a forwarding address is provided and you have consent, add the new address through your normal acquisition process.

### 552 — Exceeded Storage Allocation / Message Too Large

```
552 5.2.2 The email account that you tried to reach is over quota.
552 5.3.4 Message size exceeds fixed maximum message size.
```

| Enhanced Code | Meaning | Action |
|---|---|---|
| 5.2.2 | Mailbox over quota | Treat as soft bounce for 72 hours, then suppress |
| 5.3.4 | Message too large for this server | Reduce message size; check the receiver's advertised `SIZE` in EHLO response |

**Operational note:** The `SIZE` extension (RFC 1870) allows the receiving server to advertise its maximum message size during `EHLO`. Your MTA should check this and reject oversized messages before transmitting the entire `DATA` payload, saving bandwidth and time. Gmail's limit is 25 MB (after MIME encoding). Microsoft 365 defaults to 35 MB. Many corporate servers are set to 10 MB.

### 553 — Mailbox Name Not Allowed

```
553 5.1.3 Invalid address format
553 5.1.8 Sender address rejected: Domain not found
```

| Enhanced Code | Meaning | Action |
|---|---|---|
| 5.1.3 | Syntactically invalid address | Fix the address — likely contains illegal characters or formatting |
| 5.1.8 | Sender domain not found in DNS | Your sending domain has no MX or A record; fix your DNS |

### 554 — Transaction Failed

```
554 5.7.1 Service unavailable; Client host [x.x.x.x] blocked
554 5.7.9 Message not accepted for policy reasons.
```

A `554` can appear as the initial connection response (before `EHLO`), indicating the server is refusing all communication from your IP. This is the most severe form of IP-level blocking. These are block/policy bounces — do not suppress the recipient address; fix your sender reputation.

| Enhanced Code | Meaning | Action |
|---|---|---|
| 5.7.1 | Blocked by policy (often IP block) | Check blocklists; review sender reputation. Do not suppress the address. |
| 5.7.9 | Receiver-specific policy rejection | Contact postmaster; review recent sending patterns. Do not suppress the address. |
| 5.7.0 | General security issue | Investigate authentication and IP reputation. Do not suppress the address. |

**Provider-specific patterns:**

- **Gmail:** `554-5.7.1` on connection typically means your IP is on Gmail's internal block. Unlike third-party blocklists, there is no lookup tool. You must use Google Postmaster Tools to assess domain reputation and file a form via Gmail's sender troubleshooter.
- **Microsoft 365:** `550 5.7.606` or `550 5.7.607` indicates you are on Microsoft's internal block. Use their delist portal at `https://sender.office.com` to request removal. `5.7.606` is IP-based; `5.7.607` is for new or low-reputation IPs.
- **Yahoo:** `554 5.7.9 Message not accepted for policy reasons` is Yahoo's general content/reputation block. Yahoo tends to be more opaque in its rejection reasons. Check the Complaint Feedback Loop (CFL) data if you are enrolled.

### 556 — Domain Does Not Accept Mail

```
556 5.1.10 Recipient address has a null MX
```

**RFC fact (RFC 7505):** A null MX record (`example.com. IN MX 0 .`) explicitly declares that a domain does not accept email. This is a permanent, unambiguous hard bounce. Suppress immediately.

## Provider-Specific Code Extensions

Major providers augment the standard codes with proprietary extensions. These do not follow RFC numbering conventions but appear frequently in production logs.

### Gmail

| Code | Meaning |
|---|---|
| `421 4.7.28` | Rate limited; too many messages from IP |
| `550 5.7.26` | Unauthenticated sender (SPF+DKIM required since Feb 2024) |
| `550 5.7.27` | DMARC failure on message |
| `421 4.7.26` | Sending rate exceeds domain reputation allowance |
| `550 5.2.1` | Account disabled or suspended |

Gmail rate limits are dynamic and reputation-dependent. A new IP with no sending history may be limited to approximately 500 messages/hour to Gmail initially. A well-established IP with high reputation can sustain tens of thousands per hour.

### Microsoft 365 / Exchange Online Protection

| Code | Meaning |
|---|---|
| `550 5.7.606` | IP blocked by EOP |
| `550 5.7.607` | IP not provisioned for sending (new or low-rep IP) |
| `550 5.4.1` | Recipient address rejected (relay not permitted) |
| `451 4.7.500` | Server busy; temporary throttle |
| `550 5.7.708` | DMARC enforcement rejection (p=reject) |

### Yahoo / AOL

| Code | Meaning |
|---|---|
| `421 4.7.0 [TSS04]` | Rate limiting / connection throttle |
| `421 4.7.1 [TSS09]` | IP temporarily deferred due to reputation |
| `554 5.7.9` | Content or reputation block |
| `553 5.7.1 [BL21]` | IP blocklisted |
| `421 4.7.0 [GL01]` | Greylisting |

Yahoo's bracket codes (e.g., `[TSS04]`, `[BL21]`) are internal classification tags. They are not documented publicly but appear consistently in logs and are widely cataloged by the deliverability community.

## Three-Category Bounce Classification Model

The simple 4xx/5xx distinction from the RFC does not map cleanly to operational bounce handling. In practice, bounces fall into three categories with distinct causes and distinct required actions:

| Category | Cause | Key Codes | Action |
|---|---|---|---|
| **Hard bounce** | Address-level: mailbox does not exist, domain invalid, account disabled | `5.1.1`, `5.1.2`, `5.1.3`, `5.2.1`, `5.1.6`, `5.1.10` | Suppress the address immediately |
| **Block/Policy bounce** | Sender-level: reputation block, authentication failure, content rejection, blocklist hit | `5.7.1`, `5.7.23`, `5.7.25`, `5.7.26`, `5.7.27`, `4.7.x` policy | Do NOT suppress the address; fix your infrastructure |
| **Soft bounce** | Transient: mailbox full, server down, greylisting, rate limiting | `4.2.2`, `4.3.2`, `4.7.1` rate limit, `450` greylisting | Retry; suppress only after repeated failures over 72 hours |

### Why Three Categories Matter

The traditional two-category model (hard bounce = suppress, soft bounce = retry) fails because it conflates two very different 5xx scenarios:

- **`550 5.1.1` (user unknown)** and **`550 5.7.1` (IP blocklisted)** both return 5xx. Under a two-category model, both trigger suppression. But `5.1.1` means the address is dead, while `5.7.1` means your IP has a reputation problem. Suppressing a valid address because your IP is blocklisted is wrong — once you resolve the blocklist issue, that address will accept your mail again.
- **`550 5.7.26` (unauthenticated sender)** is a 5xx permanent failure, but the fix is to configure SPF/DKIM, not to suppress the address. After you fix authentication, every previously bouncing address at that domain becomes deliverable.

### Practical Classification by Enhanced Code

| Enhanced Code | Category | Suppress? | Action |
|---|---|---|---|
| `5.1.1` | Hard bounce | Yes, immediately | Address does not exist |
| `5.1.2` | Hard bounce | Yes, immediately | Domain does not exist |
| `5.1.3` | Hard bounce | Yes, if address cannot be corrected | Invalid syntax |
| `5.1.6` | Hard bounce | Yes, immediately | Mailbox moved, no forwarding |
| `5.1.10` | Hard bounce | Yes, immediately | Domain has null MX (does not accept mail) |
| `5.2.1` | Hard bounce | Yes, immediately | Account disabled/suspended |
| `5.2.2` | Soft bounce (despite 5xx) | After 72 hours of retries | Mailbox full; may be abandoned |
| `5.7.1` | Block/Policy bounce | No | Investigate blocklists, content, authentication |
| `5.7.23` | Block/Policy bounce | No | Fix SPF record |
| `5.7.25` | Block/Policy bounce | No | Fix DKIM configuration |
| `5.7.26` | Block/Policy bounce | No | Fix SPF/DKIM authentication |
| `5.7.27` | Block/Policy bounce | No | Fix DMARC alignment |
| `4.2.2` | Soft bounce | After 72 hours of retries | Mailbox full (transient form) |
| `4.3.2` | Soft bounce | No | Server temporarily unavailable |
| `4.7.0` | Soft bounce | No | Rate limiting; slow down |
| `4.7.1` | Soft bounce or Block/Policy | No | Greylisting or policy deferral; retry |
| `4.7.28` | Soft bounce | No | Gmail rate limit; slow down |

### How ESPs Handle the Three Categories

Most major ESPs internally classify bounces beyond the simple hard/soft split, though their terminology varies:

- **Amazon SES** classifies permanent bounces into subtypes: `General` (address-level), `NoEmail`, `Suppressed`, `OnAccountSuppressionList`. A `5.7.1` rejection where SES recognizes the cause as a policy block may appear as bounce type `Transient` with subtype `General` rather than `Permanent`.
- **SendGrid** separates bounce reasons into categories including `Invalid`, `Blocked`, and `Technical`. `Invalid` maps to address-level hard bounces; `Blocked` maps to block/policy bounces and is tracked separately from the hard-bounce rate.
- **Postmark** uses explicit categories: `HardBounce`, `SoftBounce`, `Blocked`, `AutoResponder`, and others. Their `Blocked` category corresponds directly to block/policy bounces and does not trigger address suppression.

## Reading Bounce Codes in MTA Logs

### Postfix

```
Feb 21 14:32:01 mail postfix/smtp[12345]: A1B2C3D4E5: to=<user@example.com>,
  relay=mx.example.com[203.0.113.10]:25, delay=1.2, delays=0.1/0/0.8/0.3,
  dsn=5.1.1, status=bounced (host mx.example.com[203.0.113.10] said:
  550 5.1.1 <user@example.com> Recipient not found (in reply to RCPT TO command))
```

Key fields: `dsn=5.1.1` (enhanced status code), `status=bounced` (permanent) or `status=deferred` (temporary), and the parenthetical text showing the remote server's full response.

### PowerMTA

```
type=b,timeLogged=2026-02-21 14:32:01,orig=sender@yourdomain.com,
  rcpt=user@example.com,dsnAction=failed,dsnStatus=5.1.1,
  dsnDiag=smtp;550 5.1.1 User unknown,dsnMta=mx.example.com
```

Key fields: `dsnAction=failed` (permanent) vs. `dsnAction=delayed` (temporary), `dsnStatus` (enhanced code), `dsnDiag` (full remote response).

### Amazon SES (SNS Bounce Notification)

```json
{
  "bounceType": "Permanent",
  "bounceSubType": "General",
  "bouncedRecipients": [{
    "emailAddress": "user@example.com",
    "action": "failed",
    "status": "5.1.1",
    "diagnosticCode": "smtp; 550 5.1.1 user unknown"
  }]
}
```

SES classifies bounces into `Permanent` (hard) and `Transient` (soft) at the platform level. The `status` field contains the enhanced code. SES automatically suppresses addresses after a hard bounce and will suspend your account if your bounce rate exceeds 5% (with warnings starting at 2%). Note that SES may classify some `5.7.x` policy rejections as `Transient` rather than `Permanent` — always check the `status` enhanced code for your own bounce processing, not just the SES-level `bounceType`.

## Uncommon but Operationally Relevant Codes

| Code | Enhanced | Meaning | Notes |
|---|---|---|---|
| 521 | 5.2.1 | Host does not accept mail | Server explicitly refuses all inbound mail (RFC 7504) |
| 523 | 5.1.0 | Message too large for server policy | Distinguished from `552` by being policy rather than quota |
| 541 | 5.7.1 | Message rejected for content/security | Less common; some filters use this instead of `550` |
| 571 | 5.7.1 | Message refused, spam policy | Used by some corporate gateways |

**RFC fact (RFC 7504):** Codes 521 and 556 were standardized specifically to handle domains that do not accept email. If your logs show these, the receiving domain has explicitly opted out of email receipt. Suppress unconditionally.

## Key Takeaways

- **The first digit drives MTA retry logic:** 4xx means retry, 5xx means stop. But 5xx does not universally mean "suppress the address." Your bounce processing pipeline must examine the enhanced status code to determine the correct suppression action.
- **Use three bounce categories, not two.** Hard bounces (address-level `5.1.x`, `5.2.1`) require immediate address suppression. Block/policy bounces (sender-level `5.7.x`) require infrastructure investigation — do not suppress the address. Soft bounces (`4.x.x`) require retry with eventual suppression after prolonged failure.
- **Suppress `5.1.1` (user unknown) on first occurrence, no exceptions.** Continuing to send to non-existent addresses degrades your sender reputation faster than almost any other practice. Keep your hard bounce rate below 2%.
- **Never suppress an address on a `5.7.x` block/policy bounce.** These rejections are about your sending reputation, authentication, or content — not the recipient address. Fix the root cause (blocklist delisting, SPF/DKIM configuration, content changes) and the addresses become deliverable again.
- **Treat `5.2.2` (mailbox full) as a soft bounce operationally** despite its 5xx classification. Retry for 72 hours, then suppress. A permanently full mailbox is an abandoned account.
- **Read the text after `5.7.1` carefully** — this single enhanced code covers blocklisting, authentication failures, content filtering, and policy blocks. The remediation is completely different depending on the actual cause.
- **Provider-specific codes (Gmail's `4.7.28`, Microsoft's `5.7.606`, Yahoo's bracket codes) are not in any RFC** but are essential knowledge for production email operations. Document the ones you encounter in your runbooks.
