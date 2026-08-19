EL ATELIER BOUTIQUE V5 - LISTA PARA OPERAR
===========================================

NOVEDADES
---------
- Categorías visibles: Prendas, Zapatos, Hogar y Variedades.
- Mantiene compatibilidad con productos antiguos categorizados como Ropa o Calzado.
- Admin simplificado y con estilos incorporados en admin.html para evitar que vuelva a verse sin diseño.
- Vista previa de imágenes antes de publicar.
- Productos publicados visibles en lista.
- Edición rápida de nombre, precio, referencia, categoría, tallas, colores, descripción y foto principal.
- Eliminación de productos.
- Mantiene Supabase, Render, carrito y WhatsApp.
- No requiere IA ni costos adicionales de API.

PARA PUBLICAR V5 EN GITHUB
--------------------------
La opción más segura es subir TODO el contenido de esta carpeta V5 al repositorio,
reemplazando archivos existentes. NO subas el ZIP sin descomprimir.

Después:
1. Commit changes.
2. Render > Manual Deploy > Deploy latest commit si no inicia solo.
3. Espera estado Live.
4. Prueba /health. Debe indicar storage=supabase.
5. Entra a /admin/login y publica un producto real.
