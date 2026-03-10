# DMARC: Domain-based Message Authentication, Reporting, and Conformance

DMARC (RFC 7489) is the policy layer that connects SPF and DKIM into a unified authentication framework. Without DMARC, a domain can publish SPF and DKIM records, but has no mechanism to tell receivers what to do when both checks fail, and no way to receive feedback about authentication outcomes across the internet. DMARC closes both gaps: it publishes a domain owner's policy preference (none, quarantine, or reject) and establishes a reporting channel that provides aggregate and forensic data about authentication results.

This article covers DMARC's mechanism, its alignment model, how to interpret the three policy levels, the structure of DMARC reports, and concrete deployment considerations for production mail infrastructure.

## How DMARC Evaluation Works

When a receiving MTA processes an inbound message, it performs SPF and DKIM checks independently. DMARC then evaluates whether either result **aligns** with the domain in the `From:` header (RFC 5322). The evaluation sequence is:

1. The receiver extracts the domain from the message's `From:` header (the RFC 5322 `From` domain). This is the **organizational domain** that DMARC protects.
2. The receiver checks whether SPF passed and, if so, whether the domain used in the `MAIL FROM` (envelope sender) aligns with the `From:` header domain.
3. The receiver checks whether any DKIM signature passed validation and, if so, whether the `d=` domain in the DKIM signature aligns with the `From:` header domain.
4. If **either** SPF or DKIM passes **and** aligns, the message passes DMARC.
5. If neither passes with alignment, the message fails DMARC, and the receiver applies the published policy.

This is an OR evaluation, not AND. A message needs only one aligned, passing mechanism to satisfy DMARC. This design is deliberate: messages frequently lose DKIM signatures through mailing list processing or break SPF through forwarding, so requiring both would cause excessive false failures.

### The Authentication-Results Header for DMARC

Receivers record the DMARC outcome in the `Authentication-Results` header. A typical passing result:

```
Authentication-Results: mx.google.com;
    dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=example.com
```

A failing result under a reject policy:

```
Authentication-Results: mx.google.com;
    dmarc=fail (p=REJECT sp=REJECT dis=REJECT) header.from=example.com
```

The fields in parentheses:
- **`p=`**: The published domain policy (NONE, QUARANTINE, or REJECT).
- **`sp=`**: The subdomain policy, if different from the organizational domain policy.
- **`dis=`**: The **disposition** actually applied by the receiver. This may differ from `p=` -- a receiver can choose to be more lenient than the published policy (RFC 7489 Section 6.7 explicitly permits this). A `dis=NONE` with `p=REJECT` means the receiver overrode the domain's reject policy, which Gmail and Microsoft do in some circumstances based on their own internal reputation signals.

## Alignment: The Core DMARC Concept

Alignment is what distinguishes DMARC from simply running SPF and DKIM. Without alignment, an attacker could send a phishing email with a `From: ceo@yourcompany.com` header while using their own domain in the envelope sender (passing their own SPF) and signing with their own DKIM key. SPF and DKIM would both pass, but they would authenticate the attacker's domain, not `yourcompany.com`. DMARC's alignment requirement catches this: the authenticated domain must match the `From:` header domain.

### Relaxed vs. Strict Alignment

DMARC supports two alignment modes, configured independently for SPF (`aspf` tag) and DKIM (`adkim` tag):

**Relaxed alignment (default):** The authenticated domain and the `From:` domain must share the same **organizational domain** (registered domain). For example:
- `From: user@mail.example.com` with SPF passing for `bounce.example.com` -- **passes** relaxed alignment because both share the organizational domain `example.com`.
- `From: user@example.com` with DKIM `d=notifications.example.com` -- **passes** relaxed alignment.
- `From: user@example.com` with DKIM `d=example.net` -- **fails** even relaxed alignment because the organizational domains differ.

**Strict alignment (`aspf=s` or `adkim=s`):** The authenticated domain must exactly match the `From:` domain. No subdomain variation is permitted.
- `From: user@example.com` with DKIM `d=example.com` -- **passes** strict alignment.
- `From: user@example.com` with DKIM `d=mail.example.com` -- **fails** strict alignment.

