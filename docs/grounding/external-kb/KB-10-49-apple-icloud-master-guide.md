# Apple iCloud Master Guide

## Overview

Apple iCloud Mail (@icloud.com, @me.com, @mac.com) is a unique and often opaque environment for deliverability. Apple utilizes **Proofpoint** as its primary security gateway and filtering service. Consequently, deliverability success at Apple is a function of your reputation with Proofpoint's Dynamic Reputation (PDR) system and your adherence to Apple's "Local Policy" standards.

Apple provides no public dashboard and no traditional feedback loop (FBL). Success is measured by the stability of click-through rates and the absence of `550` errors containing internal policy tags like `[CS01]` or `[HME1]`.

## The Proofpoint Filtering Layer

Most rejections from Apple are actually Proofpoint-driven. Understanding the interaction between Apple's SMTP gateway and Proofpoint is the key to remediation.

### 1. Proofpoint Dynamic Reputation (PDR)
Proofpoint assigns a real-time reputation score to every sending IP.
- **Low Reputation:** Results in `421 4.7.0` deferrals (throttling) as Proofpoint evaluates your traffic patterns.
- **Critical Reputation Failure:** Results in `550 5.7.0` blocks with a URL pointing to `support.proofpoint.com`.

### 2. Proofpoint-Specific Diagnostic Tags
Apple appends bracketed codes to its `550` and `554` rejections. These are direct signals from the Proofpoint engine:

| Code | Meaning | Probable Root Cause |
| :--- | :--- | :--- |
| **`[CS01]`** | **Content-Based Block** | URLs in the body, "spammy" keywords, or attachment signatures. |
| **`[CS02]`** | **Domain Reputation Block** | The domain itself has a poor history with Proofpoint, regardless of IP. |
| **`[HME1]`** | **Authentication Failure** | The message failed **both** SPF and DKIM. Apple requires at least one to pass. |
| **`[HM08]`** | **Infrastructure Block** | Your MTA is deemed to be violating high-volume best practices. |

---

## 2024-2025 Mandatory Technical Requirements

### 1. Mandatory Triple-Authentication
- **SPF and DKIM:** Must be valid for every message. Apple is a "standards-first" receiver and heavily penalizes unauthenticated mail.
- **DMARC:** A DMARC record is mandatory. Apple increasingly expects `p=quarantine` or `p=reject` for bulk senders.
- **Alignment:** Visible `From:` MUST align with DKIM or SPF domains.

### 2. Infrastructure Standards
- **Reverse DNS (PTR):** Non-negotiable. PTR MUST match the HELO string. Proofpoint often ignores delisting requests if the PTR is missing or generic (e.g., `ec2-1-2-3-4.aws.com`).
- **Mandatory TLS:** Apple requires TLS for all inbound sessions. Failure to negotiate STARTTLS results in immediate rejection.

---

## Mail Privacy Protection (MPP): Strategic Impact

MPP pre-fetches all remote content, including tracking pixels, immediately upon delivery.

### The Impact
- **Inflated Opens:** Open rates for Apple users approach 100%. 
- **The Filter Signal:** Apple's internal filter (integrated with Proofpoint) knows the difference between a "machine open" and a "human open." Senders do not.
- **Action:** Ignore opens for Apple segments. Use **Click-to-Open (CTOR)** and **Downstream Conversions** as your only reliable reputation signals.

## Troubleshooting and Remediation

Because there is no dashboard, troubleshooting at Apple requires a "Proofpoint-First" approach.

### Step 1: Check Proofpoint IP Reputation
If you see `550` or `421` errors, immediately check your IP at:
**[https://ipcheck.proofpoint.com/](https://ipcheck.proofpoint.com/)**
- If blocked, submit a delisting request. Proofpoint is generally responsive if your technical foundation (PTR/SPF) is correct.

### Step 2: Content Isolation (For [CS01] Errors)
If your IP is clean but you see `[CS01]` blocks:
- Send a plain-text version of the email with no links.
- If it delivers, the block was triggered by a URL or a specific link-shortener domain in your HTML.

### Step 3: Mitigation Support
If you are 100% compliant and the Proofpoint tool shows no block, email **`icloudadmin@apple.com`**. 
- **Required Info:** Sending IPs, exact SMTP error strings with timestamps, and full headers of a rejected message.

## Key Takeaways

- **Proofpoint is the Guardian:** Your reputation with Apple is your reputation with Proofpoint.
- **PDR is the Source of Truth:** Use the Proofpoint IP Check tool as your primary diagnostic.
- **Reverse DNS is Mandatory:** Proofpoint will not delist IPs without valid, non-generic PTR records.
- **Engagement is "Clicks-Only":** Due to MPP, opens are a false signal. Rely on clicks for list hygiene.
- **[HME1] is a Hard Fail:** If you see this, your authentication is broken. Fix SPF/DKIM before sending another message.
