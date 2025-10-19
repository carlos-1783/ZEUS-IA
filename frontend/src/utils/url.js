/**
 * URL encoding/decoding utilities
 * Ensures consistent handling of URL parameters across the application
 */

/**
 * Encodes a string for use in a URL path or query parameter
 * @param {string} str - The string to encode
 * @returns {string} The encoded string
 */
export const encodeUrlParam = (str) => {
  if (str === undefined || str === null) return '';
  return encodeURIComponent(String(str));
};

/**
 * Decodes a URL-encoded string
 * @param {string} str - The string to decode
 * @returns {string} The decoded string
 */
export const decodeUrlParam = (str) => {
  if (str === undefined || str === null) return '';
  try {
    return decodeURIComponent(String(str));
  } catch (e) {
    console.warn('Failed to decode URL parameter:', e);
    return str;
  }
};

/**
 * Builds a URL with properly encoded query parameters
 * @param {string} baseUrl - The base URL without query parameters
 * @param {Object} params - The query parameters as key-value pairs
 * @returns {string} The complete URL with encoded query parameters
 */
export const buildUrl = (baseUrl, params = {}) => {
  const queryString = Object.entries(params)
    .filter(([_, value]) => value !== undefined && value !== null)
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        return value
          .filter(v => v !== undefined && v !== null)
          .map(v => `${encodeUrlParam(key)}=${encodeUrlParam(v)}`)
          .join('&');
      }
      return `${encodeUrlParam(key)}=${encodeUrlParam(value)}`;
    })
    .filter(Boolean)
    .join('&');

  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};
