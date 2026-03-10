# IP Warming

## Overview

Every new IP address starts with no sending history. Mailbox providers — Gmail, Microsoft, Yahoo, and others — treat unknown IPs with suspicion because spammers routinely acquire fresh IPs, blast large volumes, and abandon them. IP warming is the process of gradually increasing send volume on a new IP to build a positive sending reputation before reaching production-level traffic.

This is not optional. Sending 500,000 messages from an IP with no history on day one will result in mass deferrals, blocks, and potential blocklisting. The receiving infrastructure has no basis for trusting you, and high volume from an unknown source is the single strongest spam signal an IP can produce.

IP warming applies whenever you introduce a new dedicated IP address into your sending infrastructure. It does not apply to shared IP pools managed by an ESP (those IPs already carry established reputation), but it does apply when you move from shared to dedicated IPs, add new IPs to an existing pool, migrate to a new ESP that assigns you new IPs, or bring new IPs online after an infrastructure expansion.

Warming typically takes 2-6 weeks depending on volume targets, list quality, and engagement patterns. The process is not purely mechanical — you must monitor feedback signals throughout and adjust the schedule based on how receiving servers respond.

## Why Mailbox Providers Require Warming

### The Reputation Cold-Start Problem

Mailbox providers maintain per-IP reputation scores derived from historical sending behavior: bounce rates, spam complaint rates, spam trap hits, engagement signals (opens, clicks, replies, deletes-without-reading), and volume patterns. A new IP has no data points in any of these dimensions.

Providers handle this cold start with throttling. When an unknown IP connects and begins sending, the receiving MTA accepts a limited number of messages and defers the rest. This is not a rejection — it is a rate limit. The provider is saying: "I will accept a small sample, observe what recipients do with it, and decide whether to accept more."

**Gmail** is the most explicit about this. A new IP sending to Gmail will typically see acceptance of 50-200 messages per day initially, with the rest deferred via `421 4.7.28 Our system has detected an unusual rate of unsolicited mail originating from your IP address` or `452 4.5.3 Domain policy limitation`. Gmail's internal systems then observe recipient behavior over 24-72 hours before expanding the acceptance window.

**Microsoft (Outlook.com, Hotmail, Office 365)** uses the Smart Network Data Services (SNDS) reputation system. New IPs start in a "neutral" state. Microsoft is less aggressive about initial throttling than Gmail but more aggressive about blocklisting if early signals are negative. A new IP that generates complaint rates above 0.3% in its first week may receive `550 5.7.606 Access denied, banned sending IP` — a block/policy bounce that can take days to resolve through their JMRP/SNDS process.

**Yahoo/AOL** (now under Yahoo Mail umbrella) throttle new IPs and monitor complaint feedback loop (CFL) data. Initial acceptance is typically 100-500 messages per day, scaling based on CFL complaint rates and bounce rates.

### What Providers Are Measuring During Warming

During the warming period, providers are building a reputation profile based on:

- **Bounce rate**: Are you sending to valid addresses? High bounce rates (above 2-3%) suggest a purchased or poorly maintained list.
- **Complaint rate**: Are recipients marking your messages as spam? Google Postmaster Tools reports this directly; the threshold for concern is 0.1%, and above 0.3% causes active throttling.
- **Spam trap hits**: Are you hitting recycled or pristine traps? Even one pristine trap hit during warming can stall the entire process.
- **Engagement**: Are recipients opening, clicking, or replying? Or are they deleting without reading?
- **Volume consistency**: Is volume growing gradually, or did it spike overnight?
- **Content patterns**: Is the content consistent, or does it change dramatically between sends?

The warming process is fundamentally about giving providers enough positive data points to assign a favorable reputation before you need to send at full volume.

## Prerequisites Before Starting a Warm

Do not begin IP warming until these items are confirmed:

**DNS and authentication must be fully configured.** The new IP must have a valid PTR (reverse DNS) record that resolves forward to the same IP. SPF records for all sending domains must include the new IP. DKIM signing must be operational with keys published in DNS. DMARC records should be in place with at least `p=none` during warming (though `p=quarantine` or `p=reject` is fine if you are confident in alignment). Sending from an IP without proper PTR will produce immediate `550 5.7.1 IP not in DNS` rejections from many providers.

