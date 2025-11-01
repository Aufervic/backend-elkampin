from rest_framework.permissions import BasePermission

class EsAdministrador(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'administrador'

class EsTrabajador(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in ['trabajador', 'administrador']

class EsCliente(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == 'cliente'

class PuedeEditarReserva(BasePermission):
    """Permite que solo Admin o Trabajador editen reservas de clientes"""
    def has_object_permission(self, request, view, obj):
        if request.user.rol == 'administrador':
            return True
        if request.user.rol == 'trabajador':
            return True
        # Cliente solo puede ver/editar sus propias reservas
        return obj.cliente == request.user