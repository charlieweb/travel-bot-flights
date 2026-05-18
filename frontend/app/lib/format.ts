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
