# SPF (Sender Policy Framework)

## Overview

SPF (Sender Policy Framework) is a DNS-based email authentication mechanism that allows a domain owner to declare which IP addresses and hostnames are authorized to send email on behalf of that domain. Receiving mail servers check the sending IP against the SPF record published in DNS for the domain in the `MAIL FROM` (envelope sender / return-path) address. If the IP is not listed, the SPF check fails, and the receiver uses that result as one input into its filtering and delivery decisions.

SPF is defined in RFC 7208 (which obsoleted the original RFC 4408). It is one of the three pillars of modern email authentication alongside DKIM and DMARC. On its own, SPF does not prevent spam or phishing — it only answers one question: "Is this IP authorized to send mail for this domain?" What the receiver does with the answer depends on local policy, DMARC policy, and reputation scoring.

SPF operates on the envelope sender (the `MAIL FROM` address in the SMTP transaction), not the header `From:` address that the recipient sees in their mail client. This distinction is critical: SPF alone does not protect against display-name spoofing or header-From forgery. That is DMARC's role, which requires SPF (or DKIM) to pass and align with the header `From:` domain.

## How SPF Works: The Lookup Process

When a receiving mail server gets an inbound connection, it performs SPF evaluation using this sequence:

1. **Extract the domain from the `MAIL FROM` address.** If the `MAIL FROM` is `bounces@marketing.example.com`, the SPF domain is `marketing.example.com`. If the `MAIL FROM` is empty (as in DSN/bounce messages, represented as `MAIL FROM:<>`), the receiver uses the `EHLO`/`HELO` identity instead.

2. **Query DNS for a TXT record at that domain.** The receiver looks for a TXT record starting with `v=spf1`. Per RFC 7208, there must be exactly one SPF record per domain. Multiple `v=spf1` records cause a `permerror` result.

3. **Evaluate the mechanisms in the record left to right.** Each mechanism is tested against the connecting IP. The first mechanism that matches determines the result. If no mechanism matches, the default result is `neutral` unless an explicit `all` mechanism provides a different default.

4. **Return a result.** The possible results are:
   - **`pass`** — The IP is authorized. The message passes SPF.
   - **`fail`** — The IP is explicitly not authorized. The domain owner asserts this IP should not be sending for them.
   - **`softfail`** — The IP is probably not authorized. This is a weaker assertion than `fail`, commonly used during SPF deployment/testing.
   - **`neutral`** — The domain owner makes no assertion about this IP. Treated similarly to no SPF record at all.
   - **`none`** — No SPF record exists for the domain.
   - **`temperror`** — A temporary DNS error prevented evaluation (e.g., DNS timeout). The receiver should defer delivery.
   - **`permerror`** — The SPF record is malformed and cannot be evaluated (e.g., syntax error, too many DNS lookups, multiple `v=spf1` records).

**RFC fact:** The entire SPF evaluation must complete within 10 DNS lookups (the "10-lookup limit," RFC 7208 Section 4.6.4). Each `include`, `a`, `mx`, `ptr`, `exists`, and `redirect` mechanism counts as one lookup. The `ip4`, `ip6`, and `all` mechanisms do not require DNS lookups and do not count. Exceeding 10 lookups produces a `permerror`, which most receivers treat similarly to a `fail`.

## SPF Record Syntax

An SPF record is a DNS TXT record published at the domain's apex (or subdomain). The general format is:

```
v=spf1 [mechanisms] [modifiers]
```

### Mechanisms

Mechanisms are evaluated left to right. Each can be prefixed with a qualifier:

| Qualifier | Meaning | Result if matched |
|---|---|---|
| `+` (default, can be omitted) | Pass | `pass` |
| `-` | Fail | `fail` |
| `~` | Softfail | `softfail` |
| `?` | Neutral | `neutral` |

The available mechanisms:

