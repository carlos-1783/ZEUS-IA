import { defineComponent, ref, computed } from 'vue';
import api from '@/services/api';
import { PERSEO_IMAGES_ENABLED } from '@/config';
import {
  MEDIA_UPLOAD_UI,
  resolveMediaUploadState,
} from '@/utils/mediaUploadPolicy';

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
  emits: ['uploaded', 'state-change'],
  setup(_, { emit }) {
    const selectedFile = ref(null);
    const previewUrl = ref('');
    const uploadedUrl = ref('');
    const isUploading = ref(false);
    const errorMessage = ref('');

    const isDisabled = computed(() => !PERSEO_IMAGES_ENABLED);

    const uiState = computed(() =>
      resolveMediaUploadState({
        isUploading: isUploading.value,
        hasError: Boolean(errorMessage.value),
        hasUploaded: Boolean(uploadedUrl.value),
        hasFile: Boolean(selectedFile.value),
      }),
    );

    const revokePreview = () => {
      if (previewUrl.value) {
        URL.revokeObjectURL(previewUrl.value);
      }
    };

    const clearError = () => {
      errorMessage.value = '';
    };

    const resetSelection = () => {
      selectedFile.value = null;
      revokePreview();
      previewUrl.value = '';
      clearError();
    };

    const resetAll = () => {
      resetSelection();
      uploadedUrl.value = '';
    };

    const applyFile = (file) => {
      if (!file) return;
      revokePreview();
      uploadedUrl.value = '';
      if (!ALLOWED_TYPES.includes(file.type)) {
        errorMessage.value = MEDIA_UPLOAD_UI.error.show;
        return;
      }
      selectedFile.value = file;
      previewUrl.value = URL.createObjectURL(file);
      clearError();
      emit('state-change', { state: 'file_selected', file });
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
        return;
      }

      isUploading.value = true;
      clearError();
      emit('state-change', { state: 'uploading' });

      try {
        const formData = new FormData();
        formData.append('file', selectedFile.value);

        const data = await api.postFormData('/api/v1/upload', formData);
        if (!data?.success) {
          throw new Error(data?.detail || data?.error || MEDIA_UPLOAD_UI.error.show);
        }

        uploadedUrl.value = data.url;
        emit('uploaded', {
          url: data.url,
          metadata: data,
          content_type: data.content_type,
          input_type: 'file',
        });
        emit('state-change', { state: 'uploaded', url: data.url });
        selectedFile.value = null;
        revokePreview();
        previewUrl.value = '';
      } catch (error) {
        errorMessage.value = error?.message || MEDIA_UPLOAD_UI.error.show;
        emit('state-change', { state: 'error', message: errorMessage.value });
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

    const statusMessage = computed(() => {
      const state = uiState.value;
      if (state === 'idle') return MEDIA_UPLOAD_UI.idle;
      if (state === 'error') {
        return {
          show: errorMessage.value || MEDIA_UPLOAD_UI.error.show,
          type: 'error',
        };
      }
      if (state === 'uploaded') return MEDIA_UPLOAD_UI.uploaded;
      if (state === 'uploading') {
        return { show: 'Subiendo archivo…', type: 'neutral' };
      }
      return null;
    });

    return () => (
      <div class="perseo-image-uploader" data-upload-state={uiState.value}>
        <div class="uploader-header">
          <span>Imagen, vídeo o PDF</span>
          {uiState.value === 'uploaded' && uploadedUrl.value && (
            <a href={uploadedUrl.value} target="_blank" rel="noopener" class="uploader-link">
              Ver archivo subido
            </a>
          )}
        </div>

        {statusMessage.value && (
          <p
            class={[
              'uploader-status',
              statusMessage.value.type === 'error'
                ? 'uploader-error'
                : statusMessage.value.type === 'success'
                  ? 'uploader-success'
                  : 'uploader-neutral',
            ]}
          >
            {statusMessage.value.show}
          </p>
        )}

        <div
          class="uploader-body uploader-dropzone"
          onDragover={onDragOver}
          onDrop={onDrop}
        >
          <input
            type="file"
            accept={ACCEPT_ATTR}
            onChange={handleFileChange}
            disabled={isDisabled.value || isUploading.value}
          />
          <button
            type="button"
            class="uploader-btn"
            onClick={uploadFile}
            disabled={isDisabled.value || uiState.value !== 'file_selected' || isUploading.value}
          >
            {isUploading.value ? 'Subiendo…' : 'Subir archivo'}
          </button>
          {uiState.value === 'file_selected' && previewUrl.value && previewKind.value === 'image' && (
            <div class="uploader-preview">
              <img src={previewUrl.value} alt="Vista previa" />
              <button type="button" class="uploader-reset" onClick={resetSelection}>
                ✕
              </button>
            </div>
          )}
          {uiState.value === 'file_selected' && previewUrl.value && previewKind.value === 'video' && (
            <div class="uploader-preview uploader-preview-video">
              <video src={previewUrl.value} controls muted playsInline class="uploader-video" />
              <button type="button" class="uploader-reset" onClick={resetSelection}>
                ✕
              </button>
            </div>
          )}
          {uiState.value === 'file_selected' && previewUrl.value && previewKind.value === 'pdf' && (
            <div class="uploader-preview uploader-preview-pdf">
              <span class="pdf-label">PDF · {selectedFile.value?.name}</span>
              <button type="button" class="uploader-reset" onClick={resetSelection}>
                ✕
              </button>
            </div>
          )}
        </div>
        <p class="uploader-dnd-hint">Arrastra y suelta aquí (máx. 100 MB). La subida no envía mensajes al agente.</p>

        {uiState.value === 'uploaded' && (
          <button type="button" class="uploader-btn uploader-btn-secondary" onClick={resetAll}>
            Subir otro archivo
          </button>
        )}

        {isDisabled.value && (
          <p class="uploader-hint">Las cargas están deshabilitadas en esta instancia.</p>
        )}
      </div>
    );
  },
});
