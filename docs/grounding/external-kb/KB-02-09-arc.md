# ARC (Authenticated Received Chain)

SPF, DKIM, and DMARC were designed for direct sender-to-receiver paths. When a message passes through an intermediary that modifies it — a mailing list that appends a footer, a forwarding rule that relays from one mailbox to another, a security gateway that rewrites URLs — those authentication mechanisms break. The original DKIM signature no longer validates because the body changed; SPF fails because the forwarding server's IP is not in the original sender's SPF record; DMARC fails because neither mechanism passes with alignment. ARC, defined in RFC 8617 (published July 2019, Experimental status), provides a way for intermediaries to record the authentication state of a message before they modify it, so the final receiver can make an informed trust decision rather than a binary pass/fail.

## The Problem ARC Solves

Consider a concrete scenario: a user at `university.edu` subscribes to a mailing list hosted at `lists.org`. A sender at `company.com` sends a message to the list. The mailing list software (e.g., Mailman 3, GNU Mailman, Sympa) adds a subject prefix `[ListName]`, appends a footer with unsubscribe instructions, and relays the message to all subscribers — including the `university.edu` address.

At `university.edu`, the receiving MTA evaluates authentication:

- **SPF**: The connecting IP belongs to `lists.org`, not `company.com`. SPF for `company.com` fails.
- **DKIM**: The `company.com` DKIM signature covered the original body. The mailing list altered the body (footer) and likely modified the `Subject:` header (prefix). The DKIM signature no longer validates. `dkim=fail (body hash did not verify)`.
- **DMARC**: Neither SPF nor DKIM passes with alignment to `company.com`. DMARC fails.

If `company.com` publishes `p=reject`, the message is rejected at `university.edu` — even though it is a legitimate message from a legitimate sender, forwarded by a legitimate mailing list. This is the "DMARC breaks mailing lists" problem that has been a persistent operational pain point since DMARC adoption accelerated around 2014-2015.

Without ARC, the receiving MTA at `university.edu` has no way to know that the message was fully authenticated when it arrived at `lists.org`. ARC fills that gap.

## How ARC Works

ARC defines three headers that an intermediary adds to a message before forwarding it. Each set of headers is numbered sequentially (`i=1` for the first ARC-participating intermediary, `i=2` for the second, and so on).

### ARC-Authentication-Results (AAR)

Records the authentication results as seen by the intermediary at the time it received the message — before any modifications. This is structurally identical to a standard `Authentication-Results` header (RFC 8601):

```
ARC-Authentication-Results: i=1; lists.org;
    dkim=pass header.i=@company.com header.s=sel1;
    spf=pass (lists.org: domain of sender@company.com designates 198.51.100.10 as permitted sender) smtp.mailfrom=sender@company.com;
    dmarc=pass (p=reject dis=none) header.from=company.com
```

This captures the fact that when `lists.org` received the message directly from `company.com`, all authentication passed.

### ARC-Message-Signature (AMS)

A DKIM-like signature computed by the intermediary over the message as it received it (before modification). Uses the same `DKIM-Signature` format and algorithm (typically `rsa-sha256` or `ed25519-sha256`). This allows the final receiver to verify that the intermediary's claimed authentication results correspond to the actual message content at that point in transit:

```
ARC-Message-Signature: i=1; a=rsa-sha256; c=relaxed/relaxed;
    d=lists.org; s=arc-20230101;
    h=from:to:subject:date:message-id:mime-version;
    bh=AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ABCDEF=;
    b=<base64-encoded signature>
```

### ARC-Seal

A signature over the ARC header set itself — specifically over the `ARC-Authentication-Results`, `ARC-Message-Signature`, and all previous `ARC-Seal` headers in the chain. The seal prevents tampering with the ARC chain after it has been created:

```
ARC-Seal: i=1; a=rsa-sha256; cv=none; d=lists.org; s=arc-20230101;
    b=<base64-encoded signature>
```

The `cv=` (chain validation) field indicates the state of the ARC chain:

