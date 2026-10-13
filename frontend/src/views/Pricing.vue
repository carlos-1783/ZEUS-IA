<template>
  <div class="pricing-page">
    <!-- Hero Section -->
    <section class="hero">
      <div class="hero-content">
        <h1 class="hero-title">
          <span class="gradient-text">Automatiza tu empresa</span> con IA
        </h1>
        <p class="hero-subtitle">
          6 Agentes especializados trabajando 24/7 para tu negocio
        </p>
        
        <!-- Value Proposition -->
        <div class="value-prop">
          <div class="value-badge">🥉 3ª más económica del mercado</div>
          <div class="value-badge main">🏆 #1 en funcionalidades completas</div>
          <div class="value-badge">✅ Todo incluido sin sorpresas</div>
        </div>

        <div class="hero-stats">
          <div class="stat">
            <div class="stat-value">6</div>
            <div class="stat-label">Agentes IA</div>
          </div>
          <div class="stat">
            <div class="stat-value">24/7</div>
            <div class="stat-label">Disponibilidad</div>
          </div>
          <div class="stat">
            <div class="stat-value">100%</div>
            <div class="stat-label">Automatización</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Comparison Section -->
    <section class="comparison-section">
      <div class="container">
        <h2 class="section-title">¿Por qué ZEUS-IA?</h2>
        <p class="section-subtitle">Comparamos para que tú no tengas que hacerlo</p>
        
        <div class="comparison-grid">
          <div class="comparison-card">
            <div class="comparison-rank">🥇</div>
            <h3>Competidor A</h3>
            <div class="comparison-price">€2,500/mes</div>
            <ul class="comparison-features">
              <li>❌ Solo contabilidad</li>
              <li>❌ No incluye marketing</li>
              <li>❌ Sin RRHH ni logística</li>
            </ul>
          </div>

          <div class="comparison-card">
            <div class="comparison-rank">🥈</div>
            <h3>Competidor B</h3>
            <div class="comparison-price">€1,800/mes</div>
            <ul class="comparison-features">
              <li>✅ CRM + Marketing</li>
              <li>❌ Sin fiscal ni legal</li>
              <li>❌ No automatiza RRHH</li>
            </ul>
          </div>

          <div class="comparison-card winner">
            <div class="winner-badge">🏆 GANADOR</div>
            <div class="comparison-rank">🥉</div>
            <h3>ZEUS-IA (tú)</h3>
            <div class="comparison-price">€497/mes</div>
            <ul class="comparison-features">
              <li>✅ Marketing + Fiscal + Legal</li>
              <li>✅ RRHH + Logística completa</li>
              <li>✅ Seguridad + Compliance</li>
              <li class="highlight">🚀 Todo por 3.6x menos</li>
              <li class="highlight">💡 No pagas hasta que funcione</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- Pricing Section -->
    <section class="pricing-section">
      <div class="container">
        <h2 class="section-title">Elige el plan perfecto para tu empresa</h2>
        <p class="section-subtitle">
          Todos los planes incluyen los 6 agentes IA + todas las funcionalidades
        </p>

        <!-- Plans Grid -->
        <div class="plans-grid">
          <!-- ZEUS STARTUP -->
          <div class="plan-card">
            <div class="plan-badge">🏃 Ideal para autónomos</div>
            <h3 class="plan-name">ZEUS STARTUP</h3>
            <p class="plan-description">1-5 empleados</p>
            
            <div class="hybrid-badge">
              💡 Solo pagas €197 para empezar. El resto cuando ZEUS funcione al 100%
            </div>
            
            <div class="plan-pricing">
              <div class="price-item">
                <span class="price-label">Hoy pagas</span>
                <span class="price">€197</span>
                <span class="price-note">para empezar</span>
              </div>
              <div class="price-divider">→</div>
              <div class="price-item">
                <span class="price-label">Mensual</span>
                <span class="price">€197</span>
                <span class="price-note">/mes (desde mes 2)</span>
              </div>
            </div>
            
            <div class="price-breakdown">
              <small>💰 Setup total: €197 (pagas solo cuando ZEUS funcione al 100%)</small>
            </div>

            <ul class="features-list">
              <li>✅ Automatización con 6 agentes</li>
              <li>✅ WhatsApp + Email automation</li>
              <li>✅ Modelos fiscales básicos vía RAFAEL (preparación, draft only)</li>
              <li>✅ RRHH y logística esencial vía AFRODITA</li>
              <li>✅ Stripe Payments</li>
              <li>✅ Soporte por email</li>
              <li>✅ Capacidad recomendada: volumen bajo-medio</li>
              <li>✅ Velocidad estándar</li>
            </ul>

            <button class="btn-primary" @click="selectPlan('startup')">
              Empezar ahora
            </button>
          </div>

          <!-- ZEUS GROWTH (MOST POPULAR) -->
          <div class="plan-card popular">
            <div class="popular-badge">⭐ MÁS POPULAR</div>
            <div class="plan-badge">🏢 Para PYMEs</div>
            <h3 class="plan-name">ZEUS GROWTH</h3>
            <p class="plan-description">6-25 empleados</p>
            
            <div class="hybrid-badge">
              💡 Solo pagas €497 para empezar. El resto cuando ZEUS funcione al 100%
            </div>
            
            <div class="plan-pricing">
              <div class="price-item">
                <span class="price-label">Hoy pagas</span>
                <span class="price">€497</span>
                <span class="price-note">para empezar</span>
              </div>
              <div class="price-divider">→</div>
              <div class="price-item">
                <span class="price-label">Mensual</span>
                <span class="price">€497</span>
                <span class="price-note">/mes (desde mes 2)</span>
              </div>
            </div>
            
            <div class="price-breakdown">
              <small>💰 Setup total: €497 (pagas solo cuando ZEUS funcione al 100%)</small>
            </div>

            <ul class="features-list">
              <li>✅ Todo STARTUP</li>
              <li>✅ Google Workspace Integration</li>
              <li>✅ Marketing Ads (Google Ads + Meta Ads)</li>
              <li>✅ Analytics avanzado</li>
              <li>✅ Onboarding personalizado</li>
              <li>✅ Soporte prioritario</li>
              <li>✅ Capacidad recomendada: volumen medio</li>
              <li>✅ Velocidad rápida</li>
            </ul>

            <button class="btn-primary pulse" @click="selectPlan('growth')">
              Empezar ahora
            </button>
          </div>

          <!-- ZEUS BUSINESS -->
          <div class="plan-card">
            <div class="plan-badge">🏛️ Empresas</div>
            <h3 class="plan-name">ZEUS BUSINESS</h3>
            <p class="plan-description">26-100 empleados</p>
            
            <div class="hybrid-badge">
              💡 Solo pagas €897 para empezar. El resto cuando ZEUS funcione al 100%
            </div>
            
            <div class="plan-pricing">
              <div class="price-item">
                <span class="price-label">Hoy pagas</span>
                <span class="price">€897</span>
                <span class="price-note">para empezar</span>
              </div>
              <div class="price-divider">→</div>
              <div class="price-item">
                <span class="price-label">Mensual</span>
                <span class="price">€897</span>
                <span class="price-note">/mes (desde mes 2)</span>
              </div>
            </div>
            
            <div class="price-breakdown">
              <small>💰 Setup total: €897 (pagas solo cuando ZEUS funcione al 100%)</small>
            </div>

            <ul class="features-list">
              <li>✅ Todo GROWTH</li>
              <li>✅ Integraciones personalizadas</li>
              <li>✅ API access completo</li>
              <li>✅ Múltiples administradores</li>
              <li>✅ Account Manager dedicado</li>
              <li>✅ Soporte 24/7</li>
              <li>✅ SLA garantizado</li>
              <li>✅ Capacidad recomendada: volumen alto</li>
              <li>✅ Velocidad en tiempo real</li>
            </ul>

            <button class="btn-primary" @click="selectPlan('business')">
              Empezar ahora
            </button>
          </div>

          <!-- ZEUS ENTERPRISE -->
          <div class="plan-card enterprise">
            <div class="plan-badge">⚡ Corporativo</div>
            <h3 class="plan-name">ZEUS ENTERPRISE</h3>
            <p class="plan-description">101+ empleados</p>
            
            <div class="hybrid-badge">
              💡 Solo pagas €1,797 para empezar. El resto cuando ZEUS funcione al 100%
            </div>
            
            <div class="plan-pricing">
              <div class="price-item">
                <span class="price-label">Hoy pagas</span>
                <span class="price">€1,797</span>
                <span class="price-note">para empezar</span>
              </div>
              <div class="price-divider">→</div>
              <div class="price-item">
                <span class="price-label">Mensual</span>
                <span class="price">€1,797</span>
                <span class="price-note">/mes (desde mes 2)</span>
              </div>
            </div>
            
            <div class="price-breakdown">
              <small>💰 Setup total: €1,797 (pagas solo cuando ZEUS funcione al 100%)</small>
            </div>

            <ul class="features-list">
              <li>✅ Todo BUSINESS</li>
              <li>✅ White-label</li>
              <li>✅ Instalación on-premise opcional</li>
              <li>✅ Integraciones SAP/Oracle</li>
              <li>✅ Auditorías + Compliance avanzados</li>
              <li>✅ Training presencial</li>
              <li>✅ Contrato enterprise SLA 99.9%</li>
              <li>✅ Soporte técnico dedicado</li>
              <li>✅ Capacidad máxima</li>
              <li>✅ Velocidad ilimitada en tiempo real</li>
            </ul>

            <button class="btn-secondary" @click="contactSales">
              Contactar ventas
            </button>
          </div>
        </div>

        <!-- Trust Badges -->
        <div class="trust-section">
          <p class="trust-text">✅ Sin permanencia • ✅ Cancela cuando quieras • ✅ Datos seguros</p>
        </div>
      </div>
    </section>

    <!-- Features Section -->
    <section class="features-section">
      <div class="container">
        <h2 class="section-title">¿Qué incluye ZEUS-IA?</h2>
        
        <!-- Agents Grid -->
        <div class="agents-showcase">
          <h3 class="agents-title">Los 6 Agentes de ZEUS-IA</h3>
          <div class="agents-grid">
            <div class="agent-card">
              <div class="agent-avatar">
                <img :src="zeusAvatar" alt="ZEUS CORE" />
              </div>
              <h4>ZEUS CORE</h4>
              <p>Orquestador supremo que coordina todo el sistema</p>
            </div>
            <div class="agent-card">
              <div class="agent-avatar">
                <img :src="perseoAvatar" alt="PERSEO" />
              </div>
              <h4>PERSEO</h4>
              <p>Marketing, SEO, SEM y optimización de ventas</p>
            </div>
            <div class="agent-card">
              <div class="agent-avatar">
                <img :src="rafaelAvatar" alt="RAFAEL" />
              </div>
              <h4>RAFAEL</h4>
              <p>Fiscal, contabilidad y gestión con Hacienda</p>
            </div>
            <div class="agent-card">
              <div class="agent-avatar">
                <img :src="thalosAvatar" alt="THALOS" />
              </div>
              <h4>THALOS</h4>
              <p>Ciberseguridad, auditorías y protección 24/7</p>
            </div>
            <div class="agent-card">
              <div class="agent-avatar">
                <img :src="justiciaAvatar" alt="JUSTICIA" />
              </div>
              <h4>JUSTICIA</h4>
              <p>Legal, contratos, GDPR y compliance</p>
            </div>
            <div class="agent-card">
              <div class="agent-avatar">
                <img :src="afroditaAvatar" alt="AFRODITA" />
              </div>
              <h4>AFRODITA</h4>
              <p>RRHH, logística, horarios y gestión de equipos</p>
            </div>
          </div>
        </div>

        <div class="features-grid">
          <div class="feature-item">
            <div class="feature-icon">📱</div>
            <h3>WhatsApp Automation</h3>
            <p>Responde automáticamente a tus clientes por WhatsApp 24/7</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">📧</div>
            <h3>Email Automation</h3>
            <p>Gestiona tu correo con respuestas inteligentes de IA</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">🏛️</div>
            <h3>Facturación + Hacienda</h3>
            <p>Facturas y borradores de modelos fiscales (303) para tu asesor. La presentación ante la AEAT no está incluida.</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">👥</div>
            <h3>RRHH + Logística</h3>
            <p>Gestión de equipos, horarios, rutas y entregas con AFRODITA</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">📊</div>
            <h3>Marketing Automation</h3>
            <p>Optimiza campañas en Google Ads y Meta Ads con IA</p>
          </div>
          <div class="feature-item">
            <div class="feature-icon">🔒</div>
            <h3>Seguridad Total</h3>
            <p>Ciberseguridad, auditorías y protección de datos</p>
          </div>
        </div>
      </div>
    </section>

    <!-- FAQ Section -->
    <section class="faq-section">
      <div class="container">
        <h2 class="section-title">Preguntas Frecuentes</h2>
        
        <div class="faq-grid">
          <div class="faq-item">
            <h3>¿Puedo cambiar de plan después?</h3>
            <p>Sí, puedes hacer upgrade o downgrade cuando quieras desde tu panel de control.</p>
          </div>
          <div class="faq-item">
            <h3>¿Hay periodo de prueba?</h3>
            <p>Ofrecemos demo gratuita de 30 minutos para que veas el sistema en acción.</p>
          </div>
          <div class="faq-item">
            <h3>¿Cómo funciona el modelo de pago?</h3>
            <p>El cliente paga el setup completo únicamente cuando ZEUS funcione al 100%. El despliegue funcional es verificado por TeamFlow y human_gatekeeper. No existen límites por mensajes o tokens - los planes se basan en el tamaño de tu empresa.</p>
          </div>
          <div class="faq-item">
            <h3>¿Qué significa "funcionando al 100%"?</h3>
            <p>ZEUS está desplegado cuando: (1) Los 6 agentes responden correctamente, (2) APIs integradas funcionan, (3) Tu equipo lo ha usado 5 días consecutivos, (4) Se completó un workflow completo. TÚ decides cuando está listo.</p>
          </div>
          <div class="faq-item">
            <h3>¿Qué formas de pago aceptan?</h3>
            <p>Tarjeta de crédito/débito vía Stripe. Pagos 100% seguros y encriptados.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Final -->
    <section class="cta-section">
      <div class="cta-content">
        <h2>¿Listo para automatizar tu empresa?</h2>
        <p>Únete a las empresas que ya usan ZEUS-IA</p>
        <div class="cta-buttons">
          <button class="btn-primary large" @click="selectPlan('growth')">
            Empezar ahora
          </button>
          <button class="btn-secondary large" @click="contactSales">
            Agendar demo
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

