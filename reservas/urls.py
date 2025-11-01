from django.urls import path
from .views import (
    UsuarioListCreateView, UsuarioDetailView, PerfilView,
    CanchaListCreateView, CanchaDetailView,
    ReservaListCreateView, ReservaDetailView, MisReservasView, ReservasConSaldoView, AbonarReservaView,
    PagoListCreateView, PagoDetailView,
    MyTokenObtainPairView
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    # ----------------- AUTENTICACIÓN JWT -----------------
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('login/', MyTokenObtainPairView.as_view(), name='custom_token_obtain_pair'),

    # ----------------- USUARIOS -----------------
    path('usuarios/', UsuarioListCreateView.as_view(), name='usuarios-list-create'),
    path('usuarios/<int:pk>/', UsuarioDetailView.as_view(), name='usuarios-detail'),
    path('perfil/', PerfilView.as_view(), name='perfil'),

    # ----------------- CANCHAS -----------------
    path('canchas/', CanchaListCreateView.as_view(), name='canchas-list-create'),
    path('canchas/<int:pk>/', CanchaDetailView.as_view(), name='canchas-detail'),

    # ----------------- RESERVAS -----------------
    path('reservas/mis-reservas/', MisReservasView.as_view(), name='reservas-mis'),
    path('reservas/con-saldo/', ReservasConSaldoView.as_view(), name='reservas-con-saldo'),
    path('reservas/<int:reserva_id>/abonar/', AbonarReservaView.as_view(), name='abonar-reserva'),
    path('reservas/<int:pk>/', ReservaDetailView.as_view(), name='reservas-detail'),
    path('reservas/', ReservaListCreateView.as_view(), name='reservas-list-create'),

    # ----------------- PAGOS -----------------
    path('pagos/', PagoListCreateView.as_view(), name='pagos-list-create'),
    path('pagos/<int:pk>/', PagoDetailView.as_view(), name='pagos-detail'),
]
