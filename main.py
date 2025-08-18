import time
from typing import Any
from collections import OrderedDict
from threading import Lock
import requests  # already in requirements.txt
from fastapi import Query  # /search için

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Set, Optional

app = FastAPI(title="Remote Dictionary Service")

# In-memory store
lists: Dict[str, List[str]] = {}   # LPUSH/LPOP
sets_: Dict[str, Set[str]] = {}    # SADD/SPOP

class Command(BaseModel):
    command: str                 # "LPUSH" | "LPOP" | "SADD" | "SPOP"
    stack_name: str
    value: Optional[str] = None  # LPUSH/SADD için gerekli

@app.get("/health")
def health_check():
    return {"status": "ok"}

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



# --- SIMPLE LRU CACHE WITH TTL ---
CACHE_TTL_SECONDS = 300        # 5 dakika / 5 minutes
CACHE_MAX_ITEMS   = 100        # maksimum kayıt / max entries

_cache_lock = Lock()
_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
# her entry: key -> {"value": Any, "ts": float(epoch)}

def _cache_get(key: str):
    """Return cached value if fresh; else None (TTL expired or missing)."""
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
    """Insert value, evict LRU if over capacity."""
    now = time.time()
    with _cache_lock:
        _cache[key] = {"value": value, "ts": now}
        _cache.move_to_end(key, last=True)
        # kapasiteyi aşarsa en eskiyi at
        while len(_cache) > CACHE_MAX_ITEMS:
            _cache.popitem(last=False)

# --- EXTERNAL CALL (mock or real) ---
def call_external_api(query: str) -> Any:
    """
    TR: Burada gerçek bir API'ye gidebilirsin. Şimdilik demo için
    basit bir JSON dönüyoruz. İstersen requests ile gerçek bir endpoint çağır.
    EN: Replace this with a real API. For demo we return a simple JSON.
    """
    # ÖRNEK: Gerçek bir GET (isteğe bağlı)
    # r = requests.get("https://example.com/search", params={"q": query}, timeout=10)
    # r.raise_for_status()
    # return r.json()

    # Demo cevap
    sample = [
        {"id": 1, "title": f"{query} ürünü A"},
        {"id": 2, "title": f"{query} ürünü B"},
        {"id": 3, "title": f"{query} ürünü C"},
    ]
    return {"res": sample}

# --- /search endpoint ---
from fastapi import Query

@app.get("/search")
def search(q: str = Query(..., description="Arama sorgusu / Search query")):
    """
    TR: Aynı sorgu kısa sürede tekrar gelirse cache'den dön.
    EN: If the same query comes again soon, return from cache.
    """
    key = q.strip().lower()
    if not key:
        return {"ok": False, "error": "empty query"}

    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "source": "cache", "query": q, "data": cached}

    # cache miss -> external call
    data = call_external_api(key)
    _cache_put(key, data)
    return {"ok": True, "source": "api", "query": q, "data": data}

# 2) --- SIMPLE LRU CACHE WITH TTL ---
# TR: TTL = kaç saniye cache'te tutulsun, MAX_ITEMS = en fazla kaç kayıt
# EN: TTL = how long to keep in cache (seconds), MAX_ITEMS = max entries
CACHE_TTL_SECONDS = 300   # 5 dakika / 5 minutes
CACHE_MAX_ITEMS   = 100   # LRU kapasitesi / capacity

_cache_lock = Lock()
_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
# entry: key -> {"value": Any, "ts": float(epoch)}

def _cache_get(key: str):
    """TR: Varsa ve süresi dolmamışsa cache'ten getir. EN: Return if not expired."""
    now = time.time()
    with _cache_lock:
        item = _cache.get(key)
        if not item:
            return None
        if now - item["ts"] > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        # LRU: used → move to end
        _cache.move_to_end(key, last=True)
        return item["value"]

def _cache_put(key: str, value: Any):
    """TR: Kaydet, kapasite aşılırsa en eskiyi at. EN: Save; evict LRU if full."""
    now = time.time()
    with _cache_lock:
        _cache[key] = {"value": value, "ts": now}
        _cache.move_to_end(key, last=True)
        while len(_cache) > CACHE_MAX_ITEMS:
            _cache.popitem(last=False)

# 3) --- EXTERNAL CALL (mock or real) ---
def call_external_api(query: str) -> Any:
    """
    TR: Burada gerçek bir API'ye istek atabilirsin (requests ile). Demo için sahte data dönüyoruz.
    EN: You can call a real API here (via requests). For demo, we return mock data.
    """
    # ÖRNEK GERÇEK ÇAĞRI (istersen açıp URL'yi koy):
    # r = requests.get("https://example.com/search", params={"q": query}, timeout=10)
    # r.raise_for_status()
    # return r.json()

    # Demo response
    return {
        "res": [
            {"id": 1, "title": f"{query} - result A"},
            {"id": 2, "title": f"{query} - result B"},
            {"id": 3, "title": f"{query} - result C"},
        ]
    }

# 4) --- /search endpoint ---
@app.get("/search")
def search(q: str = Query(..., description="Arama sorgusu / Search query")):
    """
    TR: Aynı sorgu kısa sürede tekrar gelirse cache'den dönerek gereksiz CPU/isteği önler.
    EN: Prevents repeated external calls by serving recent queries from cache.
    """
    key = q.strip().lower()
    if not key:
        return {"ok": False, "error": "empty query"}

    cached = _cache_get(key)
    if cached is not None:
        return {"ok": True, "source": "cache", "query": q, "data": cached}

    data = call_external_api(key)     # cache miss → call
    _cache_put(key, data)             # store in cache
    return {"ok": True, "source": "api", "query": q, "data": data}


