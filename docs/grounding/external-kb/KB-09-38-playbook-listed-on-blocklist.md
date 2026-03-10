# Playbook: Listed on a Blocklist

## Overview
A blocklist listing—specifically on a high-influence list like Spamhaus—is an emergency state that results in a near-total cessation of deliverability across the internet. Being listed is a technical verdict from the email ecosystem that your sending behavior is indistinguishable from spam.

## Symptoms
- **Global Delivery Drop:** You see near-100% bounce rates at all ISPs.
- **Log Signals:** 
  - `554 5.7.1 Service unavailable; Client host [IP] blocked using sbl.spamhaus.org`
  - `550 5.7.1 ... blocked by bl.spamcop.net`
  - `550 5.7.1 ... listed at dbl.spamhaus.org` (Domain Blocklist)
- **Dashboard Alerts:** Alerts from MXToolbox or other RBL (Real-time Blocklist) monitoring services.

## Root Cause Analysis
1.  **Pristine Spam Trap Hit (The Most Likely Cause):** You recently imported a scraped or purchased list (see `KB-05-22`). 
2.  **Compromised Infrastructure:** Your MTA or an internal server has been "hacked," and a spam bot is sending massive volume from your IP (XBL listing).
3.  **High Complaint Rate:** Your users are marking your mail as spam at an extreme frequency (>1%), triggering a blocklist like SpamCop.
4.  **Shared IP Reputation Contamination:** Another sender on your shared IP range is spamming, resulting in the entire subnet being listed.

## Step-by-Step Fix

### 1. Identify the Listing Type
Check the specific blocklist on the list operator's website (e.g., `spamhaus.org/lookup`).
- **SBL (Spamhaus Block List):** IP reputation. 
- **DBL (Domain Block List):** Domain reputation.
- **XBL (Exploits Block List):** Security/botnet issue.

### 2. Identify and Halt the Cause
Do not request delisting yet. **If you request delisting without fixing the root cause, you will be re-listed within hours and your reputation will be permanently damaged.**
- **If SBL/DBL:** Audit your last 48 hours of sends. Identify any new list sources or "unengaged" campaigns. Immediately suppress the problematic segment.
- **If XBL:** Check your MTA logs for volume spikes to unknown recipients. Scan your sending server for unauthorized processes or scripts.

### 3. Implement Permanent Suppression
- If the listing was caused by a specific list source, **purge that list source** from your database permanently.
- Apply a strict 90-day sunset policy (see `KB-05-21`) to all existing segments.

### 4. The Delisting Request
- Once the cause is fixed, follow the list operator's formal removal process.
- **Communication:** Be honest and technical. State: "We identified that list source [X] hit a trap. We have permanently suppressed all 50,000 addresses from that source and implemented a strict sunset policy."
- **Avoid:** Generic "I'm sorry, I won't do it again" messages. Blocklist operators want to see technical remediation steps.

### 5. Monitor the De-Listing
Check your MTA logs to verify that the `554 5.7.1` rejections have stopped. It may take 12–24 hours for the change to propagate globally.

## Prevention
- **Avoid Purchased Lists:** No legitimate delisting request succeeds if you continue to mail purchased data.
- **Monitor Your Reputation Daily:** Use Google Postmaster Tools and Microsoft SNDS to catch reputation drops *before* they result in a blocklist listing.
- **Secure Your MTA:** Ensure your SMTP server is not an "Open Relay" and uses strong authentication for all submission ports (587/465).
- **Automate Hygiene:** Integrate bounce and FBL processing into your MTA so invalid addresses are suppressed in real-time.
