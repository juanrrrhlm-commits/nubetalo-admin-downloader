# Dependencias y fuentes

- Qt / PySide6 Essentials y Shiboken 6.12.0: Qt Project / The Qt Company; módulos utilizados Core, GUI, Widgets y Network; licencias comunitarias aplicables y avisos incluidos en `licenses/`. Distribución con DLL dinámicas, no enlace estático. Fuentes e instrucciones: https://code.qt.io/cgit/pyside/pyside-setup.git/ y https://code.qt.io/cgit/qt/qtbase.git/ (tag v6.12.0).
- libtorrent 2.1.1: Arvid Norberg y colaboradores; BSD y avisos adicionales del archivo LICENSE incluido. Fuentes: https://github.com/arvidn/libtorrent/tree/v2.1.1. El wheel incluye dependencias nativas; consultar sus avisos y build scripts de distribución.
- PycURL 7.49.0: licencia dual LGPL/MIT; se incluyen ambas. Fuente: https://github.com/pycurl/pycurl/tree/REL_7_49_0.
- libcurl y bibliotecas integradas en el wheel de PycURL: versión real de la compilación registrada en `docs/VERIFICACION.md`; fuente de curl https://curl.se/download.html. Conserva sus condiciones originales; el texto principal de curl se incluye en `licenses/`.
- CPython 3.13: Python Software Foundation; fuente https://www.python.org/downloads/source/. Licencia del runtime incluida.
- IBM Plex Sans: IBM, SIL Open Font License 1.1; se distribuyen Regular y SemiBold sin modificar. Fuente https://github.com/IBM/plex. Texto OFL incluido.
- Logo Nubetalo: recurso de marca proporcionado por el proyecto del usuario, obtenido del proyecto hermano Nubetalo Sound.
- PyInstaller se usa para empaquetar; su excepción permite distribuir aplicaciones empaquetadas con su licencia propia. https://pyinstaller.org/.

Las URLs son referencias de procedencia, no anuncios ni conexiones automáticas de la aplicación. Las fuentes originales de esta app se entregan en un ZIP junto con el instalador. Antes de una publicación externa se debe conservar esta información y los avisos de las bibliotecas efectivamente empaquetadas.
