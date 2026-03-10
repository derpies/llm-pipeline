# IP Reputation vs. Domain Reputation

## Overview

Mailbox providers evaluate inbound mail against two parallel reputation systems: one tied to the sending IP address and one tied to the sending domain. Both systems exist because neither alone is sufficient — IP addresses can be shared, recycled, or spoofed at the SMTP envelope level, while domain identifiers can be forged without proper authentication. Modern filtering stacks weight both signals, but the balance between them has shifted substantially over the past decade. Understanding which axis carries more weight, how each is built, and how to monitor both is essential for diagnosing delivery problems that authentication alone cannot explain.

The core distinction: **IP reputation** answers "has this mail server historically sent good mail?" while **domain reputation** answers "has this brand/entity historically sent good mail?" A sender can have a clean IP and a damaged domain reputation (e.g., after a spam complaint spike on a dedicated IP that was later swapped), or a strong domain reputation undermined by a newly provisioned IP with no history.

## How IP Reputation Works

### What Gets Tracked

IP reputation is computed per IPv4 address (or, less commonly, per IPv6 /64 or /48 prefix). The receiving MTA records the IP address from the TCP connection during the SMTP handshake — this is the connecting IP, not necessarily the IP listed in `Received` headers from earlier hops. The following signals feed into IP reputation at major providers:

- **Volume and consistency:** How many messages per hour/day originate from this IP, and how stable is that volume over time. Sudden spikes (e.g., going from 500/day to 50,000/day) trigger throttling regardless of content quality.
- **Bounce rate on delivery attempts:** The ratio of RCPT TO commands that result in `550 5.1.1` (user unknown) responses. IPs that consistently attempt delivery to nonexistent addresses are penalized. Thresholds vary by provider, but hitting invalid recipients on more than 2-5% of delivery attempts is a strong negative signal.
- **Spam complaint rate:** When recipients mark messages as spam, that signal is attributed back to both the sending IP and the authenticated domain. At Gmail, complaint rates above 0.1% trigger warnings in Postmaster Tools; above 0.3% causes measurable filtering degradation.
- **Spamtrap hits:** Messages delivered to known spamtrap addresses are extremely damaging to IP reputation. A single hit to a pristine (never-valid) trap on a monitored network can result in immediate blocklisting.
- **Blocklist presence:** Many receiving MTAs query DNS-based blocklists (DNSBLs) in real time during the SMTP transaction. If the connecting IP is listed on Spamhaus SBL/XBL, Barracuda BRBL, or similar lists, the connection may be rejected outright with a `554 5.7.1` or `421 4.7.0` response before the DATA command.

### Shared vs. Dedicated IPs

The question of IP ownership is fundamental to how IP reputation affects you:

**Dedicated IP:** You are the sole sender on this IP. Your reputation is entirely your own — you build it, you damage it, you repair it. This gives full control but also full accountability. A dedicated IP with no sending history starts with neutral (not positive) reputation. Most providers will throttle or defer mail from unknown IPs, which is why IP warming is necessary (see below).

**Shared IP:** Multiple senders share the same IP, typically through an ESP. Your mail inherits the aggregate reputation of all senders on that IP. This can be beneficial if the other senders are high-quality, or catastrophic if a co-tenant sends spam. You have no control over your IP reputation in a shared pool. If you observe block/policy bounces with messages like `550 5.7.1 Mail from IP x.x.x.x rejected due to poor reputation`, the problem may not be your traffic at all.

**Practical threshold (industry convention):** Most ESPs recommend moving to a dedicated IP once you consistently send more than 50,000-100,000 messages per month. Below that volume, it is difficult to build and maintain stable IP reputation on a dedicated IP — providers need sufficient signal to differentiate you from a newly provisioned spam source.

### IP Warming

A new dedicated IP has no reputation history. Major mailbox providers (Gmail, Microsoft, Yahoo) will aggressively rate-limit or defer mail from unknown IPs. IP warming is the process of gradually increasing send volume to build positive reputation.

