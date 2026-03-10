# Monitoring Tools and Dashboards

## Overview

Deliverability monitoring is a multi-layered technical discipline. You cannot rely on a single dashboard to understand your sender health. Instead, you must aggregate data from **Postmaster Tools** (the ISP view), **MTA Logs** (the infrastructure view), and **Global Blocklists** (the ecosystem view).

This article provides a technical reference for the essential tools used to monitor deliverability. It defines what each tool tells you, what it doesn't, and how to integrate their data into a coherent "Health Dashboard."

## The "ISP-First" Dashboards (Source of Truth)

These are the only tools that provide data directly from the mailbox providers' internal filtering systems.

### 1. Google Postmaster Tools (GPT)
The gold standard for domain reputation.
- **Key Metrics:** Domain Reputation (High/Med/Low/Bad), Spam Rate, Authentication Success.
- **Limitation:** Only shows data for mail delivered to Gmail addresses. It requires a minimum volume of approximately 100-200 daily emails to display reputation data.
- **Diagnostic Signal:** A drop in "Domain Reputation" is the earliest warning of a systemic block at Gmail.

### 2. Microsoft SNDS (Smart Network Data Services)
The gold standard for IP reputation.
- **Key Metrics:** IP Reputation (Green/Yellow/Red), Spam Trap Hits, Complaint Rates.
- **Limitation:** Only shows data for consumer Microsoft domains (@outlook.com, @hotmail.com, etc.). 
- **Diagnostic Signal:** "Red" IP status or non-zero "Spam Trap Hits" indicate a critical list hygiene failure.

### 3. Yahoo Postmaster Tools
Provides aggregate reputation data for Yahoo and AOL domains.
- **Key Metrics:** Spam Rate, Sender Reputation Score.
- **Limitation:** Less granular than Google's tools. It is primarily used to monitor the Yahoo CFL (Complaint Feedback Loop) performance.

## Global Reputation and Blocklist Monitors

These tools monitor whether your IP or Domain has been flagged by third-party security entities.

### 1. Spamhaus (SBL/DBL/XBL)
The most influential blocklist in the world.
- **Function:** Senders check their IP and Domain on `spamhaus.org/lookup`.
- **Diagnostic Signal:** An "SBL" listing is an immediate, global emergency. An "XBL" listing usually indicates that your server has been compromised and is being used as a botnet node.

### 2. MXToolbox and Multi-RBL Lookups
These services check your IP against hundreds of smaller blocklists (Barracuda, SORBS, etc.).
- **Function:** Automated daily monitoring that alerts you if your IP appears on any of the ~100 most common RBLs.
- **Diagnostic Signal:** Being listed on 1-2 minor lists (like SORBS) is common for shared IPs and often has little impact. Being listed on 5+ lists simultaneously indicates a reputation crisis.

## Infrastructure and Authentication Monitors

These tools verify that your technical "foundation" is correctly configured.

### 1. DMARC Aggregation Tools (e.g., dmarcian, Postmark DMARC)
- **Function:** Collects and visualizes DMARC reports (RUA) sent by ISPs. 
- **Diagnostic Signal:** Shows you which IP addresses are attempting to send mail on behalf of your domain. This is the only way to detect "shadow IT" or unauthorized senders using your domain.

### 2. SSL/TLS Monitors (e.g., SSLLabs)
- **Function:** Verifies the validity and cipher strength of your MTA's TLS certificates.
- **Diagnostic Signal:** An expired or weak certificate will cause modern MTAs to reject your connection during STARTTLS negotiation.

### 3. DNS Monitors
- **Function:** Tracks changes to your MX, SPF, DKIM, and PTR records.
- **Diagnostic Signal:** Alerts you if an accidental DNS change (e.g., a "cleanup" by an IT admin) has deleted your SPF record or invalidated a DKIM selector.

## Building a Unified Health Dashboard

A mature deliverability "Control Center" should aggregate these data points into a single view. 

| Metric Group | Tooling Source | Recommended Alert Threshold |
| :--- | :--- | :--- |
| **Global Reputation** | Spamhaus, MXToolbox | **Listing Found** (Any SBL/DBL listing). |
| **Gmail Reputation** | Google Postmaster | **Status != "High"**. |
| **Microsoft Reputation** | Microsoft SNDS | **Status == "Red"** or **Trap Hits > 0**. |
| **Authentication** | DMARC Reports | **DMARC Success < 99%**. |
| **Bounce Rate** | MTA Logs / ESP | **Hard Bounce > 0.5%** or **Spam Bounce > 0.1%**. |
| **Complaint Rate** | FBLs / GPT | **Rate > 0.1%** at any major ISP. |

## The Role of "Seed Testing" Services (e.g., GlockApps)

While not "monitoring" in the sense of real-time status, seed testing provides the "In-Box/Spam" placement data that the other tools lack.
- **Usage:** Run a seed test once per week, or before every major bulk campaign, to verify that your technical reputation is translating into actual inbox placement.

## Key Takeaways

- **No single tool is enough:** Deliverability is the intersection of all these signals.
- **Monitor the "Relay" destination:** Always group your alerts by ISP (Gmail alerts, Microsoft alerts, etc.).
- **Reputation is a lagging indicator:** By the time SNDS turns "Red," the behavior that caused it (the "spammy" send) likely happened 24–48 hours ago.
- **DNS is the most common failure point:** Use a monitor to watch your SPF and DKIM records; they are the most fragile part of your setup.
- **Don't ignore the FBLs:** The data from Yahoo and Microsoft feedback loops is your only way to see who is complaining and why.
