# GreenArrow Architecture: From RAM Queue to Delivery Edge

## Overview

In high-volume sending environments (15M+ messages per day), the primary bottleneck is often disk I/O. GreenArrow Engine addresses this by utilizing a unique dual-queue architecture within the `hvmail` environment. For your infrastructure, while PowerMTA acts as the injection layer, GreenArrow serves as the intelligent "Delivery Edge"—handling all SMTP state logic, throttling, and final handoff to mailbox providers (MBPs).

This guide details the technical path a message takes once it enters the GreenArrow ecosystem and how the system manages high-concurrency delivery while protecting system resources.

## The `hvmail` Environment

GreenArrow operates within a self-contained directory structure, typically located at `/var/hvmail`. This environment includes its own set of control files, binaries, and queue directories. Understanding the layout is critical for low-level performance monitoring:

- **`/var/hvmail/bin/`**: Core delivery and management binaries.
- **`/var/hvmail/control/`**: Configuration files for throttling, VMTAs, and global limits.
- **`/var/hvmail/log/`**: Raw delivery and bounce logs (the primary source for deliverability forensics).

## The Dual-Queue System: RAM vs. Disk

The most critical architectural feature of GreenArrow is the separation of first-delivery attempts from retries through its multi-tiered queue system.

### 1. The RAM Queue (`qmail-ram`)
When a message is injected from PowerMTA via SMTP, it is first placed into the **RAM Queue** (typically located at `/var/hvmail/qmail-ram/queue`).
- **Technical Goal**: High-speed, zero-latency first attempts. By keeping the metadata and small message bodies in a RAM disk, GreenArrow can initiate thousands of concurrent SMTP sessions without being constrained by disk write speeds.
- **Behavior**: If the destination MBP (e.g., Gmail) accepts the message on the first try (`250 OK`), the message never touches the physical disk.

### 2. The Disk Queue (`qmail-disk`)
If the first attempt results in a temporary failure (4xx code) or a connection timeout, GreenArrow moves the message from RAM to the **Disk Queue** (typically `/var/hvmail/qmail-disk/queue`).
- **Technical Goal**: Persistence and reliability. Once in the disk queue, the message is written to non-volatile storage to ensure it is not lost if the server reboots or RAM is cleared.
- **Scheduling**: The disk queue manages the retry schedule (exponential backoff). As the queue grows, GreenArrow uses specialized I/O logic to ensure that "old" mail doesn't block "new" mail attempts.

**Performance Indicator**: A healthy system should have a near-empty disk queue. If the disk queue is growing significantly (>100k messages), it indicates a "Backpressure" event, likely caused by widespread ISP throttling or a networking bottleneck.

## Virtual MTAs (VMTAs) and IP Bindings

GreenArrow abstracts physical IP addresses into **Virtual MTAs (VMTAs)**. This is the mechanism used to partition your thousands of clients into logical sending pools.

- **IP Bindings**: Each VMTA is bound to a specific local IP. This ensures that outbound packets originate from the correct source IP for SPF and DKIM alignment.
- **Hostnames (PTR)**: GreenArrow allows each VMTA to present a unique HELO/EHLO hostname, ensuring that the SMTP greeting matches the Reverse DNS (PTR) record.
- **Relay VMTAs**: GreenArrow can also act as a smart-relay, forwarding mail to other internal clusters or third-party gateways while still applying its internal throttling and logging logic.

## Routing Rules and Multitenancy

To handle 15M emails per day for thousands of clients, GreenArrow uses **Routing Rules** to group VMTAs into pools.

- **Load Balancing**: A client can be assigned to a "Routing Rule" that randomizes traffic across 10 different IP VMTAs. This prevents any single IP from bearing the full weight of a high-volume client send.
- **Reputation Partitioning**: You can create separate Routing Rules for "High Reputation" clients and "New/Warming" clients. This ensures that a reputation drop for a new client (resulting in 4xx codes) only fills the disk queue for their specific VMTAs, leaving the "Safe" IPs unaffected.

## Data Flow: From Injection to Log

1.  **Injection**: PowerMTA 4.5 delivers the message to GreenArrow via SMTP on a local port (e.g., 25 or 2525).
2.  **Classification**: GreenArrow identifies the `ListID` or `ClientID` (often passed via an `X-Mailer-Info` or similar header).
3.  **Throttling Evaluation**: The system checks `/var/hvmail/control/throttles` to determine how many concurrent connections are allowed for the destination domain.
4.  **SMTP Attempt**: GreenArrow opens a session from the assigned VMTA IP.
5.  **Logging**: Regardless of the outcome (`sent`, `bounced`, `deferred`), the event is recorded in the GreenArrow logs.

## Key Takeaways

- **Disk I/O is the enemy**: GreenArrow's RAM Queue bypasses disk latency for the majority of successful deliveries.
- **Disk Queue = Backlog**: Growing disk queues are the primary indicator of deliverability issues or infrastructure bottlenecks.
- **VMTAs are the Edge**: Use VMTAs to strictly control the IP/Hostname identity presented to the receiving ISP.
- **Partitioning is essential**: At 15M/day, use Routing Rules to isolate "risky" client traffic from your stable IP pools.
- **Forensics start in `/var/hvmail/log`**: Every delivery decision made by the system is documented here, providing the "ground truth" for your RAG analysis.
