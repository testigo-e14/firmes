# Cómo Contribuir

Gracias por su interés en contribuir a este proyecto.

## Para Usuarios No Técnicos

### Proponer un Nuevo Negocio

1. Vaya a la pestaña **Issues**
2. Haga clic en **New Issue**
3. Seleccione **Proponer Negocio**
4. Complete el formulario con:
   - Nombre del negocio
   - Ciudad
   - Categoría
   - Enlace a la fuente que verifica el apoyo público
5. Envíe el issue

### Solicitar Corrección o Eliminación

1. Vaya a **Issues**
2. Seleccione **Solicitar Corrección/Eliminación**
3. Explique el motivo de la solicitud
4. Proporcione evidencia si es posible

## Para Mantenedores

### Proceso de Actualización

1. Edite `data/negocios.csv` y/o `data/fuentes.csv`
2. Asegúrese de incluir fuentes verificables
3. Para evidencia tipo **Prensa**, incluya `url_archivo` de Wayback Machine
4. Ejecute `python scripts/generate.py`
5. Verifique con `python scripts/validate.py`
6. Cree un Pull Request

### Requisitos de Calidad

- Toda entrada debe tener fuente verificable
- No se aceptan entradas "Por determinar"
- Los logos deben tener uso nominativo legítimo
- Las fuentes de prensa deben tener snapshot en Wayback
