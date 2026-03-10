# MX Records and DNS in Email Delivery

## The DNS Resolution Chain for Email Routing

When an MTA (Mail Transfer Agent) needs to deliver a message addressed to `user@example.com`, it initiates a multi-step DNS resolution chain before any SMTP communication occurs. Understanding this chain is essential for diagnosing delivery failures, because a breakdown at any stage produces different symptoms.

**Step 1: MX record lookup.** The sending MTA queries the DNS for MX (Mail Exchanger) records of the recipient domain `example.com`. The authoritative DNS server returns zero or more MX records, each consisting of a priority value and a mail server hostname:

```
example.com.    3600  IN MX   10 mx1.example.com.
example.com.    3600  IN MX   20 mx2.example.com.
example.com.    3600  IN MX   30 mx3.backup-provider.net.
```

**Step 2: MX host address resolution.** The MTA selects the lowest-priority-number host (10 in this case) and performs an A record lookup (and/or AAAA for IPv6) on `mx1.example.com` to obtain an IP address. If the hostname returns multiple A records, the MTA may try each IP within that single MX host before moving to the next MX priority.

**Step 3: TCP connection and SMTP handshake.** The MTA opens a TCP connection to the resolved IP on port 25 and waits for the remote server's 220 banner. From this point, standard SMTP exchange (EHLO, MAIL FROM, RCPT TO, DATA) proceeds.

**Step 4: Failover.** If the connection to the first MX host fails (timeout, connection refused, or a 4xx temporary error), the MTA proceeds to the next-lowest priority MX host (20, then 30). If every MX host fails with a temporary error, the message is queued for retry. If every MX host returns a permanent 5xx error, the message bounces.

The entire chain -- MX lookup, A/AAAA resolution, TCP connect, and SMTP banner -- typically completes in 1-3 seconds under normal conditions. RFC 5321 Section 4.5.3.2 specifies a minimum initial connection timeout of 5 minutes for the SMTP greeting, but most MTAs use shorter timeouts (30-120 seconds) for the DNS and TCP phases. If any single DNS query takes more than 10-15 seconds, something is wrong at the resolver or authoritative server level.

**Fallback when no MX records exist.** RFC 5321 Section 5.1 defines a fallback: if a domain has no MX records but has an A or AAAA record, the MTA should attempt delivery directly to that address record. In practice, many modern receiving systems and spam filters treat a domain without MX records as suspicious, and some MTAs (notably Postfix with `strict_rfc821_envelopes` or similar configurations) may not attempt the fallback at all. A domain explicitly publishing a null MX record (`0 .`) per RFC 7505 declares it does not accept email.

## What MX Records Control and Do Not Control

MX records govern **inbound** mail routing. They tell the world which servers accept email for a given domain. They do not directly affect outbound sending -- a domain can send mail from any IP regardless of its MX configuration. However, MX records have several indirect effects on sending operations that are frequently overlooked:

**Bounce and DSN receipt.** When a sent message bounces, the receiving MTA generates a Delivery Status Notification (DSN) and sends it to the envelope sender address (the MAIL FROM address). If the envelope sender domain has broken MX records, these DSNs cannot be delivered. The sending organization loses visibility into hard bounces, which means list hygiene degrades silently. Over weeks, continued sending to invalid addresses accumulates reputation damage at major mailbox providers.

**Feedback loop (FBL) processing.** Complaint feedback loops from providers like Yahoo, Outlook.com, and AOL send ARF-formatted reports to the address registered in the FBL program. Many programs require the registered domain to have functional MX records. Even for those that don't, the FBL messages themselves must be receivable.

**Postmaster and abuse address reachability.** RFC 2142 specifies that `postmaster@<domain>` and `abuse@<domain>` should be functional. Operational security organizations and receiving MTAs may attempt to contact these addresses. Broken MX records prevent this, which can escalate into blocklisting if abuse reports go unacknowledged.

