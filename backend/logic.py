# backend/logic.py
# Toda la lógica de negocio del sistema

from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from .models import (
    Empleado, HorarioSemanal, RegistroAsistencia, SaludEmpleado,
    EstadoAsistencia, TipoTurno, SaludNivel, DiaSemana
)


# ─────────────────────────────────────────────
# CONFIGURACIÓN DE TURNOS
# ─────────────────────────────────────────────

TURNOS_CONFIG = {
    TipoTurno.TURNO_1: {
        "nombre":    "Turno 1",
        "entrada":   time(10, 15),
        "salida":    time(16, 30),
        "tolerancia": 15,          # minutos
    },
    TipoTurno.TURNO_2: {
        "nombre":    "Turno 2",
        "entrada":   time(14, 0),
        "salida":    time(20, 0),
        "tolerancia": 15,
    },
    TipoTurno.TURNO_3: {
        "nombre":    "Turno 3",
        "entrada":   time(16, 0),
        "salida":    time(22, 0),
        "tolerancia": 15,
    },
}

# Puntos por cada estado
PUNTOS_CONFIG = {
    EstadoAsistencia.A_TIEMPO:       10,
    EstadoAsistencia.TARDANZA_BAJA:  -2,
    EstadoAsistencia.TARDANZA_MEDIA: -5,
    EstadoAsistencia.TARDANZA_GRAVE: -10,
    EstadoAsistencia.AUSENTE:        -15,
    EstadoAsistencia.DESCANSO:       0,
}

DIAS_MAP = {
    0: DiaSemana.LUNES,
    1: DiaSemana.MARTES,
    2: DiaSemana.MIERCOLES,
    3: DiaSemana.JUEVES,
    4: DiaSemana.VIERNES,
    5: DiaSemana.SABADO,
    6: DiaSemana.DOMINGO,
}


# ─────────────────────────────────────────────
# LÓGICA DE TURNOS
# ─────────────────────────────────────────────

def get_turno_config(turno: TipoTurno) -> dict:
    """Retorna la configuración de un turno."""
    return TURNOS_CONFIG.get(turno, {})


def get_turno_nombre(turno: TipoTurno) -> str:
    config = TURNOS_CONFIG.get(turno)
    if config:
        h = config["entrada"]
        return f"{config['nombre']} ({h.strftime('%I:%M %p')})"
    return "Descanso"


def get_horario_empleado_hoy(db: Session, empleado_id: int, fecha: date = None) -> TipoTurno:
    """
    Retorna el turno asignado a un empleado para un día específico.
    Primero busca horario específico por semana, luego el horario base.
    """
    if fecha is None:
        fecha = date.today()

    dia_semana = DIAS_MAP[fecha.weekday()]

    # Buscar horario específico para esa semana
    horario = db.query(HorarioSemanal).filter(
        HorarioSemanal.empleado_id  == empleado_id,
        HorarioSemanal.dia_semana   == dia_semana,
        HorarioSemanal.semana_inicio <= fecha,
        HorarioSemanal.semana_fin   >= fecha,
    ).first()

    # Si no hay específico, buscar horario base (sin semana)
    if not horario:
        horario = db.query(HorarioSemanal).filter(
            HorarioSemanal.empleado_id  == empleado_id,
            HorarioSemanal.dia_semana   == dia_semana,
            HorarioSemanal.semana_inicio == None,
        ).first()

    if horario:
        return horario.turno

    return None  # Sin horario asignado


# ─────────────────────────────────────────────
# LÓGICA DE TARDANZAS
# ─────────────────────────────────────────────

def calcular_estado_asistencia(
    hora_ingreso: datetime,
    turno: TipoTurno
) -> tuple[EstadoAsistencia, int]:
    """
    Calcula el estado de asistencia comparando la hora de ingreso
    con el turno asignado.

    Retorna: (EstadoAsistencia, minutos_tardanza)
    """
    if turno == TipoTurno.DESCANSO:
        return EstadoAsistencia.DESCANSO, 0

    config = TURNOS_CONFIG[turno]
    hora_entrada_programada = config["entrada"]
    tolerancia_minutos      = config["tolerancia"]

    # Convertir hora programada a datetime del mismo día
    fecha_registro = hora_ingreso.date()
    dt_programado  = datetime.combine(fecha_registro, hora_entrada_programada)
    dt_tolerancia  = dt_programado + timedelta(minutes=tolerancia_minutos)

    # Calcular diferencia
    diferencia = (hora_ingreso - dt_programado).total_seconds() / 60

    if diferencia <= tolerancia_minutos:
        # Dentro del margen de tolerancia (incluye llegadas antes de hora)
        return EstadoAsistencia.A_TIEMPO, 0
    elif diferencia <= 30:
        return EstadoAsistencia.TARDANZA_BAJA, int(diferencia)
    elif diferencia <= 60:
        return EstadoAsistencia.TARDANZA_MEDIA, int(diferencia)
    else:
        return EstadoAsistencia.TARDANZA_GRAVE, int(diferencia)


