# Acceptance-record checker (cold build)

A cold implementation of the acceptance conditions Shodai posted to
[x402-foundation/tsc#4](https://github.com/x402-foundation/tsc/issues/4) on 2026-10-04. An acceptance record is
made after the outcome and signed by the counterparty. It states the counterparty's disposition toward a record
someone else issued. The confirming party's key goes through draft-krausz-verification-state-03 Section 5.4.2
unchanged: `key_unresolved` versus `signature_invalid`, with the completeness input.

- Checker: [`tools/acceptance_record_check.py`](../../tools/acceptance_record_check.py). Stdlib only; Ed25519 verification is `tools/_ed25519.py`.
- Vectors: `vectors.json` (25), CC0-1.0. Built by `build_vectors.py`, which uses fixed seeds and deterministic Ed25519, so it regenerates byte-identically. The checker and the runner are stdlib-only; `build_vectors.py` alone needs the `cryptography` package (signing only). Byte-identical regeneration was confirmed with `cryptography` 50.0.2 by an independent reproduction on x86_64 glibc ([tsc#4](https://github.com/x402-foundation/tsc/issues/4), @Tetsurohhori, which also ran the checker 22/22 on x86 glibc/musl, aarch64 and s390x); other versions are untested. Every expectation was written by hand from the condition table, not read back from the checker.
- Run: `python3 run_vectors.py` reports 25/25. Condition lists compare as sets.

## Result tokens

| Result | Meaning | Exit |
|---|---|---|
| `verified` | A valid record signed by the counterparty exists, and the signer's authority resolves. The disposition (`accepted`, `rejected` or `disputed`) is reported beside it. The judgment stays with the counterparty. | 0 |
| `unknown` | `acceptance_authority_unresolved`: a limit of the verifier, as in -03 §5.4.1(h). | 2 |
| `key_unresolved` | -03 §5.4.2(a). Not malformed, and not a failed signature. If trust material was declared complete, `policy_refusal: true` (§5.4.2(b)). | 2 |
| `no_record` | No acceptance record was supplied. The disposition is `not_responded`, which is never `verified` and never a weaker `accepted`. | 2 |
| `malformed` | One or more malformed conditions, report-all. | 1 |

## Evaluation order

1. **Key step.** The §5.4.2 key step runs first and stops evaluation on `key_unresolved` or `signature_invalid`. The two surface differently: `key_unresolved` is its own result token (exit 2), because no check ran. `signature_invalid` is a confirmed finding, so it surfaces as result `malformed` with `conditions: ["signature_invalid"]` (exit 1). It is the only condition reported, since evaluation stops there. `key_step` records which key sub-case occurred in both cases.
2. **Malformed conditions.** All of them are then evaluated (report-all), with type-check suppression: an ill-typed member raises `acceptance_member_invalid` only, not the mismatch that depends on it. For a `*_sha256` member, well-typed means a string of exactly 64 lowercase hex characters (the -03 §5.3.2 rule for `resource_sha256`), not any JSON string. So `"not-hex"` is ill-typed, and the digest mismatch it would otherwise cause is suppressed.
3. **Authority.** It is checked only when nothing is malformed, so an `unknown` is never stacked on a malformed finding.

`disposition` is reported only with `verified` and `unknown`, where a signed, well-formed record exists to report it from. It is `null` on `malformed` and `key_unresolved`, and `not_responded` on `no_record`. No vector pins it on a non-clean result.

These three points were always the checker's behavior. They were unstated here until @actaseal's independent from-scratch implementation ([x402-acceptance-check-cold](https://github.com/actaseal/x402-acceptance-check-cold), 22/25 agreement against `646588c`) read the text the other way on exactly these cases. No expectation changed.

## Readings the comment does not fix

- **A1.** Version member `acceptance_version: "acceptance-record-v0"` (provisional; the comment names none).
- **A2.** `not_responded` is the disposition a relying party reports when no acceptance record exists. A signed record carrying `not_responded` contradicts itself and is rejected as `acceptance_member_invalid`.
- **A3.** `acceptance_member_invalid` is a name this checker needed and the comment does not have. It fires when a required member is absent or ill-typed. It is a proposed name, and can be renamed.
- **A4.** The record being accepted is supplied by the relying party as `{issuer, issuer_kid, terms_sha256, outcome_sha256, outcome_at}`. Verifying that record's own signature is -03 §5.4's job, not this step's.
- **A5.** `acceptance_signer_is_issuer` reads "the key or party that issued" as any one of:
  - the same public key bytes, even under a different kid;
  - the confirming party equals the issuer;
  - delegation material binds the signing kid to the issuer.
- **A6.** Authority resolves if and only if the delegation material (`{party: [kid, ...]}`) lists the signing kid under the confirming party. The comment does not name a delegation format.
- **A8.** `acceptance_record_digest_mismatch` (added 2026-10-05 at Shodai's request): the acceptance carries `accepted_record_sha256`. That is sha256 over the RFC 8785 (JCS) bytes of the record it accepts. The relying party recomputes it over the record it holds. A mismatch is malformed, and an absent member is `acceptance_member_invalid`. Vector pair: `acc-record-digest-matches-second-receipt` (verified) and `acc-record-digest-mismatch-replayed`. The second is the same acceptance presented against a different receipt with identical terms and outcome digests.
- **A7.** `acceptance_precedes_outcome` is strict. An acceptance at the outcome's own instant does not precede it (vector `acc-same-instant-as-outcome-ok`).

## Independent implementations

| Implementation | Written from | Pinned corpus | Result | Notes |
|---|---|---|---|---|
| This checker (`tools/acceptance_record_check.py`) | the tsc#4 condition table and -03 §5.4.2 | `646588c` | 25/25 | reference for these vectors |
| [actaseal/x402-acceptance-check-cold](https://github.com/actaseal/x402-acceptance-check-cold) at [`b06ca87`](https://github.com/actaseal/x402-acceptance-check-cold/tree/b06ca870b667e9883d3186c0ee6b4ef05b6470fd) | spec text only; this checker never opened; stdlib RFC 8032 Ed25519 | `646588c`, sha256-verified on every run | 22/25 | the 3 differences are the readings stated under "Evaluation order" (2026-10-11); reproduced here cold |

Each row is pinned to a commit. When the corpus changes, a row stays at its old pin until that implementation re-runs.

## Resolved questions (tsc#4, 2026-10-05)

- **Record binding.** Shodai asked for the record-binding condition (A8), and it is now in.
- **Signed `not_responded`.** Shodai confirmed reading A2: `not_responded` is the relying party's report, so a signed one is rejected.
- **`acceptance_member_invalid`.** It works as is; -03 may prefer splitting it.

## Changes between versions

**`816afa9` (22 vectors) -> `646588c` (25 vectors).** Added: `acc-record-digest-matches-second-receipt`, `acc-record-digest-mismatch-replayed`, `acc-record-digest-absent` (the `acceptance_record_digest_mismatch` condition, tsc#4). Removed: none. No `expect` changed. **The input bytes of all 22 existing vectors did change:** every `accepted_record` gained `record_id`, and the acceptances now sign a body that includes `accepted_record_sha256`, so their payloads and signatures are new. A runner pinned to `816afa9` is unaffected; comparing the 22 shared cases across the two commits shows 22 byte differences with identical expectations. (Precision from @Tetsurohhori's vector-by-vector diff, tsc#4.)
