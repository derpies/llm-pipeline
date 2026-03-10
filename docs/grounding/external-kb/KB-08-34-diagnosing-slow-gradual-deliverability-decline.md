# Diagnosing Slow/Gradual Deliverability Decline

## Overview

Unlike a sudden drop, a gradual deliverability decline is a "slow leak" in your reputation. It often manifests as a multi-month trend: open rates dipping from 25% to 15%, or a steady increase in "Promotions" tab placement relative to "Primary." Because the change is subtle, it often goes unnoticed until the decline becomes critical and recovery is difficult.

Gradual decline is almost always caused by **list rot** or **reputation erosion.** It signals that your list hygiene practices are not keeping pace with natural list decay, or that your content engagement is slowly losing relevance to your recipients.

## The Indicators of Gradual Decline

Identifying gradual decline requires analyzing historical trends rather than daily spikes.

1.  **Trend Line Analysis:** Plot your open rates and click rates over 90 days. If the trend is downward while your sending volume and frequency are stable, you have a reputation erosion problem.
2.  **Reputation Dashboard Drift:**
    - **Google Postmaster:** Your Domain Reputation moves from "High" to "Medium" and stays there for weeks.
    - **Microsoft SNDS:** Your IP status begins showing "Yellow" for several days a week.
3.  **Increasing Bounce "Creep":** A steady increase in your hard bounce (`5.1.1`) rate—for example, moving from 0.1% to 0.4% over six months—is a definitive signal that your list hygiene processes are failing.

## Root Cause 1: List Hygiene Erosion

The most common cause of slow decline is the accumulation of unengaged users. 

### The "Dead Weight" Mechanics
As you continue to mail users who never open your emails, your **engagement ratio** (Opens / Total Delivered) declines. Large mailbox providers (Gmail, Yahoo) use this ratio to determine whether your content is "wanted." 
- **The Threshold:** If more than 50% of your list has not engaged in the last 180 days, you are "weighting" your reputation downward every time you send.
- **The Fix:** Implement or tighten your sunset policy (see `KB-05-21`). Moving from a 12-month sunset to a 6-month sunset can often reverse a gradual decline within 30 days.

## Root Cause 2: Recycled Spam Trap Accumulation

Recycled spam traps are abandoned addresses repurposed by ISPs to catch senders who don't clean their lists.
- **The Signal:** You are not hitting a "big" trap like Spamhaus, but Microsoft SNDS shows 1-2 trap hits every few sends.
- **The Result:** Your mail is slowly "demoted" from the inbox to the Junk folder for more and more users. 
- **The Fix:** Run your list through a validation service (see `KB-05-20`) to remove known "dead" mailboxes and immediately suppress any user who has not opened in 180 days.

## Root Cause 3: Engagement Fatigue (Content Irrelevance)

If your list is "fresh" but your engagement is still declining, the problem is your content.
- **Symptoms:** Open rates are stable, but **Click-to-Open (CTOR)** rates are falling. This tells you that users are opening the mail but finding the content uninteresting.
- **The ISP Signal:** "Delete without opening" signals are increasing. If a user deletes your email 10 times in a row without reading it, the ISP will eventually route the 11th email to the spam folder for that specific user.
- **The Fix:** Review your sending frequency. "Over-mailing" is a primary driver of engagement fatigue. Reducing frequency from 5x weekly to 3x weekly often improves aggregate engagement signals.

## Phase-by-Phase Recovery Strategy

Do not attempt to fix gradual decline with "emergency" delisting tickets. It requires a behavioral shift:

### Phase 1: The Audit (Days 1-7)
- **Segment Audit:** Identify which segments have the lowest open rates. Often, the decline is driven by one "toxic" list source or a very old segment.
- **Frequency Audit:** Are you sending more volume than you were six months ago? 
- **Feedback Loop Check:** Ensure you are successfully removing every ARF/CFL complainer. A breakdown in your FBL processing will cause a slow, steady reputation death.

### Phase 2: The Pruning (Days 8-14)
- **Aggressive Sunsetting:** Temporarily move your sunset threshold to 90 days of inactivity. Stop mailing anyone who hasn't opened in 3 months.
- **Validation:** Batch clean your inactive segment before attempting any "win-back" campaigns.

### Phase 3: The Recovery Send (Days 15-30)
- **Engagement-First Sending:** For two weeks, send only to your most active users (opened/clicked in last 30 days).
- **Monitor Dashboards:** Watch Google Postmaster Tools for the move back from "Medium" to "High" reputation.

## Data Indicators for Monitoring

| Metric | Healthy | Warning | Decline Indicator |
| :--- | :--- | :--- | :--- |
| **Open Rate** | > 20% | 12-15% | Steady monthly decline. |
| **Hard Bounce (5.1.1)** | < 0.2% | 0.5% | Incremental rise over time. |
| **GPT Reputation** | High | Medium | Persistent "Medium" status. |
| **SNDS Trap Hits** | 0 | 1-2 | Occasional, repeated hits. |
| **Complaints** | < 0.05% | 0.1% | Creeping toward 0.3%. |

## Key Takeaways

- **Trend is your friend:** Look at 90-day charts, not daily dashboards.
- **Inactivity is the enemy:** The longer an unengaged user stays on your list, the more they damage your reputation.
- **List hygiene is a continuous process:** Decline happens when you treat "cleaning" as a one-time event rather than a daily automation.
- **Content fatigue leads to spam placement:** If users stop clicking, ISPs will eventually stop delivering.
- **Reversal takes time:** Because gradual decline is built on months of bad behavior, recovery often takes 2–4 weeks of "perfect" sending to highly engaged users.