**Fact (RFC 7489):** Relaxed alignment is the default when `aspf` and `adkim` tags are omitted from the DMARC record. Most production deployments use relaxed alignment.

**Best practice (industry convention):** Use relaxed alignment unless you have a specific security requirement for strict. Strict alignment breaks legitimate mail flows where the DKIM signing domain or envelope sender domain is a subdomain of the organizational domain, which is common with ESPs and transactional mail services.

## The DMARC DNS Record

DMARC is published as a TXT record at `_dmarc.example.com`. A complete example with all commonly used tags:

```
v=DMARC1; p=reject; sp=quarantine; rua=mailto:dmarc-agg@example.com; ruf=mailto:dmarc-forensic@example.com; adkim=r; aspf=r; pct=100; fo=1; ri=86400
```

### Tag Reference

| Tag | Required | Values | Default | Purpose |
|-----|----------|--------|---------|---------|
| `v` | Yes | `DMARC1` | -- | Version identifier. Must be the first tag. |
| `p` | Yes | `none`, `quarantine`, `reject` | -- | Policy for the organizational domain. |
| `sp` | No | `none`, `quarantine`, `reject` | Inherits `p` | Policy for subdomains. |
| `rua` | No | Comma-separated `mailto:` URIs | None | Aggregate report destination(s). |
| `ruf` | No | Comma-separated `mailto:` URIs | None | Forensic/failure report destination(s). |
| `adkim` | No | `r` (relaxed), `s` (strict) | `r` | DKIM alignment mode. |
| `aspf` | No | `r` (relaxed), `s` (strict) | `r` | SPF alignment mode. |
| `pct` | No | `0`-`100` | `100` | Percentage of failing messages to which the policy applies. |
| `fo` | No | `0`, `1`, `d`, `s` | `0` | Failure reporting options (controls when forensic reports are generated). |
| `ri` | No | Seconds | `86400` | Requested aggregate report interval. |

**Fact (RFC 7489):** Only `v` and `p` are required tags. A minimal valid DMARC record is `v=DMARC1; p=none;`.

**Best practice:** Always include `rua` even at `p=none`. Without a reporting address, you are publishing a policy with no visibility into what is happening. This is the most common DMARC deployment mistake.

### Cross-Domain Reporting Authorization

If your `rua` or `ruf` address is in a different domain than the one publishing the DMARC record (e.g., DMARC record for `example.com` sends reports to `reports@dmarcvendor.net`), the receiving domain must publish an authorization record:

```
example.com._report._dmarc.dmarcvendor.net TXT "v=DMARC1"
```

Without this record, receivers will not send reports to the external address. This is defined in RFC 7489 Section 7.1 and is a frequent cause of missing reports when using third-party DMARC monitoring services.

## Policy Levels: none, quarantine, reject

### p=none (Monitor Mode)

The `none` policy tells receivers to take no action based on DMARC results but to send reports. This is the starting point for any DMARC deployment.

