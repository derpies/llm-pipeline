# Email Verification and Validation

## Overview

Email verification and validation are the processes of determining whether an email address is syntactically correct, has a valid destination domain, and is currently capable of receiving mail. While these processes are essential for maintaining a high-reputation sending infrastructure, they are often misunderstood as a "cure-all" for deliverability. 

It is critical to understand that **verification is a snapshot in time.** An address that is valid today may become invalid tomorrow due to list decay. Furthermore, verification confirms "delivery" (the ability to reach the mailbox) but does not guarantee "deliverability" (the ability to reach the inbox) or "consent" (the legal and technical right to send).

## The Three Levels of Validation

Most professional validation services (e.g., Kickbox, NeverBounce, ZeroBounce) perform checks across three distinct layers:

### 1. Syntax Validation (The Format Check)
The service checks the address against RFC 5322 standards using regular expressions. This identifies obvious errors such as:
- Missing `@` symbol.
- Invalid characters (e.g., spaces, quotes, or non-ASCII characters).
- Consecutive dots (e.g., `user..name@example.com`).
- Length violations (local part > 64 chars, total address > 254 chars).

### 2. DNS/MX Validation (The Infrastructure Check)
The service queries DNS for the domain part of the email address to ensure:
- The domain exists and has a valid A or AAAA record.
- The domain has published valid MX (Mail Exchanger) records.
- The domain is not a "parking" domain that has no active mail server.

### 3. SMTP Handshaking (The Mailbox Check)
This is the most intrusive and effective check. The verification service initiates an SMTP conversation with the destination MTA:
- Connects to the MX host on port 25.
- Issues an `EHLO`.
- Issues `MAIL FROM:<check@verifiersystem.com>`.
- Issues `RCPT TO:<user@example.com>`.
- **Crucially:** If the server returns `250 OK`, the verifier issues a `QUIT` or `RSET` instead of a `DATA` command. No actual email is sent.

**Technical Note:** Many ISPs consider high-volume "pinging" of their servers for verification purposes to be a hostile act. High-quality verifiers use large, rotating IP pools and sophisticated "politeness" algorithms to avoid being blocked.

## Result Categories and How to Handle Them

Verification services typically return one of four statuses. Your bounce management logic should be configured based on these categories:

| Status | Technical Meaning | Recommended Action |
| :--- | :--- | :--- |
| **Deliverable** | Valid syntax, MX records, and SMTP `250 OK`. | Safe to send. Expect < 0.2% bounce rate. |
| **Undeliverable** | Known invalid (e.g., `5.1.1 User Unknown`). | **Suppress immediately.** Never attempt to mail these. |
| **Risky / Accept-All** | The domain is a "catch-all"—it returns `250 OK` for *every* address, whether it exists or not. | Handle with caution. These often hide high bounce rates. Only mail if they have recent engagement. |
| **Unknown** | The destination server is slow, greylisting, or temporarily down. | Do not mail in bulk. Retry validation later or flag for manual review. |

## The "Catch-all" (Accept-all) Challenge

A significant portion of B2B domains (approximately 30–40%) are configured as "catch-all." This means the server is configured to accept all mail addressed to the domain and route it to a central mailbox or discard it silently, rather than returning a `550 5.1.1` error for non-existent users.

**Verification Limitation:** For a catch-all domain, the SMTP handshake will always return `250 OK`. Verification services cannot differentiate between a real employee (`john.doe@company.com`) and a guess (`asdf123@company.com`). Sending to "Risky" catch-all addresses is the primary cause of bounces even after a list has been "cleaned."

## When to Perform Validation

### 1. Real-Time (Point of Entry)
The most effective strategy is to integrate a validation API directly into your signup forms.
- **Goal:** Catch typos (e.g., `gmail.co`) and disposable email addresses (e.g., `mailinator.com`) before they enter the database.
- **Benefit:** Reduces the need for massive batch cleaning later and prevents "pollution" of your suppression list.

### 2. Batch Cleaning (Periodic)
Clean your entire database if it has been inactive for more than 90 days.
- **Goal:** Identify natural churn (job changes, abandoned accounts) that occurred while you weren't mailing.
- **Threshold:** If you haven't mailed a segment in 6 months, expect a **10% decay rate**. Batch cleaning is mandatory here to prevent a bounce spike that could trigger ISP throttling.

### 3. Pre-Migration
Always validate your list before moving to a new ESP or a new dedicated IP.
- **Goal:** New IPs have no established reputation. A high bounce rate on the very first send is often interpreted by ISPs as "list harvesting" and can result in immediate, permanent IP blocking.

## Critical Limitations of Verification

### 1. Spam Trap Detection
**Verification cannot identify spam traps.** Because spam traps are, by definition, "valid" mailboxes that accept mail (returning `250 OK`), they appear as "Deliverable" in verification reports. In fact, aggressive verification "pinging" can sometimes trigger spam traps if the verifier hits a pristine trap domain.

### 2. Inbox Placement
Verification only confirms the pipe is open. It does not predict whether your content will trigger spam filters or if your IP/domain reputation is sufficient to reach the inbox.

### 3. Greylisting
Some servers use greylisting (returning a `451` temporary failure) to thwart automated scripts. This can cause a high number of "Unknown" results, requiring the verification service to retry multiple times over several hours.

## Key Takeaways

- **Verification is not a guarantee:** It confirms an address can *receive* mail at a specific moment, but it doesn't ensure it *wants* your mail or that it's a human-owned account.
- **Always suppress "Undeliverable":** There is zero benefit and extreme risk to mailing addresses flagged as invalid.
- **Catch-all domains are the "blind spot":** If a large percentage of your list is "Risky/Catch-all," your bounce rate will be higher than the verification report suggests.
- **API validation is better than batch cleaning:** Catching errors at the point of entry is more efficient and preserves infrastructure reputation.
- **Verification ≠ Spam Trap Removal:** You cannot "clean" your way out of a spam trap problem using verification services; that requires behavioral analysis and sunset policies.
