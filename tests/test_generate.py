# -*- coding: utf-8 -*-
"""
Tests para generate.py

Incluye test de shuffle para verificar output determinista.
"""
import hashlib
import random
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent


class TestGenerateIdempotencia:
    """Tests de idempotencia del generador."""

    def test_dos_ejecuciones_mismo_output(self):
        """Dos ejecuciones consecutivas producen el mismo output."""
        # Primera ejecución
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "generate.py")],
            capture_output=True,
            cwd=PROJECT_ROOT
        )
        readme1 = (PROJECT_ROOT / "README.md").read_bytes()
        hash1 = hashlib.sha256(readme1).hexdigest()

        # Segunda ejecución
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "generate.py")],
            capture_output=True,
            cwd=PROJECT_ROOT
        )
        readme2 = (PROJECT_ROOT / "README.md").read_bytes()
        hash2 = hashlib.sha256(readme2).hexdigest()

        assert hash1 == hash2, "Output difiere entre ejecuciones"


class TestGenerateShuffle:
    """Test de shuffle para verificar orden determinista."""

    def test_shuffle_csv_mismo_output(self):
        """Barajar el CSV y regenerar produce output byte-idéntico."""
        fixtures = PROJECT_ROOT / "data" / "fixtures" / "negocios.csv"

        # Guardar original
        original = fixtures.read_text(encoding='utf-8')

        try:
            # Primera generación
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "generate.py")],
                capture_output=True,
                cwd=PROJECT_ROOT
            )
            readme1 = (PROJECT_ROOT / "README.md").read_bytes()
            hash1 = hashlib.sha256(readme1).hexdigest()

            # Barajar CSV
            lineas = original.splitlines()
            header = lineas[0]
            data = lineas[1:]
            random.seed(42)
            random.shuffle(data)
            fixtures.write_text(header + '\n' + '\n'.join(data) + '\n', encoding='utf-8')

            # Segunda generación
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "generate.py")],
                capture_output=True,
                cwd=PROJECT_ROOT
            )
            readme2 = (PROJECT_ROOT / "README.md").read_bytes()
            hash2 = hashlib.sha256(readme2).hexdigest()

            assert hash1 == hash2, "Output difiere después de shuffle"

        finally:
            # Restaurar original
            fixtures.write_text(original, encoding='utf-8')
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "generate.py")],
                capture_output=True,
                cwd=PROJECT_ROOT
            )


class TestGenerateOutput:
    """Tests del contenido generado."""

    def test_readme_sin_thead(self):
        """README no debe contener <thead>."""
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "generate.py")],
            capture_output=True,
            cwd=PROJECT_ROOT
        )
        readme = (PROJECT_ROOT / "README.md").read_text(encoding='utf-8')
        assert '<thead>' not in readme, "README contiene <thead>"

    def test_readme_tiene_disclaimer(self):
        """README debe tener disclaimer con enlaces a NOTICE y SECURITY."""
        readme = (PROJECT_ROOT / "README.md").read_text(encoding='utf-8')
        assert 'Aviso Legal' in readme
        assert 'NOTICE' in readme
        assert 'SECURITY.md' in readme

    def test_readme_tiene_fuentes(self):
        """README debe tener sección de fuentes."""
        readme = (PROJECT_ROOT / "README.md").read_text(encoding='utf-8')
        assert '## Fuentes' in readme
