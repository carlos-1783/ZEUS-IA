type Station = 'kitchen' | 'bar';

type CartItem = Record<string, any>;

type StationLine = {
  product_id: string | null;
  name: string;
  quantity: number;
  notes: string;
};

type StationTicket = {
  station: Station;
  tableLabel: string;
  generatedAt: string;
  lines: StationLine[];
};

const BLE_PRINTER_STORAGE_KEY = 'zeus-tpv-ble-printer-bindings-v1';
const DEFAULT_SERVICE_CANDIDATES = [0xFFE0, 0xFF00, 0x18F0];

const CATEGORY_TO_STATION: Array<{ station: Station; keywords: string[] }> = [
  {
    station: 'bar',
    keywords: ['bebida', 'cerveza', 'vino', 'cocktail', 'coctel', 'refresco', 'cafe', 'caf', 'infusion'],
  },
  {
    station: 'kitchen',
    keywords: ['comida', 'plato', 'tapa', 'racion', 'bocadillo', 'hamburguesa', 'pizza', 'postre', 'cocina'],
  },
];

function normalizeText(value: string): string {
  return (value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function safeNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function getStationFromItem(item: CartItem): Station {
  const metaStation = normalizeText(
    item?.metadata?.station || item?.product?.metadata?.station || item?.station || '',
  );
  if (metaStation === 'bar' || metaStation === 'barra') return 'bar';
  if (metaStation === 'kitchen' || metaStation === 'cocina') return 'kitchen';

  const bucket = normalizeText(
    `${item?.category || ''} ${item?.product?.category || ''} ${item?.name || ''} ${item?.product?.name || ''}`,
  );
  for (const rule of CATEGORY_TO_STATION) {
    if (rule.keywords.some((kw) => bucket.includes(kw))) {
      return rule.station;
    }
  }
  return 'kitchen';
}

function stationLabel(station: Station): string {
  return station === 'bar' ? 'BARRA' : 'COCINA';
}

function getBindings(): Record<Station, string | null> {
  try {
    const raw = localStorage.getItem(BLE_PRINTER_STORAGE_KEY);
    if (!raw) return { kitchen: null, bar: null };
    const parsed = JSON.parse(raw);
    return {
      kitchen: typeof parsed?.kitchen === 'string' ? parsed.kitchen : null,
      bar: typeof parsed?.bar === 'string' ? parsed.bar : null,
    };
  } catch {
    return { kitchen: null, bar: null };
  }
}

function setBinding(station: Station, deviceId: string): void {
  const current = getBindings();
  current[station] = deviceId;
  localStorage.setItem(BLE_PRINTER_STORAGE_KEY, JSON.stringify(current));
}

async function findWritableCharacteristic(server: any): Promise<any | null> {
  const services = await server.getPrimaryServices();
  for (const service of services) {
    const chars = await service.getCharacteristics();
    for (const ch of chars) {
      if (ch.properties?.write || ch.properties?.writeWithoutResponse) {
        return ch;
      }
    }
  }
  return null;
}

async function getOrRequestDeviceForStation(station: Station): Promise<any> {
  const navBluetooth = (navigator as any).bluetooth as any;
  if (!navBluetooth) {
    throw new Error('Este navegador no soporta Web Bluetooth.');
  }

  const bindings = getBindings();
  const expectedId = bindings[station];
  if (expectedId && typeof (navBluetooth as any).getDevices === 'function') {
    const devices = await (navBluetooth as any).getDevices();
    const match = devices.find((d: any) => d.id === expectedId);
    if (match) return match;
  }

  const requestOptions: any = {
    acceptAllDevices: true,
    optionalServices: DEFAULT_SERVICE_CANDIDATES,
  };
  const device = await navBluetooth.requestDevice(requestOptions);
  if (device?.id) setBinding(station, device.id);
  return device;
}

function buildTicketText(ticket: StationTicket): string {
  const lines = ticket.lines
    .map((l) => {
      const note = l.notes ? ` (${l.notes})` : '';
      return `${l.quantity} x ${l.name}${note}`;
    })
    .join('\n');
  return [
    `ZEUS TPV - ${stationLabel(ticket.station)}`,
    `Mesa: ${ticket.tableLabel}`,
    `Hora: ${new Date(ticket.generatedAt).toLocaleString('es-ES')}`,
    '',
    lines,
    '',
    '---',
    'COMANDA',
    '',
  ].join('\n');
}

function toEscPosBytes(text: string): Uint8Array {
  const encoder = new TextEncoder();
  const init = new Uint8Array([0x1b, 0x40]);
  const body = encoder.encode(text);
  const lf = new Uint8Array([0x0a, 0x0a, 0x0a]);
  const cut = new Uint8Array([0x1d, 0x56, 0x41, 0x10]);
  const out = new Uint8Array(init.length + body.length + lf.length + cut.length);
  out.set(init, 0);
  out.set(body, init.length);
  out.set(lf, init.length + body.length);
  out.set(cut, init.length + body.length + lf.length);
  return out;
}

export function buildKitchenBarTickets(cartItems: CartItem[], tableName?: string | null): StationTicket[] {
  const byStation: Record<Station, StationLine[]> = { kitchen: [], bar: [] };
  for (const item of cartItems || []) {
    const station = getStationFromItem(item);
    const qty = Math.max(1, safeNumber(item.quantity, 1));
    byStation[station].push({
      product_id: item.product_id || item.id || item.product?.id || null,
      name: item.name || item.product?.name || 'Producto',
      quantity: qty,
      notes: String(item.notes || item.observations || '').trim(),
    });
  }

  const tableLabel = tableName && String(tableName).trim() ? String(tableName).trim() : 'Sin mesa';
  const now = new Date().toISOString();
  const tickets: StationTicket[] = [];
  if (byStation.kitchen.length) tickets.push({ station: 'kitchen', tableLabel, generatedAt: now, lines: byStation.kitchen });
  if (byStation.bar.length) tickets.push({ station: 'bar', tableLabel, generatedAt: now, lines: byStation.bar });
  return tickets;
}

export async function printTicketViaBluetooth(ticket: StationTicket): Promise<void> {
  const device = await getOrRequestDeviceForStation(ticket.station);
  const server = await device.gatt?.connect();
  if (!server) throw new Error('No se pudo abrir canal Bluetooth con la impresora.');
  const writable = await findWritableCharacteristic(server);
  if (!writable) throw new Error('No se encontró característica de escritura en la impresora Bluetooth.');

  const data = toEscPosBytes(buildTicketText(ticket));
  const chunkSize = 180;
  for (let i = 0; i < data.length; i += chunkSize) {
    const chunk = data.slice(i, i + chunkSize);
    await writable.writeValue(chunk);
  }
}

export function buildPlainTextTickets(tickets: StationTicket[]): string {
  return tickets.map((t) => buildTicketText(t)).join('\n\n====================\n\n');
}
