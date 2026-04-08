import { defineComponent, ref, computed } from 'vue';
import api from '@/services/api';
import { PERSEO_IMAGES_ENABLED } from '@/config';

const ALLOWED_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
  'video/mp4',
  'video/webm',
  'video/quicktime',
  'application/pdf',
];

const ACCEPT_ATTR = 'image/*,video/*,application/pdf';

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

    const applyFile = (file) => {
      if (!file) return;
      revokePreview();
      if (!ALLOWED_TYPES.includes(file.type)) {
        errorMessage.value =
          'Formato no soportado. Usa imagen (JPEG, PNG, WEBP, GIF), vídeo (MP4, WEBM, MOV) o PDF.';
        return;
      }
      selectedFile.value = file;
      previewUrl.value = URL.createObjectURL(file);
      errorMessage.value = '';
    };

    const handleFileChange = (event) => {
      const file = event?.target?.files?.[0];
      applyFile(file);
    };

    const onDragOver = (e) => {
      e?.preventDefault?.();
    };

    const onDrop = (e) => {
      e?.preventDefault?.();
      const file = e?.dataTransfer?.files?.[0];
      applyFile(file);
    };

    const uploadFile = async () => {
      if (!selectedFile.value) {
        errorMessage.value = 'Selecciona o arrastra un archivo antes de subir.';
        return;
      }

      isUploading.value = true;
      errorMessage.value = '';

      try {
        const formData = new FormData();
        formData.append('file', selectedFile.value);

        const data = await api.postFormData('/api/v1/upload', formData);
        if (!data?.success) {
          throw new Error(data?.detail || data?.error || 'No se pudo subir el archivo');
        }

        uploadedUrl.value = data.url;
        emit('uploaded', { url: data.url, metadata: data, content_type: data.content_type });
        selectedFile.value = null;
        revokePreview();
        previewUrl.value = '';
      } catch (error) {
        errorMessage.value = error?.message || 'Error subiendo el archivo';
      } finally {
        isUploading.value = false;
      }
    };

    const previewKind = computed(() => {
      const f = selectedFile.value;
      if (!f?.type) return '';
      if (f.type.startsWith('video/')) return 'video';
      if (f.type === 'application/pdf') return 'pdf';
      return 'image';
    });

    return () => (
      <div class="perseo-image-uploader">
        <div class="uploader-header">
          <span>Imagen, vídeo o PDF</span>
          {uploadedUrl.value && (
            <a href={uploadedUrl.value} target="_blank" rel="noopener" class="uploader-link">
              Ver última subida
            </a>
          )}
        </div>

        <div
          class="uploader-body uploader-dropzone"
          onDragover={onDragOver}
          onDrop={onDrop}
        >
          <input
            type="file"
            accept={ACCEPT_ATTR}
            onChange={handleFileChange}
            disabled={isDisabled.value}
          />
          <button
            type="button"
            class="uploader-btn"
            onClick={uploadFile}
            disabled={isDisabled.value || !selectedFile.value || isUploading.value}
          >
            {isUploading.value ? 'Subiendo…' : 'Subir archivo'}
          </button>
          {previewUrl.value && previewKind.value === 'image' && (
            <div class="uploader-preview">
              <img src={previewUrl.value} alt="Vista previa" />
              <button type="button" class="uploader-reset" onClick={reset}>
                ✕
              </button>
            </div>
          )}
          {previewUrl.value && previewKind.value === 'video' && (
            <div class="uploader-preview uploader-preview-video">
              <video src={previewUrl.value} controls muted playsInline class="uploader-video" />
              <button type="button" class="uploader-reset" onClick={reset}>
                ✕
              </button>
            </div>
          )}
          {previewUrl.value && previewKind.value === 'pdf' && (
            <div class="uploader-preview uploader-preview-pdf">
              <span class="pdf-label">PDF</span>
              <button type="button" class="uploader-reset" onClick={reset}>
                ✕
              </button>
            </div>
          )}
        </div>
        <p class="uploader-dnd-hint">Arrastra y suelta aquí (máx. 100 MB).</p>

        {errorMessage.value && <p class="uploader-error">{errorMessage.value}</p>}
        {isDisabled.value && (
          <p class="uploader-hint">Las cargas están deshabilitadas en esta instancia.</p>
        )}
      </div>
    );
  },
});
