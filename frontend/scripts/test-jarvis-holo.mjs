// Prueba de detectHoloRequest (paneles holograma del orbe) sin vitest: esbuild (ya incluido con vite).
// Uso (desde frontend/):  node scripts/test-jarvis-holo.mjs
// Sale con codigo != 0 si algun caso falla.
import { build } from 'esbuild';
import { tmpdir } from 'os';
import { join, resolve } from 'path';
import { pathToFileURL } from 'url';

const entry = resolve('src/utils/jarvisHoloPanels.ts');
const out = join(tmpdir(), `jarvis-holo-test-${process.pid}.mjs`);
await build({ entryPoints: [entry], bundle: true, format: 'esm', platform: 'node', outfile: out, logLevel: 'error' });
const { detectHoloRequest } = await import(pathToFileURL(out).href);

const cases = [
  // Abren panel: sin periodo, o con la coletilla que el panel de verdad aplica.
  ['enséñame la facturación', 'billing'],
  ['muéstrame las facturas', 'billing'],
  ['facturas', 'billing'],
  ['enséñame las facturas recientes', 'billing'],
  ['enséñame las tareas', 'tasks'],
  ['muéstrame las tareas de las últimas 24 horas', 'tasks'],
  ['abre el marketing', 'marketing'],
  ['enséñame la actividad', 'activity'],
  ['muéstrame la actividad del agente', 'activity'],
  ['enséñame la actividad de los últimos 7 días', 'activity'],
  ['oye zeus, enséñame la facturación', 'billing'],
  // Periodo que el panel NO aplica -> null (va al chat del agente, que filtra de verdad).
  ['enséñame las facturas de hoy', null],
  ['muéstrame las facturas de hoy', null],
  ['¿me enseñas las facturas de ayer?', null],
  ['enséñame las facturas de la semana', null],
  ['muéstrame la facturación del mes', null],
  ['enséñame las facturas del trimestre', null],
  ['enséñame las facturas de este mes', null],
  ['muéstrame las facturas del 3 de octubre', null],
  ['enséñame las tareas de hoy', null],
  ['enséñame las tareas de la semana', null],
  ['enséñame la actividad de hoy', null],
  ['enséñame la actividad del mes', null],
  ['enséñame el marketing de hoy', null],
  ['muéstrame las campañas recientes', null],
  // Órdenes: nunca panel.
  ['crea una factura', null],
  ['lanza una campaña', null],
];

let fails = 0;
for (const [msg, want] of cases) {
  const got = detectHoloRequest(msg);
  const ok = got === want;
  if (!ok) fails += 1;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${JSON.stringify(msg)} -> ${got} (esperado ${want})`);
}
console.log(`\n${cases.length - fails}/${cases.length} casos correctos`);
process.exit(fails ? 1 : 0);
