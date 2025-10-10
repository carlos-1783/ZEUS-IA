/**
 * Swagger UI Configuration for ZEUS-IA API
 * Custom initialization script with enhanced features
 */

window.onload = function() {
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
        }
      },
      defaultExpanded: true,
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
    
    // Configuración de seguridad
    oauth2RedirectUrl: window.location.origin + '/oauth2-redirect',
    
    // Configuración de OAuth2
    initOAuth: {
      clientId: 'zeus-ia-client',
      clientSecret: 'your-client-secret',
      realm: 'zeus-ia',
      appName: 'ZEUS-IA API',
      scopeSeparator: ' ',
      scopes: 'read write',
      additionalQueryStringParams: {},
      usePkceWithAuthorizationCodeGrant: true
    },
    
    // Configuración de respuesta
    responseInterceptor: function(response) {
      // Mejorar el manejo de errores
      if (response.status >= 400) {
        console.warn('API Error:', response.status, response.statusText);
      }
      return response;
    },
    
    // Configuración de solicitud
    requestInterceptor: function(request) {
      // Agregar headers personalizados si es necesario
      if (request.headers) {
        request.headers['X-Requested-With'] = 'SwaggerUI';
      }
      return request;
    },
    
    // Configuración de validación
    validatorUrl: null, // Deshabilitar validación externa
    
    // Configuración de caché
    supportedSubmitMethods: ['get', 'post', 'put', 'delete', 'patch'],
    
    // Configuración de temas
    onComplete: function() {
      // Aplicar tema personalizado
      applyCustomTheme();
      
      // Configurar eventos personalizados
      setupCustomEvents();
      
      // Mejorar accesibilidad
      improveAccessibility();
    }
  });
  
  // Función para aplicar tema personalizado
  function applyCustomTheme() {
    const style = document.createElement('style');
    style.textContent = `
      .swagger-ui .topbar {
        background-color: #1a1f2c;
        border-bottom: 2px solid #4990e2;
      }
      
      .swagger-ui .info .title {
        color: #4990e2;
        font-weight: 600;
      }
      
      .swagger-ui .opblock.opblock-get .opblock-summary-method {
        background-color: #61affe;
      }
      
      .swagger-ui .opblock.opblock-post .opblock-summary-method {
        background-color: #49cc90;
      }
      
      .swagger-ui .opblock.opblock-put .opblock-summary-method {
        background-color: #fca130;
      }
      
      .swagger-ui .opblock.opblock-delete .opblock-summary-method {
        background-color: #f93e3e;
      }
      
      .swagger-ui .btn.execute {
        background-color: #4990e2;
        border-color: #4990e2;
      }
      
      .swagger-ui .btn.execute:hover {
        background-color: #357abd;
        border-color: #357abd;
      }
      
      /* Mejoras de accesibilidad */
      .swagger-ui .opblock-summary-description {
        font-size: 14px;
        line-height: 1.5;
      }
      
      .swagger-ui .opblock-summary-path {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
      }
      
      /* Responsive design */
      @media (max-width: 768px) {
        .swagger-ui .opblock-summary-path {
          font-size: 12px;
        }
        
        .swagger-ui .opblock-summary-description {
          font-size: 12px;
        }
      }
    `;
    document.head.appendChild(style);
  }
  
  // Función para configurar eventos personalizados
  function setupCustomEvents() {
    // Evento para cuando se expande una operación
    document.addEventListener('click', function(e) {
      if (e.target.classList.contains('opblock-summary')) {
        setTimeout(() => {
          // Scroll suave a la operación expandida
          e.target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      }
    });
    
    // Evento para copiar URL de la operación
    document.addEventListener('click', function(e) {
      if (e.target.classList.contains('opblock-summary-path')) {
        const path = e.target.textContent;
        navigator.clipboard.writeText(path).then(() => {
          // Mostrar notificación de copiado
          showNotification('URL copiada al portapapeles');
        });
      }
    });
  }
  
  // Función para mejorar accesibilidad
  function improveAccessibility() {
    // Agregar atributos ARIA
    const opblocks = document.querySelectorAll('.opblock');
    opblocks.forEach((block, index) => {
      block.setAttribute('aria-label', `Operación ${index + 1}`);
      block.setAttribute('role', 'region');
    });
    
    // Mejorar navegación por teclado
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
      button.setAttribute('tabindex', '0');
    });
  }
  
  // Función para mostrar notificaciones
  function showNotification(message) {
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background-color: #4990e2;
      color: white;
      padding: 10px 20px;
      border-radius: 4px;
      z-index: 9999;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
  
  // Configurar interceptores de errores globales
  window.addEventListener('error', function(e) {
    console.error('Swagger UI Error:', e.error);
  });
  
  // Configurar interceptores de errores de red
  window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled Promise Rejection:', e.reason);
  });
  
  return ui;
}; 