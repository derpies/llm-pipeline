# Yahoo and AOL Deliverability

## Overview

Yahoo and AOL (both part of Yahoo Inc.) share the same technical infrastructure and filtering engine. For deliverability purposes, they can be treated as a single entity. Like Gmail, Yahoo has adopted strict 2024 Bulk Sender requirements, mandating SPF, DKIM, and DMARC for all high-volume senders.

Yahoo's filtering is characterized by its **strong reliance on complaint rates** and its unique feedback loop program. Yahoo is also more likely to use "throttling" (rate-limiting) as a primary filtering tool, often deferring a high percentage of mail with `421` codes before ultimately accepting it or rejecting it.

## The 2024 Yahoo Sender Requirements

Yahoo's requirements for 2024 mirror those of Google, with some specific nuances:

1.  **Authentication Mandatory:** All senders must have SPF or DKIM. Bulk senders (those sending more than 5,000 messages per day) must have **both** and must have a DMARC policy of at least `p=none`.
2.  **Alignment Requirement:** Yahoo requires SPF or DKIM to align with the domain in the visible `From:` header.
3.  **One-Click Unsubscribe:** Senders must implement the `List-Unsubscribe` header with the one-click (RFC 8058) POST mechanism.
4.  **Complaint Rate Ceiling:** Yahoo strictly enforces a **0.3%** spam complaint rate limit. Senders exceeding this will see immediate deliverability degradation.

## The Yahoo Complaint Feedback Loop (CFL)

The CFL is Yahoo's ARF-format feedback loop. Unlike Gmail, Yahoo provides the actual "complainer" data back to the sender.
- **How to Register:** You must register your sending domain and IPs at `postmaster.yahoo.com`.
- **Action:** You must **immediately** remove any recipient who marks your email as spam. Yahoo monitors your FBL response rate; if you do not remove complainers, your reputation will be permanently downgraded.

## Yahoo-Specific Filtering Patterns

### 1. Intense Throttling and Deferrals
Yahoo is the most aggressive provider when it comes to "deferring" mail. Even if your reputation is good, Yahoo may temporarily reject your connection to protect their system's capacity.
- **Log Indicator:** `421 4.7.0 [TS01] Messages from [IP] temporarily deferred due to user complaints.`
- **Interpretation:** This is not a block; it's a "slow down" signal. Your MTA should retry automatically. However, if the `TS01` or `TS02` code persists for more than 4 hours, it means Yahoo is evaluating your volume against your complaint rate and has found you wanting.

### 2. "User Unknown" Harvesting Blocks
Yahoo is very sensitive to senders attempting to "harvest" email addresses.
- **The Signal:** If a sender attempts to deliver to a high volume of non-existent Yahoo accounts (`550 5.1.1 User Unknown`) in a single session, Yahoo will temporarily block the IP for 24 hours.
- **Indicator:** `421 4.7.1 [GL01] Message from [IP] temporarily deferred - [User unknown rate is too high].`

### 3. Yahoo Postmaster Tools
While less feature-rich than Google's tools, Yahoo Postmaster provides a "Sender Reputation" grade and a "Spam Rate" dashboard for your verified domains. It is the only official source for Yahoo's view of your "Commercial" vs. "Transaction" classification.

## Troubleshooting Yahoo Issues

If your mail at Yahoo is going to the "Spam" folder, use this triage process:

1.  **Check the CFL (Feedback Loop):** Is your complaint rate spiking? If so, identify the campaign or list source that caused the spike and suppress it.
2.  **Verify SPF/DKIM Alignment:** Yahoo's filters will penalize unaligned mail more heavily than Gmail. Ensure your `From:` domain and your DKIM/SPF domains match exactly.
3.  **Monitor the `TS` Codes:** Parse your MTA logs for Yahoo's specific `[TSxx]` error codes. These codes are highly specific and tell you whether the problem is reputation, volume, or technical.
4.  **The "Slow Down" Strategy:** If you are being deferred with `TS01`, reduce your connection concurrency (the number of simultaneous TCP connections) to Yahoo MX servers. A "polite" connection strategy often resolves Yahoo deferrals within 12–24 hours.

## Key Takeaways

- **Complaints are the "Yahoo Killer":** Stay below 0.3% and remove all CFL complainers immediately.
- **Alignment is critical:** Ensure SPF/DKIM domains match your visible `From:` header.
- **Don't panic on `421` deferrals:** They are normal at Yahoo. Panic only if they persist beyond 4-6 hours or turn into `550` rejections.
- **Respect the "User Unknown" limit:** High hard bounce rates at Yahoo will lead to immediate IP blocks. Validate your list before sending.
- **Use Yahoo Postmaster Tools:** It's the only way to see your official Yahoo reputation score.
