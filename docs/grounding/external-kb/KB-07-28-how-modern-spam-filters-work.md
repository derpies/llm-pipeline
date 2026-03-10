# How Modern Spam Filters Work

## Overview

Modern spam filtering has evolved from simple keyword-based analysis (e.g., searching for "Viagra" or "Free Money") into a multi-layered, machine-learning-driven evaluation of sender reputation, technical infrastructure, and real-time user engagement. For a deliverability engineer, it is critical to understand that **spam is no longer defined by what is in the message, but by who sent it and how the recipient reacted to it.**

Large mailbox providers (MBPs) like Gmail, Microsoft, and Yahoo use a "weighted signal" approach. No single factor—such as a missing DKIM signature or a "spammy" subject line—guarantees a spam folder placement. Instead, the filter aggregates hundreds of signals into a single "reputation score." If that score falls below a dynamic threshold, the message is filtered.

## The Three Pillars of Filtering

Modern filters evaluate every incoming message across three primary dimensions:

### 1. Technical Infrastructure and Authentication
This is the "entrance exam" for any email. Before the content is even scanned, the filter checks:
- **Authentication (SPF/DKIM/DMARC):** Does the message prove it is from who it claims to be? A `DMARC: pass` is now a baseline requirement for reaching the inbox at Gmail and Yahoo (especially for bulk senders).
- **IP/Domain Reputation:** Is the sending IP or domain on any reputable blocklists (Spamhaus, Barracuda)? What is the historical "trust" level of this sending identity?
- **Connection Hygiene:** Is the sender using a valid PTR (Reverse DNS) record? Are they using TLS encryption?

### 2. Reputation and Historical Patterns
ISPs maintain a "memory" of every sender. They track:
- **Volume Consistency:** Sudden spikes in volume (e.g., from 1k to 100k overnight) are a major red flag for "spammy" behavior.
- **Bounce Rates:** High `5.1.1` (User Unknown) rates indicate a sender is using old or purchased data.
- **Trap Hits:** Hits to pristine or recycled spam traps (see `KB-05-22`) are high-confidence signals of malicious intent.

### 3. Engagement Signals (The Most Influential Pillar)
This is the most significant shift in filtering over the last decade. ISPs observe how users interact with your mail:
- **Positive Signals:** Opening the email, clicking a link, moving the email from "Promotions" to "Primary," and (most importantly) "Marking as Not Spam."
- **Negative Signals:** Deleting without opening, moving to "Spam," and explicit "Mark as Spam" complaints.

## The Filtering Lifecycle: From SMTP to Inbox

Filtering happens in three discrete stages during the delivery lifecycle:

### Stage 1: Connection-Level Filtering (Gateway)
The filter evaluates the IP address and connection behavior.
- **Technical Signal:** If the IP is on a "Real-time Blocklist" (RBL), the server issues a `554 5.7.1` rejection at the SMTP gateway.
- **Throttling:** If the IP's reputation is "Neutral" but volume is high, the server issues `421 4.7.0` (Try again later) to slow down the sender while it evaluates more data.

### Stage 2: Content and Header Scanning (Post-DATA)
Once the message is accepted via the `DATA` command, the filter scans:
- **URL Reputation:** Every link in the email is checked against a "Domain Blocklist" (DBL). A single link to a compromised or "spammy" domain can sink the entire message.
- **Fingerprinting:** Filters look for "clusters" of identical messages sent across the internet. If 100,000 identical messages appear simultaneously from many different IPs, it is flagged as a botnet attack.

### Stage 3: Machine Learning Classification (Inbox/Spam/Tab)
This is the "brain" of the operation. Models like Gmail's TensorFlow-based filters combine the technical, reputation, and engagement signals to make a final placement decision.
- **Clustering:** The filter groups your message with other "similar" messages. If other messages in that cluster were marked as spam by users, your message will likely follow.
- **Tab Placement:** This is where the filter decides if a message is "Commercial" (Promotions), "Social," or "Transactional" (Primary).

## The Concept of "Dynamic Thresholds"

Filtering thresholds are not static. They vary based on:
- **Recipient Behavior:** If a specific user frequently opens your emails, your "reputation threshold" for that user is lower. You might reach *their* inbox even if your global reputation is declining.
- **Global Spam Trends:** During high-spam events (like elections or holidays), ISPs often "tighten" their filters, requiring higher reputation scores for inbox placement.
- **Sender Type:** Transactional senders (e.g., password resets) are often held to different (more lenient) reputation standards than bulk marketing senders, provided they use separate subdomains/IPs.

## Log Indicators of Filtering Decisions

| Signal | SMTP Code | Meaning |
| :--- | :--- | :--- |
| **Gateway Block** | `554 5.7.1` | The connection was refused based on IP reputation or RBL listing. |
| **Policy Rejection** | `550 5.7.1` | The content or sender reputation failed internal policy checks. |
| **Rate Limiting** | `421 4.7.0` | "Too many messages" - the filter is "braking" your send to protect its users. |
| **DMARC Rejection** | `550 5.7.26` | Gmail specific: The message failed DMARC and the policy is `p=reject`. |

## Key Takeaways

- **Authentication is the baseline:** You cannot reach the inbox without valid SPF, DKIM, and DMARC.
- **Engagement is the king of signals:** High "Mark as Spam" rates (above 0.1%) will override even the best technical setup.
- **Reputation is portable:** Your domain reputation follows you across IPs. Changing your IP will not "fix" a filter problem rooted in domain reputation.
- **Filters are looking for "patterns":** Consistency in volume, content, and list hygiene is the best way to stay on the right side of the filter.
- **The "DATA" response is just the beginning:** A `250 OK` only means the message passed the gateway; it does not guarantee the filter won't move it to spam 2 seconds later.
