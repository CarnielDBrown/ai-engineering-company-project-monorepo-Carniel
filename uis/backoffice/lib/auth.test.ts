import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiRequestError,
  TOKEN_KEY,
  apiError,
  clearToken,
  getToken,
  readApiResponse,
  saveToken,
} from "./auth";

describe("auth token storage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("saves, reads, and clears the access token under the app key", () => {
    const values = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    });
    expect(TOKEN_KEY).toBe("healthcore_access_token");
    expect(getToken()).toBeNull();

    saveToken("test-access-token");
    expect(getToken()).toBe("test-access-token");
    expect(values.get(TOKEN_KEY)).toBe("test-access-token");

    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("API error messages", () => {
  it("allows only known safe API details", () => {
    expect(apiError({ detail: "Incorrect email or password" }, "Fallback")).toBe(
      "Incorrect email or password",
    );
    expect(apiError({ detail: "database password=secret" }, "Fallback")).toBe("Fallback");
    expect(apiError({ detail: ["validation", "details"] }, "Fallback")).toBe(
      "Please check the information and try again.",
    );
    expect(apiError({ message: "private failure" }, "Fallback")).toBe("Fallback");
    expect(apiError(null, "Fallback")).toBe("Fallback");
  });
});

describe("readApiResponse", () => {
  it("returns parsed JSON for a successful response", async () => {
    const response = new Response(JSON.stringify({ ok: true }), { status: 200 });
    await expect(readApiResponse<{ ok: boolean }>(response, "Fallback")).resolves.toEqual({ ok: true });
  });

  it("uses an allowlisted detail for an API error", async () => {
    const response = new Response(JSON.stringify({ detail: "Profile not found" }), { status: 404 });
    await expect(readApiResponse(response, "Fallback")).rejects.toMatchObject({
      name: "ApiRequestError",
      message: "Profile not found",
    });
  });

  it("hides unknown API error details behind the fallback", async () => {
    const response = new Response(JSON.stringify({ detail: "sensitive internal error" }), { status: 500 });
    await expect(readApiResponse(response, "Safe fallback")).rejects.toMatchObject({
      name: "ApiRequestError",
      message: "Safe fallback",
    });
  });

  it("uses the fallback for non-JSON bodies on success or failure", async () => {
    const success = new Response("not-json", { status: 200 });
    await expect(readApiResponse(success, "Safe fallback")).rejects.toBeInstanceOf(ApiRequestError);
    await expect(readApiResponse(new Response("not-json", { status: 500 }), "Safe fallback")).rejects.toMatchObject({
      message: "Safe fallback",
    });
  });

  it("supports an empty successful response body", async () => {
    await expect(readApiResponse(new Response(null, { status: 204 }), "Fallback")).resolves.toBeUndefined();
  });
});
