# SMTP Delivery Lifecycle

## Overview

Every email traverses a series of discrete handoff points between the moment a sending application dispatches it and the moment it lands (or fails to land) in a recipient's inbox. Each handoff produces specific, observable signals — SMTP response codes, log entries, DNS query results, authentication verdicts — that tell you exactly where and why delivery succeeded or failed. This article walks through the full lifecycle in operational detail, with the concrete indicators you need to diagnose problems at each stage.

A healthy SMTP transaction (steps 2 through 5 below) completes end-to-end in 1–30 seconds. When deferrals occur, most MTAs retry on an escalating schedule — commonly 15 minutes, 30 minutes, 1 hour, 4 hours — and abandon the message after 72 hours (configurable; Postfix defaults to 5 days, Exchange Online uses approximately 24 hours for external recipients). Messages stuck in retry queues for more than 6 hours warrant investigation. Messages that never leave the sending infrastructure at all (step 1 failures) produce no trace on the receiving side and are the hardest class of problem to catch without internal monitoring.

## Message Submission (Sender to Outbound MTA)

The sending application — a web app, marketing platform, transactional service, or mail client — connects to its designated outbound MTA. Per RFC 6409, message submission uses port 587 with STARTTLS or port 465 with implicit TLS. Port 25 is reserved for MTA-to-MTA relay and should not be used for submission from end-user applications.

During submission the outbound MTA performs several checks:

- **Authentication:** The client must authenticate via SASL (typically PLAIN or LOGIN over TLS). Unauthenticated submission attempts are rejected with `530 5.7.0 Authentication required`.
- **Envelope validation:** The MTA validates the `MAIL FROM` and `RCPT TO` addresses for syntactic correctness. Some MTAs also verify that the sender domain is authorized for the authenticated user.
- **Message size:** Most MTAs enforce a maximum message size, commonly 10–25 MB (Gmail enforces 25 MB including base64 encoding overhead, which means raw attachments should be under approximately 18.75 MB). Oversized messages receive `552 5.3.4 Message size exceeds fixed maximum message size`.
- **Rate limits:** ESPs and relay services impose per-account or per-hour sending limits. Exceeding these yields `452 4.5.3` (too many messages) or a custom `421` deferral.

**Log indicators:** Failures at this stage appear exclusively in your application logs and MTA submission logs. There is no record on the receiving side — no bounce, no rejection, no DSN. Common patterns:

- Connection refused / connection timeout — the MTA is down, unreachable, or a firewall is blocking the port.
- `535 5.7.8 Authentication credentials invalid` — wrong username or password, expired API key.
- `550 5.1.0 Sender rejected` — the authenticated user is not permitted to send from the specified envelope sender address.

**Operational note (best practice):** Monitor your submission queue depth and rejection rate. A submission rejection rate above 1% typically indicates a misconfiguration in the sending application rather than a deliverability problem.

## DNS Resolution (MX Lookup)

Once the outbound MTA accepts a message for relay, it must determine where to deliver it. The MTA extracts the domain from the `RCPT TO` address and queries DNS for that domain's MX (Mail Exchanger) records.

### MX Record Selection

MX records include a preference value (sometimes called priority). Lower preference values indicate higher priority — the MTA attempts delivery to the lowest-preference host first. If that host is unreachable or returns a temporary failure, the MTA falls back to higher-preference (higher-numbered) hosts.

If no MX records exist for the domain, RFC 5321 Section 5.1 requires the MTA to fall back to the domain's A or AAAA record and attempt delivery there on port 25. If neither MX nor A/AAAA records exist, delivery fails permanently.

### Common DNS Failure Modes

