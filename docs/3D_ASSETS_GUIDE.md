# 🎨 Guía de Assets 3D para ZEUS-IA (Sin Unreal Engine)

## 📋 ESTRATEGIA: Three.js + Assets Profesionales Gratis

**Objetivo:** Lograr realismo 7-8/10 sin instalar Unreal Engine (ahorro de 50-100GB)

---

## 🌐 FUENTES DE ASSETS (100% GRATIS)

### 1️⃣ **PERSONAJES (Agentes IA)**

#### **Mixamo by Adobe** ⭐ RECOMENDADO
- **URL:** https://www.mixamo.com
- **Registro:** Gratis (cuenta Adobe)
- **Qué descargar:**
  ```
  PERSONAJES:
  ├── "X Bot" (genérico, bueno para empezar)
  ├── "Y Bot" (femenino alternativo)
  └── Cualquier humanoide que te guste

  ANIMACIONES (para cada personaje):
  ├── Idle (respiración, movimiento sutil)
  ├── Walking (caminar)
  ├── Talking (hablar/gesticular)
  ├── Flying (pose de vuelo Superman)
  └── Idle Floating (flotar en el aire)
  ```

- **Configuración de exportación:**
  ```
  Format: FBX (.fbx)
  Frames per second: 30
  Skin: With Skin (si descargas personaje)
  ```

- **Conversión a GLTF:**
  ```bash
  # Instalar conversor
  npm install -g fbx2gltf
  
  # Convertir
  fbx2gltf-win.exe personaje.fbx
  # Output: personaje.glb
  ```

---

### 2️⃣ **ARQUITECTURA (Olimpo/Templos)**

#### **Sketchfab** ⭐ GRAN BIBLIOTECA
- **URL:** https://sketchfab.com
- **Búsqueda sugerida:**
  ```
  "greek temple" + filter: Downloadable
  "olympus" + filter: CC0 License
  "marble column"
  "ancient greece"
  "pantheon"
  ```

- **Modelos recomendados (buscar por nombre):**
  - "Parthenon" (varios disponibles)
  - "Greek Temple Ruins"
  - "Ionic Column"
  - "Ancient Greek Architecture"

- **Descargar:**
  1. Buscar modelo
  2. Clic en "Download 3D model"
  3. Seleccionar formato: **GLTF** o **FBX**
  4. Bajar a `frontend/public/models/environment/`

#### **Poly Haven** ⭐ TEXTURAS + HDRI
- **URL:** https://polyhaven.com
- **Para ZEUS-IA:**
  ```
  TEXTURAS:
  ├── Marble (búsqueda: "marble")
  ├── Gold (búsqueda: "gold metal")
  ├── Stone (búsqueda: "stone floor")
  └── Cloud textures

  HDRI (iluminación realista):
  ├── "sky" (cielos azules)
  ├── "sunset" (atardecer dorado)
  └── "cloud" (nubes dramáticas)
  ```

- **Descargar:**
  - Formato: **PNG** o **JPG** (texturas)
  - Formato: **HDR** o **EXR** (iluminación)
  - Resolución: 2K (balance calidad/peso)

---

### 3️⃣ **EFECTOS ESPECIALES**

#### **Partículas Doradas (para halos/auras):**
- **Usar:** Texture Packer o crear en Photoshop
- **Alternativa:** Buscar en Sketchfab "particle texture"

#### **God Rays / Rayos Divinos:**
- **Usar:** Three.js VolumetricLight
- **Ejemplo:** https://threejs.org/examples/?q=volumetric#webgl_postprocessing_godrays

---

## 📂 ESTRUCTURA DE CARPETAS

```
frontend/public/models/
├── agents/               # Personajes (agentes IA)
│   ├── zeus.glb
│   ├── perseo.glb
│   ├── rafael.glb
│   ├── thalos.glb
│   ├── justicia.glb
│   └── animations/       # Animaciones separadas (opcional)
│       ├── idle.glb
│       ├── walk.glb
│       └── talk.glb
│
├── environment/          # Arquitectura y escenario
│   ├── temple-main.glb
│   ├── columns.glb
│   ├── floor-marble.glb
│   ├── mountains.glb
│   └── clouds.glb
│
└── effects/              # Partículas y efectos
    ├── particle-gold.png
    ├── halo-texture.png
    └── sky-hdri.hdr
```

---

## 🛠️ PIPELINE DE TRABAJO

