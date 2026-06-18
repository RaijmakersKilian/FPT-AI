# Research and Installation Manual — FPT AI

**Jada Guerzoni · Andreas Adam · Kilian Raijmakers · Dang Duc Anh · Le Quoc Ban**

---

## Inhoudsopgave

1. [Introduction](#1-introduction)
2. [Project Objectives](#2-project-objectives)
3. [System Overview](#3-system-overview)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [System Requirements](#6-system-requirements)
7. [Installation Guide](#7-installation-guide)
8. [Cloud Storage (Azure)](#8-cloud-storage-azure)
9. [XR / 3D Processing Pipeline](#9-xr--3d-processing-pipeline)
10. [IFC Processing Workflow](#10-ifc-processing-workflow)
11. [Coverage Analysis & Progress Estimation](#11-coverage-analysis--progress-estimation)
12. [Frontend Visualization](#12-frontend-visualization)
13. [Folder Structure](#13-folder-structure)
14. [Troubleshooting](#14-troubleshooting)
15. [Research Methodology](#15-research-methodology)

---

## 1. Introduction

The FTP-AI system is an automated construction monitoring platform designed to estimate the progress of bridge construction using UAV drone footage and BIM/IFC models.

The system focuses on the **GOT Bridge (XL8 IFC model)** and combines:

- Drone video processing
- 3D reconstruction of real-world geometry
- BIM/IFC model conversion
- Point cloud alignment
- Automated progress estimation

The goal is to create a **digital twin comparison system** that evaluates construction progress without manual inspection.

Video's, 3D modellen en rapporten worden opgeslagen in **Azure Blob Storage** (cloud). De coverage analyse resultaten worden als JSON bestanden bewaard naast de verwerkingsscripts. Er is geen lokale database of extra cloudservice nodig om het dashboard te draaien.

---

## 2. Project Objectives

Het systeem heeft als doel:

- UAV drone video's van bouwplaatsen verwerken
- Echte 3D geometrie reconstrueren
- BIM IFC modellen naar point clouds converteren
- Echte en geplande structuren uitlijnen
- Bouwvoortgang automatisch berekenen
- Resultaten visualiseren in een 3D dashboard

**Verwachte outputs:**

- Voltooiingspercentage van de brugconstructie
- 3D vergelijking tussen BIM model en werkelijkheid
- Coverage heatmaps (groen / oranje / rood)
- JSON resultaatbestanden per scandatum
- PDF-, CSV- en JSON-rapporten voor stakeholders

---

## 3. System Overview

Het systeem volgt een **geometry-based digital twin approach**.

In plaats van objecten te detecteren in 2D beelden, worden zowel echte als BIM-data omgezet naar 3D point clouds en direct vergeleken. Dit maakt de vergelijking robuust ongeacht:

- Lichtomstandigheden
- Camera-invalshoek
- Beeldruis
- Bewegingsonscherpte

De coverage resultaten (.ply en .json) en 3D modellen worden opgeslagen in **Azure Blob Storage** en rechtstreeks door de browser geladen — er hoeven geen grote bestanden lokaal aanwezig te zijn.

---

## 4. System Architecture

**Verwerkingspipeline (eenmalig per nieuwe dronevlucht):**

```
Drone video
 → Frame extractie (OpenCV)
 → 3D reconstructie (MASt3R-SLAM)
 → Echte point cloud (.ply)
 → IFC model → point cloud (ifctocloud.py)
 → Point cloud uitlijning (ICP)
 → Coverage analyse (coverage_analysis.py)
 → Resultaten opgeslagen in XR/IFC-TO-Cloud/coverage_results/
 → Uploaden naar Azure Blob Storage (upload_to_azure.py)
```

**Data flow tijdens gebruik van het dashboard:**

```
Browser  →  http://localhost:8000
                │
           FastAPI Backend (Python / Uvicorn)
                │
                ├── Azure Blob Storage (cloud)
                │     ├── videos/            drone video's (.mp4)
                │     ├── 3dmodels/
                │     │     ├── coverage/    gekleurde point clouds per datum
                │     │     ├── glb/         BIM model voor 3D viewer
                │     │     └── pointclouds/ ruwe point clouds
                │     └── reports/
                │           ├── pdf/         geëxporteerde PDF rapporten
                │           ├── csv/         CSV exports
                │           └── json/        JSON exports
                │
                └── XR/IFC-TO-Cloud/coverage_results/  (lokaal)
                      ├── coverage_results_DDMMYYYY.json  → tijdlijn + inspector
                      └── coverage_DDMMYYYY.json          → dekkingsdata per datum
```

---

## 5. Technology Stack

| Laag | Technologie | Doel |
|------|-------------|------|
| Backend | Python · FastAPI · Uvicorn | REST API, frontend serveren |
| Cloud opslag | Azure Blob Storage | Video's, 3D modellen, rapporten |
| 3D verwerking | Open3D · IfcOpenShell | IFC → point cloud, coverage analyse |
| Video verwerking | OpenCV | Frame extractie uit drone video |
| Frontend | HTML · CSS · JavaScript · Three.js | Dashboard, 3D BIM viewer |
| PDF export | ReportLab (backend) · jsPDF (frontend) | Rapporten genereren |

---

## 6. System Requirements

| Component | Minimum |
|-----------|---------|
| Besturingssysteem | Windows 10 / 11 (64-bit) |
| Python | 3.10 of hoger |
| RAM | 8 GB (16 GB aanbevolen) |
| Schijfruimte | 2 GB vrij |
| Internet | Vereist (Azure Blob Storage) |

> **Geen database installatie nodig.** Geen Docker vereist. Alleen Python en een internetverbinding voor Azure.

---

## 7. Installation Guide

### 7.1 Repository ophalen

```powershell
git clone https://github.com/RaijmakersKilian/FTP-AI.git
cd FTP-AI
```

### 7.2 Backend configureren

Kopieer het voorbeeld `.env` bestand en vul de Azure credentials in:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

In te vullen waarden:

```env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=fptstorageai;AccountKey=<key>;EndpointSuffix=core.windows.net
AZURE_MODELS_CONTAINER=3dmodels
AZURE_REPORTS_CONTAINER=reports
```

> De volledige `.env` met echte credentials wordt apart aangeleverd door het projectteam.

### 7.3 Frontend configureren

Kopieer het voorbeeld Azure config en vul de SAS tokens in:

```powershell
Copy-Item Frontend\azure-config.example.js Frontend\azure-config.js
notepad Frontend\azure-config.js
```

```javascript
window.AZURE_CONFIG = {
  account: "fptstorageai",
  videosContainer: "videos",
  modelsContainer: "3dmodels",
  sasToken: "<SAS token voor videos container — Read + List>",
  modelsSasToken: "<SAS token voor 3dmodels container — Read + List>",
};
```

> SAS tokens worden apart aangeleverd. Ze hebben een vervaldatum — vraag nieuwe tokens aan bij het verlopen.

### 7.4 Opstarten (één klik)

Dubbelklik op **`start.bat`** in de projectmap.

**Wat er automatisch gebeurt:**

| Stap | Actie |
|------|-------|
| Eerste keer | Python virtual environment aanmaken + alle packages installeren (~1 minuut) |
| Altijd | Backend starten op poort 8000 |
| Altijd | Browser automatisch openen op **http://localhost:8000** |

**Stoppen:** druk op `Ctrl+C` in het terminalvenster dat opende.

### 7.5 Handmatig opstarten (alternatief)

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

## 8. Cloud Storage (Azure)

Alle media en rapporten worden opgeslagen in **Azure Blob Storage** onder het account `fptstorageai`.

### 8.1 Containerstructuur

| Container | Map | Inhoud |
|-----------|-----|--------|
| `videos` | — | Drone video's (.mp4) |
| `3dmodels` | `coverage/` | Gekleurde point clouds (.ply) per scandatum |
| `3dmodels` | `glb/` | BIM model (.glb) voor 3D viewer |
| `3dmodels` | `pointclouds/` | Ruwe drone point clouds per datum |
| `reports` | `pdf/` | Geëxporteerde PDF rapporten |
| `reports` | `csv/` | CSV exports |
| `reports` | `json/` | JSON exports |

### 8.2 Toegang (SAS tokens)

De browser laadt video's en 3D modellen rechtstreeks van Azure via **SAS tokens** (Shared Access Signatures). Dit zijn tijdelijke toegangssleutels met een vervaldatum.

SAS tokens genereer je in de **Azure Portal**:
1. Navigeer naar het storage account `fptstorageai`
2. Ga naar **Data storage → Containers → `<container>`**
3. Klik op **Shared access tokens**
4. Stel rechten in: **Read + List**
5. Stel vervaldatum in op **minimaal 1 jaar**
6. Klik **Generate SAS token and URL** — kopieer de token (zonder het vraagteken)

### 8.3 Nieuwe bestanden uploaden naar Azure

Na het uitvoeren van de coverage analyse:

```powershell
cd backend
python upload_to_azure.py
```

Dit script uploadt automatisch alle bestanden uit `XR/IFC-TO-Cloud/coverage_results/` naar de juiste Azure containers.

---

## 9. XR / 3D Processing Pipeline

De 3D verwerkingsscripts staan in `XR/IFC-TO-Cloud/`. Dit onderdeel wordt **alleen uitgevoerd na nieuwe dronevluchten** om nieuwe coverage resultaten te genereren. Voor normaal gebruik van het dashboard is dit niet nodig.

### 9.1 Dependencies installeren

```powershell
pip install ifcopenshell trimesh numpy open3d scipy
```

> Bij problemen met `open3d` op Python 3.10: download het wheel-bestand van  
> [github.com/isl-org/Open3D/releases](https://github.com/isl-org/Open3D/releases)  
> en installeer met `pip install <bestand>.whl`

### 9.2 Benodigde bronbestanden

Plaats de volgende bestanden in `XR\IFC-TO-Cloud\`:

| Bestand | Beschrijving | Grootte |
|---------|-------------|---------|
| `Full_Build_Bridge.ifc` | BIM referentiemodel | ~135 MB |
| `Allpointclouds/pointcloud_DDMMYYYY.ply` | Drone reconstructie per datum | ~50–200 MB per stuk |

> Deze bestanden zijn te groot voor git en worden apart aangeleverd.

### 9.3 IFC naar Point Cloud converteren (eenmalig)

```powershell
cd XR\IFC-TO-Cloud
python ifctocloud.py --ifc Full_Build_Bridge.ifc
```

Output: `ifc_cloud.ply` — tijdelijk bestand, niet opgeslagen in git.

### 9.4 Coverage analyse uitvoeren

Voor alle beschikbare datums tegelijk:

```powershell
python batch_per_type.py
```

Of voor één specifieke datum:

```powershell
python coverage_analysis.py `
  --ifc ifc_cloud.ply `
  --mast3r Allpointclouds\pointcloud_18112023.ply `
  --date 18112023
```

**Output** (opgeslagen in `coverage_results/`):

| Bestand | Inhoud | Gebruikt door |
|---------|--------|---------------|
| `coverage_DDMMYYYY.ply` | Gekleurde point cloud | 3D viewer (via Azure) |
| `coverage_DDMMYYYY.json` | Dekkingsdata per segment | Backend API (fallback) |
| `coverage_results_DDMMYYYY.json` | Samenvatting per element type | Dashboard inspector + tijdlijn |

### 9.5 Resultaten uploaden naar Azure

```powershell
cd backend
python upload_to_azure.py
```

---

## 10. IFC Processing Workflow

Het IFC model (XL8 – GOT Bridge) wordt gebruikt als referentie BIM model.

Het systeem:

1. Extraheert structurele geometrie uit het `.ifc` bestand via **IfcOpenShell**
2. Converteert IFC elementen per type naar point cloud formaat
3. Normaliseert het coördinatensysteem (Z-up → Y-up voor Three.js)
4. Slaat per element type de punten op voor gerichte coverage analyse

Het resultaat (`ifc_cloud.ply`) vormt de "geplande" structuur waartegen de drone reconstructie wordt vergeleken.

---

## 11. Coverage Analysis & Progress Estimation

Het systeem vergelijkt de **echte point cloud** (drone reconstructie via MASt3R-SLAM) met de **BIM point cloud** (IFC model).

### Uitlijnmethode

De twee point clouds worden uitgelijn met **Iterative Closest Point (ICP)** — een geometrisch algoritme dat de echte structuur optimaliserend uitlijnt op het BIM model.

### Classificatieregels

| Status | Criterium | Kleur in dashboard |
|--------|-----------|--------------------|
| Gebouwd | ≥ 80% van BIM punten gedekt | Groen |
| In uitvoering | 30–80% gedekt | Oranje |
| Niet gebouwd | < 30% gedekt | Rood |

### Output

- Totaal voortgangspercentage
- Voltooiingsstatus per brugonderdeel
- Voltooiingsstatus per element type (pijler, dek, fundament...)
- Heatmap visualisatie in de 3D viewer
- Timeline van voortgang over meerdere scandatums (4D analyse)

---

## 12. Frontend Visualization

Het dashboard is beschikbaar via **http://localhost:8000**.

### Functies

| Functie | Werking |
|---------|---------|
| **Video tijdlijn** | Drone video's geladen van Azure `videos` container |
| **3D BIM viewer** | Point cloud van Azure, gekleurd op dekkingsstatus (groen/oranje/rood) |
| **Construction Inspector** | Dekkingspercentage per element type, geladen via backend API |
| **Overall Progress** | Totaalpercentage + telling gebouwd/bezig/niet gestart |
| **PDF export** | Rapport met 3D snapshot + grafieken → Azure `reports/pdf/` |
| **CSV export** | Tijdlijn + elementen als spreadsheet → Azure `reports/csv/` |
| **JSON export** | Machine-leesbare data → Azure `reports/json/` |

### Video ↔ 3D koppeling

Wanneer je op een video in de tijdlijn klikt:

1. De drone video van die datum speelt af
2. De 3D viewer laadt automatisch de bijbehorende coverage point cloud van die datum (van Azure)
3. De Construction Inspector toont de dekkingsdata van die specifieke datum

---

## 13. Folder Structure

```
FTP-AI/
├── start.bat                          ← Dubbelklik om te starten
│
├── backend/
│   ├── .env                           ← Credentials (niet in git — aangeleverd apart)
│   ├── .env.example                   ← Template
│   ├── init.sql                       ← Database schema (optioneel)
│   ├── requirements.txt               ← Python packages
│   ├── upload_to_azure.py             ← Bestanden uploaden naar Azure
│   └── app/
│       ├── main.py                    ← Startpunt backend
│       ├── db/
│       │   └── azure_storage.py       ← Azure Blob client
│       ├── routers/
│       │   ├── coverage_router.py     ← /api/coverage/* endpoints
│       │   ├── report_router.py       ← /reports/* endpoints
│       │   └── video_router.py        ← /videos/* endpoints
│       └── services/
│           ├── pdf_service.py         ← PDF generatie
│           └── report_service.py      ← Rapport logica
│
├── Frontend/
│   ├── Dashboard.html                 ← Hoofdpagina
│   ├── Dashboard.css
│   ├── azure-config.js                ← SAS tokens (niet in git — aangeleverd apart)
│   ├── azure-config.example.js        ← Template
│   ├── azure-data.js                  ← Video's laden van Azure
│   ├── viewer.js                      ← Three.js 3D point cloud viewer
│   ├── inspector.js                   ← Construction Inspector paneel
│   ├── thumbnails.js                  ← Tijdlijn navigatie (pijltjes + paginering)
│   ├── chart.js                       ← Voortgangsgrafiek over tijd
│   └── pdf.js                         ← PDF / CSV / JSON export
│
└── XR/
    └── IFC-TO-Cloud/
        ├── ifctocloud.py              ← IFC → point cloud conversie
        ├── coverage_analysis.py       ← Coverage analyse per datum
        ├── batch_per_type.py          ← Batch verwerking alle datums
        ├── batch_coverage.py          ← Alternatieve batch runner
        ├── filter_pipeline.py         ← Point cloud filtering / cleaning
        ├── compare_clouds.py          ← Vergelijkingstool (analyse)
        ├── viz_utils.py               ← Visualisatie hulpfuncties
        └── coverage_results/          ← JSON resultaten per datum (in git)
            ├── coverage_DDMMYYYY.json
            └── coverage_results_DDMMYYYY.json
```

---

## 14. Troubleshooting

### `start.bat` sluit meteen

Open een terminal (CMD of PowerShell), navigeer naar de projectmap en voer het script handmatig uit zodat je de foutmelding kunt lezen:

```powershell
cd FTP-AI
.\start.bat
```

### "Python niet gevonden"

- Installeer Python 3.10+ via [python.org](https://www.python.org/downloads/)
- Vink **"Add Python to PATH"** aan tijdens installatie
- Open daarna een nieuw terminalvenster

### ".env bestand niet gevonden"

Kopieer het voorbeeld en vul de Azure credentials in:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

### Video's laden niet

- Controleer of `Frontend/azure-config.js` bestaat (kopieer van `azure-config.example.js`)
- Controleer of de SAS token in `azure-config.js` nog geldig is (er staat een `se=` vervaldatum in de token)
- Open de browser console via F12 → tabblad **Network** en kijk naar mislukte requests

### 3D model of coverage point cloud toont niet

- Open het dashboard via `http://localhost:8000` — **niet** via een bestandspad of VS Code Live Server
- Controleer of de `modelsSasToken` in `azure-config.js` geldig is
- Klik op een video in de tijdlijn — de 3D viewer laadt de coverage van die datum

### Construction Inspector is leeg

- Open `http://localhost:8000/api/coverage/data/18112023` in de browser
- Als dit JSON teruggeeft: de backend werkt correct
- Als 404: controleer of de `.json` bestanden aanwezig zijn in `XR/IFC-TO-Cloud/coverage_results/`

### Rapporten worden niet opgeslagen in Azure

- Controleer `AZURE_REPORTS_CONTAINER` in `backend/.env`
- Controleer `AZURE_STORAGE_CONNECTION_STRING` in `backend/.env`
- Bekijk de browser console (F12) voor foutmeldingen bij het exporteren

### PowerShell blokkeert scripts

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 15. Research Methodology

### Core Idea

Het systeem is gebaseerd op een **digital twin vergelijkingsaanpak**.

Zowel de echte droneumstructie als het BIM ontwerp worden omgezet naar 3D point clouds en geometrisch vergeleken via **Iterative Closest Point (ICP)** uitlijning gevolgd door een nearest-neighbour coverage analyse.

### Key Advantages

- Geen afhankelijkheid van 2D objectdetectie (geen trainingsdata nodig)
- Robuust tegen lichtomstandigheden en camerageluid
- Werkt direct in 3D ruimte
- Maakt nauwkeurige infrastructuurvergelijking mogelijk
- Ondersteunt **multi-datum (4D) voortgangsregistratie** — resultaten per scandatum apart opgeslagen
- Dashboard update automatisch wanneer nieuwe scandata wordt geüpload

### Pipeline Samenvatting

| Stap | Tool | Input | Output |
|------|------|-------|--------|
| Frame extractie | OpenCV | Drone video (.mp4) | Keyframes (.jpg) |
| 3D reconstructie | MASt3R-SLAM | Keyframes | Point cloud (.ply) |
| IFC conversie | IfcOpenShell | BIM model (.ifc) | `ifc_cloud.ply` |
| Point cloud uitlijning | Open3D ICP | 2× point clouds | Uitgelijnde cloud |
| Coverage analyse | Open3D | Uitgelijnde clouds | `coverage_DDMMYYYY.ply` + `.json` |
| Upload naar cloud | azure-storage-blob | Lokale bestanden | Azure Blob Storage |
| Dashboard visualisatie | Three.js + FastAPI | Azure URLs + lokale JSON | 3D dashboard in browser |

---

*FTP-AI · GOT Bridge Monitoring Platform · Juni 2026*
