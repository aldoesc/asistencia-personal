import flet as ft


class CameraWidget(ft.UserControl):
    def __init__(self, on_qr_detected):
        super().__init__()
        self.on_qr_detected = on_qr_detected

    def build(self):
        return ft.Container(
            content=ft.Icon(ft.Icons.VIDEO_CAMERA_BACK, size=100),
            width=300,
            height=200,
            bgcolor=ft.Colors.GREY_800,
            border_radius=10,
            alignment=ft.alignment.center,
        )
