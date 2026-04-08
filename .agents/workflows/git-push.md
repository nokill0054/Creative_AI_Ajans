---
description: Her revision sonrası otomatik olarak GitHub'a commit ve push yapar
---

# Auto Git Push Workflow

Her dosya değişikliğinden sonra bu adımları izle:

// turbo-all

## Adımlar

1. Değişiklikleri staging'e ekle:
```bash
cd "/Users/nokillnokill/Desktop/antigravity projects/Creative_AI_Ajans/creative-engine-template" && git add -A
```

2. Commit mesajı oluştur (değişikliğe uygun kısa açıklama ile):
```bash
cd "/Users/nokillnokill/Desktop/antigravity projects/Creative_AI_Ajans/creative-engine-template" && git commit -m "<değişiklik açıklaması>"
```

3. GitHub'a push et:
```bash
cd "/Users/nokillnokill/Desktop/antigravity projects/Creative_AI_Ajans/creative-engine-template" && GIT_TERMINAL_PROMPT=0 git push origin master
```

## Notlar
- Bu workflow her **dosya değişikliği/düzeltme** sonrasında otomatik çalıştırılmalıdır
- Commit mesajı değişikliği açıklayıcı olmalıdır (Conventional Commits formatında: `feat:`, `fix:`, `refactor:` vb.)
- Push başarısız olursa (token süresi dolmuşsa) kullanıcıya bildir
