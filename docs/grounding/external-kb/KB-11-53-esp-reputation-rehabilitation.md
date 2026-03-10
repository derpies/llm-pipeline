# ESP Reputation Rehabilitation: Recovery and Strike Systems

## Overview

When an account's sender reputation is damaged—indicated by high complaint rates, low engagement, or persistent blocklisting—it requires immediate and intentional intervention. Because the platform uses shared IP pools, a single account's bad behavior can jeopardize delivery for thousands of others. 

The platform manages this risk through an automated "Strike System" for enforcement and a structured "4-Week Rehabilitation" protocol for recovery. This article details the thresholds for these systems and the technical path to restoration.

---

## The Internal Strike System

The platform monitors every account's delivery performance in real-time. If an account's behavior exceeds safety thresholds, a "strike" is recorded.

### Thresholds for Enforcement
1.  **Complaint Rate (Spam Reports):** The most critical metric.
    - **ISP Hard Limit:** Google and Yahoo enforce a **0.3%** absolute limit. Exceeding this often leads to immediate and permanent rejection of mail.
    - **Platform Strike Threshold:** Any account exceeding **0.1%** (1 complaint per 1,000 emails) is subject to an automated strike.
2.  **Hard Bounce Rate:** Indicates poor list hygiene or purchased lists.
    - **Platform Strike Threshold:** Consistently exceeding **5%** on bulk sends.
3.  **Authentication Failures:** Sending large volumes without SPF/DKIM/DMARC compliance.

### Consequences of Strikes
- **Tier 1:** Automated warning notification sent to the account owner.
- **Tier 2:** Temporary throttling of outbound volume (lower send speed).
- **Tier 3:** Mandatory move to an `ISO*` isolation pool (Penalty Box), effectively separating the account's reputation from the shared pools.
- **Tier 4:** Full suspension of sending privileges pending manual review by the Deliverability Operations team.

---

## The 4-Week Rehabilitation Protocol

Rehabilitating a damaged sender reputation is similar to "warming up" a new domain, but with higher scrutiny. The goal is to prove to ISPs that the sender has cleaned their list and is now only sending high-value content to engaged recipients.

### The Rehabilitation Cadence
During the 4-week recovery period, the account must adhere to a strict engagement-to-send ratio.

| Week | 0–30 Day Engagement | 31–60 Day Engagement | 61–90 Day Engagement | 91+ Days (Unengaged) |
| :--- | :--- | :--- | :--- | :--- |
| **Week 1** | 100% | 0% | 0% | **FORBIDDEN** |
| **Week 2** | 100% | 0% | 0% | **FORBIDDEN** |
| **Week 3** | 90% | 10% | 0% | **FORBIDDEN** |
| **Week 4** | 85% | 10% | 5% | **FORBIDDEN** |

### Critical Requirements During Rehab
1.  **Pure Engagement:** The sender must only target recipients who have opened or clicked an email within the specified timeframe.
2.  **Mandatory List Cleaning:** All hard bounces must be purged, and any unengaged contacts (91+ days) must be suppressed immediately.
3.  **Authentication Fix:** All SPF, DKIM, and DMARC records must be verified and fully compliant before rehab begins.
4.  **Content Audit:** Content must be audited to ensure it is relevant, contains a clear "List-Unsubscribe" header, and avoids "spammy" formatting (all-caps, excessive links, etc.).

---

## Monitoring Restoration

Success is measured by improvements in technical signals rather than just "getting the email delivered."

- **Inbox Placement:** Verified through seed testing.
- **Complaint Reduction:** Staying below the 0.05% mark for the duration of rehab.
- **Provider Sentiment:** Monitoring for the removal of "backoff" requests (421/451 deferrals) and "suspected spam" rejections (550).

If the account successfully completes the 4-week protocol without a new strike, it may be eligible to transition back to the standard shared engagement pools (`SEG_E_*`).

---

## Key Takeaways

- **Reputation damage is cumulative:** The longer it is ignored, the harder it is to repair.
- **0.1% is the danger zone:** This is the platform's internal strike threshold for complaints.
- **Rehab is engagement-driven:** Recovery depends entirely on sending ONLY to contacts who have recently engaged (0–30 days).
- **Isolation is the penalty:** Frequent offenders are moved to `ISO*` pools to protect the platform's overall IP reputation.
- **Authentication is non-negotiable:** No reputation repair can succeed if the email is not properly authenticated.
