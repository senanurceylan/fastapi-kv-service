# fastapi-kv-service
**FastAPI Key-Value API (Memory, Multi-Store)**

Bellekte çalışan bir anahtar–değer (key–value) servisi.  
Çoklu store desteği, temel **list/set** komutları ve **TTL + LRU cache** içerir.  

---

## ✨ Özellikler / Features
- **Multi-Store:** Birden fazla store oluşturulabilir (`/stores/{store}`).
- **Key-Value işlemleri:** `set`, `get`, `del`, `keys`, `items`.
- **TTL/EXPIRE + LRU cache:** `/search` endpoint’inde (varsayılan 300 sn, max 100 kayıt).
- **List/Set komutları:** `LPUSH`, `LPOP`, `SADD`, `SPOP` (demo amaçlı).
- **Healthcheck:** `GET /health` → `{"status":"up","backend":"memory"}`.
- **Swagger UI:** `GET /docs`.

---

## 🧩 Desteklenen Komutlar / Supported Commands
- `LPUSH` → Liste başına eleman ekler / Push to head of list
- `LPOP`  → Listenin başından eleman çeker / Pop from head of list
- `SADD`  → Set’e eleman ekler / Add to set
- `SPOP`  → Set’ten rastgele eleman çeker / Pop random element from set

---

## 🧰 Gereksinimler / Requirements
- Python **3.10+**
- `pip` (Python package manager)

---

## ⚙️ Kurulum / Installation
```bash
# Clone
git clone https://github.com/senanurceylan/fastapi-kv-service.git
cd fastapi-kv-service

# (Optional) Virtualenv
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
uvicorn main:app --host 0.0.0.0 --port 8000
# Swagger: http://127.0.0.1:8000/docs

