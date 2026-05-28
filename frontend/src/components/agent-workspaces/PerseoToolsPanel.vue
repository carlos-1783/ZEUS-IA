<template>
  <section class="tools-panel">
    <header>
      <h4>🛠️ Herramientas en vivo</h4>
      <p>Ejecuta análisis instantáneos sin salir del workspace.</p>
    </header>
    <div class="tools-grid">
      <div class="tool-card">
        <h5>Analizador de imagen</h5>
        <input v-model="imageForm.image_url" placeholder="URL de la imagen" />
        <input v-model="imageForm.goals" placeholder="Objetivos (coma)" />
        <input v-model="imageForm.tags" placeholder="Tags visuales" />
        <button :disabled="loading.image" @click="runImageAnalyzer">
          {{ loading.image ? 'Analizando…' : 'Analizar' }}
        </button>
        <p v-if="imageResult" class="tool-text">{{ imageResult }}</p>
      </div>

      <div class="tool-card">
        <h5>Mejora de vídeo</h5>
        <label>Duración (s)</label>
        <input type="number" v-model.number="videoForm.duration_seconds" />
        <label>Tono</label>
        <input v-model="videoForm.tone" />
        <label>Plataforma</label>
        <input v-model="videoForm.platform" />
        <button :disabled="loading.video" @click="runVideoEnhancer">
          {{ loading.video ? 'Calculando…' : 'Recomendar' }}
        </button>
        <p v-if="videoResult" class="tool-text">{{ videoResult }}</p>
      </div>

      <div class="tool-card">
        <h5>Auditoría SEO</h5>
        <input v-model="seoForm.url" placeholder="https://sitio.com" />
        <input v-model="seoForm.keywords" placeholder="keywords separadas por coma" />
        <textarea v-model="seoForm.html_snapshot" placeholder="HTML opcional"></textarea>
        <button :disabled="loading.seo" @click="runSeoAudit">
          {{ loading.seo ? 'Auditando…' : 'Auditar' }}
        </button>
        <p v-if="seoResult" class="tool-text">{{ seoResult }}</p>
      </div>

      <div class="tool-card">
        <h5>Blueprint Ads</h5>
        <input v-model="adsForm.product" placeholder="Producto" />
        <input type="number" v-model.number="adsForm.budget" placeholder="Presupuesto" />
        <input v-model="adsForm.audience" placeholder="Audiencia" />
        <select v-model="adsForm.objective">
          <option value="leads">Leads</option>
          <option value="ventas">Ventas</option>
          <option value="branding">Branding</option>
        </select>
        <button :disabled="loading.ads" @click="runAdsBuilder">
          {{ loading.ads ? 'Generando…' : 'Generar plan' }}
        </button>
        <p v-if="adsResult" class="tool-text">{{ adsResult }}</p>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { workspaceTools } from '@/api/workspaceTools'

const loading = reactive({ image: false, video: false, seo: false, ads: false })
const error = ref('')

const imageForm = reactive({ image_url: '', goals: '', tags: '' })
const videoForm = reactive({ duration_seconds: 45, tone: 'energético', platform: 'meta' })
const seoForm = reactive({ url: '', keywords: '', html_snapshot: '' })
const adsForm = reactive({ product: 'ZEUS IA', budget: 1000, audience: 'general', objective: 'leads' })

const imageResult = ref<string | null>(null)
const videoResult = ref<string | null>(null)
const seoResult = ref<string | null>(null)
const adsResult = ref<string | null>(null)

const parseCsv = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

const runImageAnalyzer = async () => {
  error.value = ''
  loading.image = true
  try {
    const out = await workspaceTools.runPerseoImageAnalyzer({
      image_url: imageForm.image_url || undefined,
      goals: parseCsv(imageForm.goals),
      tags: parseCsv(imageForm.tags),
    })
    imageResult.value = String((out as any)?.text || 'Análisis completado.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.image = false
  }
}

const runVideoEnhancer = async () => {
  error.value = ''
  loading.video = true
  try {
    const out = await workspaceTools.runPerseoVideoEnhancer({ ...videoForm })
    videoResult.value = String((out as any)?.text || 'Recomendación de vídeo generada.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.video = false
  }
}

const runSeoAudit = async () => {
  error.value = ''
  loading.seo = true
  try {
    const out = await workspaceTools.runPerseoSeoAudit({
      url: seoForm.url || undefined,
      keywords: parseCsv(seoForm.keywords),
      html_snapshot: seoForm.html_snapshot || undefined,
    })
    seoResult.value = String((out as any)?.text || 'Auditoría SEO completada.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.seo = false
  }
}

const runAdsBuilder = async () => {
  error.value = ''
  loading.ads = true
  try {
    const out = await workspaceTools.runPerseoAdsBuilder({ ...adsForm })
    adsResult.value = String((out as any)?.text || 'Plan de anuncios generado.')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.ads = false
  }
}
</script>

<style scoped>
.tools-panel {
  margin-top: 28px;
  padding: 24px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

.tools-panel header {
  margin-bottom: 18px;
}

.tools-panel h4 {
  margin: 0 0 4px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 18px;
}

.tool-card {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-card input,
.tool-card textarea,
.tool-card select {
  border: 1px solid rgba(148, 163, 184, 0.5);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
}

.tool-card textarea {
  min-height: 80px;
}

.tool-card button {
  margin-top: 6px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  padding: 8px 12px;
  cursor: pointer;
}

.tool-text {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: 10px;
  background: #eff6ff;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.4;
}

.tool-error {
  margin-top: 12px;
  color: #dc2626;
}
</style>

