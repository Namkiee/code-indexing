
import os, json, requests
from typing import Optional

VAULT_ADDR = os.getenv("VAULT_ADDR")
VAULT_TOKEN = os.getenv("VAULT_TOKEN")
VAULT_SECRET_TPL = os.getenv("VAULT_SECRET_TEMPLATE","kv/data/codeindexing/{tenant}/salts")
FALLBACK_SALTS = os.getenv("FALLBACK_SALTS_JSON")

def get_salts_for_tenant(tenant: str) -> list[dict]:
    if VAULT_ADDR and VAULT_TOKEN:
        url = VAULT_ADDR.rstrip("/") + "/" + VAULT_SECRET_TPL.format(tenant=tenant).lstrip("/")
        try:
            r = requests.get(url, headers={"X-Vault-Token": VAULT_TOKEN}, timeout=5)
            r.raise_for_status()
            data = r.json()
            return data.get("data",{}).get("data",{}).get("salts",[])
        except Exception:
            pass
    if FALLBACK_SALTS:
        try:
            j = json.loads(FALLBACK_SALTS)
            return j.get(tenant, [])
        except Exception:
            return []
    return []

def get_current_salt(tenant: str) -> Optional[dict]:
    salts = get_salts_for_tenant(tenant)
    if not salts: return None
    salts = sorted(salts, key=lambda x: x.get("ver",0), reverse=True)
    return salts[0]