**Reputation signals.** Some receiving systems cross-reference the sending domain's MX infrastructure as part of their reputation assessment. A domain that can send but not receive email raises flags. This is an industry convention rather than an RFC requirement, but it is consistently observed behavior at Gmail, Microsoft, and Yahoo.

## MX Priority, Load Distribution, and Failover Mechanics

MX priority values are relative, not absolute. A configuration of `10/20/30` behaves identically to `1/2/3` or `100/200/300`. What matters is the ordering. Lower numbers mean higher priority (attempted first).

**Equal-priority records.** When multiple MX records share the same priority value, RFC 5321 Section 5.1 specifies that the sending MTA should randomize the order among those equal-priority hosts. This provides basic load distribution:

```
example.com.    IN MX   10 mx1.example.com.
example.com.    IN MX   10 mx2.example.com.
example.com.    IN MX   10 mx3.example.com.
```

With this configuration, incoming mail is distributed roughly evenly across the three servers. In practice, the randomization is per-query, so over thousands of messages the distribution approaches 33%/33%/33% but any individual sender's MTA may consistently pick the same host for the duration of that record's TTL if it caches the ordering.

**Backup MX design.** A common pattern uses a lower-priority (higher number) MX host as a backup that queues mail when the primary is unavailable:

```
example.com.    IN MX   10 mx-primary.example.com.
example.com.    IN MX   100 mx-backup.example.com.
```

The backup MX should be configured to relay mail to the primary servers, not to deliver locally. A misconfigured backup MX that accepts mail but cannot relay it to the actual mailbox servers creates a mail black hole. Additionally, open backup MX hosts that accept mail for any recipient without verifying against the primary's user directory are frequently exploited by spammers for backscatter attacks. Best practice (industry convention): backup MX servers should perform recipient verification callouts or maintain a synchronized list of valid recipients.

**How many MX records.** Most organizations publish 2-4 MX records. There is no hard limit in the DNS protocol, but RFC 5321 requires the sending MTA to try at least the first 15 MX hosts. Publishing more than 5-6 is unusual and rarely beneficial. Having at least 2 MX hosts on different network segments provides redundancy.

## Common Misconfigurations and Their Specific Symptoms

### MX Pointing to a CNAME

RFC 2181 Section 10.3 and RFC 5321 Section 5.1 explicitly prohibit MX records from pointing to a hostname that is itself a CNAME. The MX target must resolve directly to an A or AAAA record.

**What happens in practice:** Some resolvers silently follow the CNAME chain and return the correct IP. Others return `SERVFAIL` or an empty response. The behavior is resolver-dependent, which makes this misconfiguration intermittent and difficult to diagnose -- mail delivery works from some senders but fails from others.

**Log indicators:** The sending MTA may log `Host not found` or `DNS SERVFAIL` for the MX hostname, even though a direct A-record query for the same hostname resolves fine. The key diagnostic is to run `dig mx1.example.com` and look for a CNAME record in the response.

**Fix:** Create a direct A record for the MX hostname. If the target is a cloud provider service (e.g., a load balancer), create a dedicated A record pointing to the provider's IP rather than CNAMEing to their hostname.

### MX Pointing to a Nonexistent Host

If an MX hostname returns `NXDOMAIN` during the A/AAAA lookup, the sending MTA skips that host and proceeds to the next MX record. If all MX hostnames are unresolvable, the message bounces.

**SMTP error codes:**
- `550 5.1.2` -- "Bad destination mailbox address" or "Host not found" -- permanent failure when no MX host resolves.
- `450 4.4.3` -- "Directory server failure" -- temporary failure if the DNS query itself fails (timeout, SERVFAIL) rather than returning a definitive NXDOMAIN.

**Common cause:** Domain migration or hosting changes where the MX records were updated to new hostnames but the A records for those hostnames were never created, or were created in the wrong DNS zone.

### Missing MX Records Entirely

A domain with no MX records can still receive mail via the A/AAAA fallback per RFC 5321, but as noted above, many MTAs and spam filters treat this as suspicious or do not attempt the fallback.

