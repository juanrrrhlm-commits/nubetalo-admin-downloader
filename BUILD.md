# Compilación en Windows

Requisitos: Windows x64, Python3.13 e Inno Setup6 de sus fuentes oficiales.

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe tools/build.py
```

Usa tools/downloader.spec: evita que alias de ICU de un proveedor oculten la ICU de
Windows. No sustituyas DLL del sistema. Qt se mantiene dinámico, sin protección que
impida sustituir sus bibliotecas por versiones modificadas compatibles.

tools/make_icon.py y tools/make_chime.py generan los recursos propios.
tools/collect_licenses.py conserva fuentes Qt/PySide y textos legales de origen.
tools/source_zip.py exporta solo el manifiesto de tools/public_files.py.

El ZIP de fuentes y los archivos de dependencias correspondientes deben conservarse
junto al instalador de cada publicación. Las fuentes originales de dependencias son
las de docs/DEPENDENCY_SOURCES.json; sus instrucciones de compilación están incluidas
en cada archivo de origen.

Las pruebas de instalación usan tools/qa_installer.py y
tools/verify_distribution.py --qa-installer con la ruta del instalador QA generado,
para conservar instalaciones existentes. No ejecutes el verificador normal si ya
usas una instalación de la app.
