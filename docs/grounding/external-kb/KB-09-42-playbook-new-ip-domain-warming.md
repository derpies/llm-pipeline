# Playbook: New IP/Domain Warming

## Overview
IP and Domain "Warming" is the process of building a positive reputation with mailbox providers (ISPs) by gradually increasing the volume of mail sent from a new infrastructure. ISPs are inherently suspicious of new, high-volume senders, as this is a primary behavior of spammers. 

A "cold" IP or Domain starts with zero reputation. Sending a million emails on Day 1 will result in immediate and permanent blocking. To reach the inbox, you must "prove" you are a legitimate sender by sending to engaged users and slowly ramping up over 14–30 days.

## Symptoms (If Warming is Skipped)
- **High Initial Deferrals:** Your logs are filled with `421 4.7.0` (Try again later) or `421 4.7.1` (Rate limit exceeded) codes.
- **Universal Spam Placement:** Even clean, authenticated mail goes to the junk folder at every major ISP.
- **Reputation Blocks:** Immediate blocks from Microsoft (`S3150`) or Gmail.

## Root Cause Analysis
- **ISPs lack historical data:** They have no record of your bounce rates, complaint rates, or user engagement. 
- **Spam Filtering Models:** ISPs assume high-volume, new-sender traffic is a "botnet" or "spam burst" until proven otherwise. 

## Step-by-Step Fix (The Warming Schedule)

### 1. Preparation Phase (Days 1-2)
*Technicals first.*
- **Verify PTR:** Ensure your new IP's reverse DNS resolves correctly.
- **Verify Authentication:** SPF, DKIM, and DMARC (`p=none`) must be 100% correct.
- **Verify List Hygiene:** Clean your list using a verification service (see `KB-05-20`). **Zero tolerance for hard bounces** on a new IP.

### 2. Phase 1: The "Ultra-Engaged" Segment (Days 3-7)
- **Send Only to Your Best Users:** This means people who have opened or clicked an email in the last **30 days**.
- **Volume Ramping:** Start small and double daily. 
  - Day 1: 50 emails
  - Day 2: 100 emails
  - Day 3: 200 emails
  - Day 4: 400 emails
  - Day 5: 800 emails
- **Goal:** This generates the maximum density of "Positive Engagement" signals (opens, clicks, moving to inbox).

### 3. Phase 2: Moderate Ramping (Days 8-14)
- **Expand the Segment:** Start including users who have opened in the last **60–90 days**.
- **Volume Ramping:** Increase by 50% daily.
  - Day 8: 1,500 emails
  - Day 10: 3,500 emails
  - Day 12: 8,000 emails
  - Day 14: 15,000 emails

### 4. Phase 3: Transition to Full Bulk (Days 15-30)
- **Slowly include the rest of your list:** Continue to monitor Google Postmaster Tools and Microsoft SNDS daily.
- If at any point you see a reputation drop or a spike in `421` codes, **pause the ramp-up for 48 hours.**

### 5. Monitor and Adjust
- **GPT:** Ensure your Domain Reputation is moving from "No Data" to "Medium" or "High."
- **SNDS:** Ensure the status is "Green."

## Prevention
- **Separate Transactional vs. Marketing:** Always warm your transactional IP/domain separately. Never mix a new marketing campaign with your critical password reset emails.
- **Maintain Consistency:** Once warmed, do not let an IP go "cold" by stopping all sending for 30+ days. If you have a period of no activity, you must re-warm the IP at 50% of its normal volume.
- **Avoid Content Variation:** Keep your content consistent during the warm-up period. Do not change your brand name or subject line "style" mid-warm-up.
- **Listen to the ISPs:** If you get a `421` code, **it is a command to slow down.** Respect the throttle.
- **Don't Rush:** A 30-day warm-up is the standard. Attempting to "shortcut" the process to 7 days is the fastest way to trigger a permanent block.
