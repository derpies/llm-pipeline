# DKIM (DomainKeys Identified Mail)

## Overview

DKIM (DomainKeys Identified Mail), defined in RFC 6376, is a cryptographic authentication mechanism that allows a sending domain to take responsibility for a message by attaching a digital signature to it. The receiving mail server retrieves the sender's public key from DNS and uses it to verify that the message body and specified headers were not altered in transit. Unlike SPF, which validates the sending server's IP address, DKIM validates the message content itself — meaning a DKIM signature can survive forwarding and relaying intact, provided intermediaries do not modify the signed portions.

DKIM does not, by itself, determine whether a message is spam or legitimate. It answers a single question: "Was this message actually sent by the domain claiming responsibility, and has it been tampered with?" That verdict then feeds into DMARC alignment checks, reputation systems, and filtering decisions. A passing DKIM signature does not guarantee inbox placement, but a failing or absent signature on mail claiming to be from your domain is an increasingly strong negative signal at all major mailbox providers.

## How DKIM Signing Works

### Key Pair Generation

DKIM uses asymmetric (public/private) cryptography. The sending organization generates an RSA or Ed25519 key pair:

- **Private key:** Stored securely on the signing MTA or ESP infrastructure. Never published or transmitted. Used to generate signatures on outbound messages.
- **Public key:** Published in DNS as a TXT record under `<selector>._domainkey.<domain>`. Used by receiving servers to verify signatures.

RSA key lengths in production use today are typically 1024-bit or 2048-bit. RFC 6376 requires verifiers to support keys up to 2048 bits. The practical situation:

- **1024-bit RSA:** Still widely deployed and accepted by all receivers. Considered cryptographically weak by modern standards — factorable with sufficient resources — but no publicly documented attacks against DKIM 1024-bit keys in the wild as of early 2026. Some organizations and security auditors flag these as insufficient.
- **2048-bit RSA:** The current industry standard recommendation. Supported by all major mailbox providers. Some DNS providers have issues with the TXT record length (a 2048-bit key produces a base64-encoded string of approximately 392 characters, which may require splitting across multiple DNS strings within a single TXT record per RFC 7208 / RFC 6376).
- **Ed25519 (RFC 8463):** Produces much shorter keys and signatures with comparable or better security than 2048-bit RSA. Receiver support is growing but not universal — as of early 2026, Gmail verifies Ed25519 signatures, but some smaller providers do not. Best practice is to dual-sign with both RSA and Ed25519 if your MTA supports it.

**Fact (RFC 6376, Section 3.3.3):** Verifiers MUST support key sizes from 512 bits to 2048 bits for RSA. Keys shorter than 1024 bits SHOULD NOT be used by signers.

### The Signing Process

When an outbound MTA is configured for DKIM signing, it performs these steps for each message:

1. **Canonicalize the message.** The signer applies a canonicalization algorithm to normalize the headers and body before signing. This accounts for minor, legitimate modifications that mail relays might make (whitespace changes, header line wrapping). Two canonicalization modes exist for each of headers and body:
   - **simple:** Almost no normalization. The signed content must be delivered nearly byte-identical. More likely to break in transit but provides stronger integrity guarantees.
   - **relaxed:** Normalizes whitespace, converts header names to lowercase, and collapses runs of whitespace in the body. More resilient to transit modifications.
   The canonicalization choice is recorded in the `c=` tag of the DKIM-Signature header (e.g., `c=relaxed/relaxed` means relaxed for both headers and body). **Best practice:** Use `relaxed/relaxed` unless you have a specific reason not to — it survives most legitimate in-transit modifications.

2. **Hash the body.** The signer computes a hash of the canonicalized body (SHA-256 is standard; SHA-1 is deprecated and rejected by some receivers including Gmail since 2020). The body hash is placed in the `bh=` tag of the DKIM-Signature header.

3. **Select headers to sign.** The signer chooses which headers to include in the signature. The `h=` tag lists these headers. At minimum, the `From` header MUST be signed (RFC 6376, Section 5.4). Standard practice is to sign: `From`, `To`, `Subject`, `Date`, `MIME-Version`, `Content-Type`, and any other headers the signer wants to protect. Headers NOT listed in `h=` can be modified or added in transit without breaking the signature.

