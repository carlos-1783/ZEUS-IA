<template>
  <section class="tools-panel">
    <header>
      <div class="header-row">
        <div>
          <h4>🛠️ Herramientas PERSEO</h4>
          <p class="sim-note">{{ statusNote }}</p>
        </div>
        <ThalosExecutionBadge
          :global-mode="globalMode"
          :real-execution="globalMode === 'REAL'"
          :inline="true"
        />
      </div>
    </header>

    <div class="tools-grid">
      <div class="tool-card" :class="{ real: featureStatus('video_editing') === 'REAL' }">
        <div class="card-title-row">
          <h5>Edición de vídeo (FFmpeg)</h5>
          <ThalosExecutionBadge
            :module-badge="perseoFeatureBadge(featureStatus('video_editing'))"
            :inline="true"
            :show-global="false"
          />
        </div>
        <input v-model="videoEditForm.input_url" placeholder="/static/uploads/videos/..." />
        <label>Inicio (s)</label>
        <input type="number" v-model.number="videoEditForm.start_sec" min="0" />
        <label>Fin (s, opcional)</label>
        <input type="number" v-model.number="videoEditForm.end_sec" min="0" />
        <button :disabled="loading.videoEdit || featureStatus('video_editing') !== 'REAL'" @click="runVideoEdit">
          {{ loading.videoEdit ? `Procesando ${videoJobProgress}%…` : 'Editar vídeo' }}
        </button>
        <p v-if="videoEditError" class="tool-error-inline">{{ videoEditError }}</p>
        <a v-if="videoEditUrl" :href="videoEditUrl" target="_blank" rel="noopener" class="video-link">
          Ver vídeo editado
        </a>
      </div>

      <div class="tool-card" :class="{ real: featureStatus('image_analyzer') === 'REAL' }">
        <div class="card-title-row">
          <h5>Analizador de imagen</h5>
          <ThalosExecutionBadge
            :module-badge="perseoFeatureBadge(featureStatus('image_analyzer'))"
            :inline="true"
            :show-global="false"
          />
        </div>
        <input v-model="imageForm.image_url" placeholder="URL de la imagen" />
        <input v-model="imageForm.goals" placeholder="Objetivos (coma)" />
        <input v-model="imageForm.tags" placeholder="Tags visuales" />
        <button :disabled="loading.image" @click="runImageAnalyzer">
          {{ loading.image ? 'Analizando…' : aiLabel('image_analyzer', 'Analizar imagen') }}
        </button>
        <p v-if="imageResult" class="tool-text">{{ imageResult }}</p>
      </div>

      <div class="tool-card" :class="{ real: featureStatus('video_recommender') === 'REAL' }">
        <div class="card-title-row">
          <h5>Recomendaciones de vídeo</h5>
          <ThalosExecutionBadge
            :module-badge="perseoFeatureBadge(featureStatus('video_recommender'))"
            :inline="true"
            :show-global="false"
          />
        </div>
        <label>Duración (s)</label>
        <input type="number" v-model.number="videoForm.duration_seconds" />
        <label>Tono</label>
        <input v-model="videoForm.tone" />
        <label>Plataforma</label>
        <input v-model="videoForm.platform" />
        <button :disabled="loading.video" @click="runVideoEnhancer">
          {{ loading.video ? 'Calculando…' : aiLabel('video_recommender', 'Generar guion') }}
        </button>
        <p v-if="videoResult" class="tool-text">{{ videoResult }}</p>
      </div>

      <div class="tool-card" :class="{ real: featureStatus('seo_audit') === 'REAL' }">
        <div class="card-title-row">
          <h5>Auditoría SEO</h5>
          <ThalosExecutionBadge
            :module-badge="perseoFeatureBadge(featureStatus('seo_audit'))"
            :inline="true"
            :show-global="false"
          />
        </div>
        <input v-model="seoForm.url" placeholder="https://sitio.com" />
        <input v-model="seoForm.keywords" placeholder="keywords separadas por coma" />
        <textarea v-model="seoForm.html_snapshot" placeholder="HTML opcional"></textarea>
        <button :disabled="loading.seo" @click="runSeoAudit">
          {{ loading.seo ? 'Auditando…' : aiLabel('seo_audit', 'Auditar SEO') }}
        </button>
        <p v-if="seoResult" class="tool-text">{{ seoResult }}</p>
      </div>

      <div class="tool-card" :class="{ real: featureStatus('ads_blueprint') === 'REAL' }">
        <div class="card-title-row">
          <h5>Blueprint Ads</h5>
          <ThalosExecutionBadge
            :module-badge="perseoFeatureBadge(featureStatus('ads_blueprint'))"
            :inline="true"
            :show-global="false"
          />
        </div>
        <input v-model="adsForm.product" placeholder="Producto" />
        <input type="number" v-model.number="adsForm.budget" placeholder="Presupuesto" />
        <input v-model="adsForm.audience" placeholder="Audiencia" />
        <select v-model="adsForm.objective">
          <option value="leads">Leads</option>
          <option value="ventas">Ventas</option>
          <option value="branding">Branding</option>
        </select>
        <button :disabled="loading.ads" @click="runAdsBuilder">
          {{ loading.ads ? 'Generando…' : aiLabel('ads_blueprint', 'Generar plan') }}
        </button>
        <p v-if="adsResult" class="tool-text">{{ adsResult }}</p>
      </div>
    </div>
    <p v-if="error" class="tool-error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  fetchPerseoStatus,
  fetchPerseoV2Status,
  perseoAnalyzeImage,
  perseoFeatureBadge,
  perseoGenerateAds,
  perseoRecommendVideo,
  perseoSeoAudit,
  pollPerseoVideoJob,
  pollPerseoV2Job,
  submitPerseoVideoEdit,
  submitPerseoV2VideoEdit,
  type PerseoFeatureStatus,
} from '@/api/perseo_status_api'
import { workspaceTools } from '@/api/workspaceTools'
import ThalosExecutionBadge from './ThalosExecutionBadge.vue'

