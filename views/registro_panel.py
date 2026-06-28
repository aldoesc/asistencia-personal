import flet as ft
from backend.database import SessionLocal
from backend.logic import (
    procesar_registro,
    cerrar_turno_manual,
    consultar_ultimo_registro_por_codigo,
)
from datetime import datetime
try:
    import winsound
except Exception:
    winsound = None


class RegistroPanel:
    def __init__(self, page: ft.Page, refresh_callback):
        self.page = page
        self.refresh = refresh_callback
        self.ultimo_evento = ft.Column(spacing=4)
        self.feedback = ft.Text("", size=13, color=ft.Colors.GREY_300)
        self.feedback_time = ft.Text("", size=11, color=ft.Colors.GREY_500)
        self.feedback_container = ft.Container(
            content=ft.Column([self.feedback, self.feedback_time], spacing=2),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_400),
            border_radius=8,
            border=ft.border.all(1, ft.Colors.with_opacity(0.16, ft.Colors.BLUE_400)),
            height=62,
        )

        self.codigo_input = ft.TextField(
            label="Código de empleado",
            hint_text="Escanea QR o escribe...",
            on_submit=self.procesar,
            border_color=ft.Colors.BLUE_700,
            focused_border_color=ft.Colors.BLUE_400,
            border_radius=10,
            text_size=14,
            prefix_icon=ft.Icons.QR_CODE_SCANNER,
        )

    def build(self):
        return ft.Column(
            [
                # Título sidebar
                ft.Row(
                    [
                        ft.Icon(ft.Icons.FINGERPRINT_ROUNDED,
                                color=ft.Colors.BLUE_400, size=20),
                        ft.Text("Registro", size=16,
                                weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=4),

                # Input
                self.codigo_input,

                # Botón registrar
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE,
                                    color=ft.Colors.WHITE, size=18),
                            ft.Text("Registrar asistencia", color=ft.Colors.WHITE,
                                    size=14, weight=ft.FontWeight.W_500),
                        ],
                        spacing=8,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    on_click=self.procesar,
                    bgcolor=ft.Colors.BLUE_700,
                    border_radius=10,
                    padding=ft.padding.symmetric(vertical=12),
                    ink=True,
                ),
                ft.OutlinedButton(
                    "Consultar mi último registro",
                    icon=ft.Icons.HISTORY_TOGGLE_OFF,
                    on_click=self.consultar_ultimo_registro,
                    style=ft.ButtonStyle(
                        color=ft.Colors.GREY_300,
                        side=ft.BorderSide(1, "#2b313d"),
                    ),
                ),

                # Feedback
                self.feedback_container,

                ft.Divider(color="#21262d", height=24),

                # Último evento
                ft.Text("ÚLTIMO EVENTO", size=11,
                        color=ft.Colors.GREY_600, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=self.ultimo_evento,
                    padding=14,
                    bgcolor="#1c2128",
                    border_radius=12,
                    border=ft.border.all(1, "#21262d"),
                    height=80,
                ),
            ],
            spacing=12,
        )

    def procesar(self, e):
        codigo = self.codigo_input.value.strip().upper()
        if not codigo:
            self._set_feedback("⚠️ Ingrese un código", ft.Colors.AMBER_400)
            self.page.update()
            return
        self.codigo_input.value = ""
        with SessionLocal() as db:
            resultado = procesar_registro(db, codigo)

        if resultado.requiere_cierre:
            self._mostrar_cierre_pendiente(resultado)
        elif resultado.exito:
            color = ft.Colors.GREEN_400 if resultado.tipo == "ingreso" else ft.Colors.BLUE_400
            icono = "🟢" if resultado.tipo == "ingreso" else "🔵"
            hora = datetime.now().strftime("%H:%M:%S")
            codigo_seguro = self._mask_codigo(codigo)
            self._set_feedback(
                f"{icono} {resultado.mensaje} | {codigo_seguro} | {hora}",
                color,
                beep_kind="ok",
            )
            self._actualizar_ultimo_evento(resultado)
            self.refresh()
        else:
            self._set_feedback(f"❌ {resultado.mensaje}", ft.Colors.RED_400, beep_kind="error")
        self.page.update()

    def consultar_ultimo_registro(self, e):
        codigo_input = ft.TextField(
            label="Código de empleado",
            hint_text="Ej: AB1234",
            width=260,
            border_radius=8,
            autofocus=True,
        )
        info = ft.Text("", size=13, color=ft.Colors.GREY_300)

        def buscar(_):
            codigo = (codigo_input.value or "").strip().upper()
            if not codigo:
                info.value = "⚠️ Ingresa un código"
                info.color = ft.Colors.AMBER_400
                self.page.update()
                return
            with SessionLocal() as db:
                data = consultar_ultimo_registro_por_codigo(db, codigo)
            if not data:
                info.value = "❌ Código no encontrado"
                info.color = ft.Colors.RED_400
                self._beep("error")
            elif not data["fecha"]:
                info.value = (
                    f"Empleado: {data['nombre']}\n"
                    "Aún no tiene registros de asistencia."
                )
                info.color = ft.Colors.GREY_300
                self._beep("ok")
            else:
                ingreso = data["hora_ingreso"].strftime("%H:%M:%S") if data["hora_ingreso"] else "—"
                salida = data["hora_salida"].strftime("%H:%M:%S") if data["hora_salida"] else "—"
                estado = (data["estado"] or "—").replace("_", " ").title()
                info.value = (
                    f"Código: {self._mask_codigo(data['codigo'])}\n"
                    f"Fecha: {data['fecha'].isoformat()}\n"
                    f"Ingreso: {ingreso}\n"
                    f"Salida: {salida}\n"
                    f"Estado: {estado}"
                )
                info.color = ft.Colors.GREEN_300
                self._beep("ok")
            self.page.update()

        codigo_input.on_submit = buscar
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Consulta de último registro", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([codigo_input, info], spacing=12, tight=True),
                width=320,
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda _: self.page.close(dlg)),
                ft.ElevatedButton("Consultar", on_click=buscar, bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(dlg)

    def _actualizar_ultimo_evento(self, resultado):
        ahora = datetime.now().strftime("%H:%M:%S")
        tipo_color = ft.Colors.GREEN_400 if resultado.tipo == "ingreso" else ft.Colors.BLUE_400
        tipo_label = "INGRESO" if resultado.tipo == "ingreso" else "SALIDA"

        self.ultimo_evento.controls = [
            ft.Container(
                content=ft.Text(tipo_label, size=10, color=tipo_color,
                                weight=ft.FontWeight.BOLD),
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                bgcolor=ft.Colors.with_opacity(0.12, tipo_color),
                border_radius=4,
            ),
            ft.Text(resultado.mensaje, size=13, color=ft.Colors.WHITE),
            ft.Text(ahora, size=11, color=ft.Colors.GREY_500),
        ]

    def _mostrar_cierre_pendiente(self, resultado):
        hora_input = ft.TextField(
            label="Hora de salida (HH:MM)",
            width=220,
            border_radius=8,
            border_color=ft.Colors.AMBER_700,
            focused_border_color=ft.Colors.AMBER_400,
        )

        def cerrar(e):
            try:
                h, m = map(int, hora_input.value.split(":"))
                dt_salida = datetime.combine(
                    resultado.registro.fecha,
                    datetime.min.time().replace(hour=h, minute=m),
                )
                with SessionLocal() as db:
                    cerrar_turno_manual(
                        db, resultado.registro.id, dt_salida, nota="Cierre manual"
                    )
                self.page.close(dlg)
                self.page.update()
                self._set_feedback(
                    "✅ Turno cerrado. Puedes registrar nuevo ingreso.",
                    ft.Colors.GREEN_400,
                    beep_kind="ok",
                )
                self.refresh()
            except Exception:
                self._set_feedback("⚠️ Formato inválido. Usa HH:MM", ft.Colors.AMBER_400)
            self.page.update()

        def cancelar(e):
            self.page.close(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED,
                            color=ft.Colors.AMBER_400),
                    ft.Text("Turno sin cerrar", size=16,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(resultado.mensaje, size=13,
                                color=ft.Colors.GREY_400),
                        ft.Container(height=8),
                        hora_input,
                    ],
                    tight=True,
                    spacing=4,
                ),
                width=300,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=cancelar,
                              style=ft.ButtonStyle(color=ft.Colors.GREY_400)),
                ft.ElevatedButton(
                    "Confirmar cierre",
                    on_click=cerrar,
                    bgcolor=ft.Colors.AMBER_700,
                    color=ft.Colors.WHITE,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        # FIX: usar page.open() en Flet 0.27
        self.page.open(dlg)

    def _set_feedback(self, text: str, color: str, beep_kind: str = None):
        self.feedback.value = text
        self.feedback.color = color
        self.feedback_time.value = f"Hora: {datetime.now().strftime('%H:%M:%S')}"
        self.feedback_container.border = ft.border.all(1, ft.Colors.with_opacity(0.30, color))
        self.feedback_container.bgcolor = ft.Colors.with_opacity(0.12, color)
        if beep_kind:
            self._beep(beep_kind)

    def _mask_codigo(self, codigo: str) -> str:
        if not codigo or len(codigo) < 5:
            return codigo
        return f"{codigo[:2]}***{codigo[-2:]}"

    def _beep(self, kind: str):
        if not winsound:
            return
        try:
            if kind == "ok":
                winsound.MessageBeep(winsound.MB_OK)
            else:
                winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass
