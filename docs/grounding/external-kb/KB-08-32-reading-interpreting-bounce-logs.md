# Reading and Interpreting Bounce Logs

## Overview

Bounce logs are the most direct and reliable technical signal in the email delivery ecosystem. While dashboard metrics provide a "high-level" view, your MTA (Mail Transfer Agent) logs contain the raw, real-time responses from receiving servers. To a deliverability engineer, these logs are the "forensics" that tell you exactly why a message failed.

This article details how to extract meaning from the unstructured text of bounce logs. You will learn to distinguish between permanent and temporary failures, identify ISP-specific policy blocks, and recognize patterns that indicate systemic reputation issues versus individual mailbox errors.

## The Anatomy of an SMTP Log Entry

A typical bounce entry in a professional MTA (like Postfix, PowerMTA, or Sendmail) contains several key fields. Understanding these fields is the first step in diagnosis:

```text
Feb 20 14:15:02 mta-01 postfix/smtp[1234]: 5C3A21F4: to=<user@example.com>, 
relay=mx1.example.com[192.0.2.1]:25, delay=0.5, delays=0.1/0.01/0.2/0.19, 
dsn=5.1.1, status=bounced (host mx1.example.com[192.0.2.1] said: 
550 5.1.1 The email account that you tried to reach does not exist. 
Please try double-checking the recipient's email address for typos or 
unnecessary spaces. [mx-id-123] (in reply to RCPT TO command))
```

### Key Components to Parse:
1.  **`dsn=` (Delivery Status Notification):** The standardized code (RFC 3463). `5.x.x` is permanent; `4.x.x` is temporary.
2.  **`status=`:** High-level result (e.g., `sent`, `deferred`, `bounced`).
3.  **`relay=`:** The specific IP and hostname of the receiving server. This tells you *which* ISP is rejecting your mail.
4.  **`said:` (The SMTP Response):** The literal text returned by the receiver. This often contains the most specific diagnostic information.
5.  **`in reply to:`:** The SMTP command that triggered the failure (e.g., `RCPT TO`, `DATA`, `EHLO`).

## Decoding the DSN and SMTP Code Matrix

The combination of the 3-digit SMTP code and the 3-digit Enhanced Status Code (DSN) provides a "coordinate system" for the error.

| DSN | SMTP Code | Category | Interpretation |
| :--- | :--- | :--- | :--- |
| **`5.1.1`** | `550` | **Hard Bounce** | User unknown. The mailbox has been deleted or never existed. |
| **`5.7.1`** | `550` | **Policy/Reputation** | Blocked by a filter. This is a "reputation" block, not a content block. |
| **`4.2.1`** | `451` | **Greylisting** | Temporary deferral. The receiver is testing if you are a legitimate MTA that retries. |
| **`4.2.2`** | `452` | **Mailbox Full** | The recipient's inbox is at capacity. This is a soft bounce. |
| **`5.3.4`** | `552` | **Message Size** | Your email (including attachments) exceeds the receiver's limit. |
| **`4.7.0`** | `421` | **Throttling** | "Too many connections" or "Rate limit exceeded." Slow down your send. |

## Extracting Meaning from Diagnostic Strings

Many ISPs include "proprietary" text or URLs in their bounce strings. These are the most valuable clues for remediation.

### 1. Reputation and Blocklist Indicators
- **Spamhaus:** `554 5.7.1 Service unavailable; Client host [IP] blocked using sbl.spamhaus.org`
- **Microsoft S3150:** `550 5.7.1 ... part of their network is on our block list (S3150)`
- **Gmail Unsolicited:** `550 5.7.1 ... detected that this message is likely unsolicited mail.`

### 2. Authentication Failures
- **DKIM/SPF:** `550 5.7.26 ... message does not have authentication information or fails to pass authentication checks.`
- **DMARC:** `550 5.7.1 ... message rejected due to DMARC policy.`

### 3. ISP-Specific "Throttle" Codes
- **Yahoo `[TS01]`:** `421 4.7.0 [TS01] ... deferred due to user complaints.`
- **Microsoft `[4.7.0]`:** `451 4.7.0 ... Too many connections from your IP.`

## Log Analysis Workflows: Pattern Recognition

To find the root cause, you must look for **clusters** in your logs.

### Scenario A: The "Domain Spike"
- **Pattern:** You see a 50% bounce rate at `@yahoo.com` but a 0.2% bounce rate at `@gmail.com`.
- **Diagnosis:** This is an ISP-specific reputation issue. Check your Yahoo CFL (Feedback Loop) and check if your IP is throttled at Yahoo.

### Scenario B: The "Universal Bounce"
- **Pattern:** You see `5.7.1` policy rejections across *all* major domains (Gmail, Yahoo, Microsoft) simultaneously.
- **Diagnosis:** Your **sending domain** has been blocklisted (e.g., Spamhaus DBL) or your authentication (DKIM) has broken for all messages.

### Scenario C: The "Connection Timeouts"
- **Pattern:** Logs show `status=deferred (connect to mx.example.com: Connection timed out)`.
- **Diagnosis:** This is an infrastructure or networking issue. Your firewall may be blocking port 25, or your IP's PTR record has been deleted.

## Practical Tooling for Log Parsing

If you are dealing with millions of log lines, manual inspection is impossible. Use these technical approaches:

1.  **Grep/Awk for Quick Triage:**
    `grep "status=bounced" /var/log/mail.log | awk -F'said: ' '{print $2}' | sort | uniq -c | sort -nr`
    *This command identifies the most common bounce reasons across your entire send.*
2.  **Regular Expression Extraction:**
    Build a parser that extracts the `dsn`, `relay`, and the first 50 characters of the `said:` string to group similar errors.
3.  **Visualization:**
    Pipe your logs into a tool like Elasticsearch/Kibana or a custom dashboard to track bounce rates by domain over time. A sudden "cliff" in the graph is a definitive signal of a block.

## Key Takeaways

- **DSN codes are your first filter:** `5.x.x` means stop; `4.x.x` means slow down and wait.
- **Group by "Relay":** Always analyze bounce reasons per destination ISP. Gmail's reason for bouncing you is rarely the same as Microsoft's.
- **Parse the text, not just the code:** The 550 code tells you "no," but the text "S3150" or "UnsolicitedMessageError" tells you "why."
- **Distinguish between Address and Reputation:** If the failure happens at `RCPT TO`, it's an address or IP block. If it happens after `DATA`, it's a content or domain reputation block.
- **Log data is the "Truth":** If your ESP dashboard says "99% delivered" but your MTA logs show `421` deferrals, you are not actually delivering mail; you are just queueing it.
