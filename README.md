# 🚀 Rfastapi-kv-Service (FastAPI, Memory, GCS Snapshot)

**FastAPI tabanlı çoklu bellek (multi-store) key–value servisi.**  
Veriler bellek üzerinde tutulur, her N mutasyonda otomatik olarak **Google Cloud Storage (GCS)** üzerine yedeklenir.  
Ayrıca **Docker** ve **Cloud Run** desteğiyle bulut üzerinde container olarak çalıştırılabilir.  

---

## ✨ Özellikler / Features
- **Multi-Store:** Birden fazla store oluşturulabilir (`/stores/{store}`)
- **Key-Value İşlemleri:** `set`, `get`, `delete`, `update`, `keys`, `items`
- **List/Set Komutları:** `LPUSH`, `LPOP`, `SADD`, `SPOP` (demo amaçlı)
- **LRU + TTL Cache:** `/search` endpoint’inde cache mekanizması (varsayılan 300 sn, max 100 kayıt)
- **Snapshot:** Her N mutasyonda otomatik GCS’ye yedekleme
- **Health Check:** `GET /health` → `{ "status": "up", "backend": "memory" }`
- **Swagger UI:** `GET /docs` üzerinden test arayüzü


![WhatsApp Görsel 2025-10-25 saat 15 02 26_dfba9a93](https://github.com/user-attachments/assets/8708d1c3-1fea-482b-82ea-aa1e5988ebb1)

---
![WhatsApp Görsel 2025-10-25 saat 15 03 51_2dfe94f4](https://github.com/user-attachments/assets/6217dc11-445e-44f9-acc9-cd2599b32403)
---
![WhatsApp Görsel 2025-10-25 saat 15 04 41_709594e6](https://github.com/user-attachments/assets/48e14663-dc5e-4b2c-a1f3-fc7af97a78ed)

---


![WhatsApp Görsel 2025-10-25 saat 15 05 29_89733f0b](https://github.com/user-attachments/assets/eda0d6cf-d006-4cc2-bd05-9960e61c3ddf)

---
![WhatsApp Görsel 2025-10-25 saat 15 05 57_8ca78529](https://github.com/user-attachments/assets/05d4831a-d3ec-4bea-80da-47d23d77ee77)

---
![WhatsApp Görsel 2025-10-25 saat 15 06 30_6c916624](https://github.com/user-attachments/assets/9bd459e7-19ae-41a3-be2b-b150b2fdad89)


## 🧩 Kullanılan Teknolojiler / Tech Stack
| Araç / Kütüphane | Amaç |
|------------------|------|
| **FastAPI** | API framework |
| **Python** | Backend dili |
| **Google Cloud Storage (GCS)** | Snapshot yedekleme |
| **Docker** | Container ortamı |
| **Cloud Run** | Bulut dağıtımı |
| **dotenv** | Ortam değişkeni yönetimi |
| **atomicwrites** | Güvenli dosya yazımı |


![WhatsApp Görsel 2025-10-25 saat 15 12 46_ec4be3ea](https://github.com/user-attachments/assets/cf9e7932-455e-45c1-9afb-83db0eca0a04)

---
![WhatsApp Görsel 2025-10-25 saat 15 14 04_40c8e4a9](https://github.com/user-attachments/assets/39c6dab4-f597-4925-9a38-af09c8d2de82)


## ⚙️ Kurulum / Installation
```bash
# Clone
git clone https://github.com/senanurceylan/remote-data-service.git
cd remote-data-service

# (Optional) Virtualenv
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
uvicorn main:app --reload
---
<img width="1117" height="850" alt="00c62fcd-f943-415f-8dd7-6847d8f13968" src="https://github.com/user-attachments/assets/ffb553fe-38c8-4044-808a-b6d45ef18f1e" />

