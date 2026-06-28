import flet as ft
import asyncio
from datetime import datetime
from backend.database import SessionLocal
from backend.logic import get_reporte_diario, get_mapa_semanal
from backend.models import EstadoAsistencia, SaludNivel
from backend.crud import verificar_admin
from views.registro_panel import RegistroPanel
from views.admin_panel import AdminPanel

ESTADO_ICONO = {
    EstadoAsistencia.A_TIEMPO:      ("✅", ft.Colors.GREEN_400,  "A tiempo"),
    EstadoAsistencia.TARDANZA_BAJA: ("🟡", ft.Colors.AMBER_400,  "T. Baja"),
    EstadoAsistencia.TARDANZA_MEDIA:("🟠", ft.Colors.ORANGE_400, "T. Media"),
    EstadoAsistencia.TARDANZA_GRAVE:("🔴", ft.Colors.RED_400,    "T. Grave"),
    EstadoAsistencia.AUSENTE:       ("❌", ft.Colors.RED_700,    "Ausente"),
    EstadoAsistencia.DESCANSO:      ("💤", ft.Colors.PURPLE_400, "Descanso"),
}

SALUD_ICONO = {
    SaludNivel.EXCELENTE:   ("🟢", ft.Colors.GREEN_400),
    SaludNivel.REGULAR:     ("🟡", ft.Colors.AMBER_400),
    SaludNivel.OBSERVACION: ("🟠", ft.Colors.ORANGE_400),
    SaludNivel.CRITICO:     ("🔴", ft.Colors.RED_400),
}


def _stat_card(icono, titulo, valor, color):
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(icono, size=20),
                            width=40, height=40,
                            bgcolor=ft.Colors.with_opacity(0.15, color),
                            border_radius=10,
                            alignment=ft.alignment.center,
                        ),
                        ft.Column(
                            [
                                ft.Text(str(valor), size=26,
                                        weight=ft.FontWeight.BOLD, color=color),
                                ft.Text(titulo, size=11, color=ft.Colors.GREY_400),
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
        ),
        padding=ft.padding.symmetric(horizontal=20, vertical=14),
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
        border_radius=14,
        border=ft.border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
        expand=True,
    )


