import { describe, expect, it } from "vitest";
import { formatInventoryDate, InventoryProduct, lowStockThreshold } from "./inventory";

const product = (id: number, stock: number): InventoryProduct => ({
  id, name: `Supply ${id}`, sku: `SKU-${id}`, category: "ppe", unit: "box", country: "US", current_stock: stock,
});

describe("inventory view helpers", () => {
  it("derives a conservative relative advisory threshold without storing it as policy", () => {
    expect(lowStockThreshold([product(1, 0), product(2, 20), product(3, 40)])).toBe(10);
    expect(lowStockThreshold([product(1, 0)])).toBe(0);
    expect(lowStockThreshold([])).toBe(0);
  });

  it("formats valid dates and safely handles invalid values", () => {
    expect(formatInventoryDate("not-a-date")).toBe("Date unavailable");
    expect(formatInventoryDate("2026-01-01T00:00:00Z")).not.toBe("Date unavailable");
  });
});
