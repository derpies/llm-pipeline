# Playbook: Throttling and Deferrals

## Overview
Throttling occurs when an ISP temporarily rejects your connection or limits the rate at which they accept mail from your IP or Domain. It is a "speed limit" designed to protect the receiver's resources or to "brake" a sender whose reputation is questionable. 

Unlike a hard bounce, a throttle is a temporary failure (`4xx` code). Your MTA will retry the message on an escalating schedule. However, if throttling is severe, the messages will expire in the queue after 24–72 hours, resulting in a delivery failure.

## Symptoms
- **High Queue Depth:** Your MTA queue is rapidly filling with thousands of messages.
- **Delivery Delay:** Messages that normally arrive in seconds are taking hours to be delivered.
- **Log Signals:** 
  - `421 4.7.0 ... Too many connections from your IP.`
  - `421 4.7.1 ... Rate limit exceeded.`
  - `451 4.7.1 ... [TS01] deferred due to user complaints.` (Yahoo)

## Root Cause Analysis
1.  **Sudden Volume Spike:** You increased your sending volume significantly (e.g., from 10k to 100k) without a proper warm-up.
2.  **Reputation Drop:** An ISP (especially Yahoo or Gmail) has detected a spike in spam complaints and is "throttling" you while it evaluates your traffic.
3.  **High Concurrency:** Your MTA is opening too many simultaneous TCP connections to the ISP's MX servers.
4.  **Low Initial Reputation:** You are sending from a new IP or Domain that hasn't established trust yet.
5.  **Technical Misconfiguration:** Your MTA is not correctly handling `4xx` responses and is aggressively retrying too quickly, which leads to further throttling.

## Step-by-Step Fix

### 1. Identify the ISP and Error Code
*Throttling is almost always ISP-specific.*
- Audit your MTA logs for the `4xx` responses. Group them by the `relay=` destination (e.g., Gmail, Yahoo, Microsoft).

### 2. Immediate Rate-Limit Reduction (The "Brake")
- Adjust your MTA's sending rate for the problematic ISP.
  - **Connections:** Reduce the maximum number of simultaneous connections (e.g., from 10 to 2).
  - **Messages per Connection:** Reduce the number of messages sent over a single TCP session (e.g., to 50).
  - **Hourly Limit:** Implement an hourly cap (e.g., 5,000 messages per hour to Yahoo).

### 3. Check Feedback Loops (FBLs)
- If the throttle is at Yahoo or Microsoft, check your FBL reports for a spike in complaints. If complaints are high, you must **halt the send** to that specific segment immediately.

### 4. Verify MTA Retry Schedule
- Ensure your MTA is configured for "Exponential Backoff." It should wait 15 minutes, then 30, then 60 before retrying a throttled message. Retrying every 60 seconds will only extend the throttle.

### 5. Monitor the Queue Release
- Watch the `mailq` to see if messages are successfully clearing. If the throttle persists beyond 12 hours, you likely have a reputation problem that requires a delisting or support ticket.

## Prevention
- **Proper Warm-Up:** Never send more than a 2x increase in volume per day when using a new IP or Domain (see `KB-09-42`).
- **Reputation Buffering:** Maintain a high domain reputation in Google Postmaster Tools. "High" reputation senders are rarely throttled.
- **MTA Optimization:** Use an MTA (like PowerMTA) that has built-in "Traffic Control" rules for major ISPs. These rules automatically adjust sending rates based on the ISP's real-time responses.
- **List Hygiene:** Monitor your complaint rate daily. A rate below 0.1% is the best defense against throttling.
