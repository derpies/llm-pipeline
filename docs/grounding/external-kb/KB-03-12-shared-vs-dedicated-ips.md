# Shared vs. Dedicated IPs

## Overview

Every outbound email originates from an IP address, and that IP carries a reputation score at every major mailbox provider. The fundamental decision — whether to send from a shared IP pool managed by your ESP or from dedicated IPs assigned exclusively to your traffic — has direct, measurable consequences for inbox placement, troubleshooting capability, and operational overhead. This article covers the mechanics of each model, the specific tradeoffs, the contamination risks inherent to shared pools, and the volume and operational thresholds that should drive the decision.

## How IP Reputation Works at Mailbox Providers

Before comparing shared and dedicated IPs, it is essential to understand what IP reputation actually measures and how it decays.

Major mailbox providers (Gmail, Microsoft, Yahoo/AOL) maintain internal reputation scores for each sending IP. These scores are derived from:

- **Complaint rate:** The percentage of delivered messages marked as spam by recipients. Gmail's threshold for problems is 0.3%; above 0.1% already degrades placement.
- **Bounce rate:** High rates of hard bounces (5.1.1 user unknown) signal poor list hygiene and reduce IP reputation.
- **Spam trap hits:** Messages to known recycled or pristine spam traps cause immediate, severe reputation damage.
- **Engagement signals:** Gmail in particular factors in open rates, read time, and reply rates as positive reputation inputs.
- **Volume consistency:** Sudden spikes from an IP trigger throttling and increased scrutiny regardless of content quality.

IP reputation is not static. At Gmail, reputation can shift within 24–48 hours of a bad send. At Microsoft, reputation changes tend to be slower (days to weeks) but harder to recover once degraded. Yahoo recalculates on roughly a rolling 30-day window.

**Key distinction (industry convention):** IP reputation is one of several reputation layers. Domain reputation (tracked via the `d=` domain in DKIM signatures and the header `From:` domain) has become increasingly important and in some cases supersedes IP reputation at Gmail and Microsoft. However, IP reputation remains the gatekeeper for initial connection acceptance — a blocklisted or very low-reputation IP will be rejected at the SMTP level before domain reputation is even evaluated.

## Shared IP Model

### How It Works

In a shared IP model, the ESP assigns your outbound mail to a pool of IP addresses used by multiple senders. The ESP's traffic-management layer distributes messages across the pool, blending your mail with other customers' mail on the same IPs. The ESP typically manages SPF records (you include their SPF via `include:` mechanism), and DKIM signing is done with either the ESP's domain or your own via delegated signing.

### Advantages

**No warmup required.** Shared pools are already sending high, consistent volumes. A new sender added to the pool inherits the existing reputation immediately. There is no multi-week warmup schedule to follow and no risk of under-sending during the ramp period.

**Volume fluctuations are absorbed.** If you send 50,000 emails one week and 5,000 the next, the overall IP volume remains stable because other senders fill the gap. This eliminates the volume-consistency problem that plagues low-volume dedicated IP senders.

**Lower operational burden.** The ESP monitors IP health, rotates IPs out of the pool if they get blocklisted, manages feedback loops, and handles deliverability at the IP level. You do not need a deliverability engineer monitoring IP reputation daily.

**Cost efficiency.** Dedicated IPs typically cost $20–$100/month per IP from most ESPs. Shared sending is included in the base platform price.

### Disadvantages

**No control over co-tenant behavior.** Your inbox placement is partially dependent on the sending practices of every other sender on the same IP. One co-tenant sending to a purchased list or ignoring bounces can degrade the IP reputation for everyone.

**Limited diagnostic visibility.** When deliverability drops, you cannot easily distinguish whether the problem is your content, your list, or a co-tenant's behavior. Tools like Google Postmaster Tools report IP reputation by IP address — if you do not know which IPs your mail traverses (and most ESPs do not expose this), you cannot correlate reputation data to your sends.