| Mechanism | Syntax | What it does | DNS lookups consumed |
|---|---|---|---|
| `ip4` | `ip4:203.0.113.0/24` | Matches if the sender IP is in the specified IPv4 range | 0 |
| `ip6` | `ip6:2001:db8::/32` | Matches if the sender IP is in the specified IPv6 range | 0 |
| `a` | `a` or `a:other.example.com` | Matches if the sender IP matches the A/AAAA record of the specified domain (defaults to the current domain) | 1 |
| `mx` | `mx` or `mx:other.example.com` | Matches if the sender IP matches any MX host of the specified domain | 1 (plus additional lookups for MX resolution, capped at 10 MX names per `mx` mechanism) |
| `include` | `include:_spf.google.com` | Recursively evaluates the SPF record of the specified domain. If that evaluation returns `pass`, this mechanism matches. | 1 (plus the lookups consumed by the included record) |
| `exists` | `exists:%{i}._spf.example.com` | Matches if a DNS A record exists for the specified domain (supports macro expansion) | 1 |
| `ptr` | `ptr` or `ptr:example.com` | Matches if the reverse DNS of the sender IP resolves to the specified domain. **Deprecated by RFC 7208 — do not use.** Slow, unreliable, and many receivers ignore it. | 1 |
| `all` | `all` | Matches unconditionally. Always placed last to set the default policy for IPs that matched no other mechanism. | 0 |

### Modifiers

| Modifier | Syntax | Purpose |
|---|---|---|
| `redirect` | `redirect=_spf.example.com` | Replaces the current record's evaluation with the target domain's SPF record. Used to centralize SPF policy. Consumes 1 DNS lookup. |
| `exp` | `exp=explain._spf.example.com` | Points to a TXT record containing a human-readable explanation string returned when SPF fails. Rarely used in practice. |

### Example Records

**Simple direct-sending domain:**
```
v=spf1 ip4:203.0.113.10 ip4:203.0.113.11 -all
```
Only two IPs are authorized. Everything else fails hard.

**Domain using Google Workspace and a transactional ESP:**
```
v=spf1 include:_spf.google.com include:sendgrid.net -all
```
Authorizes Google's and SendGrid's IP ranges via their published SPF records.

**Domain with centralized SPF via redirect:**
```
v=spf1 redirect=_spf.corp.example.com
```
All SPF evaluation is delegated to the `_spf.corp.example.com` record.

## The 10-Lookup Limit: The Most Common SPF Problem

RFC 7208 Section 4.6.4 mandates that SPF evaluation must not require more than 10 DNS mechanisms that trigger lookups. This is the single most frequent cause of SPF breakage in organizations with multiple sending services.

### How Lookups Accumulate

Consider a record like:

```
v=spf1 include:_spf.google.com include:spf.protection.outlook.com include:sendgrid.net include:spf.mandrillapp.com include:mail.zendesk.com include:spf.sendinblue.com -all
```

Each `include` costs 1 lookup, so this record costs 6 lookups at the top level. But each included record may itself contain `include` or `a` or `mx` mechanisms that consume additional lookups. For example, `_spf.google.com` currently resolves to a chain that consumes 3–4 lookups on its own. The total across all nested includes can easily exceed 10.

### How to Count Lookups

Use tools that report the total recursive lookup count:

- `dig TXT example.com` and manually trace each include chain
- MXToolbox SPF Lookup (web-based, reports total lookups)
- `dmarcian.com/spf-survey/` (provides a detailed breakdown)
- `python3 -m pyspf` (command-line SPF evaluation with verbose output)

### What Happens When You Exceed 10 Lookups

The SPF evaluation terminates with a `permerror` result. How receivers handle `permerror`:

- **Gmail:** Treats `permerror` as an SPF failure. It will appear in the `Authentication-Results` header as `spf=permerror`. Combined with a DMARC policy of `p=quarantine` or `p=reject`, this can cause messages to be quarantined or rejected.
- **Microsoft:** Treats `permerror` as a failure. Messages may be junked depending on other signals.
- **Yahoo:** Similar to Gmail — `permerror` is treated as a negative signal.

