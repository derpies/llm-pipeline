# Playbook: Authentication Failures

## Overview
Authentication failures—SPF, DKIM, or DMARC—are binary technical issues that directly lead to inbox placement failure or total rejection by major ISPs like Gmail and Yahoo. With the 2024 Bulk Sender mandates, "correct" authentication is no longer optional; it is a mandatory gate for any high-volume sender.

## Symptoms
- **Spam Placement:** All mail goes to the spam folder, even for highly engaged users.
- **Log Signals:** 
  - `550 5.7.26 ... message does not have authentication information or fails to pass authentication checks.` (Gmail)
  - `550 5.7.1 ... message rejected due to DMARC policy.`
- **Diagnostic Header:** The `Authentication-Results` header shows `spf=fail`, `dkim=fail`, or `dmarc=fail`.

## Root Cause Analysis
1.  **Broken DKIM Signature:** Your signing server (MTA) is misconfigured and produces invalid cryptographic hashes.
2.  **SPF "Permerror" (Too Many DNS Lookups):** Your SPF record contains more than 10 DNS lookups (common when using multiple third-party tools like Zendesk, Mailchimp, and Salesforce).
3.  **DMARC Alignment Failure:** Your `MAIL FROM` domain (SPF) or your `DKIM-Signature` domain does not match your visible `From:` domain.
4.  **Inadvertent DNS Change:** An IT "cleanup" recently deleted a TXT record or invalidated a DKIM selector.
5.  **DKIM Key Rotation Failure:** You generated new keys but did not update the DNS record, or vice versa.

## Step-by-Step Fix

### 1. Identify the Failure Point
Send a test email to a tool like `mail-tester.com` or `dkimvalidator.com`.
- Check if **SPF** shows `none`, `softfail`, `fail`, or `permerror`.
- Check if **DKIM** shows `fail` (invalid signature) or `none` (missing signature).
- Check if **DMARC** shows `fail` due to alignment.

### 2. Fix SPF Errors
- **If SPF is missing:** Add a TXT record: `v=spf1 ip4:[your-ip] include:[provider-domain] -all`.
- **If SPF has >10 lookups:** Use "SPF Flattening" to convert your record into a single list of IP addresses, or consolidate your sending tools.

### 3. Fix DKIM Failures
- **Verify DNS Record:** Ensure the public key at `[selector]._domainkey.example.com` matches the private key in your MTA.
- **Check for "Body Modification":** Some MTAs or spam scanners modify the body of an email after it is signed, which breaks the DKIM hash. Disable any automatic "disclaimer" footers that modify the body post-signing.

### 4. Fix DMARC Alignment
- **Ensure Alignment:** Match your Visible From domain to your DKIM or SPF domain. 
  - If you send from `marketing@brand.com`, your DKIM signature must use `d=brand.com`. 
  - If you use a subdomain (e.g., `bounce.brand.com`) for SPF, this is acceptable as "relaxed alignment."

### 5. Verify the Propagation
Run `dig TXT example.com` and `dig TXT [selector]._domainkey.example.com` to confirm that the changes are visible to the public internet.

## Prevention
- **DMARC Monitoring (RUA/RUF):** Use a service (like dmarcian or Postmark) to monitor your RUA reports daily. This is the only way to catch "shadow IT" or authentication "breaks" before they become a deliverability crisis.
- **DKIM Key Management:** Store your DKIM keys in a version-controlled system. Implement a 12-month rotation schedule with a 24-hour "overlap" period where both old and new keys are active.
- **DNS Change Control:** Implement a "change request" process for your DNS. Never allow non-technical staff to modify SPF or DKIM records.
- **Test Before Senders:** Include a "Seed Test" (see `KB-08-35`) in your pre-deployment checklist for every major campaign to verify that authentication remains intact.
