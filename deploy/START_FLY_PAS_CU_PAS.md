# 🚀 Deploy pe Fly.io — de la zero, pas cu pas

Ai deja: contul Fly, aplicația `user-peaceful-lagoon-340` și volumul
`melodix_data`. Nu le mai recreăm — doar le folosim.

---

## PASUL 0 — Deschide PowerShell ÎN folderul botului

Asta e cheia (până acum erai în folderul greșit).

1. Deschide **File Explorer** (Exploratorul de fișiere).
2. Mergi la: `Desktop` → intră în folderul **`telegram-music-bot`**.
   (Înăuntru trebuie să vezi: folderul `bot`, `Dockerfile`, `fly.toml`,
   `requirements.txt`.)
3. Click în **bara de adresă** de sus (unde scrie calea folderului).
4. Șterge tot ce e acolo, scrie **`powershell`** și apasă **Enter**.

Se deschide terminalul direct în folderul corect. Trebuie să vezi în stânga:
```
PS C:\Users\user\Desktop\telegram-music-bot>
```
Dacă vezi asta — ești în locul potrivit. ✅

---

## PASUL 1 — Verifică fișierul fly.toml

În PowerShell scrie:
```powershell
notepad fly.toml
```

Se deschide Notepad. Șterge TOT și lipește EXACT asta:

```toml
app = "user-peaceful-lagoon-340"
primary_region = "fra"

[build]
  dockerfile = "Dockerfile"

[mounts]
  source = "melodix_data"
  destination = "/data"

[env]
  DATABASE_PATH = "/data/bot.db"
  DOWNLOAD_DIR = "/tmp/downloads"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

Salvează cu **Ctrl+S**, apoi închide Notepad.

> De ce contează: `app = ...` spune Fly care aplicație e (altfel eroarea
> „missing an app name"). Secțiunea `[mounts]` face ca playlisturile să NU se
> piardă la restart.

---

## PASUL 2 — Pune tokenul botului

În PowerShell (înlocuiește cu tokenul tău dacă l-ai regenerat):
```powershell
fly secrets set BOT_TOKEN=8819981639:AAGeGKv59bY9MLb-s_tS_astVcAx6JvVB9o
```
Trebuie să vezi: `Secrets are staged for the first deployment`.

---

## PASUL 3 — Pornește botul (deploy)

```powershell
fly deploy
```

Durează 2-5 minute (construiește imaginea). La final trebuie să vezi ceva de
genul: `1 desired, 1 placed, 1 healthy` sau `deployed successfully`.

Deschide botul în Telegram și trimite `/start`. 🎉

---

## Comenzi utile după deploy

| Ce vrei | Comandă |
|---|---|
| Vezi logurile live | `fly logs` |
| Starea botului | `fly status` |
| Repornește | `fly apps restart user-peaceful-lagoon-340` |
| Schimbă tokenul | `fly secrets set BOT_TOKEN=...` |

---

## Dacă apare o eroare
- **„missing an app name”** → fly.toml nu are `app = "..."`. Refă PASUL 1.
- **„does not have a Dockerfile”** → nu ești în folderul botului. Refă PASUL 0.
- Orice altă eroare → rulează `fly logs` și trimite ce apare.