**For sending domains:** Outbound delivery continues to work. The danger is silent: DSNs, FBL reports, and abuse notifications cannot reach the domain. This creates a blind spot that compounds over time. After 30-60 days of accumulated bounces going unnoticed, sender reputation degradation becomes measurable.

**For receiving domains:** Some fraction of inbound mail will simply not arrive, depending on the sending MTA's implementation. There is no reliable way to quantify what percentage is lost because the senders that fail to deliver simply never connect.

### Incorrect or Stale IP Addresses in MX Host A Records

The MX records may be correctly configured, but the A records they point to may reference old IPs -- servers that have been decommissioned, reassigned, or moved.

**Symptoms:** Connection timeouts (no SMTP banner received), connection refused (TCP RST), or unexpected SMTP banners from a different service or organization now occupying that IP. The last scenario is particularly dangerous: the new occupant of the IP may accept the mail and either discard it or attempt to process it.

**Log indicators:**
- `Connection timed out` after 30-120 seconds per MX host, followed by attempts to each subsequent MX host.
- `Connection refused` immediately.
- SMTP banner showing an unexpected hostname: `220 not-your-server.example.net ESMTP`.

### TTL Misconfigurations

The TTL (Time To Live) on DNS records controls how long resolvers cache the response.

**TTLs that are too low (under 300 seconds):** Cause excessive DNS query volume, increase latency on every delivery attempt, and make the domain more vulnerable to brief DNS outages. If your authoritative DNS is unreachable for even 60 seconds, every MTA trying to deliver mail to your domain in that window will fail to resolve your MX records. With a 3600-second TTL, most MTAs would still have cached the response.

**TTLs that are too high (over 86400 seconds / 24 hours):** Make DNS changes propagate very slowly. If you need to change MX hosts in an emergency (server compromise, provider migration), resolvers worldwide may continue sending mail to the old hosts for up to the TTL duration.

**Best practice (industry convention):** Use 3600 seconds (1 hour) as a standard TTL for MX records and their associated A records during normal operation. Before planned changes, lower the TTL to 300-600 seconds at least 24-48 hours in advance (i.e., at least one full current-TTL cycle before the change). After the change is complete and verified, raise the TTL back to 3600 seconds.

### DNS Propagation During MX Changes

Full global propagation of a DNS change takes up to 48 hours in the worst case, though in practice most resolvers pick up changes within the old TTL value. During the propagation window:

- Some senders will connect to the old MX hosts, others to the new ones.
- Keep the old MX hosts accepting and processing mail for at least 72 hours after the change, ideally longer.
- Monitor mail flow on both old and new MX hosts during the transition.
- If the old MX hosts cannot relay to the new backend, configure them to queue and forward.

**Fact (RFC-documented):** Resolvers must respect the TTL on cached records per RFC 1035. **Caveat (industry observation):** Some large ISP resolvers and corporate DNS proxies cache records longer than the stated TTL, particularly when the authoritative server is briefly unreachable (a behavior sometimes called "stale serving"). This is why the 72-hour overlap recommendation exceeds the theoretical maximum propagation time.

## Reverse DNS (PTR Records) for Sending IPs

Reverse DNS is a separate but closely related DNS concern for email sending. While MX records control inbound routing, PTR records on your sending IPs affect outbound deliverability.

**Forward-confirmed reverse DNS (FCrDNS):** The PTR record for your sending IP must resolve to a hostname, and that hostname's A record must resolve back to the same IP. This bidirectional verification is called FCrDNS. Example:

```
IP 198.51.100.25 -> PTR -> mail.example.com -> A -> 198.51.100.25
```

**Provider requirements (fact, documented in provider guidelines):**
- **Gmail:** Explicitly requires valid PTR records on sending IPs. Mail from IPs without PTR records may be deferred or rejected. Google's Postmaster Tools documentation states: "The sending IP must have a PTR record."
- **Microsoft (Outlook.com/Office 365):** Does not hard-reject on missing PTR but factors it into reputation scoring.
- **Yahoo:** Requires PTR records for bulk senders and may reject mail without them.

