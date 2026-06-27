# -*- coding: utf-8 -*-
"""
lib_firmes.py - Utilidades base para el generador del directorio firmes.

Funciones puras y testeables, separadas del orquestador.
"""
import csv
import re
import unicodedata
from pathlib import Path
from typing import Any


# Esquema de negocios.csv (orden fijo)
NEGOCIOS_COLUMNS = ['ambito', 'ciudad', 'categoria', 'nombre', 'logo', 'redes', 'evidencia', 'fuente_ids']
NEGOCIOS_AMBITO_ENUM = {'Nacional', 'Regional'}
NEGOCIOS_EVIDENCIA_ENUM = {'Declaración propia', 'Prensa', 'Evento público', 'Por determinar'}

# Esquema de fuentes.csv (orden fijo)
FUENTES_COLUMNS = ['fuente_id', 'titulo', 'url', 'fecha', 'medio_autor', 'nota', 'url_archivo']


class SlugTracker:
    """Rastrea slugs generados para añadir sufijo -1, -2, etc. a duplicados."""

    def __init__(self):
        self.seen: dict[str, int] = {}

    def get_unique(self, slug: str) -> str:
        """Devuelve slug único, añadiendo sufijo numérico si es duplicado."""
        if slug not in self.seen:
            self.seen[slug] = 0
            return slug
        self.seen[slug] += 1
        return f"{slug}-{self.seen[slug]}"

    def reset(self):
        """Reinicia el tracker para un nuevo contexto (archivo)."""
        self.seen.clear()


def _es_caracter_a_conservar(c: str) -> bool:
    """
    Determina si un carácter debe conservarse en el slug de GitHub.

    GitHub slugger conserva:
    - Letras (incluyendo acentuadas: á, é, í, ó, ú, ñ, etc.)
    - Números
    - Espacios (que luego se convierten a guiones)

    GitHub slugger ELIMINA (no reemplaza):
    - Puntuación: !"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~
    - Símbolos especiales: em-dash, en-dash, bullets, guillemets, etc.
    - Emojis
    """
    if c.isspace():
        return True  # Espacios se conservan (para convertir a guiones después)
    if c.isalnum():
        return True  # Letras y números se conservan
    # Todo lo demás se elimina
    return False


def gh_slug(texto: str, tracker: SlugTracker = None) -> str:
    """
    Réplica FIEL de github-slugger para anclas de encabezados de GitHub.

    Algoritmo:
    1. Minúsculas (Unicode-aware)
    2. ELIMINAR (NO hyphenar) puntuación/símbolos/emoji
    3. Cada carácter de espacio en blanco -> un guión (NO se colapsan, NO se recortan)
    4. Conservar acentos y ñ
    5. Sufijo de ocurrencia -1, -2... para duplicados (si se proporciona tracker)

    Footgun documentado:
    - "Bogotá — Restaurantes" -> "bogotá--restaurantes" (em-dash eliminado, DOS espacios -> DOS guiones)
    - "Bogotá: Restaurantes" -> "bogotá-restaurantes" (dos puntos eliminado, UN espacio -> UN guión)
    - "Cafés & Bares" -> "cafés--bares" (& eliminado, DOS espacios -> DOS guiones)
    """
    # 1. Minúsculas
    result = texto.lower()

    # 2. Eliminar puntuación/símbolos/emoji (conservar letras, números, espacios)
    result = ''.join(c for c in result if _es_caracter_a_conservar(c))

    # 3. Cada whitespace -> un guión (NO colapsar)
    result = re.sub(r'\s', '-', result)

    # 4. Acentos y ñ se conservan (ya están en result)

    # 5. Sufijo para duplicados
    if tracker is not None:
        result = tracker.get_unique(result)

    return result


def disambiguar(slug: str, registro: dict, superficie: str, tracker: SlugTracker = None) -> str:
    """
    Estrategia de anclas por SUPERFICIE.

    - README (*.md renderizado por GitHub): GitHub sanitiza HTML y prefija id con 'user-content-',
      así que usamos anclas auto-generadas por GitHub a partir del TEXTO de encabezados (gh_slug).
      El índice del README enlaza a heading-slugs.

    - Pages (HTML estático en github.io): sin sanitización, usamos <a id="..."> explícitos y estables.

    Args:
        slug: Slug base (ya computado con gh_slug para README, o construido para Pages)
        registro: Diccionario con datos del registro (para contexto si es necesario)
        superficie: 'readme' o 'pages'
        tracker: SlugTracker para desambiguación de duplicados

    Returns:
        Slug desambiguado para la superficie especificada.
    """
    if superficie == 'readme':
        # Para README, el slug ya viene de gh_slug aplicado al texto del encabezado
        # Solo necesitamos rastrear duplicados
        if tracker:
            return tracker.get_unique(slug)
        return slug
    elif superficie == 'pages':
        # Para Pages, construimos id explícitos más controlados
        # Formato: <ciudad>-<categoria> o <ambito>-<categoria>
        if tracker:
            return tracker.get_unique(slug)
        return slug
    else:
        raise ValueError(f"Superficie desconocida: {superficie}")


