// Prueba del composable useJarvisVoice sin vitest: esbuild (ya incluido con vite) + mocks del navegador.
// Uso (desde frontend/):  node scripts/test-jarvis-voice.mjs [ruta/al/composable.ts]
// Sale con codigo != 0 si algun caso falla.
import { build } from 'esbuild';
import { tmpdir } from 'os';
import { join, resolve } from 'path';
import { pathToFileURL } from 'url';

const entry = resolve(process.argv[2] || 'src/composables/useJarvisVoice.ts');
const out = join(tmpdir(), `jarvis-voice-test-${process.pid}.mjs`);
await build({ entryPoints: [entry], bundle: true, format: 'esm', platform: 'node', outfile: out, logLevel: 'error' });

// reloj falso: el watchdog se prueba sin esperar
let now = 0;
let timers = [];
let nextId = 1;
globalThis.setTimeout = (fn, ms) => { const id = nextId++; timers.push({ id, at: now + ms, fn }); return id; };
globalThis.clearTimeout = (id) => { timers = timers.filter((t) => t.id !== id); };
const advance = (ms) => {
  const end = now + ms;
  for (;;) {
    const due = timers.filter((t) => t.at <= end).sort((a, b) => a.at - b.at)[0];
    if (!due) break;
    timers = timers.filter((t) => t !== due);
    now = due.at;
    due.fn();
  }
  now = end;
};

// mocks de la Web Speech API
let rec;
let recCalls;
class R { constructor() { rec = this; } start() { recCalls.start++; } stop() { recCalls.stop++; } abort() {} }
class U { constructor(t) { this.text = t; } }
const synthMock = { speaking: false, pending: false, spoken: [], throwOnSpeak: false,
  getVoices: () => [{ lang: 'es-ES' }],
  speak(u) { if (this.throwOnSpeak) throw new Error('boom'); this.spoken.push(u); this.speaking = true; },
  cancel() { this.speaking = false; } };
globalThis.SpeechSynthesisUtterance = U;
globalThis.window = { webkitSpeechRecognition: R, speechSynthesis: synthMock };

const { useJarvisVoice, speakableText } = await import(pathToFileURL(out).href);
const origWarn = console.warn; console.warn = () => {}; // avisos de Vue por onUnmounted fuera de componente

let failed = 0;
const ok = (c, m) => { if (!c) { failed++; console.log('FAIL', m); } else console.log('ok  ', m); };
const ev = (t, fin = true) => ({ results: [Object.assign([{ transcript: t }], { isFinal: fin })] });
const fresh = (opts) => { recCalls = { start: 0, stop: 0 }; synthMock.spoken = []; synthMock.speaking = false; synthMock.throwOnSpeak = false; timers = []; return useJarvisVoice(opts); };

// --- casos base
{
  const finals = [];
  const v = fresh({ onFinal: (t) => finals.push(t) });
  ok(v.supported, 'soporte detectado');
  v.start(); ok(v.listening.value && recCalls.start === 1, 'start escucha');
  rec.onresult(ev('hola', false)); ok(finals.length === 0 && v.transcript.value === 'hola', 'parcial no se envia');
  rec.onresult(ev('hola final')); ok(finals[0] === 'hola final', 'final se envia');
  v.speak('Dime "confirmar" https://x.com/api/v1/e/1 ya /jarvis/evidence/document/1 fin');
  ok(synthMock.spoken[0].text === 'Dime "confirmar" ya fin', 'URL y rutas no se leen: ' + synthMock.spoken[0].text);
  ok(v.speaking.value && !v.listening.value && recCalls.stop === 1, 'speaking para el reconocimiento');
  rec.onresult(ev('confirmar')); ok(finals.length === 1, 'transcripcion durante speaking descartada');
  ok(v.start() === false, 'no arranca mientras habla');
  synthMock.spoken[0].onend(); ok(!v.speaking.value, 'onend libera speaking');
  rec.onerror({ error: 'not-allowed' }); ok(/micrófono denegado/.test(v.error.value) && !v.listening.value, 'permiso denegado -> mensaje');
  ok(speakableText('ver /api/v1/x y www.a.com') === 'ver y', 'speakableText');
  v.dispose(); ok(!v.listening.value, 'dispose');
  delete window.webkitSpeechRecognition;
  const v2 = useJarvisVoice(); ok(!v2.supported && v2.start() === false && /no soporta/.test(v2.error.value), 'sin soporte -> mensaje y start false');
  window.webkitSpeechRecognition = R;
}

// --- 1. evento tardio de la utterance anterior no libera speaking
{
  const finals = [];
  const v = fresh({ onFinal: (t) => finals.push(t) });
  v.speak('uno'); const u1 = synthMock.spoken[0];
  v.speak('dos'); const u2 = synthMock.spoken[1];
  u1.onerror({ error: 'interrupted' });
  ok(v.speaking.value, 'onerror tardio de la anterior NO libera speaking');
  u1.onend();
  ok(v.speaking.value, 'onend tardio de la anterior NO libera speaking');
  ok(v.start() === false && recCalls.start === 0, 'el microfono no arranca mientras la vigente habla');
  rec = rec || null;
  v.speak('tres'); // fuerza creacion de rec no necesaria; comprobamos descarte con reconocimiento creado
  const w = fresh({ onFinal: (t) => finals.push(t) });
  w.start(); w.speak('uno'); const a = synthMock.spoken[0]; w.speak('dos');
  a.onend(); rec.onresult(ev('confirmar'));
  ok(finals.length === 0, 'tras evento tardio, "confirmar" oido del altavoz sigue descartado');
  synthMock.spoken[1].onend(); ok(!w.speaking.value, 'la vigente si libera speaking');
}

// --- 2. watchdog: onend nunca llega
{
  const v = fresh({});
  v.speak('Hola, esto es una respuesta de prueba');
  ok(v.speaking.value, 'speaking true tras speak');
  advance(1000); ok(v.speaking.value, 'watchdog no libera antes de tiempo');
  advance(60000); ok(!v.speaking.value, 'watchdog libera speaking si onend nunca llega');
  ok(v.start() === true, 'tras el watchdog el microfono vuelve a poder arrancar');
  const w = fresh({});
  w.speak('uno'); advance(1000); w.speak('dos');
  advance(2500); ok(w.speaking.value, 'el watchdog de la anterior no libera la utterance nueva');
  w.cancel(); ok(!w.speaking.value && timers.length === 0, 'cancel limpia speaking y temporizador');
  const d = fresh({}); d.speak('x'); d.dispose(); ok(timers.length === 0 && !d.speaking.value, 'dispose limpia temporizador');
}

// --- 3. speak lanza
{
  const v = fresh({});
  synthMock.throwOnSpeak = true;
  const r = v.speak('hola');
  ok(r === false && !v.speaking.value && /No se pudo reproducir/.test(v.error.value), 'speak que lanza -> speaking false y error claro');
  ok(timers.length === 0, 'speak que lanza no deja temporizador');
}

console.warn = origWarn;
console.log(failed ? `\n${failed} caso(s) FALLAN` : '\nTodos los casos OK');
process.exit(failed ? 1 : 0);
