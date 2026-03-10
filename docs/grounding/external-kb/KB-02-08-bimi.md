# BIMI and Brand Indicators for Email

## What BIMI Is and How It Works

Brand Indicators for Message Identification (BIMI) is a DNS-based standard that allows domain owners to display a verified brand logo next to their messages in supporting email clients. The specification is defined in the BIMI working group's Internet-Draft (draft-brand-indicators-for-message-identification) and is not yet an RFC, though it has achieved broad adoption among major mailbox providers.

The mechanism is straightforward: a domain publishes a BIMI DNS record that points to an SVG logo file. When a receiving mailbox provider processes an inbound message that passes DMARC validation, it looks up the sender's BIMI record, retrieves the logo, and displays it alongside the message in the recipient's inbox. Without BIMI, most email clients display a generic avatar, the first letter of the sender's name, or a profile photo pulled from other sources (e.g., Google account photos for Gmail).

**The DNS record format** is a TXT record published at `default._bimi.<domain>`. Example:

```
default._bimi.example.com.  IN TXT  "v=BIMI1; l=https://example.com/brand/logo.svg; a=https://example.com/brand/vmc.pem"
```

The two key fields are:
- **`l=`** (lowercase L): URL pointing to an SVG Tiny PS (Portable/Secure) version of the brand logo. The SVG must conform to the BIMI SVG profile -- standard SVG files will be rejected. The file must be served over HTTPS.
- **`a=`** (authority): URL pointing to a Verified Mark Certificate (VMC) in PEM format. This field is optional in the specification but required by Gmail and Apple Mail, which together represent the majority of BIMI-supporting clients.

The `default` selector allows for future per-stream selectors (e.g., different logos for marketing vs. transactional mail), but as of early 2026, no major mailbox provider supports non-default selectors.

## The DMARC Enforcement Prerequisite

BIMI has a hard dependency on DMARC at enforcement level. The domain must publish a DMARC policy of `p=quarantine` or `p=reject` -- a `p=none` policy disqualifies the domain from BIMI display regardless of whether the BIMI DNS record exists and is valid.

Specifically, the requirements are:

1. **DMARC policy at `p=quarantine` or `p=reject`** on the organizational domain. A subdomain override (`sp=none`) that weakens policy for the sending subdomain will disqualify that subdomain.
2. **DMARC alignment must pass** for the specific message. The message must have either SPF or DKIM alignment (or both) passing with the `From:` domain. A message that fails DMARC authentication will not display the BIMI logo even if the domain's BIMI record is correctly configured.
3. **`pct=100`** (or `pct` tag omitted, which defaults to 100). Gmail explicitly requires that the DMARC policy apply to 100% of messages. A `pct=50` during a DMARC rollout phase will prevent BIMI display.

This prerequisite is the primary practical barrier to BIMI adoption. Many organizations have DMARC deployed at `p=none` for monitoring purposes but have not moved to enforcement because they have unresolved third-party sender alignment issues. BIMI cannot be layered on top of a monitoring-only DMARC deployment.

## Verified Mark Certificates (VMCs)

A VMC is an X.509 certificate that binds a trademarked logo to a domain. It serves as third-party attestation that the entity controlling the domain has legal rights to display the logo. VMCs are issued by certificate authorities that participate in the BIMI ecosystem.

**Current VMC issuers (as of early 2026):**
- DigiCert
- Entrust

**VMC requirements:**
- The logo must be a registered trademark with an intellectual property office recognized by the issuing CA. Accepted offices include the USPTO (United States), EUIPO (European Union), UKIPO (United Kingdom), CIPO (Canada), IP Australia, and DPMA (Germany), among others. The full list varies by CA.
- The trademark registration must be active (not pending, abandoned, or expired).
- The applicant must demonstrate control over the domain, typically through a standard domain validation process similar to TLS certificate issuance.
- The logo in the VMC must visually match the registered trademark.

**Cost:** VMCs are priced in the range of $1,000-$1,500 USD per year per certificate. This is substantially more expensive than standard TLS certificates and represents the largest ongoing cost of BIMI implementation.