| Problem | Symptom in logs | Impact |
|---|---|---|
| Domain does not exist (NXDOMAIN) | `550 5.1.2 Bad destination mailbox address` or `Host or domain name not found` | Permanent failure; hard bounce |
| MX points to CNAME | Unpredictable — some MTAs resolve it, others reject per RFC 5321 Section 2.3.5 | Intermittent failures; difficult to diagnose |
| MX points to unreachable host | `4.4.1 Connection timed out` after 30–300 seconds per attempt | Messages queue; no hard bounce until retry limit |
| MX record has preference 0 pointing to "." (null MX, RFC 7505) | `556 5.1.10 Recipient address has null MX` | Domain explicitly does not accept email |
| DNS server timeout | `4.4.3 Temporary DNS failure` | Deferral; MTA retries |

**RFC fact:** An MX record whose target is a CNAME violates RFC 5321. While many MTAs follow the CNAME chain anyway, this is not guaranteed behavior and causes sporadic delivery failures that are notoriously difficult to troubleshoot.

**Log indicators:** DNS failures show up as deferral reasons in your MTA queue. In Postfix, inspect `mailq` output or logs for `status=deferred (Host or domain name not found)` or `(connect to mx.example.com[...]:25: Connection timed out)`. In PowerMTA, check the `acct` file for `dsnDiag` containing `4.4.1` or `4.4.3`.

**Operational note (best practice):** DNS TTLs on MX records typically range from 300 to 3600 seconds. Your MTA caches results per TTL. During a DNS outage, cached records may mask the problem until TTLs expire. Run `dig MX example.com` from your sending infrastructure periodically to verify resolution independently of cache.

## TCP Connection and TLS Negotiation

The sending MTA opens a TCP connection to the receiving mail server on port 25 (MTA-to-MTA relay always uses port 25, not 587 or 465). The receiving server responds with a 220 banner, and the SMTP conversation begins.

### The EHLO Handshake

The sending MTA issues `EHLO sending-hostname.example.com`. The hostname presented here matters: receiving servers compare it to the connecting IP's reverse DNS (PTR record). Mismatches do not violate SMTP standards but are used as a negative reputation signal by many receivers, including Gmail and Microsoft.

The receiver responds with a list of supported SMTP extensions:

```
250-mx.example.com Hello [203.0.113.5]
250-SIZE 52428800
250-8BITMIME
250-STARTTLS
250-ENHANCEDSTATUSCODES
250-CHUNKING
250 SMTPUTF8
```

### STARTTLS Upgrade

If the receiver advertises `STARTTLS`, the sending MTA issues the `STARTTLS` command and negotiates a TLS session. This is opportunistic encryption per RFC 3207 — if TLS negotiation fails, most MTAs fall back to plaintext transmission unless configured with mandatory TLS.

**RFC fact:** STARTTLS is an opportunistic upgrade. RFC 3207 does not require MTAs to refuse delivery if TLS fails. However, MTA-STS (RFC 8461) and DANE (RFC 7672) allow receiving domains to publish policies that mandate TLS, causing sending MTAs to reject plaintext fallback.

**Security consideration:** If a receiving domain publishes an MTA-STS policy with `mode: enforce`, your MTA must successfully negotiate TLS with a valid certificate matching the MX hostname, or the message will not be delivered. Check for MTA-STS policies at `https://mta-sts.example.com/.well-known/mta-sts.txt`.

### Connection-Level Failures

Failures at this stage prevent any message exchange from occurring:

- **Connection timeout (no response within 30–300 seconds):** Logged as `4.4.1`. The receiving server may be down, overloaded, or a firewall is dropping packets. Most MTAs use a 30-second initial connection timeout.
- **`421 4.7.0` at greeting:** The receiving server is actively rejecting the connection. Common causes:
  - IP address is on a blocklist (e.g., Spamhaus SBL/XBL, Barracuda BRBL).
  - Too many simultaneous connections from your IP (connection rate limiting).
  - Reverse DNS (PTR) for your IP is missing or does not resolve back to the connecting IP.
