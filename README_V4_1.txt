EL ATELIER BOUTIQUE V4.1 - ALMACENAMIENTO PERMANENTE

El diseño V4 se conserva. Internamente cambia así:
- GitHub: código.
- Render: servidor web.
- Supabase PostgreSQL: productos, precios, tallas, colores y estados.
- Supabase Storage: fotografías.

La app conserva SQLite como respaldo local. Si Render tiene SUPABASE_URL y
SUPABASE_SERVICE_ROLE_KEY, usa Supabase automáticamente.

CONFIGURACIÓN
1. Crea un proyecto en Supabase.
2. Abre SQL Editor y ejecuta SUPABASE_SETUP.sql.
3. En Supabase copia Project URL y Service Role Key.
4. En Render > Environment agrega las variables de RENDER_ENV_TEMPLATE.txt.
5. Save, rebuild and deploy.
6. Comprueba /health. Debe mostrar "storage": "supabase".
7. Entra a /admin/login y pulsa "Migrar catálogo actual a almacenamiento permanente".

SEGURIDAD
La SUPABASE_SERVICE_ROLE_KEY debe existir SOLO en Render Environment. Nunca la subas a GitHub.
Cambia también ATELIER_ADMIN_PASSWORD y ATELIER_SECRET_KEY antes de compartir la tienda.