**Blocklist exposure.** If a shared IP lands on a DNS-based blocklist (Spamhaus SBL, Barracuda BRBL, SORBS), all senders on that IP are affected. The ESP must handle the delisting process, which can take 24 hours to several days depending on the blocklist operator.

**SPF and DKIM alignment complexity.** On shared IPs, SPF alignment for DMARC is often handled through the ESP's envelope sender domain (e.g., `bounce.esp-domain.com`), not your domain. This means SPF will not produce a DMARC-aligned pass unless the ESP supports custom return-path domains. You must rely on DKIM alignment, which requires the ESP to sign with a `d=` value matching your header `From:` domain.

## Dedicated IP Model

### How It Works

The ESP assigns one or more IP addresses exclusively to your account. All mail you send through the platform exits from those specific IPs. You have a 1:1 mapping between your sending behavior and the IP reputation.

### Advantages

**Full reputation isolation.** Your IP reputation reflects only your sending practices. No co-tenant can degrade your placement. Conversely, your good practices directly and exclusively benefit your own delivery.

**Complete diagnostic control.** You can register your dedicated IPs in Google Postmaster Tools, Microsoft SNDS, and Yahoo's Complaint Feedback Loop. Reputation data maps directly to your traffic, making root-cause analysis straightforward.

**Predictable deliverability.** Once warmed and established, a dedicated IP with consistent volume and good practices will produce stable, predictable inbox placement. There are no external variables introducing noise into your delivery metrics.

**Granular traffic segmentation.** With multiple dedicated IPs, you can separate transactional mail (password resets, order confirmations) from marketing mail (newsletters, promotions). This prevents a marketing campaign with a higher complaint rate from degrading delivery of time-sensitive transactional messages. A common pattern is:

- IP 1: Transactional (high urgency, low complaint)
- IP 2: Marketing to engaged subscribers (opened/clicked in last 90 days)
- IP 3: Marketing to less-engaged or re-engagement campaigns

### Disadvantages

**Warmup is mandatory.** A new, previously unused IP has no reputation — mailbox providers treat it as unknown, which is worse than neutral. You must gradually increase sending volume over 2–4 weeks (sometimes longer for very large target volumes) to build positive reputation. During warmup, throttling and temporary deferrals are expected.

A typical warmup schedule for a target volume of 100,000 emails/day:

| Day | Daily Volume | Notes |
|-----|-------------|-------|
| 1–2 | 500 | Send to most engaged recipients only |
| 3–4 | 1,000 | |
| 5–6 | 2,500 | |
| 7–8 | 5,000 | Monitor for block/policy bounces |
| 9–10 | 10,000 | |
| 11–14 | 25,000 | Check Postmaster Tools reputation |
| 15–21 | 50,000 | |
| 22–28 | 100,000 | Full volume |

**Log indicators during warmup:** Expect to see `421 4.7.28 Our system has detected an unusual rate of unsolicited mail originating from your IP address` (Gmail) and `452 4.7.650 Mail rejected by Outlook; try again later` (Microsoft). These are soft bounces indicating throttling — they resolve as reputation builds. Do not suppress these addresses.

**Volume consistency is your responsibility.** If your sending volume drops significantly (e.g., from 50,000/day to 2,000/day for several weeks), the IP's reputation decays from inactivity. When you ramp back up, you may face throttling again. Industry convention: a volume drop exceeding 50% sustained for more than 2 weeks typically requires a partial re-warmup.

**You own every problem.** If you accidentally send to a bad list segment and hit spam traps, the reputation damage is entirely on your IPs with no dilution from good co-tenant traffic. Recovery from a significant reputation event on a dedicated IP takes 2–4 weeks of clean sending at consistent volume.

**Higher cost and operational overhead.** Each IP costs money, and you need internal monitoring (or a deliverability service) to watch reputation, handle blocklist events, and manage warmup for new IPs.

## When to Use Shared IPs

Shared IPs are the correct choice when:

- **Monthly volume is below 100,000 emails.** At this volume, a dedicated IP cannot sustain enough daily traffic to build and maintain a stable reputation. Many practitioners cite 50,000/month as the absolute floor, but 100,000/month is a more conservative and practical threshold for reliable reputation maintenance.
- **Sending frequency is irregular.** If you send a monthly newsletter and nothing in between, a dedicated IP will have no reputation signal for weeks at a time. Shared pools handle this naturally.
- **You lack deliverability expertise in-house.** If nobody on the team can interpret Postmaster Tools data, manage a warmup schedule, or respond to blocklist events within hours, shared IPs with a reputable ESP are lower risk.
- **You are a new sender with no established domain reputation.** Starting on shared IPs while building domain reputation through DKIM-aligned sending is a reasonable approach before migrating to dedicated IPs later.

**ESP selection matters enormously for shared IPs.** The quality of a shared IP pool depends entirely on the ESP's enforcement of acceptable use policies. ESPs that onboard customers without vetting their list sources, or that tolerate complaint rates above 0.1%, run degraded pools. Before committing to an ESP's shared pool, ask:

- What is the average complaint rate across the shared pool?
- What is the pool's current reputation in Google Postmaster Tools (High/Medium/Low/Bad)?
- What is the maximum complaint rate a customer can sustain before being removed from the pool?
- How quickly does the ESP respond to blocklist events?

## When to Use Dedicated IPs

Dedicated IPs are the correct choice when:

- **Monthly volume consistently exceeds 100,000 emails** and daily sending is relatively stable (not all concentrated in one blast per month).
- **You send both transactional and marketing email** and need to protect transactional delivery from marketing reputation risk.
- **You operate in a regulated industry** (finance, healthcare) where deliverability SLAs or audit requirements demand full control and traceability of sending infrastructure.
- **You need to diagnose deliverability issues precisely.** On shared IPs, an inbox placement drop could be you or a co-tenant. On dedicated IPs, it is definitively you.
- **You have (or can hire) deliverability operational expertise.** Managing dedicated IPs without monitoring is worse than using a well-managed shared pool.

### How Many Dedicated IPs?

The number of IPs depends on volume and traffic-type segmentation:

- **Under 250,000/month:** 1 dedicated IP is sufficient. Splitting across more IPs dilutes volume per IP and weakens reputation signals.
- **250,000–1,000,000/month:** 2 IPs — one transactional, one marketing.
- **1,000,000–5,000,000/month:** 3–5 IPs with segmentation by mail type and engagement tier.
- **Over 5,000,000/month:** Scale IP count with volume, keeping each IP at roughly 50,000–200,000 sends/day for stable reputation. At very high volumes, also consider multiple sending domains to distribute domain reputation signals.

**Best practice:** Never spread volume so thin that any single IP sends fewer than 1,000 emails/day on a sustained basis. Below that threshold, the IP lacks sufficient signal for mailbox providers to establish a reputation.

## Shared IP Reputation Contamination

### How Contamination Happens

Shared IP reputation contamination occurs when one or more senders on the pool engage in practices that generate negative reputation signals. The IP's aggregate metrics degrade, and all senders on that IP experience worse deliverability. Common contamination sources:

- **A co-tenant sends to a purchased or scraped list.** This generates high hard bounce rates (5.1.1 user unknown), spam trap hits, and complaints — all of which damage IP reputation rapidly.
- **A co-tenant ignores suppression obligations.** Continuing to send to addresses that have previously hard-bounced or unsubscribed generates repeated negative signals.
- **A co-tenant runs a re-engagement campaign to a very old list segment.** Even with legitimate opt-in, sending to addresses that have not been mailed in 12+ months often produces spam trap hits (recycled traps) and high complaint rates.
- **A new customer onboards to the pool with a large, unvetted list.** The first send from this customer can immediately impact the IP.

### Detecting Contamination

If you are on shared IPs and suspect contamination, look for these patterns:

