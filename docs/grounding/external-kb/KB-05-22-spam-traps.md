# Spam Traps

## Overview

A spam trap is an email address created or repurposed by a mailbox provider (ISP) or an anti-spam organization (such as Spamhaus) specifically to identify and block senders who use poor acquisition or list hygiene practices. Spam traps are the "landmines" of the email deliverability world—they look like legitimate email addresses, but they have no human owner and have never opted into receiving mail.

Hitting a spam trap is a high-confidence signal to an ISP that a sender is either:
1.  **Purchasing/Scraping lists:** Using data they do not have permission to mail.
2.  **Failing at list hygiene:** Continuing to mail abandoned or invalid addresses for months or years.
3.  **Failing at data validation:** Allowing typos or malicious entries into their database.

## The Three Primary Types of Spam Traps

Understanding which type of trap you have hit is essential for diagnosing the root cause of the deliverability failure.

### 1. Pristine Spam Traps (The Most Dangerous)
Pristine traps are email addresses that have never belonged to a human. They are created solely for the purpose of catching spammers. These addresses are "planted" on websites hidden from human view (using CSS `display:none`) but visible to automated web scrapers and bots.
- **Cause:** You purchased a list, scraped a website, or used a co-registration partner that uses unethical collection methods.
- **Consequence:** Immediate and severe. Hitting a single pristine trap managed by Spamhaus or a major ISP can result in a total, permanent block of your IP and domain.

### 2. Recycled Spam Traps (The Hygiene Signal)
Recycled traps are old email addresses that once belonged to a human but were abandoned. The ISP deactivates the address, returns `5.1.1` hard bounces for a period (usually 6–12 months), and then reactivates it as a trap.
- **Cause:** You have no sunset policy and are not removing hard bounces from your list. If you continue mailing an address for a year after it stops engaging, you will eventually hit a recycled trap.
- **Consequence:** While less severe than pristine traps, frequent recycled trap hits indicate "reputation rot." ISPs will begin routing your mail to the spam folder as a result of poor maintenance.

### 3. Typo Traps (The Validation Signal)
Typo traps are registered for domains that are common misspellings of major providers (e.g., `user@gamil.com`, `user@yaho.com`, `user@outlok.com`).
- **Cause:** You are not validating email addresses at the point of signup or using Double Opt-In (DOI).
- **Consequence:** These primarily signal that your list acquisition process is "unfiltered." While they rarely result in immediate blocklisting, they contribute to a lower overall sender reputation score.

## The Impact of a Spam Trap Hit

The severity of the impact depends on the authority of the entity that owns the trap:

- **Blocklist Placement:** Hitting a trap owned by **Spamhaus (SBL/PBL)** or **SURBL** can lead to immediate blocklisting. Because many ISPs use these lists as a primary filter, your delivery rate will drop to near zero across the entire internet.
- **Immediate Throttling:** ISPs like Gmail and Microsoft track trap hits internally. A spike in hits will trigger immediate connection throttling (`421 4.7.0`) and "Policy Rejections" (`550 5.7.1`).
- **Reputation Degradation:** Your "Domain Reputation" score in Google Postmaster Tools will drop from "High" to "Low" or "Bad," resulting in all mail—even to your most engaged users—going to the spam folder.

## How to Identify and Remove a Spam Trap

The challenge with spam traps is that **the trap owner will never tell you which address is the trap.** If they did, spammers would simply remove the address and continue spamming. To remove a trap, you must use data forensics:

### 1. Identify the "Hit" Date
Check your reputation monitoring tools (Microsoft SNDS, Google Postmaster Tools, or third-party blocklist monitors like MXToolbox). Identify the exact day your reputation dropped or the blocklist was triggered.

### 2. Correlate with Recent Activity
Look at the segments you mailed on or just before the hit date.
- Was a new list imported?
- Did you mail a "stale" segment that hadn't been touched in 6+ months?
- Did you run a lead-generation campaign with a new partner?

### 3. Segmented Suppression
If you cannot identify the specific address, you must suppress the high-risk segment entirely.
- **Pristine Trap Fix:** Suppress every address acquired from the suspect source or lead-gen partner.
- **Recycled Trap Fix:** Immediately apply a 180-day sunset policy (see `KB-05-21`). Suppress everyone who hasn't opened an email in the last 6 months. This effectively "cleans" the traps out of your list.

## Log Indicators of a Spam Trap Problem

Spam trap hits are rarely "silent." They manifest in your delivery logs as policy blocks:

| Log Signal | SMTP / Error Code | Meaning |
| :--- | :--- | :--- |
| **Spamhaus Listing** | `554 5.7.1 Service unavailable; Client host [IP] blocked using sbl.spamhaus.org` | You hit a pristine or high-value trap. Immediate total block. |
| **Microsoft SNDS "Trap" Count** | (External Dashboard) | SNDS will show a non-zero number in the "Spam Trap Hits" column for a specific IP. |
| **Policy Rejection** | `550 5.7.1 ... blocked for reputation` | General reputation failure often following a trap hit. |
| **Spam Folder Placement** | (No Log Signal) | Sudden drop in open rates while delivery success remains 100%. |

## Key Takeaways

- **Prevention is the only real fix:** You cannot "buy" your way off a blocklist caused by a trap hit. You must fix the underlying acquisition or hygiene issue.
- **No purchased lists:** Buying a list is the fastest way to hit a pristine trap and end your sending capability.
- **Sunset your data:** A 180-day sunset policy is the most effective defense against recycled spam traps.
- **Use Double Opt-In (DOI):** Sending a confirmation link to new subscribers prevents typo traps and malicious bots from polluting your list.
- **Don't wait for a hit:** Monitor your hard bounce (`5.1.1`) rates. If they are above 0.5%, your list is decaying and you are at imminent risk of hitting a recycled trap.
