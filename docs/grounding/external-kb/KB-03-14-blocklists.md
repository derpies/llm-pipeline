# Blocklists

## Overview

A blocklist (also called a blacklist, DNSBL, or RBL) is a database of IP addresses or domains that have been observed sending spam or otherwise abusing email infrastructure. Receiving mail servers query these lists in real time during the SMTP transaction. If the connecting IP or sending domain appears on a blocklist the receiver consults, the message is either rejected outright (typically with a 5.7.1 response) or scored negatively in the spam filter. Blocklist hits are one of the most immediately damaging reputation events a sender can experience, and they are also one of the most common causes of block/policy bounces.

Blocklists are not a single monolithic system. There are hundreds of blocklists, but only a handful carry enough weight to cause widespread delivery failures. The impact of a listing depends entirely on which blocklist you are on and which receiving servers consult it. A listing on Spamhaus SBL will cause rejections across a large percentage of the internet's mail servers. A listing on an obscure, unmaintained list may have zero practical effect.

This article covers the major blocklists that matter operationally, how listings happen, how to detect them, and the specific delisting process for each.

## How Blocklist Lookups Work

Blocklist lookups use DNS — specifically, the DNSBL (DNS-based Blocklist) mechanism defined in RFC 5782. When a receiving mail server wants to check whether a connecting IP (e.g., `192.0.2.25`) is on the Spamhaus SBL, it performs a DNS A-record query by reversing the IP octets and appending the blocklist's zone:

```
25.2.0.192.zen.spamhaus.org
```

If the query returns an A record (typically in the `127.0.0.x` range), the IP is listed. The specific return code indicates the type of listing (e.g., `127.0.0.2` for SBL, `127.0.0.4` for XBL on Spamhaus). If the query returns `NXDOMAIN`, the IP is not listed.

Domain-based blocklists (DBLs) work similarly but query the sending domain or URLs found in the message body rather than the connecting IP.

This lookup adds minimal latency — typically 1–10 ms — and is performed during the SMTP transaction, usually after the `RCPT TO` command and before the `DATA` phase, or during the `DATA` phase for content-based domain checks.

## What a Blocklist Hit Looks Like in Logs

When a receiving server rejects mail due to a blocklist, the SMTP response typically contains explicit information about which list triggered the rejection. Common patterns:

```
550 5.7.1 Service unavailable; client host [192.0.2.25] blocked using zen.spamhaus.org
550 5.7.1 Rejected - listed by bl.spamcop.net
554 5.7.1 Your IP has been blocked by Barracuda Reputation. See https://barracudacentral.org/lookups
421 4.7.0 Try again later, closing connection. This message was deferred by the recipient server because the sender IP is listed on b.barracudacentral.org
```

Key indicators to look for in bounce logs:

- **SMTP response codes:** 550 or 554 with enhanced status code `5.7.1` (permanent policy rejection) or sometimes `4.7.1` (temporary deferral pending delisting). These are block/policy bounces — do not suppress the recipient addresses.
- **Blocklist zone names in the response text:** The response almost always names the specific blocklist (e.g., `zen.spamhaus.org`, `b.barracudacentral.org`, `bl.spamcop.net`).
- **URLs in the response:** Many responses include a link to the blocklist's lookup page where you can see your listing details.
- **Sudden spike in 5.7.1 rejections:** If your 5.7.1 rate jumps from near-zero to 10%+ across multiple recipient domains simultaneously, a blocklist hit is the most likely cause. If the rejections are concentrated at a single ISP, it is more likely an ISP-specific reputation block rather than a public blocklist.

**Important bounce classification note:** Blocklist-triggered rejections are block/policy bounces, not hard bounces. The recipient address is valid — the rejection is about your sending infrastructure. Suppressing these addresses would be incorrect. The fix is to get delisted and address the root cause.

## Major Blocklists That Matter

Not all blocklists are equal. The following are the lists that cause measurable delivery impact because they are widely consulted by major ISPs, enterprise mail servers, or spam filtering appliances.

### Spamhaus

Spamhaus is the most influential blocklist operation in email. Their lists are used by the majority of ISPs and enterprise mail systems worldwide. A Spamhaus listing is a serious event that requires immediate attention.

Spamhaus operates several distinct lists:

- **SBL (Spamhaus Block List):** Lists IPs involved in sending spam. Listings are based on Spamhaus's own investigation and spam trap data. SBL listings are manually curated and tend to be highly accurate. Return code: `127.0.0.2`.
- **CSS (Component of SBL):** A subset of SBL that targets IPs sending low-volume spam, often snowshoe spam (spreading spam across many IPs). Return code: `127.0.0.3`.
- **XBL (Exploits Block List):** Lists IPs compromised by malware, botnets, or open proxies. This is sourced largely from CBL (Composite Blocking List) data. If you are on XBL, your server or a machine on your network is likely compromised. Return code: `127.0.0.4–7`.
- **PBL (Policy Block List):** Lists IP ranges that should not be sending email directly — primarily end-user/dynamic IP space (residential ISPs, mobile networks). This is not a spam listing; it is a policy listing. If a legitimate mail server's IP is on PBL, it was likely added by the IP owner. Return code: `127.0.0.10–11`.
- **DBL (Domain Block List):** Lists domains (not IPs) found in spam. Checks are performed against domains in message URLs, the envelope sender, and the header From. Return code: `127.0.1.2` (spam domain), `127.0.1.4` (phishing), `127.0.1.5` (malware), `127.0.1.6` (botnet C&C).
- **ZEN:** A combined lookup that checks SBL, CSS, XBL, and PBL in a single query. Most receivers use ZEN rather than querying individual lists. Zone: `zen.spamhaus.org`.

**How you get listed:** Spamhaus listings are driven by spam trap hits, direct complaints, and Spamhaus's own monitoring. SBL listings often result from sending to pristine spam traps (addresses that have never been used by a real person and exist solely to catch spam). Sending even a small volume to Spamhaus traps can trigger a listing. There is no published volume threshold — Spamhaus evaluates the evidence holistically.

**How to check:** Query `https://check.spamhaus.org/` or perform DNS lookups against `zen.spamhaus.org`.

**Delisting process:**
- **XBL/CBL listings:** Self-service removal at `https://www.spamhaus.org/lookup/`. Identify and fix the compromised system first, then request removal. Removal is typically processed within minutes. If the underlying issue is not fixed, you will be relisted quickly.
- **PBL listings:** If your IP is legitimately a mail server and should not be on PBL, you can request removal through the PBL portal. This is typically an issue to resolve with your IP provider, who may have submitted the range to PBL.
- **SBL/CSS listings:** These require demonstrating that you have identified and resolved the spam problem. Submit a removal request through the Spamhaus website. Spamhaus may take 24–48 hours to respond and may ask follow-up questions. For SBL, you need to explain what caused the spam, what you did to stop it, and what measures prevent recurrence. Spamhaus does not auto-expire SBL listings — you must actively request removal.
- **DBL listings:** Domain removal follows a similar process to SBL. Submit a request through the Spamhaus website.

**Industry fact:** Spamhaus is a nonprofit organization based in the UK and Switzerland. Their listings are based on observed behavior and their own policies, not on any formal legal or regulatory framework. There is no appeals court — Spamhaus has final say over their own data. This is occasionally contentious, but their accuracy rate is high enough that they remain the most trusted blocklist in the industry.

### Barracuda (BRBL)

Barracuda Networks operates the Barracuda Reputation Block List (BRBL), which is used by Barracuda spam filtering appliances deployed widely in enterprise environments. If your recipients include businesses using Barracuda appliances, a BRBL listing will cause rejections at those organizations.

**How you get listed:** Barracuda operates their own spam trap network and monitoring systems. Listings are typically triggered by spam trap hits or high complaint volumes observed by Barracuda appliances. Barracuda does not publish specific thresholds.

**How to check:** Use the lookup tool at `https://barracudacentral.org/lookups` or query `b.barracudacentral.org` via DNS.

