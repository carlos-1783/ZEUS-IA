<template>
  <div class="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-3xl mx-auto prose prose-indigo">
      <h1 class="text-3xl font-bold text-gray-900">Términos de servicio</h1>
      <p class="text-sm text-gray-500">Última actualización: {{ lastUpdated }}</p>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">1. Aceptación</h2>
        <p class="text-gray-600 mt-2">
          Al acceder o usar los servicios de ZEUS IA («la Plataforma»), usted acepta estos Términos de servicio.
          Si no está de acuerdo con ellos, no utilice la Plataforma.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">2. Descripción del servicio</h2>
        <p class="text-gray-600 mt-2">
          ZEUS IA es una plataforma SaaS de automatización empresarial que incluye, entre otros,
          TPV, control horario, nóminas, agentes de IA y módulos de fiscalidad y documentos.
          Los servicios se prestan según el plan contratado y están sujetos a disponibilidad.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">3. Uso aceptable</h2>
        <p class="text-gray-600 mt-2">
          Usted se compromete a utilizar la Plataforma de forma lícita y conforme a la normativa aplicable.
          No está permitido el uso para actividades fraudulentas, abusivas o que vulneren derechos de terceros.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">4. Cuenta y datos</h2>
        <p class="text-gray-600 mt-2">
          Es responsable de mantener la confidencialidad de su cuenta y contraseña. Los datos que introduzca
          en la Plataforma se procesan según nuestra Política de privacidad.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">5. Propiedad intelectual</h2>
        <p class="text-gray-600 mt-2">
          ZEUS IA y sus materiales (software, marcas, documentación) son propiedad de sus titulares.
          No se concede ninguna licencia implícita más allá del uso de la Plataforma conforme a estos términos.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">6. Limitación de responsabilidad</h2>
        <p class="text-gray-600 mt-2">
          La Plataforma se ofrece «tal cual». En la medida permitida por la ley, ZEUS IA no será responsable
          de daños indirectos, consecuentes o punitivos derivados del uso o la imposibilidad de uso del servicio.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">7. Modificaciones</h2>
        <p class="text-gray-600 mt-2">
          Nos reservamos el derecho de modificar estos términos. Los cambios se notificarán mediante aviso
          en la Plataforma o por correo. El uso continuado tras los cambios implica su aceptación.
        </p>
      </section>

      <div class="mt-12 pt-6 border-t border-gray-200">
        <router-link to="/" class="text-indigo-600 hover:text-indigo-500 font-medium">
          ← Volver al inicio
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const lastUpdated = new Date().toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' });
</script>
