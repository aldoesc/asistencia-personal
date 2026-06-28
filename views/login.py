import flet as ft
from backend.database import SessionLocal
from backend.crud import verificar_admin


class LoginView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.username = ft.TextField(label="Usuario", width=300, autofocus=True)
        self.password = ft.TextField(
            label="Contraseña", password=True, can_reveal_password=True, width=300
        )
        self.error = ft.Text("", color=ft.Colors.RED_400)

    def build(self):
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.add(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(
                            ft.Icons.ADMIN_PANEL_SETTINGS,
                            size=80,
                            color=ft.Colors.BLUE_400,
                        ),
                        ft.Text(
                            "Control de Personal", size=28, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text(
                            "Acceso Administrador", size=16, color=ft.Colors.GREY_500
                        ),
                        ft.Divider(height=20, color="transparent"),
                        self.username,
                        self.password,
                        self.error,
                        ft.ElevatedButton(
                            "Ingresar", icon=ft.Icons.LOGIN, on_click=self.login
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=15,
                ),
                padding=30,
                border_radius=20,
                bgcolor=ft.Colors.GREY_800,
            )
        )

    def login(self, e):
        # FIX: usar SessionLocal() directamente en lugar de page.session.get("db"),
        # que devuelve una sesión ya instanciada que se cierra tras el primer "with".
        with SessionLocal() as db:
            ok = verificar_admin(db, self.username.value, self.password.value)
        if ok:
            self.page.session.set("admin_activo", True)
            self.page.session.set("user", self.username.value)
            self.page.go_to_dashboard()
        else:
            self.error.value = "Credenciales incorrectas"
            self.page.update()