**Typical warming schedule (best practice, not standardized):**

| Day | Approximate Daily Volume |
|-----|--------------------------|
| 1-2 | 200-500 |
| 3-4 | 500-1,000 |
| 5-7 | 1,000-5,000 |
| 8-14 | 5,000-20,000 |
| 15-21 | 20,000-50,000 |
| 22-30 | 50,000-100,000 |
| 30+ | Full volume |

During warming, send first to your most engaged recipients — those who have opened or clicked in the past 30-60 days. Positive engagement during the warming period accelerates reputation building. If you see deferral rates above 10-15% on a warming IP, slow down; pushing harder compounds the problem.

**Log indicators during warming problems:**
- `421 4.7.0 Try again later` (Gmail)
- `452 4.7.1 Throttling - too many messages from IP` (various)
- `421 RP-001 The mail server IP connecting to Outlook.com has exceeded the connection limit` (Microsoft)

These are soft bounces — they indicate rate limiting, not rejection. The correct response is to queue and retry with exponential backoff, not to suppress addresses.

## How Domain Reputation Works

### Which Domain Identifiers Matter

Domain reputation is more complex than IP reputation because multiple domain identifiers are present in a single message, and providers may evaluate different ones:

- **RFC5321.MailFrom (envelope sender / Return-Path):** The domain in the SMTP `MAIL FROM` command. This is the domain SPF validates against. If you use an ESP, this may be a subdomain of your own domain (e.g., `bounce.example.com`) or the ESP's domain.
- **RFC5322.From (header From):** The domain visible to the recipient in their mail client. This is the domain DMARC alignment checks against. This is the most important domain identifier for reputation at Google and Microsoft.
- **DKIM signing domain (d= value):** The domain in the `d=` tag of the DKIM-Signature header. Must align with the header From domain to pass DMARC in DKIM-alignment mode. Google Postmaster Tools tracks reputation against this domain.
- **HELO/EHLO domain:** The domain the sending MTA presents during the SMTP greeting. Less significant for reputation but validated by SPF if no MAIL FROM domain is present (e.g., bounce messages). Misconfigured HELO hostnames that resolve to different IPs or fail FCrDNS checks can contribute to negative scoring.

**Fact (RFC 7489 - DMARC):** DMARC alignment requires that either the SPF-authenticated domain or the DKIM-authenticated domain matches the organizational domain in the header From field. This alignment is what connects authentication results to the visible sending identity and thus to domain reputation.

**Best practice:** Use your own domain (or a subdomain of it) for all of these identifiers. Sending with `MAIL FROM: bounce.yourdomain.com`, `From: notifications@yourdomain.com`, and `d=yourdomain.com` in DKIM means all reputation — positive and negative — accrues to your domain identity rather than being split across your domain and your ESP's domain.

### What Feeds Into Domain Reputation

Domain reputation systems ingest signals similar to IP reputation but tied to the authenticated domain identity rather than the connecting IP:

- **Engagement signals:** Open rates, click rates, reply rates, "this is not spam" rescues, time spent reading. Google has explicitly stated that engagement is a primary signal for domain reputation in Gmail's filtering. Domains whose mail is consistently ignored, deleted without reading, or auto-archived accumulate negative engagement reputation.
- **Spam complaints:** Attributed to the header From domain. This is the single most damaging signal. Google Postmaster Tools reports complaint rate per authenticated domain.
- **Spamtrap hits:** Attributed to both IP and domain. The domain connection persists even if you change IPs.
- **Content patterns:** Domains that consistently send mail with characteristics matching known spam patterns (misleading subject lines, excessive link density, heavy image-to-text ratios) develop content-associated reputation penalties.
- **Authentication pass rate:** Domains with high DMARC pass rates are scored more favorably than domains with mixed authentication results. A domain that intermittently fails DKIM or SPF looks like it may be partially spoofed.
- **Complaint feedback loops (FBLs):** Microsoft, Yahoo, and others provide FBL data that associates complaints with the domain identity. Consistent complaint rates above 0.1% erode domain reputation.

