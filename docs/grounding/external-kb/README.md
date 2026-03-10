# Email Deliverability Knowledge Base

This directory contains a comprehensive technical knowledge base for email delivery and deliverability. These articles are designed to be used as context for LLM-based analysis of delivery logs and health reports.

## Index of Categories

### [Category 01: Email Delivery Fundamentals](./KB-01-01-smtp-delivery-lifecycle.md)
- 01: SMTP Delivery Lifecycle
- 02: MX Records and DNS
- 03: Delivery vs. Deliverability
- 04: Email Headers

### [Category 02: Authentication](./KB-02-05-spf.md)
- 05: SPF (Sender Policy Framework)
- 06: DKIM (DomainKeys Identified Mail)
- 07: DMARC (Domain-based Message Authentication)
- 08: BIMI and Brand Indicators
- 09: ARC (Authenticated Received Chain)

### [Category 03: Sender Reputation](./KB-03-10-ip-vs-domain-reputation.md)
- 10: IP vs. Domain Reputation
- 11: IP Warming
- 12: Shared vs. Dedicated IPs
- 13: Feedback Loops and Complaints
- 14: Blocklists

### [Category 04: Bounce Management](./KB-04-15-hard-vs-soft-bounces.md)
- 15: Hard vs. Soft Bounces
- 16: SMTP Response Codes Reference
- 17: Bounce Rate Thresholds
- 18: Suppression List Management

### [Category 05: List Hygiene](./KB-05-19-why-email-lists-degrade.md)
- 19: Why Email Lists Degrade Over Time
- 20: Email Verification and Validation
- 21: Sunset Policies
- 22: Spam Traps
- 23: Risks of Purchased or Scraped Lists

### [Category 06: ISP-Specific Behavior](./KB-06-24-gmail-deliverability.md)
- 24: Gmail Deliverability
- 25: Microsoft (Outlook/Hotmail) Deliverability
- 26: Yahoo/AOL Deliverability
- 27: Apple iCloud Mail

### [Category 07: Spam Filtering](./KB-07-28-how-modern-spam-filters-work.md)
- 28: How Modern Spam Filters Work
- 29: Content-Based Filtering
- 30: Engagement-Based Filtering
- 31: Header Hygiene and Technical Signals

### [Category 08: Diagnostics and Troubleshooting](./KB-08-32-reading-interpreting-bounce-logs.md)
- 32: Reading and Interpreting Bounce Logs
- 33: Diagnosing a Sudden Deliverability Drop
- 34: Diagnosing Slow/Gradual Deliverability Decline
- 35: Using Seed Lists and Inbox Placement Testing
- 36: Monitoring Tools and Dashboards

### [Category 09: Remediation Playbooks](./KB-09-37-playbook-high-bounce-rate-bulk-sends.md)
- 37: High Bounce Rate on Bulk Sends
- 38: Listed on a Blocklist
- 39: Authentication Failures
- 40: Spam Folder Placement
- 41: Throttling and Deferrals
- 42: New IP/Domain Warming
- 43: Recovering from a Spam Trap Hit
- 44: Sudden Increase in Complaints
- 45: Transactional Email Delivery Issues

### [Category 10: ISP Master Guides](./KB-10-46-gmail-master-guide.md)
- 46: Gmail Master Guide (2024 Edition)
- 47: Microsoft Master Guide (Outlook/Hotmail/O365)
- 48: Yahoo / AOL Master Guide
- 49: Apple iCloud Master Guide (Proofpoint Integration)

### [Category 11: Internal Infrastructure & Bespoke Systems](./KB-11-50-greenarrow-delivery-architecture.md)
- 50: GreenArrow Delivery Architecture
- 51: Internal Engagement Segmentation
- 52: Log Forensic Reference
- 53: ESP Reputation Rehabilitation

### [Category 12: Receiver Identification & MX Mapping](./KB-12-54-mx-rollup-identifying-providers.md)
- 54: MX Rollup: Identifying Providers

---

## Technical Standards
All articles follow a "Technical specificity" mandate:
- **Real SMTP Codes:** (e.g., `550 5.1.1`, `421 4.7.0 [TS01]`)
- **Actionable Thresholds:** (e.g., 0.1% complaint limits, 180-day sunsetting)
- **Third-Party Integrations:** Detailed coverage of Cloudmark, Proofpoint, and Spamhaus.
