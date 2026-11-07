export function money(amount: string | number, currency = "KES"): string {
  const value = Number(amount);
  return `${currency} ${value.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function day(iso: string | null | undefined): string {
  if (!iso) return "-";
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString("en-KE", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function words(code: string): string {
  const text = code.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function can(permissions: string[] | undefined, permission: string): boolean {
  return Boolean(permissions?.includes(permission));
}

/** One sentence describing a contribution rule, for people rather than databases. */
export function describeContributions(config: Record<string, string | number | boolean>, currency: string) {
  const amount =
    config.amount_type === "fixed"
      ? money(String(config.minimum_amount), currency)
      : `${money(String(config.minimum_amount), currency)} to ${money(String(config.maximum_amount), currency)}`;
  const when =
    config.frequency === "monthly"
      ? `every month on day ${config.due_day}`
      : `every week on ${words(String(config.due_weekday))}`;
  return `${amount} ${when}, ${config.grace_period_days} grace days, ${money(String(config.late_penalty), currency)} late penalty`;
}