What happens in practice:
- Messages that fail DMARC are delivered normally (subject to the receiver's own spam filtering).
- Aggregate reports are generated and sent to the `rua` address.
- The domain gains visibility into all sources sending mail using its domain in the `From:` header.

**How long to stay at p=none:** The standard recommendation is a minimum of 2-4 weeks, but this depends on traffic volume and sending infrastructure complexity. An organization with 3 ESPs, a transactional system, and marketing automation may need 6-8 weeks to identify and remediate all legitimate sending sources. The goal is to reach a state where aggregate reports show >98% of legitimate mail passing DMARC before moving to quarantine.

**Common log indicator at p=none:** Your aggregate reports will show `<disposition>none</disposition>` for all records, with `<dkim>pass</dkim>` or `<spf>pass</spf>` results revealing which mechanisms are authenticating and which are not.

### p=quarantine

The `quarantine` policy requests that receivers treat DMARC-failing messages with suspicion. In practice:

- **Gmail:** Routes failing messages to the spam folder.
- **Microsoft 365/Outlook.com:** Routes to the junk folder. Microsoft's implementation respects `pct` if set.
- **Yahoo:** Routes to the spam folder.
- **Corporate gateways (Proofpoint, Mimecast, Barracuda):** Behavior varies by configuration. Some quarantine to an admin review queue, others deliver to junk, some add an `X-` header and deliver normally.

The `pct` tag is most useful during the transition from `none` to `quarantine`. Setting `pct=10` means only 10% of DMARC-failing messages will be quarantined; the rest are treated as `p=none`. This allows gradual rollout:

1. `p=quarantine; pct=10` -- observe for 1-2 weeks.
2. `p=quarantine; pct=25` -- expand if no legitimate mail is affected.
3. `p=quarantine; pct=50` -- continue monitoring.
4. `p=quarantine; pct=100` (or omit `pct`) -- full quarantine.

**Anecdotal (community observation):** Some receivers do not fully respect `pct` values below 100. Google's implementation is well-documented and reliable; others are inconsistent. Monitor your aggregate reports for unexpected `dis=quarantine` rates that exceed your published `pct`.

### p=reject

The `reject` policy instructs receivers to reject DMARC-failing messages at the SMTP level. This is the strongest protection against domain spoofing.

What happens in practice:
- **Gmail:** Returns a `550 5.7.26` SMTP response: `This message does not pass authentication checks (SPF and DKIM both of which must pass). ...`
- **Microsoft:** Returns a `550 5.7.1` with a message referencing DMARC policy.
- **Yahoo:** Returns a `554 5.7.9` response referencing the DMARC reject policy.
- **Receiving MTAs in general:** Generate a Non-Delivery Report (NDR/bounce) back to the envelope sender.

**Fact (RFC 7489):** Receivers are not obligated to follow the published policy. Section 6.7 states that receivers may apply their own local policy. In practice, Gmail, Microsoft, and Yahoo reliably enforce `p=reject` for direct mail. However, some corporate mail servers may still deliver DMARC-failing mail if their gateway is configured to do so.

**Critical warning:** Moving to `p=reject` without thorough monitoring at `p=quarantine` will cause legitimate mail to bounce. The most common casualties are:
- Third-party SaaS platforms sending on your behalf without proper DKIM delegation.
- Legacy systems using your domain in the `From:` header without SPF or DKIM alignment.
- Mailing lists that rewrite message bodies (breaking DKIM) without rewriting the `From:` header (breaking alignment).
- Employee-configured forwarding rules at external mailboxes.

### Subdomain Policy (sp=)

The `sp` tag sets the policy for subdomains that do not publish their own DMARC record. If `sp` is absent, subdomains inherit the `p` value.

A common and recommended pattern:

```
_dmarc.example.com TXT "v=DMARC1; p=reject; sp=reject; rua=mailto:dmarc@example.com"
```

This is important because attackers frequently spoof subdomains (e.g., `login.example.com`, `secure.example.com`) that have no DNS records and therefore no authentication. Without `sp=reject`, these spoofed subdomains default to the organizational domain's policy, which may still be `none` during a gradual rollout.

**Best practice:** Set `sp=reject` even if your organizational `p=` is still at `quarantine` or `none`, provided you are certain no legitimate subdomains are sending unauthenticated mail. Defensive subdomains that never send mail should publish their own explicit `v=DMARC1; p=reject;` record as a belt-and-suspenders measure.

## Interpreting DMARC Aggregate Reports (RUA)

Aggregate reports are XML files (typically gzip-compressed) sent by receivers to the address specified in the `rua` tag. They arrive daily by default (controlled by the `ri` tag, though most receivers send daily regardless of `ri`). The volume scales with your sending: a domain sending 100,000 messages/day to Gmail will receive a single aggregate report from Google covering all those messages.

### Report Structure

A DMARC aggregate report contains:

1. **Report metadata:** Reporting organization, report ID, date range.
2. **Published policy:** Your DMARC record as the reporter saw it.
3. **Record rows:** Each row represents a unique combination of source IP, SPF result, DKIM result, and disposition. Each row includes a `count` of messages matching that combination.

A critical excerpt from a real-world aggregate report:

```xml
<record>
  <row>
    <source_ip>198.51.100.25</source_ip>
    <count>4521</count>
    <policy_evaluated>
      <disposition>none</disposition>
      <dkim>pass</dkim>
      <spf>fail</spf>
    </policy_evaluated>
  </row>
  <identifiers>
    <header_from>example.com</header_from>
  </identifiers>
  <auth_results>
    <dkim>
      <domain>example.com</domain>
      <result>pass</result>
      <selector>sel1</selector>
    </dkim>
    <spf>
      <domain>bounce.otherdomain.com</domain>
      <result>pass</result>
    </spf>
  </auth_results>
</record>
```

### How to Read This Record

This record shows 4,521 messages from IP `198.51.100.25`:
- **DKIM passed** with domain `example.com` and selector `sel1` -- this aligns with the `From:` domain, so DMARC passes via DKIM.
- **SPF passed** for `bounce.otherdomain.com` (the envelope sender), but this does **not** align with the `From:` domain `example.com`, so SPF does not contribute to DMARC pass.
- **Disposition: none** -- consistent with a passing DMARC evaluation (or a `p=none` policy).

The distinction between `<policy_evaluated>` and `<auth_results>` is essential:
- `<policy_evaluated>` shows the **DMARC-level** verdict (pass/fail after alignment is considered).
- `<auth_results>` shows the **raw** SPF and DKIM results before alignment is applied.

A record can show `<spf><result>pass</result></spf>` in `<auth_results>` but `<spf>fail</spf>` in `<policy_evaluated>` if SPF passed but the authenticated domain did not align with the `From:` header.

### What to Look for in Aggregate Reports

**Identifying unauthorized senders:** Sort records by source IP. Any IP you do not recognize that is sending as your domain with DMARC failing is either a misconfigured legitimate source or a spoofing attempt. Perform reverse DNS on the IP and check it against your known sending infrastructure.

**Measuring DMARC pass rate:** Calculate `(sum of counts where disposition=none or dkim=pass or spf=pass) / (total count)`. Target >99% pass rate for legitimate infrastructure before advancing policy level.

**Catching configuration drift:** A source IP that was previously passing DMARC and now fails usually indicates an expired DKIM key, a removed SPF include, or an IP change at your ESP that was not reflected in your SPF record.

**Volume anomalies:** A sudden spike in message count from an unfamiliar IP sending as your domain may indicate an active phishing campaign. This is one of DMARC's primary value propositions: visibility into domain abuse.

### Report Volume and Processing

Major receivers that send aggregate reports include Google, Microsoft, Yahoo, Comcast, AOL, and many corporate mail gateways. A domain with moderate sending volume (50,000-200,000 messages/day) can expect 20-50 aggregate reports daily. At higher volumes, this can reach hundreds of reports per day.

**Best practice:** Do not attempt to process DMARC aggregate reports manually via email. Use a dedicated DMARC report processing tool or service. Open-source options include parsedmarc and OpenDMARC. Commercial services (Valimail, dmarcian, Agari, EasyDMARC, and others) provide dashboards, alerting, and historical trending. The raw XML is not practical to review at scale.

## Forensic Reports (RUF)

Forensic reports (also called failure reports) are individual message-level reports sent when a message fails DMARC. They are controlled by the `ruf` tag and the `fo` tag:

| `fo` value | Behavior |
|------------|----------|
| `0` (default) | Generate forensic report only if **both** SPF and DKIM fail to align. |
| `1` | Generate forensic report if **either** SPF or DKIM fails to align. |
| `d` | Generate forensic report if DKIM evaluation fails (regardless of alignment). |
| `s` | Generate forensic report if SPF evaluation fails (regardless of alignment). |

**Practical reality:** Forensic reports are unreliable as a data source. Gmail does not send forensic reports at all. Microsoft sends them sporadically and often redacted. Yahoo's implementation is inconsistent. Many corporate gateways do not implement `ruf` reporting. As of 2025, aggregate reports (`rua`) are the only DMARC feedback mechanism you can depend on for comprehensive data.

**Fact (RFC 7489):** Forensic reports may contain personally identifiable information (email addresses, subject lines, partial message bodies). Privacy regulations (GDPR in particular) have made many receivers reluctant to generate these reports, further reducing their availability.

## Common DMARC Failure Scenarios

### Mailing List / Discussion Group Forwarding

Mailing lists (e.g., GNU Mailman, Google Groups) receive a message, potentially modify the body (adding a footer), and redistribute it. This breaks DKIM (body hash mismatch) and SPF (the list server's IP is not in the original sender's SPF record). If the list does not rewrite the `From:` header, DMARC fails.

**Mitigation:** Modern mailing list software rewrites the `From:` header to use the list's domain and places the original sender in `Reply-To:`. Mailman 3+ does this by default when the original domain publishes `p=reject` or `p=quarantine`. Google Groups rewrites for all DMARC policies. If you control the list, ensure `From:` rewriting is enabled.

### Third-Party ESP Without DKIM Delegation

If a marketing platform sends email with `From: you@yourdomain.com` but signs DKIM with `d=esp-platform.com`, the DKIM signature does not align with `yourdomain.com`. If the ESP also uses its own envelope sender domain (common for bounce handling), SPF does not align either. Result: DMARC fails.

**Fix:** Configure custom DKIM signing with your own domain. This typically involves:
1. The ESP generates a DKIM key pair and provides you with the public key.
2. You publish the public key as a TXT record at `selector._domainkey.yourdomain.com`.
3. The ESP signs outbound mail with `d=yourdomain.com`.
4. DKIM now passes with alignment.

Additionally, configure a custom return-path/envelope sender (e.g., `bounces.yourdomain.com`) and add the ESP's sending IPs to that subdomain's SPF record for belt-and-suspenders SPF alignment.

### Auto-Forwarding

When a user sets up automatic forwarding (e.g., `oldaddress@company.com` forwards to `personal@gmail.com`), the forwarding server relays the message with the original `From:` header. SPF fails (the forwarding server's IP is not in the original sender's SPF record). DKIM may survive if the forwarding server does not modify the message. If DKIM fails or was not present, DMARC fails.

**Impact:** This is the most common source of legitimate DMARC failures. ARC (Authenticated Received Chain, RFC 8617) was designed to address this, but receiver adoption is still growing. Gmail trusts ARC chains from senders it recognizes; Microsoft's support is present but less documented.

**Log indicator:** In aggregate reports, you will see a cluster of failures from IPs belonging to the forwarding mail server, with SPF failing and DKIM either passing (forwarding preserved the signature) or failing (message was modified).

### DNS Lookup Limits and SPF Failure Cascading to DMARC

SPF has a hard limit of 10 DNS lookups (RFC 7208). If your SPF record exceeds this limit, SPF evaluation returns `permerror`, which counts as a fail for DMARC purposes. This is one of the most common and least obvious causes of DMARC failures at organizations with many sending services.

**Diagnosis:** If your aggregate reports show SPF failing across all or most source IPs (including known-good ones), check your SPF record's lookup count. Each `include:`, `a:`, `mx:`, and `redirect=` mechanism counts as one lookup. Nested includes count toward the total.

## DMARC and Organizational Domain Determination

DMARC uses the Public Suffix List (PSL) to determine the organizational domain. For `mail.example.com`, the organizational domain is `example.com`. For `mail.example.co.uk`, it is `example.co.uk`. The PSL is maintained by Mozilla and used by all major DMARC implementations.

This has implications for multi-brand organizations:
- `brand-a.example.com` and `brand-b.example.com` share the organizational domain `example.com` and are governed by a single DMARC record at `_dmarc.example.com` (unless they publish their own subdomain DMARC records).
- `brand-a.com` and `brand-b.com` are separate organizational domains and require independent DMARC records.

A subdomain can publish its own DMARC record at `_dmarc.subdomain.example.com`, which takes precedence over the organizational domain's record for mail using that subdomain in the `From:` header. This allows different policies per subdomain.

## DMARC Record Validation and Common Mistakes

**Multiple DMARC records:** Publishing more than one TXT record at `_dmarc.example.com` causes a DMARC `permerror` and most receivers will treat it as if no record exists. This is a common mistake when migrating DMARC monitoring services.

**Syntax errors:** A missing semicolon, misspelled tag name, or whitespace issues can cause the record to be unparseable. Receivers handle syntax errors inconsistently -- some ignore malformed tags, others reject the entire record.

**Missing `v=DMARC1` as first tag:** The version tag must be the first tag in the record. A record starting with `p=reject; v=DMARC1` is invalid.

**Using `p=none` indefinitely:** Organizations that deploy `p=none` and never advance to `quarantine` or `reject` gain reporting visibility but provide no spoofing protection. `p=none` is a monitoring-only state.

**Validation approach:** Before publishing or modifying a DMARC record, test it with a DNS lookup:

```bash
dig +short TXT _dmarc.example.com
```

Verify that exactly one TXT record is returned, that `v=DMARC1` is the first tag, and that the `p=` value is what you intend.

## DMARC's Impact on Deliverability Beyond Authentication

While DMARC is primarily an anti-spoofing framework, its presence and policy level influence deliverability signals at major mailbox providers:

- **Gmail:** Since February 2024, Gmail requires a DMARC record (at minimum `p=none`) for bulk senders (those sending >5,000 messages/day to Gmail). Absence of a DMARC record can result in messages being rate-limited or rejected with `421-4.7.26` or `550-5.7.26` errors.
- **Yahoo:** Implemented the same bulk sender requirement on the same timeline as Gmail.
- **Microsoft:** Does not currently mandate DMARC for delivery, but factors DMARC pass/fail into its spam filtering composite score.

**Best practice (industry convention):** Even if you are not a bulk sender, publishing a DMARC record with at least `p=none` and a `rua` address is a baseline expectation for any domain sending email in a professional context. The absence of a DMARC record is increasingly treated as a negative signal rather than a neutral one.

## Deployment Roadmap Summary

A typical DMARC deployment follows this sequence:

1. **Audit sending sources:** Inventory every system, service, and platform that sends email using your domain. Include transactional systems, marketing platforms, helpdesk software, CRM, internal notifications, and any SaaS product configured to send as your domain.
2. **Ensure SPF and DKIM are configured** for every legitimate source with proper alignment.
3. **Publish `p=none` with `rua`:** Begin collecting aggregate reports. Duration: 2-8 weeks depending on infrastructure complexity.
4. **Analyze reports:** Identify any legitimate sources failing DMARC. Remediate by configuring DKIM delegation or SPF alignment.
5. **Advance to `p=quarantine` with `pct=10`:** Gradually increase `pct` over 2-4 weeks while monitoring reports and user complaints.
6. **Advance to `p=quarantine; pct=100`:** Hold for 2-4 weeks, confirming no legitimate mail impact.
7. **Advance to `p=reject`:** Full enforcement. Continue monitoring aggregate reports for new sending sources that need configuration.
8. **Ongoing maintenance:** DMARC is not set-and-forget. New SaaS integrations, infrastructure changes, and ESP migrations require re-verification of alignment. Monitor aggregate reports continuously.

## Key Takeaways

- **DMARC passes when either SPF or DKIM passes with alignment to the From: header domain.** Alignment (relaxed or strict) is the mechanism that prevents attackers from passing SPF/DKIM with their own domain while spoofing yours. Relaxed alignment (the default) permits subdomain variation; strict requires exact domain match.
- **Always publish a `rua` address, even at `p=none`.** Aggregate reports are the only reliable, comprehensive source of DMARC authentication data across all receivers. Without them, you are deploying policy changes blind.
- **The progression from `p=none` to `p=reject` should take weeks to months, not days.** Use `pct` to gradually apply quarantine and reject policies. Premature enforcement is the leading cause of legitimate mail being blocked by your own DMARC policy.
- **Forensic reports (ruf) are not dependable.** Gmail does not send them, and most other providers are inconsistent. Base your monitoring and decision-making on aggregate reports.
- **DMARC is now a baseline requirement, not an optional enhancement.** Gmail and Yahoo mandate at least `p=none` for bulk senders as of 2024. Publishing no DMARC record is an increasingly active deliverability risk.
