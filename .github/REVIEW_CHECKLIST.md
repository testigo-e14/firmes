# Checklist de Revisión

## Antes de Aprobar un PR

### Datos
- [ ] Toda entrada tiene `fuente_ids` válidos
- [ ] Ninguna entrada tiene evidencia "Por determinar"
- [ ] Los `fuente_ids` referenciados existen en `fuentes.csv`

### Fuentes de Prensa
- [ ] Toda fuente con evidencia=Prensa tiene `url_archivo`
- [ ] Los `url_archivo` apuntan a `web.archive.org`
- [ ] Verifiqué que el snapshot de Wayback es accesible

### Logos
- [ ] Los logos nuevos tienen uso nominativo legítimo
- [ ] No se incluyen logos de alta resolución innecesaria

### Validación
- [ ] `python scripts/validate.py` pasa sin errores
- [ ] El CI pasa todos los checks
