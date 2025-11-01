from django.contrib import admin
from .models import Usuario, Cancha, Reserva, Pago
from django.contrib.auth.admin import UserAdmin

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ('username', 'first_name', 'last_name', 'rol', 'dni', 'celular', 'is_active')
    list_filter = ('rol', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {'fields': ('rol', 'dni', 'celular')}),
    )

admin.site.register(Cancha)
admin.site.register(Reserva)
admin.site.register(Pago)