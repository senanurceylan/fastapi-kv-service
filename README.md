# remote-dictionary-service
A simple remote dictionary service with Redis-like commands (LPUSH, LPOP, SPOP) implemented using FastAPI.
# Remote Dictionary Service

## 📌 Amaç / Purpose
- **TR:** Redis benzeri komutlarla çalışan basit bir API geliştirmek.  
- **EN:** Build a simple API working with Redis-like commands.

## 🧩 Desteklenen Komutlar / Supported Commands
- `LPUSH` → Liste başına eleman ekler / Push to head of list  
- `LPOP` → Listenin başından eleman çeker / Pop from head of list  
- `SADD` → Set’e eleman ekler / Add to set  
- `SPOP` → Set’ten rastgele eleman çeker / Pop random element from set  

## 🛠️ Gereksinimler / Requirements
- Python 3.10+  
- pip (Python package manager)

## ⚙️ Kurulum / Installation
```bash
git clone https://github.com/senanurceylan/remote-dictionary-service.git
cd remote-dictionary-service
python -m pip install -r requirements.txt
