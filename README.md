# Control de Asistencia Personal

App de escritorio para registrar asistencia de personal mediante códigos QR escaneados por cámara. Desarrollada con Python + Flet.

## Funcionalidades

- Registro de asistencia por escaneo QR en tiempo real
- Panel de administración con gestión de personal y horarios
- Dashboard con estado de asistencia del día
- Reportes exportables
- Base de datos local SQLite (no requiere conexión a internet)

## Stack

| Capa | Tecnología |
|------|-----------|
| UI / Desktop | Flet (Flutter-based) |
| Base de datos | SQLite vía SQLAlchemy |
| Escaneo QR | pyzbar + OpenCV |
| Generación QR | qrcode |
| Arquitectura | MVC (views / backend / data) |

## Estructura

```
├── main.py              # Entrada principal
├── views/               # UI (dashboard, admin, registro, login)
├── backend/             # Modelos, CRUD, lógica de negocio
│   ├── models.py
│   ├── database.py
│   ├── crud.py
│   └── logic.py
├── utils/               # QR generator
└── data/                # Base de datos local (no versionada)
```

## Requisitos

- Python 3.10+
- Windows (recomendado para escaneo QR con cámara)

## Instalación

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

La base de datos se crea automáticamente en `data/personal.db` al primer inicio.

---

Desarrollado por [Aldo Escobar](https://hexa38.com) · Hexa38
