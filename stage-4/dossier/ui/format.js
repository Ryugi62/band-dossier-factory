// Formatting for people: field labels, values, money, timestamps, kinds, providers and states.
export const FIELDS = ['legal_name', 'hq_city', 'ceo', 'founded_year', 'headcount_range', 'funding_total'];

export const FIELD_LABELS = {
  legal_name: 'Legal name',
  hq_city: 'Headquarters city',
  ceo: 'Chief executive',
  founded_year: 'Founded',
  headcount_range: 'Headcount',
  funding_total: 'Total funding',
};

const KIND_LABELS = { own: 'Company site', filing: 'Filing registry', news: 'News report', aggregator: 'Data aggregator' };
const PROVIDER_LABELS = { nimble: 'Nimble', tavily: 'Tavily', kernel: 'Kernel', browserbase: 'Browserbase' };
const STATUS_LABELS = { known: 'Known', contested: 'Contested', unknown: 'Unknown' };

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const dateTime = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short',
});
const dateOnly = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

export function formatValue(field, value) {
  if (value === null || value === undefined) return '—';
  if (field === 'funding_total') return `${money.format(value)} (${'$'}${compact.format(value)})`;
  if (field === 'headcount_range') return `${value} employees`;
  return String(value);
}

// The API value as text for data-value: strings unchanged, integers as plain digits.
export function dataValue(value) {
  return typeof value === 'number' ? String(Math.trunc(value)) : String(value);
}

export function formatTimestamp(rfc3339) {
  const d = new Date(rfc3339);
  return Number.isNaN(d.getTime()) ? String(rfc3339) : dateTime.format(d);
}

export function formatDate(rfc3339) {
  const d = new Date(rfc3339);
  return Number.isNaN(d.getTime()) ? String(rfc3339) : dateOnly.format(d);
}

export function kindLabel(kind) {
  return kind ? KIND_LABELS[kind] || kind : 'Imported source';
}

export function providerLabel(provider) {
  return PROVIDER_LABELS[provider] || provider;
}

export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}

export function unitsLabel(units) {
  return `${units} ${units === 1 ? 'unit' : 'units'} spent`;
}

export function hostOf(url) {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

// Domain normalisation as the API does it (stage-1 §4); null when invalid.
export function normaliseDomain(raw) {
  let d = String(raw).trim().toLowerCase();
  if (d.endsWith('.')) d = d.slice(0, -1);
  if (d.startsWith('www.')) d = d.slice(4);
  const label = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
  const labels = d.split('.');
  if (d.length > 253 || labels.length < 2 || !labels.every((l) => label.test(l))) return null;
  return d;
}