- **`421 4.7.1` with message about rate limiting:** You are sending too much mail too quickly to this receiver. Back off and reduce connection concurrency. Gmail, for example, limits connections per IP and will issue `421-4.7.0 ... try again later` when thresholds are exceeded.
- **TLS negotiation failure:** Logged as `TLS handshake failed` or similar. Common causes: expired certificate on the receiving side, cipher mismatch, or SNI misconfiguration. If MTA-STS or DANE is enforced, the message will defer. Otherwise, most MTAs fall back to plaintext.

**Log indicators:** Look for the remote IP and port in your connection logs. When a receiver has multiple MX hosts, correlate failures by MX host to determine whether the problem is specific to one server or domain-wide. Example Postfix log:

```
postfix/smtp[12345]: connect to mx1.example.com[198.51.100.1]:25: Connection timed out
postfix/smtp[12345]: connect to mx2.example.com[198.51.100.2]:25: Connection refused
```

## SMTP Envelope Exchange (MAIL FROM / RCPT TO)

After the connection and EHLO succeed, the sending MTA begins the envelope exchange. This is the phase where the receiver decides whether to accept the message for the specified sender-recipient pair — before seeing any message content.

### MAIL FROM

The sender issues `MAIL FROM:<sender@example.com>`. The receiving server may:

