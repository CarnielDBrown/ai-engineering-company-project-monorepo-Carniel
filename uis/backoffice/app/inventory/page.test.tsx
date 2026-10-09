import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InventoryPage from "./page";

vi.mock("next/link", () => ({ default: ({ children, href, ...props }: React.ComponentProps<"a">) => <a href={href} {...props}>{children}</a> }));
vi.mock("@/components/sidebar", () => ({ Sidebar: () => <nav aria-label="Main navigation">Medical inventory</nav> }));
vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return { ...actual, authFetch: vi.fn() };
});

import { authFetch } from "@/lib/auth";

const mockedAuthFetch = vi.mocked(authFetch);
const product = {
  id: 7, name: "Nitrile gloves", sku: "HCR-PPE-001", category: "ppe" as const,
  unit: "box" as const, country: "US" as const, current_stock: 24,
};
const inbound = {
  order_type: "inbound" as const, order_id: 10, supply: product, quantity: 30,
  clinic_id: 1, created_at: "2026-01-02T12:00:00Z", user_uuid: "actor-test-uuid", vendor_name: "Example Vendor",
};
const outbound = {
  order_type: "outbound" as const, order_id: 11, supply: product, quantity: 6,
  clinic_id: 2, created_at: "2026-01-03T12:00:00Z", user_uuid: "actor-test-uuid", consumption_type: "clinical_use" as const,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function queueInventory(products: unknown[] = [product], orders: unknown[] = [inbound, outbound]) {
  mockedAuthFetch.mockResolvedValueOnce(jsonResponse(products)).mockResolvedValueOnce(jsonResponse(orders));
}

async function waitForInitialLoad() {
  await screen.findByText("Available stock");
}

beforeEach(() => {
  mockedAuthFetch.mockReset();
});

describe("inventory page", () => {
  it("renders live stock and read-only delivery/consumption history after loading", async () => {
    queueInventory();
    render(<InventoryPage />);

    await waitForInitialLoad();
    expect(screen.getByText("Available stock")).toBeTruthy();
    expect(screen.getByText("24")).toBeTruthy();
    expect(screen.getAllByText("HCR-PPE-001")[0].closest("tr")?.textContent).toContain("24 boxes");
    expect(screen.getByText("Delivery")).toBeTruthy();
    expect(screen.getByText("Consumption")).toBeTruthy();
    expect(screen.getByText((_, element) => element?.textContent === "Vendor: Example Vendor")).toBeTruthy();
    expect(screen.getAllByText("Clinical use").length).toBeGreaterThan(1);
    expect(screen.getAllByText("actor-test-uuid").length).toBe(2);
    expect(mockedAuthFetch.mock.calls.slice(0, 2).map(([path]) => path)).toEqual([
      "/inventory/products", "/inventory/orders",
    ]);
    expect(mockedAuthFetch.mock.calls[0][1]).toBeUndefined();
  });

  it("renders an empty catalogue and retries failed loads without exposing internal errors", async () => {
    mockedAuthFetch
      .mockRejectedValueOnce(new Error("postgres://internal-secret"))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(jsonResponse([]));
    render(<InventoryPage />);

    expect((await screen.findByRole("alert")).textContent).toContain("Unable to load inventory");
    expect(screen.getByRole("alert").textContent).not.toContain("internal-secret");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(/No supplies are registered yet/)).toBeTruthy();
  });

  it("submits delivery and consumption using live supply/stock, then refreshes stock and history", async () => {
    queueInventory();
    render(<InventoryPage />);
    await waitForInitialLoad();
    mockedAuthFetch
      .mockResolvedValueOnce(jsonResponse({ ...product, current_stock: 30 }, 201))
      .mockResolvedValueOnce(jsonResponse([{ ...product, current_stock: 36 }]))
      .mockResolvedValueOnce(jsonResponse([inbound, outbound]));

    const user = userEvent.setup();
    const deliveryForm = screen.getByRole("heading", { name: "Record a delivery" }).closest("section")!;
    await user.selectOptions(within(deliveryForm).getByLabelText("Supply"), "7");
    await user.type(within(deliveryForm).getByLabelText("Quantity"), "12");
    await user.type(within(deliveryForm).getByLabelText("Vendor"), "New Vendor");
    await user.click(within(deliveryForm).getByRole("button", { name: /Record delivery/ }));
    await waitFor(() => expect(mockedAuthFetch).toHaveBeenCalledTimes(5));
    expect(mockedAuthFetch.mock.calls[2][0]).toBe("/inventory/orders/inbound");
    expect(JSON.parse(String(mockedAuthFetch.mock.calls[2][1]?.body))).toEqual({
      supply_id: 7, quantity: 12, vendor_name: "New Vendor", clinic_id: 1,
    });

    mockedAuthFetch
      .mockResolvedValueOnce(jsonResponse({ ...outbound, order_id: 12 }, 201))
      .mockResolvedValueOnce(jsonResponse([{ ...product, current_stock: 30 }]))
      .mockResolvedValueOnce(jsonResponse([inbound, outbound]));
    const consumptionForm = screen.getByRole("heading", { name: "Record a consumption" }).closest("section")!;
    await user.selectOptions(within(consumptionForm).getByLabelText("Supply"), "7");
    expect(screen.getByText(/Available before submission:/).textContent).toContain("36");
    await user.type(within(consumptionForm).getByLabelText("Quantity"), "6");
    await user.selectOptions(within(consumptionForm).getByLabelText("Consumption type"), "expiry_waste");
    await user.click(within(consumptionForm).getByRole("button", { name: /Record consumption/ }));
    await waitFor(() => expect(mockedAuthFetch).toHaveBeenCalledTimes(8));
    expect(mockedAuthFetch.mock.calls[5][0]).toBe("/inventory/orders/outbound");
    expect(JSON.parse(String(mockedAuthFetch.mock.calls[5][1]?.body))).toEqual({
      supply_id: 7, quantity: 6, consumption_type: "expiry_waste", clinic_id: 1,
    });
    expect(mockedAuthFetch.mock.calls[6][0]).toBe("/inventory/products");
    expect(mockedAuthFetch.mock.calls[7][0]).toBe("/inventory/orders");
  });

  it("retains outbound form input and displays a safe API rejection", async () => {
    queueInventory();
    render(<InventoryPage />);
    await waitForInitialLoad();
    mockedAuthFetch.mockResolvedValueOnce(jsonResponse({ detail: "Insufficient stock for supply 'Nitrile gloves'. Available: 24, requested: 99." }, 400));

    const form = screen.getByRole("heading", { name: "Record a consumption" }).closest("section")!;
    const user = userEvent.setup();
    await user.selectOptions(within(form).getByLabelText("Supply"), "7");
    const quantity = within(form).getByLabelText("Quantity") as HTMLInputElement;
    fireEvent.change(quantity, { target: { value: "99" } });
    fireEvent.submit(within(form).getByRole("button", { name: /Record consumption/ }).closest("form")!);

    expect((await screen.findByRole("alert")).textContent).toContain("Unable to record the consumption");
    expect(quantity.value).toBe("99");
    expect(mockedAuthFetch.mock.calls.at(-1)?.[0]).toBe("/inventory/orders/outbound");
  });
});