| Value | Meaning |
|---|---|
| `cv=none` | This is the first ARC set in the chain (`i=1`). No previous chain to validate. |
| `cv=pass` | All previous ARC sets in the chain validated successfully. |
| `cv=fail` | The chain is broken — a previous ARC set failed validation, was tampered with, or a non-ARC-aware intermediary disrupted the chain. |

## Chain Validation at the Final Receiver

When the final receiving MTA (e.g., Gmail, Microsoft 365) processes a message with ARC headers, it performs ARC validation:

1. **Verify each ARC-Seal** from `i=1` through `i=n`, confirming that the seal signature is valid and that `cv=pass` (or `cv=none` for `i=1`).
2. **Verify the ARC-Message-Signature** for each set, confirming the intermediary's signature was valid at its hop.
3. **Evaluate the ARC-Authentication-Results** from the earliest set (`i=1`) to determine what the authentication state was before any intermediary modifications.

If the full chain validates and the receiver trusts the intermediary that created the first ARC set, it can override a DMARC failure. The critical decision is trust: ARC does not automatically override anything. The final receiver must maintain a list of trusted ARC signers and only honor ARC chains from those signers.

## Who Consumes ARC Data

**RFC fact:** RFC 8617 has Experimental status, not Standards Track. Adoption is not universal, and receivers are not obligated to implement or honor ARC.

**Gmail** is the most prominent ARC consumer. Google's documentation explicitly states that Gmail evaluates ARC chains when DMARC fails, and that ARC results from trusted forwarders can cause Gmail to deliver messages that would otherwise be rejected or quarantined under DMARC policy. Gmail's trusted ARC signer list is not publicly documented, but known participants include major mailing list providers and university mail systems.

**Microsoft 365** supports ARC validation. Microsoft's documentation describes ARC as a mechanism to "help preserve email authentication results across intermediaries" and uses ARC data in its composite authentication evaluation. Microsoft refers to this as "trusted ARC sealers" configurable by administrators in Exchange Online: administrators can add trusted ARC sealers via the Microsoft 365 Defender portal or PowerShell (`Set-ArcConfig`).

**Yahoo/AOL** has not publicly documented ARC consumption behavior as of early 2025, though Yahoo participates in the broader authentication ecosystem.

**Practical impact:** If you operate a mailing list, forwarding service, or any intermediary that modifies messages, implementing ARC signing means that downstream receivers who trust your domain can recover authentication for messages you forward. Without ARC signing, every forwarded message from a `p=reject` sender will fail DMARC at the destination with no recovery path.

## Implementing ARC Signing

ARC signing is relevant if you operate an intermediary — a mailing list, an email forwarding service, a gateway that modifies messages. If you are a direct sender only, you do not need to implement ARC; your recipients' intermediaries and receivers handle it.

### Software Support

- **Mailman 3**: Supports ARC signing natively when configured with authentication milters.
- **OpenARC** (`openarc`): An open-source milter implementation for Postfix, Sendmail, and other milter-compatible MTAs. Performs both ARC validation and signing. Configuration is similar to OpenDKIM — you specify a signing domain, selector, and private key.
- **rspamd**: Supports ARC signing and validation as a built-in module (`arc` module). Configuration requires specifying the signing domain, selector, and key path.
- **Microsoft Exchange Online**: Signs with ARC automatically for messages forwarded through Exchange transport rules.
- **Google Workspace**: Google applies ARC sealing to messages processed through Gmail's infrastructure.

### DNS Requirements

ARC uses the same DNS key infrastructure as DKIM. The ARC signing key is published as a TXT record at `<selector>._domainkey.<domain>`, exactly like a DKIM key. No new DNS record types are required. Example:

```
arc-20230101._domainkey.lists.org.  IN  TXT  "v=DKIM1; k=rsa; p=MIIBIjANBg..."
```

### Key Configuration Considerations