// Import avatar images from assets (processed by Vite)
import zeusAvatar from '@/assets/images/avatars/Zeus-avatar.jpg'
import perseoAvatar from '@/assets/images/avatars/Perseo-avatar.jpg'
import rafaelAvatar from '@/assets/images/avatars/Rafael-avatar.jpg'
import thalosAvatar from '@/assets/images/avatars/Thalos-avatar.jpg'
import justiciaAvatar from '@/assets/images/avatars/Justicia-avatar.jpg'
import afroditaAvatar from '@/assets/images/avatars/Afrodita-avatar.jpg'

const router = useRouter()

const selectPlan = (plan) => {
  // Redirigir al checkout con el plan seleccionado
  router.push({
    name: 'Checkout',
    params: { plan }
  })
}

const contactSales = () => {
  // Abrir email o formulario de contacto
  window.location.href = 'mailto:sales@zeus-ia.com?subject=Consulta ZEUS Enterprise'
}
</script>

<style scoped>
.pricing-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0a0e1a 0%, #1a1f2e 100%);
  color: #fff;
}

/* Hero Section */
.hero {
  padding: 100px 20px 60px;
  text-align: center;
}

.hero-title {
  font-size: 56px;
  font-weight: 800;
  margin: 0 0 20px;
  line-height: 1.2;
}

