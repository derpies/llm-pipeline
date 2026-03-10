# Playbook: Spam Folder Placement

## Overview
Spam folder placement occurs when your mail is delivered (SMTP `250 OK`), but the mailbox provider's (ISP's) internal filters have classified the content as unwanted. This is the most common "silent" deliverability failure. Unlike bounces, it provides no error codes; it simply manifests as a collapse in open rates and engagement.

## Symptoms
- **Low Open Rates:** Open rates drop below 10% (excluding Apple MPP) at specific ISPs.
- **Stable Delivery Rate:** Your SMTP logs show near-100% success (`status=sent`).
- **Reputation Dashboard Drop:** 
  - **GPT:** Domain Reputation is "Low" or "Bad."
  - **SNDS:** IP Status is "Yellow" or "Red."
- **Seed Test Confirmation:** 100% of seed accounts report placement in the Spam or Junk folder.

## Root Cause Analysis
1.  **Engagement Reputation Deficit:** You have a long history of sending to unengaged users, and ISPs have "learned" that your content is irrelevant.
2.  **Spam Complaint Spike:** A recent campaign triggered a "Mark as Spam" rate above 0.3% at Gmail or Yahoo.
3.  **URL Pollution:** You are linking to a domain that is on a blocklist or has poor reputation (see `KB-07-29`).
4.  **Content Filter Trigger:** Your message structure (e.g., image-to-text ratio, missing List-Unsubscribe) is triggering heuristic filters.
5.  **New Sender Trust:** You are sending from a new IP or Domain that hasn't been properly warmed up.

## Step-by-Step Fix

### 1. Audit Authentication
*Always start with technicals.*
- Verify SPF, DKIM, and DMARC alignment. If any of these are `FAIL` or `SOFTFAIL`, it is the primary reason you are in the spam folder.

### 2. Isolate Content vs. Reputation
- Send a "Clean" test (text-only, no images, no links) to a seed list.
- **If the clean test goes to Inbox:** The problem is your **Content** (check URLs and image ratios).
- **If the clean test still goes to Spam:** The problem is your **IP/Domain Reputation.**

### 3. Immediate "Clean Segment" Pivot
*This is the most effective reputation repair tactic.*
- For the next 7-14 days, send ONLY to your "Ultra-Engaged" segment (users who have opened or clicked an email in the last **14 days**).
- **Goal:** This generates a high density of "positive engagement" signals that force the ISP's filters to re-evaluate your domain's trust level.

### 4. Audit Your Link Reputation
- Check every domain in your email body on `spamhaus.org/lookup`.
- Ensure your tracking domain (e.g., `links.brand.com`) is correctly aligned and authenticated.

### 5. Check List Hygiene and Complaints
- Review your Feedback Loops (FBLs) and Google Postmaster Tools "Spam Rate." Identify any campaigns with a complaint rate above 0.1%. Immediately suppress the source list for those campaigns.

## Prevention
- **Tighten Your Sunset Policy:** Move to a 180-day or even 90-day sunset policy for inactive users (see `KB-05-21`).
- **Use Double Opt-In (DOI):** Ensure only high-intent users enter your list.
- **Avoid Over-Mailing:** Monitor your sending frequency. If engagement is declining, reduce frequency to rebuild trust.
- **Continuous Postmaster Monitoring:** Check your reputation daily. If it drops from "High" to "Medium," reduce your sending volume to the unengaged segment immediately to prevent it from dropping further to "Low."
