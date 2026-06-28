from datetime import datetime
from backend.models import TipoTurno, EstadoAsistencia

# Configuración de turnos: hora de entrada esperada
TURNOS_CONFIG = {
    TipoTurno.TURNO_1: {"entrada": datetime.strptime("10:15", "%H:%M").time()},
    TipoTurno.TURNO_2: {"entrada": datetime.strptime("14:00", "%H:%M").time()},
    TipoTurno.TURNO_3: {"entrada": datetime.strptime("16:00", "%H:%M").time()},
}


def calcular_estado_asistencia(
    hora_ingreso: datetime, turno: TipoTurno
) -> tuple[EstadoAsistencia, int]:
    if turno == TipoTurno.DESCANSO:
        return EstadoAsistencia.DESCANSO, 0

    config = TURNOS_CONFIG[turno]
    hora_programada = config["entrada"]  # time object
    dt_programado = datetime.combine(hora_ingreso.date(), hora_programada)
    diff_min = (hora_ingreso - dt_programado).total_seconds() / 60

    # FIX: se agregó el rango TARDANZA_MEDIA (36-60 min) que estaba ausente.
    # Antes saltaba directamente de TARDANZA_BAJA a TARDANZA_GRAVE.
    if diff_min <= 15:
        return EstadoAsistencia.A_TIEMPO, 0
    elif diff_min <= 35:
        return EstadoAsistencia.TARDANZA_BAJA, int(diff_min)
    elif diff_min <= 60:
        return EstadoAsistencia.TARDANZA_MEDIA, int(diff_min)
    else:
        return EstadoAsistencia.TARDANZA_GRAVE, int(diff_min)

# ─────────────────────────────────────────────────────────────────────────────
# PEGAR ESTAS FUNCIONES AL FINAL DE backend/logic.py
# NO reemplaces el archivo completo — solo agrega lo que falte.
# ─────────────────────────────────────────────────────────────────────────────

def get_turno_nombre(turno) -> str:
    """Devuelve el nombre legible de un turno para mostrar en la UI."""
    from backend.models import TipoTurno
    nombres = {
        TipoTurno.TURNO_1:  "Turno 1  (10:15)",
        TipoTurno.TURNO_2:  "Turno 2  (14:00)",
        TipoTurno.TURNO_3:  "Turno 3  (16:00)",
        TipoTurno.DESCANSO: "Descanso",
    }
    return nombres.get(turno, str(turno))