- Perform a callback verification (connecting to the sender's MX to verify the address exists — uncommon at large providers but used by some corporate servers).
- Check the sender domain against blocklists or policy rules.
- Verify SPF alignment if the receiver performs early SPF checks (some do this at `MAIL FROM`, others defer to post-DATA).

Common responses:

- `250 2.1.0 OK` — Sender accepted.
- `550 5.1.8 Sender domain not found` — The domain in `MAIL FROM` does not exist or has no MX/A records.
- `550 5.7.1 Sender rejected by policy` — The sending domain or address is blocked.

### RCPT TO

The sender issues `RCPT TO:<recipient@example.com>`. This is where the majority of pre-DATA rejections occur.

**Critical responses and what they mean:**

| Code | Enhanced Status | Meaning | Action |
|---|---|---|---|
| `250` | `2.1.5` | Recipient accepted | Proceed to DATA |
| `550` | `5.1.1` | User unknown / mailbox does not exist | Hard bounce — suppress this address immediately. Continued sending to invalid addresses damages sender reputation. |
| `550` | `5.7.1` | Relaying denied or policy rejection | Your IP or domain is blocked by policy. This is a reputation or authentication block, not a content block. |
| `550` | `5.2.1` | Mailbox disabled or inactive | Hard bounce — suppress. |
| `452` | `4.5.3` | Too many recipients in this session | Deferral — retry with fewer recipients per transaction (reduce `RCPT TO` count). Many receivers limit to 100 recipients per session; some as low as 10. |
| `421` | `4.7.0` | Connection-level rate limit triggered | The receiver is throttling you. Back off and reduce sending rate. |
| `450` | `4.2.1` | Mailbox temporarily unavailable | Deferral — MTA retries automatically. Often indicates the mailbox is over quota. |

**Key diagnostic principle:** Rejections at `RCPT TO` are pre-DATA. The receiver has not seen your message content — subject line, body, links, attachments are all irrelevant at this stage. A pattern of `5.7.1` rejections from a specific domain means you have an IP reputation or domain reputation problem with that receiver, or an authentication/policy misconfiguration. Do not troubleshoot these by changing email content.

**Industry convention:** Gmail, Microsoft 365, and Yahoo handle `RCPT TO` validation differently. Gmail accepts nearly all `RCPT TO` addresses and bounces asynchronously (post-acceptance DSN). Microsoft 365 rejects unknown recipients at `RCPT TO` with `550 5.1.1`. Yahoo rejects at `RCPT TO` for nonexistent accounts. This means your bounce processing pipeline must handle both synchronous rejections (at SMTP time) and asynchronous DSN bounces.

## Message Data Transfer and Server-Side Evaluation

After at least one `RCPT TO` is accepted, the sending MTA issues the `DATA` command. The receiver responds with `354 Start mail input`, and the MTA transmits the full message: headers, body, and any MIME attachments, terminated by a lone period on a line (`\r\n.\r\n`).

### What the Receiver Evaluates During DATA

The receiving server performs multiple checks between receiving the message data and issuing its final response:

1. **SPF (Sender Policy Framework):** Verifies that the sending IP is authorized by the domain in `MAIL FROM`. Result is `pass`, `fail`, `softfail`, `neutral`, `none`, `temperror`, or `permerror`. Logged in the `Received-SPF` header or `Authentication-Results` header.

2. **DKIM (DomainKeys Identified Mail):** Verifies the cryptographic signature in the `DKIM-Signature` header against the public key published in DNS (`selector._domainkey.example.com TXT`). Result: `pass` or `fail`. A DKIM signature covers specific headers and the body; modifications by intermediaries (mailing lists, forwarding) can break the signature.

3. **DMARC (Domain-based Message Authentication, Reporting, and Conformance):** Evaluates alignment — does the domain in the visible `From:` header align with the domain that passed SPF or DKIM? DMARC policy (`none`, `quarantine`, `reject`) dictates what the receiver should do on failure. A `p=reject` policy tells receivers to reject messages that fail both SPF and DKIM alignment.

4. **ARC (Authenticated Received Chain):** If the message was forwarded through an intermediary, ARC headers preserve the authentication results from earlier hops. Receivers that support ARC (Gmail, Microsoft) may use these to override DMARC failures caused by legitimate forwarding.

5. **Content filtering:** The receiver scans headers, body text, URLs, and attachments against its own spam filters, URL blocklists (e.g., Spamhaus DBL, SURBL), and malware scanners.

6. **Reputation scoring:** The receiver evaluates the sending IP's reputation, the sending domain's reputation, and often the reputation of domains in URLs within the message body.

### The Final Response to DATA

After evaluation, the receiver issues one final SMTP response:

- **`250 2.0.0 OK`** — The receiver has accepted the message. Per RFC 5321 Section 6.1, this means the receiver has taken responsibility for delivery or for generating a DSN if delivery ultimately fails. This is the point of handoff — from here, the message is the receiver's problem.
- **`550 5.7.1` (post-DATA)** — Content or policy rejection. Many providers include a diagnostic URL. Examples:
  - Gmail: `550-5.7.1 ... Our system has detected that this message is likely unsolicited mail. To reduce the amount of spam sent to Gmail, this message has been blocked. Visit https://support.google.com/mail/?p=UnsolicitedMessageError for more information.`
  - Microsoft: `550 5.7.1 Unfortunately, messages from [IP] weren't sent. Please contact your Internet service provider since part of their network is on our block list (S3150).`
- **`451 4.7.1`** — Greylisting. The receiver is temporarily rejecting the message and expects the sender to retry. Legitimate MTAs retry after 4xx responses; many spam bots do not. First-time deferrals from greylisting typically clear on retry after 5–15 minutes.
- **`552 5.3.4`** — Message too large for the receiving system.
- **`550 5.7.26`** — DMARC failure. The message failed DMARC evaluation and the sender's DMARC policy requests rejection. This response is increasingly common as more domains adopt `p=reject`.

**RFC fact:** Once a receiver issues `250` to the `DATA` command, it has accepted responsibility for the message. If the receiver subsequently determines the message is undeliverable (e.g., the mailbox is actually full, an internal filter quarantines it), the receiver must generate a Delivery Status Notification (DSN / bounce) to the envelope sender (`MAIL FROM` address). The receiver must not silently discard the message — although in practice, messages classified as spam are routinely discarded silently by large providers, which is a known deviation from RFC 5321.

**Operational note (best practice):** Parse your MTA logs for the final response to `DATA`. This response often contains the receiver's internal queue ID (e.g., Gmail returns something like `250 2.0.0 OK 1234567890 x1si12345678abc.123 - gsmtp`). Record this queue ID — it is invaluable when filing abuse reports or support tickets with the receiving provider.

## Post-Acceptance Processing and Inbox Placement

After the receiver issues `250 OK`, the SMTP transaction is complete. Your sending MTA logs a successful delivery. But from the recipient's perspective, the journey is only half over. The receiving mail system now runs internal processing that determines where the message actually ends up.

### Internal Filtering Pipeline

Large mailbox providers run multi-stage internal filtering after SMTP acceptance:

1. **Spam classifiers:** Machine learning models evaluate the message against historical patterns. Factors include sender reputation, engagement history (does this recipient open mail from this sender?), content signals, URL reputation, and domain age.
2. **Category/tab sorting:** Gmail sorts mail into Primary, Social, Promotions, Updates, and Forums tabs. Microsoft sorts into Focused and Other. Placement in Promotions or Other is not the same as spam — the message is delivered, but user engagement rates drop significantly (industry observation: Promotions tab mail sees 50–70% lower open rates than Primary tab mail).
3. **User-level filtering:** Individual user rules, trained spam filters (marking messages as spam/not-spam), and contact lists affect placement.
4. **Quarantine / admin hold:** In enterprise environments (Microsoft 365, Google Workspace), administrator-defined transport rules or Data Loss Prevention (DLP) policies may quarantine or redirect messages.
5. **Silent discard:** Some providers silently discard messages they classify as spam with high confidence, particularly from IP addresses with very poor reputation. No DSN is generated. This violates RFC 5321 but is standard practice at scale.

### Why You Cannot See Inbox Placement in SMTP Logs

This is the most important conceptual distinction in email deliverability: **a `250 OK` response is not confirmation of inbox placement.** It is confirmation that the receiving server accepted the message for processing. The final destination — inbox, spam folder, quarantine, Promotions tab, or trash — is determined after the SMTP transaction has concluded and is invisible to the sender's SMTP logs.

A delivery rate of 99% with an inbox placement rate of 40% is a real and common scenario. Your logs show near-perfect delivery, but more than half your messages are going to spam.

### Detecting Placement Problems

Since SMTP logs cannot reveal placement, you must use other signals:

- **Engagement metrics:** A sudden drop in open rates or click rates at a specific mailbox provider, while delivery rates remain stable, is the strongest indicator of spam folder placement. Benchmark: if open rates to a domain drop below 5–10% while delivery success stays above 95%, suspect spam foldering.
- **Google Postmaster Tools:** Provides domain reputation, IP reputation, spam rate (based on user spam reports), authentication success rates, and encryption metrics for mail sent to Gmail. Requires DNS verification of the sending domain. Spam rate above 0.3% is a warning; above 0.5% will begin affecting inbox placement.
- **Microsoft SNDS (Smart Network Data Services):** Provides data on mail volume, spam complaint rates, and trap hits for your sending IPs at Microsoft domains (Outlook.com, Hotmail, Live). Requires IP registration.
- **Seed list testing:** Send messages to test accounts at major providers and manually or programmatically check whether they land in inbox or spam. Services like GlockApps, 250ok (now Validity Everest), and Mail-Tester automate this.
- **Feedback loops (FBLs):** Most large providers offer ARF-format feedback loops that notify you when a recipient marks your message as spam. Sign up for FBLs with Yahoo (CFL), Microsoft (JMRP), and others. Gmail does not offer a traditional FBL; use Postmaster Tools instead.

## Asynchronous Bounces (DSN / NDR)

Not all delivery failures are synchronous (reported during the SMTP session). Some occur after the receiver has already accepted the message with `250 OK`.

### When Async Bounces Occur

- The recipient mailbox is over quota (receiver discovers this during internal delivery after SMTP acceptance).
- An internal content filter rejects the message post-acceptance.
- The message was accepted by a secondary MX (backup server) but the primary mailbox server is unreachable.
- Auto-forwarding causes a downstream delivery failure.

### DSN Format

Async bounces are sent as new email messages to the envelope sender (`MAIL FROM`) address. Per RFC 3461 and RFC 3464, they use a standardized Delivery Status Notification format with a `Content-Type: multipart/report` structure containing:

- A human-readable explanation.
- A machine-readable `message/delivery-status` part with structured fields (`Status`, `Diagnostic-Code`, `Remote-MTA`).
- Optionally, the original message headers or full message.

### Processing Async Bounces

**Best practice:** Your bounce processing system must:

1. Parse DSNs arriving at your return-path (bounce) address.
2. Classify bounces as hard (5xx status — permanent; suppress the address) or soft (4xx status — temporary; retry but suppress after repeated failures, commonly 3–5 soft bounces across 72 hours).
3. Update your suppression list in near-real-time. Continuing to send to hard-bounced addresses is one of the fastest ways to damage sender reputation.

**Industry convention:** Suppress hard-bounced addresses immediately and permanently (until the address is re-confirmed via opt-in). For soft bounces, most senders retry for 24–72 hours before suppressing. A soft bounce rate above 5% to a specific domain often indicates a systemic issue (receiver infrastructure problems, DNS changes) rather than individual mailbox issues.

**Caveat (community observation):** Gmail and some other large providers increasingly reject at SMTP time rather than generating async bounces, reducing the volume of DSNs you need to process. However, you must still handle DSNs because smaller providers, corporate mail servers, and forwarding scenarios continue to produce them.

## Putting It Together: A Delivery Timeline

To illustrate how these stages interact, here is a representative timeline for a single message:

| Time | Stage | What happens |
|---|---|---|
| T+0ms | Submission | Application connects to outbound MTA on port 587, authenticates, submits message. |
| T+50ms | DNS resolution | MTA queries DNS for recipient domain's MX records. Receives two MX hosts. |
| T+100ms | TCP connection | MTA opens TCP connection to lowest-preference MX host on port 25. |
| T+150ms | EHLO + STARTTLS | EHLO handshake; TLS negotiation completes. |
| T+200ms | MAIL FROM | Sender accepted. |
| T+250ms | RCPT TO | Recipient accepted. |
| T+300ms | DATA | Message transmitted. Receiver runs SPF, DKIM, DMARC checks, content scan. |
| T+800ms | Final response | `250 2.0.0 OK` — message accepted. SMTP transaction complete. |
| T+1–5s | Internal filtering | Receiver's spam classifier, reputation engine, and tab/folder sorting run. |
| T+5–30s | Delivery to mailbox | Message placed in recipient's inbox (or spam folder). |

Total time for a successful delivery: typically under 30 seconds. A deferred message may take hours or days to complete, with the MTA retrying on its configured schedule.

## Key Takeaways

- **Pre-DATA rejections (at MAIL FROM or RCPT TO) indicate address validity, reputation, or authentication problems — not content problems.** Do not troubleshoot `5.7.1` rejections at the envelope stage by changing your email body or subject line. Investigate IP/domain reputation and authentication (SPF, DKIM, DMARC) instead.
- **A `250 OK` to DATA confirms acceptance, not inbox placement.** Monitor engagement metrics, Postmaster Tools, and SNDS to detect spam foldering. A 99% delivery rate is meaningless if 60% of messages land in spam.
- **4xx codes are deferrals, not failures — but persistent deferrals require attention.** Your MTA retries automatically. Investigate if deferrals to a specific domain persist beyond 24 hours or if your deferred queue depth is growing steadily.
- **Process bounces aggressively: suppress hard bounces immediately, soft bounces after 3–5 repeated failures.** Failing to suppress bounced addresses is one of the fastest paths to blocklisting and reputation damage.
- **DNS misconfigurations are silent delivery killers.** Messages queue with no recipient-side evidence of a problem. Monitor your deferred queue for DNS-related hold reasons and periodically validate MX resolution from your sending infrastructure.
