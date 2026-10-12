# ACG profile (draft): the delivery verdict against Agent Commerce Gateway's own scheme

A draft of the [parent example](../README.md)'s `deliveryVerdict`, bound to what ACG holds today (eth-mag t/29858, 2026-10-12).
It goes in the receipt's optional `metadata` member, so the frozen receipt contract does not change.

## Binding

| part | field | what it is |
|---|---|---|
| request | `invokeBodySha256` | sha256 of the original invoke body; ACG already keeps a digest of it (exact construction to confirm) |
| response | `backendBodySha256` | sha256 of the backend's raw bytes, captured before ACG parses the JSON (new; nothing hashes the response today) |
| response | `bodyJcsSha256` | sha256 of RFC 8785 JCS of the parsed backend body; it survives ACG's parse and re-serialization |
| quote | `quoteDigest` | the ERC-8409 digest once ACG issues quotes; `null` until then, and the check reports the quote step as not established |

The verdict judges the **backend's bytes**, because those are what settlement pays for. The receipt metadata also carries the
**delivered** body's digests (`deliveredBodySha256`, `deliveredBodyJcsSha256`). Anyone holding what the agent received can then tell
whether ACG's re-serialization changed formatting only (the JCS digests match, so the verdict covers what the agent got) or changed
content (they differ, and the verdict says nothing about the delivered body).

## Vectors and check

`acg_vectors.json` holds three cases with two real signed verdicts (`/review`, `sign=true`, artifact = JCS of the record):

| case | what happens | result |
|---|---|---|
| `delivered_reserialized` | backend sends pretty-printed JSON, ACG delivers it compacted | COVERED (raw digests differ, JCS digests match) |
| `gateway_altered` | the delivered body has different content from the backend's | NOT_COVERED |
| `no_quote_yet` | no 8409 quote exists yet | COVERED, quote step NOT_ESTABLISHED (never a pass) |

    pip install rfc8785
    python build_acg.py     # rebuilds acg_unsigned.json (the signed proofs are in acg_vectors.json)
    python check_acg.py     # ALL PASS: the 3 cases plus 6 mutations, each failing exactly the step it targets

## Still open

- **Who captured the bytes.** Receipts are not signed by the gateway yet, so nothing attests that the digests are the bytes ACG saw.
  Either ACG signs the receipt, or it signs the `/review` request itself (`mediator_attestation`, bound into the proof). Both attest key
  control at capture time, not independence.
- **`invokeBodySha256`** assumes sha256 over the exact bytes ACG received; it should be whatever ACG's existing digest is.
