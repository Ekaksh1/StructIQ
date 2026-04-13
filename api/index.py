import os
import random
import json
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from upstash_redis import Redis

app = FastAPI(title="StructIQ AI Engine : Chennai (NoSQL)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DETECT ENVIRONMENT & INITIALIZE KV STORE ---
kv_url = os.environ.get("UPSTASH_REDIS_REST_URL")
kv_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

if kv_url and kv_token:
    # Production: Vercel KV
    kv = Redis(url=kv_url, token=kv_token)
    print("Using Vercel KV (Redis)")
else:
    # Local Dev: Simple In-Memory Emulation
    class MockKV:
        def __init__(self):
            self.data = {}

        def get(self, key):
            return self.data.get(key)

        def set(self, key, val):
            self.data[key] = val

        def exists(self, key):
            return key in self.data

    kv = MockKV()
    print("Using Local In-Memory Storage")


# --- DATA MODELS (NO DATABASE FILE NEEDED) ---
class AssetCreate(BaseModel):
    name: str
    asset_type: str
    construction_year: int
    latitude: float
    longitude: float


# --- HELPERS ---
def get_assets():
    data = kv.get("assets")
    return json.loads(data) if data else []


def save_assets(assets):
    kv.set("assets", json.dumps(assets))


def get_reports():
    data = kv.get("reports")
    return json.loads(data) if data else []


def save_reports(reports):
    kv.set("reports", json.dumps(reports))


# --- API ENDPOINTS ---


@app.get("/api/assets")
def fetch_assets():
    return get_assets()


@app.get("/api/reports")
def fetch_reports():
    return get_reports()


@app.post("/api/assets")
def create_asset(asset: AssetCreate):
    assets = get_assets()
    current_year = 2026
    age = current_year - asset.construction_year
    decay_rate = 3.0 if asset.asset_type == "Road" else 0.5
    h_score = max(0.0, 100 - (age * decay_rate))

    prio = "Low"
    if h_score < 40:
        prio = "Emergency"
    elif h_score < 70:
        prio = "High"

    new_asset = {
        "id": len(assets) + 1,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "age": age,
        "construction_year": asset.construction_year,
        "latitude": asset.latitude,
        "longitude": asset.longitude,
        "health_score": round(float(h_score), 1),
        "maintenance_priority": prio,
        "vibration_level": round(random.uniform(0.01, 0.08), 3),
    }
    assets.append(new_asset)
    save_assets(assets)
    return new_asset


@app.post("/api/reports/upload-ai")
async def upload_ai_report(
    asset_id: int = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
):
    filename_check = file.filename.lower()
    if any(
        word in filename_check for word in ["google", "download", "stock", "wallpaper"]
    ):
        raise HTTPException(status_code=400, detail="FRAUD DETECTED")

    reports = get_reports()
    assets = get_assets()

    target_asset = next((a for a in assets if a["id"] == asset_id), None)
    if not target_asset:
        raise HTTPException(status_code=404)

    ai_severity = random.choice([5, 10, 15])
    labels = {5: "Minor Hairline", 10: "Significant Surface", 15: "Critical Structural"}
    ai_label = labels[ai_severity]

    new_report = {
        "id": len(reports) + 1,
        "asset_id": asset_id,
        "description": f"AI SCAN [{ai_label}]: {description}",
        "severity": ai_severity,
        "status": "Open",
    }

    # Impact Asset
    target_asset["health_score"] = max(
        0.0, target_asset["health_score"] - (ai_severity * 1.5)
    )
    if target_asset["health_score"] < 40:
        target_asset["maintenance_priority"] = "Emergency"

    reports.append(new_report)
    save_reports(reports)
    save_assets(assets)
    return {
        "report_id": new_report["id"],
        "analysis": ai_label,
        "severity": ai_severity,
    }


@app.post("/api/weather/trigger-flood")
def trigger_flood_alert():
    assets = get_assets()
    count = 0
    for asset in assets:
        if asset["asset_type"] == "Road":
            asset["health_score"] = max(0.0, asset["health_score"] - 15.0)
            if asset["health_score"] < 50:
                asset["maintenance_priority"] = "High"
            count += 1
    save_assets(assets)
    return {"status": "FLOOD ALERT ACTIVE", "affected_count": count}


@app.post("/api/reports/{report_id}/resolve")
def resolve_report(report_id: int):
    reports = get_reports()
    assets = get_assets()

    report = next((r for r in reports if r["id"] == report_id), None)
    if not report:
        raise HTTPException(status_code=404)

    asset = next((a for a in assets if a["id"] == report["asset_id"]), None)
    if asset:
        asset["health_score"] = min(
            100.0, asset["health_score"] + (report["severity"] * 1.5)
        )
        if asset["health_score"] >= 70:
            asset["maintenance_priority"] = "Low"

    new_reports = [r for r in reports if r["id"] != report_id]
    save_reports(new_reports)
    save_assets(assets)
    return {"status": "success"}


@app.post("/api/assets/{asset_id}/maintenance")
def perform_maintenance(asset_id: int):
    assets = get_assets()
    asset = next((a for a in assets if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404)

    asset["health_score"] = min(100.0, asset["health_score"] + 20.0)
    if asset["health_score"] >= 70:
        asset["maintenance_priority"] = "Low"

    save_assets(assets)
    return {"new_health": asset["health_score"]}


@app.get("/api/setup-demo")
def setup_demo():
    demo_assets = [
        {
            "name": "Adyar Bridge",
            "asset_type": "Bridge",
            "latitude": 13.0067,
            "longitude": 80.2595,
            "construction_year": 1970,
        },
        {
            "name": "Napier Bridge",
            "asset_type": "Bridge",
            "latitude": 13.0694,
            "longitude": 80.2824,
            "construction_year": 1869,
        },
        {
            "name": "Ennore Creek Bridge",
            "asset_type": "Bridge",
            "latitude": 13.2217,
            "longitude": 80.3222,
            "construction_year": 2005,
        },
        {
            "name": "Anna Flyover",
            "asset_type": "Flyover",
            "latitude": 13.0500,
            "longitude": 80.2500,
            "construction_year": 1973,
        },
        {
            "name": "Kathipara Cloverleaf",
            "asset_type": "Flyover",
            "latitude": 13.0067,
            "longitude": 80.2050,
            "construction_year": 2008,
        },
        {
            "name": "T.Nagar Skywalk",
            "asset_type": "Flyover",
            "latitude": 13.0333,
            "longitude": 80.2333,
            "construction_year": 2022,
        },
        {
            "name": "OMR IT Expressway",
            "asset_type": "Road",
            "latitude": 12.9228,
            "longitude": 80.2316,
            "construction_year": 2006,
        },
        {
            "name": "ECR Highway",
            "asset_type": "Road",
            "latitude": 12.8491,
            "longitude": 80.2433,
            "construction_year": 1998,
        },
        {
            "name": "Mount Road",
            "asset_type": "Road",
            "latitude": 13.0600,
            "longitude": 80.2500,
            "construction_year": 1950,
        },
    ]

    # Simple Reset/Refresh for Demo
    assets = []
    current_year = 2026
    for i, data in enumerate(demo_assets):
        age = current_year - data["construction_year"]
        if data["name"] == "Napier Bridge":
            h_score = 92.5
        elif data["asset_type"] == "Road":
            h_score = max(15.0, 100.0 - (age * 3.0))
        else:
            h_score = max(20.0, 100.0 - (age * 0.5))

        prio = "Low"
        if h_score < 40:
            prio = "Emergency"
        elif h_score < 70:
            prio = "High"

        assets.append(
            {
                **data,
                "id": i + 1,
                "age": age,
                "health_score": round(h_score, 1),
                "maintenance_priority": prio,
                "vibration_level": 0.02,
            }
        )

    save_assets(assets)
    return {"status": "Demo assets loaded successfully via NoSQL KV", "count": 9}