**PTR hostname conventions (best practice, industry convention):** The PTR hostname does not need to match the sending domain or the HELO/EHLO hostname, though matching the EHLO hostname is considered best practice. The PTR hostname should not look "generic" -- hostnames like `198-51-100-25.example.net` or `unknown.example.net` are treated as indicators of unconfigured or residential IPs. Prefer descriptive hostnames like `mail.example.com` or `outbound1.example.com`.

**SMTP error indicators for PTR issues:**
- `550 5.7.1 ... IP has no PTR record` -- explicit rejection.
- `421 4.7.0 ... try again later` with PTR-related text -- deferral pending reputation check.
- Gmail may return `550-5.7.1 ... The IP you're using to send mail is not authorized to send email directly to our servers. Please use the SMTP relay` -- though this can have multiple causes, missing PTR is a common one.

## DNS-Based Blocklists (DNSBLs) and Their Interaction with MX Resolution

DNSBLs are queried via DNS during the SMTP connection phase. While this is a reputation mechanism rather than a routing mechanism, it uses the same DNS infrastructure and failures are often conflated with MX/routing issues.

**How DNSBL queries work:** The receiving MTA takes the connecting IP (e.g., `198.51.100.25`), reverses the octets (`25.100.51.198`), appends the blocklist zone (e.g., `zen.spamhaus.org`), and performs an A record lookup on `25.100.51.198.zen.spamhaus.org`. If the query returns an IP (typically in the `127.0.0.x` range), the IP is listed. Different return values indicate different listing categories.

**SMTP error codes from DNSBL rejections:**
- `554 5.7.1 Service unavailable; Client host [198.51.100.25] blocked using zen.spamhaus.org`
- `550 5.7.1 Rejected - see https://www.spamhaus.org/query/ip/198.51.100.25`

**Distinguishing DNSBL issues from MX issues:** DNSBL rejections occur during or after the SMTP connection is established. If the sending MTA successfully connects on port 25 and receives a 220 banner but then gets a 5xx rejection mentioning a blocklist zone, the MX resolution chain worked correctly. The problem is IP reputation, not DNS routing.

**DNS resolution failures affecting DNSBL lookups:** If the receiving MTA cannot query the DNSBL due to DNS failures, most configurations fail open (accept the mail) rather than fail closed. However, some strict configurations will defer delivery with a 4xx until the DNSBL can be queried, which can look like a DNS-related delivery delay.

## DNSSEC and Its Relevance to Email

DNSSEC (DNS Security Extensions) provides cryptographic authentication of DNS responses, preventing spoofing and cache poisoning.

**Current state (fact):** DNSSEC is defined in RFC 4033, 4034, and 4035. Adoption for email domains remains inconsistent. Major mailbox providers query DNSSEC-signed zones and validate signatures, but most do not reject mail solely based on DNSSEC validation failures.

**DANE (DNS-Based Authentication of Named Entities):** RFC 7672 defines how TLSA records in DNSSEC-signed zones can enforce TLS on SMTP connections to MX hosts. When a receiving domain publishes DANE TLSA records, sending MTAs that support DANE will require a valid TLS certificate matching the TLSA record before delivering mail, preventing man-in-the-middle attacks.

**Practical impact (industry observation):** As of mid-2025, DANE adoption is significant in European ISPs (particularly in the Netherlands and Germany, where providers like XS4ALL and Posteo have long supported it) but limited elsewhere. For most organizations, DNSSEC and DANE are defense-in-depth measures rather than prerequisites for delivery. However, if DNSSEC is deployed incorrectly (expired signatures, mismatched keys), it can cause DNS resolution failures that break mail delivery entirely -- resolvers that validate DNSSEC will return `SERVFAIL` for zones with invalid signatures, making all records in that zone unresolvable.

## Diagnostic Commands and Procedures

A systematic approach to diagnosing MX/DNS issues uses standard command-line tools:

