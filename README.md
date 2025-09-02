# fastapi-kv-service
**FastAPI Key-Value API (Redis-ready, Memory fallback)**

Redis varsa onu, yoksa **bellek** kullanan  bir anahtar–değer (key–value) servisi. **TTL/EXPIRE**, **/search için LRU cache** ve temel **list/set** komutları içerir. Docker ile çalışır; Cloud’a hazırdır.

---

## ✨ Özellikler / Features
- **Redis (opsiyonel)** → `REDIS_URL` ile bağlanır; erişilemezse **memory fallback**
- **TTL/EXPIRE** ve **LRU cache** (`/search`, varsayılan 300 sn, max 100 kayıt)
- Temel **list/set** komutları: `LPUSH`, `LPOP`, `SADD`, `SPOP`
- **Healthcheck:** `GET /health` → `{"status":"up","backend":"redis|memory"}`
- **Swagger UI:** `GET /docs`

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

# Environment (.env)
echo REDIS_URL=redis://127.0.0.1:6379/0 > .env

# Run
uvicorn main:app --host 0.0.0.0 --port 8000
# Swagger: http://127.0.0.1:8000/docs


