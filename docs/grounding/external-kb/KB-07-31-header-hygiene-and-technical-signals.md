# Header Hygiene and Technical Signals

## Overview

Email headers are the technical "metadata" of an email. While the body of the email is for the human recipient, the headers are for the mailbox providers (ISPs) and their filtering systems. Headers contain the history of the email's journey, the results of authentication checks, and technical "trust" signals that ISPs use to determine where to place the message.

"Header hygiene" refers to the practice of ensuring that all email headers are syntactically correct, follow RFC 5322 standards, and do not contain contradictory or suspicious information. Poor header hygiene is a common cause of deliverability failure for senders who build their own MTAs (Mail Transfer Agents) or use low-quality sending platforms.

## The Most Critical Technical Headers

ISPs scan specific headers to verify the sender's identity and determine the message's legitimacy:

### 1. The `From:` Header vs. Envelope Sender (`MAIL FROM`)
One of the most common causes of filtering is a mismatch between the "Visible From" (the address the user sees) and the "Return-Path" (the address used in the `MAIL FROM` SMTP command).
- **Alignment Rule:** While not strictly required by RFCs, most modern filters (and the DMARC protocol) expect these domains to align. If the user sees `marketing@brand.com` but the Return-Path is `bounce@otherdomain.com`, the message is flagged as "high risk" for phishing.
- **DMARC Signal:** Alignment failure results in `DMARC: fail`, which often leads to spam folder placement or rejection.

### 2. `List-Unsubscribe` (The Bulk Sender Badge)
Bulk senders **must** include this header to signal to ISPs that they follow best practices.
- **Function:** It allows the ISP to provide an "Unsubscribe" button directly in the inbox interface (separate from the body of the email).
- **Requirement:** Modern standards (RFC 8058) require a "one-click" unsubscribe mechanism using `List-Unsubscribe-Post: List-Unsubscribe=One-Click`.
- **Filtering Impact:** Absence of this header at high volume (Gmail/Yahoo) is a primary trigger for "Promotions" or "Spam" placement.

### 3. `Message-ID`
Every email must have a globally unique `Message-ID`.
- **RFC Standard:** A valid ID follows the format `<random-string@sending-domain.com>`. 
- **The Signal:** Low-quality spam bots often omit this header or use generic IDs like `12345@localhost`. A missing or malformed `Message-ID` is an immediate "invalid sender" signal.

## Metadata That "Leaks" Infrastructure Secrets

Headers often contain traces of your internal infrastructure that can inadvertently damage your reputation:

### 1. The `Received:` Header Chain
This header records every server the email touched.
- **The Risk:** If your internal network uses non-RFC compliant hostnames (e.g., `web-server-01.local`) or leaks internal IP addresses (e.g., `10.0.0.x`), ISPs may flag the message as originating from an unauthenticated or "unprofessional" source.
- **Best Practice:** Professional MTAs should "clean" or "anonymize" internal `Received:` headers before relaying the message to the internet.

### 2. `X-Mailer` and `User-Agent`
These headers identify the software used to send the email (e.g., `X-Mailer: Microsoft Outlook 16.0`).
- **The Risk:** Many legacy spam filters assign higher scores to emails sent from "suspicious" software or generic scripts (e.g., `phpmailer` or `python-requests`). If you are using a custom script, it is often better to omit the `X-Mailer` header entirely.

### 3. `X-Report-Abuse`
This is a "proactive trust" header that tells ISPs and users how to report spam directly to you.
- **Value:** Including `X-Report-Abuse: abuse@yourdomain.com` signals that you are a responsible sender with a dedicated abuse department.

## Technical Headers Produced by the Receiver

When troubleshooting, you must look at the headers **added by the receiving ISP.** These headers tell you exactly why your email was filtered:

### 1. `Authentication-Results`
This is the single most important diagnostic header. It reveals the ISP's verdict on your technical setup:
```
Authentication-Results: mx.google.com;
       spf=pass (google.com: domain of bounce@brand.com designates 1.2.3.4 as permitted sender)
       dkim=pass header.i=@brand.com;
       dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=brand.com
```
- **Action:** If any of these show `fail`, your deliverability will be impacted regardless of your content.

### 2. `X-Forefront-Antispam-Report` (Microsoft 365)
Microsoft provides a detailed code in this header (the `SCL` or Spam Confidence Level score).
- **SCL: 1-4:** Not spam.
- **SCL: 5-6:** "Suspected" spam (likely filtered).
- **SCL: 9:** "High confidence" spam (immediately quarantined or rejected).

## Summary: Header "Must-Haves" for High Deliverability

| Header | Required For | Technical Value |
| :--- | :--- | :--- |
| **`Date`** | RFC Compliance | Prevents "replay" attacks; if missing, message is rejected. |
| **`From`** | Authentication | Must align with DKIM/SPF domains for DMARC success. |
| **`Subject`** | Engagement | Must not contain ALL-CAPS or deceptive prefixes (like `Re: `). |
| **`List-Unsubscribe`** | Bulk Senders | One-click required by Gmail/Yahoo in 2024+. |
| **`Precedence: bulk`** | ISPs | Tells the ISP the message is commercial, reducing its "urgency" score. |

## Key Takeaways

- **Headers are the "trust" layer:** Malformed headers are a high-confidence signal for low-quality or automated spam bots.
- **Alignment is essential:** Ensure your "Visible From" and "Envelope From" (Return-Path) domains are identical or subdomains of the same parent.
- **Monitor the `Authentication-Results` header:** Use it as your primary diagnostic tool when emails go to spam.
- **Clean your `Received` headers:** Do not leak internal IP addresses or non-public hostnames to the internet.
- **One-click unsubscribe is mandatory:** If you send bulk mail, you must use the `List-Unsubscribe` and `List-Unsubscribe-Post` headers to avoid being blocked by Gmail and Yahoo.