.gradient-text {
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-subtitle {
  font-size: 24px;
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 30px;
}

/* Value Proposition */
.value-prop {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 40px;
}

.value-badge {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.1);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 30px;
  font-size: 14px;
  font-weight: 600;
  backdrop-filter: blur(10px);
  transition: all 0.3s;
}

.value-badge:hover {
  transform: translateY(-2px);
  background: rgba(255, 255, 255, 0.15);
}

.value-badge.main {
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  border-color: transparent;
  font-size: 16px;
  animation: glow 2s infinite;
}

@keyframes glow {
  0%, 100% {
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.5);
  }
  50% {
    box-shadow: 0 0 40px rgba(139, 92, 246, 0.8);
  }
}

.hero-stats {
  display: flex;
  justify-content: center;
  gap: 60px;
  flex-wrap: wrap;
}

.stat {
  text-align: center;
}

.stat-value {
  font-size: 48px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 8px;
}

/* Comparison Section */
.comparison-section {
  padding: 80px 20px;
  background: rgba(0, 0, 0, 0.2);
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 30px;
  max-width: 1000px;
  margin: 0 auto;
}

.comparison-card {
  background: rgba(255, 255, 255, 0.05);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 30px;
  text-align: center;
  transition: all 0.3s;
}

.comparison-card:hover {
  transform: translateY(-8px);
  border-color: rgba(255, 255, 255, 0.3);
}