**Symptom 1: Sudden deliverability drop not correlated with your sending changes.** If your content, list, and sending patterns have not changed but inbox placement drops, the problem may be external to your traffic.

**Symptom 2: Block/policy bounces referencing IP reputation.** Look for SMTP responses like:

- `550 5.7.1 [IP address] has been blocked by Spamhaus` — The shared IP is on a blocklist.
- `550 5.7.1 Mail from IP has been temporarily rate limited due to IP reputation` (Yahoo).
- `421 4.7.0 [IP address] Try again later, closing connection. This message was not accepted due to IP reputation` (Gmail).
- `550 5.7.606 Access denied, banned sending IP [IP address]` (Microsoft).

These are block/policy bounces — they indicate a sender-level (IP-level) problem, not an address-level problem. Do not suppress recipient addresses that receive these responses.

**Symptom 3: Google Postmaster Tools shows IP reputation declining.** If you can identify the shared IPs (check email headers for the `Received:` chain or the `X-Originating-IP` header), register them in Postmaster Tools. A reputation drop from "High" to "Medium" or "Low" that does not align with your sending behavior suggests co-tenant contamination.

**Symptom 4: Blocklist appearance.** Check the IP against Spamhaus (SBL, XBL, PBL), Barracuda BRBL, SORBS, and SpamCop using MXToolbox or similar multi-blocklist checkers. If the IP is listed and you have not changed your practices, contamination is the likely cause.

### Responding to Contamination

1. **Contact your ESP immediately.** Report the specific SMTP rejection codes and the affected IPs. A reputable ESP will investigate, identify the offending co-tenant, and either remediate or remove them from the pool.
2. **Request IP migration.** Ask the ESP to move your traffic to a different IP pool or a specific set of IPs with better reputation. Most ESPs can do this within 24–48 hours.
3. **Escalate if response is slow.** If the ESP does not act within 48 hours, or if this is a recurring problem, it is a signal that the ESP's acceptable-use enforcement is inadequate. This is a legitimate reason to evaluate switching ESPs or moving to dedicated IPs.
4. **Monitor recovery.** After the ESP addresses the issue, IP reputation typically recovers within 3–7 days of clean sending at normal volume, assuming the blocklist listing (if any) has been resolved.

### Contractual Protections

When using shared IPs, confirm the following with your ESP:

- **SLA on blocklist resolution time.** Reputable ESPs commit to initiating a delisting request within 4 hours of detection.
- **Co-tenant complaint rate enforcement.** The ESP should have a published maximum complaint rate (typically 0.08–0.1%) with automatic throttling or suspension for senders who exceed it.
- **Notification policy.** You should be notified if the shared IPs assigned to your traffic are blocklisted or experience reputation degradation.
- **Migration option.** The ability to move to a different pool or to dedicated IPs without contract renegotiation.

## Hybrid and Transitional Approaches

### Dedicated for Transactional, Shared for Marketing

A common hybrid approach: send transactional email (account notifications, receipts, security alerts) from a dedicated IP, and marketing email from the ESP's shared pool. This protects the delivery of high-priority transactional messages while keeping marketing costs lower and avoiding the volume-consistency challenge for marketing sends that may be infrequent.

### Shared-to-Dedicated Migration

If you start on shared IPs and grow into dedicated IP territory, the migration requires planning:

1. **Provision the dedicated IP(s)** through your ESP.
2. **Begin warmup** by routing a percentage of your highest-engagement traffic (recipients who opened or clicked in the last 30 days) through the new dedicated IP. Start at 5–10% and increase weekly.
3. **Monitor dedicated IP reputation** in Postmaster Tools and SNDS during the warmup.
4. **Shift remaining traffic** from shared to dedicated once the dedicated IP reaches "High" or "Medium" reputation at major providers. This typically takes 3–6 weeks.
5. **Maintain the shared pool as a fallback** during the transition. Do not cut over all traffic simultaneously.

**Log indicator during migration:** Watch for increased `4xx` deferral rates on the dedicated IP during early warmup. A deferral rate under 10% is acceptable during warmup. If deferral rates exceed 20%, slow the ramp — you are increasing volume faster than the IP is building reputation.

