#!/usr/bin/env node

import WebSocket from 'ws';

// Test WebSocket connection with authentication
async function testWebSocketWithAuth() {
  console.log('🧪 Probando conexión WebSocket con autenticación...');
  
  // First, try to get a token by logging in
  console.log('🔐 Intentando obtener token de autenticación...');
  
  try {
    const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: 'username=marketingdigitalper.seo@gmail.com&password=Carnay19!'
    });
    
    if (!loginResponse.ok) {
      console.error('❌ Error en login:', loginResponse.status, loginResponse.statusText);
      const errorText = await loginResponse.text();
      console.error('Error details:', errorText);
      return;
    }
    
    const loginData = await loginResponse.json();
    console.log('✅ Login exitoso');
    console.log('Token obtenido:', loginData.access_token ? 'Sí' : 'No');
    
    if (!loginData.access_token) {
      console.error('❌ No se obtuvo token de acceso');
      return;
    }
    
    // Test WebSocket with token
    const baseUrl = 'ws://localhost:8000/api/v1/ws';
    const clientId = 'test-client-' + Date.now();
    const testUrl = `${baseUrl}/${clientId}?token=${encodeURIComponent(loginData.access_token)}`;
    
    console.log('URL de conexión WebSocket:', testUrl.replace(/token=([^&]+)/, 'token=***'));
    
    const ws = new WebSocket(testUrl);
    
    ws.on('open', () => {
      console.log('✅ Conexión WebSocket establecida correctamente con autenticación');
      
      // Send a test message
      const testMessage = {
        type: 'ping',
        data: { message: 'Test message from client' }
      };
      ws.send(JSON.stringify(testMessage));
    });
    
    ws.on('message', (data) => {
      console.log('📨 Mensaje recibido:', data.toString());
    });
    
    ws.on('error', (error) => {
      console.error('❌ Error de conexión WebSocket:', error.message);
    });
    
    ws.on('close', (code, reason) => {
      console.log(`🔌 Conexión cerrada - Código: ${code}, Razón: ${reason}`);
    });
    
    // Timeout después de 10 segundos
    setTimeout(() => {
      if (ws.readyState === WebSocket.CONNECTING) {
        console.log('⏰ Timeout: La conexión no se estableció en 10 segundos');
        ws.close();
      } else if (ws.readyState === WebSocket.OPEN) {
        console.log('✅ Conexión mantenida exitosamente');
        ws.close();
      }
    }, 10000);
    
  } catch (error) {
    console.error('❌ Error en el proceso de autenticación:', error.message);
  }
}

// Test HTTP connection first
async function testHttpConnection() {
  console.log('🌐 Probando conexión HTTP...');
  
  try {
    const response = await fetch('http://localhost:8000/api/v1/health');
    if (response.ok) {
      const data = await response.json();
      console.log('✅ Backend HTTP funcionando:', data);
      return true;
    } else {
      console.log('⚠️ Backend HTTP respondió con código:', response.status);
      return false;
    }
  } catch (error) {
    console.error('❌ Error de conexión HTTP:', error.message);
    return false;
  }
}

// Run tests
async function runTests() {
  console.log('🚀 Iniciando pruebas de WebSocket con autenticación...\n');
  
  const httpOk = await testHttpConnection();
  
  if (httpOk) {
    console.log('\n📡 Probando WebSocket con autenticación...');
    await testWebSocketWithAuth();
  } else {
    console.log('\n❌ No se puede probar WebSocket: Backend HTTP no disponible');
  }
  
  console.log('\n✨ Pruebas completadas');
}

runTests().catch(console.error);