**Feedback loops must be registered.** Register for Microsoft JMRP/SNDS, Yahoo CFL, and any other available feedback loops before sending. You need complaint data from day one.

**Google Postmaster Tools must be configured.** Verify your sending domain in Google Postmaster Tools. Data takes 24-48 hours to appear after the first send, so early registration matters.

**List hygiene must be completed.** Run your recipient list through a verification service to remove obviously invalid addresses before warming. Hitting a 5% hard bounce rate on day two of warming because your list contains stale addresses will undermine the entire process. Target a pre-verified hard bounce rate below 1%.

**Segment your most engaged recipients.** Warming sends should go to your most engaged subscribers — people who opened or clicked within the last 30 days. These recipients are least likely to complain and most likely to engage, which is exactly the signal providers need to see.

## A Practical Warming Schedule

The following schedule targets a production volume of approximately 500,000 messages per day. Adjust proportionally for your target volume — if your target is 100,000/day, divide the numbers by 5; if your target is 2 million/day, multiply by 4. The ratios and progression rate matter more than the absolute numbers.

### Daily Volume Ramp

| Day | Daily Volume | Notes |
|-----|-------------|-------|
| 1 | 500 | Send to most-engaged segment only |
| 2 | 1,000 | |
| 3 | 2,000 | |
| 4 | 4,000 | |
| 5 | 8,000 | First checkpoint: review bounce/complaint data |
| 6 | 12,000 | |
| 7 | 18,000 | |
| 8 | 25,000 | Second checkpoint: Google Postmaster data should be visible |
| 9 | 35,000 | |
| 10 | 50,000 | |
| 11 | 70,000 | |
| 12 | 100,000 | Third checkpoint: review all provider dashboards |
| 13 | 130,000 | |
| 14 | 170,000 | |
| 15 | 200,000 | |
| 16 | 250,000 | |
| 17 | 300,000 | |
| 18 | 350,000 | |
| 19 | 400,000 | |
| 20 | 450,000 | |
| 21 | 500,000 | Target volume reached |

This is approximately a doubling every 2-3 days in the early phase, transitioning to 30-50k/day increments once past 100,000. The early phase (days 1-5) is the most critical — this is when providers form initial impressions.

### Distribution Across Providers

Do not send all volume to a single provider. Distribute across your recipient base proportionally, but be aware that each major provider maintains independent reputation. If 40% of your list is Gmail, 30% is Microsoft, and 15% is Yahoo, your sends should reflect that distribution from day one.

If you have very uneven provider distribution (e.g., 80% Gmail), consider per-provider sub-limits:

| Day | Total Volume | Gmail (max) | Microsoft (max) | Yahoo (max) | Other |
|-----|-------------|-------------|-----------------|-------------|-------|
| 1 | 500 | 200 | 150 | 75 | 75 |
| 5 | 8,000 | 3,200 | 2,400 | 1,200 | 1,200 |
| 10 | 50,000 | 20,000 | 15,000 | 7,500 | 7,500 |
| 15 | 200,000 | 80,000 | 60,000 | 30,000 | 30,000 |

### Sending Pattern

- **Send at consistent times.** Choose a sending window (e.g., 9:00-17:00 in your primary recipient time zone) and stick to it. Erratic sending patterns — bursts at 3:00 AM followed by silence — look like bot behavior.
- **Spread volume across the sending window.** Do not dump 50,000 messages in 5 minutes. Throttle to a steady rate across the window. At 50,000 messages over 8 hours, that is roughly 100 messages per minute — well within what providers expect from a legitimate sender.
- **Send every day, including weekends.** Gaps in sending during warming reset some of the momentum. If you cannot send on weekends, hold volume flat on Monday rather than jumping (e.g., if Friday was 50,000, send 50,000 again on Monday rather than jumping to 70,000).

## Monitoring During the Warm

### SMTP Response Codes to Watch

During warming, you will see deferrals. This is expected. The key is distinguishing normal warming deferrals from signals that something is wrong.

**Normal warming deferrals (soft bounces — retry):**

