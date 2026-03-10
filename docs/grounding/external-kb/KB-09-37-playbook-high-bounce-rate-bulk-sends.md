# Playbook: High Bounce Rate on Bulk Sends

## Overview
A high bounce rate on a bulk campaign is a critical technical failure that threatens your immediate ability to reach the inbox. Mailbox providers (ISPs) view high bounce rates—especially `5.1.1 User Unknown` errors—as a definitive signal that a sender is using stale, purchased, or harvested data.

## Symptoms
- **ESP Suspension:** Your email service provider (e.g., SendGrid, Mailchimp) automatically pauses your campaign.
- **High 5.x.x Rates:** Your delivery logs show a hard bounce rate exceeding **1%** globally or **5%** for a specific ISP.
- **Log Signals:** 
  - `550 5.1.1 User Unknown`
  - `550 5.1.0 Address rejected`
  - `550 5.2.1 Mailbox disabled`
- **MTA Throttling:** ISPs begin issuing `421 4.7.0` codes (rate-limiting) as a reaction to your high failure rate.

## Root Cause Analysis
1.  **Stale Data:** You are mailing a segment that has not been touched in 6+ months, and 10-20% of the addresses have since been deactivated (see `KB-05-19`).
2.  **Point-of-Entry Failure:** Your signup form is being targeted by "bot signups" or is allowing typo domains (e.g., `user@gamil.co`) without validation.
3.  **List Source Contamination:** A recent list import from a partner or a "co-registration" source contains low-quality or non-permissioned data.
4.  **Suppression Failure:** Your MTA or ESP is failing to honor previous hard bounces, attempting to mail the same invalid addresses repeatedly.

## Step-by-Step Fix

### 1. Immediate Halt and Log Audit
- Stop all active campaigns to prevent further reputation damage.
- Export your bounce logs and filter by SMTP code. Identify if the bounces are concentrated in a specific **List Source** or **ISP**.

### 2. Isolate the "Toxic" Segment
- If the bounces are concentrated in a new import, **suppress the entire import immediately.**
- If the bounces are across your whole list, identify the "Last Engagement Date" for the bouncing addresses. You will likely find they haven't opened an email in 180+ days.

### 3. Verification Scrub
- Export your unengaged segment (no opens in 90 days) and run it through a professional verification service (e.g., Kickbox, ZeroBounce).
- **Hard Rule:** Permanently suppress any address returned as "Undeliverable" or "Invalid."

### 4. Suppression List Reconciliation
- Verify that your "Master Suppression List" is correctly loaded into your sending infrastructure. 
- Ensure your MTA is configured to automatically suppress any address that returns a `5.x.x` code on the first attempt.

### 5. The "Recovery Send"
- Resume sending **only** to users who have opened/clicked in the last 30 days. 
- Monitor your bounce rate for the first 5,000 emails. It should be below **0.1%**.

## Prevention
- **Real-Time Validation:** Integrate a validation API into all lead-capture forms to stop typos and fake addresses at the source.
- **Double Opt-In (DOI):** Implement a confirmation email for every new signup. This ensures the mailbox exists and the user has access.
- **Automated Sunsetting:** Set a hard rule to move subscribers to a "Sunset" segment after 180 days of zero engagement.
- **Bounce Honor:** Regularly audit your database to ensure that "Hard Bounced" status is synchronized across your CRM, your Marketing Automation tool, and your MTA.
