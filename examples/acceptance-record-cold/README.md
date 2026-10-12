# Acceptance-record checker (cold build)

A cold implementation of the acceptance conditions Shodai posted to
[x402-foundation/tsc#4](https://github.com/x402-foundation/tsc/issues/4) on 2026-10-04. An acceptance record is
made after the outcome and signed by the counterparty. It states the counterparty's disposition toward a record
someone else issued. The confirming party's key goes through draft-krausz-verification-state-03 Section 5.4.2
unchanged: `key_unresolved` versus `signature_invalid`, with the completeness input.

- Checker: [`tools/acceptance_record_check.py`](../../tools/acceptance_record_check.py). Stdlib only; Ed25519 verification is `tools/_ed25519.py`.
- Vectors: `vectors.json` (33), CC0-1.0. Built by `build_vectors.py`, which uses fixed seeds and deterministic Ed25519, so it regenerates byte-identically. The checker and the runner are stdlib-only; `build_vectors.py` alone needs the `cryptography` package (signing only). Byte-identical regeneration was confirmed with `cryptography` 50.0.2 by an independent reproduction on x86_64 glibc ([tsc#4](https://github.com/x402-foundation/tsc/issues/4), @Tetsurohhori, which also ran the checker 22/22 on x86 glibc/musl, aarch64 and s390x); other versions are untested. Every expectation was written by hand from the condition table, not read back from the checker.
- Run: `python3 run_vectors.py` reports 33/33. Condition lists compare as sets.

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

## Inputs the vectors do not yet pin (tsc#4, 2026-10-12)

Sentences 1-3 were proposed by @robertolocatelli81-dev (Noûs) on x402-foundation/tsc#4 and are adopted as worded; they state what the checker already returns. Sentence 4 settles the reading the text left open and is a checker change (see "Changes between versions").

1. A member of the signed acceptance other than the seven the vectors use (`acceptance_version`, `accepted_at`, `accepted_record_sha256`, `confirming_party`, `disposition`, `outcome_sha256`, `terms_sha256`) is ignored.
2. An acceptance whose `protected`, `payload` or `signature` is not base64url without padding (RFC 7515 §2), or whose protected header or payload does not decode to a JSON object, is malformed `acceptance_member_invalid`.
3. `acceptance_version` is required and is `acceptance-record-v0`; absent, not a string, or any other value, it is malformed `acceptance_member_invalid`.
4. A key in the trust material that is a small-order point (any of the 8 points whose order divides 8, the identity among them) is not a key of the confirming party: the result is `key_unresolved` (§5.4.2(a)), with `policy_refusal: true` if the trust material was declared complete. A signature whose `R` is a small-order point is `signature_invalid`. RFC 8032 does not require either refusal, but under such a key one signature (`R` = identity, `S` = 0) verifies every message, so an acceptance under it binds nobody.

Sentences 5-8 were added on 2026-10-12 after @Tetsurohhori's fourth reader (written from the text, 27/27) probed inputs the text did not cover and found the two existing checkers enforcing rules nothing published. They state what this checker already returns; no checker code changed. Sentences 5, 6 and 8 are pinned by new vectors.

5. A timestamp (`accepted_at` in the acceptance, `outcome_at` in the supplied record) is the -03 §5.3.2 form exactly: `YYYY-MM-DDTHH:MM:SS.mmmZ`, UTC, three fractional digits. Any other spelling is ill-typed (`acceptance_member_invalid`), including a valid RFC 3339 value without the fraction or with an offset, even one naming the same instant. Ordering (`acceptance_precedes_outcome`) is therefore compared only between two values of this form. Vectors: `acc-accepted-at-no-fraction`, `acc-accepted-at-offset-same-instant`, `acc-outcome-at-no-fraction`.
6. The protected header must carry `alg: "EdDSA"` and a string `kid`. Any other `alg` (even with a valid Ed25519 signature), or a missing or non-string `kid`, is malformed `acceptance_member_invalid`, found before the key step: with no usable `kid` there is nothing to look up, so it is not `key_unresolved`. Vectors: `acc-header-alg-not-eddsa`, `acc-header-no-kid`.
7. The signature covers the payload bytes as given, so a payload that is valid JSON but not in canonical form verifies. `confirming_party` is compared byte-exact and is not trimmed: whitespace only is a party name, not `confirming_party_absent`, and the authority step decides it.
8. `trust_material_complete` is a declaration only as the JSON value `true`; anything else, including the string `"true"` or `1`, is "not complete" (-03 §5.4.2: omitting the input is not a declaration). If the trust material lists the same `kid` twice, the first Ed25519 entry for it is used. A relying party that wants either case refused as an input error may do so before calling the checker; @robertolocatelli81-dev's omega does (`input_error`). Vector: `acc-complete-not-boolean`.

Order, per "Evaluation order" above: an undecodable encoding or protected header is found before the key step; a payload that decodes but is not a JSON object is found after it, so with an invalid signature the result is `signature_invalid`.

## Readings the comment does not fix

- **A1.** Version member `acceptance_version: "acceptance-record-v0"` (provisional; the comment names none).
- **A2.** `not_responded` is the disposition a relying party reports when no acceptance record exists. A signed record carrying `not_responded` contradicts itself and is rejected as `acceptance_member_invalid`.
- **A3.** `acceptance_member_invalid` is a name this checker needed and the comment does not have. It fires when a required member is absent or ill-typed. It is a proposed name, and can be renamed.
- **A4.** The record being accepted is supplied by the relying party. The checker reads `{issuer, issuer_kid, terms_sha256, outcome_sha256, outcome_at}` from it; `accepted_record_sha256` (A8) is computed over the record as supplied, every member included (the vectors' records also carry `record_id`, so six members are hashed). Corrected 2026-10-12 after @Tetsurohhori's probe. Verifying that record's own signature is -03 §5.4's job, not this step's.
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
| This checker (`tools/acceptance_record_check.py`) | the tsc#4 condition table and -03 §5.4.2 | `a747e46` | 27/27 | reference for these vectors |
| [actaseal/x402-acceptance-check-cold](https://github.com/actaseal/x402-acceptance-check-cold) at [`b06ca87`](https://github.com/actaseal/x402-acceptance-check-cold/tree/b06ca870b667e9883d3186c0ee6b4ef05b6470fd) | spec text only; this checker never opened; stdlib RFC 8032 Ed25519 | `646588c`, sha256-verified on every run | 22/25 | the 3 differences are the readings stated under "Evaluation order" (2026-10-11); reproduced here cold |
| [robertolocatelli81-dev/x402-acceptance-check-omega](https://github.com/robertolocatelli81-dev/x402-acceptance-check-omega) at [`fd88fbb`](https://github.com/robertolocatelli81-dev/x402-acceptance-check-omega/tree/fd88fbb3fc369b656bf9eb237131885b3e27ef5d) (Noûs, for Roberto Locatelli) | the tsc#4 table and replies, this README at `646588c` and `5a4ea06`, -03 §5.3.2, §5.4.1 and §5.4.2; this checker never opened; stdlib RFC 8032 Ed25519 | `a747e46` (same bytes at `d750291`), sha256-pinned | 27/27 (25/25 at `646588c`); always-accept control 3/27; reproduced here cold | not independent on the three readings stated at `5a4ea06` (read before writing); with them read the other way, 23/27 |

| Tetsuroh Hori's reader, [aos-standard/catalog `docs/runs/acceptance-record-cold-27/`](https://github.com/aos-standard/catalog/tree/bc9f621/docs/runs/acceptance-record-cold-27) at `bc9f621` | Shodai's table, -03 §5.3.2, §5.4.1(h) and §5.4.2, this README at `d750291` (before sentences 1-4); this checker and the other implementations never opened; Ed25519 via `cryptography` | `d750291` (same bytes at `90b5032`), sha256 `4d01f3e7…ced0e` | 27/27 | plus 23 one-change probes run three ways (this checker at `90b5032`, omega at `0496d58`); its findings became sentences 5-8 |

Each row is pinned to a commit. When the corpus changes, a row stays at its old pin until that implementation re-runs.

## Resolved questions (tsc#4, 2026-10-05)

- **Record binding.** Shodai asked for the record-binding condition (A8), and it is now in.
- **Signed `not_responded`.** Shodai confirmed reading A2: `not_responded` is the relying party's report, so a signed one is rejected.
- **`acceptance_member_invalid`.** It works as is; -03 may prefer splitting it.

## Changes between versions

**27 vectors -> 33 vectors, 2026-10-12 (checker unchanged).** Added, from @Tetsurohhori's probes on x402-foundation/tsc#4: `acc-accepted-at-no-fraction`, `acc-accepted-at-offset-same-instant`, `acc-outcome-at-no-fraction` (sentence 5), `acc-header-alg-not-eddsa`, `acc-header-no-kid` (sentence 6), `acc-complete-not-boolean` (sentence 8). Removed: none. The first 27 vectors are byte-identical to the previous file, and `vectors.json` regenerates byte-identically; `run_vectors.py` 33/33. Expectations written by hand from sentences 5-8. A4 corrected: the record digest covers the record as supplied, `record_id` included.

**Checker, 2026-10-12 (corpus unchanged, 27 vectors).** `tools/_ed25519.py` refuses small-order public keys and small-order `R`, and decodes `x = 0` with the sign bit set as invalid (RFC 8032 §5.1.3, checked before negation). `tools/acceptance_record_check.py` treats a small-order trust-material key as unresolved (sentence 4 above). Reported by @robertolocatelli81-dev (Noûs) on x402-foundation/tsc#4: before this change, an identity key with `R` = identity, `S` = 0 verified for every message. No `expect` changed; `vectors.json` regenerates byte-identically; `run_vectors.py` 27/27.

**`646588c` (25 vectors) -> `a747e46` (27 vectors).** Added: `acc-key-unresolved-valid-signature-kid-not-in-trust-material`, `acc-signature-invalid-one-byte-flipped` (the §5.4.2(a)/(c) split, pinned to one signed record instead of two differently-signed ones). Removed: none. No `expect` changed for the 25 existing vectors; byte-identical regeneration confirmed. The pair holds a single acceptance (`BODY`, signed by `cp-1`) fixed and changes exactly one input each: vector A drops `cp-1` from `trust_material` (other, unrelated keys stay in, so the result is attributable to the missing key and not to an empty trust set) for `key_unresolved`; vector B keeps `cp-1` resolvable and flips the first signature byte for `malformed`/`signature_invalid`. Contributed as [PR #13](https://github.com/babyblueviper1/preaction-governance-conformance/pull/13) by @actaseal, through `build_vectors.py`, expectations written by hand from this README. Independently re-verified here before merge: regeneration is byte-identical and `run_vectors.py` reports 27/27.

**`816afa9` (22 vectors) -> `646588c` (25 vectors).** Added: `acc-record-digest-matches-second-receipt`, `acc-record-digest-mismatch-replayed`, `acc-record-digest-absent` (the `acceptance_record_digest_mismatch` condition, tsc#4). Removed: none. No `expect` changed. **The input bytes of all 22 existing vectors did change:** every `accepted_record` gained `record_id`, and the acceptances now sign a body that includes `accepted_record_sha256`, so their payloads and signatures are new. A runner pinned to `816afa9` is unaffected; comparing the 22 shared cases across the two commits shows 22 byte differences with identical expectations. (Precision from @Tetsurohhori's vector-by-vector diff, tsc#4.)
