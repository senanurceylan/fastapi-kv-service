# ==========================
#  FastAPI Key-Value Service
# ==========================
# Bellekte çoklu store (dict of dicts) tutar.
# Ekstra olarak list/set benzetimleri, küçük bir cache ve
# her N mutasyonda snapshot dosyaya yazma (batch persist) içerir.

import os
import json
import time
import tempfile
import shutil
from typing import Set, Optional, Any, Dict, List
from datetime import datetime
from atomicwrites import atomic_write
from google.cloud import storage

from collections import OrderedDict
from threading import Lock
from fastapi import FastAPI, Query, HTTPException, Body
from pydantic import BaseModel
from google.cloud import storage  # NEW
from dotenv import load_dotenv
load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME", "").strip()
SNAPSHOT_BLOB = os.getenv("SNAPSHOT_BLOB", "").strip()
PERSIST_FILE = os.getenv("PERSIST_FILE", "").strip()
PERSIST_BATCH_SIZE = int(os.getenv("PERSIST_BATCH_SIZE", "2"))



#UCKET_NAME = os.getenv("BUCKET_NAME")
#SNAPSHOT_BLOB = os.getenv("SNAPSHOT_BLOB", "rds_snapshot.json")


app_title = "Remote Data Service (Memory, Multi-Store)"
app = FastAPI(title=app_title)
@app.get("/")
def home():
    return {"message": "Remote Data Service is running successfully 🚀"}

# =================================================
# 1) CORE: MULTI-STORE (Memory Only)
# =================================================

# Birden fazla store tutulur: STORES["store_adi"]["key"] = value
STORES: Dict[str, Dict[str, Any]] = {}

class KV(BaseModel):
    key: str
    value: Any  # string, int, dict vb.

def ensure_store(name: str) -> Dict[str, Any]:
    """Store yoksa oluştur, varsa döndür."""
    if name not in STORES:
        STORES[name] = {}
    return STORES[name]
#-----GEÇİCİ EKLENDİ-------------
@app.get("/debug-env")
def debug_env():
    return {
        "BUCKET_NAME": BUCKET_NAME,
        "SNAPSHOT_BLOB": SNAPSHOT_BLOB,
        "PERSIST_FILE": PERSIST_FILE,
        "PERSIST_BATCH_SIZE": PERSIST_BATCH_SIZE
    }

#-------------------------------
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
    _bump_mutation(); _maybe_persist()
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
    _bump_mutation(); _maybe_persist()
    return {"ok": True, "deleted": True, "store": store, "key": key}
@app.put("/stores/{store}/update/{key}")
def update_item(store: str, key: str, value: Any = Body(...)):
    """
    Var olan bir store içindeki key'in değerini günceller.
    Eğer store veya key yoksa hata döner.
    """
    s = STORES.get(store)
    if not s:
        raise HTTPException(status_code=404, detail=f"Store '{store}' not found")
    if key not in s:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found in store '{store}'")

    s[key] = value
    _bump_mutation()
    _maybe_persist()
    return {"ok": True, "store": store, "key": key, "new_value": value}

# --- Store içi listeleme / prefix ---
@app.get("/stores/{store}/keys")
def list_keys(store: str, prefix: Optional[str] = Query(None, description="İstersen prefix filtrele")):
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
        lst.insert(0, cmd.value)
        _bump_mutation(); _maybe_persist()
        return {"ok": True, "type": "list", "name": cmd.stack_name, "length": len(lst)}

    elif c == "LPOP":
        lst = lists.get(cmd.stack_name, [])
        if not lst:
            _bump_mutation(); _maybe_persist()
            return {"ok": True, "type": "list", "name": cmd.stack_name, "value": None}
        val = lst.pop(0)
        _bump_mutation(); _maybe_persist()
        return {"ok": True, "type": "list", "name": cmd.stack_name, "value": val, "length": len(lst)}

    elif c in ("SADD", "SPUSH"):
        if cmd.value is None:
            raise HTTPException(400, detail="SADD requires 'value'")
        s = sets_.setdefault(cmd.stack_name, set())
        before = len(s)
        s.add(cmd.value)
        _bump_mutation(); _maybe_persist()
        return {"ok": True, "type": "set", "name": cmd.stack_name, "added": int(len(s) > before), "size": len(s)}

    elif c == "SPOP":
        s = sets_.get(cmd.stack_name, set())
        if not s:
            _bump_mutation(); _maybe_persist()
            return {"ok": True, "type": "set", "name": cmd.stack_name, "value": None}
        val = s.pop()
        _bump_mutation(); _maybe_persist()
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
        if now - item["ts"] > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key, last=True)
        return item["value"]

