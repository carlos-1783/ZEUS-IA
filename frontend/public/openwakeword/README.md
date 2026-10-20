# Modelos de openWakeWord (palabra de activación del orbe)

El motor (`src/utils/openWakeWord.ts`) es una adaptación a TypeScript del pipeline de
[openWakeWord](https://github.com/dscripka/openWakeWord) (código Apache-2.0) sobre
`onnxruntime-web` (MIT). Necesita tres modelos ONNX, de release v0.5.1:

| Archivo | Origen | Licencia | ¿En el repo? |
|---|---|---|---|
| `melspectrogram.onnx` | openWakeWord v0.5.1 (implementación ONNX del melspectrograma de torchaudio, parámetros fijos) | El README de openWakeWord declara **todos** los modelos preentrenados incluidos como CC BY-NC-SA 4.0 | **No** |
| `embedding_model.onnx` | openWakeWord v0.5.1 (reimplementación del `speech_embedding` de Google, publicado por Google en TF Hub como Apache-2.0) | Origen Apache-2.0, pero el archivo distribuido por openWakeWord cae bajo la misma declaración CC BY-NC-SA 4.0 | **No** |
| `hey_jarvis_v0.1.onnx` | openWakeWord v0.5.1 (modelo de palabra preentrenado) | CC BY-NC-SA 4.0 (no comercial) | **No** |

Lo único versionado en esta carpeta es `capture-worklet.js` (código propio de ZEUS: AudioWorklet que
captura el micro; está en `public/` porque Vite 4 lo incrustaría como `data:` URL y la CSP lo bloquea).
El `.wasm` de onnxruntime-web (MIT) lo empaqueta Vite desde `node_modules` y se sirve en local, sin CDN.

Por qué no se versiona ningún modelo: el apartado *License* del README de openWakeWord dice
«All of the included pre-trained models are licensed under CC BY-NC-SA 4.0». Los dos modelos
comunes tienen un origen permisivo (transformación sin entrenamiento / Google Apache-2.0), pero no se
puede confirmar que los archivos `.onnx` publicados por openWakeWord queden fuera de esa declaración.
Hasta confirmarlo (o regenerarlos nosotros a partir del original de Google), se tratan igual que el
modelo de palabra.

## Pruebas internas

`scripts/fetch-wakeword-dev.ps1` (o `.sh`) descarga los tres a `public/openwakeword/local/`
(ignorada por git). Luego, en `frontend/.env.local`:

```
VITE_WAKEWORD_MODEL_PATH=/openwakeword/local/hey_jarvis_v0.1.onnx
VITE_WAKEWORD_LABEL=Hey Jarvis
```

Esa carpeta solo se sirve con `vite dev`: ningún `vite build` la publica (el plugin
`zeus-exclude-local-wakeword-models` de `vite.config.ts` la borra de `dist/`), `.gitignore` la deja
fuera del repo y `.dockerignore` fuera de cualquier imagen Docker.

## Producción

Hace falta un modelo de palabra propio («Zeus») entrenado con datos de licencia comercial, y los
modelos comunes con licencia confirmada. Se configuran con `VITE_WAKEWORD_MODEL_PATH`,
`VITE_WAKEWORD_LABEL`, `VITE_WAKEWORD_THRESHOLD` y, si no están junto al modelo,
`VITE_WAKEWORD_MELSPECTROGRAM_PATH` / `VITE_WAKEWORD_EMBEDDING_PATH`.
Sin `VITE_WAKEWORD_MODEL_PATH` el orbe funciona igual, sin escucha en espera.
