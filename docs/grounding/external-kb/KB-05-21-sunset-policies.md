# Sunset Policies

## Overview

A sunset policy is a technical and procedural framework for identifying and removing unengaged subscribers from your active mailing list. While it may seem counterintuitive to "willingly" reduce your list size, a sunset policy is one of the most powerful tools available for protecting your sender reputation.

Modern mailbox providers (MBPs), led by Google and Microsoft, use **engagement-based filtering**. If they see that a large percentage of your recipients never open your emails, they conclude that your content is unsolicited or unwanted. This results in your mail being routed to the spam folder, even for subscribers who *do* want to see it. A sunset policy prevents this "reputation decay" by proactively pruning those who are no longer listening.

## Defining Inactivity

Inactivity is the failure of a subscriber to interact with your emails over a specific period. "Interaction" traditionally means:
- **Email Opens:** Tracked via a 1x1 pixel.
- **Email Clicks:** Tracked via redirected links.
- **Secondary Signals:** Logins to your app, website visits from a logged-in state, or purchases.

### The Apple MPP Challenge
Since late 2021, Apple’s Mail Privacy Protection (MPP) has complicated inactivity tracking. Apple now "pre-fetches" (opens) all images in emails sent to users using the Apple Mail app, resulting in "inflated" open rates. For users identified as Apple MPP, **click data or secondary signals** are much more reliable indicators of engagement than open data.

## The Subscriber Lifecycle and Sunsetting Stages

A robust sunset policy moves subscribers through three discrete stages of decreasing engagement:

### 1. The Watchlist (90 Days of Inactivity)
When a subscriber has not engaged for 90 days, they enter the "risky" segment.
- **Action:** Reduce sending frequency. If you mail them daily, move them to weekly. If you mail them weekly, move them to bi-weekly.
- **Goal:** Minimize the "negative engagement" (delete-without-reading) signals sent to ISPs.

### 2. The Re-Engagement Phase (120–180 Days of Inactivity)
The subscriber is now a serious threat to your reputation and is approaching the "recycled spam trap" window.
- **Action:** Trigger a "Win-Back" campaign. This is a series of 1–3 highly targeted, high-value emails designed to elicit a final click or open.
- **Messaging:** "Do you still want to hear from us?" or "We're cleaning our list—click here to stay subscribed."
- **Technical Requirement:** The final email in this sequence should clearly state that the user will be removed if they do not interact.

### 3. The Sunset (180+ Days of Inactivity)
If there is no interaction after the Win-Back attempt, the subscriber must be **permanently suppressed**.
- **Action:** Move the address to a "Sunset" suppression list. Do not delete them (to prevent accidental re-import), but ensure they are excluded from all future sends.
- **Exception:** If the user makes a purchase or logs into your service, their "clock" resets to zero, and they return to the active pool.

## Recommended Timeframes by Industry

Sunsetting windows should be adjusted based on your sending frequency and business model:

| Business Type | Sending Frequency | Re-engagement Start | Final Sunset |
| :--- | :--- | :--- | :--- |
| **B2B / SaaS** | Monthly/Weekly | 180 Days | 270–365 Days |
| **B2C Retail** | Daily/Bi-Weekly | 60–90 Days | 180 Days |
| **Flash Sales** | Daily | 30–60 Days | 120 Days |
| **Newsletters** | Daily | 30 Days | 90 Days |

## Technical Benefits of Sunsetting

Implementing a sunset policy directly impacts your deliverability metrics in three ways:

### 1. Protection from Recycled Spam Traps
As discussed in `KB-05-19`, ISPs deactivate abandoned mailboxes and later convert them into traps. This process usually takes 6–12 months. By sunsetting at 180 days, you almost always remove these addresses **before** they become traps.

### 2. Improved Open and Click Rates
By removing the "denominator" of unengaged users, your aggregate engagement percentages rise. ISPs use these ratios to determine whether your mail belongs in the Primary tab, the Promotions tab, or the Spam folder.

### 3. Reduced Infrastructure Costs and Throttling
Large lists of unengaged users often lead to "rate-limiting" by ISPs. If Gmail sees you trying to deliver to 50,000 unengaged users simultaneously, it will throttle your throughput (returning `421 4.7.0`). Pruning the list ensures your infrastructure remains fast and responsive for your active users.

## How to Execute a Sunset without "Vanishing"

If you have never implemented a sunset policy and have a large backlog of unengaged users, **do not remove them all at once.**
- **The Risk:** A sudden, massive drop in volume (e.g., from 1M to 500k) can look suspicious to ISP algorithms and trigger a "re-warming" period for your IP.
- **The Strategy:** Gradually "phase out" the unengaged segment over 4–6 weeks. Remove the oldest/most unengaged first, and slowly decrease the volume until your list reflects only the truly active population.

## Key Takeaways

- **Sunsetting is non-negotiable:** In modern deliverability, if you don't sunset your list, the ISPs will "sunset" your inbox placement for you.
- **Use "Last Click" as the gold standard:** Due to Apple MPP, click data is far more reliable for determining true engagement than open data.
- **Automate the process:** A manual sunset policy will fail. Use your CRM or Marketing Automation tool to create dynamic segments that automatically suppress users based on their "Last Engagement Date."
- **Win-back campaigns are "last calls":** Treat them as the final opportunity to save a relationship. If they fail, let the subscriber go.
- **Don't fear a smaller list:** A list of 50,000 engaged subscribers will generate more revenue and better deliverability than a list of 100,000 with 50% dead weight.