4. **Compute the signature.** The signer concatenates the canonicalized, selected headers plus the DKIM-Signature header itself (with the `b=` tag empty), hashes the result with SHA-256, and signs the hash with the private key. The resulting signature goes into the `b=` tag.

5. **Prepend the DKIM-Signature header.** The complete header is added to the message before transmission.

A typical DKIM-Signature header looks like:

```
DKIM-Signature: v=1; a=rsa-sha256; c=relaxed/relaxed;
    d=example.com; s=selector1;
    h=from:to:subject:date:mime-version:content-type;
    bh=2jUSOH9NhtVGCQWNr9BrIAPreKQjO6Sn7XIkfJVOzv8=;
    b=AuUoFEfDxTDkHlLXSZEpZj79LICEps6eda7W3deTVFOk2...
```

Key tags: `v=` (version, always 1), `a=` (signing algorithm), `c=` (canonicalization), `d=` (signing domain), `s=` (selector), `h=` (signed headers), `bh=` (body hash), `b=` (signature), `l=` (optional body length limit — avoid using this; see failure modes below).

## How DKIM Verification Works

When a receiving MTA encounters a DKIM-Signature header, it performs verification:

1. **Extract the `d=` and `s=` tags** to determine the signing domain and selector.
2. **Query DNS** for the TXT record at `<selector>._domainkey.<domain>` (e.g., `selector1._domainkey.example.com`).
3. **Parse the DKIM public key record.** The record contains the public key (`p=` tag), optionally the key type (`k=rsa` by default), acceptable hash algorithms (`h=`), service type (`s=`), and flags (`t=`). If `p=` is empty, the key has been revoked — the signature fails.
4. **Canonicalize the received message** using the algorithm specified in the `c=` tag.
5. **Recompute the body hash** and compare it to the `bh=` tag value. If they do not match, the signature fails (body was modified).
6. **Recompute the header hash and verify the signature** using the public key. If verification fails, the headers were modified or the wrong key was used.

The verification result is recorded in the `Authentication-Results` header added by the receiving MTA:

```
Authentication-Results: mx.google.com;
    dkim=pass header.i=@example.com header.s=selector1 header.b=AuUoFE;
```

Possible results: `pass`, `fail` (signature verification failed), `neutral` (signature present but could not be verified, e.g., DNS timeout), `temperror` (temporary DNS failure), `permerror` (malformed signature or DNS record), `none` (no DKIM signature present).

### DNS Record Format

A DKIM public key TXT record at `selector1._domainkey.example.com` looks like:

```
v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
```

Tags:

| Tag | Meaning | Required |
|-----|---------|----------|
| `v=DKIM1` | Version (must be DKIM1) | Recommended |
| `k=` | Key type (`rsa` or `ed25519`; default `rsa`) | Optional |
| `p=` | Base64-encoded public key | Required |
| `h=` | Acceptable hash algorithms (e.g., `sha256`) | Optional |
| `s=` | Service type (`*` for any, `email` for email only) | Optional |
| `t=` | Flags: `y` = testing mode, `s` = strict domain match | Optional |

**Operational note:** If the `p=` tag is empty (`p=`), this is a valid record that explicitly revokes the key. Any signature referencing this selector will fail. This is the correct way to decommission an old selector.

## Selectors and Key Rotation

### What Selectors Are For

The selector mechanism (`s=` tag) allows a single domain to maintain multiple active DKIM keys simultaneously. Each key pair is published under a different selector name. This is critical for several scenarios:

- **Key rotation:** Publish a new key under a new selector, start signing with it, then revoke the old key after a transition period.
- **Multiple signing systems:** Your marketing ESP, transactional email service, and internal mail servers can each have their own selector and key pair, all signing as `d=yourdomain.com`.
- **Delegation to third parties:** When you authorize an ESP to send on your behalf, they typically ask you to publish a DKIM record under a selector they control (e.g., `s1._domainkey.yourdomain.com`), and they hold the private key.

Common selector naming conventions include `s1`/`s2`, `selector1`/`selector2` (Microsoft 365 default), `google` (Google Workspace), date-based names like `202601`, or ESP-specific names like `em1234` (Mailgun).

### Key Rotation Procedure

Key rotation is the process of replacing an active DKIM key pair with a new one. You should rotate DKIM keys periodically to limit the exposure window if a private key is compromised. There is no RFC-mandated rotation interval, but industry best practice is to rotate every 6–12 months.