### Subdomain Reputation Isolation

A critical operational consideration: reputation at the subdomain level is partially isolated from the parent domain, but not fully.

**Google (community observation, not officially documented):** Gmail appears to track reputation at both the exact subdomain and the organizational domain level. A subdomain (`promo.example.com`) that develops poor reputation will primarily affect mail sent from that subdomain, but sufficiently bad reputation can bleed upward to affect `example.com` and other subdomains. Conversely, a new subdomain with no history may initially inherit some reputation signal from the parent domain.

**Microsoft (community observation):** Outlook/Hotmail appears to be more aggressive about associating subdomain reputation with the parent domain. Segmenting promotional and transactional mail across subdomains (`promo.example.com` vs. `txn.example.com`) provides some isolation but is not a firewall.

**Best practice:** Use separate subdomains for transactional mail (password resets, order confirmations) and marketing/promotional mail. This provides partial reputation isolation so that a complaint spike from a marketing campaign does not drag down transactional delivery. Configure separate DKIM selectors and SPF records for each subdomain.

## Which Matters More: IP or Domain?

### The Shift Toward Domain Reputation

Over the past 5-7 years, major mailbox providers have progressively shifted filtering weight from IP reputation toward domain reputation. The reasons are structural:

1. **Cloud sending infrastructure:** The growth of ESPs, cloud MTAs, and shared sending platforms means that millions of senders share relatively small IP pools. Evaluating senders by IP alone penalizes legitimate senders who share IPs with spammers, and allows spammers to benefit from clean shared pools.

2. **IPv6 adoption:** IPv6 provides an effectively unlimited address space, making IP-based reputation impractical as a sole filtering mechanism. A spammer can burn through millions of IPv6 addresses without reusing one.

3. **Authentication maturity:** DKIM and DMARC adoption has reached sufficient scale (as of 2025, roughly 80%+ of legitimate commercial email carries valid DKIM signatures with DMARC alignment) that domain identity is now a reliable, persistent identifier. This was not the case a decade ago when authentication coverage was sparse.

4. **Google's explicit statements:** Google has publicly stated through Postmaster Tools documentation and blog posts that domain reputation is the primary signal for Gmail filtering decisions when the domain is authenticated. IP reputation remains a factor but is secondary for authenticated mail. For unauthenticated mail, IP reputation is still dominant because there is no verified domain identity to evaluate.

### Current Provider Weighting (Industry Convention / Community Observation)

| Provider | Primary Signal | Secondary Signal | Notes |
|----------|---------------|-----------------|-------|
| Gmail | Domain reputation (DKIM d= domain) | IP reputation | Domain reputation dominates for DKIM-authenticated mail. IP reputation is still significant for unauthenticated mail and for initial throttling of new IPs. |
| Microsoft (Outlook.com, Exchange Online) | Blended IP + domain | SmartScreen content filtering | Microsoft appears to weight IP reputation more heavily than Google does. SenderScore (from Validity, which acquired Return Path) correlates well with Microsoft delivery outcomes. |
| Yahoo/AOL | IP reputation + domain reputation | Content filtering, engagement | Yahoo historically leaned heavily on IP reputation. Post-DMARC enforcement (2014+), domain reputation has increased in importance. |
| Apple Mail (iCloud) | IP reputation | Limited domain-level signals | Apple's filtering is less sophisticated than Google/Microsoft. IP reputation and blocklist queries remain primary. |

**Key implication:** If you are primarily sending to Gmail recipients (common for B2C senders in the US), domain reputation is the dominant factor. If your recipient base is heavily Microsoft-oriented (common for B2B senders), IP reputation still carries substantial weight. A multi-provider recipient base requires attention to both axes.

### When IP Reputation Still Matters Most

Despite the shift toward domain reputation, there are scenarios where IP reputation is the decisive factor:

