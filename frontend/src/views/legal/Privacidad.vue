<template>
  <div class="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-3xl mx-auto prose prose-indigo">
      <h1 class="text-3xl font-bold text-gray-900">Política de privacidad</h1>
      <p class="text-sm text-gray-500">Última actualización: {{ lastUpdated }}</p>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">1. Responsable del tratamiento</h2>
        <p class="text-gray-600 mt-2">
          Los datos personales que recogemos a través de la plataforma ZEUS IA son tratados por el responsable
          del servicio, conforme a la normativa aplicable en materia de protección de datos (RGPD y LOPDGDD).
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">2. Datos que recogemos</h2>
        <p class="text-gray-600 mt-2">
          Recogemos los datos que usted nos facilita al registrarse y usar el servicio: correo electrónico,
          nombre, datos de empresa, y los que introduzca en los módulos (TPV, control horario, nóminas, etc.).
          También podemos recoger datos técnicos de uso (logs, direcciones IP) para el funcionamiento y seguridad del servicio.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">3. Finalidad y legitimación</h2>
        <p class="text-gray-600 mt-2">
          Los datos se tratan para la prestación del servicio contratado, la gestión de la cuenta,
          la facturación y el cumplimiento de obligaciones legales. La base legal es la ejecución del contrato
          y, cuando corresponda, el consentimiento o el interés legítimo.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">4. Conservación y seguridad</h2>
        <p class="text-gray-600 mt-2">
          Conservamos los datos mientras sea necesario para las finalidades indicadas y durante los plazos
          legales aplicables. Aplicamos medidas técnicas y organizativas para proteger sus datos frente a
          accesos no autorizados y pérdida.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">5. Derechos</h2>
        <p class="text-gray-600 mt-2">
          Puede ejercer sus derechos de acceso, rectificación, supresión, limitación, portabilidad y oposición,
          así como reclamar ante la autoridad de control, dirigiéndose al contacto que indiquemos en la Plataforma.
        </p>
      </section>

      <section class="mt-8">
        <h2 class="text-xl font-semibold text-gray-900">6. Cookies y tecnologías similares</h2>
        <p class="text-gray-600 mt-2">
          La Plataforma puede utilizar cookies y tecnologías similares para el funcionamiento de la sesión
          y la mejora del servicio, conforme a nuestra política de cookies (si aplica).
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
