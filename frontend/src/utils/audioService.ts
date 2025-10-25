import { ref } from 'vue';

type SoundType = 'activation' | 'deactivation' | 'success' | 'error' | 'notification' | 'startup' | 'shutdown' | 'alert' | 'confirm';

interface SoundOptions {
  volume?: number;
  pitch?: number;
  duration?: number;
}

// Audio context for Web Audio API
let audioContext: AudioContext | null = null;
const audioEnabled = ref<boolean>(true);
const activeOscillators = new Set<OscillatorNode>();
const activeBuffers = new Set<AudioBufferSourceNode>();

// Initialize audio context on user interaction
const initAudioContext = (): AudioContext => {
  if (!audioContext) {
    try {
      audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      console.log('Audio context initialized');
    } catch (error) {
      console.error('Failed to initialize audio context:', error);
      throw error;
    }
  }
  return audioContext;
};

// Clean up audio resources
const cleanupAudio = () => {
  // Stop all oscillators
  activeOscillators.forEach(osc => {
    try {
      osc.stop();
      osc.disconnect();
    } catch (e) {
      console.warn('Error cleaning up oscillator:', e);
    }
  });
  activeOscillators.clear();
  
  // Stop all buffer sources
  activeBuffers.forEach(buffer => {
    try {
      buffer.stop();
      buffer.disconnect();
    } catch (e) {
      console.warn('Error cleaning up audio buffer:', e);
    }
  });
  activeBuffers.clear();
  
  if (audioContext) {
    if (audioContext.state !== 'closed') {
      audioContext.close().catch(console.error);
    }
    audioContext = null;
  }
};

// Generate a sound with configurable parameters
const generateSound = (options: SoundOptions = {}): { play: () => void; stop: () => void } => {
  const {
    volume = 0.5,
    pitch = 440,
    duration = 200,
  } = options;
  
  let oscillator: OscillatorNode | null = null;
  let gainNode: GainNode | null = null;
  
  const play = () => {
    if (!audioEnabled.value) return;
    
    try {
      const audioCtx = initAudioContext();
      
      // Resume audio context if it was suspended
      if (audioCtx.state === 'suspended') {
        audioCtx.resume().catch(console.error);
      }
      
      oscillator = audioCtx.createOscillator();
      gainNode = audioCtx.createGain();
      
      oscillator.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      
      oscillator.type = 'sine';
      oscillator.frequency.value = pitch;
      gainNode.gain.value = volume;
      
      // Add to active oscillators
      if (oscillator) {
        activeOscillators.add(oscillator);
        
        oscillator.onended = () => {
          activeOscillators.delete(oscillator!);
          oscillator?.disconnect();
          gainNode?.disconnect();
        };
        
        oscillator.start();
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration / 1000);
        
        setTimeout(() => {
          try {
            if (oscillator) {
              oscillator.stop();
              activeOscillators.delete(oscillator);
              oscillator.disconnect();
              gainNode?.disconnect();
            }
          } catch (e) {
            console.warn('Error stopping oscillator:', e);
          }
        }, duration + 50); // Add small buffer
      }
      
    } catch (error) {
      console.error('Error playing sound:', error);
    }
  };
  
  const stop = () => {
    if (oscillator) {
      try {
        oscillator.stop();
        activeOscillators.delete(oscillator);
        oscillator.disconnect();
        gainNode?.disconnect();
      } catch (e) {
        console.warn('Error stopping sound:', e);
      }
    }
  };
  
  return { play, stop };
};