- **New domain with no reputation:** A domain sending its first email has no domain reputation. The IP reputation (if the IP has history) is the only signal available.
- **Failed or absent authentication:** If DKIM fails verification, SPF fails, and DMARC is not deployed, the receiving MTA has no authenticated domain identity. It falls back to IP-based evaluation.
- **Connection-level blocking:** Blocklist lookups happen before the DATA command — before the receiver even sees the message headers or DKIM signature. If the IP is on Spamhaus SBL, the connection is rejected before domain reputation can be evaluated. Log example: `550 5.7.1 Service unavailable; client [x.x.x.x] blocked using zen.spamhaus.org`.
- **Rate limiting/throttling:** Initial rate limits on new or low-reputation IPs are applied at the connection level, before domain-level evaluation occurs.

## Monitoring IP Reputation

### External Tools

- **Google Postmaster Tools:** Provides IP reputation ratings (High, Medium, Low, Bad) for IPs that send significant volume to Gmail. Requires domain verification. Only shows data when daily volume exceeds approximately 200-500 messages to Gmail. The reputation rating updates daily.
- **Microsoft SNDS (Smart Network Data Services):** Provides data on mail volume, complaint rates, and trap hits per IP for mail sent to Microsoft consumer properties (Outlook.com, Hotmail). Requires IP ownership verification. Shows a traffic light status (green/yellow/red) per IP.
- **Validity/Everest SenderScore:** Provides a 0-100 score per IP based on data from the Validity network. Scores above 80 are generally considered good; below 70 indicates deliverability risk. Free lookup at senderscore.org. Updated daily.
- **DNS Blocklist Queries:** Check your sending IPs against major blocklists directly via DNS. The critical lists to monitor:
  - `zen.spamhaus.org` (combined SBL/XBL/PBL)
  - `b.barracudacentral.org`
  - `bl.spamcop.net`
  - `dnsbl.sorbs.net`

  To query manually: `dig +short <reversed-IP>.zen.spamhaus.org`. A result of `127.0.0.2` means listed on SBL; `127.0.0.4` means XBL (exploited hosts); no result means not listed.

- **MXToolbox:** Aggregates blocklist lookups across 50+ lists. Useful for quick checks but some of the minor lists it queries are not widely used by receiving MTAs.

### Internal Monitoring

Monitor your own MTA logs for signals of IP reputation problems:

- **Deferral rate by IP:** Track the percentage of delivery attempts that receive `4xx` responses, broken out by sending IP. A deferral rate above 5% on an established IP warrants investigation. Example log pattern: `421 4.7.28 Our system has detected an unusual rate of unsolicited mail originating from your IP address` (Gmail).
- **Block/policy bounce rate by IP:** Track `5xx` rejections that reference the IP explicitly. Example: `550 5.7.1 [x.x.x.x] Our system has detected that this message is likely unsolicited mail` (Gmail) or `550 SC-001 Mail rejected by Outlook.com for policy reasons... Reasons for rejection may be related to content with spam-like characteristics or IP/domain reputation` (Microsoft).
- **FCrDNS (Forward-Confirmed Reverse DNS):** Verify that each sending IP has a PTR record, and that the hostname in the PTR record resolves back to the same IP via an A record. Missing or mismatched rDNS is a strong negative signal. Most providers will not deliver mail from IPs without valid rDNS. Check: `dig +short -x <IP>` then `dig +short <hostname>` and confirm the IP matches.
- **Connection refusals:** Track how often your MTA cannot establish a TCP connection to the receiving MTA. While this can indicate a network issue, it can also indicate IP-level blocking at the network layer (before SMTP even begins).

## Monitoring Domain Reputation

### External Tools

- **Google Postmaster Tools — Domain Reputation:** Provides a domain reputation rating (High, Medium, Low, Bad) for domains that send authenticated mail to Gmail. This is the single most authoritative source for Gmail domain reputation. Requires minimum volume of roughly 100+ authenticated messages per day to display data.
  - **High:** Mail is rarely filtered to spam. This is the target state.
  - **Medium:** Some mail may be filtered. Investigate recent changes in sending patterns or complaint rates.
  - **Low:** Significant spam filtering is occurring. Likely triggered by elevated complaints or spamtrap hits.
  - **Bad:** Most mail is being filtered to spam or rejected. Requires immediate remediation — typically a sending pause and list hygiene.