def parse_redes(campo: str) -> list[dict[str, str]]:
    """
    Parsea el campo redes del CSV.

    Formato: "plataforma=url;plataforma2=url2"
    Plataformas soportadas: instagram, x, facebook, tiktok, youtube, web

    Returns:
        Lista de dicts con keys 'plataforma' y 'url'
    """
    if not campo or not campo.strip():
        return []

    redes = []
    for par in campo.split(';'):
        par = par.strip()
        if '=' in par:
            plataforma, url = par.split('=', 1)
            redes.append({
                'plataforma': plataforma.strip().lower(),
                'url': url.strip()
            })
    return redes


def cargar_csv(path: Path, esquema: list[str], nombre: str) -> list[dict[str, str]]:
    """
    Carga un CSV validando esquema (columnas en orden).

    Args:
        path: Ruta al archivo CSV
        esquema: Lista de nombres de columnas esperadas en orden
        nombre: Nombre del archivo para mensajes de error

    Returns:
        Lista de diccionarios (una por fila)

    Raises:
        ValueError: Si el esquema no coincide
    """
    with open(path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)

        # Validar columnas
        if reader.fieldnames is None:
            raise ValueError(f"{nombre}: archivo vacío o sin encabezados")

        columnas_archivo = list(reader.fieldnames)
        if columnas_archivo != esquema:
            raise ValueError(
                f"{nombre}: esquema inválido.\n"
                f"  Esperado: {esquema}\n"
                f"  Encontrado: {columnas_archivo}"
            )

        return list(reader)


def cargar_negocios(path: Path) -> list[dict[str, str]]:
    """Carga negocios.csv validando esquema y enums."""
    filas = cargar_csv(path, NEGOCIOS_COLUMNS, 'negocios.csv')

    errores = []
    for i, fila in enumerate(filas, start=2):  # +2 porque línea 1 es header
        # Validar ambito
        if fila['ambito'] not in NEGOCIOS_AMBITO_ENUM:
            errores.append(f"Fila {i}: ambito '{fila['ambito']}' no válido")

        # Validar ciudad requerida si Regional
        if fila['ambito'] == 'Regional' and not fila['ciudad'].strip():
            errores.append(f"Fila {i}: ciudad requerida para ambito Regional")

        # Validar evidencia
        if fila['evidencia'] not in NEGOCIOS_EVIDENCIA_ENUM:
            errores.append(f"Fila {i}: evidencia '{fila['evidencia']}' no válida")

    if errores:
        raise ValueError("negocios.csv: errores de validación:\n  " + "\n  ".join(errores))

    return filas


def cargar_fuentes(path: Path) -> dict[str, dict[str, str]]:
    """
    Carga fuentes.csv validando esquema.

    Returns:
        Diccionario indexado por fuente_id
    """
    filas = cargar_csv(path, FUENTES_COLUMNS, 'fuentes.csv')

    fuentes = {}
    errores = []
    for i, fila in enumerate(filas, start=2):
        fuente_id = fila['fuente_id'].strip()
        if not fuente_id:
            errores.append(f"Fila {i}: fuente_id vacío")
            continue
        if fuente_id in fuentes:
            errores.append(f"Fila {i}: fuente_id '{fuente_id}' duplicado")
            continue
        fuentes[fuente_id] = fila

    if errores:
        raise ValueError("fuentes.csv: errores de validación:\n  " + "\n  ".join(errores))

    return fuentes


def es_publicable(fila: dict[str, str], fuentes: dict[str, dict]) -> bool:
    """
    Determina si una fila de negocios es publicable.

    Criterios:
    - evidencia != "Por determinar"
    - fuente_ids no vacío
    - Todos los fuente_ids resuelven en fuentes.csv
    """
    # No publicar "Por determinar"
    if fila['evidencia'] == 'Por determinar':
        return False

    # Debe tener al menos una fuente
    fuente_ids_raw = fila['fuente_ids'].strip()
    if not fuente_ids_raw:
        return False

    # Todas las fuentes deben resolver
    fuente_ids = [f.strip() for f in fuente_ids_raw.split(';') if f.strip()]
    for fid in fuente_ids:
        if fid not in fuentes:
            return False

    return True


def normalizar_redes(redes_raw: str) -> str:
    """
    Normaliza el campo redes para orden determinista.
    Ordena plataformas alfabéticamente.
    """
    if not redes_raw or not redes_raw.strip():
        return ''

    pares = []
    for par in redes_raw.split(';'):
        par = par.strip()
        if '=' in par:
            pares.append(par)

    # Ordenar por plataforma
    pares.sort(key=lambda p: p.split('=')[0].lower())
    return ';'.join(pares)


