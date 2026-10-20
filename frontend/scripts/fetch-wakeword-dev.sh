#!/usr/bin/env sh
# Descarga los modelos de openWakeWord v0.5.1 SOLO PARA PRUEBAS INTERNAS de la palabra de activacion.
#
# LICENCIA: el codigo de openWakeWord es Apache-2.0, pero sus modelos preentrenados se publican bajo
# CC BY-NC-SA 4.0 (uso NO comercial). Por eso NO se versionan en el repo: se descargan aqui, en
# frontend/public/openwakeword/local/ (ignorada por git), y solo para probar en local.
# Produccion necesita un modelo de palabra propio («Zeus») con licencia comercial, y
# melspectrogram/embedding con licencia confirmada. Ver frontend/public/openwakeword/README.md.
#
# Uso:  sh frontend/scripts/fetch-wakeword-dev.sh
# Despues, en frontend/.env.local:
#   VITE_WAKEWORD_MODEL_PATH=/openwakeword/local/hey_jarvis_v0.1.onnx
#   VITE_WAKEWORD_LABEL=Hey Jarvis
set -eu
RELEASE="https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
DEST="$(cd "$(dirname "$0")/.." && pwd)/public/openwakeword/local"
mkdir -p "$DEST"
for f in melspectrogram.onnx embedding_model.onnx hey_jarvis_v0.1.onnx; do
  if [ -f "$DEST/$f" ]; then echo "Ya existe: $f"; continue; fi
  echo "Descargando $f ..."
  curl -fsSL "$RELEASE/$f" -o "$DEST/$f"
done
echo "Modelos de prueba en $DEST (uso NO comercial, no se versionan)."
