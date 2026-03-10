# Gmail Deliverability

## Overview

Gmail is the largest mailbox provider (MBP) in the world and serves as the primary "trendsetter" for global deliverability standards. Gmail's filtering infrastructure, built on top of Google's sophisticated machine learning (TensorFlow), focuses almost entirely on **sender reputation** and **recipient engagement.** 

For a deliverability engineer, Gmail is unique because it provides the most transparent data (via Google Postmaster Tools) while enforcing the strictest technical requirements (such as the 2024 Bulk Sender mandates). Success at Gmail requires a "clean" technical setup, near-zero complaint rates, and a highly engaged recipient base.

## The 2024 Bulk Sender Mandates

Starting in February 2024, Google enforced a set of mandatory technical requirements for all senders, with additional requirements for "Bulk Senders" (defined as those sending more than 5,000 messages per day to Gmail addresses).

### 1. Mandatory Authentication (SPF, DKIM, and DMARC)
- **The Rule:** All senders must authenticate using SPF or DKIM. Bulk senders must have **both** SPF and DKIM, and a DMARC policy of at least `p=none`.
- **Technical Detail:** Gmail requires "Alignment." This means the domain in the visible `From:` header must match the domain in either the SPF (`Return-Path`) or the DKIM signature.
- **Log Indicator:** `550 5.7.26` Rejection. Gmail's error message will explicitly state: "This message does not have authentication information or fails to pass authentication checks."

### 2. One-Click Unsubscribe (RFC 8058)
- **The Rule:** Bulk senders must implement a one-click unsubscribe mechanism in the email headers.
- **Technical Requirement:** You must include two headers:
  - `List-Unsubscribe: <https://example.com/unsubscribe/id>`
  - `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
- **Impact:** Failure to include this will result in immediate "Promotions" or "Spam" folder placement, and potentially rate-limiting.

### 3. The 0.3% Spam Rate Ceiling
- **The Rule:** Senders must maintain a spam complaint rate (as reported in Google Postmaster Tools) of below **0.1%**. A rate of **0.3%** or higher is considered a "critical failure" and will result in widespread blocking.
- **The Nuance:** Gmail's spam rate is calculated based on "active" users. If your Postmaster Tools dashboard shows 0.3%, you are at extreme risk of your domain reputation being permanently downgraded.

## Google Postmaster Tools (GPT)

GPT is the only "official" way to see your reputation through Google's eyes. It provides seven distinct dashboards that every deliverability engineer must monitor:

### 1. Domain Reputation
This is the most critical metric. It is graded as **High, Medium, Low, or Bad.**
- **High:** Mail is almost never filtered.
- **Medium/Low:** Mail will likely go to the "Promotions" tab or occasionally to "Spam."
- **Bad:** Almost all mail goes directly to "Spam" or is rejected at the gateway.

### 2. IP Reputation
While domain reputation is now more important, IP reputation still matters for high-volume senders. If your IP reputation is "Bad" but your domain is "High," Gmail may throttle your connection speed (`421 4.7.0`) while still delivering the mail.

### 3. Spam Rate
This dashboard shows the percentage of users who clicked "Report Spam" relative to the volume delivered to the inbox. **Note:** If your mail is already going to the spam folder, your "Spam Rate" will paradoxically drop to 0%, because users cannot report spam on mail that is already in the spam folder.

### 4. Delivery Errors
Shows the percentage of mail rejected or temporarily deferred by Gmail, along with a "Reason" code (e.g., "Rate limit exceeded," "Suspected spam").

## The Gmail "Tab" Algorithm

Gmail uses a secondary layer of filtering to sort mail into Primary, Social, Promotions, and Updates tabs. **Tab placement is not the same as spam filtering.**

- **The Primary Tab:** Reserved for person-to-person communication and highly critical transactional mail (e.g., password resets).
- **The Promotions Tab:** The default home for almost all commercial/marketing mail. Placement here is considered a "success" for marketing mail; it does not indicate a reputation problem.
- **How Tabs are Decided:** Gmail looks at the "commerciality" of the content. High image-to-text ratios, "Shop Now" buttons, and the presence of the `Precedence: bulk` header all trigger "Promotions" placement.

**Strategy Note:** Do not try to "game" the tab algorithm by removing formatting or pretending to be a person-to-person email. If Gmail detects a bulk sender trying to "trick" the Primary tab, it will often result in a "Spam" folder placement as a penalty for deceptive behavior.

## Gmail-Specific SMTP Error Codes

When Gmail filters your mail, it provides specific "Diagnostic URLs" in the SMTP response. You must parse these URLs to understand the root cause.

| Error Code | Meaning | Diagnostic URL Suffix |
| :--- | :--- | :--- |
| **`550 5.7.1`** | **Unsolicited Message:** Gmail thinks your mail is spam based on reputation or content. | `/UnsolicitedMessageError` |
| **`550 5.7.26`** | **Auth Failure:** The message failed SPF, DKIM, or DMARC. | `/AuthenticationError` |
| **`421 4.7.0`** | **Throttling:** Too many messages from your IP, or a sudden spike in volume. | `/RateLimitExceededError` |
| **`550 5.7.1`** | **New Sender:** Your IP/Domain has no reputation and you are sending too fast. | `/NewSenderError` |

## Dealing with the "Spam Folder Trap"

If your mail suddenly moves to the spam folder at Gmail, follow this "Recovery Protocol":

1.  **Check GPT Domain Reputation:** If it has dropped to "Low" or "Bad," you have a reputation crisis.
2.  **Verify Authentication:** Ensure SPF, DKIM, and DMARC are all `PASS` and aligned in GPT's "Authentication" dashboard.
3.  **Halt Bulk Sending:** Immediately stop all marketing sends to unengaged users (anyone who hasn't opened in 30 days).
4.  **Send ONLY to "Ultra-Engaged" Users:** For the next 14 days, send only to users who have opened/clicked in the last 7–14 days. This generates "Positive Engagement" signals (opens, moving to inbox) that tell Gmail's ML model to re-evaluate your reputation.
5.  **Avoid Content Changes:** Do not change your subject lines or body copy during a reputation crisis. Gmail's filters are primarily reputation-based; changing content looks like a "spammer tactic" to bypass filters.

## Key Takeaways

- **Authentication is mandatory:** As of 2024, if you don't have SPF, DKIM, and DMARC (with alignment), you will be blocked.
- **Postmaster Tools is your "Source of Truth":** Monitor your Domain Reputation daily. A drop from "High" to "Medium" is an early warning; "Low" is an emergency.
- **One-click unsubscribe is a technical requirement:** Ensure your headers include RFC 8058 compliant tags.
- **Engagement is calculated per-user:** Gmail's filters are highly personalized. Your mail may land in the inbox for your fans and the spam folder for your inactive users simultaneously.
- **Respect the 0.1% complaint limit:** Gmail is less tolerant of complaints than any other provider. List hygiene is the only way to stay below this ceiling.