| Provider | Code | Diagnostic | Meaning |
|----------|------|------------|---------|
| Gmail | `421 4.7.28` | `Our system has detected an unusual rate of unsolicited mail` | Rate limiting; reduce volume or wait |
| Gmail | `452 4.5.3` | `Domain policy limitation` | Per-domain or per-IP rate limit hit |
| Microsoft | `421 4.7.0` | `Connection frequency limited` | Too many connections from this IP |
| Yahoo | `421 4.7.0` | `[TSS04] Messages from x.x.x.x temporarily deferred` | Temporary throttling |
| Generic | `451 4.3.2` | `System not accepting messages` | Server-side rate limiting |

These are transient. Your MTA should retry automatically. If deferral rates exceed 20-30% of attempted sends on a given day, reduce volume the next day rather than pushing through.

**Warning signals (block/policy bounces — do NOT suppress addresses; investigate):**

| Provider | Code | Diagnostic | Meaning |
|----------|------|------------|---------|
| Gmail | `550 5.7.1` | `Our system has detected that this message is likely unsolicited mail` | Content or reputation rejection |
| Gmail | `550 5.7.26` | `This mail is unauthenticated` | SPF/DKIM/DMARC failure |
| Microsoft | `550 5.7.606` | `Access denied, banned sending IP` | IP blocklisted by Microsoft |
| Microsoft | `550 5.7.1` | `Service unavailable, client host [x.x.x.x] blocked` | Reputation block |
| Yahoo | `553 5.7.1` | `[BL21] Connections will not be accepted from x.x.x.x` | IP blocklisted |
| Spamhaus | via any provider | `listed by zen.spamhaus.org` or `blocked using sbl.spamhaus.org` | Third-party blocklist hit |

If you see block/policy bounces during warming, **stop sending immediately** and diagnose. Continuing to send into blocks will deepen the reputation damage. Common causes: hitting spam traps (list quality issue), authentication failures (DNS misconfiguration), or content that triggers filters.

### Metrics to Track Daily

Maintain a daily warming log with these metrics:

| Metric | Healthy Range | Action Threshold |
|--------|--------------|-----------------|
| Hard bounce rate | < 1% | > 2%: pause; clean list |
| Deferral rate | 5-15% (normal during warming) | > 30%: reduce volume |
| Block/policy bounce rate | 0% | > 0.1%: pause; investigate |
| Spam complaint rate (FBL) | < 0.05% | > 0.1%: pause; check content/segmentation |
| Google Postmaster domain reputation | N/A to Medium (early) | "Low" or "Bad": pause immediately |
| Google Postmaster IP reputation | N/A to Medium (early) | "Low" or "Bad": pause immediately |
| Spam trap hits | 0 | Any confirmed trap hit: pause; audit list source |

### What "Pause" Means

When metrics breach action thresholds, pause does not mean stop permanently. It means:

1. Hold at the current volume (do not increase) for 2-3 days.
2. Investigate the root cause (list segment, content, authentication).
3. Fix the issue.
4. Resume the ramp from the last healthy volume, not from where you stopped.

If the issue is severe (blocklisting, multiple spam trap hits), you may need to drop volume back by 50% before resuming.

## Common IP Warming Mistakes

### Mistake 1: Sending Too Much Too Fast

The most common mistake. Sending 100,000 messages on day one from a brand-new IP will produce immediate mass deferrals and likely a temporary blocklisting. Gmail in particular will defer nearly everything after the first few hundred messages, and if your MTA aggressively retries, the retry volume itself can trigger a block.

**What it looks like in logs:** Escalating `421 4.7.28` responses from Gmail, `421 4.7.0` from Microsoft, followed by `550 5.7.1` rejections as the provider upgrades from throttling to blocking.

### Mistake 2: Warming With Low-Quality Recipients

Warming with your full list instead of your engaged segment means higher bounce rates, lower engagement, and more complaints. The entire point of warming is to show providers that real humans want your mail. Sending to addresses that last opened 18 months ago undermines this.

**Best practice:** Warm with recipients who engaged (opened or clicked) within the last 30 days. After warming is complete and you have established reputation, gradually expand to 60-day, 90-day, and older segments.

### Mistake 3: Ignoring Provider-Specific Signals

Each major provider warms independently. You can have a "High" reputation at Gmail and be blocklisted at Microsoft simultaneously. Monitor each provider separately. Google Postmaster Tools, Microsoft SNDS, and Yahoo CFL data are independent systems that require individual attention.

### Mistake 4: Changing Content During Warming

