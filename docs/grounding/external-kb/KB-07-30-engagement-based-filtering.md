# Engagement-Based Filtering

## Overview

Engagement-based filtering is the most influential factor in modern email deliverability. For mailbox providers (ISPs) like Gmail, Microsoft (Outlook/Hotmail), and Yahoo, **engagement is the primary measure of consent.** They no longer rely solely on whether a sender has the technical "right" to send an email; they care more about whether the recipient actually *wants* to receive it.

ISPs observe billions of interactions daily to build a "reputation profile" for every sender. If they see that your emails are consistently opened, clicked, and moved out of the spam folder, your "Engagement Reputation" rises, and you gain better inbox placement. If they see that your emails are deleted without being opened or marked as spam, your reputation will plummet, leading to permanent spam-folder placement.

## The Hierarchy of Engagement Signals

Not all engagement signals are weighted equally. ISPs categorize signals into "Positive" and "Negative" clusters to inform their filtering decisions.

### Positive Signals (Inbox Boosting)
- **Open and Click (Medium Value):** While basic, high open and click rates signal that the content is relevant to the recipient.
- **Reply (High Value):** A direct reply from a recipient to a sender is a "trust" signal of the highest order. It suggests a two-way relationship.
- **Add to Contacts / Safe Senders (Highest Value):** This explicitly tells the ISP that the recipient trusts the sender and wants their mail in the inbox.
- **"Mark as Not Spam" (Highest Value):** This is the strongest possible corrective signal. It tells the ISP their filter was wrong and provides a massive boost to your reputation.
- **Move to Folder:** Moving an email from "Promotions" to "Primary" or a custom user folder indicates long-term value.

### Negative Signals (Reputation Damage)
- **Delete without Opening (Medium Impact):** A high volume of this signal suggests the user is "skimming" and doesn't find your content valuable.
- **Unsubscribe (Low/Neutral Impact):** Paradoxically, a high unsubscribe rate is better than a high spam complaint rate. ISPs view unsubscribing as a "polite" way to end a relationship.
- **"Mark as Spam" / Complaints (High Impact):** This is the most damaging signal. It is a direct "report" that the sender is violating the recipient's trust.
- **Bounce Rate (High Impact):** As discussed in `KB-04-17`, high hard bounce rates signal a lack of list hygiene and imply non-consensual acquisition.

## The Feedback Loop Mechanism

Large ISPs provide data back to senders to help them improve their behavior. 

### 1. Traditional Feedback Loops (ARF)
Most providers (Yahoo, Microsoft, etc.) offer an **Abuse Reporting Format (ARF)** feedback loop. When a user marks an email as spam, the ISP sends a copy of that email back to the sender.
- **Technical Requirement:** You must register your sending IPs and domains with each ISP's FBL program.
- **Action:** You must **immediately** remove any user who marks your email as spam from your active list. Failing to do so is a "hygiene failure" that leads to blocking.

### 2. Gmail's Unique Approach
Gmail does not provide a traditional ARF-based feedback loop. Instead, they provide aggregate data through **Google Postmaster Tools.**
- **Indicator:** The "Spam Rate" dashboard. If this rate exceeds **0.1%** (1 complaint per 1,000 sends), you will see an immediate drop in inbox placement. If it reaches **0.3%**, Gmail will begin blocking your mail entirely.

## Engagement Ratios and "The Denominator"

ISPs don't just look at the *total* number of opens; they look at the **ratio of engagement.** 

- **The Math:** If you send 100,000 emails and get 10,000 opens (10%), your engagement is "Medium." If you send 50,000 emails and get 10,000 opens (20%), your engagement is "High."
- **The Strategy:** This is why **sunsetting unengaged users** (see `KB-05-21`) is so critical. By removing the 50,000 people who *never* open your mail, you increase your engagement ratio, which signals to the ISP that your list is "higher quality." This results in better placement for the remaining 50,000.

## The Interaction between Placement and Engagement

Deliverability is a "circular" system:
1.  **Good Placement** leads to **High Engagement** (people can see the email, so they open it).
2.  **High Engagement** leads to **Better Reputation**.
3.  **Better Reputation** leads to **Even Better Placement**.

**The Danger Zone:** Conversely, if you are routed to the spam folder, engagement will drop (no one sees the email). This leads to a declining reputation, which "traps" you in the spam folder. To break this cycle, you must stop bulk sending and focus exclusively on your most engaged (recently active) segment until your reputation recovers.

## Log Indicators of Engagement Problems

Engagement failures are often "silent" in SMTP logs because the ISP accepts the message with a `250 OK`. However, look for these secondary signals:

| Indicator | Source | Interpretation |
| :--- | :--- | :--- |
| **Declining Open Rates** | ESP Metrics | Sudden drop from 20% to 5% open rate at one specific domain (e.g., @gmail.com) while others stay stable. |
| **Increased Complaints** | FBL / Postmaster | "Mark as Spam" rate exceeding 0.1% on a per-campaign basis. |
| **SNDS "Yellow" or "Red"** | Microsoft SNDS | Microsoft's reputation dashboard turning yellow or red for your IP. |
| **Increased Throttling** | SMTP Logs | `421 4.7.0` codes appearing as the ISP "protects" its users from high-volume, low-engagement mail. |

## Key Takeaways

- **Consent is the foundation:** Permission is the "right" to send; engagement is the "proof" that the user still wants the mail.
- **Sunsetting is a deliverability tool:** Pruning unengaged users is the most effective way to improve your engagement ratios.
- **Complaints are toxic:** Keep your "Mark as Spam" rate below 0.1% at all times. Use FBLs to remove complainers immediately.
- **Engagement is domain-specific:** A problem at Gmail won't necessarily exist at Yahoo, but your domain reputation is the underlying driver for all of them.
- **Positive engagement "repairs" reputation:** Encourage replies, clicks, and "move to primary" interactions to build a buffer against future reputation hits.
