# 🚀 Deploy pe Render (gratuit, fără card) + Neon

Koyeb s-a închis (a fost cumpărat de Mistral). Folosim **Render** — free, fără
card. Ai deja tot ce trebuie: repo pe GitHub + baza de date Neon.

Playlisturile sunt pe **Neon**, deci sunt permanente indiferent de platformă.

---

## PARTEA 1 — Actualizează codul pe GitHub

Am adăugat un mic „keep-alive" ca Render free să nu adoarmă botul. Trebuie să
urci versiunea nouă:

1. Descarcă `melodix-bot.zip` (versiunea nouă) și dezarhiveaz-o.
2. Pe GitHub, în repo-ul `melodix-bot`: **Add file → Upload files**.
3. Trage TOATE fișierele din folderul dezarhivat (înlocuiește-le pe cele vechi).
4. **Commit changes**.

(Fișiere noi importante: `render.yaml`, `bot/utils/keepalive.py`.)

---

## PARTEA 2 — Creează serviciul pe Render

1. Intră pe **https://render.com** → **Get Started** → **Sign in with GitHub**
   (gratuit, fără card).
2. În dashboard apasă **New +** → **Web Service**.
3. Conectează / alege repo-ul **melodix-bot**.
4. Setări:
   - **Language / Runtime**: alege **Docker** (Render detectează `Dockerfile`).
   - **Instance Type**: **Free**.
   - **Region**: Frankfurt (aproape de tine), dacă e disponibil.
5. La **Environment Variables**, adaugă două:

   | Key | Value |
   |-----|-------|
   | `BOT_TOKEN` | tokenul tău de la @BotFather |
   | `DATABASE_URL` | connection string-ul de la Neon (fără `&channel_binding=require`) |

   `DATABASE_URL` arată așa:
   ```
   postgresql://neondb_owner:PAROLA@ep-....eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
6. Apasă **Create Web Service**.

Render construiește imaginea (2-5 min) și pornește botul.

---

## PARTEA 3 — Ține botul treaz (important pe planul free)

Render free adoarme serviciul după ~15 min fără trafic. Ca să rămână pornit:

1. Copiază URL-ul serviciului tău Render (arată ca
   `https://melodix-bot.onrender.com`).
2. Intră pe **https://uptimerobot.com** → cont gratuit (fără card).
3. **Add New Monitor**:
   - Type: **HTTP(s)**
   - URL: `https://melodix-bot.onrender.com/health`
   - Interval: **5 minutes**
4. Salvează.

UptimeRobot face ping la fiecare 5 min → Render nu mai adoarme → botul merge
non-stop.

---

## Verificare
- În Render, tab **Logs** → trebuie să vezi:
  ```
  Using PostgreSQL storage backend
  Keep-alive HTTP server listening on port ...
  Running as @TextRamabot
  Bot is up. Press Ctrl+C to stop.
  ```
- Telegram → `/start` → fă un playlist. E salvat în Neon (permanent).

---

## ⚠️ Securitate
- **Resetează parola Neon** (ai postat-o în chat): Neon → **Roles** →
  **Reset password**, apoi actualizează `DATABASE_URL` în Render.
- Ține repo-ul GitHub pe **Private**.

---

## Note oneste despre Render free
- 750 ore/lună gratis (suficient pentru 1 bot non-stop).
- Cu UptimeRobot rămâne treaz; fără el, adoarme.
- Prima cerere după inactivitate poate fi lentă (~30s) — normal pe free.
- Playlisturile NU depind de Render (sunt pe Neon), deci sunt mereu în siguranță.
