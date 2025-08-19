# ==========================
# Remote Dictionary Service (FastAPI)
# ==========================
# Bu dosya; çekirdek "key → value" sözlük servisini,
# örnek list/set komutlarını ve LRU+TTL cache'li /search'i içerir.
#
# 🔑 Veri Yapıları ve nerede kullanıldıkları:
# - Hash Table (Python dict)  → STORE + /set & /list  (aktif kullanılıyor)
# - List (LPUSH/LPOP benzetimi) → /command içinde lists[...]  (opsiyonel örnek)
# - Set  (SADD/SPOP benzetimi)  → /command içinde sets_[...]  (opsiyonel örnek)
# - LRU Cache (OrderedDict)     → /search içinde cache        (aktif kullanılıyor)
# - Skip List / Trie            → Şimdilik yok; Redis tarafında ZSET/RediSearch ile gelir

import time
from typing import Any ,Dict, List, Set, Optional
from collections import OrderedDict
from threading import Lock
import requests  # already in requirements.txt
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Set, Optional

import os
from dotenv import load_dotenv
load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# -------------------------------------------------
# FastAPI uygulaması
# -------------------------------------------------
app = FastAPI(title="Remote Dictionary Service")
# Geçici depolama (ileride Redis'e geçeceğiz)
USE_REDIS = False
r = None
try:
    import redis
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()         # bağlantı testi
    USE_REDIS = True
except Exception as e:
    print(f"[WARN] Redis kullanılamıyor: {e}. STORE (memory) kullanılacak.")


# =================================================
# 1) CORE: HASH TABLE (Python dict)  → /set & /list
# =================================================
# Python'daki dict = Hash Table → ortalama O(1) ekleme/okuma.
# Not: RAM'de olduğu için process yeniden başlarsa veriler silinir.
STORE: Dict[str, str] = {}   # 3.8 uyumlu tipleme (Dict[str, str])

@app.get("/set/{name}")
def set_value(name: str, value: str = Query(..., description="Kaydedilecek değer")):
    if USE_REDIS:
        r.set(name, value); backend = "redis"
    else:
        STORE[name] = value; backend = "memory"
    return {"ok": True, "backend": backend, "key": name, "value": value}

@app.get("/list/{name}")
def get_value(name: str):
    if USE_REDIS:
        val = r.get(name)
        if val is None:
            raise HTTPException(404, detail=f"Key '{name}' not found (redis)")
        return {"ok": True, "backend": "redis", "key": name, "value": val}
    else:
        if name not in STORE:
            raise HTTPException(404, detail=f"Key '{name}' not found (memory)")
        return {"ok": True, "backend": "memory", "key": name, "value": STORE[name]}

# =========================================
# 2) HEALTHCHECK (tek ve sade)
# =========================================
@app.get("/health")
def health():
    return JSONResponse({"status": "up", "backend": "redis" if USE_REDIS else "memory"})


# ============================================================
# 3) (OPSİYONEL) LIST / SET KOMUTLARI  → /command (demo amaçlı)
# ============================================================
# Amaç: Redis'e geçtiğimizde kullanacağımız LIST/SET komutlarının
# davranışını görmek. Burada Python list/set ile benzetim yapıyoruz.
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

# --- LIST: LPUSH/LPOP (Stack / LIFO benzetimi) ---
# Not: Python list'te başa ekleme O(n); Redis LIST (quicklist) bu işi daha verimli yapar.
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


# =====================================================
# 4) (AKTİF) LRU + TTL CACHE  → /search (demo dış çağrı)
# =====================================================
# Aynı sorgu kısa sürede tekrar gelirse cache'den cevaplayıp,
# gereksiz dış istekleri önlüyoruz. OrderedDict ile LRU yapıyoruz.
CACHE_TTL_SECONDS = 300        # 5 dakika / 5 minutes
CACHE_MAX_ITEMS   = 100        # maksimum kayıt / max entries

_cache_lock = Lock()
_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
# her entry: key -> {"value": Any, "ts": float(epoch)}

def _cache_get(key: str):
    """Var ve TTL süresi dolmamışsa değeri döndür + LRU için sona taşı."""
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
    """Kaydet; kapasite aşılırsa en eski girdiyi at (LRU)."""
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
    Burada gerçek bir API'ye gidebilirsin. Şimdilik demo için
    basit bir JSON dönüyoruz. İstersen requests ile gerçek bir endpoint çağır.
    Gerçek bir servise çağrı yerine demo veri dönüyoruz
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
    1) cache'de var mı? → 'source': 'cache'
    2) yoksa dış çağrı → cache'e koy → 'source': 'api'
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

# -------------------------------------------------
# Notlar (ileri seviye):
# - Skip List: Redis'te ZSET (sorted set) yapısının temelidir; sıralı skor/aralık
#   sorguları için O(log n) ort. sağlar. Biz burada implement etmedik; Redis'e
#   geçince ZADD/ZRANGE ile kullanırız.
# - Trie: Prefiks arama/auto-complete için uygundur. Redis çekirdeğinde yok;
#   RediSearch/AutoComplete modülleri veya özel implementasyon gerekir.
# -------------------------------------------------