import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewForm } from "./ReviewForm";
import { exportFormPdf, requestSubmissionApproval, simulateFormSubmission, updateFormDraft, validateForm } from "./api";

vi.mock("./api", () => ({
  getFormSchema: vi.fn().mockResolvedValue({
    form_code: "BIRTH_REGISTRATION_FORM",
    title_vi: "Tờ khai đăng ký khai sinh",
    groups: [{ group_code: "person", label_vi: "Người yêu cầu", display_order: 1 }],
    fields: [{ field_code: "applicant_full_name", label_vi: "Họ tên", group_code: "person", data_type: "string", required: true, enum_values: null }],
  }),
  getFormDraft: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", fields: {}, updated_at: null }),
  updateFormDraft: vi.fn().mockResolvedValue({ form_code: "BIRTH_REGISTRATION_FORM", fields: {}, updated_at: null }),
  validateForm: vi.fn().mockResolvedValue({
    validation_id: "v1", form_code: "BIRTH_REGISTRATION_FORM", input_hash: "sha256:x", status: "valid",
    summary: { blocking_error: 0, warning: 0, suggestion: 0, unable_to_verify: 0 }, issues: [], validated_at: new Date().toISOString(),
  }),
  exportFormPdf: vi.fn().mockResolvedValue(new Blob(["%PDF-1.7"])),
  requestSubmissionApproval: vi.fn().mockResolvedValue({
    approval_id: "approval-1", form_code: "BIRTH_REGISTRATION_FORM", destination: "Bộ phận Một cửa (mô phỏng)",
    purpose: "Tạo và gửi hồ sơ mô phỏng", disclosed_fields: ["Họ tên"], effect: "Tạo biên nhận mô phỏng",
    expires_at: new Date(Date.now() + 60_000).toISOString(),
  }),
  simulateFormSubmission: vi.fn().mockResolvedValue({
    submission_id: "submission-1", receipt_code: "SPDVC-DEMO-001", form_code: "BIRTH_REGISTRATION_FORM",
    validation_id: "v1", status: "submitted_simulation", channel: "review_form", submitted_at: new Date().toISOString(),
    simulation: true, official_submission: false, delivery_destination: "Bộ phận Một cửa (mô phỏng)",
    pdf_sha256: "abc", pdf_size_bytes: 1024, artifact_available: true, message_vi: "Gửi mô phỏng thành công",
  }),
  downloadSubmissionArtifact: vi.fn(),
}));

describe("ReviewForm validation snapshot", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:preview"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("persists the complete visible form before validation", async () => {
    render(<ReviewForm activeFormCode="BIRTH_REGISTRATION_FORM" locale="vi" onFormCodeConsumed={() => undefined} />);
    const input = await screen.findByLabelText("Họ tên*");
    fireEvent.input(input, { target: { value: "Nguyễn Văn An" } });
    fireEvent.click(screen.getByRole("button", { name: "Thẩm định & Rà soát" }));

    await waitFor(() => expect(validateForm).toHaveBeenCalledTimes(1));
    expect(updateFormDraft).toHaveBeenCalledWith("BIRTH_REGISTRATION_FORM", { applicant_full_name: "Nguyễn Văn An" });
    expect(vi.mocked(updateFormDraft).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(validateForm).mock.invocationCallOrder[0]);
  });

  it("requires data confirmation and PDF confirmation before submission", async () => {
    const onSubmissionComplete = vi.fn();
    render(<ReviewForm activeFormCode="BIRTH_REGISTRATION_FORM" locale="vi" onFormCodeConsumed={() => undefined} onSubmissionComplete={onSubmissionComplete} />);
    await screen.findByLabelText("Họ tên*");
    fireEvent.click(screen.getByRole("button", { name: "Thẩm định & Rà soát" }));
    await screen.findByText("HỒ SƠ HỢP LỆ");

    fireEvent.click(screen.getByRole("button", { name: "Nộp hồ sơ mô phỏng" }));
    expect(await screen.findByRole("dialog", { name: "Xác nhận hành động một lần" })).toBeInTheDocument();
    expect(simulateFormSubmission).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Xác nhận thông tin và xem PDF" }));
    expect(await screen.findByRole("dialog", { name: /Kiểm tra PDF lần cuối/ })).toBeInTheDocument();
    expect(exportFormPdf).toHaveBeenCalledWith("BIRTH_REGISTRATION_FORM", "v1");
    expect(simulateFormSubmission).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Xác nhận lần cuối và gửi" }));
    await waitFor(() => expect(simulateFormSubmission).toHaveBeenCalledWith("BIRTH_REGISTRATION_FORM", "v1", "approval-1"));
    expect(onSubmissionComplete).toHaveBeenCalledWith(expect.objectContaining({ receipt_code: "SPDVC-DEMO-001" }));
  });
});
