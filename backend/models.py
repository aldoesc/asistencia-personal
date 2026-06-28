# backend/models.py
# Modelos de base de datos - Sistema de Control de Personal

from sqlalchemy import (
    Column, Integer, String, DateTime, Time, Boolean,
    ForeignKey, Enum, Float, Text, Date
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class EstadoAsistencia(str, enum.Enum):
    A_TIEMPO     = "a_tiempo"
    TARDANZA_BAJA   = "tardanza_baja"
    TARDANZA_MEDIA  = "tardanza_media"
    TARDANZA_GRAVE  = "tardanza_grave"
    AUSENTE      = "ausente"
    DESCANSO     = "descanso"

class TipoTurno(str, enum.Enum):
    TURNO_1 = "turno_1"   # 10:15am - 4:30pm
    TURNO_2 = "turno_2"   # 2:00pm  - 8:00pm
    TURNO_3 = "turno_3"   # 4:00pm  - 10:00pm
    DESCANSO = "descanso"

class SaludNivel(str, enum.Enum):
    EXCELENTE    = "excelente"    # 90-100%
    REGULAR      = "regular"      # 70-89%
    OBSERVACION  = "observacion"  # 50-69%
    CRITICO      = "critico"      # 0-49%

class DiaSemana(str, enum.Enum):
    LUNES     = "lunes"
    MARTES    = "martes"
    MIERCOLES = "miercoles"
    JUEVES    = "jueves"
    VIERNES   = "viernes"
    SABADO    = "sabado"
    DOMINGO   = "domingo"


# ─────────────────────────────────────────────
# TABLA: SUCURSALES
# ─────────────────────────────────────────────

class Sucursal(Base):
    __tablename__ = "sucursales"

    id          = Column(Integer, primary_key=True, index=True)
    nombre      = Column(String(100), nullable=False)
    direccion   = Column(String(200))
    activa      = Column(Boolean, default=True)
    creado_en   = Column(DateTime, default=datetime.now)

    # Relaciones
    empleados   = relationship("Empleado", back_populates="sucursal")

    def __repr__(self):
        return f"<Sucursal {self.nombre}>"


# ─────────────────────────────────────────────
# TABLA: EMPLEADOS
# ─────────────────────────────────────────────

class Empleado(Base):
    __tablename__ = "empleados"

    id              = Column(Integer, primary_key=True, index=True)
    codigo_unico    = Column(String(10), unique=True, nullable=False, index=True)
    nombre          = Column(String(100), nullable=False)
    apellido        = Column(String(100), nullable=False)
    dni             = Column(String(20), unique=True, nullable=False)
    cargo           = Column(String(100), nullable=False)
    sucursal_id     = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    activo          = Column(Boolean, default=True)
    foto_path       = Column(String(255), nullable=True)
    qr_path         = Column(String(255), nullable=True)
    creado_en       = Column(DateTime, default=datetime.now)
    modificado_en   = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relaciones
    sucursal        = relationship("Sucursal", back_populates="empleados")
    horarios        = relationship("HorarioSemanal", back_populates="empleado", cascade="all, delete-orphan")
    registros       = relationship("RegistroAsistencia", back_populates="empleado", cascade="all, delete-orphan")
    salud           = relationship("SaludEmpleado", back_populates="empleado", uselist=False, cascade="all, delete-orphan")

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    def __repr__(self):
        return f"<Empleado {self.codigo_unico} - {self.nombre_completo}>"


# ─────────────────────────────────────────────
# TABLA: HORARIOS SEMANALES
# Cada fila = un día de la semana para un empleado
# ─────────────────────────────────────────────

class HorarioSemanal(Base):
    __tablename__ = "horarios_semanales"

    id              = Column(Integer, primary_key=True, index=True)
    empleado_id     = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    dia_semana      = Column(Enum(DiaSemana), nullable=False)
    turno           = Column(Enum(TipoTurno), nullable=False)
    # Semana específica (None = horario base recurrente)
    semana_inicio   = Column(Date, nullable=True)
    semana_fin      = Column(Date, nullable=True)
    creado_en       = Column(DateTime, default=datetime.now)
    modificado_en   = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relaciones
    empleado        = relationship("Empleado", back_populates="horarios")

    def __repr__(self):
        return f"<Horario {self.empleado_id} - {self.dia_semana} - {self.turno}>"


# ─────────────────────────────────────────────
# TABLA: REGISTRO DE ASISTENCIA
# ─────────────────────────────────────────────

class RegistroAsistencia(Base):
    __tablename__ = "registros_asistencia"

    id                  = Column(Integer, primary_key=True, index=True)
    empleado_id         = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    fecha               = Column(Date, nullable=False, index=True)

    # Ingreso
    hora_ingreso        = Column(DateTime, nullable=True)
    turno_asignado      = Column(Enum(TipoTurno), nullable=True)
    estado_asistencia   = Column(Enum(EstadoAsistencia), nullable=True)
    minutos_tardanza    = Column(Integer, default=0)

    # Salida
    hora_salida         = Column(DateTime, nullable=True)
    salida_manual       = Column(Boolean, default=False)  # True si admin la cargó

    # Flags
    ausencia_justificada = Column(Boolean, default=False)
    nota                = Column(Text, nullable=True)  # Nota del admin
    registrado_por_qr   = Column(Boolean, default=True)

    # Puntos de salud generados por este registro
    puntos_salud        = Column(Integer, default=0)

    creado_en           = Column(DateTime, default=datetime.now)
    modificado_en       = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relaciones
    empleado            = relationship("Empleado", back_populates="registros")

    def __repr__(self):
        return f"<Registro {self.empleado_id} - {self.fecha} - {self.estado_asistencia}>"


# ─────────────────────────────────────────────
# TABLA: SALUD DEL EMPLEADO
# Índice acumulado de responsabilidad
# ─────────────────────────────────────────────

class SaludEmpleado(Base):
    __tablename__ = "salud_empleados"

    id                  = Column(Integer, primary_key=True, index=True)
    empleado_id         = Column(Integer, ForeignKey("empleados.id"), unique=True, nullable=False)

    # Contadores del mes actual
    dias_a_tiempo       = Column(Integer, default=0)
    dias_tardanza_baja  = Column(Integer, default=0)
    dias_tardanza_media = Column(Integer, default=0)
    dias_tardanza_grave = Column(Integer, default=0)
    dias_ausente        = Column(Integer, default=0)
    dias_justificado    = Column(Integer, default=0)

    # Puntos y porcentaje
    puntos_totales      = Column(Integer, default=0)
    puntos_posibles     = Column(Integer, default=0)
    porcentaje_salud    = Column(Float, default=100.0)
    nivel_salud         = Column(Enum(SaludNivel), default=SaludNivel.EXCELENTE)

    # Mes de referencia
    mes_referencia      = Column(String(7))  # formato: "2026-05"

    actualizado_en      = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relaciones
    empleado            = relationship("Empleado", back_populates="salud")

    def __repr__(self):
        return f"<Salud {self.empleado_id} - {self.porcentaje_salud}% - {self.nivel_salud}>"


# ─────────────────────────────────────────────
# TABLA: ADMIN
# ─────────────────────────────────────────────

class Admin(Base):
    __tablename__ = "admins"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False)
    password_hash   = Column(String(255), nullable=False)
    nombre          = Column(String(100))
    activo          = Column(Boolean, default=True)
    creado_en       = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Admin {self.username}>"
