import { useAuthStore } from '@/stores/auth';
import { getWebSocketUrl } from '@/config';

// Make auth store available globally for testing
const authStore = useAuthStore();

// Test login function
export async function testLogin(email: string, password: string) {
  console.log('=== Starting login test ===');
  
  try {
    console.log('Calling login with:', { email });
    const response = await authStore.login(email, password);
    
    if (response.success) {
      console.log('✅ Login successful!');
      console.log('Access Token:', authStore.token ? 'Received' : 'Missing');
      console.log('Refresh Token:', authStore.refreshToken ? 'Received' : 'Missing');
      console.log('User:', authStore.user);
      
      // Try to initialize WebSocket
      console.log('\n=== Testing WebSocket connection ===');
      try {
        const wsUrl = `${getWebSocketUrl(`test-${Date.now()}`)}?token=${authStore.token}`;
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('✅ WebSocket connected successfully!');
          ws.send(JSON.stringify({ type: 'test', message: 'Hello from client' }));
        };
        
        ws.onmessage = (event) => {
          console.log('📩 WebSocket message:', event.data);
        };
        
        ws.onerror = (error) => {
          console.error('❌ WebSocket error:', error);
        };
        
        ws.onclose = (event) => {
          console.log('🔌 WebSocket closed:', event.code, event.reason);
        };
        
        // Store WebSocket instance for testing
        (window as any).testWs = ws;
      } catch (wsError) {
        console.error('❌ WebSocket connection failed:', wsError);
      }
      
    } else {
      console.error('❌ Login failed:', response.error);
    }
    
  } catch (error) {
    console.error('❌ Error during login:', error);
  } finally {
    console.log('=== Login test completed ===');
  }
}

// Add to window for easy access in browser console
if (typeof window !== 'undefined') {
  (window as any).testLogin = testLogin;
  console.log('Test login function available as `testLogin(email, password)`');
}