- **Google Postmaster Tools — Spam Rate:** Shows the percentage of authenticated mail from your domain that recipients reported as spam. This is displayed as a percentage (e.g., 0.05%). Cross-reference with domain reputation: if spam rate rises above 0.1%, expect domain reputation to degrade within 1-3 days. Above 0.3%, expect a drop to Low or Bad within days.

- **Microsoft SNDS:** Primarily IP-focused but complaint data can be cross-referenced with domain sending patterns.

- **Yahoo/AOL CFL (Complaint Feedback Loop):** Provides per-message complaint data that can be aggregated by domain. Requires registration at feedbackloop.yahoo.net.

### Internal Domain Reputation Indicators

Since mailbox providers do not expose domain reputation scores as granularly as IP reputation, you must infer domain reputation from delivery outcomes:

- **Inbox placement rate:** Track whether mail is landing in inbox vs. spam folder. Tools like Validity Everest, GlockApps, or seed-list-based monitoring provide this visibility. A sudden drop from 95%+ inbox placement to below 80% indicates a reputation shift.
- **Engagement metrics:** Monitor open rates, click rates, and unsubscribe rates by domain. Declining engagement is both a symptom and a cause of reputation degradation — less engagement leads to lower reputation, which leads to more spam folder placement, which leads to even less engagement (a feedback loop).
- **DMARC aggregate reports:** Your DMARC `rua` reports contain per-source breakdowns of authentication pass/fail rates. A sudden increase in DKIM failures from your known sending sources indicates a signing infrastructure problem that will affect domain reputation. Reports also reveal unauthorized sources sending mail using your domain — spoofing that damages domain reputation if your DMARC policy is `p=none`.
- **Response code patterns tied to domain:** Some providers include domain-specific messaging in rejections. Example: `550-5.7.26 This message does not have authentication information or fails to pass authentication checks (SPF or DKIM). To best protect our users from spam, the message has been blocked.` (Gmail, indicating domain authentication failure impacting reputation evaluation).

## Diagnosing Whether a Problem Is IP-Based or Domain-Based

When delivery degrades, determining whether the root cause is IP reputation, domain reputation, or both is critical to choosing the correct remediation:

| Signal | IP Problem | Domain Problem |
|--------|-----------|----------------|
| Google Postmaster Tools IP reputation | Low/Bad | Normal/High |
| Google Postmaster Tools domain reputation | Normal/High | Low/Bad |
| Switching to a new, clean IP fixes delivery | Yes | No — problem follows the domain |
| Problem persists after changing ESP/IP pool | No | Yes — problem follows the domain |
| Blocklist listed | Yes (IP listed) | Sometimes (some lists track domains) |
| Rejection message references IP | Yes (`client [IP] blocked`) | No |
| Rejection message references domain | No | Yes (`domain has been blocked`) |
| Problem affects only one mailbox provider | Could be either | Often domain (especially Gmail) |
| Problem affects all providers simultaneously | Likely IP (blocklist) | Less common for domain-only |

**Diagnostic procedure:**

1. Check Google Postmaster Tools for both IP reputation and domain reputation ratings.
2. Check SNDS for IP reputation at Microsoft.
3. Query DNS blocklists for the sending IP.
4. Review DMARC aggregate reports for authentication failures.
5. Check complaint rate in Postmaster Tools. If complaint rate is elevated and domain reputation is Low/Bad but IP reputation is fine, the problem is domain-based.
6. If IP reputation is Low/Bad but domain reputation is High, consider whether the IP is shared (co-tenant problem) or whether you have recently changed IPs without warming.

## Remediation Strategies

### IP Reputation Recovery

