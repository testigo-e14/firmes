#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py - Validador completo para el directorio firmes.

Verifica:
- Esquema CSV
- fuente_ids resolubles
- Cero "Por determinar" publicado
- url_archivo obligatoria para Prensa (Wayback)
- Duplicados de contenido
- Idempotencia del generador
- Archivos de gobernanza (--gobernanza)
"""
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

# Importar utilidades locales
sys.path.insert(0, str(Path(__file__).parent))
from lib_firmes import (
    cargar_negocios, cargar_fuentes, es_publicable,
    clave_orden_contenido, NEGOCIOS_COLUMNS, FUENTES_COLUMNS
)


class ValidationError(Exception):
    """Error de validación."""
    pass


def validar_esquema_csv(proyecto: Path) -> list[str]:
    """Valida que los CSV tengan el esquema correcto."""
    errores = []

    # Determinar rutas
    data_dir = proyecto / "data"
    if (data_dir / "fixtures" / "negocios.csv").exists():
        negocios_path = data_dir / "fixtures" / "negocios.csv"
        fuentes_path = data_dir / "fixtures" / "fuentes.csv"
    else:
        negocios_path = data_dir / "negocios.csv"
        fuentes_path = data_dir / "fuentes.csv"

    try:
        cargar_negocios(negocios_path)
    except ValueError as e:
        errores.append(f"negocios.csv: {e}")

    try:
        cargar_fuentes(fuentes_path)
    except ValueError as e:
        errores.append(f"fuentes.csv: {e}")

    return errores


def validar_fuentes_resolubles(negocios: list[dict], fuentes: dict) -> list[str]:
    """Valida que todos los fuente_ids referenciados existan."""
    errores = []

    for i, fila in enumerate(negocios, start=2):
        fuente_ids_raw = fila.get('fuente_ids', '').strip()
        if not fuente_ids_raw:
            continue

        for fid in fuente_ids_raw.split(';'):
            fid = fid.strip()
            if fid and fid not in fuentes:
                errores.append(f"Fila {i}: fuente_id '{fid}' no existe en fuentes.csv")

    return errores


def validar_cero_por_determinar_publicado(negocios: list[dict], fuentes: dict) -> list[str]:
    """Valida que ningún registro "Por determinar" esté en publicables."""
    errores = []

    for i, fila in enumerate(negocios, start=2):
        if fila['evidencia'] == 'Por determinar':
            if es_publicable(fila, fuentes):
                errores.append(f"Fila {i}: 'Por determinar' no debe ser publicable")

    return errores


def validar_url_archivo_prensa(negocios: list[dict], fuentes: dict) -> list[str]:
    """
    Valida que toda evidencia tipo Prensa tenga url_archivo apuntando a Wayback.
    """
    errores = []
    wayback_pattern = re.compile(r'^https?://web\.archive\.org/')

    for i, fila in enumerate(negocios, start=2):
        if fila['evidencia'] != 'Prensa':
            continue

        # Obtener fuentes de esta fila
        fuente_ids_raw = fila.get('fuente_ids', '').strip()
        if not fuente_ids_raw:
            continue

        for fid in fuente_ids_raw.split(';'):
            fid = fid.strip()
            if fid not in fuentes:
                continue

            fuente = fuentes[fid]
            url_archivo = fuente.get('url_archivo', '').strip()

            if not url_archivo:
                errores.append(
                    f"Fila {i}: evidencia=Prensa pero fuente '{fid}' sin url_archivo"
                )
            elif not wayback_pattern.match(url_archivo):
                errores.append(
                    f"Fila {i}: url_archivo de fuente '{fid}' no es Wayback: {url_archivo}"
                )

    return errores


def validar_duplicados_contenido(negocios: list[dict]) -> list[str]:
    """Valida que no haya filas byte-idénticas (duplicados de contenido)."""
    errores = []
    vistas = {}

    for i, fila in enumerate(negocios, start=2):
        clave = clave_orden_contenido(fila)

        if clave in vistas:
            errores.append(
                f"Fila {i}: duplicado de contenido con fila {vistas[clave]}"
            )
        else:
            vistas[clave] = i

    return errores


def validar_idempotencia(proyecto: Path) -> list[str]:
    """Valida que dos ejecuciones del generador produzcan el mismo output."""
    errores = []

    # Primera ejecución
    subprocess.run(
        [sys.executable, str(proyecto / "scripts" / "generate.py")],
        capture_output=True,
        cwd=proyecto
    )

    # Capturar hashes
    readme = proyecto / "README.md"
    hash1 = hashlib.sha256(readme.read_bytes()).hexdigest() if readme.exists() else ""

    regionales = {}
    regionales_dir = proyecto / "regionales"
    if regionales_dir.exists():
        for f in regionales_dir.glob("*.md"):
            regionales[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()

    # Segunda ejecución
    subprocess.run(
        [sys.executable, str(proyecto / "scripts" / "generate.py")],
        capture_output=True,
        cwd=proyecto
    )

    # Comparar
    hash2 = hashlib.sha256(readme.read_bytes()).hexdigest() if readme.exists() else ""

    if hash1 != hash2:
        errores.append("Idempotencia: README.md difiere entre ejecuciones")

    if regionales_dir.exists():
        for f in regionales_dir.glob("*.md"):
            hash_nuevo = hashlib.sha256(f.read_bytes()).hexdigest()
            if f.name in regionales and regionales[f.name] != hash_nuevo:
                errores.append(f"Idempotencia: regionales/{f.name} difiere entre ejecuciones")

    return errores


def validar_html_sin_thead(proyecto: Path) -> list[str]:
    """Valida que las tablas generadas no tengan <thead>."""
    errores = []

    archivos = [proyecto / "README.md"]
    regionales_dir = proyecto / "regionales"
    if regionales_dir.exists():
        archivos.extend(regionales_dir.glob("*.md"))

    for archivo in archivos:
        if not archivo.exists():
            continue
        contenido = archivo.read_text(encoding='utf-8')
        if '<thead>' in contenido:
            errores.append(f"{archivo.name}: contiene <thead> (debe ser headerless)")

    return errores


def validar_gobernanza(proyecto: Path) -> list[str]:
    """Valida archivos de gobernanza y comunidad."""
    errores = []

    # Archivos requeridos
    archivos_requeridos = [
        'LICENSE',
        'NOTICE',
        'CONTRIBUTING.md',
        'SECURITY.md',
        'CODE_OF_CONDUCT.md',
    ]

    for archivo in archivos_requeridos:
        if not (proyecto / archivo).exists():
            errores.append(f"Gobernanza: falta {archivo}")

    # Verificar SLA en SECURITY.md
    security = proyecto / "SECURITY.md"
    if security.exists():
        contenido = security.read_text(encoding='utf-8')
        # Buscar SLA con tiempos concretos
        tiene_sla = (
            re.search(r'\d+\s*h', contenido, re.IGNORECASE) or
            re.search(r'\d+\s*día', contenido, re.IGNORECASE) or
            re.search(r'\d+\s*hours?', contenido, re.IGNORECASE) or
            re.search(r'\d+\s*days?', contenido, re.IGNORECASE)
        )
        if not tiene_sla:
            errores.append("Gobernanza: SECURITY.md no tiene SLA con tiempos concretos")

    # CODEOWNERS
    codeowners = proyecto / ".github" / "CODEOWNERS"
    if not codeowners.exists():
        errores.append("Gobernanza: falta .github/CODEOWNERS")
    else:
        contenido = codeowners.read_text(encoding='utf-8')
        if 'data/' not in contenido:
            errores.append("Gobernanza: CODEOWNERS no cubre data/")

    # settings.yml
    settings = proyecto / ".github" / "settings.yml"
    if not settings.exists():
        errores.append("Gobernanza: falta .github/settings.yml")

    # Issue templates
    templates_dir = proyecto / ".github" / "ISSUE_TEMPLATE"
    if not templates_dir.exists():
        errores.append("Gobernanza: falta .github/ISSUE_TEMPLATE/")

    return errores


def main():
    parser = argparse.ArgumentParser(description="Validador del directorio firmes")
    parser.add_argument(
        '--gobernanza',
        action='store_true',
        help='También validar archivos de gobernanza y comunidad'
    )
    parser.add_argument(
        '--proyecto',
        type=Path,
        default=Path(__file__).parent.parent,
        help='Ruta al proyecto (default: directorio padre de scripts/)'
    )
    args = parser.parse_args()

    proyecto = args.proyecto.resolve()
    print(f"Validando proyecto: {proyecto}")
    print()

    todos_errores = []

    # Determinar rutas de datos
    data_dir = proyecto / "data"
    if (data_dir / "fixtures" / "negocios.csv").exists():
        negocios_path = data_dir / "fixtures" / "negocios.csv"
        fuentes_path = data_dir / "fixtures" / "fuentes.csv"
        print("Usando datos de fixtures/")
    else:
        negocios_path = data_dir / "negocios.csv"
        fuentes_path = data_dir / "fuentes.csv"
        print("Usando datos de data/")
    print()

    # 1. Esquema CSV
    print("1. Validando esquema CSV...")
    errores = validar_esquema_csv(proyecto)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # Cargar datos para validaciones siguientes
    try:
        negocios = cargar_negocios(negocios_path)
        fuentes = cargar_fuentes(fuentes_path)
    except ValueError as e:
        print(f"\nERROR FATAL: No se pueden cargar datos: {e}")
        sys.exit(1)

    # 2. Fuentes resolubles
    print("2. Validando fuentes resolubles...")
    errores = validar_fuentes_resolubles(negocios, fuentes)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # 3. Cero Por determinar publicado
    print("3. Validando cero 'Por determinar' publicado...")
    errores = validar_cero_por_determinar_publicado(negocios, fuentes)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # 4. url_archivo para Prensa
    print("4. Validando url_archivo para Prensa...")
    errores = validar_url_archivo_prensa(negocios, fuentes)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # 5. Duplicados de contenido
    print("5. Validando duplicados de contenido...")
    errores = validar_duplicados_contenido(negocios)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # 6. HTML sin thead
    print("6. Validando HTML sin <thead>...")
    errores = validar_html_sin_thead(proyecto)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # 7. Idempotencia
    print("7. Validando idempotencia...")
    errores = validar_idempotencia(proyecto)
    if errores:
        todos_errores.extend(errores)
        print(f"   FAIL: {len(errores)} errores")
    else:
        print("   PASS")

    # 8. Gobernanza (opcional)
    if args.gobernanza:
        print("8. Validando gobernanza...")
        errores = validar_gobernanza(proyecto)
        if errores:
            todos_errores.extend(errores)
            print(f"   FAIL: {len(errores)} errores")
        else:
            print("   PASS")

    # Resumen
    print()
    if todos_errores:
        print(f"=== VALIDACIÓN FALLIDA: {len(todos_errores)} errores ===")
        for err in todos_errores[:20]:  # Mostrar primeros 20
            print(f"  - {err}")
        if len(todos_errores) > 20:
            print(f"  ... y {len(todos_errores) - 20} más")
        sys.exit(1)
    else:
        print("=== VALIDACIÓN EXITOSA ===")
        sys.exit(0)


if __name__ == "__main__":
    main()
