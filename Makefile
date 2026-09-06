# Atajos del proyecto (opcional: requiere 'make')
PY := python

.PHONY: instalar pruebas casos reporte app limpiar todo

instalar:      ## instala las dependencias
	$(PY) -m pip install -r requirements.txt

pruebas:       ## ejecuta la batería de verificación
	$(PY) -m pytest

casos:         ## resuelve los dos casos de estudio y genera las figuras
	$(PY) main.py casos

reporte:       ## genera el reporte técnico en PDF
	$(PY) main.py reporte

app:           ## abre la interfaz gráfica interactiva
	streamlit run app_streamlit.py
	@echo "Alternativa sin terminal: doble clic en 'Abrir herramienta.command'"

entorno:       ## crea .venv e instala todo (lo mismo que hace el lanzador)
	$(PY) -m venv .venv && ./.venv/bin/python -m pip install -r requirements.txt

todo: pruebas casos reporte  ## todo el flujo completo

limpiar:       ## borra las salidas generadas
	rm -rf salidas __pycache__ */__pycache__ */*/__pycache__ .pytest_cache
