// Shared INR/paise formatting for the new finance ledger pages. Money is
// integer paise everywhere on the wire; this is the only place that divides.
export function formatINR(paise: number | null | undefined): string {
  const rupees = (paise ?? 0) / 100;
  return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function rupeesToPaise(input: string): number {
  const value = Number.parseFloat(input);
  if (Number.isNaN(value)) return 0;
  return Math.round(value * 100);
}

export function currentFyLabel(on: Date = new Date()): string {
  const year = on.getMonth() >= 3 ? on.getFullYear() : on.getFullYear() - 1; // getMonth() 0-indexed; April = 3
  return `${year}-${String((year + 1) % 100).padStart(2, "0")}`;
}
