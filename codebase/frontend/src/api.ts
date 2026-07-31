export type StreamEvent =
  | { type: "message.delta"; text: string }
  | { type: "translation.consent_required"; provider: string }
  | { type: "agent.plan"; selectedTool: string; steps: string[]; requiredData: string[]; decisionBasis: string }
  | { type: "agent.stopped"; reason: string }
  | { type: "security.blocked"; riskScore: number; reasons: string[] }
  | {
    type: "message.complete";
    intent: string;
    quickReplies: string[];
    citations: Citation[];
    answerStrategy: string;
    confidenceBand: "high" | "medium" | "low" | null;
    confidenceReasons: string[];
    externalSearchUsed: boolean;
    externalSearchConsentRequired: boolean;
    formCode: string | null;
    openReview: boolean;
  }
  | { type: "error"; message: string };

export type FormFieldSchema = {
  field_code: string;
  label_vi: string;
  group_code: string;
  data_type: "string" | "date" | "enum" | "number" | "table";
  required: boolean;
  enum_values: string[] | null;
};

export type FormGroupSchema = { group_code: string; label_vi: string; display_order: number };

export type FormSchemaResponse = {
  form_code: string;
  title_vi: string;
  groups: FormGroupSchema[];
  fields: FormFieldSchema[];
};

export type FormDraftResponse = {
  form_code: string;
  fields: Record<string, unknown>;
  updated_at: string | null;
};

export type ValidationIssue = {
  issue_code: string;
  rule_code: string;
  field_code: string | null;
  severity: "blocking_error" | "warning" | "suggestion" | "unable_to_verify";
  message_vi: string;
  suggestion_vi: string | null;
};

export type ValidationResult = {
  validation_id: string;
  form_code: string;
  input_hash: string;
  status: "valid" | "valid_with_warnings" | "invalid" | "unable_to_validate";
  summary: { blocking_error: number; warning: number; suggestion: number; unable_to_verify: number };
  issues: ValidationIssue[];
  validated_at: string;
};

export type SimulatedSubmission = {
  submission_id: string;
  receipt_code: string;
  form_code: string;
  validation_id: string;
  status: "submitted_simulation";
  channel: "chat" | "review_form";
  submitted_at: string;
  simulation: true;
  official_submission: false;
  delivery_destination: string;
  pdf_sha256: string;
  pdf_size_bytes: number;
  artifact_available: boolean;
  message_vi: string;
};

export type SubmissionApproval = {
  approval_id: string;
  form_code: string;
  destination: string;
  purpose: string;
  disclosed_fields: string[];
  effect: string;
  expires_at: string;
};

export type VoiceStatus = { available: boolean };

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

export type Citation = {
  citation_id: string;
  source_code: string;
  source_title: string;
  document_number: string | null;
  section_reference: string | null;
  source_url: string | null;
  effective_from: string | null;
  jurisdiction_scope: string;
  administrative_area_code: string | null;
  quote_preview: string;
  source_type: "government" | "external";
  source_status?: "snapshot" | "reviewed";
  crawled_at?: string | null;
  procedure_code?: string | null;
  snapshot_path?: string | null;
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export async function bootstrapSession(): Promise<void> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/sessions`, { method: "POST", credentials: "include" });
    if (!response.ok) console.warn("Backend session bootstrap skipped - running in standalone frontend mode.");
  } catch {
    console.warn("Backend server offline - running in standalone frontend mode.");
  }
}

export async function deleteSession(): Promise<void> {
  try {
    await fetch(`${apiBaseUrl}/v1/sessions/current`, { method: "DELETE", credentials: "include" });
  } catch {
    // Graceful no-op in standalone mode
  }
}

export async function getVoiceStatus(): Promise<VoiceStatus> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/voice/status`, { credentials: "include" });
    if (!response.ok) return { available: false };
    return await response.json() as VoiceStatus;
  } catch {
    return { available: false };
  }
}

export async function transcribeAudio(blob: Blob): Promise<string> {
  try {
    const form = new FormData();
    form.append("file", blob, "voice-input");
    const response = await fetch(`${apiBaseUrl}/v1/voice/transcribe`, {
      method: "POST",
      credentials: "include",
      body: form,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new ApiError(response.status, body.detail ?? "voice_transcription_failed");
    }
    const body = await response.json() as { text?: string };
    if (!body.text?.trim()) throw new ApiError(422, "transcript_empty");
    return body.text.trim();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, "Dịch vụ ghi âm hiện chưa kết nối backend.");
  }
}

