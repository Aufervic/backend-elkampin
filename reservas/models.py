from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class Usuario(AbstractUser):
    ROL_CHOICES = (
        ('administrador', 'Administrador'),
        ('trabajador', 'Trabajador'),
        ('cliente', 'Cliente'),
    )

    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='cliente')
    dni = models.CharField(max_length=8, unique=True, null=True, blank=True)
    celular = models.CharField(max_length=15, null=True, blank=True)
    puede_reservar_sin_adelanto = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='usuarios',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='usuarios',
        blank=True
    )

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"


class Cancha(models.Model):
    DEPORTE_CHOICES = [
        ('futbol', 'Fútbol'),
        ('voley', 'Vóley'),
    ]
    CALIDAD_CHOICES = [
        ('basica', 'Básica'),
        ('premium', 'Premium'),
    ]

    nombre = models.CharField(max_length=100)
    deporte = models.CharField(max_length=10, choices=DEPORTE_CHOICES)
    calidad = models.CharField(max_length=10, choices=CALIDAD_CHOICES, default='basica')
    costo_dia = models.DecimalField(max_digits=6, decimal_places=2)
    costo_noche = models.DecimalField(max_digits=6, decimal_places=2)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - {self.get_deporte_display()} ({self.get_calidad_display()})"


class Reserva(models.Model):
    ESTADO_RESERVA_CHOICES = [
        ("PENDIENTE_APROBACION", "Pendiente de aprobación"),
        ("APROBADA", "Aprobada"),
        ("PAGO_COMPLETO", "Pago completo"),
        ("ANULADA", "Anulada"),
    ]

    cancha = models.ForeignKey(Cancha, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='reservas_cliente')
    atendido_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservas_atendidas',
        limit_choices_to={'rol': 'trabajador'}
    )

    fecha_reserva = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    monto_pagado = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    monto_total = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    pago_por_yape = models.BooleanField(default=False)
    yape_verificado = models.BooleanField(default=False)

    fecha_creacion = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=ESTADO_RESERVA_CHOICES, default="PENDIENTE_APROBACION")
    motivo_anulacion = models.TextField(null=True, blank=True)

    @property
    def calcular_monto_total(self):
        hora = self.hora_inicio.hour if self.hora_inicio else 0
        cancha = self.cancha
        base = cancha.costo_dia if hora < 18 else cancha.costo_noche
        return base * 2 if cancha.deporte == 'voley' else base

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"


    def __str__(self):
        return f"{self.cancha} - {self.cliente} ({self.fecha_reserva} {self.hora_inicio})"

    def realizada_por_cliente(self):
        return self.atendido_por is None


class Pago(models.Model):
    ESTADO_PAGO_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("CONFIRMADO", "Confirmado"),
        ("RECHAZADO", "Rechazado"),
        ("DEVUELTO", "Devuelto"),
    ]

    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=6, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, default="YAPE")
    comprobante_imagen = models.ImageField(upload_to="comprobantes/", null=True, blank=True)
    estado_pago = models.CharField(max_length=15, choices=ESTADO_PAGO_CHOICES, default="PENDIENTE")
    fecha_pago = models.DateTimeField(auto_now_add=True)
    verificado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'rol__in': ['trabajador', 'administrador']}
    )
    observacion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Pago #{self.id} - {self.reserva}"
