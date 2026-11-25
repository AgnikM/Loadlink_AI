import os
from typing import List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True)

    PROJECT_NAME: str = "LoadLink AI"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "loadlink-secret-key-super-secure-production-ready-kolkata-corridor")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Resolve absolute path to database in backend directory
    _backend_dir: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{os.path.join(_backend_dir, 'loadlink.db').replace('\\', '/')}"
    )

    # Database Connection Pool Configuration
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    # Security & CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://10.0.2.2:3000",
        "https://loadlink.ai",
        "https://driver.loadlink.ai",
        "https://admin.loadlink.ai",
    ]

    # Rate Limiting Defaults
    RATE_LIMIT_GENERAL_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_GENERAL_PER_MINUTE", "120"))
    RATE_LIMIT_AUTH_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "30"))

    # West Bengal Multi-Hub Logistics Network (Development & Demo Seed Locations)
    CORRIDOR_HUBS: Dict[str, Dict[str, float]] = {
        "Kolkata Port / Docks": {"lat": 22.5448, "lon": 88.3186},
        "Howrah Logistics Park": {"lat": 22.5958, "lon": 88.2636},
        "Dankuni Freight Terminal (NH19)": {"lat": 22.6842, "lon": 88.2934},
        "Bardhaman Agricultural Hub": {"lat": 23.2324, "lon": 87.8615},
        "Durgapur Steel Complex": {"lat": 23.5204, "lon": 87.3119},
        "Raniganj Coal & Cement Bypass": {"lat": 23.6210, "lon": 87.1265},
        "Asansol Industrial Hub": {"lat": 23.6739, "lon": 86.9524},
        "Haldia Deep Water Port": {"lat": 22.0667, "lon": 88.0698},
        "Kharagpur Heavy Engineering Zone": {"lat": 22.3460, "lon": 87.2320},
        "Malda Central Transit Corridor": {"lat": 25.0108, "lon": 88.1411},
        "Siliguri North Bengal Gateway": {"lat": 26.7271, "lon": 88.3953},
    }


    # Deterministic Scoring Default Weights (PRD Section 8.2)
    DEFAULT_MATCH_WEIGHTS: Dict[str, float] = {
        "route_compatibility": 0.25,
        "availability_feasibility": 0.20,
        "pickup_proximity": 0.15,
        "capacity_fit": 0.10,
        "price_competitiveness": 0.10,
        "reliability": 0.10,
        "return_load_potential": 0.10,
    }

    # File storage upload directory
    UPLOAD_DIR: str = "./uploads"

settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

