# Playbook: Sudden Increase in Complaints

## Overview
Spam complaints are the most damaging "negative engagement" signal in the deliverability ecosystem. When a user clicks "Report Spam" or "Move to Junk," they are making a direct, human-verified report that your content is unwanted. A sudden spike in complaints—above the industry standard of **0.1%**—will result in immediate throttling and permanent reputation damage.

## Symptoms
- **Open Rate Collapse:** After a specific send, your open rates for subsequent campaigns drop by 50% or more.
- **Throttling Codes:** Logs show `421 4.7.0 [TS01] ... deferred due to user complaints` (Yahoo) or `421 4.7.0` (Gmail).
- **Dashboard Spikes:** 
  - **GPT:** The "Spam Rate" dashboard shows a spike above 0.3%.
  - **FBLs:** Your ARF (Abuse Reporting Format) feedback loop volume increases significantly.

## Root Cause Analysis
1.  **"Unsubscribe" Friction:** Your unsubscribe process is too complex (e.g., requiring a login) or your link is hidden. Users click "Spam" because it's the easiest way to stop the mail.
2.  **Frequency Overload:** You increased your sending frequency without warning, or you sent a "duplicate" email by mistake.
3.  **Content Disconnect:** You changed your content or brand "style" dramatically, causing users to not recognize the sender.
4.  **Consent Decay:** You mailed a "cold" segment of users who haven't heard from you in 12+ months and have forgotten their opt-in.
5.  **Malicious Bot Signups:** Your signup form was hit by a bot attack that populated your list with thousands of "unconfirmed" addresses.

## Step-by-Step Fix

### 1. Identify the Campaign and Segment
- Correlate the complaint spike with a specific campaign. Look at the **List Source** for that campaign.
- **Action:** If one list source is causing 80% of the complaints, **halt all sends to that source** immediately.

### 2. Audit the Unsubscribe Process
- **One-Click Check:** Verify your `List-Unsubscribe` headers are present and RFC 8058 compliant.
- **Body Unsubscribe:** Ensure your body link is clearly visible (not hidden in small text or light colors) and works with a single click. **Do not require a login to unsubscribe.**

### 3. Immediate List Scrubbing (Feedback Loops)
- Verify that your FBL (Feedback Loop) processing is actually working. If you see complaints in Yahoo CFL or Microsoft JMRP but the users are still in your "Active" list, your automation has failed.
- **Action:** Manually export all FBL complainants and permanently suppress them from your database.

### 4. Implement a "Cool-Off" Period
- For the problematic segment, stop all sending for 7-14 days. This allows the ISP's filtering model to "reset" after the complaint spike.
- When you resume, use the **Engagement-First** strategy: Send only to users who have opened/clicked in the last 14 days.

### 5. Transition to Double Opt-In (DOI)
- If the complaints are coming from new signups, you have a bot problem. Transition all lead capture forms to Double Opt-In immediately.

## Prevention
- **Stay Below 0.1%:** This is the hard ceiling for healthy deliverability. If you hit 0.3%, you are in an emergency state.
- **Visible Unsubscribe Link:** Place an additional "Unsubscribe" link at the *top* of your emails for mobile users. It is better for a user to unsubscribe than to report you as spam.
- **Consistent Branding:** Ensure your "From Name" and "Subject Line" are recognizable to your audience.
- **Re-permission Stale Lists:** If a list is older than 6 months and hasn't been mailed, send a "re-permission" email with a clear opt-in call to action before including them in bulk sends.
- **Monitor the GPT Spam Rate Dashboard:** Check this daily. It is the only way to see complaints at Gmail.