- **If blocklisted:** Submit delisting requests to the specific blocklist. Spamhaus provides a self-service delisting portal. Spamcop listings expire automatically after 24-48 hours if no further spam is received from the IP. Barracuda requires a manual request. Fix the underlying cause (compromised account, bad list, misconfiguration) before requesting delisting — repeated listing-delisting cycles lead to longer listing durations.
- **If throttled at a provider:** Reduce volume from the affected IP. Gmail throttling typically recovers within 24-48 hours if volume is reduced and engagement remains positive. Microsoft throttling can persist longer (up to 1-2 weeks) and may require submitting a support request via the Outlook.com sender support form.
- **If reputation is degraded without blocklisting:** Reduce volume, send only to engaged recipients, and wait. IP reputation at Gmail typically takes 2-4 weeks to recover with consistently positive sending signals. Aggressive list hygiene (removing 90-day-inactive recipients) accelerates recovery.
- **IP replacement as a last resort:** If an IP is severely damaged, switching to a new IP and warming it properly can be faster than rehabilitating the old IP. However, if the underlying sending practices are not fixed, the new IP will develop the same problems within weeks.

### Domain Reputation Recovery

Domain reputation is harder to recover than IP reputation because you cannot simply switch to a new domain without losing all brand recognition and trust history:

- **Immediately reduce volume** to only your most engaged recipients (opened or clicked within the last 30 days). This concentrates positive engagement signals.
- **Pause promotional/marketing sends** and continue only transactional mail (which has naturally higher engagement) if you are using separate subdomains.
- **Scrub your list** of hard bounces, chronic non-openers (no engagement in 90+ days), and known spamtrap patterns. Re-confirm opted-in subscribers if complaint rates are high.
- **Audit your DMARC reports** for unauthorized senders. If spoofing is contributing to reputation damage, move your DMARC policy from `p=none` to `p=quarantine` or `p=reject` to stop fraudulent mail from being delivered under your domain.
- **Timeline:** Domain reputation recovery at Gmail typically requires 2-6 weeks of consistently clean sending. Microsoft domain reputation recovery is less predictable and can take longer. During recovery, monitor Postmaster Tools daily — the reputation rating should transition from Bad to Low, Low to Medium, and Medium to High in a staircase pattern. Any setback (a single bad campaign) can reset the recovery clock.

**Critical distinction in bounce handling:** During reputation problems, you will see block/policy bounces (e.g., `550 5.7.1` rejections citing reputation). These are sender-level rejections — do NOT suppress recipient addresses based on these bounces. The addresses are valid; your sending infrastructure is the problem. Suppressing addresses based on block/policy bounces shrinks your list, concentrating the problem on fewer recipients and making recovery harder. Fix the reputation issue, then retry delivery.

## Key Takeaways

- **Domain reputation has become the primary filtering signal at Gmail and is increasingly weighted at other providers.** For authenticated mail, domain reputation determines inbox vs. spam more than IP reputation does. However, IP reputation remains significant at Microsoft and for connection-level decisions (blocklisting, rate limiting) at all providers.
- **You need to monitor both axes independently.** Use Google Postmaster Tools for both IP and domain reputation at Gmail, SNDS for IP reputation at Microsoft, and DNS blocklist queries for real-time IP status. A delivery problem that persists after changing IPs is a domain reputation problem.
- **Authentication is the bridge between IP and domain reputation.** Without DKIM and DMARC, receiving MTAs cannot reliably attribute mail to your domain and must fall back to IP-based evaluation. Full DKIM + SPF + DMARC deployment is a prerequisite for building domain reputation.
- **Block/policy bounces (5.7.1, reputation-based rejections) are infrastructure problems, not address problems.** Never suppress recipient addresses based on reputation-related rejections. Fix the sending reputation; the addresses are valid.
- **Recovery timelines differ: IP reputation can recover in 1-4 weeks; domain reputation typically requires 2-6 weeks of clean sending.** Domain reputation cannot be reset by switching to a new domain without losing all accumulated positive history. Prevention through engagement-based sending and list hygiene is substantially cheaper than remediation.
