# MX Rollup: Identifying Mailbox Providers via DNS

## Overview

In high-volume email delivery, "Receiver Fingerprinting" is the practice of identifying the underlying infrastructure of a recipient domain. While a domain might be `corporate-client.com`, the actual server receiving the mail is often a third-party security cluster or a global business suite.

Knowing the true receiver allows you to apply the correct **Throttling Rules**, interpret **Specific Bounce Codes**, and identify the **Reputation Vendor** (e.g., Proofpoint, Cloudmark) that you need to mitigate. This guide provides a comprehensive "rollup" of MX patterns for major US ISPs, enterprise gateways, and forensic methods for identifying "masked" receivers.

## 1. Major US Consumer & Business Suites

These providers manage the majority of US-based mailboxes.

| Provider | Primary MX Pattern | Key Identification Notes |
| :--- | :--- | :--- |
| **Google Workspace** | `smtp.google.com` | Use legacy `aspmx.l.google.com` for older setups. |
| **Microsoft 365** | `[unique].mail.protection.outlook.com` | Confirms **Exchange Online Protection (EOP)**. |
| **Outlook.com** | `[unique].olc.protection.outlook.com` | Consumer Hotmail/Outlook; distinct from M365. |
| **Yahoo / AOL** | `[mta].am0.yahoodns.net` | Unified infrastructure for all Yahoo Inc. domains. |
| **iCloud Mail** | `mx1.mail.icloud.com` | Protected internally by **Proofpoint**. |

## 2. US Regional ISP Patterns

Regional ISPs often maintain their own legacy infrastructure or have outsourced to larger clusters.

| ISP | MX Record Pattern | Notes |
| :--- | :--- | :--- |
| **Comcast (Xfinity)** | `mx1.comcast.net` | Centralized US-wide cluster. |
| **Spectrum (Charter)** | `msg.charter.net` | Includes TWC, RoadRunner, and BrightHouse. |
| **Cox** | `mx.east.cox.net` | Split by region (east/west/central). |
| **Frontier** | `mx.frontier.com` | Legacy use of `frontiernet.net`. |
| **CenturyLink** | `mx.centurylink.net` | Includes legacy Qwest infrastructure. |
| **AT&T** | `[unique].yahoodns.net` | AT&T consumer mail is hosted by Yahoo. |

## 3. The "Guardian" Layer: Enterprise Security Gateways

Large organizations route their mail through these gateways before it reaches the final destination. The **gateway's reputation** is the only one that matters for initial delivery.

### Proofpoint (The US Market Leader)
- **Enterprise:** `mxa-[unique].pphosted.com` (Individual clusters per client).
- **Essentials:** `mx1-us1.ppe-hosted.com` (Shared SMB cluster).
- **Remediation:** Check `ipcheck.proofpoint.com`.

### Mimecast (The Structured Regional Cluster)
- **US Region:** `us-smtp-inbound-1.mimecast.com`
- **UK Region:** `eu-smtp-inbound-1.mimecast.com`
- **Notes:** Always look for the region prefix to determine data center location.

### Secondary Enterprise Gateways
| Provider | MX Pattern |
| :--- | :--- |
| **Barracuda** | `[unique].mx.ess.barracudanetworks.com` |
| **Sophos** | `[unique].prod.hydra.sophos.com` |
| **Fortinet** | `[unique].fortimailcloud.com` |
| **Appriver** | `server28.appriver.com` |
| **Trend Micro** | `[unique].in.tmes.trendmicro.com` |

## 4. Forensic Identification (When MX is Masked)

When a domain uses a generic MX record (e.g., `mail.target.com`), use these forensic layers to "unmask" the provider.

### Layer A: SPF Record "Includes"
Check the TXT record (`dig txt domain.com`). MBPs require their customers to "include" their SPF records.
- `include:_spf.google.com` → **Google**
- `include:spf.protection.outlook.com` → **Microsoft**
- `include:pphosted.com` → **Proofpoint**
- `include:_spf.mimecast.com` → **Mimecast**

### Layer B: WHOIS IP Ownership
If the MX resolves to an IP (e.g., `1.2.3.4`), run a WHOIS on the IP.
- **AS15169** → Google
- **AS8075** → Microsoft
- **AS36647** → Yahoo
- **AS3356** → Lumen (CenturyLink)

### Layer C: SMTP "Banner Grabbing"
Connect to the server on port 25 and observe the 220 greeting.
- **Cisco IronPort:** `220 **************************` (A row of asterisks is the signature).
- **Microsoft Exchange:** `220 ... Microsoft ESMTP MAIL Service ready`
- **Postfix:** `220 ... ESMTP Postfix`
- **PowerMTA:** `220 ... ESMTP PowerMTA ... ready`

## Triage Workflow for High-Volume Senders

1.  **Identify the Cluster:** Is it a "Known Good" cluster like Google or a "Sensitive" cluster like Yahoo?
2.  **Locate the Gateway:** If it points to Proofpoint, stop troubleshooting SPF/DKIM content and check the PDR IP reputation immediately.
3.  **Cross-Reference Throttles:** Group domains by their **MX Suffix** (e.g., all domains pointing to `pphosted.com`) and apply a unified connection limit to that group to avoid "Distributed Rate Limiting."

## Key Takeaways

- **MX reveals the gatekeeper:** The reputation of the MX server owner determines whether the session is even allowed to start.
- **Regional ISPs are legacy:** Many (like AT&T and Cox) have outsourced to Yahoo; check for `yahoodns.net` first.
- **Asterisks = IronPort:** If you see a banner of stars, you are fighting a Cisco IronPort appliance.
- **Region matters:** Enterprise gateways like Mimecast and Sophos are segmented by region; ensure your MTA is routing to the nearest regional cluster.
- **SPF doesn't lie:** Even if MX records are custom-branded, the SPF `include` usually reveals the underlying infrastructure.