### Sub-account Isolation on ESPs

Some ESPs offer "dedicated IP pools" that are shared among a smaller, curated group of senders rather than the full customer base. This middle ground provides better isolation than a fully shared pool while offering more volume stability than a single-tenant dedicated IP. Ask your ESP whether they offer tiered pools segmented by sender quality or industry vertical.

## IP Reputation vs. Domain Reputation: The Shifting Balance

As of current industry practice, the weight of IP reputation versus domain reputation varies by mailbox provider:

- **Gmail:** Domain reputation (the DKIM `d=` domain and envelope sender domain) is the primary reputation signal. IP reputation still matters for connection-level decisions (rate limiting, blocking) but is secondary for inbox vs. spam folder placement. Google has stated publicly that domain reputation is more important than IP reputation for filtering decisions.
- **Microsoft (Outlook/Hotmail):** IP reputation remains heavily weighted. Microsoft's SmartScreen filter and their proprietary reputation system place significant emphasis on IP history. Dedicated IPs with clean records perform measurably better at Microsoft.
- **Yahoo/AOL:** A blend of IP and domain reputation, with IP reputation still carrying substantial weight for rate-limiting decisions.

**Practical implication:** Even on shared IPs, investing in strong domain reputation (consistent DKIM signing with your own `d=` domain, low complaint rates, good engagement) provides a meaningful buffer against shared IP reputation fluctuations, especially at Gmail. However, domain reputation cannot fully compensate for a blocklisted or very low-reputation IP — the connection will be rejected before content or domain signals are evaluated.

## Monitoring Dedicated IP Health

If you operate dedicated IPs, establish monitoring for:

| Signal | Tool | Check Frequency | Action Threshold |
|--------|------|-----------------|-----------------|
| Google IP reputation | Google Postmaster Tools | Daily | Drop below "Medium" |
| Microsoft IP reputation | SNDS (Smart Network Data Services) | Daily | Complaint rate > 0.3% |
| Blocklist status | MXToolbox, Spamhaus check | Every 4 hours (automated) | Any listing on Spamhaus SBL/XBL |
| Bounce rate by category | ESP reporting / internal logs | Per campaign | Hard bounces > 2%, block/policy bounces > 1% |
| Deferral rate | MTA logs | Hourly during sends | Deferrals > 5% sustained |
| Complaint rate (FBL) | Yahoo CFL, Microsoft JMRP | Daily | Rate > 0.08% |

**Automation note (best practice):** Set up alerting — not just dashboards — for blocklist events and reputation drops. A Spamhaus SBL listing that goes undetected for 24 hours will affect tens of thousands of messages. Most monitoring services (MXToolbox, Hetrix Tools, UltraTools) support webhook or email alerts on blocklist changes.

## Key Takeaways

- **Use shared IPs if you send fewer than 100,000 emails/month or lack the operational capacity to manage warmup, volume consistency, and blocklist monitoring.** The ESP absorbs these responsibilities, but you depend on their enforcement of co-tenant quality.
- **Use dedicated IPs if you send more than 100,000 emails/month consistently, need to separate transactional from marketing streams, or require precise diagnostic control over deliverability.** Budget for 2–4 weeks of warmup and ongoing reputation monitoring.
- **Shared IP contamination is detectable:** look for block/policy bounces referencing IP reputation (5.7.1, 5.7.606), blocklist appearances, and Postmaster Tools reputation drops that do not correlate with your sending behavior. Escalate to your ESP immediately.
- **Domain reputation is increasingly important and partially decouples your deliverability from IP reputation, especially at Gmail.** Invest in DKIM alignment with your own domain regardless of whether you use shared or dedicated IPs.
- **The hybrid model — dedicated IP for transactional, shared pool for marketing — is a practical middle ground** that protects critical message delivery while managing cost and volume-consistency challenges for marketing sends.