class DashboardView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.registro_panel = RegistroPanel(page, self.refresh)
        self.admin_panel = AdminPanel(page)
        self.stats_row = ft.Row(spacing=12)
        self.tabla = ft.DataTable(columns=[], rows=[])
        self.mapa_container = ft.Column()
        self._login_dialog = None
        self._kiosk_placeholder = None
        self._autolock_task_started = False

    def build(self):
        self.page.clean()
        self.page.appbar = None
        self.page.padding = 0
        self.page.bgcolor = "#0f1117"

        # ── Header ───────────────────────────────────────────────────────
        is_admin = self.page.session.get("admin_activo")
        admin_user = self.page.session.get("user") or ""

        # Track activity for autolock.
        self.page.session.set("last_activity_ts", datetime.now().timestamp())
        self.page.on_user_activity = self._on_user_activity

        admin_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED,
                            color=ft.Colors.BLUE_300, size=18),
                    ft.Text(
                        f"Admin  ·  {admin_user}" if is_admin else "Admin",
                        size=13, color=ft.Colors.BLUE_300,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_400),
            border_radius=10,
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.BLUE_400)),
            on_click=self.abrir_admin,
            ink=True,
        )

        logout_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.LOGOUT, color=ft.Colors.GREY_400, size=16),
                    ft.Text("Salir", size=13, color=ft.Colors.GREY_400),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            border_radius=10,
            on_click=self._cerrar_sesion_admin,
            ink=True,
            visible=is_admin,
        )

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.BUSINESS_CENTER_ROUNDED,
                                                color=ft.Colors.BLUE_400, size=22),
                                width=38, height=38,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_400),
                                border_radius=10,
                                alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                [
                                    ft.Text("Control de Personal", size=16,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.WHITE),
                                    ft.Text("Panel principal", size=11,
                                            color=ft.Colors.GREY_500),
                                ],
                                spacing=0,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.CIRCLE, size=8,
                                                color=ft.Colors.GREEN_400),
                                        ft.Text("En línea", size=11,
                                                color=ft.Colors.GREY_400),
                                    ],
                                    spacing=6,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_400),
                                border_radius=20,
                            ),
                            logout_btn,
                            admin_btn,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=24, vertical=14),
            bgcolor="#161b22",
            border=ft.border.only(bottom=ft.BorderSide(1, "#21262d")),
        )

        # ── Layout ───────────────────────────────────────────────────────
        right_content = self._build_main_content() if is_admin else self._build_kiosk_content()

        content = ft.Row(
            [
                ft.Container(
                    content=self.registro_panel.build(),
                    width=300,
                    bgcolor="#161b22",
                    border=ft.border.only(right=ft.BorderSide(1, "#21262d")),
                    padding=20,
                ),
                ft.Container(
                    content=right_content,
                    expand=True,
                    padding=ft.padding.all(24),
                ),
            ],
            expand=True,
            spacing=0,
        )

        self.page.add(
            ft.Column([header, content], spacing=0, expand=True)
        )
        if is_admin:
            self.refresh()
        else:
            self.page.update()

        # Start/refresh autolock timer (only meaningful when admin logged in).
        self._ensure_autolock_timer()

    def _build_main_content(self):
        self.stats_row = ft.Row(spacing=12)

        self.tabla = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Empleado", color=ft.Colors.GREY_400, size=12)),
                ft.DataColumn(ft.Text("Cargo",    color=ft.Colors.GREY_400, size=12)),
                ft.DataColumn(ft.Text("Turno",    color=ft.Colors.GREY_400, size=12)),
                ft.DataColumn(ft.Text("Ingreso",  color=ft.Colors.GREY_400, size=12)),
                ft.DataColumn(ft.Text("Salida",   color=ft.Colors.GREY_400, size=12)),
                ft.DataColumn(ft.Text("Estado",   color=ft.Colors.GREY_400, size=12)),
                ft.DataColumn(ft.Text("Salud",    color=ft.Colors.GREY_400, size=12)),
            ],
            rows=[],
            heading_row_color="#1c2128",
            heading_row_height=44,
            border=ft.border.all(1, "#21262d"),
            border_radius=12,
            horizontal_lines=ft.BorderSide(1, "#21262d"),
            column_spacing=24,
        )

        tabla_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Asistencia de hoy", size=15,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE),
                            ft.Container(
                                content=ft.Text("Actualizar", size=11,
                                                color=ft.Colors.BLUE_400),
                                on_click=lambda _: self.refresh(),
                                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_400),
                                border_radius=6,
                                ink=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Column([self.tabla], scroll=ft.ScrollMode.AUTO),
                ],
                spacing=16,
            ),
            padding=20,
            bgcolor="#161b22",
            border_radius=16,
            border=ft.border.all(1, "#21262d"),
        )

        self.mapa_container = ft.Column(spacing=4)
        mapa_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Mapa semanal", size=15,
                            weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    self.mapa_container,
                ],
                spacing=14,
            ),
            padding=20,
            bgcolor="#161b22",
            border_radius=16,
            border=ft.border.all(1, "#21262d"),
        )

        return ft.Column(
            [
                ft.Text("Dashboard", size=22,
                        weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                self.stats_row,
                tabla_card,
                mapa_card,
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_kiosk_content(self):
        self._kiosk_placeholder = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Modo registro (kiosko)",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Text(
                        "La pantalla queda lista para registrar asistencia.\n"
                        "Para ver dashboard, reportes o administrar personal, ingresa como Admin.",
                        size=13,
                        color=ft.Colors.GREY_500,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.LOCK_OUTLINE, color=ft.Colors.GREY_500),
                                ft.Text(
                                    "Datos sensibles ocultos",
                                    color=ft.Colors.GREY_400,
                                    size=13,
                                ),
                            ],
                            spacing=10,
                        ),
                        padding=16,
                        bgcolor="#161b22",
                        border_radius=16,
                        border=ft.border.all(1, "#21262d"),
                    ),
                ],
                spacing=10,
            ),
        )
        return ft.Column([self._kiosk_placeholder], expand=True, scroll=ft.ScrollMode.AUTO)

    def refresh(self):
        if not self.page.session.get("admin_activo"):
            return
        with SessionLocal() as db:
            reporte = get_reporte_diario(db)
            mapa    = get_mapa_semanal(db)

        conteos = {"a_tiempo": 0, "tardanzas": 0, "ausentes": 0, "descansos": 0}
        for r in reporte:
            e = r["estado"]
            if e == EstadoAsistencia.A_TIEMPO:
                conteos["a_tiempo"] += 1
            elif e in (EstadoAsistencia.TARDANZA_BAJA,
                       EstadoAsistencia.TARDANZA_MEDIA,
                       EstadoAsistencia.TARDANZA_GRAVE):
                conteos["tardanzas"] += 1
            elif e == EstadoAsistencia.AUSENTE:
                conteos["ausentes"] += 1
            elif e == EstadoAsistencia.DESCANSO:
                conteos["descansos"] += 1

        self.stats_row.controls = [
            _stat_card("✅", "A tiempo",  conteos["a_tiempo"],  ft.Colors.GREEN_400),
            _stat_card("⏰", "Tardanzas", conteos["tardanzas"], ft.Colors.AMBER_400),
            _stat_card("❌", "Ausentes",  conteos["ausentes"],  ft.Colors.RED_400),
            _stat_card("💤", "Descansos", conteos["descansos"], ft.Colors.PURPLE_400),
        ]

        self.tabla.rows.clear()
        for r in reporte:
            icono, color, label = ESTADO_ICONO.get(
                r["estado"], ("❓", ft.Colors.GREY_400, ""))
            salud_info = SALUD_ICONO.get(r["salud_nivel"])
            salud_porc = int(r["salud_porcentaje"]) if r["salud_porcentaje"] else 0
            salud_icono = salud_info[0] if salud_info else ""
            salud_color = salud_info[1] if salud_info else ft.Colors.GREY_400
            ingreso = r["hora_ingreso"].strftime("%H:%M") if r["hora_ingreso"] else "—"
            salida  = r["hora_salida"].strftime("%H:%M")  if r["hora_salida"]  else "—"

            self.tabla.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(r["nombre"], weight=ft.FontWeight.W_500,
                                        color=ft.Colors.WHITE)),
                    ft.DataCell(ft.Text(r["cargo"], color=ft.Colors.GREY_400, size=13)),
                    ft.DataCell(ft.Text(r["turno_nombre"] or "Sin turno",
                                        color=ft.Colors.GREY_400, size=13)),
                    ft.DataCell(ft.Text(ingreso, color=ft.Colors.WHITE, size=13)),
                    ft.DataCell(ft.Text(salida,  color=ft.Colors.GREY_500, size=13)),
                    ft.DataCell(
                        ft.Container(
                            content=ft.Text(f"{icono} {label}", size=12, color=color),
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            bgcolor=ft.Colors.with_opacity(0.1, color),
                            border_radius=6,
                        )
                    ),
                    ft.DataCell(
                        ft.Text(f"{salud_icono} {salud_porc}%",
                                color=salud_color, size=13)
                    ),
                ])
            )

        self.mapa_container.controls.clear()
        if mapa and mapa.get("empleados"):
            dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            self.mapa_container.controls.append(
                ft.Row(
                    [ft.Text("", width=160)]
                    + [ft.Text(d, width=44, size=12, color=ft.Colors.GREY_500,
                               text_align=ft.TextAlign.CENTER) for d in dias],
                    spacing=0,
                )
            )
            for emp in mapa["empleados"]:
                self.mapa_container.controls.append(
                    ft.Row(
                        [ft.Text(emp["nombre"][:22], width=160, size=13,
                                 color=ft.Colors.GREY_300)]
                        + [
                            ft.Container(
                                content=ft.Text(self._estado_icono(d["estado"]),
                                                size=16, text_align=ft.TextAlign.CENTER),
                                width=44, height=32,
                                alignment=ft.alignment.center,
                                border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                            )
                            for d in emp["dias"]
                        ],
                        spacing=0,
                    )
                )
        self.page.update()

    def _estado_icono(self, estado):
        return {
            "a_tiempo": "✅", "tardanza_baja": "🟡",
            "tardanza_media": "🟠", "tardanza_grave": "🔴",
            "ausente": "❌", "descanso": "💤", "pendiente": "⬜",
        }.get(estado, "⬜")

    # ── Login de administrador (modal) ────────────────────────────────────
    def abrir_admin(self, e):
        if self.page.session.get("admin_activo"):
            # Ya autenticado → abrir panel directamente
            self.admin_panel.open()
            return

        username = ft.TextField(
            label="Usuario", width=280, autofocus=True,
            border_radius=8, border_color=ft.Colors.BLUE_700,
            focused_border_color=ft.Colors.BLUE_400,
            prefix_icon=ft.Icons.PERSON_OUTLINE,
        )
        password = ft.TextField(
            label="Contraseña", password=True, can_reveal_password=True,
            width=280, border_radius=8, border_color=ft.Colors.BLUE_700,
            focused_border_color=ft.Colors.BLUE_400,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
        )
        error_text = ft.Text("", color=ft.Colors.RED_400, size=13)

        def intentar_login(ev):
            with SessionLocal() as db:
                ok = verificar_admin(db, username.value, password.value)
            if ok:
                self.page.session.set("admin_activo", True)
                self.page.session.set("user", username.value)
                self.page.close(self._login_dialog)
                # Reconstruir header para mostrar usuario y botón salir
                self.build()
                self.admin_panel.open()
            else:
                error_text.value = "Usuario o contraseña incorrectos"
                password.value = ""
                self.page.update()

        password.on_submit = intentar_login

        self._login_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED,
                            color=ft.Colors.BLUE_400),
                    ft.Text("Acceso Administrador", size=16,
                            weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    [username, password, error_text],
                    spacing=14, tight=True,
                ),
                width=300,
                padding=ft.padding.only(top=8),
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda _: self.page.close(self._login_dialog),
                    style=ft.ButtonStyle(color=ft.Colors.GREY_400),
                ),
                ft.ElevatedButton(
                    "Ingresar",
                    icon=ft.Icons.LOGIN,
                    on_click=intentar_login,
                    bgcolor=ft.Colors.BLUE_700,
                    color=ft.Colors.WHITE,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(self._login_dialog)

    def _cerrar_sesion_admin(self, e):
        self.page.session.set("admin_activo", False)
        self.page.session.set("user", None)
        self.build()  # Reconstruir header

    def _on_user_activity(self, e):
        self.page.session.set("last_activity_ts", datetime.now().timestamp())

    def _ensure_autolock_timer(self):
        # Auto-lock after 10 minutes of inactivity.
        timeout_s = 10 * 60

        if self._autolock_task_started:
            return

        self._autolock_task_started = True

        async def autolock_loop():
            while True:
                await asyncio.sleep(30)
                if not self.page.session.get("admin_activo"):
                    continue
                last = self.page.session.get("last_activity_ts")
                if not last:
                    continue
                if datetime.now().timestamp() - float(last) >= timeout_s:
                    self.page.session.set("admin_activo", False)
                    self.page.session.set("user", None)
                    self.build()

        self.page.run_task(autolock_loop)
