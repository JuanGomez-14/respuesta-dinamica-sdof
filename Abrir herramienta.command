#!/bin/bash
# ============================================================================
#  Abre la plataforma de cálculo de respuesta dinámica.
#  Doble clic en este archivo: no hay que escribir nada en la terminal.
#  La primera vez tarda un par de minutos instalando lo necesario.
# ============================================================================
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo " Laboratorio de Respuesta Dinámica — Universidad de Medellín"
echo "============================================================"
echo

PY=""
for cand in python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "  No se encontró Python 3.10 o superior en este computador."
  echo
  echo "  Descárguelo (gratis) desde:   https://www.python.org/downloads/"
  echo "  Durante la instalación deje marcadas todas las opciones por defecto,"
  echo "  y luego vuelva a dar doble clic en este archivo."
  echo
  read -r -p "  Presione Enter para cerrar..."
  exit 1
fi

echo "  Python encontrado: $($PY -V)"

if [ ! -d ".venv" ]; then
  echo "  Primera vez: preparando el entorno (tarda 1-2 minutos)..."
  "$PY" -m venv .venv || { echo "  No se pudo crear el entorno."; read -r -p "  Enter para cerrar..."; exit 1; }
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt || {
    echo "  Falló la instalación de dependencias. ¿Hay conexión a internet?"
    read -r -p "  Enter para cerrar..."; exit 1; }
  echo "  Entorno listo."
else
  ./.venv/bin/python -c "import streamlit" 2>/dev/null || {
    echo "  Faltan dependencias; instalando..."
    ./.venv/bin/python -m pip install --quiet -r requirements.txt; }
fi

echo
echo "  Abriendo la herramienta en el navegador..."
echo "  Para cerrarla: vuelva a esta ventana y presione Ctrl+C."
echo

# Streamlit corre en modo headless (ver .streamlit/config.toml) para que no
# pregunte por un correo en el primer arranque; por eso el navegador lo abrimos
# nosotros, en cuanto el servidor esté escuchando.
(
  for _ in $(seq 1 60); do
    if curl -s -o /dev/null "http://localhost:8501"; then break; fi
    sleep 1
  done
  open "http://localhost:8501"
) &

exec ./.venv/bin/python -m streamlit run app_streamlit.py --server.headless=true
