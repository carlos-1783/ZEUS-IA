<template>
  <section class="marketing-integrations">
    <header>
      <h4>Integraciones de marketing</h4>
      <p>Conecta redes, ads y permisos de automatización para PERSEO.</p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="success">Integraciones guardadas correctamente.</p>

    <div v-if="loading" class="muted">Cargando integraciones…</div>

    <template v-else>
      <fieldset class="block">
        <legend>Redes sociales</legend>
        <div v-for="(row, key) in socialPlatforms" :key="key" class="platform-row">
          <label class="connect">
            <input v-model="row.connected" type="checkbox" />
            {{ platformLabel(key) }}
          </label>
          <input
            v-model="row[socialField(key)]"
            :placeholder="socialPlaceholder(key)"
            :disabled="!row.connected"
          />
        </div>
      </fieldset>

      <fieldset class="block">
        <legend>Publicidad (Ads)</legend>
        <div v-for="(row, key) in adsPlatforms" :key="key" class="platform-row">
          <label class="connect">
            <input v-model="row.connected" type="checkbox" />
            {{ platformLabel(key) }}
          </label>
          <input
            v-model="row.account_id"
            placeholder="ID de cuenta publicitaria"
            :disabled="!row.connected"
          />
          <label class="inline-check">
            <input v-model="row.track_metrics" type="checkbox" :disabled="!row.connected" />
            Seguir métricas
          </label>
        </div>
      </fieldset>

      <fieldset class="block">
        <legend>Permisos de automatización</legend>
        <label><input v-model="permissions.allow_auto_post" type="checkbox" /> Publicación automática</label>
        <label><input v-model="permissions.allow_auto_ads_analysis" type="checkbox" /> Análisis automático de ads</label>
        <label><input v-model="permissions.allow_auto_messages" type="checkbox" /> Mensajes automáticos</label>
      </fieldset>

      <div v-if="metrics" class="metrics-box">
        <h5>Métricas recogidas</h5>
        <ul>
          <li v-for="m in metricsCollected" :key="m">{{ metricLabel(m) }}</li>
        </ul>
        <p v-if="metrics.enabled" class="muted">
          Gasto: {{ metrics.metrics?.ad_spend ?? 0 }} € · Leads: {{ metrics.metrics?.leads_generated ?? 0 }}
        </p>
      </div>

      <div class="actions">
        <button type="button" class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Guardando…' : 'Guardar integraciones' }}
        </button>
        <button type="button" class="btn-secondary" :disabled="loading" @click="load">Actualizar</button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import api from '@/services/api'

type PlatformRow = Record<string, string | boolean>

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref(false)
const metricsCollected = ref<string[]>([])
const metrics = ref<any>(null)

const socialPlatforms = reactive<Record<string, PlatformRow>>({})
const adsPlatforms = reactive<Record<string, PlatformRow>>({})
const permissions = reactive({
  allow_auto_post: false,
  allow_auto_ads_analysis: true,
  allow_auto_messages: false,
})

const SOCIAL_FIELDS: Record<string, string> = {
  instagram: 'username',
  facebook: 'page_id',
  whatsapp_business: 'phone_number',
  google_business: 'location_id',
  email_marketing: 'email',
}

function platformLabel(key: string) {
  const labels: Record<string, string> = {
    instagram: 'Instagram',
    facebook: 'Facebook',
    whatsapp_business: 'WhatsApp Business',
    google_business: 'Google Business',
    email_marketing: 'Email marketing',
    meta_ads: 'Meta Ads',
    google_ads: 'Google Ads',
  }
  return labels[key] || key
}

function socialField(key: string) {
  return SOCIAL_FIELDS[key] || 'username'
}

function socialPlaceholder(key: string) {
  const map: Record<string, string> = {
    instagram: '@usuario',
    facebook: 'ID de página',
    whatsapp_business: '+34…',
    google_business: 'ID ubicación',
    email_marketing: 'email@empresa.com',
  }
  return map[key] || ''
}

function metricLabel(m: string) {
  const map: Record<string, string> = {
    ad_spend: 'Gasto en publicidad',
    leads_generated: 'Leads generados',
    cost_per_lead: 'Coste por lead',
    engagement: 'Engagement',
  }
  return map[m] || m
}

function assignPlatforms(target: Record<string, PlatformRow>, source: Record<string, any>, defaults: Record<string, any>) {
  for (const k of Object.keys(defaults)) {
    target[k] = { ...defaults[k], ...(source[k] || {}) }
  }
}

async function load() {
  loading.value = true
  error.value = ''
  saved.value = false
  try {
    const res = await api.get('/api/v1/marketing/integrations')
    const data = res?.data ?? res
    assignPlatforms(
      socialPlatforms,
      data.social_platforms || {},
      {
        instagram: { username: '', connected: false },
        facebook: { page_id: '', connected: false },
        whatsapp_business: { phone_number: '', connected: false },
        google_business: { location_id: '', connected: false },
        email_marketing: { email: '', connected: false },
      },
    )
    assignPlatforms(
      adsPlatforms,
      data.ads_platforms || {},
      {
        meta_ads: { account_id: '', connected: false, track_metrics: true },
        google_ads: { account_id: '', connected: false, track_metrics: true },
      },
    )
    Object.assign(permissions, data.permissions || {})
    metricsCollected.value = data.metrics_collected || []
    const met = await api.get('/api/v1/marketing/integrations/metrics')
    metrics.value = met?.data ?? met
  } catch (e: any) {
    error.value = e?.message || 'No se pudieron cargar las integraciones.'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const body = {
      social_platforms: JSON.parse(JSON.stringify(socialPlatforms)),
      ads_platforms: JSON.parse(JSON.stringify(adsPlatforms)),
      permissions: { ...permissions },
    }
    await api.put('/api/v1/marketing/integrations', body)
    saved.value = true
    await load()
  } catch (e: any) {
    error.value = e?.message || 'Error al guardar integraciones.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.marketing-integrations {
  margin-top: 24px;
  padding: 20px;
  border: 1px solid rgba(236, 72, 153, 0.35);
  border-radius: 16px;
  background: #fff;
}
.block {
  border: none;
  margin: 16px 0;
  padding: 0;
}
.platform-row {
  display: grid;
  grid-template-columns: 140px 1fr auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.connect {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.platform-row input[type='text'],
.platform-row input:not([type='checkbox']) {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px;
}
.inline-check {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.btn-primary {
  background: #db2777;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
}
.btn-secondary {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
}
.error {
  color: #b91c1c;
}
.success {
  color: #047857;
}
.muted {
  color: #64748b;
  font-size: 14px;
}
.metrics-box {
  background: #fdf2f8;
  border-radius: 10px;
  padding: 12px;
  margin-top: 12px;
}
</style>