- **Use a dedicated selector** for ARC signing, separate from any DKIM selectors used for your own outbound mail. This makes key rotation and troubleshooting cleaner.
- **Key length**: RSA 2048-bit minimum (RFC 8301 recommendation). 1024-bit keys are technically functional but considered weak by current standards.
- **Signing headers**: The ARC-Message-Signature should cover at minimum `from`, `to`, `subject`, `date`, and `message-id`. Including additional headers reduces the ability of downstream intermediaries to inject content.

## What ARC Looks Like in Logs and Headers

When diagnosing a forwarded message that arrived despite a DMARC failure, look for this pattern in the `Authentication-Results` header at the final destination:

```
Authentication-Results: mx.google.com;
    dkim=fail (body hash did not verify) header.i=@company.com;
    spf=fail (google.com: domain of sender@company.com does not designate
    203.0.113.50 as permitted sender) smtp.mailfrom=sender@company.com;
    dmarc=fail (p=REJECT dis=NONE) header.from=company.com;
    arc=pass (i=1 spf=pass dkim=pass dmarc=pass)
```

The key indicator is `arc=pass` with the inner results showing the authentication state at the intermediary. The `dis=NONE` in the DMARC result — despite `p=REJECT` — indicates the receiver chose not to apply the reject policy, likely because the ARC chain was valid and from a trusted sealer.

If ARC validation fails, you will see `arc=fail` in the `Authentication-Results`. Common causes:

- The intermediary's ARC signing key is not published in DNS or has been rotated without updating the DNS record.
- A non-ARC-aware hop between the ARC signer and the final receiver stripped or corrupted the ARC headers.
- The ARC seal's `cv=fail` because a previous set in the chain was invalid.

## Limitations and Caveats

**ARC is not a fix for broken authentication — it is a chain-of-custody mechanism.** It does not repair a failed DKIM signature or authorize an IP for SPF. It records what the authentication state was at an earlier point and lets the final receiver decide whether to trust that record.

**Trust is the gatekeeping factor.** A final receiver only honors ARC from intermediaries it trusts. An attacker could theoretically set up a mail server, create a valid ARC chain claiming `dmarc=pass`, and forward phishing messages. The defense is that the receiver does not trust arbitrary ARC signers — only those with established reputation. This trust model is opaque: Gmail does not publish its trusted ARC signer list, and Microsoft requires explicit administrator configuration.

**ARC does not help with direct-path failures.** If your own message fails DKIM or SPF on a direct path (no intermediary), ARC is irrelevant. ARC specifically addresses the intermediary forwarding scenario.

**Experimental status means inconsistent adoption.** Not all receivers validate ARC. Not all intermediaries sign ARC. In heterogeneous mail environments, you cannot rely on ARC as a universal solution. It is one tool in the authentication recovery toolkit, effective primarily with Gmail and Microsoft 365 as the final destination.

## Key Takeaways

- **ARC preserves authentication results across intermediaries** (mailing lists, forwarding services, security gateways) by recording the authentication state before message modification, so the final receiver can evaluate trust rather than seeing a flat DMARC failure.
- **ARC is consumed primarily by Gmail and Microsoft 365.** Gmail uses ARC data from trusted sealers to override DMARC `p=reject` failures on forwarded mail. Microsoft 365 supports configurable trusted ARC sealers via `Set-ArcConfig`. Other receivers have limited or undocumented ARC support.
- **If you operate a mailing list or forwarding service, implement ARC signing.** Use OpenARC, rspamd, or your MTA's native support. Publish ARC keys in DNS using the same `_domainkey` TXT record format as DKIM. Use a dedicated selector and RSA 2048-bit keys at minimum.
- **ARC does not fix direct-path authentication failures** and does not replace proper SPF, DKIM, and DMARC configuration. It is specifically a chain-of-custody mechanism for messages that traverse intermediaries that modify content or relay from unauthorized IPs.
- **Look for `arc=pass` in `Authentication-Results`** when diagnosing forwarded messages that were delivered despite DMARC failure — this confirms the receiver honored the ARC chain from a trusted intermediary.