**Common Mark Certificates (CMCs):** The BIMI specification also defines a lighter-weight certificate type called a Common Mark Certificate, which does not require trademark registration. As of early 2026, Gmail does not support CMCs -- it requires a full VMC. Apple Mail supports CMCs for display in its email client. This split significantly limits the practical utility of CMCs for most senders, since Gmail represents the largest share of consumer inboxes.

## SVG Requirements

BIMI logos must conform to the SVG Tiny PS (Portable/Secure) profile, which is a restricted subset of SVG. This is not the same as standard SVG or SVG Tiny 1.2. Key restrictions include:

- **No scripting or animation.** JavaScript, SMIL animations, and event handlers are stripped or cause rejection.
- **No external references.** The SVG must be self-contained with no external images, stylesheets, or fonts. All content must be inline.
- **Square aspect ratio.** The viewBox must be square (equal width and height). Non-square logos will be rejected.
- **`baseProfile="tiny-ps"`** and **`version="1.2"`** must be declared in the root `<svg>` element.
- **File size:** There is no hard specification limit, but keeping the file under 32 KB is recommended. Gmail has been observed to reject files over 32 KB in practice.
- **Title element required.** The SVG must contain a `<title>` element with the brand name.

Most standard SVG files exported from design tools (Illustrator, Figma, Inkscape) will not pass BIMI validation without manual adjustment. The BIMI working group provides a validation tool at bimigroup.org, and several third-party validators exist. Testing the SVG against these validators before publishing the DNS record is strongly recommended -- an invalid SVG will silently prevent logo display with no error surfaced to the sender.

## Mailbox Provider Support

BIMI support varies significantly across providers:

| Provider | BIMI Support | VMC Required | Notes |
|----------|-------------|--------------|-------|
| Gmail | Yes (since July 2021) | Yes | Largest BIMI-supporting provider. Displays logo as sender avatar in inbox list and message view. |
| Apple Mail | Yes (since iOS 16 / macOS Ventura, Sept 2022) | Supports both VMC and CMC | Displays logo in Mail app on iOS, iPadOS, and macOS. |
| Yahoo/AOL | Yes (pilot since 2018) | No | Was an early BIMI adopter. Displays logo without requiring VMC. |
| Microsoft Outlook/365 | No | N/A | As of early 2026, Microsoft has not implemented BIMI. Outlook uses its own brand verification system. |
| Fastmail | Yes | No | Displays BIMI logos without VMC requirement. |

The absence of Microsoft Outlook support is notable because Outlook.com and Exchange Online represent a significant share of both consumer and enterprise inboxes. For organizations whose recipient base is heavily Microsoft-weighted, the visible impact of BIMI is reduced.

## Implementation Steps

1. **Confirm DMARC is at enforcement.** Verify `p=quarantine` or `p=reject` with `pct=100` on the organizational domain. Check aggregate reports to confirm alignment rates are consistently above 95% before proceeding, as BIMI draws attention to your domain's authentication posture.

2. **Prepare the SVG logo.** Convert your brand logo to SVG Tiny PS format. Ensure square aspect ratio, no external references, and the required profile declarations. Validate using the BIMI Group validator or an equivalent tool.

3. **Obtain a VMC (if targeting Gmail/Apple Mail).** Apply through DigiCert or Entrust. The process typically takes 3-6 weeks, including trademark verification. You will need to provide the trademark registration number and demonstrate domain control.

4. **Host the SVG and VMC files.** Place both files at stable HTTPS URLs. These URLs must remain accessible -- if the mailbox provider cannot retrieve the files, logo display stops. Use a CDN or reliable hosting with high uptime. The files are cached by mailbox providers, but cache durations are not standardized and may be as short as 24 hours.

5. **Publish the BIMI DNS record.** Add the TXT record at `default._bimi.<your-domain>`. If you do not have a VMC, you can publish the record with `a=` empty (i.e., `a=`), but only Yahoo, Fastmail, and Apple Mail (with CMC) will display the logo.

6. **Verify.** Send test messages to Gmail, Yahoo, and Apple Mail accounts. Logo display is not instantaneous -- Gmail in particular may take several days to begin showing the logo after the BIMI record is first published. There is no programmatic feedback mechanism; you must visually check recipient inboxes.

