# Log Forensic Reference: Parsing XMRID and ClickTrackingID

## Overview

For deliverability engineers and data analysts, the platform's raw email logs are the ultimate source of truth. While top-level fields like `status`, `recipient`, and `outmtaid_ip` provide immediate context, the deepest diagnostic signals are often buried within delimited string fields. 

This article provides a technical reference for parsing and interpreting the two most critical metadata fields: `clicktrackingid` and `XMRID`. Understanding these fields is essential for attribution, compliance tracking, and identifying the root cause of deliverability anomalies.

---

## The `clicktrackingid` Field

The `clicktrackingid` is a semicolon-delimited string (`component1;component2;...`) containing 6 distinct sub-fields. It encodes the subscriber's state and the message's intent at the exact moment the email was generated.

| Index | Field Name | Description | Diagnostic Use |
| :--- | :--- | :--- | :--- |
| 0 | **XMRID** | A dot-delimited composite ID (see below). | Primary key for joining to external systems. |
| 1 | **Last-Active** | Unix timestamp of the contact's last confirmed engagement. | Verifies if the `listid` (segment) assignment was correct. |
| 2 | **Contact-Added** | Unix timestamp of when the contact was added to the account. | Identifies "new contact" spikes that might trigger spam filters. |
| 3 | **OP-Queue-Time**| Unix timestamp of when the message was scheduled for sending. | Used to calculate "Pre-Edge Latency" (Upstream delays). |
| 4 | **OP-Queue-ID** | An opaque internal identifier for the scheduling job. | Useful for grouping all messages from a single batch send. |
| 5 | **Marketing Flag**| Boolean integer: `0` = Transactional, `1` = Marketing. | Essential for separating high-priority system mail from bulk sends. |

### Handling Zero Values (`0`)
A value of `0` in any timestamp field indicates that the data was unavailable at the time of email creation. 
- **Last-Active = 0:** The system applies a safety default: `Contact-Added + 15 days`. This ensures unknown contacts are routed to medium-tier pools (`SEG_E_UK`) rather than pristine IPs.
- **Data Completeness:** Monitoring the ratio of `0` values in these fields is a key metric for system health. High "zero-rate" indicates a breakdown in the data pipeline between the CRM and the Mailer.

---

## The `XMRID` Composite ID

Nested as the first component of the `clicktrackingid`, the `XMRID` is a dot-delimited string (`val1.val2.val3.val4.val5.val6.val7`) that identifies the specific entities involved in the send.

### Parsing Structure
1. **Object ID:** Internal system object type.
2. **Account ID:** **CRITICAL.** The unique identifier for the customer sending the email. All reputation "strikes" and compliance actions are anchored to this ID.
3. **Contact ID:** The unique identifier for the recipient in the sender's database.
4. **Log ID:** Unique ID for this specific delivery attempt record.
5. **Message ID:** Identifier for the content template used.
6. **Drip ID:** The ID of the automation sequence (0 if manual/bulk).
7. **Step ID:** The specific step within the automation sequence (0 if manual/bulk).

### Forensic Value
By grouping failures by **Account ID** across different **IP Pools** (`listid`), you can determine if a deliverability drop is caused by a single bad actor (one account with high failures across all pools) or an infrastructure-wide issue (many accounts failing on one specific IP).

---

## The Timing Chain: Detecting Latency

Logs contain three timestamps that allow you to reconstruct the message's journey and identify where delays are occurring.

1.  **Scheduling Time:** `OP-Queue-Time` (from `clicktrackingid` index 3).
2.  **Edge Arrival:** `injected_time` (top-level log field).
3.  **Delivery Result:** `timestamp` (top-level log field).

### Calculating Latency
- **Pre-Edge Latency (`injected_time` - `OP-Queue-Time`):** Delays within the platform's internal queues, database contention, or processing overhead.
- **Delivery Latency (`timestamp` - `injected_time`):** External delays. 
    - **< 2 seconds:** Normal, direct SMTP handoff.
    - **Minutes to Hours:** Indicates the recipient server is deferring (rate-limiting) the mail, and the platform is retrying.

---

## Compliance & Authentication Signals

The `headers.x-op-mail-domains` field reveals the authentication state at the moment of handoff.

- **Compliant Pattern:** `compliant-from:domain.com; compliant-mailfrom:domain.com;`
    - The email was sent using the client's own domain. 
    - Full SPF/DKIM/DMARC alignment is possible.
- **Non-Compliant Pattern:** `no-compliant-check: ontramail or opmailer`
    - The client has not configured their DNS correctly.
    - The platform "rewrites" the sender to a shared platform domain.
    - **Risk:** These senders are high-risk for shared pools and are often the first to be throttled by ISPs like Gmail.

---

## Key Takeaways

- **`clicktrackingid` is the diagnostic map:** Use it to extract the Marketing Flag and Last-Active status for every send.
- **Account ID is the anchor:** Always attribute deliverability metrics to the `Account ID` from the XMRID to isolate bad actors.
- **Watch the zeros:** High rates of `0` values in timestamps indicate a failure in the data enrichment pipeline.
- **Latency reveals the "Who":** Internal delays (Pre-Edge) are the platform's problem; external delays (Delivery Latency) are reputation or ISP-side problems.
- **Authentication state is logged:** Use `x-op-mail-domains` to verify if a failing account was even properly authenticated.
