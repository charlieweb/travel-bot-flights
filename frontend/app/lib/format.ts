/** USD like Google Flights: $1,592 (commas, no .00 when whole dollars). */
export function formatUsdPrice(price: number): string {
  const hasCents = Math.abs(price - Math.round(price)) > 0.001
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: hasCents ? 2 : 0,
    maximumFractionDigits: hasCents ? 2 : 0,
  }).format(price)
}

/** Readable date like "Thu, Dec 10, 2026". */
export function formatDate(iso: string): string {
  const d = new Date(iso.includes('T') ? iso : `${iso}T12:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/** Country code (e.g. "GB") → readable name ("United Kingdom"). Falls back to the code. */
const regions = new Intl.DisplayNames(['en'], { type: 'region' })
export function formatCountry(isoCode: string): string {
  if (!isoCode) return ''
  try {
    return regions.of(isoCode) || isoCode
  } catch {
    return isoCode
  }
}
