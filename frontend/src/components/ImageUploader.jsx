import { defineComponent, ref, computed } from 'vue';
import tokenService from '@/api/tokenService';
import { API_BASE_URL, PERSEO_IMAGES_ENABLED } from '@/config';

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export default defineComponent({
  name: 'ImageUploader',
  emits: ['uploaded'],
  setup(_, { emit }) {
    const selectedFile = ref(null);
    const previewUrl = ref('');
    const uploadedUrl = ref('');
    const isUploading = ref(false);
    const errorMessage = ref('');

    const isDisabled = computed(() => !PERSEO_IMAGES_ENABLED);

    const revokePreview = () => {
      if (previewUrl.value) {
        URL.revokeObjectURL(previewUrl.value);
      }
    };

    const reset = () => {
      selectedFile.value = null;
      revokePreview();
      previewUrl.value = '';
      errorMessage.value = '';
    };

    const handleFileChange = (event) => {
      const file = event?.target?.files?.[0];
      if (!file) return;

      revokePreview();

      if (!ALLOWED_TYPES.includes(file.type)) {
        errorMessage.value = 'Formato no soportado. Usa JPEG, PNG o WEBP.';
        return;
      }

      selectedFile.value = file;
      previewUrl.value = URL.createObjectURL(file);
      errorMessage.value = '';
    };

    const uploadFile = async () => {
      if (!selectedFile.value) {
        errorMessage.value = 'Selecciona una imagen antes de subirla.';
        return;
      }

      isUploading.value = true;
      errorMessage.value = '';

      try {
        const formData = new FormData();
        formData.append('image', selectedFile.value);

        const headers = {};
        const token = tokenService.getToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE_URL}/perseo/upload-image`, {
          method: 'POST',
          body: formData,
          headers,
        });

        const data = await response.json();
        if (!response.ok || !data?.success) {
          throw new Error(data?.detail || data?.error || 'No se pudo subir la imagen');
        }

        uploadedUrl.value = data.url;
        emit('uploaded', { url: data.url, metadata: data });
        selectedFile.value = null;
        revokePreview();
        previewUrl.value = '';
      } catch (error) {
        errorMessage.value = error?.message || 'Error subiendo la imagen';
      } finally {
        isUploading.value = false;
      }
    };

    return () => (
      <div class="perseo-image-uploader">
        <div class="uploader-header">
          <span>Referencia visual</span>
          {uploadedUrl.value && (
            <a href={uploadedUrl.value} target="_blank" rel="noopener" class="uploader-link">
              Ver última
            </a>
          )}
        </div>

        <div class="uploader-body">
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            disabled={isDisabled.value}
          />
          <button
            type="button"
            class="uploader-btn"
            onClick={uploadFile}
            disabled={isDisabled.value || !selectedFile.value || isUploading.value}
          >
            {isUploading.value ? 'Subiendo…' : 'Subir imagen'}
          </button>
          {previewUrl.value && (
            <div class="uploader-preview">
              <img src={previewUrl.value} alt="Vista previa" />
              <button type="button" class="uploader-reset" onClick={reset}>
                ✕
              </button>
            </div>
          )}
        </div>

        {errorMessage.value && <p class="uploader-error">{errorMessage.value}</p>}
        {isDisabled.value && (
          <p class="uploader-hint">Las cargas de imágenes están deshabilitadas en esta instancia.</p>
        )}
      </div>
    );
  },
});