def normalizar_fuente_ids(fuente_ids_raw: str) -> str:
    """
    Normaliza fuente_ids para orden determinista.
    Ordena IDs alfabéticamente.
    """
    if not fuente_ids_raw or not fuente_ids_raw.strip():
        return ''

    ids = [f.strip() for f in fuente_ids_raw.split(';') if f.strip()]
    ids.sort()
    return ';'.join(ids)


def clave_orden_contenido(fila: dict[str, str]) -> tuple:
    """
    Genera la clave de orden total por contenido para una fila.

    Orden de la tupla (campos publicados):
    (nombre, categoria, ciudad, ambito, redes_normalizadas, evidencia, fuente_ids_ordenados, logo)

    El orden es determinista y no depende de la posición física en el CSV.
    Solo filas byte-idénticas en todo el contenido producen la misma clave.
    """
    return (
        fila['nombre'].strip(),
        fila['categoria'].strip(),
        fila['ciudad'].strip(),
        fila['ambito'].strip(),
        normalizar_redes(fila['redes']),
        fila['evidencia'].strip(),
        normalizar_fuente_ids(fila['fuente_ids']),
        fila['logo'].strip()
    )


def slug_simple(texto: str) -> str:
    """
    Genera un slug simple para nombres de archivo (logos, regionales).

    A diferencia de gh_slug (que replica GitHub), este es más permisivo:
    - Minúsculas
    - Normaliza caracteres acentuados a ASCII base
    - Reemplaza espacios y caracteres especiales por guiones
    - Colapsa guiones múltiples
    - Elimina guiones al inicio/final
    """
    # Minúsculas
    result = texto.lower()

    # Normalizar a NFD y eliminar marcas diacríticas
    result = unicodedata.normalize('NFD', result)
    result = ''.join(c for c in result if unicodedata.category(c) != 'Mn')

    # Reemplazar caracteres no alfanuméricos por guiones
    result = re.sub(r'[^a-z0-9]+', '-', result)

    # Colapsar guiones múltiples
    result = re.sub(r'-+', '-', result)

    # Eliminar guiones al inicio/final
    result = result.strip('-')

    return result


# ==============================================================================
# RENDERIZADO HTML
# ==============================================================================

# Mapa de evidencias a archivos de badge
EVIDENCIA_BADGE_MAP = {
    'Declaración propia': 'declaracion.svg',
    'Prensa': 'prensa.svg',
    'Evento público': 'evento.svg',
    'Donación': 'donacion.svg',
    'Publicidad': 'publicidad.svg',
}

# Plataformas de redes sociales soportadas
PLATAFORMAS_REDES = {'instagram', 'x', 'facebook', 'tiktok', 'youtube', 'web'}


def _generar_iniciales(nombre: str) -> str:
    """
    Genera iniciales para un nombre (máximo 2 caracteres).

    Ejemplos:
    - "Café Delicia" -> "CD"
    - "El Buen Sabor" -> "EB"
    - "McDonald's" -> "MC"
    """
    palabras = nombre.split()
    if len(palabras) >= 2:
        return (palabras[0][0] + palabras[1][0]).upper()
    elif len(nombre) >= 2:
        return nombre[:2].upper()
    elif nombre:
        return nombre[0].upper()
    return "??"


