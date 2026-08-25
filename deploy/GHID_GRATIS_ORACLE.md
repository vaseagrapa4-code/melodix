# 🆓 Găzduire GRATUITĂ non-stop cu playlisturi păstrate — Oracle Cloud

Aceasta e cea mai bună opțiune **cu adevărat gratuită** (gratis pentru
totdeauna, nu trial) care:
- ✅ ține botul pornit **24/7**, non-stop
- ✅ **NU adoarme** (spre deosebire de Render free)
- ✅ **păstrează playlisturile** (fișierul `data/bot.db` stă pe disc real)
- ✅ repornește botul singur dacă pică sau dacă serverul se restartează

Vei crea un mic server Linux gratuit (VPS) și vei rula botul pe el.

---

## Partea 1 — Creează serverul gratuit Oracle (o singură dată)

1. Intră pe **https://www.oracle.com/cloud/free/** și apasă **Start for free**.
2. Creează cont (îți cere un card pentru verificare, dar resursele
   **Always Free NU se taxează** — nu plătești nimic dacă rămâi pe ele).
3. După ce intri în consolă, apasă **Create a VM instance** (Compute → Instances → Create).
4. Setări recomandate:
   - **Image**: Ubuntu 22.04 (sau 24.04)
   - **Shape**: alege una marcată **„Always Free-eligible”**
     - `VM.Standard.E2.1.Micro` (x86), SAU
     - `VM.Standard.A1.Flex` cu 1 OCPU / 6 GB (ARM, mai puternic — recomandat)
   - La **Add SSH keys**: alege **Generate a key pair for me** și
     **descarcă cheia privată** (fișierul `.key`). O păstrezi bine.
5. Apasă **Create**. După ~1 minut, notează **Public IP address**-ul instanței.

---

## Partea 2 — Conectează-te la server

### Windows (folosind PowerShell)
Deschide PowerShell în folderul unde ai salvat cheia și rulează
(înlocuiește `IP_UL_TAU` și numele cheii):

```powershell
ssh -i .\ssh-key.key ubuntu@IP_UL_TAU
```

Dacă îți cere permisiuni pe cheie, rulează întâi:
```powershell
icacls .\ssh-key.key /inheritance:r
icacls .\ssh-key.key /grant:r "$($env:USERNAME):(R)"
```

La prima conectare scrie **yes**. Ești acum pe server.

---

## Partea 3 — Pune botul pe server și pornește-l

Pe server (în terminalul SSH), rulează pe rând:

### 3a. Instalează git și adu proiectul
Ai două variante ca să urci fișierele:

**Varianta A — prin GitHub (recomandat):**
```bash
sudo apt-get update -y && sudo apt-get install -y git
git clone <URL-ul-repo-ului-tău> telegram-music-bot
cd telegram-music-bot
```

**Varianta B — copiezi de pe laptop cu SCP** (rulezi pe LAPTOP, nu pe server):
```powershell
scp -i .\ssh-key.key -r C:\Users\user\Desktop\telegram-music-bot ubuntu@IP_UL_TAU:/home/ubuntu/
```
Apoi pe server: `cd telegram-music-bot`

### 3b. Rulează scriptul de instalare (face TOT automat)
```bash
bash deploy/setup.sh
```
Instalează Python, ffmpeg, dependențele și configurează pornirea automată.

### 3c. Pune tokenul
```bash
nano .env
```
Găsește linia `BOT_TOKEN=` și lipește tokenul de la @BotFather.
Salvează cu **Ctrl+O**, Enter, apoi **Ctrl+X**.

### 3d. Pornește botul
```bash
sudo systemctl start melodix-bot
sudo systemctl status melodix-bot
```
Dacă vezi **active (running)** verde → botul merge! Deschide-l în Telegram.

---

## Comenzi utile (pe server)

| Ce vrei | Comandă |
|---|---|
| Vezi logurile live | `journalctl -u melodix-bot -f` |
| Repornește botul | `sudo systemctl restart melodix-bot` |
| Oprește botul | `sudo systemctl stop melodix-bot` |
| Stare bot | `sudo systemctl status melodix-bot` |

Botul pornește **automat** la fiecare restart al serverului și se
**repornește singur** dacă pică. Nu trebuie să faci nimic manual.

---

## Despre playlisturi (important)

Playlisturile + limba utilizatorilor stau în fișierul **`data/bot.db`** pe
discul serverului. Pe Oracle acest disc e **permanent**, deci datele
**NU se pierd** la restart/redeploy (spre deosebire de Render free).

### Backup rapid al playlisturilor (opțional)
Ca să faci o copie de siguranță, rulează pe LAPTOP:
```powershell
scp -i .\ssh-key.key ubuntu@IP_UL_TAU:/home/ubuntu/telegram-music-bot/data/bot.db .\bot-backup.db
```

---

## Actualizarea botului mai târziu
Când modifici codul, pe server:
```bash
cd telegram-music-bot
git pull                 # sau re-copiezi fișierele cu scp
sudo systemctl restart melodix-bot
```

---

## De ce Oracle și nu Render free?

| | Oracle Free | Render Free |
|---|---|---|
| Non-stop (nu adoarme) | ✅ | ❌ (adoarme în 15 min) |
| Playlisturi păstrate | ✅ disc permanent | ❌ disc efemer |
| Gratis permanent | ✅ | ✅ (dar cu limitări) |
| Potrivit pt. bot cu polling | ✅ | ⚠️ necesită hack-uri |

Dacă vrei o alternativă și mai simplă de creat cont (fără card), spune-mi
și îți fac ghid pentru **Fly.io** sau **Railway**.
