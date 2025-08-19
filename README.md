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

## 🚀 Kullanım Örnekleri / Usage Examples

### 🐚 cURL ile / With cURL
#### LPUSH
```bash
curl -X POST "http://127.0.0.1:8000/command" -H "Content-Type: application/json" -d '{"command":"LPUSH","stack_name":"mylist","value":"apple"}'
#### LPOP
curl -X POST "http://127.0.0.1:8000/command" -H "Content-Type: application/json" -d '{"command":"LPOP","stack_name":"mylist"}'
#### SADD
curl -X POST "http://127.0.0.1:8000/command" -H "Content-Type: application/json" -d '{"command":"SADD","stack_name":"myset","value":"banana"}'
#### SPOP
curl -X POST "http://127.0.0.1:8000/command" -H "Content-Type: application/json" -d '{"command":"SPOP","stack_name":"myset"}'

### 🌐 Swagger UI
## 🧪 Testler / Tests

- TR: Komut endpoint’leri için otomatik testler eklendi (LPUSH, LPOP, SADD, SPOP).
- EN: Automated tests added for command endpoints (LPUSH, LPOP, SADD, SPOP).

## 🗂️ .gitignore Düzenlemesi / .gitignore Update

- TR: Gereksiz dosyalar (ör: `__pycache__`, `.env`) versiyon kontrolünden hariç tutuldu.  
- EN: Unnecessary files (e.g., `__pycache__`, `.env`) excluded from version control.

- TR: Proje çalıştığında [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) adresinden tarayıcıyla Swagger arayüzüne girip komutları test edebilirsiniz.  
- EN: When the project is running, go to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) in your browser to test the commands via Swagger UI.  


