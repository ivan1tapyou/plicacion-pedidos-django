from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productos')
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    peso = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
    stock = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)  # Añadido para los subtotales del carrito

    def __str__(self):
        return self.nombre


class Restaurante(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(blank=True, null=True) # Recomendado por si quieres usar su propio email en servicios

    def __str__(self):
        return self.nombre


class UsuarioRestaurante(models.Model):
    correo = models.EmailField(unique=True)
    password = models.CharField(max_length=100)  # En producción se cifraría, para prácticas se valida plano
    
    # Restaurante asociado (opcional por si el rol es admin o stock y no gestionan un local concreto)
    restaurante = models.ForeignKey(Restaurante, on_delete=models.SET_NULL, null=True, blank=True)
    
    # --- CAMPO AÑADIDO: Control de Roles (RA / Administrativo) ---
    ROLES = (
        ('user', 'Usuario / Cliente'),
        ('admin', 'Administrador'),
        ('stock', 'Personal de Almacén'),
    )
    rol = models.CharField(max_length=10, choices=ROLES, default='user')
    # -------------------------------------------------------------

    def __str__(self):
        rest_nombre = self.restaurante.nombre if self.restaurante else "Sin Restaurante"
        return f"{self.correo} - Rol: [{self.rol}] ({rest_nombre})"


# ==========================================
# MODELOS PARA LA PERSISTENCIA DE PEDIDOS (RA6)
# ==========================================

class Pedido(models.Model):
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE, related_name='pedidos')
    fecha = models.DateTimeField(auto_now_add=True)
    
    # --- CAMPO AÑADIDO: Gestión de estados para el personal de stock ---
    ESTADOS_PEDIDO = [
        ('en_proceso', 'En proceso'),
        ('enviado', 'Enviado'),
        ('cancelado', 'Cancelado'),
    ]
    estado = models.CharField(max_length=20, choices=ESTADOS_PEDIDO, default='en_proceso')
    enviado = models.BooleanField(default=False) # Mantenido por compatibilidad previa

    def __str__(self):
        return f"Pedido #{self.id} - {self.restaurante.nombre}"

    @property
    def total_pedido(self):
        """Propiedad útil para calcular el importe total sumando las líneas."""
        return sum(linea.subtotal for linea in self.lineas.all())


class LineaPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    unidades = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        """Calcula el subtotal de esta línea específica."""
        return self.producto.precio * self.unidades

    def __str__(self):
        return f"{self.unidades} unidades de {self.producto.nombre} (Pedido #{self.pedido.id})"