**Best practice:** Keep your top-level SPF record at 7–8 total recursive lookups to leave headroom for changes by included third-party services (whose SPF records can change without notice, adding lookups).

### Solutions for the 10-Lookup Limit

1. **Flatten the record:** Replace `include` mechanisms with the resolved `ip4`/`ip6` ranges. This eliminates DNS lookups but creates a maintenance burden — if the ESP changes their IP ranges, your record becomes stale. Automated SPF flattening services (e.g., AutoSPF, SPF Guru, or EasySPF) monitor included records and update your flattened record automatically.

2. **Use subdomains for different mail streams:** Send marketing email from `marketing.example.com` and transactional email from `mail.example.com`, each with their own SPF record. This distributes the lookup budget across multiple domains.

3. **Consolidate ESPs:** If you have five services each with their own `include`, evaluate whether you can reduce to fewer sending providers.

4. **Use `ip4`/`ip6` for static infrastructure:** If you control the sending IP and it never changes, use `ip4:` directly instead of `include:` or `a:`. This costs zero lookups.

**Industry convention:** SPF flattening is widely practiced but introduces its own risks. If an ESP rotates IP addresses (which they do — sometimes without notice), your flattened record becomes instantly wrong. Automated flattening with monitoring is preferred over manual one-time flattening.

## Configuring SPF: Step by Step

### 1. Inventory All Authorized Senders

Before writing an SPF record, identify every system that sends email using your domain in the `MAIL FROM`:

- Your organization's mail server(s) — IP addresses or hostnames
- Marketing ESPs (Mailchimp, SendGrid, Braze, etc.)
- Transactional ESPs (Postmark, Amazon SES, Mailgun, etc.)
- CRM systems that send email (Salesforce, HubSpot)
- Support/ticketing platforms (Zendesk, Freshdesk)
- Internal applications (monitoring alerts, CI/CD notifications)
- Any server using your domain's `MAIL FROM` address

Check what `MAIL FROM` domain each service actually uses. Many ESPs use their own domain for the bounce address (e.g., `bounces.sendgrid.net`) by default, in which case SPF checks happen against the ESP's domain, not yours. If the ESP uses your domain as the `MAIL FROM` (custom return-path), then your SPF record must authorize their IPs.

### 2. Construct the Record

Start with `v=spf1`, add mechanisms for each authorized sender, and end with `-all` (hard fail) or `~all` (soft fail):

```
v=spf1 ip4:203.0.113.0/28 include:_spf.google.com include:sendgrid.net -all
```

### 3. Publish the Record in DNS

Add a TXT record at the domain (or subdomain) that appears in the `MAIL FROM`. Example DNS zone entry:

```
example.com.  IN  TXT  "v=spf1 ip4:203.0.113.0/28 include:_spf.google.com include:sendgrid.net -all"
```

**RFC fact:** The SPF record must be a single DNS TXT record. If the record exceeds 255 characters (a single DNS string limit), it must be split into multiple strings within the same TXT record. DNS automatically concatenates these strings. Most DNS providers handle this transparently. Do not create two separate TXT records — that produces a `permerror`.

### 4. Verify

After DNS propagation (typically 5 minutes to 48 hours depending on previous TTL), verify:

```bash
dig TXT example.com +short | grep spf
```

Use an online SPF validator (MXToolbox, dmarcian) to confirm the record is syntactically valid and within the 10-lookup limit.

### 5. Choose `-all` vs. `~all`

| Termination | Meaning | When to use |
|---|---|---|
| `-all` (hard fail) | Unauthorized IPs get a `fail` result. | Production configuration for domains with complete SPF records. Required for strongest protection. |
| `~all` (soft fail) | Unauthorized IPs get a `softfail` result. | During initial deployment when you are not yet confident all legitimate senders are listed. |
| `?all` (neutral) | No assertion about unauthorized IPs. | Functionally useless — provides no protection. Avoid. |
| No `all` at all | Default result is `neutral`. | Misconfiguration. Always include an explicit `all` mechanism. |

