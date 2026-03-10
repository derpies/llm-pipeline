# Why Email Lists Degrade Over Time

## Overview

Email list degradation, often called "list decay," is the natural process by which a once-healthy database of email addresses becomes increasingly invalid, unengaged, or toxic. For deliverability professionals, list decay is not merely a marketing concern regarding "reach"—it is a primary driver of reputation damage and infrastructure throttling. 

Industry benchmarks indicate that the average B2B email list degrades at a rate of **22.5% to 30% per year**, while B2C lists often see decay rates between **15% and 25%**. Sending to a decaying list results in higher hard bounce rates, increased spam trap hits, and declining engagement signals—all of which inform ISP filtering algorithms to move your mail from the inbox to the spam folder.

## The Mechanics of Natural Churn

Natural churn occurs when a recipient no longer uses the email address they provided. This happens for several structural reasons:

- **Employment Changes (B2B):** In the B2B sector, the most common cause of decay is job turnover. When an employee leaves a company, their mailbox is typically deactivated (resulting in a `550 5.1.1 User Unknown` hard bounce) or converted to a "catch-all" that accepts mail but never reads it (dead engagement).
- **Provider Migration (B2C):** Users frequently switch primary email providers (e.g., moving from a legacy ISP like Comcast or AOL to Gmail). While the old account may stay active for a period, it eventually becomes a "ghost" account that contributes to low engagement before finally being deactivated.
- **Account Abandonment:** Users often create "burner" accounts for one-time discounts or gated content. These accounts are abandoned shortly after creation. Mailbox providers like Outlook and Gmail monitor these accounts; if an account is not accessed for a prolonged period (typically 1–2 years), the provider may deactivate it or, more dangerously, convert it into a recycled spam trap.

**Log Indicator:** Natural churn manifests in logs as a steady, incremental increase in `5.1.1` (User Unknown) status codes. If your daily hard bounce rate is increasing by **0.1% to 0.5% per month** without changes to your acquisition strategy, you are witnessing natural list decay.

## Role Accounts and Generic Addresses

Role accounts (e.g., `sales@`, `support@`, `admin@`, `info@`) are email addresses defined by a job function rather than an individual. While these addresses are technically "valid," they are high-risk for deliverability:

- **Multiple Recipients:** These addresses often forward to multiple people. If any one of those individuals marks your email as spam, it generates a complaint signal for the entire group, effectively multiplying your complaint rate.
- **Low Engagement:** Role accounts are rarely "engaged" in the way ISPs like to see. They are used for inbound inquiries, not for subscribing to newsletters.
- **Higher Trap Probability:** Role accounts are frequently harvested by scrapers and are more likely to be associated with "pristine" spam traps managed by blocklist operators.

**Best Practice:** Many high-reputation senders automatically suppress role accounts during the signup process or flag them for manual review. A list containing more than **10% role accounts** is typically flagged by ESPs as a "high-risk" or "purchased" list.

## Typo Domains and Synthetic Invalidity

Typo domains enter a list at the point of collection when a user mistypes their address (e.g., `user@gamil.com` instead of `user@gmail.com`).

- **Immediate Hard Bounces:** Most typo domains do not exist, resulting in an immediate `5.1.2` (Host not found) or `5.1.1` (User unknown) bounce.
- **Typo Traps:** Some blocklist operators and security firms register common typo versions of major domains (like `yaho.com` or `outlok.com`) specifically to catch senders with poor list hygiene. Hitting a typo trap is a signal to ISPs that you lack "confirmed opt-in" (COI) or basic data validation at the point of entry.

**Data Insight:** Typo domains typically account for **2% to 5%** of new signups in unvalidated web forms. Using real-time API validation (like Kickbox or NeverBounce) at the point of entry can eliminate this form of decay before it enters your database.

## The Transition from "Unengaged" to "Spam Trap"

This is the most critical technical aspect of list decay. When a user abandons a mailbox, the ISP follows a specific deactivation lifecycle:

1.  **Active/Unengaged:** The mailbox exists, but the user never opens mail. ISPs see this lack of engagement and begin routing your mail to the spam folder for that specific user.
2.  **Soft Bounce (Temporary):** The ISP may temporarily disable the account, returning `451 4.2.1` or `452 4.2.2` (Mailbox full) codes.
3.  **Hard Bounce (Permanent):** The ISP deactivates the account entirely, returning `550 5.1.1` (User unknown).
4.  **Recycled Spam Trap:** After a period of inactivity (6–12 months), the ISP may reactivate the address. It no longer belongs to a human; it is now a trap. Any mail sent to this address is a "trap hit," signaling that the sender is mailing old, stale data and has no sunset policy.

**Key Technical Threshold:** If more than **10% of your list has not opened an email in 6 months**, your list is in an advanced state of decay. You are significantly more likely to hit recycled spam traps in this segment than in your active segment.

## Log Indicators of List Decay

When analyzing delivery logs, look for these specific patterns that indicate your list is degrading:

| Log Signal | SMTP Code | Interpretation |
| :--- | :--- | :--- |
| **Rising 5.1.1 Rate** | `550 5.1.1` | Addresses are being deactivated. A rate above **0.5% per send** indicates stale data. |
| **Increasing 4.2.1/4.2.2** | `452 4.2.2` | Mailboxes are full and abandoned. These are "pre-dead" addresses that will soon hard bounce. |
| **MTA Throttling** | `421 4.7.0` | ISPs (especially Gmail/Yahoo) may throttle you if they see too many attempts to invalid users in a single session. |
| **Policy Rejections** | `550 5.7.1` | If this appears after a "clean" send, it may indicate you hit a spam trap (e.g., Spamhaus SBL) due to mailing old addresses. |

## Key Takeaways

- **Decay is inevitable:** Expect **20-25%** of your list to become invalid every year due to natural life changes of your recipients.
- **Engagement is the leading indicator:** Addresses that haven't opened in 90–180 days are the primary source of future hard bounces and recycled spam traps.
- **Validate at entry:** Prevent typo domains (which account for up to 5% of entries) by using real-time syntax and domain validation on all signup forms.
- **Monitor your 5.1.1 rates:** A hard bounce rate exceeding **0.5%** on a per-campaign basis is a technical signal that your list hygiene processes are failing.
- **Role accounts are risk multipliers:** Addresses like `info@` or `admin@` increase the probability of spam complaints and trap hits; treat them as high-risk segments.
