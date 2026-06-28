from sqlalchemy.orm import Session
from datetime import date
from passlib.context import CryptContext
from backend.models import (
    Empleado, Sucursal, Admin,
    HorarioSemanal,
    RegistroAsistencia, SaludEmpleado,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─────────────────────────── AUTH ────────────────────────────────────────────

def verificar_admin(db: Session, username: str, password: str) -> bool:
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        return False
    return pwd_context.verify(password, admin.password_hash)


def crear_admin(db: Session, username: str, password: str, nombre: str = "Administrador") -> Admin:
    username = (username or "").strip()
    if not username:
        raise ValueError("El usuario es obligatorio.")
    if db.query(Admin).filter(Admin.username == username).first():
        raise ValueError("Ese usuario ya existe.")
    if not password or len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")

    admin = Admin(
        username=username,
        password_hash=pwd_context.hash(password),
        nombre=nombre,
        activo=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def cambiar_password_admin(db: Session, username: str, password_actual: str, password_nueva: str) -> None:
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        raise ValueError("Admin no encontrado.")
    if not pwd_context.verify(password_actual or "", admin.password_hash):
        raise ValueError("Contraseña actual incorrecta.")
    if not password_nueva or len(password_nueva) < 8:
        raise ValueError("La nueva contraseña debe tener al menos 8 caracteres.")

    admin.password_hash = pwd_context.hash(password_nueva)
    db.commit()


# ─────────────────────────── SUCURSALES / TIENDAS ────────────────────────────

def get_sucursales(db: Session):
    return (
        db.query(Sucursal)
        .filter(Sucursal.activa == True)
        .order_by(Sucursal.nombre)
        .all()
    )


def crear_sucursal(db: Session, nombre: str) -> Sucursal:
    s = Sucursal(nombre=nombre, activa=True)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def eliminar_sucursal(db: Session, sucursal_id: int) -> None:
    s = db.get(Sucursal, sucursal_id)
    if s:
        db.delete(s)
        db.commit()


# ─────────────────────────── EMPLEADOS ───────────────────────────────────────

def get_empleados(db: Session):
    return (
        db.query(Empleado)
        .filter(Empleado.activo == True)
        .order_by(Empleado.apellido)
        .all()
    )


def get_empleado_por_codigo(db: Session, codigo: str):
    return db.query(Empleado).filter(Empleado.codigo_unico == codigo).first()


class DNIExistenteError(Exception):
    pass

class SucursalNoEncontradaError(Exception):
    pass


def get_empleado_por_dni(db: Session, dni: str):
    return db.query(Empleado).filter(Empleado.dni == dni).first()


def crear_empleado(
    db: Session,
    nombre: str,
    apellido: str,
    dni: str,
    cargo: str,
    sucursal_nombre: str,
) -> Empleado:
    # Verificar DNI duplicado antes de intentar el INSERT
    if get_empleado_por_dni(db, dni):
        raise DNIExistenteError(f"El DNI {dni} ya está registrado en el sistema.")
    sucursal = db.query(Sucursal).filter(Sucursal.nombre == sucursal_nombre).first()
    if not sucursal:
        raise SucursalNoEncontradaError(
            f"La tienda/sucursal '{sucursal_nombre}' no existe. Recarga la lista y vuelve a intentar."
        )
    codigo = f"{nombre[0].upper()}{apellido[0].upper()}{dni[-4:]}"
    base, n = codigo, 1
    while db.query(Empleado).filter(Empleado.codigo_unico == codigo).first():
        codigo = f"{base}{n}"
        n += 1
    emp = Empleado(
        nombre=nombre,
        apellido=apellido,
        dni=dni,
        cargo=cargo,
        codigo_unico=codigo,
        sucursal_id=sucursal.id,
        activo=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    salud = SaludEmpleado(empleado_id=emp.id)
    db.add(salud)
    db.commit()
    return emp


def actualizar_empleado(
    db: Session,
    empleado_id: int,
    nombre: str,
    apellido: str,
    dni: str,
    cargo: str,
    sucursal_nombre: str,
) -> Empleado:
    """Actualiza los datos editables de un empleado. El código QR no cambia."""
    emp = db.get(Empleado, empleado_id)
    if not emp:
        return None
    # Verificar que el DNI no pertenezca a OTRO empleado
    otro = db.query(Empleado).filter(
        Empleado.dni == dni,
        Empleado.id != empleado_id,
    ).first()
    if otro:
        raise DNIExistenteError(f"El DNI {dni} ya está registrado en otro empleado.")
    sucursal = db.query(Sucursal).filter(Sucursal.nombre == sucursal_nombre).first()
    emp.nombre      = nombre
    emp.apellido    = apellido
    emp.dni         = dni
    emp.cargo       = cargo
    emp.sucursal_id = sucursal.id if sucursal else emp.sucursal_id
    db.commit()
    db.refresh(emp)
    return emp


def desactivar_empleado(db: Session, empleado_id: int) -> None:
    emp = db.get(Empleado, empleado_id)
    if emp:
        emp.activo = False
        db.commit()


# ─────────────────────────── HORARIOS ────────────────────────────────────────

def get_horarios_empleado(db: Session, empleado_id: int):
    return (
        db.query(HorarioSemanal)
        .filter(HorarioSemanal.empleado_id == empleado_id)
        .all()
    )


def set_horario_base(db: Session, empleado_id: int, horario: dict) -> None:
    db.query(HorarioSemanal).filter(
        HorarioSemanal.empleado_id == empleado_id,
        HorarioSemanal.semana_inicio == None,
    ).delete()
    for dia, turno in horario.items():
        h = HorarioSemanal(
            empleado_id=empleado_id,
            dia_semana=dia,
            turno=turno,
            semana_inicio=None,
            semana_fin=None,
        )
        db.add(h)
    db.commit()


# ─────────────────────────── REGISTROS ───────────────────────────────────────

def get_registros_empleado(
    db: Session,
    empleado_id: int,
    fecha_desde: date,
    fecha_hasta: date,
):
    return (
        db.query(RegistroAsistencia)
        .filter(
            RegistroAsistencia.empleado_id == empleado_id,
            RegistroAsistencia.fecha >= fecha_desde,
            RegistroAsistencia.fecha <= fecha_hasta,
        )
        .order_by(RegistroAsistencia.fecha.desc())
        .all()
    )


# ─────────────────────────── SALUD ───────────────────────────────────────────

def get_salud_todos(db: Session):
    return (
        db.query(Empleado)
        .filter(Empleado.activo == True)
        .order_by(Empleado.apellido)
        .all()
    )
