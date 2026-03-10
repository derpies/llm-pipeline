# Microsoft (Outlook/Hotmail) Deliverability

## Overview

Microsoft's consumer email ecosystem—comprising Outlook.com, Hotmail, MSN, and Live.com—is notoriously difficult for high-volume senders. Microsoft uses a combination of its own "SmartScreen" filtering technology and data from its "SNDS" (Smart Network Data Services) platform to make delivery decisions.

Unlike Gmail, which is heavily domain-centric, Microsoft remains deeply invested in **IP reputation.** Even if your domain reputation is high, a "bad" neighborhood of IP addresses (shared IPs) or a sudden spike in volume from a new IP can lead to immediate and permanent blocks. Microsoft is also more prone to "silent discards," where mail is accepted with a `250 OK` but never actually appears in the recipient's mailbox (not even in the Junk folder).

## Smart Network Data Services (SNDS)

SNDS is Microsoft's equivalent to Google Postmaster Tools, but it provides data primarily on **IP addresses.** To use SNDS, you must "request access" to specific IP ranges, usually by receiving a verification email sent to the `postmaster@` or `abuse@` address for those IPs.

### Key SNDS Metrics
- **IP Reputation (Color Coding):**
  - **Green:** Good. Low complaint rates and few spam trap hits.
  - **Yellow:** Suspicious. High complaint rates or moderate trap hits. Some mail will go to the Junk folder.
  - **Red:** Poor. High complaint rates or frequent trap hits. Most mail will be blocked or sent to Junk.
- **Complaint Rate:** Microsoft is very sensitive to complaints. A complaint rate consistently above **0.1%** will turn an IP red.
- **Trap Hits:** SNDS explicitly reports the number of spam traps your IP has hit. Frequent hits indicate a severe list hygiene problem.

## The Junk Mail Reporting Program (JMRP)

The JMRP is Microsoft's feedback loop. When a user marks your email as "Junk" in the Outlook.com interface, Microsoft sends a copy of that email back to you in ARF (Abuse Reporting Format) format.
- **Technical Requirement:** You must sign up for JMRP for every IP you use.
- **Action:** Like all FBLs, you must **suppress** these users immediately. Microsoft monitors your JMRP response time; if you continue to mail users who have complained, your IP reputation will be downgraded to "Red."

## Microsoft's Filtering Tendencies

### 1. Connection-Level Blocking
Microsoft is more aggressive than Gmail at blocking connections based on IP reputation before any message data is sent.
- **Log Indicator:** `550 5.7.1 Service unavailable; Client host [IP] blocked using Spamhaus` or similar Microsoft-internal blocklists.
- **The "S3150" Error:** This is the most common Microsoft block. It indicates that "part of their network is on our block list." This is often a permanent block that requires a manual support ticket to resolve.

### 2. The "Focused" vs. "Other" Inbox
Similar to Gmail's tabs, Microsoft uses "Focused Inbox" to separate personal mail from commercial mail.
- **Mechanism:** Microsoft analyzes user engagement (opens/replies) to determine placement.
- **Impact:** Commercial mail almost always lands in the "Other" tab. This is not a failure; it is the intended destination for marketing content.

### 3. Silent Discards
This is Microsoft's most controversial filtering practice. They may accept a message with a `250 OK` but then discard it during internal processing because it was classified as high-confidence spam.
- **Detection:** You will only notice silent discards by observing a "Green" status in SNDS but **0% engagement** (no opens/clicks) from Microsoft recipients.

## Deliverability Support and Mitigation

Microsoft provides a formal "Sender Support" ticket system. If your IP is blocked (`S3150` or `550 5.7.1`), you can submit a request for mitigation.
- **Pre-requisite:** You must be enrolled in JMRP and SNDS before they will even consider your request.
- **Outcome:** If Microsoft finds your behavior is "generally good" but you hit a trap or had a temporary complaint spike, they may "conditionally mitigate" your IP, allowing mail to flow again while they monitor your performance.

## Microsoft 365 (Enterprise) vs. Consumer

It is important to distinguish between **Outlook.com (Consumer)** and **Microsoft 365 (Enterprise/Corporate).**
- **Consumer:** Uses the SNDS/JMRP logic described above.
- **Enterprise:** Each tenant (company) can set their own "Exchange Online Protection" (EOP) policies. While they use the same underlying "SmartScreen" engine, an IT admin can override Microsoft's defaults and block any sender at their discretion.
- **Diagnostic Header:** Look for the `X-Forefront-Antispam-Report` header in received mail. The `SCL` (Spam Confidence Level) score tells you how Microsoft 365 viewed the message (SCL 1-4 is clean; 5-9 is spam).

## Key Takeaways

- **IP Reputation is paramount:** Use dedicated IPs if possible, and monitor SNDS daily.
- **Sign up for JMRP:** It is the only way to "see" complaints and prune your list to prevent a "Red" reputation.
- **Warm up slowly:** Microsoft is extremely suspicious of new volume. A "burst" of mail from a new IP will result in an immediate `S3150` block.
- **Watch for "S3150" and "S3140" errors:** These are your signals to stop sending and file a support ticket.
- **Silent discards are real:** Monitor engagement rates at Outlook.com domains. If they drop to zero while logs show `250 OK`, your mail is being silently discarded.