**Step-by-step rotation (zero-downtime approach):**

1. **Generate a new key pair.** Create a new RSA-2048 or Ed25519 key pair.
2. **Publish the new public key in DNS under a new selector.** For example, if your current selector is `s202501`, publish the new key under `s202507`. Allow DNS propagation time — wait until the record is resolvable from multiple geographic locations. A minimum of 24–48 hours after publication before using the new key is a safe margin, though records with low TTLs (300 seconds) propagate much faster.
3. **Reconfigure your MTA to sign with the new selector.** Update the signing configuration to use the new private key and new selector name.
4. **Monitor for verification failures.** Check Authentication-Results headers on test messages and monitor any DMARC aggregate reports for `dkim=fail` results associated with the new selector.
5. **Revoke the old key.** After a transition period (at least 7 days, ideally 14–30 days to account for delayed delivery, messages in retry queues, and cached DNS records), update the old selector's DNS record to `v=DKIM1; p=` (empty `p=` tag). This explicitly invalidates any residual signatures using the old selector. Do not delete the DNS record entirely — an NXDOMAIN response can cause some verifiers to return `temperror` rather than a clean `fail`, which complicates DMARC evaluation.

**Best practice (industry convention):** Maintain at least two selectors at all times — the active one and the previous one (during wind-down). Some organizations keep a standby selector pre-published (public key in DNS, private key not yet in use) to enable rapid emergency rotation.

### Key Rotation for Third-Party ESPs

When your ESP holds the private key (the typical case for cloud-based sending services), you depend on the ESP's rotation practices. Most major ESPs (SendGrid, Mailgun, Amazon SES, Postmark) handle rotation internally and either auto-rotate or provide a mechanism to trigger rotation. Verify with your ESP whether:

- They rotate keys automatically and on what schedule.
- They notify you if a DNS record update is needed on your side.
- They support customer-managed keys (BYOK) if your security policy requires it.

**Anecdotal (community observation):** Some ESPs have been observed running the same DKIM keys for years without rotation. If you manage your own DNS records for ESP DKIM, audit the `p=` values periodically to confirm they have actually changed.

## Common DKIM Failure Modes

### Body Modification in Transit

**Symptoms:** `dkim=fail` with body hash mismatch. The `bh=` value computed by the verifier does not match the `bh=` tag in the DKIM-Signature header.

**Causes:**
- Mailing list software (e.g., Mailman, Google Groups) appends footers, modifies subject lines, or rewrites body content.
- Security gateways or DLP (Data Loss Protection) systems that inspect and rewrite message content, add disclaimers, or modify URLs for link tracking.
- Content-scanning appliances that re-encode MIME parts or change transfer encoding.
- Using the `l=` (body length) tag incorrectly — this tag tells verifiers to only hash the first `l` bytes of the body, but it also opens the door to content appending attacks. RFC 6376 recommends against using `l=`.

**Log indicators:**
```
Authentication-Results: mx.example.com;
    dkim=fail (body hash did not verify) header.d=example.com
```

**Mitigation:** If you control the modification point (e.g., an outbound gateway adding disclaimers), ensure signing happens AFTER all modifications. If a mailing list is the culprit, this is expected behavior — ARC (Authenticated Received Chain) exists to preserve authentication context through such modifications.

### Header Modification in Transit

**Symptoms:** `dkim=fail` but body hash (`bh=`) verifies correctly. The header hash / signature verification step fails.

**Causes:**
- An intermediate relay modified a signed header (e.g., rewrote the `Subject` or `From` header).
- A security appliance added or modified a signed header field.
- Header folding or encoding changes that exceed what `relaxed` canonicalization can normalize.

**Log indicators:**
```
Authentication-Results: mx.example.com;
    dkim=fail (signature did not verify) header.d=example.com
```

### DNS Lookup Failures

**Symptoms:** `dkim=temperror` or `dkim=neutral` — the verifier could not retrieve the public key record.

**Causes:**
- DNS timeout — the authoritative nameserver for `_domainkey.example.com` is slow or unreachable.
- SERVFAIL — DNSSEC validation failure on the `_domainkey` subdomain.
- The TXT record exceeds the 512-byte UDP DNS response limit without proper TCP fallback or EDNS0 support. This commonly occurs with 2048-bit RSA keys. Ensure your DNS provider supports responses larger than 512 bytes (virtually all modern providers do, but misconfigured firewalls sometimes block DNS over TCP or large UDP responses).
- The selector record simply does not exist (typo in selector name, record not yet published, or wrong DNS zone).

