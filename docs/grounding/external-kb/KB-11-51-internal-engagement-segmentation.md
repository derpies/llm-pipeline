# Internal Engagement Segmentation & IP Pooling

## Overview

The platform utilizes a mechanically enforced segmentation system to protect sender reputation across its multi-thousand client base. By routing traffic through isolated IP pools based on recipient engagement recency, the system creates a "Reputation Firewall." This ensures that high-engagement, high-value traffic is never contaminated by the reputation drag of unengaged or toxic segments.

For deliverability engineers, these segments (`listid`) are the primary dimension for diagnosing whether a delivery failure is an infrastructure-wide issue, a pool-specific reputation hit, or a client-specific hygiene problem.

## The Reputation Firewall: Segment Definitions

Routing is determined by the number of days since a recipient's last confirmed engagement (Clicks, Website Visits, Form Submissions, or Purchases). Confirmed Opens are included, provided they are not masked by Apple Mail Privacy Protection (MPP).

### 1. High-Trust Shared Pools
- **`SEG_E_VH` (Very High: 0–7 Days):** The pristine tier. Reserved for the most active recipients. Delivery rates should consistently exceed 95%. Drops here are treated as critical infrastructure emergencies.
- **`SEG_E_H` (High: 8–30 Days):** The standard tier for regular marketing volume. Reputation is generally strong and stable.
- **`SEG_E_M` (Medium: 31–60 Days):** The transition zone. Engagement is cooling, and ISPs may begin shifting placement from the Primary tab to Promotions.

### 2. Low-Trust & Containment Pools
- **`SEG_E_L` (Low: 61–90 Days):** The "Warning" tier. Increased bounce rates are expected as addresses begin to go stale.
- **`SEG_E_VL` (Very Low: 91–120 Days):** Borderline unengaged traffic. This pool acts as a buffer to prevent reputation decay from reaching the Higher tiers.
- **`SEG_E_RO` (Re-engagement: 121–365 Days):** Intended for win-back campaigns. Currently carries regular marketing volume as re-engagement enforcement is not yet active.
- **`SEG_E_NM` (No Marketing: 366–540 Days):** Recipients who should no longer be mailed. Suppression is not yet enforced; traffic is relegated to these IPs to contain the resulting reputation damage.
- **`SEG_E_DS` (Drop Send: 541+ Days):** The most toxic tier. Performance is expected to be poor. The metric of interest is whether delivery is stabilizing or degrading further.

### 3. Special Case: Unknown Engagement (`SEG_E_UK`)
This segment handles cases where engagement data is missing (`last-active=0`).
- **Implementation Note:** This is often a consequence of backend data completeness gaps (e.g., system-generated mailers) rather than a deliberate strategy.
- **Routing Logic:** The system applies a 15-day offset (`contact-added + 15 days`). This conservatively routes unknown traffic into the Medium/Low tiers rather than risking the VH or H pools.

## Non-Engagement Segment Types

Certain traffic bypasses the automatic engagement-based routing described above:

- **`PRIVATE_*` (Dedicated IP Assignment):** Clients who have their own IPs. Engagement segmentation is **disabled** for these accounts. All traffic, regardless of recipient activity, flows through the dedicated IPs. The client owns 100% of the reputation trajectory.
- **`ISO*` (Isolation Pools):** Manual assignments by Deliverability Operations. Used for testing, "penalty box" scenarios for high-risk senders, or traffic requiring manual quarantine.
- **Bespoke/Custom:** Any `listid` with a custom name. These are treated as isolated, first-class segments with unique routing.

## Mechanical Pool Isolation

Isolation is enforced at the infrastructure layer. It is physically impossible for an email assigned to `SEG_E_VH` to leave the platform via a `SEG_E_DS` IP. 

### Diagnostic Implications:
1.  **Pool Hit:** If `VH` delivery drops while `H` and `M` remain stable at the same ISP, the `VH` pool IPs have a specific reputation problem.
2.  **Provider Hit:** If delivery drops across **all** `SEG_E_*` pools for a specific ISP (e.g., Gmail), the ISP has changed a global policy or the sender's **Domain Reputation** has collapsed.
3.  **Client Hit:** If a specific `account-id` shows high failures across multiple pools while other clients in those same pools are succeeding, the problem is the client's content or list source.

## Key Takeaways

- **Reputation is isolated:** The system prevents "toxic" unengaged sends from affecting your best clients' delivery signals.
- **`listid` is the diagnostic key:** Always group log analysis by `listid` to understand the reputation context of the send.
- **Trend matters for lower tiers:** Do not expect high delivery on `DS` or `NM` pools; watch for changes in the failure rate rather than the absolute number.
- **Dedicated IPs are "Unprotected":** `PRIVATE_*` senders do not benefit from the engagement firewall and must manage their own list hygiene strictly.
- **Data Gaps = UK Pool:** Zero-value engagement fields are routed to the `UK` pool as a safety measure to protect pristine IPs.