**Delisting process:** Barracuda offers self-service delisting at `https://barracudacentral.org/lookups`. You enter your IP, and if it is listed, you can request removal. Removal requests are typically processed within 12–24 hours. Barracuda's system is largely automated. However, repeat listings will result in longer listing durations, and persistent offenders may find their removal requests denied until they can demonstrate the problem is resolved. There is no manual review or support contact for standard delisting — the self-service portal is the primary mechanism.

### SpamCop

SpamCop is a complaint-driven blocklist. Users submit spam they have received, and SpamCop parses the headers to identify the sending IP. Once enough complaints accumulate against an IP within a time window, the IP is listed.

**How you get listed:** SpamCop listings are driven entirely by user complaints submitted through SpamCop's reporting system. A handful of complaints in a short period can trigger a listing, especially from lower-volume IPs. SpamCop does not use spam traps — it relies on reports from recipients who forward spam to SpamCop.

**How to check:** Query `bl.spamcop.net` via DNS or use `https://www.spamcop.net/bl.shtml`.

**Delisting process:** SpamCop listings are automatic and time-based. Listings expire automatically after 24–48 hours if no new complaints are received. There is no manual delisting process — you wait for the listing to expire. If complaints continue, the listing persists. The only way to clear a SpamCop listing permanently is to stop generating complaints. This makes SpamCop relatively low-severity compared to Spamhaus, but recurring SpamCop listings indicate a complaint-rate problem that will eventually cause broader reputation damage.

**Best practice:** Because SpamCop is complaint-driven, listings here are a signal that recipients are marking your mail as spam. Investigate which campaigns or segments are generating complaints, and focus on complaint-rate reduction rather than trying to game the delisting timeline.

### SORBS (Spam and Open Relay Blocking System)

SORBS maintains multiple lists covering different abuse types: spam, open relays, open proxies, dynamic IP ranges, and more. SORBS was historically significant but has become less relevant in recent years. Its accuracy has been questioned, and maintenance has been inconsistent since its acquisition by Proofpoint in 2011.

**How you get listed:** SORBS uses spam traps, open relay/proxy detection, and reports. Some SORBS listings are based on the IP being in a dynamic/residential range (similar to Spamhaus PBL).

**How to check:** Query the appropriate SORBS zone (e.g., `dnsbl.sorbs.net`) via DNS or use `http://www.sorbs.net/lookup.shtml`.

**Delisting process:** SORBS historically required a fee (around $50 USD) for "express" delisting, which was controversial. Standard delisting is free but slow — listings may persist for weeks or months. As of the time of writing, SORBS operations have been intermittent. If you are listed on SORBS alone and not on other major lists, the practical impact is usually limited, and waiting for automatic expiration or focusing on other reputation factors may be more productive than pursuing delisting.

**Community observation:** Many deliverability professionals now consider SORBS a lower-priority list. If you are listed only on SORBS and experiencing delivery issues, investigate whether the receiving systems actually consult SORBS, or whether other reputation factors are the real cause.

### invaluement

invaluement operates several lists focused on snowshoe spam, botnet spam, and URI-based spam. Their lists are used by some enterprise filtering systems and smaller ISPs.

- **ivmSIP:** Lists IPs sending spam.
- **ivmSIP/24:** Lists /24 ranges when enough individual IPs in the range are listed.
- **ivmURI:** Lists domains found in spam URLs.

**How you get listed:** invaluement uses their own spam trap data and manual investigation. Listings tend to focus on patterns associated with snowshoe spam (using many IPs to distribute low volumes per IP).

**How to check:** Use `https://www.invaluement.com/lookup/` for lookup.

**Delisting process:** invaluement requires an email request to their support. They typically respond within 1–3 business days. They may require evidence that the spam issue has been resolved.

### UCEPROTECT

UCEPROTECT operates three levels of listing:

- **Level 1:** Individual IPs, based on observed spam.
- **Level 2:** Entire /24 blocks, listed when multiple IPs in the range appear on Level 1.
- **Level 3:** Entire ASNs (Autonomous System Numbers), listed when many /24s within the ASN are on Level 2.

