"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { ApiRequestError, authFetch, readApiResponse } from "@/lib/auth";
import { formatInventoryDate, InventoryOrder, InventoryProduct, lowStockThreshold } from "@/lib/inventory";
import "../operations.css";

const productCategories = ["ppe", "wound_care", "diagnostics", "medications", "consumables"] as const;
const units = ["box", "unit", "pack", "vial"] as const;
const emptyProductForm = { name: "", sku: "", category: "ppe", unit: "box", country: "US" };
const emptyInboundForm = { supply_id: "", quantity: "", vendor_name: "", clinic_id: "1" };
const emptyOutboundForm = { supply_id: "", quantity: "", consumption_type: "clinical_use", clinic_id: "1" };

function pluralUnit(unit: InventoryProduct["unit"], quantity: number): string {
  if (quantity === 1) return unit;
  return unit === "box" ? "boxes" : `${unit}s`;
}

export default function InventoryPage() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [productForm, setProductForm] = useState(emptyProductForm);
  const [inboundForm, setInboundForm] = useState(emptyInboundForm);
  const [outboundForm, setOutboundForm] = useState(emptyOutboundForm);
  const [error, setError] = useState("");
  const [productFormError, setProductFormError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const threshold = useMemo(() => lowStockThreshold(products), [products]);
  const selectedOutboundProduct = products.find((product) => String(product.id) === outboundForm.supply_id);

  const loadInventory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [productResponse, orderResponse] = await Promise.all([
        authFetch("/inventory/products"),
        authFetch("/inventory/orders"),
      ]);
      const [nextProducts, nextOrders] = await Promise.all([
        readApiResponse<InventoryProduct[]>(productResponse, "Unable to load inventory. Check your connection and try again."),
        readApiResponse<InventoryOrder[]>(orderResponse, "Unable to load inventory history. Check your connection and try again."),
      ]);
      setProducts(nextProducts);
      setOrders(nextOrders);
    } catch (cause) {
      setError(cause instanceof ApiRequestError ? cause.message : "Unable to load inventory. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadInventory(), 0);
    return () => window.clearTimeout(timer);
  }, [loadInventory]);

  async function submit<T>(path: string, body: unknown, fallback: string): Promise<T> {
    const response = await authFetch(path, { method: "POST", body: JSON.stringify(body) });
    try {
      return await readApiResponse<T>(response, fallback);
    } catch (cause) {
      if (cause instanceof ApiRequestError) throw cause;
      throw new ApiRequestError(fallback);
    }
  }

  async function runAction(
    action: () => Promise<void>,
    fallback: string,
    onError: (message: string) => void = setError,
  ) {
    setSaving(true);
    setError("");
    try {
      await action();
      await loadInventory();
    } catch (cause) {
      onError(cause instanceof ApiRequestError ? cause.message : fallback);
    } finally {
      setSaving(false);
    }
  }

  async function registerProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = productForm.name.trim();
    const sku = productForm.sku.trim();
    if (!name || !sku) {
      setProductFormError("Enter both a supply name and SKU.");
      return;
    }
    setProductFormError("");
    await runAction(async () => {
      await submit<InventoryProduct>(
        "/inventory/products",
        { ...productForm, name, sku },
        "Unable to register the supply. Check the details and try again.",
      );
      setProductForm(emptyProductForm);
    }, "Unable to register the supply. Check the details and try again.", setProductFormError);
  }

  async function receiveDelivery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction(async () => {
      await submit("/inventory/orders/inbound", {
        supply_id: Number(inboundForm.supply_id), quantity: Number(inboundForm.quantity),
        vendor_name: inboundForm.vendor_name.trim(), clinic_id: Number(inboundForm.clinic_id),
      }, "Unable to record the delivery. Check the details and try again.");
      setInboundForm(emptyInboundForm);
    }, "Unable to record the delivery. Check the details and try again.");
  }

  async function recordConsumption(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction(async () => {
      await submit("/inventory/orders/outbound", {
        supply_id: Number(outboundForm.supply_id), quantity: Number(outboundForm.quantity),
        consumption_type: outboundForm.consumption_type, clinic_id: Number(outboundForm.clinic_id),
      }, "Unable to record the consumption. Check the details and try again.");
      setOutboundForm(emptyOutboundForm);
    }, "Unable to record the consumption. Check the details and try again.");
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content inventory-page">
        <header className="topbar"><div className="breadcrumb"><Link href="/">HealthCore Digital</Link><span aria-hidden="true">/</span><strong>Inventory</strong></div><div className="topbar-actions"><span className="status-dot"><i></i>Live inventory API</span></div></header>
        <section className="welcome-section inventory-welcome"><div><p className="eyebrow">Clinical operations · Supply tracking</p><h1>Medical inventory.</h1><p className="welcome-copy">Available stock is calculated from recorded deliveries and consumptions. There is no manual stock adjustment.</p></div><div className="welcome-aside"><span className="signal-line" aria-hidden="true"></span><p><strong>{products.length}</strong> catalogue items<br /><span>loaded from the inventory API</span></p></div></section>

        <section className="panel inventory-stock-panel" aria-labelledby="inventory-stock-title">
          <div className="panel-heading"><div><p className="eyebrow">Catalogue</p><h2 id="inventory-stock-title">Supply and available stock</h2></div><span className="panel-count">{products.length} items</span></div>
          <div className="inventory-advisory" role="note"><strong>Low-stock advisory:</strong> highlighted levels are a relative visual cue based on this catalogue’s returned stock, not an approved reorder point or clinical threshold.</div>
          {error && <div className="inventory-error" role="alert">{error}{!loading && <button className="supplier-small-button" type="button" onClick={() => void loadInventory()}>Try again</button>}</div>}
          {loading ? <p className="supplier-empty" role="status">Loading live inventory…</p> : products.length === 0 ? <p className="supplier-empty">No supplies are registered yet. Use the form below to add the first catalogue item.</p> : (
            <div className="supplier-table-wrap"><table className="supplier-table inventory-table"><thead><tr><th>Medical supply</th><th>SKU</th><th>Category</th><th>Jurisdiction</th><th>Unit</th><th>Available stock</th></tr></thead><tbody>
              {products.map((product) => { const low = product.current_stock <= threshold; return <tr key={product.id} className={low ? "inventory-low-stock" : ""}><td><strong>{product.name}</strong>{low && <small className="inventory-low-label">Low-stock advisory</small>}</td><td>{product.sku}</td><td>{product.category.replaceAll("_", " ")}</td><td>{product.country}</td><td>{product.unit}</td><td><strong>{product.current_stock}</strong> <span>{pluralUnit(product.unit, product.current_stock)}</span></td></tr>; })}
            </tbody></table></div>
          )}
        </section>

        <div className="inventory-forms-grid">
          <section className="panel inventory-form-panel" aria-labelledby="product-form-title"><div className="panel-heading"><div><p className="eyebrow">Catalogue</p><h2 id="product-form-title">Register a supply</h2></div></div>
            <form className="supplier-form inventory-form" onSubmit={registerProduct}>
              {productFormError && <p className="inventory-error" role="alert">{productFormError}</p>}
              <label>Name<input required minLength={1} autoComplete="off" value={productForm.name} onChange={(event) => { setProductFormError(""); setProductForm({ ...productForm, name: event.target.value }); }} /></label>
              <label>SKU<input required minLength={1} autoComplete="off" value={productForm.sku} onChange={(event) => { setProductFormError(""); setProductForm({ ...productForm, sku: event.target.value }); }} /></label>
              <label>Category<select value={productForm.category} onChange={(event) => setProductForm({ ...productForm, category: event.target.value as typeof productForm.category })}>{productCategories.map((category) => <option key={category} value={category}>{category.replaceAll("_", " ")}</option>)}</select></label>
              <label>Unit<select value={productForm.unit} onChange={(event) => setProductForm({ ...productForm, unit: event.target.value as typeof productForm.unit })}>{units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select></label>
              <label>Country<select value={productForm.country} onChange={(event) => setProductForm({ ...productForm, country: event.target.value as "US" | "UK" })}><option value="US">US</option><option value="UK">UK</option></select></label>
              <button className="button supplier-submit" type="submit" disabled={saving}>{saving ? "Registering…" : "Register supply"} <span aria-hidden="true">→</span></button>
            </form>
          </section>

          <section className="panel inventory-form-panel" aria-labelledby="delivery-form-title"><div className="panel-heading"><div><p className="eyebrow">Inbound order</p><h2 id="delivery-form-title">Record a delivery</h2></div></div>
            <form className="supplier-form inventory-form" onSubmit={receiveDelivery}>
              <label>Supply<select required value={inboundForm.supply_id} onChange={(event) => setInboundForm({ ...inboundForm, supply_id: event.target.value })}><option value="">Choose supply</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} · {product.sku}</option>)}</select></label>
              <label>Quantity<input required type="number" min="1" step="1" value={inboundForm.quantity} onChange={(event) => setInboundForm({ ...inboundForm, quantity: event.target.value })} /></label>
              <label>Vendor<input required minLength={1} value={inboundForm.vendor_name} onChange={(event) => setInboundForm({ ...inboundForm, vendor_name: event.target.value })} /></label>
              <label>Clinic ID<select value={inboundForm.clinic_id} onChange={(event) => setInboundForm({ ...inboundForm, clinic_id: event.target.value })}>{Array.from({ length: 12 }, (_, index) => index + 1).map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
              <button className="button supplier-submit" type="submit" disabled={saving || products.length === 0}>Record delivery <span aria-hidden="true">→</span></button>
            </form>
          </section>

          <section className="panel inventory-form-panel" aria-labelledby="consumption-form-title"><div className="panel-heading"><div><p className="eyebrow">Outbound order</p><h2 id="consumption-form-title">Record a consumption</h2></div></div>
            <form className="supplier-form inventory-form" onSubmit={recordConsumption}>
              <label>Supply<select required value={outboundForm.supply_id} onChange={(event) => setOutboundForm({ ...outboundForm, supply_id: event.target.value })}><option value="">Choose supply</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name} · {product.sku}</option>)}</select></label>
              {selectedOutboundProduct && <p className="inventory-available" role="status">Available before submission: <strong>{selectedOutboundProduct.current_stock}</strong> {pluralUnit(selectedOutboundProduct.unit, selectedOutboundProduct.current_stock)}</p>}
              <label>Quantity<input required type="number" min="1" step="1" max={selectedOutboundProduct?.current_stock} value={outboundForm.quantity} onChange={(event) => setOutboundForm({ ...outboundForm, quantity: event.target.value })} /></label>
              <label>Consumption type<select value={outboundForm.consumption_type} onChange={(event) => setOutboundForm({ ...outboundForm, consumption_type: event.target.value as typeof outboundForm.consumption_type })}><option value="clinical_use">Clinical use</option><option value="expiry_waste">Expiry waste</option></select></label>
              <label>Clinic ID<select value={outboundForm.clinic_id} onChange={(event) => setOutboundForm({ ...outboundForm, clinic_id: event.target.value })}>{Array.from({ length: 12 }, (_, index) => index + 1).map((id) => <option key={id} value={id}>{id}</option>)}</select></label>
              <button className="button supplier-submit" type="submit" disabled={saving || products.length === 0 || (selectedOutboundProduct?.current_stock ?? 0) < 1}>Record consumption <span aria-hidden="true">→</span></button>
            </form>
          </section>
        </div>

        <section className="panel inventory-history-panel" aria-labelledby="inventory-history-title"><div className="panel-heading"><div><p className="eyebrow">Audit trail</p><h2 id="inventory-history-title">Order history</h2></div><span className="panel-count">{orders.length} orders</span></div>
          {loading ? <p className="supplier-empty" role="status">Loading order history…</p> : orders.length === 0 ? <p className="supplier-empty">No inventory movements have been recorded yet.</p> : <div className="supplier-table-wrap"><table className="supplier-table inventory-table"><thead><tr><th>Type</th><th>Medical supply</th><th>Quantity</th><th>Clinic</th><th>Details</th><th>Recorded by</th><th>Date</th></tr></thead><tbody>
            {orders.map((order) => <tr key={`${order.order_type}-${order.order_id}`}><td><span className={`inventory-order-type ${order.order_type}`}>{order.order_type === "inbound" ? "Delivery" : "Consumption"}</span></td><td><strong>{order.supply.name}</strong><small>{order.supply.sku}</small></td><td>{order.quantity} {pluralUnit(order.supply.unit, order.quantity)}</td><td>{order.clinic_id}</td><td>{order.order_type === "inbound" ? `Vendor: ${order.vendor_name ?? "Not supplied"}` : order.consumption_type === "expiry_waste" ? "Expiry waste" : "Clinical use"}</td><td><code>{order.user_uuid}</code></td><td>{formatInventoryDate(order.created_at)}</td></tr>)}
          </tbody></table></div>}
        </section>
        <footer className="main-footer"><span>HealthCore Digital · Inventory management</span><span>Stock is derived from order history · authenticated access</span></footer>
      </main>
    </div>
  );
}