# ─────────────────────────────────────────────
# LÓGICA DE REGISTRO (INGRESO / SALIDA)
# ─────────────────────────────────────────────

class ResultadoRegistro:
    def __init__(self, exito: bool, tipo: str, mensaje: str,
                 registro=None, empleado=None, requiere_cierre: bool = False):
        self.exito           = exito
        self.tipo            = tipo       # "ingreso" | "salida" | "error" | "cierre_pendiente"
        self.mensaje         = mensaje
        self.registro        = registro
        self.empleado        = empleado
        self.requiere_cierre = requiere_cierre


def procesar_registro(db: Session, codigo: str, ahora: datetime = None) -> ResultadoRegistro:
    """
    Lógica principal de registro.
    Determina automáticamente si es ingreso o salida.
    """
    if ahora is None:
        ahora = datetime.now()

    hoy = ahora.date()

    # 1. Buscar empleado
    empleado = db.query(Empleado).filter(
        Empleado.codigo_unico == codigo,
        Empleado.activo == True
    ).first()

    if not empleado:
        return ResultadoRegistro(
            exito=False, tipo="error",
            mensaje=f"Código '{codigo}' no encontrado. Verifica e intenta de nuevo."
        )

    # 2. Verificar si tiene turno abierto SIN SALIDA de un día anterior
    registro_sin_cerrar = db.query(RegistroAsistencia).filter(
        RegistroAsistencia.empleado_id  == empleado.id,
        RegistroAsistencia.fecha        <  hoy,
        RegistroAsistencia.hora_ingreso != None,
        RegistroAsistencia.hora_salida  == None,
    ).order_by(RegistroAsistencia.fecha.desc()).first()

    if registro_sin_cerrar:
        return ResultadoRegistro(
            exito=False,
            tipo="cierre_pendiente",
            mensaje=(
                f"⚠️ {empleado.nombre_completo}, tienes un turno sin cerrar "
                f"del {registro_sin_cerrar.fecha.strftime('%d/%m/%Y')}. "
                f"Debes registrar tu salida antes de continuar."
            ),
            registro=registro_sin_cerrar,
            empleado=empleado,
            requiere_cierre=True
        )

    # 3. Buscar registro de HOY
    registro_hoy = db.query(RegistroAsistencia).filter(
        RegistroAsistencia.empleado_id == empleado.id,
        RegistroAsistencia.fecha       == hoy,
    ).first()

    # 4. Sin registro hoy → INGRESO
    if not registro_hoy:
        return _registrar_ingreso(db, empleado, ahora, hoy)

    # 5. Tiene ingreso pero sin salida → SALIDA
    if registro_hoy.hora_ingreso and not registro_hoy.hora_salida:
        return _registrar_salida(db, empleado, registro_hoy, ahora)

    # 6. Tiene ingreso y salida → nuevo INGRESO (segundo turno del día, poco común)
    return _registrar_ingreso(db, empleado, ahora, hoy)