**Best practice:** Deploy with `~all` initially, monitor authentication results via DMARC aggregate reports for 2–4 weeks to confirm no legitimate senders are missing, then switch to `-all`. Once you have DMARC at `p=reject`, the distinction between `-all` and `~all` matters less because DMARC enforcement supersedes SPF's own fail/softfail distinction — but `-all` remains the correct signal of intent.

## SPF and DMARC Alignment

DMARC requires that the domain passing SPF aligns with the domain in the header `From:` address. SPF alignment means:

- The domain in `MAIL FROM` (which SPF checks) matches the domain in the header `From:` (which the user sees).
- In "relaxed" alignment mode (the default), the organizational domains must match. For example, `MAIL FROM: bounces@mail.example.com` aligns with `From: sender@example.com` because both share the organizational domain `example.com`.
- In "strict" alignment mode, the exact domains must match.

**Critical implication:** If your ESP uses its own domain as the `MAIL FROM` (e.g., `bounce-12345@esp.sendgrid.net`), SPF will pass for the ESP's domain, but it will not align with your header `From:` domain. This means SPF alignment fails under DMARC, even though SPF itself passed. You need either custom return-path configuration (so the ESP uses your domain as `MAIL FROM`) or a passing DKIM signature on your domain for DMARC to pass.

## Common SPF Misconfigurations

### Multiple SPF Records

Publishing two TXT records that both start with `v=spf1` is one of the most common mistakes. This causes a `permerror` — SPF evaluation fails entirely.

**How it happens:** An administrator adds a new ESP's `include` by creating a new TXT record instead of editing the existing one. Or a DNS migration leaves a stale SPF record alongside a new one.

**Detection:** `dig TXT example.com` returns two lines starting with `v=spf1`. Some DNS management interfaces make this error easy to commit.

**Log indicator:** `Authentication-Results: ... spf=permerror` in message headers.

### Exceeding the 10-Lookup Limit

Covered in detail above. The record is syntactically valid but operationally broken.

**Log indicator:** `spf=permerror` (same as for malformed records — the receiver does not distinguish between syntax errors and lookup limit violations in the result code).

### Missing Senders from the Record

A newly onboarded ESP or internal service starts sending with your domain but is not in the SPF record.

**Log indicator:** `spf=fail` or `spf=softfail` from specific IP ranges that correspond to the unlisted sender. The `Authentication-Results` header will show the connecting IP, which you can trace to the missing sender.

### Using `+all`

Publishing `v=spf1 +all` authorizes every IP on the internet to send as your domain. This is functionally identical to having no SPF record and provides zero protection. Some receivers treat it as a negative signal because it suggests the domain owner is either negligent or compromised.

### Overly Broad `include` Chains

Including an ESP's SPF record authorizes all of that ESP's sending IPs, not just the ones assigned to your account. If the ESP has thousands of customers on shared IPs, your SPF record authorizes those shared IPs to send as your domain. This is unavoidable with shared IP sending and is one reason dedicated IPs provide stronger authentication control.

### DNS Record Length and Formatting Errors

SPF records that exceed 255 characters per DNS string must be split correctly. Some DNS providers mishandle this:

```
; Correct — one TXT record with two strings concatenated:
example.com. IN TXT "v=spf1 ip4:203.0.113.0/24 ip4:198.51.100.0/24 " "include:_spf.google.com include:sendgrid.net -all"

; Wrong — two separate TXT records:
example.com. IN TXT "v=spf1 ip4:203.0.113.0/24 ip4:198.51.100.0/24 -all"
example.com. IN TXT "v=spf1 include:_spf.google.com include:sendgrid.net -all"
```

### PTR Mechanism Usage

The `ptr` mechanism is deprecated by RFC 7208 Section 5.5. It is slow (requires reverse DNS lookups), unreliable (many IPs lack proper PTR records), and some receivers ignore it entirely. Replace any `ptr` mechanism with explicit `ip4`/`ip6` or `a` mechanisms.