## Is BIMI Worth Implementing?

BIMI is primarily a brand visibility feature, not a deliverability lever. There is no evidence that BIMI directly influences inbox placement, spam scoring, or sender reputation at any major mailbox provider. Google has explicitly stated that BIMI does not affect spam filtering decisions.

**Arguments for implementing BIMI:**
- **Brand recognition in the inbox.** A consistent, recognizable logo increases visual trust and may improve open rates. Industry reports (Entrust, Red Sift) cite open rate improvements of 5-10%, though these figures come from vendor-sponsored studies and should be treated as directional rather than definitive.
- **Phishing deterrence.** BIMI with VMC provides a visible signal that a message is authenticated and from a verified brand. This raises the bar for impersonation, since attackers cannot display the logo without both DMARC-aligned authentication and a valid VMC for the trademarked logo.
- **It forces DMARC enforcement.** For organizations that have been procrastinating on moving from `p=none` to `p=reject`, BIMI provides a tangible business incentive to complete the DMARC enforcement journey.

**Arguments against (or for deferring):**
- **Cost.** The $1,000-$1,500/year VMC cost is trivial for large brands but meaningful for smaller organizations, especially given the limited provider support.
- **No Microsoft support.** If a significant portion of your recipients use Outlook, the visible impact is limited.
- **Maintenance overhead.** VMCs expire annually and must be renewed. SVG and VMC hosting must remain available. The DNS record adds one more entry to maintain in your email authentication stack.
- **No deliverability benefit.** BIMI does not help messages reach the inbox. If deliverability is the primary concern, resources are better spent on DMARC enforcement, list hygiene, and complaint rate reduction.

**Recommendation (industry best practice):** Implement BIMI after DMARC enforcement is fully deployed and stable, not before. Treat it as a brand-layer enhancement that sits on top of a mature authentication stack. For organizations still working through DMARC enforcement, BIMI should not be a priority -- but it can serve as a useful milestone target that motivates the team to complete the enforcement rollout.

## Troubleshooting BIMI Display Issues

When the BIMI logo fails to appear despite having a published record:

- **Check DMARC policy.** Confirm `p=quarantine` or `p=reject` at the organizational domain with `pct=100`. Use `dig txt _dmarc.example.com` to verify.
- **Check BIMI record syntax.** Use `dig txt default._bimi.example.com` and verify the record parses correctly. Common errors include missing semicolons, incorrect tag names, and HTTP (not HTTPS) URLs.
- **Validate SVG format.** Run the SVG through the BIMI Group validator. The most common failure is an SVG that is valid per the SVG specification but does not conform to the Tiny PS profile.
- **Verify VMC chain.** If using a VMC, confirm the PEM file is accessible at the published URL and the certificate chain is complete. An expired or improperly chained VMC will prevent display.
- **Check DMARC alignment on the specific message.** A BIMI record on the domain is necessary but not sufficient -- each individual message must pass DMARC. Check the `Authentication-Results` header on the received message for `dmarc=pass`.
- **Wait.** Gmail caches BIMI data and may not display the logo immediately after record publication. Allow 48-72 hours before investigating further.

## Key Takeaways

- BIMI displays a verified brand logo in supporting email clients (Gmail, Apple Mail, Yahoo) when messages pass DMARC authentication. It requires DMARC at `p=quarantine` or `p=reject` with `pct=100` as a prerequisite.
- Gmail and Apple Mail require a Verified Mark Certificate (VMC), which costs $1,000-$1,500/year and requires an active registered trademark. Yahoo and Fastmail display logos without a VMC.
- BIMI is a brand visibility feature, not a deliverability tool. There is no evidence it influences spam filtering or inbox placement decisions at any major provider.
- Microsoft Outlook does not support BIMI as of early 2026, which limits its visible impact for organizations with Microsoft-heavy recipient bases.
- Implement BIMI only after DMARC enforcement is fully deployed and stable. It is the capstone of an email authentication stack, not a substitute for foundational authentication work.