### **PASO 1: Descargar Assets**
```bash
# 1. Crear cuenta en Mixamo
# 2. Descargar 1 personaje + 5 animaciones
# 3. Guardar en: C:\Users\Acer\Downloads\mixamo\

# 4. Buscar en Sketchfab "greek temple"
# 5. Descargar formato GLTF
# 6. Guardar en: C:\Users\Acer\Downloads\sketchfab\
```

### **PASO 2: Convertir FBX a GLTF (si es necesario)**
```bash
# Instalar conversor (una vez)
npm install -g fbx2gltf

# Convertir todos los FBX
cd C:\Users\Acer\Downloads\mixamo
fbx2gltf-win.exe zeus-idle.fbx
fbx2gltf-win.exe zeus-walk.fbx
# ... etc
```

### **PASO 3: Optimizar modelos**
```bash
# Instalar optimizador (una vez)
npm install -g gltf-pipeline

# Optimizar (reduce tamaño 40-60%)
gltf-pipeline -i temple.glb -o temple-optimized.glb -d
```

### **PASO 4: Mover a proyecto**
```bash
# Copiar a frontend
cp *.glb C:\Users\Acer\ZEUS-IA\frontend\public\models\agents\
cp *temple*.glb C:\Users\Acer\ZEUS-IA\frontend\public\models\environment\
```

---

## 🎯 ASSETS PRIORITARIOS (Para empezar)

### **FASE 1 - MVP (Mínimo viable):**
```
✅ 1 personaje humanoide (X Bot de Mixamo)
✅ 3 animaciones: idle, walk, talk
✅ 1 templo griego básico (Sketchfab)
✅ 1 textura de mármol (Poly Haven)
✅ 1 HDRI de cielo (Poly Haven)
```

**Tamaño total:** ~50-100MB (manejable)

### **FASE 2 - Completo:**
```
✅ 5 personajes personalizados (Zeus, Perseo, etc.)
✅ 8+ animaciones por personaje
✅ Templo detallado con columnas
✅ Terreno/montañas
✅ Sistema de partículas
✅ Post-processing
```

**Tamaño total:** ~300-500MB (con Git LFS)

---

## 🔗 LINKS RÁPIDOS

| Recurso | URL | Propósito |
|---------|-----|-----------|
| **Mixamo** | https://www.mixamo.com | Personajes + animaciones |
| **Sketchfab** | https://sketchfab.com | Modelos 3D (templos) |
| **Poly Haven** | https://polyhaven.com | Texturas + HDRI |
| **FBX to GLTF** | https://github.com/facebookincubator/FBX2glTF | Conversor |
| **GLTF Viewer** | https://gltf-viewer.donmccurdy.com | Preview online |
| **Three.js Examples** | https://threejs.org/examples | Inspiración + código |

---

## ⚡ COMANDOS ÚTILES

```bash
# Ver info de modelo GLTF
npx gltfjsx model.glb

# Comprimir textura PNG
npx pngquant image.png --output image-compressed.png

# Convertir HDR a JPG (si es muy pesado)
npx sharp-cli input.hdr -o output.jpg
```

---

## 📊 COMPARACIÓN: Con vs Sin Unreal Engine

| Aspecto | Con Unreal | Sin Unreal (Esta guía) |
|---------|-----------|------------------------|
| **Espacio disco** | 50-100GB | 0GB |
| **Tiempo setup** | 2-4 horas | 15 min |
| **Realismo** | 10/10 | 7-8/10 |
| **Complejidad** | Alta | Media |
| **Costo servidor** | $50-200/mes | $0 (Railway gratis) |
| **Performance web** | Requiere streaming | Nativo |

---

## 🎬 SIGUIENTE PASO

**Cuando tengas los primeros assets descargados:**

1. Avísame y actualizo `OlympoFirstPerson.vue`
2. Implemento GLTFLoader
3. Configuro animaciones
4. Deploy a Railway

**Objetivo:** Ver tu primer agente 3D caminando en el Olimpo en ~1 hora.

---

## 💡 TIPS DEVOPS

### **Git LFS ya configurado ✅**
```bash
# Verificar
git lfs track
# Output: *.glb, *.gltf, *.fbx, *.hdr, *.exr
```

### **No commitear assets innecesarios:**
```bash
# .gitignore ya tiene:
*.fbx.meta
*.blend1
*.obj
```

### **Límites de GitHub:**
- Archivo max: 100MB
- Repo max con LFS: 1GB (gratis)
- Si pasas: usar Git LFS bandwidth ($5/50GB)

**Para ZEUS-IA:** Con assets optimizados, estarás ~200-300MB ✅

---

**¡LISTO PARA DESCARGAR TU PRIMER MODELO!** 🚀

