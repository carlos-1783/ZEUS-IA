# Autenticación JWT en ZEUS-IA

Esta guía explica cómo implementar la autenticación JWT en el frontend para interactuar con la API de ZEUS-IA.

## Flujo de Autenticación

1. **Inicio de Sesión**: El usuario envía sus credenciales al endpoint `/api/v1/auth/login`
2. **Respuesta Exitosa**: El servidor devuelve un token de acceso y un token de actualización
3. **Almacenamiento**: Guardar el token de acceso en memoria (no en localStorage por seguridad)
4. **Uso del Token**: Incluir el token en el encabezado `Authorization: Bearer <token>`
5. **Renovación**: Usar el token de actualización para obtener un nuevo token de acceso cuando expire

## Configuración del Cliente HTTP

```typescript
// src/lib/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para añadir el token a las peticiones
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Interceptor para manejar errores de autenticación
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Si el error es 401 y no es una solicitud de actualización de token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        // Intentar renovar el token
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post('/auth/refresh-token', {
            refresh_token: refreshToken
          });
          
          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          if (refresh_token) {
            localStorage.setItem('refresh_token', refresh_token);
          }
          
          // Reintentar la petición original
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (error) {
        // Si falla la renovación, redirigir al login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;
```

## Ejemplo de Servicio de Autenticación

```typescript
// src/services/auth.service.ts
import api from '@/lib/api';

type LoginCredentials = {
  username: string;
  password: string;
};

type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user_id: number;
};

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);
    formData.append('grant_type', 'password');

    const response = await api.post<AuthResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Guardar tokens
    localStorage.setItem('access_token', response.data.access_token);
    if (response.data.refresh_token) {
      localStorage.setItem('refresh_token', response.data.refresh_token);
    }

    return response.data;
  },

  logout(): void {
    // Opcional: Llamar al endpoint de logout en el backend
    api.post('/auth/logout', {
      refresh_token: localStorage.getItem('refresh_token')
    }).catch(console.error);
    
    // Limpiar almacenamiento local
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // Redirigir al login
    window.location.href = '/login';
  },

  getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  },

  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  },

  // Verificar si el token está a punto de expirar (útil para renovación proactiva)
  isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const now = Date.now() / 1000;
      return payload.exp < now + 300; // 5 minutos de margen
    } catch (e) {
      return true;
    }
  },
};
```

## Uso en Componentes React

```tsx
// src/components/LoginForm.tsx
import { useState } from 'react';
import { authService } from '@/services/auth.service';

const LoginForm = () => {
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await authService.login(credentials);
      // Redirigir al dashboard
      window.location.href = '/dashboard';
    } catch (error) {
      setError('Usuario o contraseña incorrectos');
      console.error('Error en el login:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && <div className="error">{error}</div>}
      <div>
        <label>Email:</label>
        <input
          type="email"
          value={credentials.username}
          onChange={(e) => setCredentials({...credentials, username: e.target.value})}
          required
        />
      </div>
      <div>
        <label>Contraseña:</label>
        <input
          type="password"
          value={credentials.password}
          onChange={(e) => setCredentials({...credentials, password: e.target.value})}
          required
        />
      </div>
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Iniciando sesión...' : 'Iniciar sesión'}
      </button>
    </form>
  );
};

export default LoginForm;
```

## Protección de Rutas

```tsx
// src/components/ProtectedRoute.tsx
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '@/services/auth.service';

type ProtectedRouteProps = {
  children: React.ReactNode;
  requiredRoles?: string[];
};

const ProtectedRoute = ({ children, requiredRoles = [] }: ProtectedRouteProps) => {
  const navigate = useNavigate();
  const token = authService.getAccessToken();

  useEffect(() => {
    if (!token) {
      // Redirigir al login si no hay token
      navigate('/login', { replace: true });
      return;
    }

    // Verificar roles si es necesario
    if (requiredRoles.length > 0) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const hasRequiredRole = requiredRoles.some(role => 
          payload.scopes?.includes(role)
        );
        
        if (!hasRequiredRole) {
          // Redirigir a página de acceso denegado
          navigate('/unauthorized', { replace: true });
        }
      } catch (e) {
        console.error('Error al verificar roles:', e);
        navigate('/login', { replace: true });
      }
    }
  }, [token, navigate, requiredRoles]);

  if (!token) {
    return null; // O un componente de carga
  }

  return <>{children}</>;
};

export default ProtectedRoute;
```

## Uso del Componente de Ruta Protegida

```tsx
// En tu enrutador principal
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import AdminPanel from './pages/AdminPanel';

const AppRoutes = () => (
  <Router>
    <Routes>
      {/* Ruta pública */}
      <Route path="/login" element={<LoginPage />} />
      
      {/* Ruta protegida (cualquier usuario autenticado) */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      
      {/* Ruta solo para administradores */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AdminPanel />
          </ProtectedRoute>
        }
      />
    </Routes>
  </Router>
);
```

## Manejo de Errores Comunes

### Token expirado
El servidor devolverá un código de estado 401 cuando el token haya expirado. El interceptor de respuesta manejará automáticamente la renovación del token.

### Token inválido
Si el token es inválido o ha sido manipulado, el servidor devolverá un error 401. El interceptor redirigirá al usuario a la página de inicio de sesión.

### Sin permisos
Para rutas que requieren roles específicos, el servidor devolverá un error 403 si el usuario no tiene los permisos necesarios.

## Mejoras de Seguridad

1. **HttpOnly Cookies**: Para mayor seguridad, considera usar cookies HttpOnly para almacenar los tokens.
2. **Rotación de Tokens**: Implementa la rotación de tokens de actualización para mayor seguridad.
3. **Doble Envío de Tokens**: Envía el token tanto en una cookie HttpOnly como en el encabezado Authorization para compatibilidad con APIs y protección contra CSRF.
4. **Revocación de Tokens**: Implementa un sistema para revocar tokens cuando sea necesario.

## Pruebas

```typescript
// Ejemplo de prueba para el servicio de autenticación
describe('AuthService', () => {
  beforeEach(() => {
    localStorage.clear();
    jest.clearAllMocks();
  });

  it('debe autenticar al usuario correctamente', async () => {
    // Configurar mock de la API
    const mockResponse = {
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      token_type: 'bearer',
      expires_in: 3600,
      user_id: 1,
    };
    
    jest.spyOn(api, 'post').mockResolvedValueOnce({ data: mockResponse });
    
    // Ejecutar login
    const result = await authService.login({
      username: 'test@example.com',
      password: 'password123',
    });
    
    // Verificar resultados
    expect(result).toEqual(mockResponse);
    expect(localStorage.getItem('access_token')).toBe('test-access-token');
    expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token');
  });
  
  // Más pruebas...
});
```

## Conclusión

Esta implementación proporciona una base sólida para la autenticación JWT en el frontend. Asegúrate de personalizar los componentes y servicios según las necesidades específicas de tu aplicación.