**How you get listed:** UCEPROTECT uses automated detection systems. Level 2 and Level 3 listings are entirely algorithmic — your IP can be listed because of other senders in your IP neighborhood, not because of anything you did.

**Delisting process:** UCEPROTECT is controversial. They offer "express" delisting for a fee (approximately EUR 50 for Level 1, more for Level 2/3). Free delisting requires waiting 7 days (Level 1) with no further incidents. Level 2 and Level 3 listings expire automatically when the underlying Level 1 listings are cleared.

**Community observation:** Many deliverability experts view UCEPROTECT's paid delisting model as borderline extortionate, and relatively few major mail systems consult UCEPROTECT. If you are listed only on UCEPROTECT Level 2 or 3 due to IP neighborhood issues, the practical impact is often minimal. Do not pay for delisting unless you have confirmed that the listing is actually causing delivery failures at systems you care about.

### Microsoft's Internal Blocklist

Microsoft (Outlook.com, Hotmail, Live, Office 365) operates an internal blocklist that is not publicly queryable as a DNSBL. You will see rejections like:

```
550 5.7.606 Access denied, banned sending IP [192.0.2.25]. To request removal from this list please visit https://sender.office.com
```

Or the older format:

```
550 SC-001 ... blocked by Outlook.com
```

**Delisting process:** Submit a delisting request through Microsoft's Sender Support form at `https://sender.office.com`. Response times vary from 24 hours to several days. Microsoft's process involves manual review, and they may ask for information about your sending practices. Repeated listings make delisting progressively harder. JMRP (Junk Mail Reporting Program) and SNDS (Smart Network Data Services) enrollment can help prevent future listings.

### Gmail's Internal Reputation System

Gmail does not use external blocklists and does not operate a traditional blocklist. Instead, Gmail uses internal reputation scoring that considers IP reputation, domain reputation, authentication, and engagement signals. When Gmail rejects or defers your mail, the response typically looks like:

```
421-4.7.28 Our system has detected an unusual rate of unsolicited mail originating from your IP address.
550-5.7.26 This mail has been blocked because the sender is unauthenticated.
```

There is no delisting form for Gmail. Reputation recovery requires fixing the underlying issues (authentication, complaint rates, list quality) and waiting for Gmail's algorithms to observe improved behavior. Google Postmaster Tools provides visibility into your domain and IP reputation at Gmail.

## How to Monitor for Blocklist Listings

Reactive delisting is necessary, but proactive monitoring is far better. Check your sending IPs and domains against major blocklists regularly.

**Manual checking tools:**
- MXToolbox Blacklist Check (`https://mxtoolbox.com/blacklists.aspx`): Checks against 80+ blocklists in one query.
- MultiRBL (`https://multirbl.valli.org/`): Checks against 200+ lists.
- Spamhaus Lookup (`https://check.spamhaus.org/`): Authoritative for Spamhaus-specific lists.

**Automated monitoring (best practice):**
- Set up automated monitoring that checks your sending IPs against at least Spamhaus ZEN, Barracuda BRBL, SpamCop, and any other lists relevant to your recipient base.
- Check frequency: Every 1–4 hours for high-volume senders. Daily for lower-volume senders.
- Alert immediately on any Spamhaus listing. Alert within a reasonable window for other lists.
- Most commercial deliverability monitoring platforms (e.g., 250ok/Validity, Senderscore by Validity, Kickbox) include blocklist monitoring as a core feature.

**DNS-based self-monitoring:** You can script your own checks by performing DNS lookups against blocklist zones for each of your sending IPs. A simple loop querying `zen.spamhaus.org`, `b.barracudacentral.org`, `bl.spamcop.net`, and `dnsbl.sorbs.net` covers the highest-impact lists. Any A-record response (rather than NXDOMAIN) indicates a listing.

## Common Causes of Blocklist Listings

Understanding why listings happen is essential for both remediation and prevention:

1. **Spam trap hits:** The most common cause of Spamhaus and Barracuda listings. Pristine traps (never-used addresses) indicate purchased or scraped lists. Recycled traps (abandoned addresses reactivated as traps) indicate poor list hygiene and lack of sunset policies.

