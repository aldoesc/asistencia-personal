import flet as ft
from backend.database import init_db, admin_existe, SessionLocal
from backend.crud import crear_admin
from views.dashboard import DashboardView


def main(page: ft.Page):
    page.title = "Control de Personal"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 1300
    page.window_height = 800
    page.window_min_width = 1000
    page.window_min_height = 600

    # Sin login de inicio — acceso directo al dashboard.
    # El login solo existe para ingresar al panel de administración.
    page.session.set("admin_activo", False)
    page.session.set("user", None)

    def _ensure_admin():
        with SessionLocal() as db:
            if admin_existe(db):
                return

        username = ft.TextField(
            label="Usuario admin",
            width=320,
            autofocus=True,
            border_radius=8,
        )
        password = ft.TextField(
            label="Contraseña (mínimo 8)",
            password=True,
            can_reveal_password=True,
            width=320,
            border_radius=8,
        )
        password2 = ft.TextField(
            label="Repetir contraseña",
            password=True,
            can_reveal_password=True,
            width=320,
            border_radius=8,
        )
        error = ft.Text("", color=ft.Colors.RED_400, size=13)

        def crear(ev):
            if (password.value or "") != (password2.value or ""):
                error.value = "Las contraseñas no coinciden"
                page.update()
                return
            try:
                with SessionLocal() as db:
                    crear_admin(db, username.value, password.value)
                page.close(dlg)
                page.update()
                go_to_dashboard()
            except Exception as ex:
                error.value = str(ex)
                page.update()

        password2.on_submit = crear

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Configuración inicial", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "No existe un administrador. Crea el admin para habilitar el panel de administración.",
                            size=12,
                            color=ft.Colors.GREY_400,
                        ),
                        username,
                        password,
                        password2,
                        error,
                    ],
                    tight=True,
                    spacing=12,
                ),
                width=380,
                padding=ft.padding.only(top=8),
            ),
            actions=[
                ft.ElevatedButton(
                    "Crear admin",
                    on_click=crear,
                    bgcolor=ft.Colors.BLUE_700,
                    color=ft.Colors.WHITE,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dlg)

    def go_to_dashboard():
        page.clean()
        DashboardView(page).build()

    page.go_to_dashboard = go_to_dashboard
    _ensure_admin()
    # Si ya existe admin, _ensure_admin() no abre modal y seguimos.
    if not page.overlay:  # overlay vacío → no hay modal abierto
        go_to_dashboard()


if __name__ == "__main__":
    init_db()
    ft.app(target=main, view=ft.AppView.FLET_APP)
