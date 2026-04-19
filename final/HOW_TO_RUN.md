# How to Run — NeuroFeed

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10 + | `python --version` |
| pip | latest | `pip --version` |
| Webcam | any USB / built-in | — |

---

## 1 — One-time setup

Open a terminal in the project root:

```
c:\Users\dheer\OneDrive\Desktop\final
```

### Create & activate the virtual environment

```bash
python -m venv env

# Windows CMD
env\Scripts\activate.bat

# Windows PowerShell
env\Scripts\Activate.ps1

# Git Bash / WSL
source env/Scripts/activate
```

### Install all dependencies

```bash
pip install -r requirements.txt
```

> This installs FastAPI, Uvicorn, PyTorch, OpenCV, MediaPipe, scikit-learn, pandas.

---

## 2 — Import the news data (one-time)

Make sure `news_transformed.csv` and `interaction_profile_scored_final.csv`
are in the project root or inside `data/`.

```bash
# From project root — run the database seeder
python database.py
```

Or call the API endpoint after the server starts:
```
POST http://localhost:8000/import_data
```

---

## 3 — Start the backend server

**From the project root** (recommended):

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Or from inside the `backend/` folder:**

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Optional — auto-start the webcam on launch

```bash
# Windows CMD
set ENABLE_WEBCAM_ATTENTION=1
uvicorn backend.main:app --reload --port 8000

# PowerShell
$env:ENABLE_WEBCAM_ATTENTION="1"
uvicorn backend.main:app --reload --port 8000

# Bash
ENABLE_WEBCAM_ATTENTION=1 uvicorn backend.main:app --reload --port 8000
```

---

## 4 — Open the frontend

Navigate to:

```
http://localhost:8000/app
```

The frontend is served directly by FastAPI — no separate server needed.

---

## 5 — Start face tracking / webcam

Click **Start webcam** in the top-right of the feed page.

This does two things:
1. Tells the backend to open your camera with OpenCV + MediaPipe
2. Displays the annotated MJPEG stream (face box + eye markers) in the UI

The face tracking stream appears in the right-side camera panel.
Metrics (brightness, eye openness, gaze, energy, etc.) update live.

---

## 6 — Full flow

```
Onboard → Pick interests → Launch feed
    ↓
Article appears → Read → Like / Dislike / Next
    ↓
Backend: updates interactions, category_prefs, users, category_stats
    ↓
Webcam: captures brightness, EAR, gaze, movement every frame
    ↓
DDQN agent: trains on your feedback, updates Q-values
    ↓
Next recommendations: re-scored with updated preferences + attention
```

---

## API endpoints (for debugging)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/` | Health check |
| `GET` | `/app` | Frontend UI |
| `GET` | `/docs` | Swagger docs |
| `POST` | `/onboard` | Register user |
| `POST` | `/recommend` | Get articles |
| `POST` | `/feedback` | Submit interaction |
| `GET` | `/attention` | Latest attention snapshot |
| `GET` | `/attention/stream` | MJPEG camera stream |
| `GET` | `/attention/frame` | Single JPEG frame |
| `POST` | `/attention/start` | Start webcam backend |
| `POST` | `/attention/stop` | Stop webcam backend |
| `GET` | `/user/{user_id}` | User profile |
| `POST` | `/import_data` | Import CSV data |

---

## Troubleshooting

**`ModuleNotFoundError` for mediapipe / torch / cv2**
→ Run `pip install -r requirements.txt` again with the venv active.

**Camera won't start (`camera_unavailable`)**
→ Another app is using the camera. Close browsers, Zoom, Teams etc.
→ Try a different camera index: edit `start_background_attention(camera_index=1)` in `backend/main.py`.

**No articles showing**
→ Run `POST /import_data` to seed the database.
→ Check `data/news_recommender.sqlite` exists.

**Webcam stream shows nothing in browser**
→ Allow `localhost:8000` through your firewall.
→ Disable browser extensions that block mixed content.

**PyTorch `FutureWarning` about `weights_only`**
→ Already fixed in `ddqn_agent.py` with `weights_only=False`.
