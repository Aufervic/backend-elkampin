from rest_framework import serializers
from .models import Usuario, Cancha, Reserva, Pago
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# ----------------- TOKEN CON DATOS -----------------
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Agregar claims personalizados
        token['rol'] = user.rol  # tu campo rol en el modelo User
        token['username'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Agregar información extra al response
        data['usuario'] = {
            'username': self.user.username,
            'rol': self.user.rol
        }
        return data

# ----------------- USUARIOS -----------------
class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'first_name', 'last_name', 'rol', 'dni', 'celular', 'puede_reservar_sin_adelanto']


# ----------------- CANCHAS -----------------
class CanchaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cancha
        fields = ['id', 'nombre', 'deporte', 'calidad', 'costo_dia', 'costo_noche', 'disponible']


class CanchaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cancha
        fields = ['id', 'nombre', 'deporte', 'costo_dia', 'costo_noche']


# ----------------- RESERVAS -----------------
class ReservaSerializer(serializers.ModelSerializer):
    cliente = UsuarioSerializer(read_only=True)
    atendido_por = UsuarioSerializer(read_only=True)
    cliente_username = serializers.CharField(write_only=True, required=False)
    cancha_detalle = CanchaSerializer(source='cancha', read_only=True)
    monto_total = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = [
            'id', 'cancha', 'cancha_detalle', 'cliente', 'atendido_por',
            'fecha_reserva', 'hora_inicio', 'hora_fin',
            'monto_pagado', 'monto_total', 'pago_por_yape', 'yape_verificado',
            'fecha_creacion', 'estado', 'motivo_anulacion',
            'cliente_username'
        ]
        read_only_fields = ['motivo_anulacion', 'fecha_creacion']

    def get_monto_total(self, obj):
        return obj.calcular_monto_total
    

    def validate(self, data):
        user = self.context['request'].user

        cancha = data.get('cancha') or getattr(self.instance, 'cancha', None)
        fecha = data.get('fecha_reserva') or getattr(self.instance, 'fecha_reserva', None)
        hora_inicio = data.get('hora_inicio') or getattr(self.instance, 'hora_inicio', None)
        hora_fin = data.get('hora_fin') or getattr(self.instance, 'hora_fin', None)
        monto_pagado = data.get('monto_pagado', getattr(self.instance, 'monto_pagado', 0))

        # Validar adelanto según política del cliente
        if user.rol == 'cliente' and not getattr(user, 'puede_reservar_sin_adelanto', False):
            if monto_pagado < 10:
                raise serializers.ValidationError({
                    "monto_pagado": "Se requiere un adelanto mínimo de 10 soles"
                })

        # Evitar solapamiento de horarios activos (aprobados o pagados)
        reservas_existentes = Reserva.objects.filter(
            cancha=cancha,
            fecha_reserva=fecha,
            estado__in=['PENDIENTE_APROBACION', 'APROBADA', 'PAGO_COMPLETO']
        ).exclude(
            hora_fin__lte=hora_inicio  # termina antes de que empiece la nueva
        ).exclude(
            hora_inicio__gte=hora_fin  # empieza después de que termina la nueva
        )

        # Evita comparar consigo misma cuando se actualiza
        if self.instance:
            reservas_existentes = reservas_existentes.exclude(id=self.instance.id)

        if reservas_existentes.exists():
            raise serializers.ValidationError("Ya existe una reserva activa que se solapa con este horario.")

        return data

    def create(self, validated_data):
        request = self.context['request']
        usuario = request.user
        cliente_username = validated_data.pop('cliente_username', None)

        # Determinar quién es el cliente
        if usuario.rol == 'cliente':
            validated_data['cliente'] = usuario
            cliente = usuario
        else:
            # Trabajador o administrador: crea reserva para otro cliente
            if not cliente_username:
                raise serializers.ValidationError({
                    "cliente_username": "Debe especificarse un cliente."
                })
            try:
                cliente = Usuario.objects.get(username=cliente_username)
                validated_data['cliente'] = cliente
            except Usuario.DoesNotExist:
                raise serializers.ValidationError({
                    "cliente_username": "Cliente no encontrado."
                })
            # Asignar el usuario que atiende
            validated_data['atendido_por'] = usuario

        # ---- CÁLCULO AUTOMÁTICO DEL PRECIO ----
        cancha = validated_data['cancha']
        hora_inicio = validated_data['hora_inicio']
        hora_int = hora_inicio.hour
        base = cancha.costo_dia if hora_int < 18 else cancha.costo_noche
        monto_total = base

        # ---- VALIDACIÓN DE ADELANTO ----
        monto_pagado = validated_data.get('monto_pagado', 0)
        if cliente.rol == 'cliente' and not cliente.puede_reservar_sin_adelanto:
            if monto_pagado < 10:
                raise serializers.ValidationError({
                    "monto_pagado": "Se requiere un adelanto mínimo de 10 soles."
                })
        else:
            # Si el cliente puede reservar sin adelanto, la reserva se aprueba directamente
            validated_data['estado'] = 'PENDIENTE_APROBACION'

        # ---- Crear la reserva ----
        reserva = super().create(validated_data)

        # ---- Crear pago automático si corresponde ----
        if reserva.monto_pagado and reserva.monto_pagado > 0:
            from .models import Pago  # evitar import circular
            Pago.objects.create(
                reserva=reserva,
                monto=monto_pagado,
                metodo_pago='EFECTIVO',  # o 'YAPE', si quieres mantener coherencia
                observacion='Pago inicial al crear la reserva',
                estado_pago='PENDIENTE',
                verificado_por=None  # se llenará luego por un trabajador
            )

        return reserva
    

    def update(self, instance, validated_data):
        """
        Permite edición limitada para clientes y completa para trabajadores/admins.
        """
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        # --- Si el usuario es cliente ---
        if user and user.rol == 'cliente':
            nuevo_estado = validated_data.get('estado', None)

            # Permitir solo anulación, no otros cambios de estado
            if nuevo_estado == 'ANULADA':
                instance.estado = 'ANULADA'
            else:
                validated_data.pop('estado', None)  # bloquear otros estados
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)

                if instance.estado != 'ANULADA':
                    if instance.monto_pagado >= instance.monto_total:
                        instance.estado = 'PAGO_COMPLETO'
                    elif instance.monto_pagado > 0:
                        instance.estado = 'APROBADA'

        # --- Si es trabajador o administrador ---
        else:
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            '''
            # Si se anula → monto_pagado = 0
            if instance.estado == 'ANULADA':
                instance.monto_pagado = 0

            # Si el estado se modifica a APROBADA y no hay pago completo
            if instance.estado == 'APROBADA' and instance.monto_pagado == 0:
                instance.monto_pagado = 0  # mantener coherencia
            '''

        instance.save()
        return instance
    
    

class AbonarReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = ['id', 'reserva', 'monto', 'metodo_pago', 'estado_pago', 'fecha_pago']   


# ----------------- PAGOS -----------------
class PagoSerializer(serializers.ModelSerializer):
    reserva = serializers.PrimaryKeyRelatedField(queryset=Reserva.objects.all())
    verificado_por = UsuarioSerializer(read_only=True)
    cliente_username = serializers.CharField(source='reserva.cliente.username', read_only=True)
    reserva_cancha_nombre = serializers.CharField(source='reserva.cancha.nombre', read_only=True)

    class Meta:
        model = Pago
        fields = [
            'id', 'reserva', 'monto', 'metodo_pago',
            'comprobante_imagen', 'estado_pago', 'fecha_pago',
            'verificado_por', 'observacion',
            'cliente_username', 'reserva_cancha_nombre'
        ]
        read_only_fields = ['fecha_pago', 'verificado_por']

    def validate_monto(self, value):
        # Validación: no pagar más que el total pendiente de la reserva
        reserva = self.initial_data.get('reserva')
        try:
            reserva_obj = Reserva.objects.get(id=reserva)
        except Reserva.DoesNotExist:
            raise serializers.ValidationError("Reserva no existe.")

        if value + reserva_obj.monto_pagado > self.context.get('total_reserva', 0):
            raise serializers.ValidationError("El monto pagado excede el total de la reserva.")
        return value

    # Método para verificar o registrar pago
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Si el pago es confirmado, actualizamos reserva
        if instance.estado_pago == 'CONFIRMADO':
            reserva = instance.reserva
            reserva.monto_pagado += instance.monto

            if reserva.monto_pagado >= reserva.monto_total:
                reserva.estado = 'PAGO_COMPLETO'
            reserva.save()

        instance.save()
        return instance