## SPF Failures in Logs

### Where SPF Results Appear

SPF results are recorded in email headers inserted by the receiving mail server:

**`Authentication-Results` header (RFC 8601):**
```
Authentication-Results: mx.google.com;
    spf=pass (google.com: domain of bounces@example.com designates 203.0.113.10 as permitted sender) smtp.mailfrom=bounces@example.com
```

```
Authentication-Results: mx.google.com;
    spf=fail (google.com: domain of bounces@example.com does not designate 198.51.100.50 as permitted sender) smtp.mailfrom=bounces@example.com
```

**`Received-SPF` header (older format, RFC 7208 Section 9.1):**
```
Received-SPF: fail (domain of example.com does not designate 198.51.100.50 as permitted sender) client-ip=198.51.100.50; envelope-from=bounces@example.com;
```

### SPF Result Patterns and What They Indicate

| Result | Header shows | Common cause | Action |
|---|---|---|---|
| `spf=pass` | `designates [IP] as permitted sender` | IP is in the SPF record. Working as expected. | None |
| `spf=fail` | `does not designate [IP] as permitted sender` | Sending IP is not authorized. Likely a missing `include` or `ip4` entry, or a sender using the wrong domain. | Identify the IP, determine which service uses it, and add it to SPF. |
| `spf=softfail` | `does not designate [IP] as permitted sender` | IP is not authorized but the domain uses `~all` instead of `-all`. | Same as `fail` — identify the missing sender. If intentional (testing), plan transition to `-all`. |
| `spf=neutral` | `is neither permitted nor denied` | The SPF record uses `?all` or the IP matched a `?`-qualified mechanism. | Review the SPF record — `?all` provides no protection. |
| `spf=none` | `no SPF record found` | The `MAIL FROM` domain has no SPF record published. | Publish an SPF record. |
| `spf=permerror` | `SPF permanent error` | The SPF record is malformed: multiple records, exceeded 10 lookups, syntax errors. | Check for duplicate records, count lookups, validate syntax. |
| `spf=temperror` | `SPF temporary error` | DNS timeout or failure during evaluation. | Transient — the receiver will defer and retry. If persistent, investigate DNS availability for the domain. |

### SMTP-Level Rejection Patterns

Some receivers reject at SMTP time based on SPF results. Common patterns in your sending MTA's logs:

**Gmail (typically does not reject at SMTP for SPF alone, relies on DMARC):**
```
550-5.7.26 This mail is unauthenticated, which poses a security risk to the
sender and Gmail users, and has been blocked. The sender must authenticate
with at least one of SPF or DKIM.
```
This `5.7.26` rejection indicates a DMARC `p=reject` enforcement where both SPF and DKIM failed or failed alignment. It is not a pure SPF rejection.

**Microsoft:**
```
550 5.7.23 The message was rejected because of Sender Policy Framework violation
```
Microsoft can reject directly on SPF `fail`, especially when the domain has `-all` and DMARC is at `p=reject`.

**Yahoo:**
```
553 5.7.1 [BL21] Connections will not be accepted from [IP], because the ip is
in Spamhaus's list; see http://postmaster.yahoo.com/errors/...
```
Yahoo frequently blocks at the connection level rather than purely on SPF, but SPF failures compound the decision.

### Identifying SPF Problems in Aggregate

When diagnosing SPF issues at scale, look for these patterns in your delivery logs:

- **Cluster of `spf=fail` results from a specific IP range:** A sender is not in your SPF record. Cross-reference the IP against your ESP configurations.
- **Sudden appearance of `spf=permerror` across all recipients:** Your SPF record was recently changed and is now malformed. Check for duplicate records or lookup limit violations.
- **`spf=temperror` spikes correlated with DNS provider outages:** Your DNS infrastructure is unreliable. Consider a secondary DNS provider.
- **`spf=pass` but `dmarc=fail`:** SPF is passing but the domain in `MAIL FROM` does not align with the header `From:` domain. This is an alignment problem, not an SPF problem per se.