**Log indicators:**
```
Authentication-Results: mx.example.com;
    dkim=temperror (DNS query timeout) header.d=example.com
```

**Operational note:** A `temperror` result for DKIM, when evaluated by DMARC, is treated as neither pass nor fail. Depending on the DMARC policy and the receiver's implementation, this may result in the message being accepted (if SPF passes and aligns), deferred, or treated as if DKIM were absent.

### Key Mismatch or Revoked Key

**Symptoms:** `dkim=fail` — signature does not verify, no body hash issue.

**Causes:**
- The public key in DNS does not match the private key used for signing. This occurs when the wrong key was deployed, when a key rotation updated DNS but not the signing config (or vice versa), or when an ESP rotated keys without the corresponding DNS update.
- The key has been revoked (empty `p=` tag).

**Log indicators:**
```
Authentication-Results: mx.example.com;
    dkim=fail (key not found or revoked) header.d=example.com
```

### Signing Domain vs. From Domain Misalignment

This is not a DKIM failure per se — the DKIM signature may verify perfectly — but the `d=` domain in the signature does not match the domain in the `From` header. This causes a DMARC alignment failure even though DKIM itself passes. See the distinction:

- **DKIM verification:** Does the signature cryptographically check out? (Yes/no, independent of From header.)
- **DKIM alignment (DMARC context):** Does the `d=` domain match (or be a parent of, for relaxed alignment) the From header domain?

**Example:** Message From header is `user@example.com`, but the DKIM signature has `d=esp.sendgrid.net`. DKIM passes (the signature is valid for `esp.sendgrid.net`), but DKIM alignment fails for `example.com`. For DMARC to pass on the DKIM leg, the ESP must sign with `d=example.com` (which requires the customer to publish the ESP's key in `example.com`'s DNS).

## Diagnosing DKIM Issues

### Step 1: Inspect the Authentication-Results Header

Retrieve the full headers of a delivered message (or a message in the spam folder). Look for `Authentication-Results` headers added by the receiving MTA. The DKIM section will show:

- `dkim=pass`: Signature verified. Check the `header.d=` value to confirm it matches your sending domain (relevant for DMARC alignment).
- `dkim=fail`: Signature verification failed. The parenthetical usually indicates the reason: `body hash did not verify`, `signature did not verify`, `key not found`, `key revoked`.
- `dkim=temperror`: DNS issue retrieving the public key. Transient — may resolve on retry.
- `dkim=permerror`: Malformed DKIM-Signature header or DNS record. Requires manual fix.
- `dkim=none`: No DKIM signature was present on the message.

### Step 2: Validate the DNS Record

Use command-line tools to check the public key record:

```bash
dig TXT selector1._domainkey.example.com +short
```

Verify:
- The record exists and returns a response (not NXDOMAIN).
- The `v=DKIM1` tag is present.
- The `p=` tag contains a non-empty base64 string.
- If using a 2048-bit key, the base64 string is approximately 392 characters. If it appears truncated, the DNS provider may be silently cutting the record. Use `dig` with `+tcp` to verify the full record is served.

### Step 3: Test the Signing Configuration

Send a test message to a diagnostic service (e.g., `check-auth@verifier.port25.com`, or use mail-tester.com) and review the detailed DKIM analysis in the response. These services report:

- Whether a DKIM signature was found on the message.
- The selector and domain used.
- Whether the body hash matches.
- Whether the signature verifies against the published key.
- Any canonicalization issues.

Alternatively, send to a Gmail account and view the original message headers (Gmail menu > "Show original"). Gmail displays a summary table showing DKIM pass/fail and the signing domain.

### Step 4: Check for Intermediary Modifications

If DKIM is failing with `body hash did not verify` and you have confirmed the key and signing are correct, the message body is being modified after signing. Trace the message path:

1. Review the `Received` headers to identify all intermediary hops.
2. Common culprits: outbound security gateways, link-rewriting services (e.g., URL rewriting for click tracking if applied post-signing), disclaimer/footer insertion, virus scanning appliances that modify MIME structure.
3. Solution: Ensure DKIM signing is the LAST transformation applied to the message before it leaves your infrastructure. If using an outbound gateway, the gateway should do the signing — not the upstream MTA.