def _cache_put(key: str, value: Any):
    """Cache'e yaz (gerekirse en eskiyi sil)."""
    now = time.time()
    with _cache_lock:
        _cache[key] = {"value": value, "ts": now}
        _cache.move_to_end(key, last=True)
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

# =================================================
# 4) BATCH SNAPSHOT (her N mutasyonda /tmp'ye yaz)
# =================================================

# Cloud Run için /tmp güvenli; lokalde istersek env ile değiştirilebilir.
PERSIST_FILE = os.getenv("PERSIST_FILE", "/tmp/rds_snapshot.json")
PERSIST_BATCH_SIZE = int(os.getenv("PERSIST_BATCH_SIZE", "2"))

_persist_lock = Lock()
_ops_since_last_persist = 0  # kaç mutasyon oldu sayacı
#----------------------------------------------------
snapshot = {
    "stores": STORES,  # veya başka dict
    "timestamp": datetime.utcnow().isoformat()
}

#değiştirildi
def upload_to_gcs(snapshot_dict: dict, gcs_uri: str):
    """Upload a snapshot dictionary to Google Cloud Storage."""
    assert gcs_uri.startswith("gs://"), "Invalid GCS URI"

    # ✅ Bölmeyi güvenli yap
    parts = gcs_uri.replace("gs://", "").split("/", 1)
    bucket_name = parts[0]
    file_path = parts[1] if len(parts) > 1 else "snapshot.json"

    print(f"[DEBUG] bucket_name={bucket_name}, file_path={file_path}")

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)

    try:
        blob.upload_from_string(
            json.dumps(snapshot_dict, indent=2),
            content_type="application/json"
        )
        print(f"[INFO] Snapshot uploaded to gs://{bucket_name}/{file_path}")
    except Exception as e:
        print(f"[ERROR] Failed to upload snapshot to GCS: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload snapshot to GCS.")




def _serialize_snapshot() -> dict:
    """Bellekteki tüm verileri (stores, lists, sets) JSON formatına hazırlar."""
    return {
        "stores": STORES,
        "lists": lists,
        "sets": {k: list(v) for k, v in sets_.items()},
        "timestamp": datetime.utcnow().isoformat()
    }
#------------------ sonradan eklendi
def _gcs_download():
    """GCS'den snapshot dosyasını indirir."""
    try:
        if not BUCKET_NAME or not SNAPSHOT_BLOB:
            return None
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(SNAPSHOT_BLOB)
        if not blob.exists():
            print(f"[INFO] No existing snapshot found in bucket {BUCKET_NAME}")
            return None
        data = blob.download_as_bytes()
        print(f"[INFO] Snapshot downloaded from {BUCKET_NAME}/{SNAPSHOT_BLOB}")
        return data
    except Exception as e:
        print(f"[WARN] GCS download failed: {e}")
        return None

#-------

def _persist_snapshot():
    """Bellekteki tüm store'ları JSON olarak kaydeder ve GCS'ye yükler."""
    try:
        data = json.dumps(STORES, indent=2).encode("utf-8")
        # 1️⃣ Önce local /tmp klasörüne yaz
        tmp_path = "/tmp/rds_snapshot.json"
        with open(tmp_path, "wb") as f:
            f.write(data)
        print(f"[INFO] Snapshot written locally to {tmp_path}")

        # 2️⃣ GCS'ye yükle
        if BUCKET_NAME:
            client = storage.Client()
            bucket = client.bucket(BUCKET_NAME)
            blob = bucket.blob(SNAPSHOT_BLOB)
            blob.upload_from_filename(tmp_path)
            print(f"[INFO] Snapshot uploaded to gs://{BUCKET_NAME}/{SNAPSHOT_BLOB}")

    except Exception as e:
        print(f"[ERROR] Failed to upload snapshot to GCS: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload snapshot to GCS.")

    



@app.post("/snapshot")
def create_snapshot():
    _persist_snapshot()
    return {"ok": True, "message": "Snapshot saved to GCS"}


    # 2) Olmazsa /tmp'ye yaz (fallback)
   