## SPF for Subdomains and Non-Sending Domains

### Subdomain SPF Records

SPF records are per-domain. If you send email from `notifications.example.com`, that subdomain needs its own SPF record. SPF does not inherit from parent domains — `example.com`'s SPF record does not apply to `notifications.example.com`.

### Protecting Non-Sending Domains

If a domain or subdomain does not send email, publish a restrictive SPF record to prevent spoofing:

```
no-email.example.com. IN TXT "v=spf1 -all"
```

This tells receivers that no IP is authorized to send email for this domain. Combined with a DMARC record at `p=reject`, this provides strong protection against spoofing of non-sending domains.

**Best practice:** Publish `v=spf1 -all` on every domain and subdomain you own that does not send email. This is often overlooked for parked domains, redirector domains, and internal-only subdomains.

## SPF Record Propagation and TTL Considerations

SPF records are cached by DNS resolvers according to their TTL (Time To Live). When you change an SPF record:

- The old record remains in resolver caches until the previous TTL expires.
- During this window, some receivers will evaluate the old record and some will evaluate the new one.
- **Best practice for changes:** Lower the TTL to 300 seconds (5 minutes) at least 24 hours before making the change. Make the change. Wait for traffic to confirm the new record is working. Then raise the TTL back to a normal value (3600 seconds / 1 hour is common).

**Risk scenario:** You add a new ESP's `include` and simultaneously start sending through them. For recipients whose resolvers still have the old cached SPF record (without the `include`), SPF will fail for messages from the new ESP's IPs. This produces a burst of `spf=fail` results that can trigger DMARC enforcement actions. Always update the SPF record and wait for full propagation before starting to send from new infrastructure.

## SPF Limitations

SPF has several inherent limitations that are important to understand:

1. **SPF checks the envelope sender, not the header `From:`.** It does not directly prevent header-From spoofing. DMARC addresses this gap by requiring alignment.

2. **SPF breaks on forwarding.** When a message is forwarded (e.g., university alumni forwarding, `.forward` files, auto-forwarding rules), the forwarding server's IP is not in the original domain's SPF record. SPF fails at the final destination. SRS (Sender Rewriting Scheme) mitigates this by rewriting the envelope sender, but adoption is inconsistent. ARC (Authenticated Received Chain) provides an alternative solution for receivers that support it.

3. **SPF does not protect against cousin-domain spoofing.** An attacker using `examp1e.com` (with a numeral 1) is not affected by `example.com`'s SPF record.

4. **The 10-lookup limit constrains complex organizations.** Enterprises with many sending services may find SPF insufficient to enumerate all authorized senders.

5. **SPF authorizes IPs, not individual senders.** Including an ESP's SPF record authorizes all of that ESP's customers on shared IPs. Any customer on those shared IPs can pass SPF for your domain if they set the right `MAIL FROM`.

## Key Takeaways

- **SPF checks the `MAIL FROM` domain against the connecting IP.** It does not check the header `From:` that recipients see. SPF alone does not prevent display-name spoofing — DMARC alignment is required for that.

- **The 10 DNS lookup limit is the most common operational SPF failure.** Count lookups across all nested `include` chains. Target 7–8 total recursive lookups to leave headroom. Use `ip4`/`ip6` for static IPs and consider subdomain-based mail stream separation to distribute the lookup budget.

- **Deploy with `~all`, monitor via DMARC reports for 2–4 weeks, then switch to `-all`.** Never publish `+all` or omit the `all` mechanism. For non-sending domains, publish `v=spf1 -all` to block spoofing.

- **SPF `permerror` is as damaging as `fail` in practice.** Duplicate SPF records, syntax errors, and lookup limit violations all produce `permerror`. Monitor for this result and treat it as urgent — it means your SPF record is not functional.

- **Update SPF records and wait for DNS propagation before sending from new infrastructure.** Lower TTLs before making changes. A `spf=fail` burst from premature sending through newly authorized IPs can trigger DMARC enforcement and damage reputation.
