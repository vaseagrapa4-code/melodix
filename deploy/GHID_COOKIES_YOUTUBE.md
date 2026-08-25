# 🍪 Repară „Sign in to confirm you're not a bot" (cookies YouTube)

## De ce apare eroarea
Pe serverele cloud (Render), YouTube vede că cererile vin dintr-un centru de
date, nu de la un om, și le blochează cu mesajul
**„Sign in to confirm you're not a bot"**. Căutarea merge, dar descărcarea nu.

## Soluția: dăm botului cookies de YouTube
Cookies dintr-un browser logat fac ca yt-dlp să pară un utilizator real.

---

## PASUL 1 — Exportă cookies din browser

1. Într-un browser (Chrome/Firefox), fii **logat pe youtube.com**.
   - Ideal: folosește un cont YouTube secundar / de test, nu contul principal.
2. Instalează extensia **„Get cookies.txt LOCALLY”**:
   - Chrome: caută-o în Chrome Web Store
   - Firefox: caută-o în Add-ons
3. Deschide **https://www.youtube.com** (logat).
4. Apasă pe iconița extensiei → **Export** (format **Netscape**).
5. Se descarcă un fișier **`cookies.txt`**.

---

## PASUL 2 — Transformă cookies.txt în text (base64)

Pe Render e cel mai simplu să dăm cookies ca o singură variabilă de mediu.
Transformăm fișierul în base64.

### Pe Windows (PowerShell):
Deschide PowerShell în folderul unde e `cookies.txt` și rulează:
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard
```
Asta copiază automat textul base64 în clipboard (Ctrl+V ca să-l lipești).

> Dacă vrei să-l vezi într-un fișier în loc de clipboard:
> ```powershell
> [Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) > cookies_b64.txt
> ```
> apoi deschizi `cookies_b64.txt` și copiezi tot conținutul.

---

## PASUL 3 — Adaugă variabila pe Render

1. **dashboard.render.com** → serviciul **melodix** → **Environment**
2. **Add Environment Variable**:
   - **Key:** `YT_COOKIES_B64`
   - **Value:** lipește textul base64 (lung) copiat la Pasul 2
3. **Save Changes**

Render repornește automat botul. De acum descărcările folosesc cookies-urile.

---

## Verificare
- În Render → **Logs** → la pornire trebuie să vezi:
  ```
  Loaded YouTube cookies from YT_COOKIES_B64
  ```
- În Telegram, caută o melodie și apasă pe un rezultat → acum trimite audio.

---

## Note importante
- Cookies-urile **expiră** după un timp (săptămâni). Dacă descărcările încep
  iar să eșueze, repetă pașii (re-exportă și actualizează `YT_COOKIES_B64`).
- Folosește un **cont YouTube secundar** — teoretic YouTube poate limita un
  cont folosit intens de un bot.
- Nu pune niciodată `cookies.txt` în repo-ul public de pe GitHub! Îl dăm doar
  ca variabilă de mediu secretă pe Render.
