import { authFetch, readApiResponse } from "@/lib/auth";

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

export type InventoryProductCreate = Omit<InventoryProduct, "id" | "current_stock">;

export type InventoryInboundCreate = {
  supply_id: number;
  quantity: number;
  vendor_name: string;
  clinic_id: number;
};

export type InventoryOutboundCreate = {
  supply_id: number;
  quantity: number;
  consumption_type: "clinical_use" | "expiry_waste";
  clinic_id: number;
};

const inventoryLoadError = "Unable to load inventory. Check your connection and try again.";
const historyLoadError = "Unable to load inventory history. Check your connection and try again.";

async function inventoryRequest<T>(path: string, fallback: string, options?: RequestInit): Promise<T> {
  const response = await authFetch(path, options);
  return readApiResponse<T>(response, fallback);
}

export function getInventoryProducts(): Promise<InventoryProduct[]> {
  return inventoryRequest("/inventory/products", inventoryLoadError);
}

export function getInventoryProduct(supplyId: number): Promise<InventoryProduct> {
  return inventoryRequest(
    `/inventory/products/${supplyId}`,
    "Unable to refresh this supply's available stock. Try again.",
  );
}

export function getInventoryOrders(): Promise<InventoryOrder[]> {
  return inventoryRequest("/inventory/orders", historyLoadError);
}

export function createInventoryProduct(payload: InventoryProductCreate): Promise<InventoryProduct> {
  return inventoryRequest("/inventory/products", "Unable to register the supply. Check the details and try again.", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createInventoryInboundOrder(payload: InventoryInboundCreate): Promise<unknown> {
  return inventoryRequest("/inventory/orders/inbound", "Unable to record the delivery. Check the details and try again.", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createInventoryOutboundOrder(payload: InventoryOutboundCreate): Promise<unknown> {
  return inventoryRequest("/inventory/orders/outbound", "Unable to record the consumption. Check the details and try again.", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

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
