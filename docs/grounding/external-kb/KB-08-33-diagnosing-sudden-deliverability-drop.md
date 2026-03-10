# Diagnosing a Sudden Deliverability Drop

## Overview

A sudden deliverability drop—often appearing as a "cliff" in your open-rate or delivery-rate charts—is a high-severity event that requires immediate technical triage. Unlike gradual decline, a sudden drop indicates a binary failure: an IP or domain has been blocklisted, a technical authentication mechanism has broken, or an ISP has triggered an emergency rate-limit.

This article provides a systematic, flowchart-based approach to identifying the root cause of a sudden drop. The goal is to isolate the variables (Infrastructure vs. Reputation vs. Content) and move from "we're in spam" to a "step-by-step fix" in under 60 minutes.

## Phase 1: Impact Assessment

Before troubleshooting, determine the "blast radius."

1.  **Is it ISP-specific or Global?**
    - **ISP-specific:** Open rates at Gmail are 2% but Yahoo is 25%. (Root cause: ISP-specific reputation or throttle).
    - **Global:** All providers show a 70-90% drop in volume/engagement. (Root cause: Global blocklist or broken authentication).
2.  **Is it a Delivery Failure or a Deliverability Failure?**
    - **Delivery (Hard/Soft Bounce):** SMTP logs show `5xx` or `4xx` codes. The mail never arrived.
    - **Deliverability (Spam Placement):** SMTP logs show `250 OK`, but open rates are near zero.

## Phase 2: The Technical Triage Flowchart

Follow these steps in order. Stop once a failure is identified.

### Step 1: Infrastructure and DNS Check
*The foundation of the email must be valid for any delivery to occur.*
- **PTR Record (Reverse DNS):** Verify that your sending IP's PTR record still exists and resolves. Run `dig -x [sending-ip]`. If the PTR is missing, ISPs will immediately reject all connections.
- **Port 25 Connectivity:** Can your MTA still reach the outside world? A firewall change can suddenly block outbound traffic.
- **Queue Depth:** Check your MTA queue (`mailq` or `postqueue -p`). If it's spiking, the problem is a **block** or **throttle** (Delivery), not spam folder placement (Deliverability).

### Step 2: Authentication Verification (The #1 Source of Sudden Drops)
*Authentication often breaks due to DNS changes (e.g., a new marketing tool added a record that exceeded the 10-lookup SPF limit).*
- **SPF:** Check for `permerror` (often caused by too many DNS lookups).
- **DKIM:** Send a test email to a service like `mail-tester.com` or `dkimvalidator.com`. If the signature fails, *everything* goes to spam or is rejected.
- **DMARC:** Check if your DMARC policy recently moved to `p=reject`. If SPF/DKIM is even slightly misaligned, `p=reject` will cause a total delivery cliff.

### Step 3: Global Blocklist Check
*A single spam trap hit can result in a sudden block.*
- **Check Spamhaus (SBL/DBL):** This is the "kill switch" for global email. Check your IP and Domain on `spamhaus.org/lookup`.
- **Check Barracuda and Cloudmark:** Many enterprise filters use these.

### Step 4: Reputation Dashboard Triage
*If authentication and infrastructure are fine, check the "official" reputation grades.*
- **Google Postmaster Tools:** Did the Domain Reputation drop from "High" to "Bad"? Check the "Spam Rate" for a spike above 0.3%.
- **Microsoft SNDS:** Is the IP status "Red"? Look for a spike in "Spam Trap Hits."

## Phase 3: Content and Segment Isolation

If technical checks pass, the drop is likely due to a specific **send** or **segment.**

1.  **Analyze the "Last Send":**
    - Did you mail a new list source? (Pristine Spam Trap risk).
    - Did you mail a "stale" segment (inactive > 1 year)? (Recycled Spam Trap risk).
    - Did you change your URL shortener or add a new link to a compromised domain? (URL Blocklist risk).
2.  **Review Spam Complaints:**
    - Check your Feedback Loops (FBLs). Did a specific campaign trigger a complaint rate above 1%? This will cause immediate spam folder placement at Yahoo and Microsoft.

## Log Signal Indicators

| Symptom | SMTP Code | Likely Root Cause |
| :--- | :--- | :--- |
| **Authentication Rejection** | `550 5.7.26` | DKIM or SPF failed/missing. |
| **Global Blocklist** | `554 5.7.1` | IP/Domain on Spamhaus or similar. |
| **Reputation Throttle** | `421 4.7.0` | High complaints or sudden volume spike. |
| **DMARC Policy** | `550 5.7.1` | Alignment failure under `p=reject`. |
| **Greylisting (Normal)** | `451 4.7.1` | First time sending to this receiver. |

## Immediate Remediation Steps

If you've identified a reputation-based drop:
1.  **Pause all bulk sends.** Do not "push through" a block; it only deepens the reputation damage.
2.  **Fix the technical failure** (DNS, SPF, DKIM) immediately.
3.  **Halt sending to unengaged users.** For the next 7 days, send **only** to users who have opened/clicked in the last 14 days.
4.  **Submit mitigation tickets** (Microsoft SNDS, Apple Postmaster) only *after* you have fixed the root cause.

## Key Takeaways

- **Isolate the variable:** Determine if the problem is one ISP or all ISPs, and one IP or the whole Domain.
- **Authentication is the first suspect:** Always verify DKIM and SPF before investigating reputation or content.
- **Check the "Return-Path":** A sudden drop often occurs when a sender changes their return-path domain, breaking SPF alignment.
- **Spamhaus is the "Oracle":** If you are listed there, nothing else matters until you are delisted.
- **Don't ignore the MTA queue:** A growing queue with `421` codes is the earliest warning of a sudden drop in reputation.