.comparison-card.winner {
  border-color: #3b82f6;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(139, 92, 246, 0.2));
  box-shadow: 0 0 40px rgba(59, 130, 246, 0.4);
  position: relative;
}

.winner-badge {
  position: absolute;
  top: -16px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  padding: 6px 20px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.comparison-rank {
  font-size: 48px;
  margin-bottom: 10px;
}

.comparison-card h3 {
  font-size: 24px;
  margin-bottom: 15px;
  color: rgba(255, 255, 255, 0.9);
}

.comparison-price {
  font-size: 32px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 20px;
}

.comparison-features {
  list-style: none;
  padding: 0;
  margin: 0;
  text-align: left;
}

.comparison-features li {
  padding: 10px 0;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.8);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.comparison-features li:last-child {
  border-bottom: none;
}

.comparison-features li.highlight {
  color: #10b981;
  font-weight: 700;
  font-size: 16px;
  animation: pulse-text 2s infinite;
}

@keyframes pulse-text {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Pricing Section */
.pricing-section {
  padding: 80px 20px;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
}

.section-title {
  font-size: 40px;
  font-weight: 700;
  text-align: center;
  margin: 0 0 16px;
}

.section-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.7);
  text-align: center;
  margin: 0 0 60px;
}

.plans-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 30px;
  margin-bottom: 40px;
}