def _registrar_ingreso(
    db: Session, empleado: Empleado,
    ahora: datetime, hoy: date
) -> ResultadoRegistro:
    """Crea un nuevo registro de ingreso."""

    # Obtener turno del día
    turno = get_horario_empleado_hoy(db, empleado.id, hoy)

    if turno == TipoTurno.DESCANSO:
        return ResultadoRegistro(
            exito=False, tipo="error",
            mensaje=f"{empleado.nombre_completo}, hoy es tu día de descanso. 😊"
        )

    # Calcular estado
    if turno:
        estado, minutos = calcular_estado_asistencia(ahora, turno)
        puntos = PUNTOS_CONFIG[estado]
    else:
        # Sin horario asignado, registrar igual como a tiempo
        estado, minutos, puntos = EstadoAsistencia.A_TIEMPO, 0, 10

    # Crear registro
    registro = RegistroAsistencia(
        empleado_id         = empleado.id,
        fecha               = hoy,
        hora_ingreso        = ahora,
        turno_asignado      = turno,
        estado_asistencia   = estado,
        minutos_tardanza    = minutos,
        puntos_salud        = puntos,
    )
    db.add(registro)

    # Actualizar salud
    _actualizar_salud(db, empleado, estado, puntos)

    db.commit()
    db.refresh(registro)

    # Mensaje según estado
    mensajes = {
        EstadoAsistencia.A_TIEMPO:       f"✅ Bienvenido/a {empleado.nombre}. Ingreso a tiempo.",
        EstadoAsistencia.TARDANZA_BAJA:  f"🟡 Hola {empleado.nombre}. Tardanza leve: {minutos} min.",
        EstadoAsistencia.TARDANZA_MEDIA: f"🟠 Hola {empleado.nombre}. Tardanza media: {minutos} min.",
        EstadoAsistencia.TARDANZA_GRAVE: f"🔴 {empleado.nombre}. Tardanza grave: {minutos} min.",
    }

    return ResultadoRegistro(
        exito=True, tipo="ingreso",
        mensaje=mensajes.get(estado, f"Ingreso registrado - {empleado.nombre}"),
        registro=registro, empleado=empleado
    )