Switching from transactional-style content to promotional content mid-warm changes the signal profile. If you warmed with order confirmations and then switch to marketing newsletters at 200,000/day, providers see a content shift from a still-new IP — this looks like a compromised account or a bait-and-switch.

**Best practice:** Warm with the same type of content you plan to send at production volume. If you send both transactional and marketing email, warm the IP with the content type that will carry the highest volume.

### Mistake 5: Failing to Spread Volume Across the Day

Sending the entire day's volume in a single burst (e.g., 50,000 messages in 10 minutes at 08:00) creates a spike that triggers rate limiting. Legitimate senders produce steady, distributed traffic patterns. Burst sending is a spam characteristic.

**What it looks like in logs:** A wall of `421` deferrals within the first few minutes of a send, followed by successful delivery hours later as your MTA retries gradually — effectively spreading the volume out anyway, but with unnecessary deferrals recorded against your reputation.

### Mistake 6: Not Having a Rollback Plan

If warming fails — a blocklisting, a spam trap hit, a catastrophic complaint spike — you need to be able to fall back to your previous sending infrastructure while you resolve the issue. Do not cut over production traffic to the new IP before warming is fully complete. Maintain your existing IPs in parallel until the new IP is verified at full volume.

### Mistake 7: Warming Multiple IPs Simultaneously Without Per-IP Tracking

If you are warming a pool of 4 IPs, each IP must be tracked independently. A blocklist hit on one IP in the pool should not cause you to pause all four — isolate the problem IP, continue warming the others, and diagnose the issue on the affected IP separately. Your MTA logs must distinguish traffic per sending IP.

## Warming for IP Pools

When warming multiple IPs for a pool, you have two strategies:

**Sequential warming:** Warm IP #1 to full volume, then start IP #2, then IP #3, etc. Slower but simpler to manage. Each IP gets full attention. Use this if you have limited monitoring resources.

**Parallel warming:** Warm all IPs simultaneously, distributing daily volume across the pool. Faster but requires per-IP monitoring. Use the per-IP daily volume targets from the schedule above for each individual IP — if you are warming 4 IPs in parallel and each needs to reach 125,000/day (for a combined 500,000/day target), each IP follows the schedule independently.

**Best practice (industry convention):** Most deliverability practitioners prefer sequential warming because it isolates variables. If IP #2 develops a problem, IP #1 is already fully warmed and unaffected. With parallel warming, a shared list quality issue (e.g., a spam trap present across all send segments) damages all IPs simultaneously.

## Dedicated vs. Shared IP Considerations

Warming only applies to **dedicated IPs** — IPs assigned exclusively to your sending. Shared IPs (used by multiple senders on an ESP like Mailchimp, SendGrid, or Mailgun) inherit the pooled reputation of all senders on that IP and do not require warming by individual customers.

When migrating from shared to dedicated IPs:

- Your deliverability may temporarily decrease, even for the same content and recipients, because the dedicated IP starts from zero reputation while the shared IP had established history.
- Do not migrate all traffic at once. Run the dedicated IP in parallel, sending a warming subset through it while the shared IP handles production volume.
- ESP platforms often provide automated warming features (SendGrid's "IP Warmup" toggle, SES's gradual sending recommendations). These are useful but may not match your specific volume and audience profile. Monitor the automated process and override if metrics deteriorate.

## How to Know When Warming Is Complete

Warming is complete when the new IP can sustain your target daily volume without elevated deferrals, blocks, or reputation warnings. There is no single definitive signal — it is a convergence of indicators.

### Completion Criteria

All of the following should be true for at least 3-5 consecutive days at target volume:

1. **Deferral rate at target volume is below 5%.** During early warming, 10-20% deferrals are normal. At full volume on a warmed IP, deferrals should be in the 1-5% range (identical to what a mature IP experiences).

2. **Google Postmaster Tools shows "Medium" or "High" IP reputation.** A "Low" or "Bad" rating means warming is not complete — or has regressed. Note that Postmaster Tools requires approximately 200-500 daily messages to Gmail to display data; below that threshold, reputation shows as "N/A."

3. **Microsoft SNDS shows green (normal) status for the IP.** Yellow (suspect) or red (poor) status indicates ongoing reputation issues with Microsoft.

