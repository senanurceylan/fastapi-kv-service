# ==========================
#  FastAPI Key-Value Service
# ==========================
# Bellekte çoklu store (dict of dicts) tutar.
# Ekstra olarak list/set benzetimleri ve cache içerir.

import time
from typing import Set, Optional, Any
from collections import OrderedDict
from threading import Lock
from fastapi import FastAPI


app_title = "Remote Dictionary Service (Memory, Multi-Store)"  
app = FastAPI(title=app_title)  # web sunucusu


# =================================================
# 1) CORE: MULTI-STORE (Memory Only)
# =================================================
from pydantic import BaseModel
from typing import Dict, List,Any
from fastapi import Query, HTTPException


# Birden fazla store tutulur: STORES["store_adi"]["key"] = value
STORES: Dict[str, Dict[str, Any]] = {}

class KV(BaseModel):
    key: str
    value: Any   # string, int, dict vb. her şey olabilir

def ensure_store(name: str) -> Dict[str,Any]:
    """Store yoksa oluştur, varsa döndür."""
    if name not in STORES:
        STORES[name] = {}
    return STORES[name]

# --- Health ---
@app.get("/health")
def health():
    return {"status": "up", "backend": "memory", "stores": list(STORES.keys())}

# --- Store yönetimi ---
@app.get("/stores")
def list_stores() -> List[str]:
    return sorted(STORES.keys())

@app.put("/stores/{store}")
def create_store(store: str):
    ensure_store(store)
    return {"ok": True, "store": store}

@app.delete("/stores/{store}")
def delete_store(store: str):
    if store in STORES:
        del STORES[store]
        return {"ok": True, "deleted": store}
    raise HTTPException(404, f"Store '{store}' not found")

# --- SET/GET/DEL (Redis SET/GET benzeri) ---
@app.post("/stores/{store}/set")
def set_item(store: str, item: KV):
    s = ensure_store(store)
    s[item.key] = item.value
    return {"ok": True, "store": store, "key": item.key, "value": item.value}

@app.get("/stores/{store}/get/{key}")
def get_item(store: str, key: str):
    s = STORES.get(store)
    if not s or key not in s:
        raise HTTPException(404, f"Key '{key}' not found in store '{store}'")
    return {"ok": True, "store": store, "key": key, "value": s[key]}

@app.delete("/stores/{store}/del/{key}")
def del_item(store: str, key: str):
    s = STORES.get(store)
    if not s or key not in s:
        return {"ok": False, "deleted": False, "store": store, "key": key}
    del s[key]
    return {"ok": True, "deleted": True, "store": store, "key": key}

# --- Store içi listeleme / prefix ---
@app.get("/stores/{store}/keys")
def list_keys(store: str, prefix: str | None = Query(None, description="İstersen prefix filtrele")):
    s = STORES.get(store)
    if not s:
        raise HTTPException(404, f"Store '{store}' not found")
    keys = list(s.keys())
    if prefix:
        keys = [k for k in keys if k.startswith(prefix)]
    keys.sort()
    return {"store": store, "count": len(keys), "keys": keys}

@app.get("/stores/{store}/items")
def list_items(store: str):
    s = STORES.get(store)
    if not s:
        raise HTTPException(404, f"Store '{store}' not found")
    return {"store": store, "size": len(s), "items": [{"key": k, "value": v} for k, v in s.items()]}




# =================================================
# 2) LIST / SET KOMUTLARI (Opsiyonel)
# =================================================
lists: Dict[str, List[str]] = {}   
sets_: Dict[str, Set[str]] = {}    

class Command(BaseModel):
    command: str                 
    stack_name: str
    value: Optional[str] = None 


@app.post("/command")
def run_command(cmd: Command):
    c = cmd.command.upper()

    if c == "LPUSH":
        if cmd.value is None:
            raise HTTPException(400, detail="LPUSH requires 'value'")
        lst = lists.setdefault(cmd.stack_name, [])
        lst.insert(0, cmd.value)  # başa ekle
        return {"ok": True, "type": "list", "name": cmd.stack_name, "length": len(lst)}

    elif c == "LPOP":
        lst = lists.get(cmd.stack_name, [])
        if not lst:
            return {"ok": True, "type": "list", "name": cmd.stack_name, "value": None}
        val = lst.pop(0)
        return {"ok": True, "type": "list", "name": cmd.stack_name, "value": val, "length": len(lst)}

    elif c in ("SADD", "SPUSH"):  # SPUSH'u uyumluluk için kabul ediyoruz
        if cmd.value is None:
            raise HTTPException(400, detail="SADD requires 'value'")
        s = sets_.setdefault(cmd.stack_name, set())
        before = len(s)
        s.add(cmd.value)
        return {"ok": True, "type": "set", "name": cmd.stack_name, "added": int(len(s) > before), "size": len(s)}

    elif c == "SPOP":
        s = sets_.get(cmd.stack_name, set())
        if not s:
            return {"ok": True, "type": "set", "name": cmd.stack_name, "value": None}
        val = s.pop()
        return {"ok": True, "type": "set", "name": cmd.stack_name, "value": val, "size": len(s)}

    else:
        raise HTTPException(400, detail=f"Unknown command: {cmd.command}")



# =================================================
# 3) LRU + TTL CACHE (/search)
# =================================================
CACHE_TTL_SECONDS = 300       
CACHE_MAX_ITEMS   = 100      

_cache_lock = Lock()
_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
# her entry: key -> {"value": Any, "ts": float(epoch)}

def _cache_get(key: str):
    """Cache'den oku (varsa & süresi dolmadıysa)."""
    now = time.time()
    with _cache_lock:
        item = _cache.get(key)
        if not item:
            return None
        # TTL kontrolü
        if now - item["ts"] > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        # LRU: en sona taşı
        _cache.move_to_end(key, last=True)
        return item["value"]

def _cache_put(key: str, value: Any):
    """Cache'e yaz (gerekirse en eskiyi sil)."""
    now = time.time()
    with _cache_lock:
        _cache[key] = {"value": value, "ts": now}
        _cache.move_to_end(key, last=True)
        # kapasiteyi aşarsa en eskiyi at
        while len(_cache) > CACHE_MAX_ITEMS:
            _cache.popitem(last=False)


def call_external_api(query: str) -> Any:
    """Demo dış servis."""
    sample = [
        {"id": 1, "title": f"{query} ürünü A"},
        {"id": 2, "title": f"{query} ürünü B"},
        {"id": 3, "title": f"{query} ürünü C"},
    ]
    return {"res": sample}



@app.get("/search")
def search(q: str = Query(..., description="Arama sorgusu")):
    key = q.strip().lower()
    if not key:
        return {"ok": False, "error": "empty query"}

    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "source": "cache", "query": q, "data": cached}

  
    data = call_external_api(key)
    _cache_put(key, data)
    return {"ok": True, "source": "api", "query": q, "data": data}