def _registrar_salida(
    db: Session, empleado: Empleado,
    registro: RegistroAsistencia, ahora: datetime
) -> ResultadoRegistro:
    """Registra la salida en un registro existente."""

    registro.hora_salida   = ahora
    registro.modificado_en = ahora
    db.commit()
    db.refresh(registro)

    duracion = ahora - registro.hora_ingreso
    horas    = int(duracion.total_seconds() // 3600)
    minutos  = int((duracion.total_seconds() % 3600) // 60)

    return ResultadoRegistro(
        exito=True, tipo="salida",
        mensaje=f"👋 Hasta luego {empleado.nombre}. Salida: {ahora.strftime('%H:%M')} | Duración: {horas}h {minutos}m.",
        registro=registro, empleado=empleado
    )


def cerrar_turno_manual(
    db: Session, registro_id: int,
    hora_salida: datetime, nota: str = None
) -> ResultadoRegistro:
    """Admin cierra manualmente un turno sin salida."""
    registro = db.query(RegistroAsistencia).filter(
        RegistroAsistencia.id == registro_id
    ).first()

    if not registro:
        return ResultadoRegistro(exito=False, tipo="error", mensaje="Registro no encontrado.")

    registro.hora_salida   = hora_salida
    registro.salida_manual = True
    registro.nota          = nota
    db.commit()

    return ResultadoRegistro(
        exito=True, tipo="salida",
        mensaje="✅ Salida registrada manualmente.",
        registro=registro
    )


# ─────────────────────────────────────────────
# LÓGICA DE SALUD
# ─────────────────────────────────────────────

def _actualizar_salud(
    db: Session, empleado: Empleado,
    estado: EstadoAsistencia, puntos: int
):
    """Actualiza el índice de salud del empleado."""
    mes_actual = date.today().strftime("%Y-%m")

    salud = db.query(SaludEmpleado).filter(
        SaludEmpleado.empleado_id == empleado.id
    ).first()

    if not salud:
        salud = SaludEmpleado(
            empleado_id     = empleado.id,
            mes_referencia  = mes_actual
        )
        db.add(salud)

    # Resetear si cambió el mes
    if salud.mes_referencia != mes_actual:
        salud.dias_a_tiempo       = 0
        salud.dias_tardanza_baja  = 0
        salud.dias_tardanza_media = 0
        salud.dias_tardanza_grave = 0
        salud.dias_ausente        = 0
        salud.dias_justificado    = 0
        salud.puntos_totales      = 0
        salud.puntos_posibles     = 0
        salud.mes_referencia      = mes_actual

    # Incrementar contadores
    if estado == EstadoAsistencia.A_TIEMPO:
        salud.dias_a_tiempo += 1
    elif estado == EstadoAsistencia.TARDANZA_BAJA:
        salud.dias_tardanza_baja += 1
    elif estado == EstadoAsistencia.TARDANZA_MEDIA:
        salud.dias_tardanza_media += 1
    elif estado == EstadoAsistencia.TARDANZA_GRAVE:
        salud.dias_tardanza_grave += 1
    elif estado == EstadoAsistencia.AUSENTE:
        salud.dias_ausente += 1

    # Puntos
    salud.puntos_totales  += puntos
    salud.puntos_posibles += PUNTOS_CONFIG[EstadoAsistencia.A_TIEMPO]  # máximo posible

    # Calcular porcentaje (mínimo 0)
    if salud.puntos_posibles > 0:
        raw = (salud.puntos_totales / salud.puntos_posibles) * 100
        salud.porcentaje_salud = max(0.0, round(raw, 1))
    else:
        salud.porcentaje_salud = 100.0

    # Nivel
    p = salud.porcentaje_salud
    if p >= 90:
        salud.nivel_salud = SaludNivel.EXCELENTE
    elif p >= 70:
        salud.nivel_salud = SaludNivel.REGULAR
    elif p >= 50:
        salud.nivel_salud = SaludNivel.OBSERVACION
    else:
        salud.nivel_salud = SaludNivel.CRITICO

    db.flush()


def recalcular_salud_empleado(db: Session, empleado_id: int, mes: str = None):
    """Recalcula desde cero la salud de un empleado para el mes dado."""
    if not mes:
        mes = date.today().strftime("%Y-%m")

    año, m = map(int, mes.split("-"))
    desde  = date(año, m, 1)
    hasta  = date(año, m + 1, 1) if m < 12 else date(año + 1, 1, 1)

    registros = db.query(RegistroAsistencia).filter(
        RegistroAsistencia.empleado_id == empleado_id,
        RegistroAsistencia.fecha       >= desde,
        RegistroAsistencia.fecha       <  hasta,
    ).all()

    salud = db.query(SaludEmpleado).filter(
        SaludEmpleado.empleado_id == empleado_id
    ).first()

    if not salud:
        salud = SaludEmpleado(empleado_id=empleado_id)
        db.add(salud)

    # Reset
    salud.dias_a_tiempo       = 0
    salud.dias_tardanza_baja  = 0
    salud.dias_tardanza_media = 0
    salud.dias_tardanza_grave = 0
    salud.dias_ausente        = 0
    salud.puntos_totales      = 0
    salud.puntos_posibles     = 0
    salud.mes_referencia      = mes

    for reg in registros:
        estado = reg.estado_asistencia
        if not estado or estado == EstadoAsistencia.DESCANSO:
            continue

        puntos = PUNTOS_CONFIG.get(estado, 0)
        if reg.ausencia_justificada:
            puntos = 0

        salud.puntos_totales  += puntos
        salud.puntos_posibles += 10

        if estado == EstadoAsistencia.A_TIEMPO:
            salud.dias_a_tiempo += 1
        elif estado == EstadoAsistencia.TARDANZA_BAJA:
            salud.dias_tardanza_baja += 1
        elif estado == EstadoAsistencia.TARDANZA_MEDIA:
            salud.dias_tardanza_media += 1
        elif estado == EstadoAsistencia.TARDANZA_GRAVE:
            salud.dias_tardanza_grave += 1
        elif estado == EstadoAsistencia.AUSENTE:
            salud.dias_ausente += 1

    if salud.puntos_posibles > 0:
        raw = (salud.puntos_totales / salud.puntos_posibles) * 100
        salud.porcentaje_salud = max(0.0, round(raw, 1))
    else:
        salud.porcentaje_salud = 100.0

    p = salud.porcentaje_salud
    if p >= 90:
        salud.nivel_salud = SaludNivel.EXCELENTE
    elif p >= 70:
        salud.nivel_salud = SaludNivel.REGULAR
    elif p >= 50:
        salud.nivel_salud = SaludNivel.OBSERVACION
    else:
        salud.nivel_salud = SaludNivel.CRITICO

    db.commit()
    return salud


# ─────────────────────────────────────────────
# HELPERS DE REPORTE
# ─────────────────────────────────────────────

def get_reporte_diario(db: Session, fecha: date = None, sucursal_id: int = None):
    """Retorna snapshot del día para el dashboard."""
    if not fecha:
        fecha = date.today()

    query = db.query(Empleado).filter(Empleado.activo == True)
    if sucursal_id:
        query = query.filter(Empleado.sucursal_id == sucursal_id)

    empleados = query.all()
    resultado = []

    for emp in empleados:
        turno   = get_horario_empleado_hoy(db, emp.id, fecha)
        registro = db.query(RegistroAsistencia).filter(
            RegistroAsistencia.empleado_id == emp.id,
            RegistroAsistencia.fecha       == fecha,
        ).first()

        salud = db.query(SaludEmpleado).filter(
            SaludEmpleado.empleado_id == emp.id
        ).first()

        resultado.append({
            "empleado_id":    emp.id,
            "codigo":         emp.codigo_unico,
            "nombre":         emp.nombre_completo,
            "cargo":          emp.cargo,
            "sucursal":       emp.sucursal.nombre if emp.sucursal else "",
            "turno":          turno,
            "turno_nombre":   get_turno_nombre(turno) if turno else "Sin turno",
            "hora_ingreso":   registro.hora_ingreso if registro else None,
            "hora_salida":    registro.hora_salida  if registro else None,
            "estado":         registro.estado_asistencia if registro else (
                                EstadoAsistencia.DESCANSO if turno == TipoTurno.DESCANSO
                                else EstadoAsistencia.AUSENTE
                              ),
            "minutos_tardanza": registro.minutos_tardanza if registro else 0,
            "salud_porcentaje": salud.porcentaje_salud if salud else 100.0,
            "salud_nivel":      salud.nivel_salud if salud else SaludNivel.EXCELENTE,
        })

    return resultado


def get_mapa_semanal(db: Session, sucursal_id: int = None, semana_inicio: date = None):
    """Retorna el mapa de comportamiento semanal."""
    if not semana_inicio:
        hoy = date.today()
        semana_inicio = hoy - timedelta(days=hoy.weekday())

    dias = [semana_inicio + timedelta(days=i) for i in range(7)]

    query = db.query(Empleado).filter(Empleado.activo == True)
    if sucursal_id:
        query = query.filter(Empleado.sucursal_id == sucursal_id)

    empleados = query.all()
    mapa      = []

    for emp in empleados:
        fila = {"empleado_id": emp.id, "nombre": emp.nombre_completo, "dias": []}

        for dia in dias:
            turno    = get_horario_empleado_hoy(db, emp.id, dia)
            registro = db.query(RegistroAsistencia).filter(
                RegistroAsistencia.empleado_id == emp.id,
                RegistroAsistencia.fecha       == dia,
            ).first()

            if turno == TipoTurno.DESCANSO:
                estado_dia = "descanso"
            elif registro and registro.estado_asistencia:
                estado_dia = registro.estado_asistencia.value
            elif dia <= date.today():
                estado_dia = "ausente"
            else:
                estado_dia = "pendiente"

            fila["dias"].append({
                "fecha":  dia.isoformat(),
                "estado": estado_dia,
                "turno":  turno.value if turno else None,
            })

        mapa.append(fila)

    return {"semana_inicio": semana_inicio.isoformat(), "dias": [d.isoformat() for d in dias], "empleados": mapa}


def consultar_ultimo_registro_por_codigo(db: Session, codigo: str):
    """Retorna el último registro de asistencia de un empleado por código."""
    empleado = db.query(Empleado).filter(
        Empleado.codigo_unico == codigo,
        Empleado.activo == True
    ).first()
    if not empleado:
        return None

    reg = db.query(RegistroAsistencia).filter(
        RegistroAsistencia.empleado_id == empleado.id
    ).order_by(
        RegistroAsistencia.fecha.desc(),
        RegistroAsistencia.hora_ingreso.desc()
    ).first()
    if not reg:
        return {
            "codigo": empleado.codigo_unico,
            "nombre": empleado.nombre_completo,
            "fecha": None,
            "hora_ingreso": None,
            "hora_salida": None,
            "estado": None,
        }

    return {
        "codigo": empleado.codigo_unico,
        "nombre": empleado.nombre_completo,
        "fecha": reg.fecha,
        "hora_ingreso": reg.hora_ingreso,
        "hora_salida": reg.hora_salida,
        "estado": reg.estado_asistencia.value if reg.estado_asistencia else None,
    }