### Step 5: Monitor via DMARC Reports

DMARC aggregate reports (sent daily by receiving domains when you have a DMARC record published) contain per-source-IP breakdowns of DKIM pass/fail rates and alignment results. These reports are the most reliable way to monitor DKIM health at scale because they cover all receiving domains, not just your test messages. Look for:

- High `dkim=fail` rates from specific source IPs — indicates a signing misconfiguration on that sending system.
- `dkim=pass` but alignment failure — the sending system is signing with a `d=` domain that does not match your From domain.
- `dkim=none` from IPs that should be signing — the signing is not enabled or not functioning on those systems.

## DKIM and Message Forwarding

DKIM signatures are more resilient to forwarding than SPF, because the signature is attached to the message itself rather than being tied to the sending IP. When a message is forwarded (e.g., via `.forward` files, alias expansion, or manual forwarding), the DKIM signature survives as long as the signed content is not modified.

However, mailing list managers and some forwarding implementations DO modify messages — adding footers, rewriting the From header (to comply with DMARC), prepending subject tags, or re-encoding MIME parts. In these cases, DKIM will fail. This is the primary use case for ARC (Authenticated Received Chain, RFC 8617), which allows intermediaries to record the authentication state of a message at each hop, preserving the chain of custody even when the original DKIM signature breaks.

**Practical impact (industry convention):** Gmail, Microsoft, and Yahoo all evaluate ARC chains when making authentication decisions for forwarded mail. If you operate a mailing list or forwarding service, implementing ARC signing significantly reduces the authentication failures your subscribers experience.

## Performance and Operational Considerations

### Signing Performance

DKIM signing adds computational overhead to each outbound message. RSA-2048 signing is approximately 5–10x more expensive computationally than RSA-1024, and orders of magnitude more expensive than Ed25519. For high-volume senders (millions of messages per day), this can be measurable:

- **RSA-2048:** Approximately 1,000–5,000 signatures per second per modern CPU core, depending on hardware and implementation.
- **Ed25519:** Approximately 50,000–100,000 signatures per second per core.
- **RSA-1024:** Approximately 5,000–15,000 signatures per second per core.

For most senders, DKIM signing is not a bottleneck. For very high volume senders using RSA-2048, consider hardware acceleration, dedicated signing proxies, or adding Ed25519 as an alternative.

### DNS Considerations

Receiving servers perform a DNS TXT lookup for every DKIM signature they verify. If your selector records have a very low TTL (e.g., 60 seconds), you generate more DNS queries. A TTL of 3600 seconds (1 hour) is a reasonable balance between cacheability and the ability to rotate keys promptly. During active key rotation, temporarily lowering TTL to 300 seconds before the switch and restoring it afterward is a common operational pattern.

### Multiple Signatures

A message can carry multiple DKIM signatures (e.g., one from the originating domain and one from the ESP). RFC 6376 permits this, and receivers will evaluate all present signatures. A message passes DKIM if ANY valid signature matches. This means having your ESP add their own signature alongside yours does not cause problems — it provides redundancy.

## Key Takeaways

- **DKIM validates message integrity, not sender IP.** It cryptographically proves the message body and key headers were not altered after signing, and that the signing domain authorized the message. This makes it more resilient to forwarding than SPF, but vulnerable to any in-transit content modification.
- **Use RSA-2048 keys with `relaxed/relaxed` canonicalization and SHA-256 as your baseline configuration.** This combination is universally supported by receivers and resilient to minor legitimate modifications in transit. Consider dual-signing with Ed25519 for future-proofing.
- **Rotate keys every 6–12 months using the two-selector overlap method.** Publish the new key, switch signing, wait at least 7–14 days, then revoke the old key by setting `p=` to empty. Never delete the old DNS record outright.
- **When DKIM fails, check three things in order:** (1) Is the DNS record present and correct? (2) Is the signing configuration using the correct private key and selector? (3) Is anything modifying the message after signing? The Authentication-Results header and DMARC aggregate reports are your primary diagnostic data sources.
- **DKIM alignment matters for DMARC.** A passing DKIM signature on a third-party domain (e.g., your ESP's domain) does not satisfy DMARC for your From domain. Ensure your ESP signs with `d=yourdomain.com` by publishing their key in your DNS.
