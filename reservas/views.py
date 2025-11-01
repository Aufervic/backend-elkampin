from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db.models import F
from .models import Cancha, Reserva, Pago, Usuario
from .serializers import CanchaSerializer, ReservaSerializer, PagoSerializer, UsuarioSerializer, MyTokenObtainPairSerializer
from .permissions import EsAdministrador, EsTrabajador, EsCliente, PuedeEditarReserva
from decimal import Decimal
from rest_framework_simplejwt.views import TokenObtainPairView

# ----------------- token -----------------
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


Usuario = get_user_model()
# ----------------- USUARIOS -----------------
class UsuarioListCreateView(generics.ListCreateAPIView):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

    def get_permissions(self):
        return [EsAdministrador()]
    
    def perform_create(self, serializer):
        # Por defecto, todo registro desde el endpoint es cliente
        serializer.save(rol='cliente')

class UsuarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [EsAdministrador]

class PerfilView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

# ----------------- CANCHAS -----------------
class CanchaListCreateView(generics.ListCreateAPIView):
    queryset = Cancha.objects.all()
    serializer_class = CanchaSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [EsAdministrador()]
        return [permissions.AllowAny()]

class CanchaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Cancha.objects.all()
    serializer_class = CanchaSerializer
    permission_classes = [EsAdministrador]

# ----------------- RESERVAS -----------------
class ReservaListCreateView(generics.ListCreateAPIView):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer

    def get_queryset(self):
        user = self.request.user
        if user.rol == 'cliente':
            return Reserva.objects.filter(cliente=user)
        return Reserva.objects.all()
    
    def perform_create(self, serializer):
        usuario = self.request.user

        if usuario.rol == 'cliente':
            # Cliente logueado se asigna automáticamente
            serializer.save(cliente=usuario)

            # Validar adelanto mínimo
            monto_pagado = serializer.validated_data.get('monto_pagado', 0)
            if not usuario.puede_reservar_sin_adelanto and monto_pagado < 10:
                raise serializers.ValidationError({
                    "monto_pagado": "Se requiere un adelanto mínimo de 10 soles"
                })
        else:
            # Trabajador o administrador
            cliente_id = self.request.data.get('cliente')
            if not cliente_id:
                raise serializers.ValidationError({
                    "cliente": "Este campo es obligatorio para trabajadores/administradores."
                })

            try:
                cliente_obj = Usuario.objects.get(id=cliente_id, rol='cliente')
            except Usuario.DoesNotExist:
                raise serializers.ValidationError({
                    "cliente": "El usuario indicado no existe o no es cliente."
                })

            serializer.save(cliente=cliente_obj)

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

class ReservaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer
    permission_classes = [PuedeEditarReserva]

# ----------------- MIS RESERVAS (solo cliente) -----------------
class MisReservasView(generics.ListAPIView):
    serializer_class = ReservaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Si es cliente, solo sus reservas
        if user.rol == 'cliente':
            return Reserva.objects.filter(cliente=user).order_by('-fecha_reserva')

        # Si es trabajador o admin, puede ver todas (opcional)
        return Reserva.objects.all().order_by('-fecha_reserva')


class ReservasConSaldoView(generics.ListAPIView):
    serializer_class = ReservaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Filtrar reservas aprobadas con saldo pendiente
        queryset = Reserva.objects.filter(
            estado='APROBADA',
            monto_pagado__lt=F('monto_total')  # monto_pagado < monto_total
        )

        # Si es cliente, solo sus reservas
        if user.rol == 'cliente':
            queryset = queryset.filter(cliente=user)

        return queryset



class AbonarReservaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, reserva_id):
        try:
            reserva = Reserva.objects.get(id=reserva_id)
        except Reserva.DoesNotExist:
            return Response({"error": "Reserva no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        # Permitir: cliente dueño, trabajador o admin
        if reserva.cliente != request.user and request.user.rol not in ["trabajador", "administrador"]:
            return Response(
                {"error": "No tienes permisos para abonar esta reserva."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        monto = request.data.get("monto")
        metodo_pago = request.data.get("metodo_pago", "YAPE")
        if monto is None:
            return Response({"error": "Se requiere el monto a abonar."}, status=status.HTTP_400_BAD_REQUEST)

        try:
           monto = Decimal(str(monto))
        except ValueError:
            return Response({"error": "Monto inválido."}, status=status.HTTP_400_BAD_REQUEST)

        if monto <= 0:
            return Response({"error": "El monto debe ser mayor que 0."}, status=status.HTTP_400_BAD_REQUEST)

        # Crear registro de pago
        pago = Pago.objects.create(
            reserva=reserva,
            monto=monto,
            metodo_pago=metodo_pago,
            estado_pago="PENDIENTE",
        )

        # Actualizar monto pagado de la reserva
        reserva.monto_pagado += monto

        # Si ya alcanza el total → marcar como PAGO_COMPLETO
        if reserva.monto_pagado >= reserva.calcular_monto_total:
            reserva.estado = "PAGO_COMPLETO"
        else:
            reserva.estado = "APROBADA"

        reserva.save()

        return Response({
            "reserva_id": reserva.id,
            "monto_pagado": reserva.monto_pagado,
            "estado": reserva.estado,
            "pago_id": pago.id
        })
    

# ----------------- PAGOS -----------------
class PagoListCreateView(generics.ListCreateAPIView):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Cliente ve solo sus pagos
        if user.rol == 'cliente':
            return Pago.objects.filter(reserva__cliente=user)
        # Trabajador o administrador ve todos los pagos
        return Pago.objects.all()

class PagoDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    permission_classes = [EsTrabajador]