const loading = reactive({ image: false, video: false, seo: false, ads: false, videoEdit: false })
const error = ref('')
const globalMode = ref<'REAL' | 'SIMULATED' | 'ERROR'>('SIMULATED')
const featureMap = ref<Record<string, { status: PerseoFeatureStatus }>>({})

const imageForm = reactive({ image_url: '', goals: '', tags: '' })
const videoForm = reactive({ duration_seconds: 45, tone: 'energético', platform: 'meta' })
const videoEditForm = reactive({ input_url: '', start_sec: 0, end_sec: 0 as number | null })
const seoForm = reactive({ url: '', keywords: '', html_snapshot: '' })
const adsForm = reactive({ product: '', budget: 1000, audience: 'general', objective: 'leads' })

const imageResult = ref<string | null>(null)
const videoResult = ref<string | null>(null)
const seoResult = ref<string | null>(null)
const adsResult = ref<string | null>(null)
const videoEditUrl = ref<string | null>(null)
const videoEditError = ref<string | null>(null)
const videoJobProgress = ref(0)
const useV2 = ref(false)

const featureStatus = (key: string): PerseoFeatureStatus =>
  (featureMap.value[key]?.status as PerseoFeatureStatus) || 'SIMULATED'

const statusNote = computed(() => {
  const keys = Object.keys(featureMap.value)
  const real = keys.filter((k) => featureStatus(k) === 'REAL')
  const sim = keys.filter((k) => featureStatus(k) === 'SIMULATED')
  return `REAL: ${real.join(', ') || '—'} · SIMULADO: ${sim.join(', ') || '—'}`
})

const aiLabel = (key: string, realLabel: string) =>
  featureStatus(key) === 'REAL' ? realLabel : `${realLabel} (fallback)`

const formatResult = (data: Record<string, unknown>) => {
  const text = (data.script as string) || (data.summary as string)
  if (text) return text
  const score = data.seo_score ?? data.score
  if (score != null) return `Score: ${score} — ${JSON.stringify(data.improvements || data.issues || data, null, 2)}`
  return JSON.stringify(data, null, 2)
}

const parseCsv = (value: string) =>
  value.split(',').map((item) => item.trim()).filter(Boolean)

