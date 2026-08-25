# 🚀 Deploy final: GitHub (drag & drop) + Koyeb + Neon

Rezultat: bot non-stop, gratuit, fără card, cu playlisturile permanente pe Neon.

Nu instalezi nimic — totul prin browser.

---

## PARTEA A — Urcă botul pe GitHub (prin site)

### A1. Fă-ți cont GitHub
- Intră pe **https://github.com** → **Sign up** (gratuit, fără card).

### A2. Creează un repository
1. Sus dreapta, apasă **+** → **New repository**.
2. **Repository name**: `melodix-bot` (sau ce vrei).
3. Alege **Private** (recomandat, ca să nu-l vadă alții).
4. NU bifa nimic la „Initialize" (lasă gol).
5. Apasă **Create repository**.

### A3. Urcă fișierele (drag & drop)
1. Pe pagina noului repo apasă linkul **„uploading an existing file”**
   (sau: tab **Add file** → **Upload files**).
2. Pe laptop, deschide folderul `telegram-music-bot`.
3. Selectează TOT ce e înăuntru și trage în pagina GitHub:
   - folderul `bot`
   - folderul `deploy`
   - `Dockerfile`
   - `requirements.txt`
   - `.env.example`
   - `.gitignore`
   - `README.md`, `run.bat`, etc.

   ⚠️ NU urca: folderul `.venv`, `data`, `downloads`, fișierul `.env`
   (acestea nu sunt necesare și `.env` conține tokenul — trebuie să rămână secret).

   > Notă: dacă drag & drop nu prinde subfolderele, urcă-le pe rând
   > (întâi `bot`, apoi `deploy`), sau folosește „Add file → Upload files"
   > de mai multe ori.
4. Jos, la **Commit changes**, apasă **Commit changes**.

Gata — codul e pe GitHub.

---

## PARTEA B — Deploy pe Koyeb

### B1. Fă-ți cont Koyeb
- Intră pe **https://www.koyeb.com** → **Sign up** → alege
  **Sign up with GitHub** (leagă direct contul, fără card).

### B2. Creează serviciul
1. În dashboard apasă **Create Service** (sau **Create Web Service**).
2. Sursă: **GitHub** → autorizează Koyeb să-ți vadă repo-urile →
   alege repo-ul **melodix-bot**.
3. Koyeb detectează automat **Dockerfile**-ul. Dacă întreabă „Builder",
   alege **Dockerfile**.

### B3. Setează tipul corect (IMPORTANT)
Botul folosește long-polling, nu are pagină web. În setările serviciului:
- La **Service type** / **Ports**: dacă îți cere un port, botul NU are unul.
  Caută opțiunea **Worker** (fără port public) dacă există.
- Dacă Koyeb cere obligatoriu un port „web", lasă valoarea default —
  botul tot merge, doar că health-check-ul pe port va fi ignorat.

### B4. Adaugă variabilele de mediu (Environment variables)
Adaugă exact aceste două variabile:

| Name | Value |
|------|-------|
| `BOT_TOKEN` | tokenul tău de la @BotFather |
| `DATABASE_URL` | connection string-ul de la Neon (vezi mai jos) |

**DATABASE_URL** (de la Neon, fără `&channel_binding=require` la final):
```
postgresql://neondb_owner:PAROLA@ep-....eu-central-1.aws.neon.tech/neondb?sslmode=require
```

### B5. Alege planul gratuit
- La **Instance**, alege tipul **Free** (Nano / Free eco).
- Regiune: **Frankfurt** (aproape de tine), dacă e disponibilă.

### B6. Deploy
- Apasă **Deploy**. Koyeb construiește imaginea (2-5 min) și pornește botul.

---

## Verificare
- În Koyeb, tab **Logs** → trebuie să vezi:
  ```
  Using PostgreSQL storage backend
  Database ready (PostgreSQL)
  Running as @TextRamabot
  Bot is up. Press Ctrl+C to stop.
  ```
- Deschide botul în Telegram → `/start`. Fă un playlist cu `/playlist`.
- Playlisturile sunt acum în Neon → permanente, nu se pierd la restart.

---

## Actualizezi codul mai târziu?
1. Pe GitHub: **Add file → Upload files** → urci fișierele modificate → Commit.
2. Koyeb detectează schimbarea și **redeployează automat**.

## ⚠️ Securitate
- **Resetează parola Neon** (ai postat-o în chat): Neon dashboard → **Roles**
  → **Reset password**. Apoi actualizează `DATABASE_URL` în Koyeb.
- Dacă vrei, **regenerează tokenul** în @BotFather și actualizează `BOT_TOKEN`.
