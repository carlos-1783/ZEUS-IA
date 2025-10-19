#!/usr/bin/env node

import WebSocket from 'ws';

// Test WebSocket connection
async function testWebSocketConnection() {
  console.log('🧪 Probando conexión WebSocket...');
  
  const baseUrl = 'ws://localhost:8000/api/v1/ws';
  const clientId = 'test-client-' + Date.now();
  const testUrl = `${baseUrl}/${clientId}`;
  
  console.log('URL de conexión:', testUrl);
  
  try {
    const ws = new WebSocket(testUrl);
    
    ws.on('open', () => {
      console.log('✅ Conexión WebSocket establecida correctamente');
      ws.close();
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
    
    // Timeout después de 5 segundos
    setTimeout(() => {
      if (ws.readyState === WebSocket.CONNECTING) {
        console.log('⏰ Timeout: La conexión no se estableció en 5 segundos');
        ws.close();
      }
    }, 5000);
    
  } catch (error) {
    console.error('❌ Error al crear conexión WebSocket:', error.message);
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
  console.log('🚀 Iniciando pruebas de conectividad...\n');
  
  const httpOk = await testHttpConnection();
  
  if (httpOk) {
    console.log('\n📡 Probando WebSocket...');
    await testWebSocketConnection();
  } else {
    console.log('\n❌ No se puede probar WebSocket: Backend HTTP no disponible');
  }
  
  console.log('\n✨ Pruebas completadas');
}

runTests().catch(console.error);
