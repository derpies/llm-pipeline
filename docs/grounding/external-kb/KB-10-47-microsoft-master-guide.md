# Microsoft Master Guide (Outlook, Hotmail, O365)

## Overview

Microsoft's email ecosystem is arguably the most complex for deliverability engineers due to its fragmentation between consumer services (Outlook.com, Hotmail, Live, MSN) and enterprise services (Microsoft 365 / Exchange Online). While both share the same underlying "SmartScreen" filtering engine, their reputation models and troubleshooting paths are distinct.

The core of Microsoft's strategy is **IP-centric reputation** and **aggressive connection-level blocking.** Unlike Gmail, which focuses heavily on the domain, Microsoft will frequently block entire subnets if a "bad neighborhood" of IPs is detected.

## Technical Mandates and Limits

### 1. Mandatory Authentication
Microsoft 365 and consumer Outlook.com enforce strict SPF, DKIM, and DMARC checks. 
- **Requirement:** SPF and DKIM are baseline requirements.
- **DMARC:** Microsoft honors `p=reject` and `p=quarantine` policies. If a message fails both SPF and DKIM alignment, it will be rejected with a `550 5.7.1` error.
- **PTR Record:** Every sending IP **must** have a valid Reverse DNS (PTR) record that matches the HELO/EHLO hostname. Missing or generic PTRs (e.g., `1-2-3-4.isp.com`) are common triggers for the `S3150` block.

### 2. Connection and Message Limits (EOP)
For Microsoft 365 (Enterprise), Exchange Online Protection (EOP) enforces these non-configurable limits:
- **Maximum Concurrent Connections:** Exceeding this triggers `421 4.3.2`.
- **Recipient Limits:** Recommended maximum of **500 recipients** per SMTP transaction to avoid being flagged as bulk/spam.
- **Message Size:** Hard limit of **150 MB** (including attachments).

---

## Technical Reference: Exhaustive NDR Code Catalog

Microsoft uses Enhanced Status Codes (ESC) to provide specific failure diagnostics in Non-Delivery Reports (NDRs).

### 5.1.x: Recipient & Address Errors (Permanent)
| Code | Meaning | Common Cause / Remediation |
| :--- | :--- | :--- |
| **5.1.0** | **Sender Denied** | General resolution failure or explicit block by recipient. |
| **5.1.1** | **Recipient Not Found** | Address does not exist. Remove from list immediately. |
| **5.1.8** | **Bad Outbound Sender** | **Account Compromise:** Your O365 account is blocked for spamming. |
| **5.1.10** | **Recipient Not Found (Internal)** | Hybrid setup failure; domain is accepted but mailbox is missing. |
| **5.1.20** | **Multiple From Addresses** | Violates SMTP standards; message lacks a single "Sender" header. |

### 5.4.x: Routing & Network Errors (Permanent)
| Code | Meaning | Common Cause / Remediation |
| :--- | :--- | :--- |
| **5.4.1** | **Access Denied (DBEB)** | Directory Based Edge Blocking; address is not in recipient's directory. |
| **5.4.4** | **DNS Issue** | Sending server could not find MX records for destination. |
| **5.4.14** | **Hop Count Exceeded** | **Mail Loop:** Message routed back and forth > 20 times. |
| **5.4.316** | **Connection Refused** | Destination server actively refused the session. |

### 5.7.x: Security & Policy Errors (Permanent)
| Code | Meaning | Common Cause / Remediation |
| :--- | :--- | :--- |
| **5.7.1** | **Access Denied** | General permission failure. Often an S3140 or S3150 block. |
| **5.7.23** | **SPF Validation Failed** | Your SPF record does not include the sending IP. |
| **5.7.500** | **Suspicious Activity** | Content or IP flagged as highly spammy. |
| **5.7.515** | **Auth Level (Outlook.com)** | Sending domain fails required SPF/DKIM/DMARC levels. |
| **5.7.705** | **Tenant Exceeded Threshold** | Entire O365 tenant is blocked due to high spam volume. |
| **5.7.708** | **IP Reputation Block** | Sending IP has a critically low reputation. |

### Microsoft-Specific "S" Codes (Diagnostic Strings)
| Code | Meaning | Remediation |
| :--- | :--- | :--- |
| **`S3140`** | **Reputation Block** | History of high complaints/traps. Check SNDS. |
| **`S3150`** | **Policy Block** | New IP, no PTR, or sudden volume spike. Slow down. |

---

## Cloudmark CSI and AUP Codes

Microsoft utilizes **Cloudmark Sender Intelligence (CSI)** as its primary IP reputation gateway. If CSI flags your IP, the connection is rejected before it reaches the SCL evaluation layer.

### Cloudmark AUP (Acceptable Use Policy) Codes
Found in SMTP bounce strings:
- **`AUP#BL`**: IP is on the Cloudmark Blacklist due to high spam volume or trap hits.
- **`AUP#In`**: Insecure behavior detected (e.g., open relay or malware-infected host).
- **`AUP#Out`**: Outbound spamming patterns detected from the IP.

### Remediation Path
Check your IP status at the [Cloudmark CSI Reset Portal](https://csi.cloudmark.com/en/reset/). If listed, submit a "Reset Request." A valid PTR record is usually required for a successful reset.

---

## Decoding Microsoft Diagnostic Headers

Microsoft provides granular filtering data via `X-MS-Exchange-Organization-` headers.

### 1. X-Forefront-Antispam-Report
This is the most critical diagnostic header. Key fields:
- **SCL (Spam Confidence Level)**: `-1` (Bypassed), `0-1` (Clean), `5-6` (Spam), `9` (High Confidence Spam).
- **SFV (Spam Filtering Verdict)**: `NSPM` (Not Spam), `SPM` (Filtered as Spam), `BLK` (Blocked by Blocklist).
- **IPV (IP Verdict)**: `CAL` (High Reputation), `LIM` (Limited/Poor Reputation), `NLI` (Not Listed).

### 2. X-Microsoft-Antispam
- **BCL (Bulk Complaint Level)**: Measures reputation of marketing traffic (0-9). A BCL ≥ 7 typically triggers a spam verdict.
- **PCL (Phish Confidence Level)**: Likelihood of phishing (0-8). A PCL of 9 is high-confidence phishing.


---

## Mastering SNDS and JMRP

### 1. SNDS (Smart Network Data Services)
- **Color Coding:** Green (Good), Yellow (Warning), Red (Critical).
- **Spam Trap Hits:** Explicitly reports the number of traps hit by the IP.
- **Data Freshness:** 24–48 hour delay.

### 2. JMRP (Junk Mail Reporting Program)
- **Action:** **MUST** remove every user who generates a report. 
- **Impact:** Ignoring JMRP is the fastest way to turn an IP "Red" in SNDS.

## Mitigation and Support

If blocked (`S3140`/`S3150`), use the [Microsoft Sender Support Request](https://olcsupport.office.com/).
1.  **Preparation:** Must be enrolled in SNDS and JMRP first.
2.  **Outcome:** May receive a "Conditional Mitigation" (mail flows to Junk while reputation rebuilds).

## Key Takeaways

- **IP Reputation is King:** Microsoft blocks subnets and IPs more than domains.
- **SCL is your primary diagnostic:** Check headers to see why mail hit the Junk folder.
- **Don't ignore the S3150:** Most common for new senders. Follow 30-day warm-up.
- **JMRP is mandatory:** Process complaints or face permanent blocking.
- **Watch for "Silent Discards":** If SNDS is "Green" but engagement is zero, file a support ticket.
