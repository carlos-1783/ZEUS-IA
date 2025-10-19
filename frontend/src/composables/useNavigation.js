import { useRouter } from 'vue-router';
import { encodeUrlParam } from '@/utils/url';

/**
 * Composable for handling navigation with proper URL encoding
 */
export function useNavigation() {
  const router = useRouter();

  /**
   * Navigate to a route with encoded parameters
   * @param {string} name - Route name
   * @param {Object} params - Route parameters (will be encoded)
   * @param {Object} query - Query parameters (will be encoded)
   * @param {Object} options - Additional router options
   */
  const navigate = (name, { params = {}, query = {}, ...options } = {}) => {
    // Encode all string parameters
    const encodedParams = Object.fromEntries(
      Object.entries(params).map(([key, value]) => {
        if (value === undefined || value === null) return [key, value];
        return [key, typeof value === 'string' ? encodeUrlParam(value) : value];
      })
    );

    // Encode all query parameters
    const encodedQuery = Object.fromEntries(
      Object.entries(query).map(([key, value]) => {
        if (value === undefined || value === null) return [key, value];
        if (Array.isArray(value)) {
          return [
            key,
            value.map(v => (typeof v === 'string' ? encodeUrlParam(v) : v))
          ];
        }
        return [key, typeof value === 'string' ? encodeUrlParam(value) : value];
      })
    );

    return router.push({
      name,
      params: encodedParams,
      query: encodedQuery,
      ...options
    });
  };

  return {
    navigate,
    router
  };
}
