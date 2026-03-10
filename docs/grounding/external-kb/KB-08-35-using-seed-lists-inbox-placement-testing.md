# Using Seed Lists and Inbox Placement Testing

## Overview

A "seed list" is a controlled set of email addresses at various mailbox providers (ISPs) used to measure the placement of an email campaign. Because SMTP logs only confirm "delivery" (the message was accepted with a `250 OK`), seed testing is the primary technical method for measuring "deliverability" (whether the message landed in the Inbox, Spam folder, or a specific tab).

Seed list testing (e.g., via GlockApps, Everest, or Mail-Tester) provides a "snapshot" of how a specific message from a specific infrastructure is treated by major filters. While highly valuable, it is important to understand its technical limitations and how to interpret its data alongside your actual recipient logs.

## How Seed Testing Works Technically

1.  **The Seed List:** A set of 50–200 email addresses distributed across Gmail, Microsoft, Yahoo, Apple, and various international/corporate providers.
2.  **The Send:** You send your email campaign to this seed list from your actual sending infrastructure (same IP, same domain).
3.  **The Collection:** A central server monitors the "Inbox" and "Spam" folders of these seed accounts.
4.  **The Report:** The tool aggregates the findings into a report showing placement percentages by ISP (e.g., "Gmail: 100% Inbox, Microsoft: 50% Spam").

## The Technical Limitations of Seeds

Seed testing is a "synthetic" measure. It has several inherent blind spots:

### 1. Lack of Engagement History
Seed accounts are automated bots. They do not have the decades of engagement history (opens, clicks, "mark as not-spam") that a real recipient has.
- **The Result:** Seed tests are "worst-case" scenarios. If your real-world reputation is bolstered by a loyal fanbase, your actual inbox placement may be higher than your seed test results.

### 2. The "Bot Behavior" Loophole
ISPs are aware of seed testing. If they detect a large number of identical messages being sent to a cluster of unused accounts, they may route them all to spam regardless of the sender's reputation.
- **The Strategy:** High-quality seed services "humanize" their seeds by periodically opening and clicking emails to avoid being flagged as "static" accounts.

### 3. Personalization Blindness
Modern filters are highly personalized. A seed test cannot reflect whether your email will go to spam for a specific *segment* of your list that has stopped opening your mail.

## Interpreting Seed Test Results

When reviewing a seed test, look for these specific technical patterns:

### Pattern A: Clean Authentication, Poor Placement
- **Result:** Seed reports show SPF/DKIM/DMARC as `PASS`, but placement is still 100% Spam at Microsoft.
- **Interpretation:** This is a **Reputation Block.** Your IP or Domain is on a Microsoft-internal blocklist, or your complaint rate is too high.

### Pattern B: The "Tab" Check (Gmail)
- **Result:** 100% Inbox placement, but 100% in the "Promotions" tab.
- **Interpretation:** This is the correct placement for marketing mail. If your goal is the "Primary" tab, you must audit your content (see `KB-06-24`).

### Pattern C: Regional Variance
- **Result:** Inbox placement is 100% in the US but 0% in Europe (e.g., GMX.de, Web.de).
- **Interpretation:** You are likely on a regional blocklist or have failed a technical requirement specific to those providers (like T-Online's aggressive DNS checks).

## Best Practices for Seed Testing

1.  **Test Before the Bulk Send:** Send to the seed list 24 hours before your main campaign. This allows you to catch technical errors (like a broken DKIM signature) before mailing your entire list.
2.  **Use "Reference" Content:** Occasionally send a "known good" email (text-only, no links) to your seed list. If it still goes to spam, the problem is definitely your IP/Domain reputation, not your content.
3.  **Correlate with Logs:** If a seed test shows 100% Inbox but your actual open rates are 2%, trust your actual open rates. Your "real" reputation with real users is the truth; the seed is a simulation.
4.  **Don't Over-Test:** Sending to seeds too frequently can lead to "seed fatigue," where ISPs begin filtering the seeds simply because they are part of a predictable, automated pattern.

## Diagnostic Value Table

| Seed Test Signal | What it Diagnoses |
| :--- | :--- |
| **Authentication Fail** | SPF/DKIM/DMARC misconfiguration. |
| **URL Blocklist Hit** | A link in your body is listed on a DBL. |
| **Microsoft "Junk" Placement** | Poor IP reputation in SNDS. |
| **Gmail "Promotions" Tab** | High image/link density or `Precedence: bulk` header. |
| **Universal Spam Placement** | Global Domain Blocklist (Spamhaus DBL). |

## Key Takeaways

- **Seeds measure placement, not delivery:** Logs tell you if the server said "yes"; seeds tell you where they put the body.
- **Seeds are reputation "baselines":** They show how a "neutral" recipient sees you.
- **Use seeds to catch "breaks":** A sudden move from Inbox to Spam in seeds is a definitive signal of a new blocklist or a broken DNS record.
- **Don't obsess over the 100% score:** Because seeds lack engagement history, a 90% score is often excellent for a high-volume sender.
- **Combine with actual data:** A seed test is one "leg" of the diagnostic tripod; the other two are SMTP logs and reputation dashboards.
