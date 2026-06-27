# -*- coding: utf-8 -*-
"""
Tests para validate.py

Incluye casos de fallo para verificar detección de errores.
"""
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES = PROJECT_ROOT / "data" / "fixtures"


class TestValidateSuccess:
    """Tests de validación exitosa."""

    def test_validate_fixtures_validos(self):
        """Fixtures válidos pasan validación."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "validate.py")],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )
        assert result.returncode == 0, f"Validación falló: {result.stdout}"


class TestValidateFailures:
    """Tests de detección de errores."""

    def test_detecta_fuente_inexistente(self):
        """Detecta referencia a fuente que no existe."""
        negocios = FIXTURES / "negocios.csv"
        original = negocios.read_text(encoding='utf-8')

        try:
            # Introducir fuente inexistente
            modificado = original.replace('f-022', 'f-999')
            negocios.write_text(modificado, encoding='utf-8')

            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "validate.py")],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )

            assert result.returncode != 0
            assert 'f-999' in result.stdout

        finally:
            negocios.write_text(original, encoding='utf-8')

    def test_detecta_url_archivo_no_wayback(self):
        """Detecta url_archivo que no es de Wayback para evidencia Prensa."""
        fuentes = FIXTURES / "fuentes.csv"
        original = fuentes.read_text(encoding='utf-8')

        try:
            # Cambiar URL de Wayback a URL normal
            modificado = original.replace(
                'https://web.archive.org/web/20250420/https://rcnradio.com/nota-ejemplo',
                'https://example.com/no-wayback'
            )
            fuentes.write_text(modificado, encoding='utf-8')

            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "validate.py")],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )

            assert result.returncode != 0
            assert 'no es Wayback' in result.stdout

        finally:
            fuentes.write_text(original, encoding='utf-8')

    def test_detecta_duplicados_contenido(self):
        """Detecta filas con contenido duplicado."""
        negocios = FIXTURES / "negocios.csv"
        original = negocios.read_text(encoding='utf-8')

        try:
            # Duplicar una línea
            lineas = original.strip().split('\n')
            lineas.append(lineas[2])  # Duplicar línea 2
            negocios.write_text('\n'.join(lineas) + '\n', encoding='utf-8')

            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "validate.py")],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT
            )

            assert result.returncode != 0
            assert 'duplicado de contenido' in result.stdout

        finally:
            negocios.write_text(original, encoding='utf-8')


class TestValidateGobernanza:
    """Tests de validación de gobernanza (requiere --gobernanza)."""

    def test_gobernanza_sin_archivos(self):
        """Sin archivos de gobernanza, --gobernanza falla."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "validate.py"), '--gobernanza'],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT
        )

        # Debe fallar porque faltan archivos de gobernanza
        assert result.returncode != 0
        assert 'Gobernanza' in result.stdout
