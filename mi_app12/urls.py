from django.urls import path
from . import views

urlpatterns = [
    # Autenticación (Login / Logout)
    path('login/', views.login_restaurante, name='login_restaurante'),
    path('logout/', views.logout_restaurante, name='logout_restaurante'),

    # Listado de categorías (Pantalla principal protegida)
    path('categorias/', views.listar_categorias, name='listar_categorias'),

    # Productos de una categoría concreta y procesamiento de cantidades
    path('categorias/<int:categoria_id>/productos/', views.productos_categoria, name='productos_categoria'),

    # Gestión del Carrito en sesión
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/eliminar/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('carrito/vaciar/', views.vaciar_carrito, name='vaciar_carrito'),

    # Confirmación del pedido
    path('pedido/confirmar/', views.confirmar_pedido, name='confirmar_pedido'),

    # ==========================================
    # RA6: Rutas para Mis Pedidos y Detalle
    # ==========================================
    path('mis-pedidos/', views.listar_mis_pedidos, name='listar_mis_pedidos'),
    path('mis-pedidos/<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),


    path('carrito/incrementar/<int:producto_id>/', views.incrementar_producto, name='incrementar_producto'),
    path('carrito/decrementar/<int:producto_id>/', views.decrementar_producto, name='decrementar_producto'),

    path('pedido/correo-enviado/<int:pedido_id>/', views.correo_emitido_view, name='correo_emitido'),


    path('admin-panel/', views.panel_administracion, name='panel_administracion'),
    path('almacen/', views.vista_almacen, name='vista_almacen'),
    path('almacen/exportar-csv/', views.exportar_pedidos_csv, name='exportar_pedidos_csv'),


]