def _generar_badge_iniciales_svg(iniciales: str, color: str = "#6b7280") -> str:
    """
    Genera SVG inline para badge de iniciales.

    Args:
        iniciales: Texto de iniciales (1-2 caracteres)
        color: Color de fondo en hex

    Returns:
        String SVG completo
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">'
        f'<rect width="40" height="40" rx="4" fill="{color}"/>'
        f'<text x="20" y="26" text-anchor="middle" fill="#fff" '
        f'font-family="Arial,sans-serif" font-size="16" font-weight="bold">{iniciales}</text>'
        f'</svg>'
    )


def render_logo(fila: dict[str, str], base_assets: str = "assets") -> str:
    """
    Renderiza el logo de un negocio con cadena de fallback.

    Cadena de resolución:
    1. assets/logos/<slug>.png (vendorizado)
    2. URL externa (si logo empieza con http)
    3. Badge de iniciales generado (fallback final)

    Args:
        fila: Diccionario con datos del negocio
        base_assets: Ruta base a carpeta assets

    Returns:
        HTML <img> con width="40"
    """
    nombre = fila['nombre'].strip()
    logo_field = fila.get('logo', '').strip()
    slug = slug_simple(nombre)

    # 1. Vendorizado local
    logo_local = f"{base_assets}/logos/{slug}.png"

    # 2. URL externa
    if logo_field.startswith('http://') or logo_field.startswith('https://'):
        return f'<img src="{logo_field}" alt="{nombre}" width="40">'

    # 3. Si hay valor en logo (ruta relativa)
    if logo_field:
        return f'<img src="{logo_field}" alt="{nombre}" width="40">'

    # 4. Fallback: badge de iniciales
    iniciales = _generar_iniciales(nombre)
    # Para el README usamos una imagen inline con data URI o simplemente texto
    # Pero como GitHub sanitiza SVG inline, usamos un badge generado
    # Para simplicidad, retornamos referencia a un badge que se generará
    badge_path = f"{base_assets}/badges/iniciales-{slug}.svg"
    return f'<img src="{badge_path}" alt="{iniciales}" width="40">'


def render_redes(fila: dict[str, str], base_assets: str = "assets") -> str:
    """
    Renderiza los iconos de redes sociales enlazados.

    Args:
        fila: Diccionario con datos del negocio
        base_assets: Ruta base a carpeta assets

    Returns:
        HTML con iconos enlazados, separados por espacio
    """
    redes = parse_redes(fila.get('redes', ''))

    if not redes:
        return ''

    iconos = []
    for red in redes:
        plataforma = red['plataforma']
        url = red['url']

        if plataforma in PLATAFORMAS_REDES:
            icono_path = f"{base_assets}/icons/{plataforma}.svg"
            iconos.append(
                f'<a href="{url}" title="{plataforma.capitalize()}">'
                f'<img src="{icono_path}" alt="{plataforma}" width="20"></a>'
            )

    return ' '.join(iconos)


def render_evidencia(fila: dict[str, str], base_assets: str = "assets") -> str:
    """
    Renderiza el badge de tipo de evidencia.

    Args:
        fila: Diccionario con datos del negocio
        base_assets: Ruta base a carpeta assets

    Returns:
        HTML <img> con el badge correspondiente
    """
    evidencia = fila.get('evidencia', '').strip()

    badge_file = EVIDENCIA_BADGE_MAP.get(evidencia)
    if badge_file:
        badge_path = f"{base_assets}/badges/{badge_file}"
        return f'<img src="{badge_path}" alt="{evidencia}">'

    # Fallback: texto simple
    return evidencia


def render_fuentes(fila: dict[str, str], fuentes: dict[str, dict]) -> str:
    """
    Renderiza las referencias de fuentes como citas numeradas estilo Wikipedia.

    Args:
        fila: Diccionario con datos del negocio
        fuentes: Diccionario de fuentes indexado por fuente_id

    Returns:
        HTML con enlaces a las fuentes [1][2]...
    """
    fuente_ids_raw = fila.get('fuente_ids', '').strip()
    if not fuente_ids_raw:
        return ''

    fuente_ids = [f.strip() for f in fuente_ids_raw.split(';') if f.strip()]

    citas = []
    for fid in fuente_ids:
        if fid in fuentes:
            # Enlace al ancla de la fuente en sección FUENTES
            citas.append(f'<a href="#fuente-{fid}">[{fid}]</a>')

    return ''.join(citas)


def render_fila(fila: dict[str, str], fuentes: dict[str, dict], base_assets: str = "assets") -> str:
    """
    Renderiza una fila completa de la tabla HTML.

    Columnas (5, sin headers):
    1. Logo
    2. Nombre
    3. Redes sociales
    4. Evidencia (badge)
    5. Fuentes (citas)

    Args:
        fila: Diccionario con datos del negocio
        fuentes: Diccionario de fuentes
        base_assets: Ruta base a carpeta assets

    Returns:
        HTML <tr> con 5 <td>
    """
    nombre = fila['nombre'].strip()

    col_logo = render_logo(fila, base_assets)
    col_nombre = nombre
    col_redes = render_redes(fila, base_assets)
    col_evidencia = render_evidencia(fila, base_assets)
    col_fuentes = render_fuentes(fila, fuentes)

    return (
        f'<tr>'
        f'<td>{col_logo}</td>'
        f'<td>{col_nombre}</td>'
        f'<td>{col_redes}</td>'
        f'<td>{col_evidencia}</td>'
        f'<td>{col_fuentes}</td>'
        f'</tr>'
    )


def render_tabla(filas: list[dict[str, str]], fuentes: dict[str, dict], base_assets: str = "assets") -> str:
    """
    Renderiza una tabla HTML completa SIN encabezados.

    Args:
        filas: Lista de diccionarios con datos de negocios
        fuentes: Diccionario de fuentes
        base_assets: Ruta base a carpeta assets

    Returns:
        HTML <table> completo sin <thead>
    """
    rows = []
    for fila in filas:
        rows.append(render_fila(fila, fuentes, base_assets))

    return (
        '<table>\n'
        '<tbody>\n'
        + '\n'.join(rows) + '\n'
        '</tbody>\n'
        '</table>'
    )