def _bump_mutation():
    global _ops_since_last_persist
    with _persist_lock:
        _ops_since_last_persist += 1

def _maybe_persist(force: bool = False):
    global _ops_since_last_persist
    with _persist_lock:
        if force or _ops_since_last_persist >= PERSIST_BATCH_SIZE:
            _persist_snapshot()
            _ops_since_last_persist = 0

@app.on_event("startup")
def _load_snapshot_if_exists():
    try:
        data_bytes = None

        # 1) Önce GCS'ten dene
        if BUCKET_NAME:
            try:
                data_bytes = _gcs_download()
                if data_bytes:
                    print(f"[INFO] Snapshot downloaded from {BUCKET_NAME}/{SNAPSHOT_BLOB}")
            except Exception as e:
                print(f"[WARN] GCS download failed: {e}")

        # 2) GCS yoksa dosyadan dene (lokal fallback)
        if data_bytes is None and os.path.exists(PERSIST_FILE):
            with open(PERSIST_FILE, "rb") as f:
                data_bytes = f.readline()

        # 3) Belleğe yükle
        if data_bytes:
            snap = json.loads(data_bytes.decode("utf-8"))
            STORES.clear(); STORES.update(snap.get("stores", {}))
            lists.clear();  lists.update(snap.get("lists", {}))
            sets_.clear();  sets_.update({k: set(v) for k, v in snap.get("sets", {}).items()})
            print("[INFO] snapshot restored")
        else:
            print("[INFO] no snapshot found; starting fresh")
    except Exception as e:
        print(f"[WARN] snapshot load failed: {e}")


@app.on_event("shutdown")
def _flush_on_shutdown():
    _maybe_persist(force=True)

@app.get("/persist/status")
def persist_status():
    return {
        "file": PERSIST_FILE,
        "batch_size": PERSIST_BATCH_SIZE,
        "ops_since_last_persist": _ops_since_last_persist,
    }

@app.post("/persist/flush")
def persist_flush():
    _maybe_persist(force=True)
    return {"ok": True, "flushed": True, "file": PERSIST_FILE}

# =================================================
# 5) KV UYUMLULUK ENDPOINTİ (/KV)
# =================================================

def _normalize_kv_input(
    store: Optional[str],
    command: Optional[str],
    key: Optional[str],
    value: Optional[str],
    query_json_str: Optional[str],
    payload: Optional[dict]
):
    data = {}
    if payload:
        data.update(payload)
    if query_json_str:
        try:
            qd = json.loads(query_json_str)
            data.update(qd)
        except Exception:
            pass
    if store:   data["store"] = store
    if command: data["command"] = command
    if key is not None:    data["key"] = key
    if value is not None:  data["value"] = value
    if "store" not in data or "command" not in data:
        raise HTTPException(400, "Parameters required: store, command")
    return (
        data.get("store"),
        str(data.get("command")).lower(),
        data.get("key"),
        data.get("value"),
    )

@app.post("/KV")
def kv_compat(
    store: Optional[str] = Query(None),
    command: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    value: Optional[str] = Query(None),
    query: Optional[str] = Query(None, description="JSON string"),
    payload: Optional[dict] = Body(None)
):
    store, cmd, key, val = _normalize_kv_input(store, command, key, value, query, payload)
    s = ensure_store(store)

    if cmd in ("read", "get"):
        if not key:
            raise HTTPException(400, "read requires 'key'")
        if key not in s:
            return {"ok": False, "store": store, "key": key, "found": False, "value": None}
        return {"ok": True, "store": store, "key": key, "found": True, "value": s[key]}

    elif cmd in ("push", "set", "write"):
        if not key:
            raise HTTPException(400, "push requires 'key'")
        s[key] = val
        _bump_mutation(); _maybe_persist()
        return {"ok": True, "store": store, "key": key, "value": s[key]}

    elif cmd in ("del", "delete", "remove"):
        if not key:
            raise HTTPException(400, "del requires 'key'")
        existed = key in s
        if existed:
            del s[key]
            _bump_mutation(); _maybe_persist()
        return {"ok": True, "store": store, "key": key, "deleted": existed}

    elif cmd == "keys":
        keys = sorted(list(s.keys()))
        return {"ok": True, "store": store, "count": len(keys), "keys": keys}

    else:
        raise HTTPException(400, f"Unknown command: {cmd}")

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