4. **No active blocklist listings.** Check the IP against Spamhaus (SBL, XBL, PBL), Barracuda (BRBL), SORBS, and Proofpoint (formerly Cloudmark) at minimum. MXToolbox or similar multi-list checkers can query dozens of lists simultaneously.

5. **Bounce classification is stable.** Hard bounce rate is below 1%, block/policy bounce rate is effectively 0%, and soft bounces are limited to genuine transient issues (mailbox full, server temporarily unavailable).

6. **Inbox placement is consistent.** If you use seed-list testing (tools like Everest, GlockApps, or InboxMonitor), inbox placement rates should be at or above 85-90% across major providers.

### Ongoing Monitoring After Warming

Warming completion is not a permanent state. IP reputation is maintained through consistent sending behavior. If you stop sending from a warmed IP for more than 30 days, reputation data ages out and you may need to re-warm — typically a faster process (1-2 weeks instead of 3-4) because some residual reputation data persists.

After warming, continue monitoring:

- Google Postmaster Tools daily (reputation, spam rate, authentication)
- Microsoft SNDS weekly
- Blocklist monitoring continuously (automated tools like HetrixTools or UltraTools provide real-time alerts)
- Bounce rates per campaign (hard bounce under 1%, block/policy bounce under 0.1%)
- Complaint rates per campaign (under 0.1%; under 0.05% for Gmail)

## Special Cases

### Re-Warming After a Blocklist Incident

If a warmed IP gets blocklisted and you successfully delist it, you must re-warm. The delisting removes the block but does not restore positive reputation — the IP is back to a neutral or slightly negative state. Follow the standard warming schedule but at an accelerated pace (3-5 day ramp instead of 21 days), monitoring closely for recurrence of the issue that caused the original listing.

### Warming for Transactional Email

Transactional email (order confirmations, password resets, account notifications) has inherently higher engagement and lower complaint rates than marketing email. IPs carrying transactional-only traffic warm faster — often reaching full volume in 7-10 days. The warming schedule can be more aggressive (doubling daily instead of every 2-3 days) because the signal quality is stronger.

**Best practice:** Keep transactional and marketing email on separate IPs with separate warming schedules. Mixing traffic types on a single IP means the transactional reputation is dragged down by marketing complaint rates.

### Warming With Very Low Volume

If your target production volume is under 10,000 messages per day, warming is still recommended but the timeline compresses. Start at 200-500/day and ramp over 5-7 days. At very low volumes, some providers (particularly Gmail) may never surface data in Postmaster Tools because you do not meet the minimum daily threshold (~200 messages/day to Gmail specifically). In these cases, monitor via bounce rates and inbox placement testing rather than provider dashboards.

### Warming in AWS SES or Similar Cloud Sending Services

AWS SES places new accounts in a "sandbox" that limits sending to verified addresses only. After sandbox removal, SES provides a sending quota that starts at 200 messages per 24-hour period and increases automatically based on sending patterns and bounce/complaint rates. This is a form of provider-enforced warming. However, SES's automatic quota increases may be slower or faster than optimal for your recipient mix. You can request quota increases manually through AWS support, but doing so without establishing sufficient positive sending history may result in a denial.

## Key Takeaways

- **IP warming is mandatory for any new dedicated IP.** Skipping or rushing the process results in mass deferrals, blocks, and potential blocklisting that takes longer to resolve than the warming itself would have taken.
- **Follow a graduated schedule starting at 500 messages/day, roughly doubling every 2-3 days, and reaching target volume over 15-21 days.** Warm with your most engaged recipients first (30-day actives) and the same content type you plan to send at production volume.
- **Monitor daily: deferral rates, bounce classification (hard vs. block/policy vs. soft), complaint rates, and provider-specific dashboards (Google Postmaster Tools, Microsoft SNDS).** Pause and investigate if hard bounces exceed 2%, block/policy bounces appear at all, or complaint rates exceed 0.1%.
- **Warming is complete when you sustain target volume for 3-5 consecutive days with deferral rates below 5%, provider reputation scores at "Medium" or above, no blocklist listings, and stable bounce/complaint metrics.**
- **Reputation is not permanent.** Extended sending gaps (30+ days) degrade reputation and may require re-warming. Consistent volume, clean lists, and strong authentication maintain what the warm established.
