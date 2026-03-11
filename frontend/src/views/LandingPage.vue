<template>
  <div class="landing-page min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white">
    <!-- Hero Section -->
    <header class="relative overflow-hidden">
      <div class="absolute inset-0">
        <div class="absolute inset-0 bg-black/60"></div>
      </div>
      
      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-32">
        <div class="text-center">
          <h1 class="text-4xl tracking-tight font-extrabold text-white sm:text-5xl md:text-6xl">
            <span class="block">Potencia tu negocio con</span>
            <span class="block text-indigo-400">ZEUS IA</span>
          </h1>
          <p class="mt-3 max-w-md mx-auto text-base text-gray-300 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl">
            La plataforma todo en uno para automatizar y escalar tu negocio con inteligencia artificial.
          </p>
          <div class="mt-10 sm:flex sm:justify-center">
            <div class="rounded-md shadow">
              <router-link 
                to="/login" 
                class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 md:py-4 md:text-lg md:px-10"
              >
                Comenzar ahora
              </router-link>
            </div>
            <div class="mt-3 rounded-md shadow sm:mt-0 sm:ml-3">
              <a 
                href="#features" 
                class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-indigo-600 bg-white hover:bg-gray-50 md:py-4 md:text-lg md:px-10"
              >
                Saber más
              </a>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Features Section -->
    <section id="features" class="py-12 bg-gray-900">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="lg:text-center">
          <h2 class="text-base text-indigo-400 font-semibold tracking-wide uppercase">Características</h2>
          <p class="mt-2 text-3xl leading-8 font-extrabold tracking-tight text-white sm:text-4xl">
            Todo lo que necesitas para hacer crecer tu negocio
          </p>
        </div>

        <div class="mt-10">
          <div class="space-y-10 md:space-y-0 md:grid md:grid-cols-2 md:gap-x-8 md:gap-y-10">
            <!-- Feature 1 -->
            <div class="relative">
              <div class="absolute flex items-center justify-center h-12 w-12 rounded-md bg-indigo-500 text-white">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div class="ml-16">
                <h3 class="text-lg leading-6 font-medium text-white">Automatización Inteligente</h3>
                <p class="mt-2 text-base text-gray-300">
                  Automatiza tareas repetitivas y procesos con IA para ahorrar tiempo y recursos.
                </p>
              </div>
            </div>

            <!-- Feature 2 -->
            <div class="relative">
              <div class="absolute flex items-center justify-center h-12 w-12 rounded-md bg-indigo-500 text-white">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div class="ml-16">
                <h3 class="text-lg leading-6 font-medium text-white">Análisis en Tiempo Real</h3>
                <p class="mt-2 text-base text-gray-300">
                  Obtén información valiosa sobre el rendimiento de tu negocio con análisis en tiempo real.
                </p>
              </div>
            </div>

            <!-- Feature 3 -->
            <div class="relative">
              <div class="absolute flex items-center justify-center h-12 w-12 rounded-md bg-indigo-500 text-white">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <div class="ml-16">
                <h3 class="text-lg leading-6 font-medium text-white">Seguridad Avanzada</h3>
                <p class="mt-2 text-base text-gray-300">
                  Protege tus datos con las últimas tecnologías de encriptación y seguridad.
                </p>
              </div>
            </div>

            <!-- Feature 4 -->
            <div class="relative">
              <div class="absolute flex items-center justify-center h-12 w-12 rounded-md bg-indigo-500 text-white">
                <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                </svg>
              </div>
              <div class="ml-16">
                <h3 class="text-lg leading-6 font-medium text-white">En la Nube</h3>
                <p class="mt-2 text-base text-gray-300">
                  Accede a tu negocio desde cualquier lugar, en cualquier momento y desde cualquier dispositivo.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Los 6 agentes -->
    <section id="agentes" class="py-16 bg-gray-800">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-12">
          <h2 class="text-base text-indigo-400 font-semibold tracking-wide uppercase">Agentes de IA</h2>
          <p class="mt-2 text-3xl font-extrabold text-white sm:text-4xl">
            Seis agentes especializados para tu negocio
          </p>
          <p class="mt-3 max-w-2xl mx-auto text-gray-300">
            Cada agente cubre un área clave: orquestación, marketing, fiscal, legal, automatización y nóminas.
          </p>
        </div>
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div class="bg-gray-900/80 rounded-lg p-6 border border-gray-700 hover:border-indigo-500/50 transition-colors">
            <h3 class="text-lg font-semibold text-indigo-400">ZEUS CORE</h3>
            <p class="mt-2 text-gray-300 text-sm">Núcleo orquestador y asistente principal.</p>
          </div>
          <div class="bg-gray-900/80 rounded-lg p-6 border border-gray-700 hover:border-indigo-500/50 transition-colors">
            <h3 class="text-lg font-semibold text-indigo-400">PERSEO</h3>
            <p class="mt-2 text-gray-300 text-sm">Campañas, imágenes y marketing (PERSEO Images).</p>
          </div>
          <div class="bg-gray-900/80 rounded-lg p-6 border border-gray-700 hover:border-indigo-500/50 transition-colors">
            <h3 class="text-lg font-semibold text-indigo-400">RAFAEL</h3>
            <p class="mt-2 text-gray-300 text-sm">Fiscal, facturación y documentos (aprobación).</p>
          </div>
          <div class="bg-gray-900/80 rounded-lg p-6 border border-gray-700 hover:border-indigo-500/50 transition-colors">
            <h3 class="text-lg font-semibold text-indigo-400">JUSTICIA</h3>
            <p class="mt-2 text-gray-300 text-sm">Legal y documentos (aprobación).</p>
          </div>
          <div class="bg-gray-900/80 rounded-lg p-6 border border-gray-700 hover:border-indigo-500/50 transition-colors">
            <h3 class="text-lg font-semibold text-indigo-400">THALOS</h3>
            <p class="mt-2 text-gray-300 text-sm">Automatización y handlers.</p>
          </div>
          <div class="bg-gray-900/80 rounded-lg p-6 border border-gray-700 hover:border-indigo-500/50 transition-colors">
            <h3 class="text-lg font-semibold text-indigo-400">AFRODITA</h3>
            <p class="mt-2 text-gray-300 text-sm">Recursos humanos y nóminas (payroll draft).</p>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="bg-indigo-700">
      <div class="max-w-2xl mx-auto text-center py-16 px-4 sm:py-20 sm:px-6 lg:px-8">
        <h2 class="text-3xl font-extrabold text-white sm:text-4xl">
          <span class="block">¿Listo para comenzar?</span>
          <span class="block">Elige tu plan</span>
        </h2>
        <p class="mt-4 text-lg leading-6 text-indigo-200">
          Únete a negocios que ya automatizan con ZEUS IA.
        </p>
        <router-link 
          to="/pricing" 
          class="mt-8 w-full inline-flex items-center justify-center px-5 py-3 border border-transparent text-base font-medium rounded-md text-indigo-600 bg-white hover:bg-indigo-50 sm:w-auto"
        >
          Ver planes
        </router-link>
      </div>
    </section>

    <!-- Footer -->
    <footer class="bg-gray-900">
      <div class="max-w-7xl mx-auto py-12 px-4 overflow-hidden sm:px-6 lg:px-8">
        <nav class="-mx-5 -my-2 flex flex-wrap justify-center" aria-label="Footer">
          <div class="px-5 py-2">
            <router-link to="/#features" class="text-base text-gray-300 hover:text-white">Características</router-link>
          </div>
          <div class="px-5 py-2">
            <router-link to="/#agentes" class="text-base text-gray-300 hover:text-white">Agentes</router-link>
          </div>
          <div class="px-5 py-2">
            <router-link to="/pricing" class="text-base text-gray-300 hover:text-white">Precios</router-link>
          </div>
          <div class="px-5 py-2">
            <router-link to="/terminos" class="text-base text-gray-300 hover:text-white">Términos</router-link>
          </div>
          <div class="px-5 py-2">
            <router-link to="/privacidad" class="text-base text-gray-300 hover:text-white">Privacidad</router-link>
          </div>
        </nav>
        <p class="mt-8 text-center text-base text-gray-400">
          &copy; {{ new Date().getFullYear() }} ZEUS IA. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
// No se necesita lógica adicional para el landing page
</script>

<style scoped>
.landing-page {
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* Animaciones */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
