# -*- coding: utf-8 -*-
"""
Tests para lib_firmes.py

Incluye tests GOLDEN pinned a slugs reales de GitHub.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lib_firmes import (
    gh_slug, SlugTracker, slug_simple,
    parse_redes, es_publicable, clave_orden_contenido,
    normalizar_redes, normalizar_fuente_ids
)


class TestGhSlug:
    """Tests GOLDEN para gh_slug - pinned a comportamiento real de GitHub."""

    def test_golden_bogota_emdash_restaurantes(self):
        """Em-dash se elimina, dejando DOS espacios -> DOS guiones."""
        assert gh_slug("Bogotá — Restaurantes") == "bogotá--restaurantes"

    def test_golden_bogota_colon_restaurantes(self):
        """Dos puntos se elimina, UN espacio -> UN guión."""
        assert gh_slug("Bogotá: Restaurantes") == "bogotá-restaurantes"

    def test_golden_cafes_ampersand_bares(self):
        """Ampersand se elimina, DOS espacios -> DOS guiones."""
        assert gh_slug("Cafés & Bares") == "cafés--bares"

    def test_preserva_acentos(self):
        """Acentos y ñ se conservan."""
        assert gh_slug("Señor Café") == "señor-café"
        assert gh_slug("Ñoño") == "ñoño"

    def test_minusculas(self):
        """Convierte a minúsculas."""
        assert gh_slug("MAYÚSCULAS") == "mayúsculas"
        assert gh_slug("MiXeD CaSe") == "mixed-case"

    def test_espacios_multiples(self):
        """Cada espacio se convierte en un guión (no se colapsan)."""
        assert gh_slug("a  b") == "a--b"
        assert gh_slug("a   b") == "a---b"

    def test_elimina_puntuacion(self):
        """Puntuación se elimina."""
        assert gh_slug("Hola, mundo!") == "hola-mundo"
        assert gh_slug("Test (ejemplo)") == "test-ejemplo"
        assert gh_slug("A/B testing") == "ab-testing"

    def test_elimina_emojis(self):
        """Emojis se eliminan."""
        assert gh_slug("Café ☕ Delicia") == "café--delicia"

    def test_tracker_duplicados(self):
        """Tracker añade sufijos para duplicados."""
        tracker = SlugTracker()
        assert gh_slug("Test", tracker) == "test"
        assert gh_slug("Test", tracker) == "test-1"
        assert gh_slug("Test", tracker) == "test-2"
        assert gh_slug("Otro", tracker) == "otro"
        assert gh_slug("Test", tracker) == "test-3"


class TestSlugSimple:
    """Tests para slug_simple (nombres de archivo)."""

    def test_normaliza_acentos(self):
        """Normaliza acentos a ASCII."""
        assert slug_simple("Bogotá") == "bogota"
        assert slug_simple("Café") == "cafe"
        assert slug_simple("Señor") == "senor"

    def test_colapsa_guiones(self):
        """Colapsa guiones múltiples."""
        assert slug_simple("a - b") == "a-b"
        assert slug_simple("a  -  b") == "a-b"

    def test_elimina_guiones_extremos(self):
        """Elimina guiones al inicio y final."""
        assert slug_simple("-test-") == "test"
        assert slug_simple("--test--") == "test"


class TestParseRedes:
    """Tests para parse_redes."""

    def test_parse_simple(self):
        """Parsea formato simple."""
        result = parse_redes("instagram=https://instagram.com/test")
        assert len(result) == 1
        assert result[0]['plataforma'] == 'instagram'
        assert result[0]['url'] == 'https://instagram.com/test'

    def test_parse_multiple(self):
        """Parsea múltiples redes."""
        result = parse_redes("instagram=url1;facebook=url2;x=url3")
        assert len(result) == 3
        plataformas = [r['plataforma'] for r in result]
        assert 'instagram' in plataformas
        assert 'facebook' in plataformas
        assert 'x' in plataformas

    def test_vacio(self):
        """Retorna lista vacía para campo vacío."""
        assert parse_redes("") == []
        assert parse_redes("   ") == []
        assert parse_redes(None) == []


class TestEsPublicable:
    """Tests para es_publicable."""

    def test_publicable_con_fuente(self):
        """Fila con evidencia válida y fuente es publicable."""
        fila = {'evidencia': 'Declaración propia', 'fuente_ids': 'f-001'}
        fuentes = {'f-001': {'fuente_id': 'f-001'}}
        assert es_publicable(fila, fuentes) is True

    def test_no_publicable_por_determinar(self):
        """'Por determinar' nunca es publicable."""
        fila = {'evidencia': 'Por determinar', 'fuente_ids': 'f-001'}
        fuentes = {'f-001': {'fuente_id': 'f-001'}}
        assert es_publicable(fila, fuentes) is False

    def test_no_publicable_sin_fuentes(self):
        """Sin fuente_ids no es publicable."""
        fila = {'evidencia': 'Prensa', 'fuente_ids': ''}
        fuentes = {'f-001': {'fuente_id': 'f-001'}}
        assert es_publicable(fila, fuentes) is False

    def test_no_publicable_fuente_inexistente(self):
        """Con fuente_id que no existe no es publicable."""
        fila = {'evidencia': 'Prensa', 'fuente_ids': 'f-999'}
        fuentes = {'f-001': {'fuente_id': 'f-001'}}
        assert es_publicable(fila, fuentes) is False


class TestNormalizacion:
    """Tests para funciones de normalización."""

    def test_normalizar_redes_ordena(self):
        """Ordena plataformas alfabéticamente."""
        result = normalizar_redes("x=url1;instagram=url2;facebook=url3")
        assert result == "facebook=url3;instagram=url2;x=url1"

    def test_normalizar_fuente_ids_ordena(self):
        """Ordena IDs alfabéticamente."""
        result = normalizar_fuente_ids("f-003;f-001;f-002")
        assert result == "f-001;f-002;f-003"

    def test_clave_orden_contenido_determinista(self):
        """Misma fila produce misma clave."""
        fila = {
            'nombre': 'Test',
            'categoria': 'Cat',
            'ciudad': 'Ciudad',
            'ambito': 'Regional',
            'redes': 'x=url',
            'evidencia': 'Prensa',
            'fuente_ids': 'f-001',
            'logo': ''
        }
        clave1 = clave_orden_contenido(fila)
        clave2 = clave_orden_contenido(fila)
        assert clave1 == clave2
