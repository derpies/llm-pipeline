# Playbook: Transactional Email Delivery Issues

## Overview
Transactional emails (password resets, purchase receipts, account notifications) are the most critical category of email. Unlike marketing emails, which can tolerate some delay, transactional emails must arrive in seconds. A deliverability failure in this category has an immediate, negative impact on business operations and user trust.

## Symptoms
- **User Complaints:** Customers report they are not receiving password resets or confirmation emails.
- **Log Signals:** 
  - `status=deferred (Connection timed out)`
  - `550 5.7.1 ... blocked by reputation`
  - `550 5.1.1 User Unknown` (indicating a bot signup)
- **Zero Engagement:** Open rates on critical transactional emails drop below 30% (unusually low for this category).
- **Tab Placement:** Transactional emails are landing in the "Promotions" tab or "Other" inbox instead of "Primary."

## Root Cause Analysis
1.  **Shared Reputation Contamination:** You are sending transactional mail from the same IP address as your bulk marketing mail. Marketing complaints are dragging down your transactional delivery.
2.  **Authentication Misalignment:** Your transactional mail is missing SPF/DKIM or is not aligned with your brand domain.
3.  **Bot Signups / List Pollution:** Malicious bots are using your signup form to send emails to third-party "spam traps," resulting in your IP being blocklisted.
4.  **Content Filter Triggers:** Your transactional templates are too long, contain too many "marketing" links, or use a "spammy" subject line (e.g., "Urgent: Action Required").
5.  **ISP-Specific Throttle:** A provider like Microsoft is throttling your connection speed, causing a backlog in your transactional queue.

## Step-by-Step Fix

### 1. Separate Infrastructure (The "Critical Path" Fix)
- **Action:** If you are currently sending both types of mail from one IP, **immediately move transactional mail to a dedicated IP or a separate sub-account.**
- **Goal:** This isolates your mission-critical mail from the reputation volatility of marketing campaigns.

### 2. Audit Authentication (The "Foundation" Fix)
- Verify that your transactional mail is 100% compliant with SPF, DKIM, and DMARC. 
- Use a unique DKIM selector specifically for your transactional mail (e.g., `trans1._domainkey.brand.com`).

### 3. Implement Rate Limiting and Queue Prioritization
- Configure your MTA (e.g., Postfix, PowerMTA) to prioritize the "Transactional Queue" over the "Marketing Queue." 
- Ensure your MTA is configured for aggressive connection rates to major ISPs for your transactional IP.

### 4. Content Audit (The "Clean Template" Fix)
- Simplify your transactional templates. Remove non-essential marketing links, social media icons, and excessive images.
- **The Rule:** A password reset email should be text-heavy and focus on a single, clear call to action.

### 5. Bot Mitigation (The "Hygiene" Fix)
- Implement CAPTCHA or invisible honeypot fields on your signup and "forgot password" forms to stop bot-driven trap hits.

## Prevention
- **Monitor the Transactional Segment Independently:** Use a unique "Mail-From" subdomain (e.g., `notif.brand.com`) so you can track its reputation separately in Google Postmaster Tools.
- **Set Alerts for Delivery Lag:** Monitor your "Average Time to Delivery" (ATTD). If it exceeds 60 seconds, trigger an alert to your infrastructure team.
- **Keep "From" Address Consistent:** Use a dedicated, recognizable address for transactional mail (e.g., `support@brand.com` or `alerts@brand.com`) and never use it for marketing.
- **Encourage "Primary" Placement:** In your signup flow, ask users to add your transactional address to their "Contacts" or "Safe Senders" list.
- **No Promotional Content:** Do not include "Recommended Products" or "Upcoming Sales" in your password reset or receipt emails. This is the #1 reason transactional mail is demoted to the Promotions tab.
