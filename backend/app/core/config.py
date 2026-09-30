from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "personal_os.db"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