.plan-card {
  background: linear-gradient(135deg, #1a1f2e 0%, #0f1419 100%);
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  padding: 32px;
  position: relative;
  transition: all 0.3s;
}

.plan-card:hover {
  transform: translateY(-8px);
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 20px 60px rgba(59, 130, 246, 0.3);
}

.plan-card.popular {
  border-color: #3b82f6;
  box-shadow: 0 10px 40px rgba(59, 130, 246, 0.4);
}

.popular-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  color: white;
  padding: 6px 20px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.plan-badge {
  display: inline-block;
  background: rgba(59, 130, 246, 0.2);
  color: #3b82f6;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
}

.hybrid-badge {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 20px;
  text-align: center;
  line-height: 1.4;
}

.price-breakdown {
  text-align: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.price-breakdown small {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.plan-name {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
}

.plan-description {
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 24px;
}

.plan-pricing {
  margin: 24px 0;
  padding: 24px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.price-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.price-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.price {
  font-size: 48px;
  font-weight: 700;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.price-note {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
}

.price-divider {
  text-align: center;
  font-size: 24px;
  color: rgba(255, 255, 255, 0.3);
  margin: 12px 0;
}

.features-list {
  list-style: none;
  padding: 0;
  margin: 24px 0;
}

.features-list li {
  padding: 10px 0;
  font-size: 14px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.8);
}

.btn-primary {
  width: 100%;
  padding: 16px 32px;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary:hover {
  transform: scale(1.05);
  box-shadow: 0 10px 30px rgba(59, 130, 246, 0.5);
}

.btn-primary.pulse {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7);
  }
  50% {
    box-shadow: 0 0 0 20px rgba(59, 130, 246, 0);
  }
}

.btn-secondary {
  width: 100%;
  padding: 16px 32px;
  background: transparent;
  color: white;
  border: 2px solid #3b82f6;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-secondary:hover {
  background: rgba(59, 130, 246, 0.1);
  transform: scale(1.05);
}

.trust-section {
  text-align: center;
  margin-top: 40px;
}

.trust-text {
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
}

/* Features Section */
.features-section {
  padding: 80px 20px;
  background: rgba(0, 0, 0, 0.3);
}

/* Agents Showcase */
.agents-showcase {
  margin-bottom: 60px;
}

.agents-title {
  text-align: center;
  font-size: 28px;
  margin-bottom: 40px;
  color: rgba(255, 255, 255, 0.9);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 30px;
  max-width: 1200px;
  margin: 0 auto 40px;
}

.agent-card {
  text-align: center;
  transition: all 0.3s;
  cursor: pointer;
}

.agent-card:hover {
  transform: translateY(-10px);
}

.agent-avatar {
  width: 120px;
  height: 120px;
  margin: 0 auto 15px;
  border-radius: 50%;
  overflow: hidden;
  border: 3px solid transparent;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
  padding: 3px;
  transition: all 0.3s;
}

.agent-card:hover .agent-avatar {
  box-shadow: 0 0 30px rgba(59, 130, 246, 0.6);
  transform: scale(1.1);
}

.agent-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  background: #1a1f2e;
}

.agent-card h4 {
  font-size: 18px;
  margin: 0 0 8px;
  color: #3b82f6;
}

.agent-card p {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.5;
  margin: 0;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 30px;
}

.feature-item {
  text-align: center;
  padding: 32px;
}

.feature-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.feature-item h3 {
  font-size: 20px;
  margin: 0 0 12px;
}

.feature-item p {
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
}

/* FAQ Section */
.faq-section {
  padding: 80px 20px;
}

.faq-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 30px;
}

.faq-item {
  background: rgba(255, 255, 255, 0.05);
  padding: 24px;
  border-radius: 12px;
}

.faq-item h3 {
  font-size: 18px;
  margin: 0 0 12px;
  color: #3b82f6;
}

.faq-item p {
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.6;
  margin: 0;
}

/* CTA Section */
.cta-section {
  padding: 100px 20px;
  text-align: center;
  background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
}

.cta-content h2 {
  font-size: 40px;
  margin: 0 0 16px;
}

.cta-content p {
  font-size: 20px;
  margin: 0 0 40px;
  opacity: 0.9;
}

.cta-buttons {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
}

.btn-primary.large,
.btn-secondary.large {
  padding: 20px 48px;
  font-size: 18px;
  width: auto;
}

.btn-primary.large {
  background: white;
  color: #3b82f6;
}

.btn-secondary.large {
  border-color: white;
  color: white;
}

.btn-secondary.large:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* Responsive */
@media (max-width: 768px) {
  .hero-title {
    font-size: 36px;
  }

  .hero-subtitle {
    font-size: 18px;
  }

  .section-title {
    font-size: 28px;
  }

  .plans-grid {
    grid-template-columns: 1fr;
  }

  .price {
    font-size: 36px;
  }
}
</style>

