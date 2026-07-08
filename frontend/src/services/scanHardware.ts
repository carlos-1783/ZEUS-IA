/**
 * Capa hardware de escaneo — Web PWA + Capacitor nativo (iOS/Android).
 */

export type ScanRuntime = {
  native: boolean
  platform: string
  nfcMode: 'native' | 'web' | 'manual'
}

export async function getScanRuntime(): Promise<ScanRuntime> {
  try {
    const { Capacitor } = await import('@capacitor/core')
    const native = Capacitor.isNativePlatform()
    return {
      native,
      platform: Capacitor.getPlatform(),
      nfcMode: native ? 'native' : typeof (window as unknown as { NDEFReader?: unknown }).NDEFReader === 'function' ? 'web' : 'manual',
    }
  } catch {
    const webNfc = typeof (window as unknown as { NDEFReader?: unknown }).NDEFReader === 'function'
    return { native: false, platform: 'web', nfcMode: webNfc ? 'web' : 'manual' }
  }
}

export async function capturePhotoBase64(): Promise<string> {
  const runtime = await getScanRuntime()
  if (runtime.native) {
    const { Camera, CameraResultType, CameraSource } = await import('@capacitor/camera')
    const photo = await Camera.getPhoto({
      quality: 92,
      allowEditing: false,
      resultType: CameraResultType.Base64,
      source: CameraSource.Camera,
      correctOrientation: true,
    })
    const b64 = photo.base64String || ''
    if (!b64) throw new Error('No se pudo capturar la foto')
    return `data:image/jpeg;base64,${b64}`
  }
  throw new Error('USE_INLINE_CAMERA')
}

export async function startNativeNfc(onRead: (text: string) => void): Promise<(() => void) | null> {
  const runtime = await getScanRuntime()
  if (!runtime.native) return null
  try {
    const { CapacitorNfc } = await import('@capgo/capacitor-nfc')
    const listener = await CapacitorNfc.addListener('nfcTagScanned', (event: { tag?: { message?: string; data?: string } }) => {
      const data = event?.tag?.message || event?.tag?.data || ''
      if (data) onRead(data)
    })
    await CapacitorNfc.startScanning()
    return () => {
      listener.remove()
      CapacitorNfc.stopScanning().catch(() => undefined)
    }
  } catch {
    return null
  }
}