2. **High complaint rates:** Primary driver for SpamCop listings and a contributor to other listings. Complaint rates above 0.1% (1 per 1,000 messages) are a risk factor. Above 0.3%, listings become likely.

3. **Compromised infrastructure:** XBL/CBL listings result from malware, compromised servers, or open relays on your network. These listings indicate a security problem, not a marketing problem.

4. **Poor list acquisition practices:** Purchasing lists, scraping addresses, or using single opt-in without verification leads to lists contaminated with traps and invalid addresses.

5. **IP neighborhood contamination:** On shared IPs or within a /24 block, other senders' behavior can affect your listings (especially on UCEPROTECT Level 2/3 and Spamhaus CSS).

6. **Sudden volume spikes:** Abruptly increasing send volume from an IP without proper warming can trigger automated detection systems, even if the mail is legitimate.

## The Delisting Process: General Principles

Regardless of the specific blocklist, the delisting process follows a common pattern:

1. **Identify the listing.** Determine which list(s) you are on, using the SMTP rejection messages from your bounce logs as the starting point. Do not guess — the rejection message names the list.

2. **Diagnose the root cause before requesting delisting.** Submitting a removal request without fixing the problem will result in immediate relisting, and repeated removal requests without remediation will damage your credibility with blocklist operators and may result in longer or permanent listings.

3. **Fix the root cause.** This may involve cleaning your list, fixing a compromised server, implementing authentication, or reducing complaint rates. The specific fix depends on the cause.

4. **Request removal.** Follow the specific process for the relevant blocklist (see sections above). Be honest and specific in any explanation you provide — blocklist operators review thousands of requests and can quickly identify generic or evasive responses.

5. **Monitor after delisting.** Watch for relisting in the hours and days after removal. If you are relisted, the root cause was not fully resolved.

**Timeframes for listing impact:** A Spamhaus SBL listing will cause rejections within minutes of the listing being published, because DNS propagation for blocklist queries is very fast (most receivers query Spamhaus directly, with low or no caching). Delisting takes effect similarly quickly — once the listing is removed from Spamhaus's DNS, receivers querying the list will stop rejecting within minutes to a few hours depending on DNS TTL caching.

## When a Listing Is Not Your Fault

In some cases, you may be listed due to factors outside your direct control:

- **Shared IP reputation:** If you send from shared IPs (e.g., through an ESP), another sender on the same IP may have caused the listing. Contact your ESP; this is their problem to resolve, but switching to a dedicated IP may be necessary if the issue recurs.
- **IP neighborhood effects:** UCEPROTECT Level 2/3 and occasionally Spamhaus CSS can list IPs based on /24 block behavior. If other tenants in your IP range are spamming, your IP may be caught in a range listing. Work with your hosting provider or IP allocator to address the abusive neighbors, or move to a cleaner IP range.
- **Inherited IP reputation:** If you acquired a new IP address that was previously used for spam, it may already be listed. Always check new IPs against blocklists before putting them into production. Request delisting for inherited listings, explaining that you are a new user of the IP.

## Key Takeaways

- **Spamhaus is the blocklist that matters most.** A Spamhaus SBL or CSS listing causes widespread delivery failures. Treat any Spamhaus listing as a priority-one incident. Other lists (Barracuda, SpamCop) have narrower impact but still warrant prompt attention.
- **Blocklist rejections are block/policy bounces, not hard bounces.** Never suppress recipient addresses based on blocklist-triggered 5.7.1 rejections. The problem is your sending infrastructure, not the recipient address.
- **Fix the root cause before requesting delisting.** Delisting without remediation leads to relisting, and repeated removal requests without demonstrated fixes erode your credibility with blocklist operators and can result in longer or permanent listings.
- **Monitor proactively.** Automated blocklist monitoring with alerting — checking at least Spamhaus ZEN, Barracuda BRBL, and SpamCop every few hours — prevents listing incidents from persisting undetected and causing extended delivery failures.
- **Not all blocklists are equal.** Before spending effort on delisting from an obscure list, confirm that the listing is actually causing delivery failures at mail systems you send to. Focus remediation effort on high-impact lists first.