onMounted(async () => {
  try {
    const [st, v2] = await Promise.all([
      fetchPerseoStatus(),
      fetchPerseoV2Status().catch(() => null),
    ])
    globalMode.value = (st.execution_mode as typeof globalMode.value) || 'SIMULATED'
    featureMap.value = st.feature_status_map || {}
    if (v2?.perseo_v2_enabled) {
      globalMode.value = (v2.execution_mode as typeof globalMode.value) || globalMode.value
      useV2.value = true
    }
  } catch {
    /* optional */
  }
})

const runVideoEdit = async () => {
  error.value = ''
  videoEditError.value = null
  videoEditUrl.value = null
  loading.videoEdit = true
  videoJobProgress.value = 0
  try {
    const ops: Array<Record<string, unknown>> = [{ type: 'scale', width: 1280, height: 720 }]
    if (videoEditForm.start_sec > 0 || (videoEditForm.end_sec && videoEditForm.end_sec > 0)) {
      ops.unshift({
        type: 'trim',
        start_sec: videoEditForm.start_sec,
        end_sec: videoEditForm.end_sec || undefined,
      })
    }
    const submit = useV2.value ? submitPerseoV2VideoEdit : submitPerseoVideoEdit
    const poll = useV2.value ? pollPerseoV2Job : pollPerseoVideoJob
    const created = await submit({
      input_url: videoEditForm.input_url,
      operations: ops,
    })
    const jobId = created.job_id
    for (let i = 0; i < 120; i++) {
      await new Promise((r) => setTimeout(r, 1000))
      const job = await poll(jobId)
      videoJobProgress.value = job.progress ?? 0
      const url = job.video_url || (job as { output?: { video_url?: string } }).output?.video_url
      if (job.status === 'completed' && url) {
        videoEditUrl.value = url
        return
      }
      if (job.status === 'failed') {
        videoEditError.value = job.error || 'Edición de vídeo fallida'
        return
      }
    }
    videoEditError.value = 'Timeout esperando el job de vídeo'
  } catch (err) {
    videoEditError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.videoEdit = false
  }
}

const runImageAnalyzer = async () => {
  error.value = ''
  loading.image = true
  try {
    const payload = {
      image_url: imageForm.image_url,
      goals: parseCsv(imageForm.goals),
      tags: parseCsv(imageForm.tags),
    }
    const out = useV2.value || featureStatus('image_analyzer') === 'REAL'
      ? await perseoAnalyzeImage(payload)
      : await workspaceTools.runPerseoImageAnalyzer(payload)
    imageResult.value = (out as { text?: string }).text || formatResult(out as Record<string, unknown>)
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
    const payload = { ...videoForm }
    const out = useV2.value || featureStatus('video_recommender') === 'REAL'
      ? await perseoRecommendVideo(payload)
      : await workspaceTools.runPerseoVideoEnhancer(payload)
    videoResult.value = (out as { text?: string }).text || formatResult(out as Record<string, unknown>)
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
    const payload = {
      url: seoForm.url || undefined,
      keywords: parseCsv(seoForm.keywords),
      html_snapshot: seoForm.html_snapshot || undefined,
    }
    const out = useV2.value || featureStatus('seo_audit') === 'REAL'
      ? await perseoSeoAudit(payload)
      : await workspaceTools.runPerseoSeoAudit(payload)
    seoResult.value = (out as { text?: string }).text || formatResult(out as Record<string, unknown>)
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
    const payload = { ...adsForm }
    const out = useV2.value || featureStatus('ads_blueprint') === 'REAL'
      ? await perseoGenerateAds(payload)
      : await workspaceTools.runPerseoAdsBuilder(payload)
    adsResult.value = (out as { text?: string }).text || formatResult(out as Record<string, unknown>)
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

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.sim-note {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
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

.tool-card.real {
  border-color: rgba(16, 185, 129, 0.45);
  background: rgba(16, 185, 129, 0.04);
}

.tool-card.legacy {
  opacity: 0.95;
  background: #fafafa;
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
  background: #64748b;
  color: #fff;
  padding: 8px 12px;
  cursor: pointer;
}

.tool-card.real button {
  background: #059669;
}

.tool-card button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.tool-text {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: 10px;
  background: #f1f5f9;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.4;
}

.tool-error,
.tool-error-inline {
  margin-top: 8px;
  color: #dc2626;
  font-size: 13px;
}

.video-link {
  color: #059669;
  font-weight: 600;
  font-size: 13px;
}
</style>