// System sounds with more variety and better audio quality
const playSound = (type: SoundType, options: SoundOptions = {}): void => {
  if (!audioEnabled.value) return;
  
  const sounds: Record<SoundType, () => void> = {
    activation: () => {
      // Rising chime for activation
      const sound = generateSound({
        volume: 0.4,
        pitch: 880,
        duration: 500,
        ...options
      });
      sound.play();
    },
    deactivation: () => {
      // Falling chime for deactivation
      const sound = generateSound({
        volume: 0.4,
        pitch: 440,
        duration: 600,
        ...options
      });
      sound.play();
    },
    success: () => {
      // Positive confirmation sound
      const sound = generateSound({
        volume: 0.3,
        pitch: 1046.5, // High C
        duration: 150,
        ...options
      });
      sound.play();
    },
    error: () => {
      // Error/warning sound
      const sound1 = generateSound({ volume: 0.3, pitch: 440, duration: 100 });
      const sound2 = generateSound({ volume: 0.3, pitch: 349.23, duration: 100 });
      
      sound1.play();
      setTimeout(() => sound2.play(), 120);
    },
    notification: () => {
      // Subtle notification sound
      const sound = generateSound({
        volume: 0.2,
        pitch: 1318.5, // E6
        duration: 100,
        ...options
      });
      sound.play();
    },
    startup: () => {
      // System startup sound
      const sound = generateSound({
        volume: 0.5,
        pitch: 523.25, // C5
        duration: 200,
        ...options
      });
      sound.play();
    },
    shutdown: () => {
      // System shutdown sound
      const sound = generateSound({
        volume: 0.5,
        pitch: 261.63, // C4
        duration: 300,
        ...options
      });
      sound.play();
    },
    alert: () => {
      // Urgent alert sound
      const sound1 = generateSound({ volume: 0.4, pitch: 880, duration: 100 });
      const sound2 = generateSound({ volume: 0.4, pitch: 587.33, duration: 100 });
      
      sound1.play();
      setTimeout(() => sound2.play(), 100);
    },
    confirm: () => {
      // Confirmation beep
      const sound = generateSound({
        volume: 0.3,
        pitch: 784.0, // G5
        duration: 80,
        ...options
      });
      sound.play();
    }
  };
  
  try {
    sounds[type]?.();
  } catch (error) {
    console.error(`Error playing sound '${type}':`, error);
  }
};

// Legacy functions for backward compatibility
const playActivationSound = () => playSound('activation');
const playDeactivationSound = () => playSound('deactivation');
const playSuccessSound = () => playSound('success');
const playErrorSound = () => playSound('error');
const playNotificationSound = () => playSound('notification');

// Toggle audio on/off
const toggleAudio = (enabled: boolean): void => {
  audioEnabled.value = enabled;
  
  if (!enabled) {
    // Stop all currently playing sounds when audio is disabled
    cleanupAudio();
  }
  
  // Save preference to localStorage
  if (typeof localStorage !== 'undefined') {
    try {
      localStorage.setItem('audioEnabled', String(enabled));
    } catch (e) {
      console.warn('Failed to save audio preference:', e);
    }
  }
};

// Check if audio is enabled
const isAudioEnabled = (): boolean => {
  // Load preference from localStorage if available
  if (typeof localStorage !== 'undefined') {
    try {
      const saved = localStorage.getItem('audioEnabled');
      if (saved !== null) {
        audioEnabled.value = saved === 'true';
      }
    } catch (e) {
      console.warn('Failed to load audio preference:', e);
    }
  }
  
  return audioEnabled.value;
};

// Preload audio context on user interaction
const preloadAudio = (): void => {
  if (typeof window === 'undefined') return;
  
  const handleInteraction = () => {
    // Performance: Defer execution para no bloquear el click handler
    Promise.resolve().then(() => {
      try {
        // Initialize audio context on first interaction
        initAudioContext();
        
        // Load any additional audio assets here
        // loadAudioAsset('notification', '/sounds/notification.mp3');
        
        console.log('Audio system ready');
      } catch (error) {
        console.error('Error initializing audio:', error);
      }
    });
    
    // Performance: Remover listeners inmediatamente para no ejecutar múltiples veces
    window.removeEventListener('click', handleInteraction);
    window.removeEventListener('keydown', handleInteraction);
    window.removeEventListener('touchstart', handleInteraction);
  };

  // Add interaction listeners
  window.addEventListener('click', handleInteraction, { once: true, passive: true });
  window.addEventListener('keydown', handleInteraction, { once: true, passive: true });
  window.addEventListener('touchstart', handleInteraction, { once: true, passive: true });
  
  // Set up beforeunload to clean up audio resources
  window.addEventListener('beforeunload', cleanupAudio);
};

// Performance: Audio COMPLETAMENTE DESHABILITADO para eliminar violations
// initAudioSystem() NO se llama nunca - sin listeners de visibilitychange

// Export all functions as a default object
export default {
  // Core functions
  playSound,
  toggleAudio,
  isAudioEnabled,
  
  // Legacy functions
  playActivationSound,
  playDeactivationSound,
  playSuccessSound,
  playErrorSound,
  playNotificationSound,
  
  // Utility functions
  preloadAudio,
  cleanupAudio,
  initAudioSystem
};

// Export types separately
export type { SoundType, SoundOptions };