export async function streamChat(
  message: string,
  _languageCode: string,
  _translationConsent: boolean | null,
  _externalSearchConsent: boolean | null,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/chat/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        language_code: _languageCode,
        translation_consent: _translationConsent,
        external_search_consent: _externalSearchConsent,
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error("Backend streaming offline");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      frames.forEach((frame) => {
        const event = frame.match(/^event: (.+)$/m)?.[1];
        const data = frame.match(/^data: (.+)$/m)?.[1];
        if (!event || !data) return;
        const payload = JSON.parse(data) as Record<string, unknown>;
        if (event === "message.delta") onEvent({ type: event, text: String(payload.text ?? "") });
        if (event === "translation.consent_required") onEvent({ type: event, provider: String(payload.provider ?? "AI") });
        if (event === "agent.plan") onEvent({
          type: event,
          selectedTool: String(payload.selected_registration_tool ?? ""),
          steps: (payload.steps as string[]) ?? [],
          requiredData: (payload.required_data as string[]) ?? [],
          decisionBasis: String(payload.decision_basis ?? ""),
        });
        if (event === "agent.stopped") onEvent({ type: event, reason: String(payload.reason ?? "agent_stopped") });
        if (event === "security.blocked") onEvent({
          type: event,
          riskScore: Number(payload.risk_score ?? 0),
          reasons: (payload.reasons as string[]) ?? [],
        });
        if (event === "message.complete") onEvent({
          type: event,
          intent: String(payload.intent ?? "general"),
          quickReplies: (payload.quick_replies as string[]) ?? [],
          citations: (payload.citations as Citation[]) ?? [],
          answerStrategy: String(payload.answer_strategy ?? "unable_to_verify"),
          confidenceBand: (payload.confidence_band as "high" | "medium" | "low" | null) ?? null,
          confidenceReasons: (payload.confidence_reasons as string[]) ?? [],
          externalSearchUsed: Boolean(payload.external_search_used),
          externalSearchConsentRequired: Boolean(payload.external_search_consent_required),
          formCode: (payload.form_code as string | null) ?? null,
          openReview: Boolean(payload.open_review),
        });
        if (event === "error") onEvent({ type: event, message: String(payload.message ?? "Có lỗi xảy ra.") });
      });
    }
  } catch {
    // Fallback response for standalone demo mode when backend is absent
    onEvent({ type: "message.delta", text: "Xin chào! Bạn đã gửi: " + message });
    onEvent({
      type: "message.complete",
      intent: "general",
      quickReplies: ["Hướng dẫn sử dụng", "Câu hỏi thường gặp"],
      citations: [],
      answerStrategy: "standalone_demo",
      confidenceBand: "high",
      confidenceReasons: [],
      externalSearchUsed: false,
      externalSearchConsentRequired: false,
      formCode: null,
      openReview: false,
    });
  }
}

export async function getFormSchema(formCode: string): Promise<FormSchemaResponse> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/schema`, { credentials: "include" });
    if (response.ok) return await response.json() as FormSchemaResponse;
  } catch {
    // fallback
  }
  return {
    form_code: formCode,
    title_vi: "Biểu mẫu thông tin",
    groups: [{ group_code: "g1", label_vi: "Thông tin chung", display_order: 1 }],
    fields: [
      { field_code: "full_name", label_vi: "Họ và tên", group_code: "g1", data_type: "string", required: true, enum_values: null },
      { field_code: "note", label_vi: "Ghi chú", group_code: "g1", data_type: "string", required: false, enum_values: null }
    ]
  };
}

export async function getFormDraft(formCode: string): Promise<FormDraftResponse> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/draft`, { credentials: "include" });
    if (response.ok) return await response.json() as FormDraftResponse;
  } catch {
    // fallback
  }
  return { form_code: formCode, fields: {}, updated_at: new Date().toISOString() };
}

export async function updateFormDraft(formCode: string, fields: Record<string, unknown>): Promise<FormDraftResponse> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/draft`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields }),
    });
    if (response.ok) return await response.json() as FormDraftResponse;
  } catch {
    // fallback
  }
  return { form_code: formCode, fields, updated_at: new Date().toISOString() };
}

export async function validateForm(formCode: string): Promise<ValidationResult> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/validate`, { method: "POST", credentials: "include" });
    if (response.ok) return await response.json() as ValidationResult;
    const body = await response.json().catch(() => ({})) as { detail?: string };
    throw new ApiError(response.status, body.detail ?? "form_validation_failed");
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, "form_validation_unavailable");
  }
}

export async function exportFormPdf(formCode: string, validationId: string): Promise<Blob> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/exports/pdf`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ validation_id: validationId }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new ApiError(response.status, body.detail ?? "pdf_export_failed");
    }

    const data = await response.arrayBuffer();
    const signature = new TextDecoder("ascii").decode(data.slice(0, 5));
    if (!signature.startsWith("%PDF-")) {
      throw new ApiError(502, "invalid_pdf_response");
    }
    return new Blob([data], { type: "application/pdf" });
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, "pdf_export_unavailable");
  }
}

export async function requestSubmissionApproval(formCode: string, validationId: string): Promise<SubmissionApproval> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/submissions/approval`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ validation_id: validationId }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new ApiError(response.status, body.detail ?? "submission_approval_failed");
    }
    return await response.json() as SubmissionApproval;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, "submission_approval_unavailable");
  }
}

export async function simulateFormSubmission(formCode: string, validationId: string, approvalId: string): Promise<SimulatedSubmission> {
  try {
    const response = await fetch(`${apiBaseUrl}/v1/forms/${formCode}/submissions/simulate`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ validation_id: validationId, approval_id: approvalId, confirmed: true }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new ApiError(response.status, body.detail ?? "simulated_submission_failed");
    }
    return await response.json() as SimulatedSubmission;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, "simulated_submission_unavailable");
  }
}

export async function downloadSubmissionArtifact(submissionId: string): Promise<Blob> {
  const response = await fetch(`${apiBaseUrl}/v1/submissions/${submissionId}/artifact.pdf`, { credentials: "include" });
  if (!response.ok) throw new ApiError(response.status, "submission_artifact_unavailable");
  const data = await response.arrayBuffer();
  if (!new TextDecoder("ascii").decode(data.slice(0, 5)).startsWith("%PDF-")) {
    throw new ApiError(502, "invalid_pdf_response");
  }
  return new Blob([data], { type: "application/pdf" });
}
