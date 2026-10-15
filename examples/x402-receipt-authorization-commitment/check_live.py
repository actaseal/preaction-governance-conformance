"""Holder-side check against the live chain, not the snapshot.

    python3 check_live.py <commitment> <salt> [asset] [authorizer]

Defaults to Base Sepolia USDC and the payer in candidates_snapshot.json. Pulls every AuthorizationUsed(authorizer, *)
log (Blockscout, one query), finds the one nonce the commitment opens to, then confirms authorizationState(authorizer,
nonce) == true on the token over plain JSON-RPC. No keys, no dependencies beyond the standard library.
"""
import json
import sys
import urllib.request

from commitment import link

RPC = "https://sepolia.base.org"
LOGS = "https://base-sepolia.blockscout.com/api"
AUTH_USED = "0x98de503528ee59b575ef0c0a2576a82497bfc029a5685b209e9ec333479b10a5"  # AuthorizationUsed(address,bytes32)
AUTH_STATE = "0xe94a0102"  # authorizationState(address,bytes32)
UA = {"user-agent": "x402-rac-check/0", "content-type": "application/json"}


def _get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))


def _rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(RPC, body, UA), timeout=30))["result"]


def main():
    commitment, salt = sys.argv[1], sys.argv[2]
    asset = sys.argv[3] if len(sys.argv) > 3 else "0x036cbd53842c5426634e7929541ec2318f3dcf7e"
    payer = sys.argv[4] if len(sys.argv) > 4 else "0x87f344b6ec48a936373d774d3de8649deeb66ee1"
    t1 = "0x" + "0" * 24 + payer[2:].lower()
    logs = _get(f"{LOGS}?module=logs&action=getLogs&fromBlock=0&toBlock=latest&address={asset}"
                f"&topic0={AUTH_USED}&topic1={t1}&topic0_1_opr=and")["result"]
    nonces = {l["topics"][2]: l["transactionHash"] for l in logs}
    print(f"{len(nonces)} nonces consumed by {payer} on {asset}")
    r = link(commitment, salt, "eip3009", asset, payer, list(nonces))
    if r["result"] != "linked":
        print(r)
        sys.exit(1)
    n = r["nonce"]
    state = _rpc("eth_call", [{"to": asset, "data": AUTH_STATE + t1[2:] + n[2:]}, "latest"])
    used = int(state, 16) == 1
    print(f"linked: nonce {n}\n  settlement tx {nonces[n]}\n  authorizationState = {used}")
    sys.exit(0 if used else 1)


if __name__ == "__main__":
    main()
