# Playbook: Recovering from a Spam Trap Hit

## Overview
A spam trap hit is a high-confidence signal to ISPs that your list acquisition or hygiene processes have failed. While some hits lead to immediate blocklisting (see `KB-09-38`), others result in a "slow death" of reputation, where your mail gradually moves to the spam folder. Recovery requires technical forensics and a willingness to permanently prune your list.

## Symptoms
- **Sudden Reputation Drop:** Google Postmaster Tools Domain Reputation moves from "High" to "Low" or "Bad."
- **Microsoft SNDS Trap Counts:** Your SNDS dashboard shows a non-zero number in the "Spam Trap Hits" column for a specific IP.
- **Increasing 421/451 Codes:** ISPs (especially Yahoo and Gmail) begin "throttling" your traffic with rate-limiting codes.
- **Spam Folder Placement:** Inbox placement testing (seed testing) shows a shift from 90%+ Inbox to near 0% across multiple providers.

## Root Cause Analysis
1.  **Pristine Trap Hit:** You mailed a "scraped" or purchased address that was never owned by a human. (Result: Immediate block).
2.  **Recycled Trap Hit:** You have no sunset policy and continue to mail addresses that have been abandoned for 1+ years. (Result: Reputation degradation).
3.  **Typo Trap Hit:** Your signup form has no real-time validation, and a bot or a mistyped user entered a trap domain (e.g., `@gamil.co`).

## Step-by-Step Fix

### 1. Identify the "Hit" Date and Campaign
- Correlate your reputation drop or blocklist listing with your sending history. 
- Look for **new list imports** or **campaigns to stale segments** that were sent 24–48 hours before the reputation drop.

### 2. Isolate the "Toxic" Source
- If the hit occurred after a specific import, **immediately and permanently suppress every address from that import.**
- If the hit was to an existing segment, you must determine which list source (e.g., "Facebook Ads Lead Gen") is producing the traps.

### 3. Tighten the Sunset Window
- **Recycled Trap Fix:** Immediately apply a **90-day sunset policy** to your entire database. Suppress any subscriber who has not opened or clicked an email in the last 3 months.
- **Why?** Recycled traps are dormant accounts. By only mailing active users, you effectively "clean" your list of traps without ever knowing which specific addresses were the traps.

### 4. Implement Double Opt-In (DOI)
- Transition all new signups to a Double Opt-In flow. This prevents any new "Typo Traps" or bot-generated addresses from entering your list.

### 5. Reputation Repair Send
- For the next 14 days, send only to your "Ultra-Engaged" segment (opened/clicked in last **14 days**).
- **Goal:** This generates massive positive engagement signals (opens, clicks, moving to inbox) that signal to ISP filters that the "trap hit" was an anomaly.

### 6. Monitor Dashboards
- Check Google Postmaster Tools daily. Your goal is to see the Domain Reputation move back from "Bad" or "Low" to "Medium," and eventually "High."

## Prevention
- **Avoid Purchased Lists:** No remediation succeeds if you continue to buy data.
- **Maintain a 180-day Sunset:** Never let a subscriber stay active on your list for more than 6 months without engagement.
- **Real-Time Validation:** Use an API (like Kickbox or NeverBounce) on all web forms to block typo domains.
- **Monitor SNDS Weekly:** Microsoft SNDS is the only tool that explicitly reports trap hits. Use it to catch "re reputation rot" before it leads to a global block.
