# Yahoo / AOL Master Guide

## Overview

Yahoo and AOL (collectively Yahoo Inc.) share a technical stack characterized by **real-time complaint sensitivity** and **aggressive deferrals (421 codes).** Unlike other ISPs, Yahoo uses "throttling" as its primary reactive filter, squeezing sender throughput the moment negative signals (complaints or traps) spike.

## 2024-2025 Mandatory Technical Requirements

Yahoo's requirements are technically aligned with Google's bulk sender mandates.

### 1. Mandatory Triple-Authentication
Bulk senders (5,000+ messages per day) must have:
- **SPF and DKIM:** Both must be present and valid.
- **DMARC:** Mandatory record. Policy (`p=`) can be `none`, `quarantine`, or `reject`.
- **Alignment:** Visible `From:` domain must match SPF or DKIM domains.

### 2. One-Click Unsubscribe (RFC 8058)
Marketing mail must include header-based one-click unsubscribe:
- `List-Unsubscribe: <https://example.com/unsubscribe/id>`
- `List-Unsubscribe-Post: List-Unsubscribe=One-Click`
- **Enforcement:** Missing headers trigger immediate "Spam" folder placement.

### 3. Spam Rate Thresholds
- **Requirement:** Keep spam rate below **0.1%**.
- **Critical Failure:** **0.3%** triggers systemic blocking or throttling.

---

## Technical Reference: Exhaustive SMTP Error Catalog

Yahoo uses specific alphanumeric tags (TS, BL, GL) in its SMTP responses to identify the exact cause of a deferral or rejection.

### TS Series: Temporary Deferrals (421/451)
Yahoo expects your server to retry these later.

| Code | Meaning | Remediation |
| :--- | :--- | :--- |
| **`[TS01]`** | **New/Cold IP Throttle** | Yahoo doesn't recognize your IP. Slow down volume. |
| **`[TS02]`** | **Reputation Deferral** | Sudden volume spike or dip in trust. Pause send. |
| **`[TS03]`** | **Anti-Spam Block** | Suspicious traffic patterns detected. Check for compromise. |
| **`[TSS04]`** | **Complaint Spike** | Users clicking "Spam" at an elevated rate. Audit content. |
| **`[TS06]`** | **Persistence Failure** | Issued after repeated warnings; improve list hygiene. |

### BL Series: Blacklist Rejections (553/554)
Permanent rejections based on reputation.

| Code | Meaning | Remediation |
| :--- | :--- | :--- |
| **`[BL21]`** | **Spamhaus SBL/PBL** | IP listed on Spamhaus. Resolve at spamhaus.org. |
| **`[BL23]`** | **Spamhaus XBL** | IP listed on Spamhaus Exploits (Botnet/Compromise). |
| **`[BL99]`** | **Internal Yahoo Block** | Permanent block due to extreme abuse or policy violations. |

### GL Series: General/Grey Listing (421)
| Code | Meaning | Remediation |
| :--- | :--- | :--- |
| **`[GL01]`** | **Grey Listing** | Unknown sender check. Legitimate MTAs must retry. |
| **`[GL02]`** | **General Limit** | Hit concurrent connection or hourly rate limit. |

### 55x Series: Bulk Mandate Rejections
| Code | Meaning | Remediation |
| :--- | :--- | :--- |
| **550 5.7.9** | **Auth Required** | SPF or DKIM missing. 2024 mandate violation. |
| **554 5.7.9** | **DMARC Policy** | Failed alignment under `p=reject`. |
| **554 5.7.1** | **Policy Rejection** | Catch-all for content blocks or missing RFC 8058. |
| **554 30** | **Mailbox Disabled** | Recipient inactive for 6+ months. Remove from list. |
| **`[BL99]`** | **Internal Yahoo Block** | Permanent block due to extreme abuse or policy violations. |
| **`cm-csi-v11`** | **Cloudmark CSI Block** | Rejection due to critically low Cloudmark IP reputation. |

---

## Cloudmark Authority and Content Fingerprinting

Yahoo and AOL utilize **Cloudmark Authority** (formerly CMAE) for advanced content analysis. Unlike heuristic filters that look for keywords, Cloudmark uses "fingerprinting" to identify identical message structures across the Global Threat Network (GTN).

### 1. X-Authority-Analysis Header
This header contains the Cloudmark analysis string. Parsing it reveals how the filter viewed the message:
`X-Authority-Analysis: v=2.x cv=HASH c=1 sm=1 a=FINGERPRINT:117 a=URL:17`
- **`v=`**: Version of the engine.
- **`a=`**: Fingerprints of message components (headers, body, URLs).
- **`sm=1`**: Indicates the message was identified as spam by the fingerprinting engine.

### 2. Cloudmark SMTP Error Strings
You may encounter these specific strings in Yahoo/AOL logs:
- **`554 5.7.1 ... blocked using cm-csi-v11; Cloudmark Poor Reputation`**
- **`550-"JunkMail rejected - ... is in an RBL on csi.cloudmark.com`**

---

## Mastering the Yahoo Sender Hub

### 1. Yahoo Postmaster Tools
Verify your domain via DKIM at `senders.yahooinc.com` to view your "Sender Reputation" grade and "Spam Rate" dashboard.

### 2. CFL (Complaint Feedback Loop)
- **Action:** Yahoo requires **immediate** removal of complainers.
- **Data Link:** If you receive `[TSS04]`, cross-reference your CFL data to see which campaign triggered the spike.

## Troubleshooting and Remediation

1.  **The "Slow Down" Strategy:** If you see `421` codes, **do not increase retry frequency**. Yahoo monitors persistence; aggressive retries turn a throttle into a block.
2.  **Cloudmark CSI Reset:** If logs reference `cm-csi-v11` or `csi.cloudmark.com`, check your IP status at the [Cloudmark CSI Reset Portal](https://csi.cloudmark.com/en/reset/).
3.  **Verify Alignment:** Yahoo penalizes unaligned mail (DMARC failure) more heavily than Gmail.
4.  **Support Tickets:** Use the [Yahoo Sender Support Form](https://senders.yahooinc.com/contact/) ONLY after resolving complaint spikes and fixing authentication.


## Key Takeaways

- **Respect the `TS` Codes:** They are real-time commands. Treat `TS02` as a "stop work" order.
- **Complaints are the primary driver:** Yahoo filters are sensitive to human feedback.
- **CFL is non-negotiable:** Processing feedback loop data is the only way to maintain reputation.
- **Align your authentication:** DMARC alignment is the baseline "trust" signal.
- **Watch 5.1.1 rates:** Yahoo will block you for "harvesting" if hard bounces exceed 2%.