**Check MX records:**
```
dig example.com MX +short
# Expected output: priority and hostname pairs
# 10 mx1.example.com.
# 20 mx2.example.com.
```

**Resolve MX hostnames to IPs:**
```
dig mx1.example.com A +short
# Expected output: one or more IPv4 addresses
# 198.51.100.25

dig mx1.example.com AAAA +short
# Expected output: one or more IPv6 addresses (if configured)
```

**Verify no CNAME exists on MX hostname:**
```
dig mx1.example.com ANY +noall +answer
# Look for CNAME records -- if present, this is a misconfiguration
```

**Check reverse DNS on sending IP:**
```
dig -x 198.51.100.25 +short
# Expected output: PTR hostname
# mail.example.com.

# Then verify forward confirmation:
dig mail.example.com A +short
# Must return 198.51.100.25
```

**Check TTL values:**
```
dig example.com MX
# Look at the TTL column (second number in the answer section)
# example.com.    3600    IN    MX    10 mx1.example.com.
```

**Test SMTP connectivity to MX host:**
```
telnet mx1.example.com 25
# Or using openssl for STARTTLS testing:
openssl s_client -connect mx1.example.com:25 -starttls smtp
```

**Query a specific DNSBL:**
```
dig 25.100.51.198.zen.spamhaus.org A +short
# Empty response = not listed
# 127.0.0.x response = listed
```

**Check DNSSEC validation:**
```
dig example.com MX +dnssec
# Look for the 'ad' (Authenticated Data) flag in the response header
```

## Monitoring Recommendations

Beyond reactive diagnosis, proactive monitoring prevents MX/DNS issues from impacting delivery:

- **Monitor DNS resolution for your own MX records** from multiple geographic locations. Services like DNS monitoring tools can alert when resolution fails or returns unexpected results. Check at least every 5 minutes from at least 3 geographically distributed probes.
- **Track TTL changes** on your MX and associated A records. Unexpected TTL drops may indicate unauthorized changes or zone configuration errors.
- **Monitor SMTP connectivity** to all published MX hosts. A synthetic monitoring check that connects to port 25, verifies a 220 banner, and issues a QUIT should run every 1-5 minutes per MX host.
- **Alert on DNS query latency** from your sending MTAs. If DNS queries that normally complete in 5-50ms start taking 500ms+, investigate resolver health before it cascades into delivery timeouts and queue buildup.
- **Log analysis patterns to watch:**
  - Sudden increase in `4.4.3` (directory server failure) deferrals across multiple recipient domains suggests your local DNS resolver is failing, not the recipients' DNS.
  - `5.1.2` errors concentrated on a single recipient domain suggest that specific domain's MX is misconfigured.
  - Connection timeouts to all MX hosts of a single domain suggest a network-level issue (firewall, routing) rather than DNS.

## Key Takeaways

- The email DNS resolution chain is MX lookup, then A/AAAA lookup on the MX hostname, then TCP connection to port 25. A failure at each stage produces distinct error codes: `NXDOMAIN` on the MX hostname yields `5.1.2`, DNS timeouts yield `4.4.3`, and TCP connection failures yield connection timeout entries in logs. Diagnose by replicating the chain with `dig` commands.
- MX records must point directly to hostnames with A/AAAA records, never to CNAMEs. This is an RFC requirement (not just best practice), and violating it causes intermittent delivery failures that vary by the sender's DNS resolver implementation.
- Sending domains must have functional MX records even though MX records do not affect outbound delivery. Without them, bounce notifications and feedback loop reports cannot be received, creating a blind spot that silently degrades sender reputation over 30-60 days.
- Every sending IP must have forward-confirmed reverse DNS (PTR record). Gmail hard-requires this; Microsoft and Yahoo factor it into reputation scoring. The PTR hostname should be descriptive (e.g., `mail.example.com`), not generic or IP-derived.
- When changing MX records, pre-lower TTLs to 300-600 seconds at least 24-48 hours before the change, maintain the old MX hosts for at least 72 hours after, and monitor mail flow on both old and new hosts during the transition period.
