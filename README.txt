MANGA READER 1.1.0-3
====================

Lector y administrador de manga local para Linux.

Manga Reader está pensado para organizar y leer mangas que ya tienes
descargados en tu computadora. La biblioteca y los datos del programa
se mantienen de forma local.


CARACTERÍSTICAS
===============

BIBLIOTECA

- Biblioteca visual con portadas.
- Buscador de mangas.
- Organización por:
    - Continuar
    - Favoritos
    - Leyendo
    - Finalizados
- Indicador de capítulos nuevos.
- Estados del manga:
    - Emisión
    - Pausado
    - Finalizado
    - Cancelado
- Sinopsis.
- Géneros.
- Orden alfabético de la biblioteca.


CAPÍTULOS

- Lista de capítulos.
- Orden automático de capítulos por número.
- Compatible con capítulos decimales.
- Orden:
    - Primero → Último
    - Último → Primero
- Marcar capítulos como leídos.
- Desmarcar capítulos como leídos.
- Marcar todos los capítulos como leídos.
- Marcar todos los capítulos como no leídos.
- Detección de capítulos nuevos.
- Eliminar capítulos seleccionados.


LECTOR

- Lector integrado.
- Navegación entre páginas.
- Capítulo anterior.
- Capítulo siguiente.
- Los capítulos se marcan automáticamente como leídos al abrirlos.


IMPORTACIÓN

- Agregar capítulos individualmente.
- Importar varios capítulos.
- Seleccionar carpetas de capítulos.
- Importar una carpeta que contiene varios capítulos.
- Vincular una carpeta existente.
- Buscar nuevos capítulos dentro de una carpeta vinculada.


FORMATOS SOPORTADOS

- Carpetas con imágenes.
- JPG / JPEG
- PNG
- PDF
- CBZ
- ZIP


ADMINISTRACIÓN DE MANGAS

- Crear manga.
- Editar manga.
- Cambiar nombre.
- Cambiar portada.
- Editar sinopsis.
- Editar géneros.
- Cambiar estado.
- Agregar capítulos.
- Eliminar capítulos.
- Eliminar manga.
- Buscar mangas desde Configuración.


VISTAS DE CONFIGURACIÓN

- Vista de lista.
- Vista de cuadrícula.
- Portadas en la vista de cuadrícula.
- El programa recuerda la vista seleccionada.


RESPALDOS

- Exportar respaldo de la biblioteca.
- Importar respaldo.


COMPATIBILIDAD
==============

Sistema operativo:

- Linux

Distribuciones principales:

- Arch Linux
- Manjaro Linux
- CachyOS
- EndeavourOS
- Otras distribuciones basadas en Arch Linux.

El paquete incluido está preparado principalmente para distribuciones
basadas en Arch Linux mediante pacman/PKGBUILD.

El código fuente está escrito en Python y PySide6, por lo que puede
funcionar en otras distribuciones Linux si se instalan manualmente
las dependencias necesarias.

IMPORTANTE:

El instalador y el paquete de esta versión están orientados a
Arch Linux y derivados. En otras distribuciones la instalación
automática no está garantizada.


REQUISITOS
==========

- Python 3
- PySide6 / Qt6
- Linux
- Entorno gráfico compatible con Qt6


INSTALACIÓN RÁPIDA
==================

1. Descarga o clona el repositorio.

2. Abre una terminal dentro de la carpeta de Manga Reader.

3. Da permisos al instalador si fuera necesario:

   chmod +x instalar.sh

4. Ejecuta:

   ./instalar.sh

5. Una vez instalado, abre:

   Manga Reader

   desde el menú de aplicaciones.


INSTALACIÓN EN ARCH / MANJARO / CACHYOS
=======================================

También puedes construir el paquete utilizando PKGBUILD:

   makepkg -si

Esto generará e instalará el paquete utilizando pacman.


DESINSTALACIÓN
==============

Puedes utilizar:

   ./desinstalar.sh

o eliminar el paquete mediante pacman si fue instalado como paquete:

   sudo pacman -Rns manga-reader-local


DATOS DE LA BIBLIOTECA
======================

Los datos personales de Manga Reader se almacenan independientemente
del programa en:

   ~/.local/share/manga-reader/

Esto permite actualizar o reinstalar Manga Reader sin tener que
eliminar automáticamente la biblioteca.


ACTUALIZACIONES
===============

Antes de actualizar se recomienda mantener un respaldo de la biblioteca.

La eliminación del programa no debería eliminar los datos almacenados
en:

   ~/.local/share/manga-reader/


NOTAS
=====

Manga Reader es un lector local.

No descarga mangas automáticamente y no incluye contenido.
El usuario administra sus propios archivos y carpetas de manga.
