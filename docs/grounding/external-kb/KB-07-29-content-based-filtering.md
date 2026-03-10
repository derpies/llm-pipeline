# Content-Based Filtering

## Overview

While reputation and engagement are the dominant factors in modern deliverability, content-based filtering remains a critical "sanitary" layer for mailbox providers (ISPs). Content filters scan the technical structure and the visible payload of an email to detect malware, phishing, and classic "spammy" patterns. 

For a deliverability professional, the most important rule is: **Reputation allows you to send, but content can still get you filtered.** Even a high-reputation sender can be routed to spam if their content triggers a specific heuristic (e.g., using a compromised URL or a suspicious header-to-body ratio).

## The Technical Scan: What Filters "See"

Content filters do not "read" an email like a human. They break the message into technical components:

### 1. URL Reputation (The #1 Content Factor)
The most common cause of content-based filtering is **URL pollution.** Every link in your email (including invisible tracking links) is checked against "Domain Blocklists" (DBLs) like Spamhaus DBL or SURBL. 
- **The Risk:** If you use a public link shortener (like `bit.ly`) or link to a domain that has been compromised, your email's reputation is immediately "poisoned" by association.
- **Log Indicator:** `550 5.7.1` Rejection with a reference to a URL blocklist.

### 2. The Image-to-Text Ratio
Spammers historically used large images to hide text from filters. Modern filters respond by penalizing emails that lack sufficient text content.
- **Rule of Thumb:** Maintain a ratio of at least **60/40 text to images.** 
- **Technical Detail:** An email consisting of a single 500KB JPEG with no `alt` text and zero body copy is a high-confidence spam signal.

### 3. MIME Structure and Malformations
A correctly formatted email uses a standard MIME (Multipurpose Internet Mail Extensions) structure. 
- **Heuristic:** Filters look for missing `boundary` tags, invalid `Content-Type` declarations, or inconsistent `Subject` headers. 
- **The "Spammy" Pattern:** Many low-quality spam bots produce malformed MIME structures. If your MTA (e.g., Postfix, PowerMTA) is misconfigured and produces invalid MIME, you will be filtered regardless of your reputation.

## The Visible Payload: Heuristic Signals

ISPs use heuristic engines (like SpamAssassin or Symantec BrightMail) to assign "spam scores" based on thousands of small triggers:

### "Spammy" Phrases and Formatting
While "Viagra" is the cliché, modern filters look for more subtle "sense of urgency" triggers:
- Excessive use of exclamation points (`!!!`).
- ALL-CAPS subject lines or headers.
- Phishing-related keywords: "Action Required," "Verify your account," "Unauthorized login detected" (when used by non-financial domains).
- **Misconception:** Using the word "Free" will not automatically send you to spam if your reputation is high. But using it 10 times in a 100-word email *will* increase your score.

### Hidden Content and Coding Tricks
Filters are designed to catch "obfuscation" techniques:
- **Invisible Text:** Using white text on a white background or font size `0`.
- **Base64 Over-encoding:** While standard for attachments, using Base64 to encode the *entire body* of a plain-text email is a major red flag.
- **JavaScript in HTML:** Most ISPs will immediately quarantine or reject emails containing `<script>` tags, as they are a primary vector for malware.

## Tracking and Infrastructure Links

Your choice of third-party tools can trigger content filters:
- **Shared Redirectors:** If you use an ESP (like Mailchimp or Klaviyo) and do not use a "Custom Tracking Domain," your links are redirected through a shared domain. If another user on that ESP is spamming, the shared redirector domain may be blocklisted, affecting *your* deliverability.
- **Unsubscribe Links:** Every bulk email **must** contain a clearly visible `List-Unsubscribe` header and a functional unsubscribe link in the body. The absence of these is a definitive "non-commercial" signal that triggers filters.

## Auditing Content Before Sending

To prevent content-based filtering, implement a "Sanity Check" workflow:

1.  **Run a "Litmus" or "Email on Acid" test:** These tools run your content through real versions of SpamAssassin and Barracuda filters.
2.  **Check URLs with "MXToolbox":** Manually verify every domain you link to is not on a DBL.
3.  **Validate HTML:** Ensure your HTML is clean and doesn't contain broken tags or malformed MIME boundaries.
4.  **Plain-Text Alternative:** Always include a `text/plain` version of your email. This satisfies older filters and shows the ISP that you are following RFC standards.

## Key Takeaways

- **URLs are the "heart" of your content reputation:** One "bad" link can sink the entire message.
- **Infrastructure domains matter:** Use a Custom Tracking Domain to separate your reputation from other users of your ESP.
- **MIME hygiene is critical:** Ensure your sending platform is producing valid, RFC-compliant email structures.
- **Consistency wins:** Dramatic changes in your content "style" (e.g., moving from text-heavy to image-heavy) can trigger a re-evaluation of your reputation.
- **"DATA" response is not a content pass:** Just because the server accepted the message with a `250 OK` doesn't mean it didn't immediately score it as spam based on the body content.
