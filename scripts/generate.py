#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py - Generador del directorio firmes.

Genera README.md y regionales/*.md desde los CSV de datos.
Taxonomía 100% data-driven (sin semillas hardcodeadas).
Orden determinista con colación UCA.
"""
import sys
from collections import defaultdict
from pathlib import Path

# Intentar importar pyuca para colación UCA portable
try:
    from pyuca import Collator
    UCA_COLLATOR = Collator()
    def uca_sort_key(texto: str) -> tuple:
        """Clave de ordenamiento UCA para texto."""
        return UCA_COLLATOR.sort_key(texto)
except ImportError:
    print("ADVERTENCIA: pyuca no instalado. Usando ordenamiento básico.", file=sys.stderr)
    def uca_sort_key(texto: str) -> str:
        """Fallback: ordenamiento por lowercase."""
        return texto.lower()

# Importar utilidades locales
sys.path.insert(0, str(Path(__file__).parent))
from lib_firmes import (
    cargar_negocios, cargar_fuentes, es_publicable,
    clave_orden_contenido, gh_slug, slug_simple,
    render_tabla, SlugTracker, FUENTES_COLUMNS
)

# Umbral para migrar ciudad a archivo regional standalone
UMBRAL_MIGRACION = 25


def agrupar_por_taxonomia(negocios: list[dict]) -> dict:
    """
    Agrupa negocios por ámbito → ciudad → categoría.

    Estructura retornada:
    {
        'Nacional': {
            '': {  # ciudad vacía para Nacional
                'Categoría1': [fila, fila, ...],
                'Categoría2': [fila, ...],
            }
        },
        'Regional': {
            'Bogotá': {
                'Restaurantes': [fila, ...],
                'Bares': [fila, ...],
            },
            'Medellín': {...}
        }
    }

    Valores 100% derivados del CSV, cero semillas hardcodeadas.
    """
    taxonomia = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for fila in negocios:
        ambito = fila['ambito'].strip()
        ciudad = fila['ciudad'].strip() if ambito == 'Regional' else ''
        categoria = fila['categoria'].strip()

        taxonomia[ambito][ciudad][categoria].append(fila)

    return taxonomia


def ordenar_filas(filas: list[dict]) -> list[dict]:
    """
    Ordena filas por tupla completa de contenido para determinismo.
    """
    return sorted(filas, key=clave_orden_contenido)


def generar_indice(taxonomia: dict, ciudades_migradas: set) -> str:
    """
    Genera el índice del README con enlaces a secciones.

    Args:
        taxonomia: Estructura agrupada
        ciudades_migradas: Set de ciudades con archivo standalone

    Returns:
        Markdown del índice
    """
    lineas = ["## Índice", ""]
    tracker = SlugTracker()

    # Nacional primero
    if 'Nacional' in taxonomia:
        lineas.append("### Nacional")
        lineas.append("")
        categorias_nacional = sorted(taxonomia['Nacional'].get('', {}).keys(), key=uca_sort_key)
        for cat in categorias_nacional:
            slug = gh_slug(f"Nacional — {cat}", tracker)
            lineas.append(f"- [{cat}](#{slug})")
        lineas.append("")

    # Regional después
    if 'Regional' in taxonomia:
        lineas.append("### Regional")
        lineas.append("")
        ciudades = sorted(taxonomia['Regional'].keys(), key=uca_sort_key)
        for ciudad in ciudades:
            if ciudad in ciudades_migradas:
                # Enlace a archivo externo
                slug_archivo = slug_simple(ciudad)
                lineas.append(f"- [{ciudad}](regionales/{slug_archivo}.md)")
            else:
                # Enlace a sección local
                slug = gh_slug(ciudad, tracker)
                lineas.append(f"- [{ciudad}](#{slug})")
        lineas.append("")

    return "\n".join(lineas)


def generar_seccion_fuentes(fuentes_usadas: set, todas_fuentes: dict) -> str:
    """
    Genera la sección FUENTES al final del documento.

    Args:
        fuentes_usadas: Set de fuente_ids usados en el documento
        todas_fuentes: Diccionario completo de fuentes

    Returns:
        Markdown de la sección FUENTES
    """
    lineas = ["## Fuentes", ""]

    # Ordenar fuentes por ID
    ids_ordenados = sorted(fuentes_usadas, key=uca_sort_key)

    for fid in ids_ordenados:
        if fid in todas_fuentes:
            fuente = todas_fuentes[fid]
            titulo = fuente['titulo']
            url = fuente['url']
            fecha = fuente['fecha']
            medio = fuente['medio_autor']
            url_archivo = fuente.get('url_archivo', '')

            # Formato: <a id="fuente-X"></a> **[X]** Título. Medio, Fecha. [URL](url) [📦](archivo)
            linea = f'<a id="fuente-{fid}"></a>**[{fid}]** {titulo}.'
            if medio:
                linea += f" {medio}."
            if fecha:
                linea += f" {fecha}."
            linea += f" [Enlace]({url})"
            if url_archivo:
                linea += f" [📦]({url_archivo})"

            lineas.append(linea)
            lineas.append("")

    return "\n".join(lineas)


def extraer_fuentes_usadas(negocios: list[dict]) -> set:
    """Extrae todos los fuente_ids usados en una lista de negocios."""
    usadas = set()
    for fila in negocios:
        ids_raw = fila.get('fuente_ids', '').strip()
        if ids_raw:
            for fid in ids_raw.split(';'):
                fid = fid.strip()
                if fid:
                    usadas.add(fid)
    return usadas


def generar_contenido_nacional(taxonomia: dict, fuentes: dict) -> tuple[str, set]:
    """
    Genera el contenido de la sección Nacional.

    Returns:
        (markdown, fuentes_usadas)
    """
    lineas = []
    fuentes_usadas = set()
    tracker = SlugTracker()

    if 'Nacional' not in taxonomia:
        return "", fuentes_usadas

    categorias = taxonomia['Nacional'].get('', {})
    cats_ordenadas = sorted(categorias.keys(), key=uca_sort_key)

    for cat in cats_ordenadas:
        filas = ordenar_filas(categorias[cat])
        slug = gh_slug(f"Nacional — {cat}", tracker)

        lineas.append(f"### Nacional — {cat}")
        lineas.append("")
        lineas.append(render_tabla(filas, fuentes))
        lineas.append("")

        fuentes_usadas.update(extraer_fuentes_usadas(filas))

    return "\n".join(lineas), fuentes_usadas


def generar_contenido_ciudad(ciudad: str, categorias: dict, fuentes: dict) -> tuple[str, set]:
    """
    Genera el contenido para una ciudad (inline en README o standalone).

    Returns:
        (markdown, fuentes_usadas)
    """
    lineas = []
    fuentes_usadas = set()
    tracker = SlugTracker()

    cats_ordenadas = sorted(categorias.keys(), key=uca_sort_key)

    for cat in cats_ordenadas:
        filas = ordenar_filas(categorias[cat])
        slug = gh_slug(f"{ciudad} — {cat}", tracker)

        lineas.append(f"#### {ciudad} — {cat}")
        lineas.append("")
        lineas.append(render_tabla(filas, fuentes))
        lineas.append("")

        fuentes_usadas.update(extraer_fuentes_usadas(filas))

    return "\n".join(lineas), fuentes_usadas


def generar_regional_inline(taxonomia: dict, fuentes: dict, ciudades_migradas: set) -> tuple[str, set]:
    """
    Genera el contenido regional que va inline en README (ciudades ≤ umbral).

    Returns:
        (markdown, fuentes_usadas)
    """
    lineas = []
    fuentes_usadas = set()

    if 'Regional' not in taxonomia:
        return "", fuentes_usadas

    ciudades = sorted(taxonomia['Regional'].keys(), key=uca_sort_key)

    for ciudad in ciudades:
        if ciudad in ciudades_migradas:
            continue  # Skip, va en archivo standalone

        categorias = taxonomia['Regional'][ciudad]
        lineas.append(f"### {ciudad}")
        lineas.append("")

        contenido, usadas = generar_contenido_ciudad(ciudad, categorias, fuentes)
        lineas.append(contenido)
        fuentes_usadas.update(usadas)

    return "\n".join(lineas), fuentes_usadas


def calcular_ciudades_migradas(taxonomia: dict) -> set:
    """
    Determina qué ciudades superan el umbral y van a archivo standalone.
    """
    migradas = set()

    if 'Regional' not in taxonomia:
        return migradas

    for ciudad, categorias in taxonomia['Regional'].items():
        total = sum(len(filas) for filas in categorias.values())
        if total > UMBRAL_MIGRACION:
            migradas.add(ciudad)

    return migradas


def generar_archivo_regional(ciudad: str, categorias: dict, fuentes: dict) -> str:
    """
    Genera el contenido completo de un archivo regional standalone.
    """
    lineas = [f"# {ciudad}", ""]

    # Índice de categorías
    lineas.append("## Índice")
    lineas.append("")
    tracker = SlugTracker()
    cats_ordenadas = sorted(categorias.keys(), key=uca_sort_key)
    for cat in cats_ordenadas:
        slug = gh_slug(f"{ciudad} — {cat}", tracker)
        lineas.append(f"- [{cat}](#{slug})")
    lineas.append("")

    # Contenido
    contenido, fuentes_usadas = generar_contenido_ciudad(ciudad, categorias, fuentes)
    lineas.append(contenido)

    # Fuentes
    lineas.append(generar_seccion_fuentes(fuentes_usadas, fuentes))

    # Footer
    lineas.append("---")
    lineas.append("")
    lineas.append("[← Volver al índice principal](../README.md)")
    lineas.append("")

    return "\n".join(lineas)


def generar_disclaimer() -> str:
    """Genera el disclaimer al pie del README."""
    return """---

## Aviso Legal

Los logos y nombres comerciales mostrados pertenecen a sus respectivos propietarios y se usan
de forma nominativa para identificación. Este uso NO implica afiliación, patrocinio ni respaldo.
Consulte [NOTICE](NOTICE) para más información.

Para solicitar corrección o eliminación de información, consulte [SECURITY.md](SECURITY.md).

---

*Generado automáticamente. Última actualización: ver historial de commits.*
"""


def generar_readme(taxonomia: dict, fuentes: dict, ciudades_migradas: set) -> str:
    """
    Genera el contenido completo del README.md.
    """
    lineas = ["# Firmes", ""]
    lineas.append("Directorio de negocios y empresas con apoyo público declarado.")
    lineas.append("")

    # Índice
    lineas.append(generar_indice(taxonomia, ciudades_migradas))

    # Contenido Nacional
    contenido_nacional, fuentes_nacional = generar_contenido_nacional(taxonomia, fuentes)
    if contenido_nacional:
        lineas.append("## Nacional")
        lineas.append("")
        lineas.append(contenido_nacional)

    # Contenido Regional (inline)
    contenido_regional, fuentes_regional = generar_regional_inline(taxonomia, fuentes, ciudades_migradas)
    if contenido_regional:
        lineas.append("## Regional")
        lineas.append("")
        lineas.append(contenido_regional)

    # Fuentes
    todas_fuentes_usadas = fuentes_nacional | fuentes_regional
    lineas.append(generar_seccion_fuentes(todas_fuentes_usadas, fuentes))

    # Disclaimer
    lineas.append(generar_disclaimer())

    return "\n".join(lineas)


def limpiar_regionales_huerfanos(dir_regionales: Path, ciudades_migradas: set):
    """
    Elimina archivos regionales que ya no corresponden a ciudades migradas.
    """
    if not dir_regionales.exists():
        return

    slugs_validos = {slug_simple(c) for c in ciudades_migradas}

    for archivo in dir_regionales.glob("*.md"):
        slug_archivo = archivo.stem
        if slug_archivo not in slugs_validos:
            archivo.unlink()
            print(f"  Eliminado huérfano: regionales/{archivo.name}")


def main():
    """Punto de entrada principal."""
    # Rutas
    proyecto = Path(__file__).parent.parent
    data_dir = proyecto / "data"

    # Usar fixtures si existen, sino data principal
    if (data_dir / "fixtures" / "negocios.csv").exists():
        negocios_path = data_dir / "fixtures" / "negocios.csv"
        fuentes_path = data_dir / "fixtures" / "fuentes.csv"
        print("Usando datos de fixtures/")
    else:
        negocios_path = data_dir / "negocios.csv"
        fuentes_path = data_dir / "fuentes.csv"
        print("Usando datos de data/")

    # Cargar datos
    print("Cargando datos...")
    negocios_raw = cargar_negocios(negocios_path)
    fuentes = cargar_fuentes(fuentes_path)

    # Filtrar publicables
    publicables = [n for n in negocios_raw if es_publicable(n, fuentes)]
    filtrados = len(negocios_raw) - len(publicables)

    print(f"  Negocios: {len(negocios_raw)} total, {len(publicables)} publicables, {filtrados} filtrados")

    # Agrupar
    taxonomia = agrupar_por_taxonomia(publicables)

    # Calcular migraciones
    ciudades_migradas = calcular_ciudades_migradas(taxonomia)

    # Crear directorio regionales
    dir_regionales = proyecto / "regionales"
    dir_regionales.mkdir(exist_ok=True)

    # Limpiar huérfanos
    limpiar_regionales_huerfanos(dir_regionales, ciudades_migradas)

    # Generar archivos regionales standalone
    for ciudad in ciudades_migradas:
        categorias = taxonomia['Regional'][ciudad]
        contenido = generar_archivo_regional(ciudad, categorias, fuentes)
        archivo = dir_regionales / f"{slug_simple(ciudad)}.md"
        archivo.write_text(contenido, encoding='utf-8')
        print(f"  Generado: regionales/{archivo.name}")

    # Generar README
    readme_contenido = generar_readme(taxonomia, fuentes, ciudades_migradas)
    readme_path = proyecto / "README.md"
    readme_path.write_text(readme_contenido, encoding='utf-8')
    print(f"  Generado: README.md")

    # Resumen
    ancladas = len(taxonomia.get('Regional', {})) - len(ciudades_migradas)
    print()
    print("=== RESUMEN ===")
    print(f"Publicados={len(publicables)} Filtrados={filtrados} Ancladas={ancladas} Migradas={len(ciudades_migradas)}")


if __name__ == "__main__":
    main()
