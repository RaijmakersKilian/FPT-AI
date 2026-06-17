# FTP-AI — Installation Guide

## Quick Start

1. Zorg dat **Python 3.10+** geïnstalleerd is ([python.org](https://www.python.org/downloads/)) — vink **"Add Python to PATH"** aan.
2. Kopieer `backend/.env.example` naar `backend/.env` en vul de credentials in (zie [Stap 2](#stap-2--env-instellen)).
3. Dubbelklik op **`start.bat`** in de projectmap.

De browser opent automatisch op **http://localhost:8000**.

---

## Systeemvereisten

| Component | Minimum        |
|-----------|----------------|
| OS        | Windows 10/11  |
| Python    | 3.10 of hoger  |
| RAM       | 8 GB           |
| Internet  | Vereist (Azure + Supabase) |

> Geen PostgreSQL, geen Docker nodig. De database draait via Supabase (cloud) en bestanden via Azure Blob Storage.

---

## Architectuur

```
Browser  →  http://localhost:8000
                │
           FastAPI Backend  (Python)
                │
                ├── Supabase (cloud database via REST/HTTPS)
                ├── Azure Blob Storage (video's, 3D modellen, rapporten)
                └── Frontend/ (Dashboard, 3D viewer, inspector)
```

---

## Stap 1 — Repository ophalen

```powershell
git clone https://github.com/RaijmakersKilian/FTP-AI.git
cd FTP-AI
```

---

## Stap 2 — .env instellen

Kopieer het voorbeeld-bestand en vul de gegevens in:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Vul de volgende waarden in (ontvangen van het projectteam):

```env
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<jouw-service-role-key>

AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_MODELS_CONTAINER=3dmodels
AZURE_REPORTS_CONTAINER=reports
```

> De volledige `.env` met echte credentials krijg je apart aangeleverd van het projectteam.

---

## Stap 3 — Opstarten

Dubbelklik op **`start.bat`** in de projectmap.

**Wat er gebeurt:**
- Bij de eerste keer: automatisch een Python virtual environment aanmaken en alle packages installeren (~1 minuut).
- Daarna: de backend starten en de browser automatisch openen op **http://localhost:8000**.

**Stoppen:** druk op `Ctrl+C` in het venster dat opende.

---

## Handmatig opstarten (alternatief)

Als `start.bat` niet werkt:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Open daarna **http://localhost:8000** in je browser.

---

## Mappenstructuur

```
FTP-AI/
├── start.bat                  ← Dubbelklik om te starten
├── backend/
│   ├── .env                   ← Credentials (niet in git)
│   ├── .env.example           ← Template
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── routers/
│       └── services/
├── Frontend/
│   ├── Dashboard.html
│   ├── azure-config.js        ← Azure SAS tokens (niet in git)
│   ├── azure-config.example.js← Template
│   └── ...
└── XR/IFC-TO-Cloud/
    ├── coverage_results/      ← Coverage JSON per scandatum
    └── *.py                   ← Verwerkingsscripts (optioneel)
```

---

## azure-config.js instellen (Frontend)

De 3D viewer en video's laden van Azure. Kopieer het voorbeeld en vul in:

```powershell
Copy-Item Frontend\azure-config.example.js Frontend\azure-config.js
notepad Frontend\azure-config.js
```

```javascript
window.AZURE_CONFIG = {
  account: "fptstorageai",
  videosContainer: "videos",
  modelsContainer: "3dmodels",
  sasToken: "<SAS-token voor videos container>",
  modelsSasToken: "<SAS-token voor 3dmodels container>",
};
```

> SAS tokens ontvang je van het projectteam. Ze hebben een vervaldatum — bij verlopen tokens zijn video's en 3D modellen niet meer zichtbaar.

---

## Probleemoplossing

**`start.bat` opent en sluit meteen**
- Klik rechts op `start.bat` → *Uitvoeren als administrator*, of open een terminal en voer het handmatig uit zodat je de foutmelding ziet.

**"Python niet gevonden"**
- Installeer Python via [python.org](https://www.python.org/downloads/) met **"Add Python to PATH"** aangevinkt.
- Start daarna een nieuw terminalvenster.

**".env bestand niet gevonden"**
- Kopieer `backend\.env.example` naar `backend\.env` en vul de credentials in.

**Video's / 3D model laden niet**
- Controleer of `Frontend\azure-config.js` bestaat en correcte SAS tokens bevat.
- SAS tokens hebben een vervaldatum — vraag nieuwe tokens aan bij het projectteam.

**Dashboard is leeg / inspector toont niets**
- Open `http://localhost:8000/api/coverage/timeline` in de browser — als dat JSON teruggeeft werkt de backend.
- Controleer de terminal op foutmeldingen.

**PowerShell blokkeert scripts**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

*FTP-AI · GOT Bridge Monitoring Platform · Juni 2026*
