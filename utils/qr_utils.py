# utils/qr_utils.py
import qrcode
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
QR_DIR = BASE_DIR / "assets" / "qr_codes"


def get_qr_path(codigo: str) -> Path:
    QR_DIR.mkdir(parents=True, exist_ok=True)
    return QR_DIR / f"{codigo}.png"


def generar_qr(codigo: str, nombre: str = None) -> str:
    path = get_qr_path(codigo)
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(codigo)
    qr.make()
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(path))
    return str(path)
