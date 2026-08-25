# 🆓 Găzduire gratuită FĂRĂ CARD — Fly.io

Această opțiune:
- ✅ **nu cere card** la înregistrare (pentru început / uz mic)
- ✅ ține botul pornit **24/7**, non-stop (nu adoarme)
- ✅ **păstrează playlisturile** pe un volum permanent (`/data/bot.db`)
- ✅ repornește botul automat dacă pică

Vei rula botul într-un container Docker pe Fly.io. Am pregătit deja
`Dockerfile` și `fly.toml`, deci nu trebuie să configurezi nimic manual.

> Notă sinceră: Fly.io poate cere un card DOAR dacă depășești limitele gratuite.
> Pentru un singur bot mic (256 MB RAM) rămâi în free. Dacă totuși îți cere
> card la înregistrare, vezi la final alternativa **Railway**.

---

## Pasul 1 — Instalează unealta Fly (o singură dată)

Pe laptopul tău (Windows PowerShell):

```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

Închide și redeschide PowerShell după instalare. Verifică:
```powershell
fly version
```

## Pasul 2 — Creează cont și autentifică-te

```powershell
fly auth signup
```
Se deschide browserul → creezi cont (email + parolă, sau GitHub).
Dacă ai deja cont: `fly auth login`.

## Pasul 3 — Intră în folderul botului

```powershell
cd C:\Users\user\Desktop\telegram-music-bot
```

## Pasul 4 — Lansează aplicația (fără să pornească încă)

```powershell
fly launch --no-deploy
```
- Când te întreabă dacă vrei să copieze configurarea din `fly.toml` → **Yes**.
- Îți poate cere un **nume unic** pentru aplicație (ex. `melodix-1234`) și o
  regiune (alege `fra` = Frankfurt, aproape de Moldova).
- Dacă întreabă de bază de date / Postgres / Redis → **No** (nu ai nevoie).

## Pasul 5 — Creează volumul permanent pentru playlisturi

```powershell
fly volumes create melodix_data --size 1 --region fra
```
(1 GB e mai mult decât suficient. Numele `melodix_data` trebuie să fie exact
la fel ca în `fly.toml`.)

## Pasul 6 — Pune tokenul (secret, nu în cod)

```powershell
fly secrets set BOT_TOKEN=PUNE_AICI_TOKENUL_DE_LA_BOTFATHER
```

## Pasul 7 — Pornește botul (deploy)

```powershell
fly deploy
```
Durează câteva minute (construiește imaginea Docker). Când termină, botul e
pornit. Deschide-l în Telegram și trimite `/start`.

---

## Comenzi utile

| Ce vrei | Comandă |
|---|---|
| Vezi logurile live | `fly logs` |
| Repornește botul | `fly apps restart` |
| Starea aplicației | `fly status` |
| Schimbă tokenul | `fly secrets set BOT_TOKEN=...` |
| Oprește (scale la 0) | `fly scale count 0` |
| Pornește la loc | `fly scale count 1` |

---

## Playlisturile sunt în siguranță

Baza de date (`/data/bot.db`) stă pe volumul **`melodix_data`**, care e
**permanent**. Playlisturile, limba utilizatorilor și statisticile
**NU se pierd** la redeploy sau restart.

### Actualizezi codul mai târziu?
Modifici fișierele, apoi:
```powershell
fly deploy
```
Volumul (deci playlisturile) rămâne neatins.

---

## Dacă Fly.io îți cere totuși card → Railway (altă opțiune fără card)

Railway oferă credit gratuit lunar și acceptă login cu GitHub:

1. Intră pe **https://railway.app** → **Login with GitHub**.
2. **New Project** → **Deploy from GitHub repo** (urcă întâi botul pe GitHub).
3. Railway detectează automat `Dockerfile`-ul din proiect.
4. La **Variables**, adaugă:
   - `BOT_TOKEN` = tokenul tău
   - `DATABASE_PATH` = `/data/bot.db`
5. La **Settings → Volumes**, adaugă un volum montat la **`/data`**
   (ca playlisturile să persiste).
6. Deploy. Gata.

> Ambele (Fly / Railway) folosesc același `Dockerfile` pe care l-am pregătit —
> nu trebuie să schimbi nimic în cod.
