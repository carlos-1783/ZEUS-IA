ontinuarwindow.onload = function() {
  // Configuración personalizada de Swagger UI
  const ui = window.ui = new SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIBundle.SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "BaseLayout",
    // Mejoras de accesibilidad
    docExpansion: 'list',
    filter: true,
    showExtensions: true,
    showCommonExtensions: true,
    // Configuración de temas y estilos
    defaultModelsExpandDepth: 1,
    defaultModelExpandDepth: 1,
    defaultModelRendering: 'example',
    displayRequestDuration: true,
    // Configuración de red
    requestSnippetsEnabled: true,
    requestSnippets: {
      generators: {
        curl_bash: {
          title: 'cURL (bash)',
          syntax: 'bash'
        },
        curl_powershell: {
          title: 'cURL (PowerShell)',
          syntax: 'powershell'
        },
        curl_cmd: {
          title: 'cURL (CMD)',
          syntax: 'bash'
        },
        // Añadir más generadores según sea necesario
      },
      defaultExpanded: true,
      // Asegurarse de que los IDs sean únicos
      // para evitar advertencias de accesibilidad
      requestSnippetsOptions: {
        generateId: function() {
          return 'snippet-' + Math.random().toString(36).substr(2, 9);
        }
      }
    },
    // Mejoras de rendimiento
    defaultModelRendering: 'model',
    displayOperationId: false,
    displayRequestDuration: true,
    maxDisplayedTags: 10,
    showExtensions: true,
    showCommonExtensions: true,
    // Configuración de la interfaz de usuario
    operationsSorter: 'method',
    showRequestHeaders: true,
    // Configuración de autenticación
    persistAuthorization: true,
    // Configuración de la API
    tryItOutEnabled: true,
    // Configuración de la documentación
    withCredentials: true,
    // Configuración de la interfaz de usuario
    useUnsafeMarkdown: false,
    // Configuración de la API
    validatorUrl: null,
    // Configuración de la interfaz de usuario
    withCredentials: true
  });

  // Mejorar accesibilidad
  document.querySelectorAll('.opblock-summary')
    .forEach(el => {
      el.setAttribute('role', 'button');
      el.setAttribute('aria-expanded', 'false');
      el.setAttribute('tabindex', '0');
      
      // Asegurar que los IDs sean únicos
      const opId = 'opblock-' + Math.random().toString(36).substr(2, 9);
      el.setAttribute('id', opId);
      
      const contentId = opId + '-content';
      const content = el.nextElementSibling;
      if (content && content.classList.contains('opblock-body')) {
        content.setAttribute('id', contentId);
        el.setAttribute('aria-controls', contentId);
      }
      
      // Manejar eventos de teclado para accesibilidad
      el.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.click();
        }
      });
    });

  // Mejorar accesibilidad de los botones
  document.querySelectorAll('button')
    .forEach(btn => {
      if (!btn.id) {
        btn.id = 'btn-' + Math.random().toString(36).substr(2, 9);
      }
      if (!btn.getAttribute('aria-label') && !btn.textContent.trim()) {
        btn.setAttribute('aria-label', 'Botón sin etiqueta');
      }
    });

  // Mejorar accesibilidad de los formularios
  document.querySelectorAll('form')
    .forEach((form, index) => {
      form.setAttribute('role', 'form');
      if (!form.id) {
        form.id = 'form-' + (index + 1);
      }
    });

  // Mejorar accesibilidad de las tablas
  document.querySelectorAll('table')
    .forEach((table, index) => {
      table.setAttribute('role', 'table');
      if (!table.id) {
        table.id = 'table-' + (index + 1);
      }
      
      // Añadir atributos de accesibilidad a las celdas de encabezado
      const headers = table.querySelectorAll('th');
      headers.forEach(header => {
        if (!header.getAttribute('scope')) {
          header.setAttribute('scope', 'col');
        }
      });
    });

  console.log('Swagger UI configurado con mejoras de accesibilidad y rendimiento');
};
