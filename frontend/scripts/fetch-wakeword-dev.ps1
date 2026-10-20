# Descarga los modelos de openWakeWord v0.5.1 SOLO PARA PRUEBAS INTERNAS de la palabra de activacion.
#
# LICENCIA: el codigo de openWakeWord es Apache-2.0, pero sus modelos preentrenados se publican bajo
# CC BY-NC-SA 4.0 (uso NO comercial). Por eso NO se versionan en el repo: se descargan aqui, en
# frontend/public/openwakeword/local/ (ignorada por git), y solo para probar en local.
# Produccion necesita un modelo de palabra propio («Zeus») con licencia comercial, y
# melspectrogram/embedding con licencia confirmada. Ver frontend/public/openwakeword/README.md.
#
# Uso (desde cualquier carpeta):
#   powershell -ExecutionPolicy Bypass -File frontend/scripts/fetch-wakeword-dev.ps1
# Despues, en frontend/.env.local:
#   VITE_WAKEWORD_MODEL_PATH=/openwakeword/local/hey_jarvis_v0.1.onnx
#   VITE_WAKEWORD_LABEL=Hey Jarvis

$ErrorActionPreference = 'Stop'
$release = 'https://github.com/dscripka/openWakeWord/releases/download/v0.5.1'
$files = @('melspectrogram.onnx', 'embedding_model.onnx', 'hey_jarvis_v0.1.onnx')
$dest = Join-Path (Split-Path -Parent $PSScriptRoot) 'public/openwakeword/local'

New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($f in $files) {
  $out = Join-Path $dest $f
  if (Test-Path $out) { Write-Host "Ya existe: $f"; continue }
  Write-Host "Descargando $f ..."
  Invoke-WebRequest -Uri "$release/$f" -OutFile $out -UseBasicParsing
}
Write-Host "Modelos de prueba en $dest (uso NO comercial, no se versionan)."
