# Asistan — Güvenlik Modeli

## 1. Rol Bazlı Erişim Kontrolü (RBAC)

Merkezi modül: `core/permissions.py`

### Roller

| Rol | Açıklama | Yetki Seviyesi |
|---|---|---|
| `admin` | Tam yetki | Tüm tool'lara erişim |
| `hr` | İnsan kaynakları | İzin onaylama + genel tool'lar |
| `employee` | Standart çalışan | Kendi verilerine erişim |

### Akış

```
Kullanıcı mesajı
    → Router (kategori seçimi)
    → Tool seçimi
    → permissions.check(user_role, tool_name)
        → İzin var mı?
            ✅ → Onay gerekli mi?
                ✅ → approval.request() → Kullanıcıya onay sorusu
                ❌ → Direkt çalıştır
            ❌ → "Yetkiniz yok" hatası
```

Her tool çağrısı `check_permission()` fonksiyonundan geçer. Tool'lar kendi içlerinde yetki kontrolü yapmaz.

## 2. Onay Mekanizması

Merkezi modül: `core/approval.py`

### Onay Gerektiren Tool'lar

```python
REQUIRES_APPROVAL = {
    "db_delete", "db_update",
    "file_delete", "file_move",
    "git_commit_and_push", "github_create_pull_request",
    "approve_leave",
    "mail_send",
    "calendar_add_event", "calendar_delete_event",
}
```

### Onay Akışı

1. Tool executor onay gerektiren tool'u tespit eder
2. `approval_manager.request()` çağrılır → UUID onay ID'si oluşturulur
3. Kullanıcıya onay sorusu gösterilir (UI veya API)
4. Kullanıcı `POST /approve/{id}` veya `POST /reject/{id}` ile yanıtlar
5. Onay verilirse tool çalıştırılır, reddedilirse işlem iptal edilir
6. Onay isteğinin süresi dolabilir (TTL)

## 3. Sandbox İzolasyonu

### Dosya Sistemi
- Tüm dosya işlemleri `SANDBOX_ROOT` dizini içinde kısıtlıdır
- Path traversal saldırıları (`../../etc/passwd`) `_safe_path()` ile engellenir
- Sembolik link takibi yapılmaz (sandbox dışına link → reddedilir)

### Kod Çalıştırma
- `code_run` Docker container içinde çalışır
- Host dosya sistemine erişim yoktur
- Zaman aşımı limiti vardır

## 4. API Güvenliği

### Faz 1 (Mevcut) — Statik API Key
```
X-API-Key: dev-api-key-change-in-production
```
- Tüm HTTP endpoint'leri bu header'ı gerektirir
- WebSocket bağlantısında query parametresi olarak alınır

### İleri Faz — JWT Tabanlı Auth
- Kullanıcı bazlı token'lar
- Token yenileme (refresh)
- Oturum yönetimi

## 5. Loglama

Merkezi modül: `core/logger.py`

Her tool çağrısı `tool_call_logs` tablosuna yazılır:

| Alan | Açıklama |
|---|---|
| `timestamp` | Çağrı zamanı |
| `user_id` | Çağıran kullanıcı |
| `tool_name` | Çağrılan tool |
| `parameters_json` | Parametreler |
| `result_json` | Sonuç |
| `approved_by` | Onaylayan (varsa) |
| `status` | success / error / rejected / pending |
| `duration_ms` | İşlem süresi |

## 6. Kapsam DIŞI (Bilinçli Kısıtlar)

Bu proje bilinçli olarak şunları **içermez**:
- ❌ Force push
- ❌ Serbest SQL yazma/silme (sadece parametrik sorgular)
- ❌ Tam otonom ekran kontrolü (computer use)
- ❌ Spotify/YouTube playback kontrolü
- ❌ Kullanıcı onayı olmadan yazma/silme işlemleri

## 7. Sır Yönetimi

- Tüm API key'ler ve token'lar `.env` dosyasında tutulur
- `.env` dosyası `.gitignore`'a dahildir
- Kod içine hiçbir secret hardcode edilmez
- Model adı bile `.env`'den okunur (gelecekte model değişikliği tek satır)
