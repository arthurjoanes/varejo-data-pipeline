// Local store/day facts only. Money stays in integer centavos through every sum.
function salesMinor(value) {
  if (value === null || value === undefined) return null;
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(String(value));
  if (!match) return null;
  return (BigInt(match[2]) * 100n + BigInt((match[3] || '').padEnd(2, '0'))) * (match[1] ? -1n : 1n);
}
function salesInteger(value) {
  if (typeof value === 'number' && !Number.isSafeInteger(value)) return null;
  return value !== null && value !== undefined && /^-?\d+$/.test(String(value)) ? BigInt(value) : null;
}
function salesMoney(value) {
  if (value === null) return '—';
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? '-' : ''}R$ ${(absolute / 100n).toLocaleString('pt-BR')},${String(absolute % 100n).padStart(2, '0')}`;
}
function sliceSales(rows, from, to, store) {
  if (from && to && from > to) throw new RangeError('A data inicial deve vir antes da final.');
  const selected = rows.filter(row => (!from || row.business_date >= from) && (!to || row.business_date <= to) && (!store || row.store_id === store));
  const sum = (items, field, parse) => {
    if (!items.length) return null;
    const values = items.map(row => parse(row[field]));
    return values.some(value => value === null) ? null : values.reduce((total, value) => total + value, 0n);
  };
  const dates = [...new Set(selected.map(row => row.business_date))].sort();
  return {
    rows: selected, revenue: sum(selected, 'net_revenue_brl', salesMinor),
    sales: sum(selected, 'sales_count', salesInteger), units: sum(selected, 'units', salesInteger),
    daily: dates.map(day => ({ day, revenue: sum(selected.filter(row => row.business_date === day), 'net_revenue_brl', salesMinor) })),
  };
}
function recentSalesPeriod(rows, days) {
  const last = rows.map(row => row.business_date).sort().at(-1);
  if (!last) return { from: '', to: '' };
  return { from: new Date(Date.parse(`${last}T00:00:00Z`) - (days - 1) * 86400000).toISOString().slice(0,10), to: last };
}
