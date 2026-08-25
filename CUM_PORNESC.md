# ▶️ Cum pornesc botul (ghid final)

Botul are: căutare muzică după titlu / artist / versuri (cea mai populară
melodie prima), buton „Mai multe melodii”, versuri și „mai multe de la artist”,
/cut pe melodiile primite, sistem de playlisturi cu cod partajabil,
clasamente (/top) și 11 limbi.

---

## ✅ Comanda care ACTIVEAZĂ botul

După ce ai instalat **Python** și **ffmpeg** (vezi mai jos), deschide un
terminal în folderul `telegram-music-bot` și rulează:

```cmd
run.bat
```

Atât. `run.bat` face automat tot: creează mediul virtual, instalează
pachetele, scrie fișierul `.env` cu tokenul și pornește botul.

> Alternativ, poți da **dublu-click** pe fișierul `run.bat` din folder.

Când vezi în terminal:
```
Bot is up. Press Ctrl+C to stop.
```
✅ botul funcționează. Deschide-l în Telegram și trimite `/start`.

Ca să oprești botul: apasă `Ctrl+C` în terminal.

---

## 📋 Ce trebuie instalat ÎNAINTE (o singură dată)

### 1. Python (orice versiune 3.11, 3.12, 3.13 sau 3.14 merge)
- Descarcă de la https://www.python.org/downloads/
- La instalare pe Windows: **bifează „Add Python to PATH”**.

#### Dacă ai încercat înainte și ai o eroare veche, curăță și reinstalează:
1. Șterge folderul `.venv` din `telegram-music-bot`.
2. Rulează `run.bat` — recreează totul curat.

### 2. ffmpeg (obligatoriu pentru descărcare + tăiere)
- Descarcă `ffmpeg-release-essentials.zip` de la
  https://www.gyan.dev/ffmpeg/builds/
- Dezarhivează în `C:\ffmpeg` (înăuntru ai folderul `bin` cu `ffmpeg.exe`)
- Adaugă `C:\ffmpeg\bin` la variabila de mediu **Path**:
  - `Win` → caută „environment variables” → *Edit the system environment
    variables* → **Environment Variables…** → la *System variables* selectează
    **Path** → **Edit** → **New** → scrie `C:\ffmpeg\bin` → OK peste tot
- **Redeschide** terminalul și verifică: `ffmpeg -version`

---

## 🔁 Data viitoare
Doar deschizi folderul și rulezi din nou:
```cmd
run.bat
```
Nu reinstalează nimic dacă e deja instalat — pornește direct.

---

## 🎮 Cum se folosește botul în Telegram

- **/start** → alegi limba (11 limbi disponibile)
- **Cauți muzică** → scrii titlul, artistul sau un vers din text. Prima melodie
  e cea mai populară. Apeși **„Mai multe melodii”** pentru mai multe rezultate.
  Sub fiecare melodie trimisă apare semnătura **@numele_botului**, plus butoane
  **„Versuri”** și **„Mai multe de la artist”**.
- **/cut** → alegi o melodie pe care botul ți-a trimis-o deja, apoi trimiți
  intervalul (ex. `00:00:30 00:01:15`) → primești fragmentul tăiat.
- **/playlist** → creezi un playlist (primești un **cod**), îl arăți prietenilor;
  ei îl deschid cu „Deschide după cod”. Adaugi melodii cu butonul „În playlist”
  de sub fiecare melodie primită.
- **/top** → clasamentul celor mai populare playlisturi și al utilizatorilor
  cu cele mai multe melodii descărcate.
- **/language** → schimbi limba · **/help** → ajutor

---

## 🎨 Nume, descriere și iconiță (se fac o singură dată)

**Numele și descrierea** se setează AUTOMAT la pornirea botului (prin cod), deci
nu trebuie să faci nimic — apar singure:
- Nume: **Melodix — Music Finder**
- Descriere scurtă + descrierea completă (textul „Ce poate face acest bot?”)

Vrei alt nume/descriere? Editează funcția `set_bot_profile` din `bot/main.py`.

**Iconița (poza de profil)** NU poate fi setată din cod — o încarci manual în
@BotFather (o singură dată):
1. Am generat o iconiță gata de folosit: fișierul **`assets/bot_icon.png`**
   din folderul proiectului.
2. În Telegram deschide **@BotFather** → `/mybots` → alege botul tău →
   **Edit Bot** → **Edit Botpic**.
3. Trimite fișierul `assets/bot_icon.png`. Gata — asta e iconița botului.

---

## ⚠️ Important
- **Regenerează tokenul** în @BotFather (l-ai postat în chat): `/mybots` →
  botul tău → *API Token* → *Revoke current token*. Apoi înlocuiește valoarea
  `BOT_TOKEN=` din fișierul `.env`.
- Melodiile descărcate se **șterg automat** după trimitere — nu se adună pe disc.
