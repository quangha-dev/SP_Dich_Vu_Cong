import { afterEach, describe, expect, it, vi } from "vitest";

import { exportFormPdf, validateForm } from "./api";

describe("exportFormPdf", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns a verified PDF blob", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("%PDF-1.7\nvalid", {
      status: 200,
      headers: { "Content-Type": "application/pdf" },
    })));

    const blob = await exportFormPdf("BIRTH_REGISTRATION_FORM", "validation-id");

    expect(blob.type).toBe("application/pdf");
    expect(blob.size).toBeGreaterThan(5);
  });

  it("surfaces the backend export error instead of returning a fake PDF", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "export_failed:vietnamese_font_missing:None",
    }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    })));

    await expect(exportFormPdf("BIRTH_REGISTRATION_FORM", "validation-id")).rejects.toMatchObject({
      status: 422,
      detail: "export_failed:vietnamese_font_missing:None",
    });
  });

  it("rejects a successful response that is not actually a PDF", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not a PDF", {
      status: 200,
      headers: { "Content-Type": "application/pdf" },
    })));

    await expect(exportFormPdf("BIRTH_REGISTRATION_FORM", "validation-id")).rejects.toMatchObject({
      status: 502,
      detail: "invalid_pdf_response",
    });
  });
});

describe("validateForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("never fabricates a validation id when the backend rejects validation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: "agent_loop_stopped:workflow_tool_budget_exhausted",
    }), {
      status: 409,
      headers: { "Content-Type": "application/json" },
    })));

    await expect(validateForm("BIRTH_REGISTRATION_FORM")).rejects.toMatchObject({
      status: 409,
      detail: "agent_loop_stopped:workflow_tool_budget_exhausted",
    });
  });

  it("reports backend unavailability instead of returning a mock success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network unavailable")));

    await expect(validateForm("BIRTH_REGISTRATION_FORM")).rejects.toMatchObject({
      status: 503,
      detail: "form_validation_unavailable",
    });
  });
});
