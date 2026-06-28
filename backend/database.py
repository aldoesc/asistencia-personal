# backend/database.py
# Configuración de base de datos SQLite + inicialización

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path
from .models import Base, Admin, Sucursal, TipoTurno, DiaSemana
from passlib.context import CryptContext

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "data" / "personal.db"
DB_URL   = f"sqlite:///{DB_PATH}"

engine       = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context  = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─────────────────────────────────────────────
# DEPENDENCIA FASTAPI
# ─────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────
# INICIALIZACIÓN
# ─────────────────────────────────────────────

def init_db():
    """Crea todas las tablas y datos iniciales si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        _seed_sucursales(db)
        print("✅ Base de datos inicializada correctamente.")
    finally:
        db.close()


def _seed_sucursales(db: Session):
    """Crea las dos sucursales si no existen."""
    if db.query(Sucursal).count() == 0:
        sucursales = [
            Sucursal(nombre="Sucursal Norte", direccion="Dirección sucursal norte"),
            Sucursal(nombre="Sucursal Sur",   direccion="Dirección sucursal sur"),
        ]
        db.add_all(sucursales)
        db.commit()
        print("✅ Sucursales creadas.")


def admin_existe(db: Session) -> bool:
    """Indica si existe al menos un admin en la base de datos."""
    return db.query(Admin).count() > 0
