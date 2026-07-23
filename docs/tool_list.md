# Asistan — Tool Listesi

> Toplam: **7 kategori, 35 tool/bileşen**

## Kategori: `dosya` (filesystem server)

| Tool | Açıklama | Onay |
|---|---|---|
| `file_read(path)` | Dosya içeriğini okur | ❌ |
| `file_write(path, content)` | Dosya oluşturur/üzerine yazar | ✅ |
| `file_delete(path)` | Dosya siler | ✅⚠️ |
| `file_list(directory)` | Klasördeki dosyaları listeler | ❌ |
| `file_move(src, dst)` | Dosya taşır/yeniden adlandırır | ✅ |

## Kategori: `veritabani` (database + hr server)

| Tool | Açıklama | Onay |
|---|---|---|
| `db_list_tables()` | Tabloları listeler | ❌ |
| `db_get_schema(table)` | Tablo şemasını gösterir | ❌ |
| `db_query(table, filters)` | Filtreyle veri çeker | ❌ |
| `db_insert(table, values)` | Yeni kayıt ekler | ✅ |
| `db_update(table, id, values)` | Kayıt günceller | ✅ |
| `db_delete(table, id)` | Kayıt siler | ✅⚠️ |
| `get_employee_leave_balance(name, requester)` | İzin bakiyesi sorgular | Rol kontrolü |
| `get_employees_on_leave(date)` | İzinli çalışanları listeler | ❌ |
| `request_leave(employee_name, start_date, end_date, type)` | İzin talebi oluşturur | ✅ |
| `approve_leave(request_id, approver_role)` | İzin onaylar | ✅ + HR rolü |

## Kategori: `kod_git` (code + git server)

| Tool | Açıklama | Onay |
|---|---|---|
| `code_run(path, language)` | Docker sandbox içinde kod çalıştırır | ❌ (sandbox) |
| `code_lint(path)` | Sözdizim/hata kontrolü | ❌ |
| `git_status(repo_path)` | Değişiklik durumunu gösterir | ❌ |
| `git_diff_preview(repo_path)` | Değişiklik özetini gösterir | ❌ |
| `git_create_branch(repo_path, branch_name)` | Yeni branch oluşturur | ❌ |
| `git_commit_and_push(repo_path, message, branch)` | Commit + push | ✅ |
| `github_create_pull_request(repo, branch, title)` | PR açar | ✅ |

## Kategori: `mail_takvim` (mail_calendar server → n8n)

| Tool | Açıklama | Onay |
|---|---|---|
| `mail_read_inbox(count)` | Son N maili okur | ❌ |
| `mail_send(to, subject, body)` | Mail gönderir | ✅ |
| `mail_extract_meeting(mail_id)` | Mailden toplantı bilgisi çıkarır | ❌ |
| `calendar_list_events(date)` | Etkinlikleri listeler | ❌ |
| `calendar_add_event(title, date, time, duration)` | Etkinlik ekler | ✅ |
| `calendar_delete_event(event_id)` | Etkinlik siler | ✅⚠️ |

## Kategori: `uygulama` (app server)

| Tool | Açıklama | Onay |
|---|---|---|
| `app_open(name)` | Uygulama açar | ❌ |
| `app_close(name)` | Uygulama kapatır | ❌ |
| `app_list_running()` | Açık uygulamaları listeler | ❌ |

## Kategori: `gorsel_ses` (multimodal)

| Bileşen | Açıklama | Bağımlılık |
|---|---|---|
| `stt_transcribe(audio_path)` | Ses → Metin | openai-whisper |
| `tts_speak(text)` | Metin → Ses | pyttsx3 |
| `vision_describe(image_path)` | Görsel → Açıklama | Ollama qwen2-vl |
| `image_generate(prompt)` | Metin → Görsel | AUTOMATIC1111 / Stable Diffusion |
| `wake_word_listen()` | "Hey Asistan" dinler | pvporcupine |

## Onay İşareti Rehberi

- ❌ = Onay gerektirmez (güvenli okuma işlemi)
- ✅ = Kullanıcı onayı gerektirir
- ✅⚠️ = Kritik işlem — vurgulu onay
