import requests
import json
import uuid

# Backend API URL'si
API_URL = "http://localhost:8000/chat"
HEADERS = {"X-API-Key": "dev-api-key-change-in-production"}
SESSION_ID = str(uuid.uuid4())

print("======================================================")
print("🤖 ASİSTAN'A HOŞ GELDİNİZ (Etkileşimli Terminal)")
print("Backend'e bağlanıldı: http://localhost:8000")
print("Çıkmak için 'q' veya 'exit' yazın.")
print("======================================================\n")

while True:
    user_input = input("👤 Siz: ")
    if user_input.lower() in ['q', 'exit', 'çıkış']:
        print("Görüşmek üzere!")
        break
    
    if not user_input.strip():
        continue
    
    payload = {
        "message": user_input,
        "session_id": SESSION_ID
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=HEADERS)
        response.raise_for_status()
        
        data = response.json()
        print(f"\n🤖 Asistan: {data.get('message', '')}")
        
        # Eğer onay bekleyen bir işlem varsa göster
        pending_approval = data.get('pending_approval')
        if pending_approval:
            print(f"\n⚠️ [ONAY BEKLENİYOR] İşlem: {pending_approval['action']}")
            print(f"Onay ID: {pending_approval['id']}")
            print(f"Onaylamak için backend'e istek atmanız gerekir.")
            
        print("-" * 50)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ HATA: Backend'e ulaşılamadı. 'uvicorn api.main:app' komutunun çalıştığından emin olun.")
    except Exception as e:
        print(f"\n❌ HATA: {e}")
