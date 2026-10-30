/** Display helpers shared across pages. */

/** Prices arrive as decimal strings ("0.00", "149.50"). Zero means the course is free. */
export function formatPrice(price: string): string {
  if (price === "0.00" || price === "0" || price === "") {
    return "مجانًا";
  }
  const amount = Number(price);
  if (Number.isNaN(amount)) return price;
  return `$${amount.toFixed(2)}`;
}

/** Localized (Arabic) date for list rows and timestamps. */
export function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("ar", { year: "numeric", month: "long", day: "numeric" });
}
