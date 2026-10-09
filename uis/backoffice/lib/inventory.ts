export type InventoryProduct = {
  id: number;
  name: string;
  sku: string;
  category: "ppe" | "wound_care" | "diagnostics" | "medications" | "consumables";
  unit: "box" | "unit" | "pack" | "vial";
  country: "US" | "UK";
  current_stock: number;
};

export type InventoryOrder = {
  order_type: "inbound" | "outbound";
  order_id: number;
  supply: InventoryProduct;
  quantity: number;
  clinic_id: number;
  created_at: string;
  user_uuid: string;
  vendor_name?: string | null;
  consumption_type?: "clinical_use" | "expiry_waste" | null;
};

export function lowStockThreshold(products: InventoryProduct[]): number {
  // The Phase 6 contract has no per-product reorder point. Use a consistent UI
  // advisory derived from returned available stock, never a company policy.
  const positiveStocks = products.map(({ current_stock }) => current_stock).filter((stock) => stock > 0).sort((a, b) => a - b);
  if (!positiveStocks.length) return 0;
  return Math.max(1, Math.ceil(positiveStocks[Math.floor(positiveStocks.length / 2)] * 0.25));
}

export function formatInventoryDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
