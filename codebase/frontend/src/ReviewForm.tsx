import { useEffect, useMemo, useRef, useState } from "react";
import {
  FormSchemaResponse,
  ApiError,
  SimulatedSubmission,
  SubmissionApproval,
  ValidationResult,
  downloadSubmissionArtifact,
  exportFormPdf,
  getFormDraft,
  getFormSchema,
  requestSubmissionApproval,
  simulateFormSubmission,
  updateFormDraft,
  validateForm,
} from "./api";
import { copy, Locale } from "./i18n";

const KNOWN_FORM_CODES = ["BIRTH_REGISTRATION_FORM", "PERMANENT_RESIDENCE_CT01_FORM", "CONSTRUCTION_PERMIT_REQUEST_FORM"];

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function exportErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  const [, reason, fieldCode] = error.detail.split(":");
  if (reason === "text_exceeds_field_width" && fieldCode) {
    return `${fallback} Trường ${fieldCode} quá dài cho vùng trên PDF.`;
  }
  if (reason === "vietnamese_font_missing") {
    return `${fallback} Máy chủ chưa có font serif hỗ trợ tiếng Việt.`;
  }
  return `${fallback} (${error.detail})`;
}

function FormPicker({ locale, onPick }: { locale: Locale; onPick: (formCode: string) => void }) {
  const [titles, setTitles] = useState<Record<string, string>>({});
  const text = copy[locale];

  useEffect(() => {
    void Promise.all(
      KNOWN_FORM_CODES.map((code) => getFormSchema(code).then((schema) => [code, schema.title_vi] as const).catch(() => [code, code] as const)),
    ).then((entries) => setTitles(Object.fromEntries(entries)));
  }, []);

  return (
    <div className="review-empty">
      <span aria-hidden="true">📄</span>
      <h2>{text.pickerTitle}</h2>
      <p>{text.pickerBody}</p>
      <div className="form-picker">
        {KNOWN_FORM_CODES.map((code) => (
          <button key={code} onClick={() => onPick(code)}>{titles[code] ?? code}</button>
        ))}
      </div>
    </div>
  );
}

function stampLabel(text: Record<string, string>, status: ValidationResult["status"]): string {
  if (status === "valid") return text.stampValid;
  if (status === "valid_with_warnings") return text.stampValidWarnings;
  if (status === "invalid") return text.stampInvalid;
  return text.stampUnableToValidate;
}

function ResultPanel({
  locale,
  validation,
  dirty,
  validating,
  onExport,
  exporting,
  onPreview,
  previewing,
  submission,
  submitting,
  onSubmitSimulation,
  onDownloadSubmission,
}: {
  locale: Locale;
  validation: ValidationResult | null;
  dirty: boolean;
  validating: boolean;
  onExport: () => void;
  exporting: boolean;
  onPreview: () => void;
  previewing: boolean;
  submission: SimulatedSubmission | null;
  submitting: boolean;
  onSubmitSimulation: () => void;
  onDownloadSubmission: () => void;
}) {
  const text = copy[locale];
  const simulationText = locale === "vi" ? {
    submit: "Nộp hồ sơ mô phỏng",
    submitting: "Đang nộp mô phỏng...",
    submitted: "Đã nộp mô phỏng",
    disclaimer: "MÔ PHỎNG DEMO — không gửi dữ liệu tới Cổng Dịch vụ công hoặc cơ quan nhà nước.",
    receipt: "Biên nhận mô phỏng",
  } : {
    submit: "Simulate submission",
    submitting: "Submitting simulation...",
    submitted: "Simulation submitted",
    disclaimer: "DEMO SIMULATION — no data is sent to a government portal or authority.",
    receipt: "Simulation receipt",
  };
  const canExport = !!validation && validation.summary.blocking_error === 0 && !dirty;

  return (
    <aside className="review-result-panel">
      <p className="result-title">{text.reviewResult}</p>
      {validating ? (
        <div className="result-loading">
          <span className="spinner" aria-hidden="true" />
          <p className="result-loading-hint">{text.validatingHint}</p>
        </div>
      ) : !validation ? (
        <div className="result-idle">
          <span className="result-icon" aria-hidden="true">📄</span>
          <p className="result-placeholder">{text.reviewHint} <strong>{text.validate}</strong> {text.reviewHintEnd}</p>
        </div>
      ) : (
        <div className="result-verdict">
          <div key={validation.validation_id} className={`verdict-stamp ${validation.status}`}>
            <span className="verdict-stamp-word">{stampLabel(text, validation.status)}</span>
          </div>
          <h3 className={`result-heading ${validation.status}`}>{text[validation.status]}</h3>
          <ul className="result-summary">
            <li className="blocking_error">{text.blocking}: {validation.summary.blocking_error}</li>
            <li className="warning">{text.warning}: {validation.summary.warning}</li>
            <li className="suggestion">{text.suggestion}: {validation.summary.suggestion}</li>
            {validation.summary.unable_to_verify > 0 && <li className="unable_to_verify">{text.unableToVerify}: {validation.summary.unable_to_verify}</li>}
          </ul>
          {validation.issues.length > 0 && (
            <ol className="result-issues">
              {validation.issues.map((issue) => (
                <li key={`${issue.field_code}-${issue.issue_code}`} className={issue.severity}>{issue.message_vi}</li>
              ))}
            </ol>
          )}
          {dirty && <p className="result-stale">{text.stale}</p>}
        </div>
      )}
      {canExport && (
        <div className="export-card">
          <div className="export-card-header">
            <span className="export-card-icon" aria-hidden="true">
              <span className="export-card-icon-line" />
              <span className="export-card-icon-line short" />
              <em>PDF</em>
            </span>
            <div className="export-card-copy">
              <h4>{text.exportCardTitle}</h4>
              <p>{text.exportCardBody}</p>
            </div>
          </div>
          <div className="export-card-actions">
            <button className="export-button" disabled={exporting} onClick={onExport} type="button">
              {exporting ? text.exporting : text.export}
            </button>
            <button className="preview-button" disabled={previewing} onClick={onPreview} type="button">
              👁 {previewing ? text.exporting : text.previewButton}
            </button>
            <button className="simulate-submit-button" disabled={submitting || !!submission} onClick={onSubmitSimulation} type="button">
              {submission ? simulationText.submitted : submitting ? simulationText.submitting : simulationText.submit}
            </button>
          </div>
          <p className="simulation-disclaimer">{simulationText.disclaimer}</p>
          {submission && (
            <div className="simulation-receipt" role="status">
              <strong>{simulationText.receipt}</strong>
              <code>{submission.receipt_code}</code>
              <span>{new Date(submission.submitted_at).toLocaleString(locale === "vi" ? "vi-VN" : "en-US")}</span>
              <span>{submission.delivery_destination} · PDF {(submission.pdf_size_bytes / 1024).toFixed(1)} KB</span>
              <button className="receipt-download" onClick={onDownloadSubmission} type="button">⬇ Tải PDF đã gửi</button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

type ReviewFormProps = {
  activeFormCode: string | null;
  locale: Locale;
  onFormCodeConsumed: () => void;
  embedded?: boolean;
  onSubmissionComplete?: (submission: SimulatedSubmission) => void;
};

export function ReviewForm({ activeFormCode, locale, onFormCodeConsumed, embedded = false, onSubmissionComplete }: ReviewFormProps) {
  const [formCode, setFormCode] = useState<string | null>(activeFormCode);
  const [schema, setSchema] = useState<FormSchemaResponse | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submission, setSubmission] = useState<SimulatedSubmission | null>(null);
  const [approval, setApproval] = useState<SubmissionApproval | null>(null);
  const [finalConfirmation, setFinalConfirmation] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const text = copy[locale];
  const simulationError = locale === "vi" ? "Không thể nộp mô phỏng." : "Could not simulate submission.";
  const previewUrl = useMemo(() => (previewBlob ? URL.createObjectURL(previewBlob) : null), [previewBlob]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  useEffect(() => {
    if (activeFormCode) {
      setFormCode(activeFormCode);
      onFormCodeConsumed();
    }
  }, [activeFormCode, onFormCodeConsumed]);

  useEffect(() => {
    if (!formCode) return;
    setLoading(true);
    setError(null);
    Promise.all([getFormSchema(formCode), getFormDraft(formCode)])
      .then(([schemaResponse, draftResponse]) => {
        setSchema(schemaResponse);
        setValues(draftResponse.fields as Record<string, string>);
        setValidation(null);
        setDirty(false);
        setPreviewBlob(null);
        setSubmission(null);
        setApproval(null);
        setFinalConfirmation(false);
      })
      .catch(() => setError(text.formLoadError))
      .finally(() => setLoading(false));
  }, [formCode]);

  function updateField(fieldCode: string, value: string) {
    setValues((current) => ({ ...current, [fieldCode]: value }));
    setDirty(true);
    setSubmission(null);
    setApproval(null);
    setFinalConfirmation(false);
  }

  // Always sends the full local snapshot (never a single changed field): the backend
  // PUT does a read-merge-write on the session draft, so overlapping per-field saves
  // from fast sequential edits can race and silently drop an earlier field's value.
  // A self-contained snapshot on every save makes each write independent of write order.
  function enqueueDraftSave(snapshot: Record<string, string>): Promise<unknown> {
    if (!formCode) return Promise.resolve();
    const save = saveChainRef.current
      .catch(() => undefined)
      .then(() => updateFormDraft(formCode, snapshot));
    saveChainRef.current = save;
    return save.catch((error) => {
      setError(text.formSaveError);
      throw error;
    });
  }

  async function persistDraft() {
    await enqueueDraftSave(values).catch(() => undefined);
  }

  function handleSelectChange(fieldCode: string, value: string) {
    const next = { ...values, [fieldCode]: value };
    setValues(next);
    setDirty(true);
    setSubmission(null);
    setApproval(null);
    setFinalConfirmation(false);
    if (formCode) void enqueueDraftSave(next).catch(() => undefined);
  }

  async function runValidation() {
    if (!formCode) return;
    setValidating(true);
    setError(null);
    setPreviewBlob(null);
    setApproval(null);
    setSubmission(null);
    setFinalConfirmation(false);
    try {
      // Validation must observe the exact snapshot visible to the user. A blur
      // save can still be in flight when the button is clicked, so persist and
      // await the complete local state before asking the backend to validate.
      await enqueueDraftSave(values);
      setValidation(await validateForm(formCode));
      setDirty(false);
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : "";
      setValidation(null);
      setError(`${text.formValidateError}${detail ? ` (${detail})` : ""}`);
    } finally {
      setValidating(false);
    }
  }

  async function runExport() {
    if (!formCode || !validation) return;
    setExporting(true);
    setError(null);
    try {
      downloadBlob(await exportFormPdf(formCode, validation.validation_id), `${formCode.toLowerCase()}.pdf`);
    } catch (error) {
      setError(exportErrorMessage(error, text.formExportError));
    } finally {
      setExporting(false);
    }
  }

  async function runPreview() {
    if (!formCode || !validation) return;
    setPreviewing(true);
    setError(null);
    try {
      setPreviewBlob(await exportFormPdf(formCode, validation.validation_id));
    } catch (error) {
      setError(exportErrorMessage(error, text.previewError));
    } finally {
      setPreviewing(false);
    }
  }

  async function runSimulatedSubmission() {
    if (!formCode || !validation) return;
    setSubmitting(true);
    setError(null);
    try {
      setApproval(await requestSubmissionApproval(formCode, validation.validation_id));
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : "";
      setError(`${simulationError}${detail ? ` (${detail})` : ""}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmDataAndPreviewPdf() {
    if (!formCode || !validation || !approval) return;
    setSubmitting(true);
    setError(null);
    try {
      setPreviewBlob(await exportFormPdf(formCode, validation.validation_id));
      setFinalConfirmation(true);
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : "";
      setError(exportErrorMessage(error, `${simulationError} Không thể tạo bản PDF để xác nhận.`));
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmFinalSubmission() {
    if (!formCode || !validation || !approval || !finalConfirmation) return;
    setSubmitting(true);
    setError(null);
    try {
      const completed = await simulateFormSubmission(formCode, validation.validation_id, approval.approval_id);
      setSubmission(completed);
      setApproval(null);
      setFinalConfirmation(false);
      setPreviewBlob(null);
      onSubmissionComplete?.(completed);
    } catch (error) {
      const detail = error instanceof ApiError ? error.detail : "";
      setError(`${simulationError}${detail ? ` (${detail})` : ""}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function downloadSubmittedPdf() {
    if (!submission) return;
    try {
      downloadBlob(await downloadSubmissionArtifact(submission.submission_id), `${submission.receipt_code}.pdf`);
    } catch (error) {
      setError(exportErrorMessage(error, text.formExportError));
    }
  }

  function closePreview() {
    setPreviewBlob(null);
    setFinalConfirmation(false);
  }

  function downloadPreview() {
    if (!formCode || !previewBlob) return;
    downloadBlob(previewBlob, `${formCode.toLowerCase()}.pdf`);
  }

  if (!formCode) return <FormPicker locale={locale} onPick={setFormCode} />;
  if (loading || !schema) return <div className="review-empty"><span aria-hidden="true">📄</span><p>{text.loadingForm}</p></div>;

  const groups = [...schema.groups].sort((a, b) => a.display_order - b.display_order);

  return (
    <div className={`review-form ${embedded ? "review-form-embedded" : ""}`}>
      <div className="review-form-main">
        <div className="review-form-header">
          <div>
            <h2>{schema.title_vi}</h2>
            <button className="link-button" onClick={() => { setFormCode(null); setSchema(null); setApproval(null); setFinalConfirmation(false); }}>{text.changeForm}</button>
          </div>
          <button className="primary-action" onClick={() => void runValidation()} disabled={validating}>
            {validating ? text.validating : text.validate}
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        {groups.map((group) => (
          <section key={group.group_code} className="field-group">
            <h3>{group.label_vi}</h3>
            <div className="field-grid">
              {schema.fields.filter((field) => field.group_code === group.group_code).map((field) => {
                const issue = validation?.issues.find((item) => item.field_code === field.field_code);
                return (
                  <label key={field.field_code} className="field">
                    <span className="field-label">{field.label_vi}{field.required && <span className="required">*</span>}</span>
                    {field.data_type === "enum" ? (
                      <select
                        data-testid={field.field_code}
                        value={values[field.field_code] ?? ""}
                        onChange={(event) => handleSelectChange(field.field_code, event.target.value)}
                        className={issue ? issue.severity : ""}
                      >
                        <option value="">{text.choose}</option>
                        {field.enum_values?.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    ) : field.data_type === "table" ? (
                      <textarea
                        data-testid={field.field_code}
                        value={values[field.field_code] ?? ""}
                        onInput={(event) => updateField(field.field_code, event.currentTarget.value)}
                        onBlur={() => void persistDraft()}
                        className={issue ? issue.severity : ""}
                        rows={2}
                      />
                    ) : (
                      <input
                        data-testid={field.field_code}
                        type={field.data_type === "date" ? "date" : field.data_type === "number" ? "number" : "text"}
                        value={values[field.field_code] ?? ""}
                        onInput={(event) => updateField(field.field_code, event.currentTarget.value)}
                        onBlur={() => void persistDraft()}
                        className={issue ? issue.severity : ""}
                      />
                    )}
                    {issue && <span className={`field-issue ${issue.severity}`}>{issue.message_vi}</span>}
                  </label>
                );
              })}
            </div>
          </section>
        ))}
      </div>
      <ResultPanel
        locale={locale}
        validation={validation}
        dirty={dirty}
        validating={validating}
        onExport={() => void runExport()}
        exporting={exporting}
        onPreview={() => void runPreview()}
        previewing={previewing}
        submission={submission}
        submitting={submitting}
        onSubmitSimulation={() => void runSimulatedSubmission()}
        onDownloadSubmission={() => void downloadSubmittedPdf()}
      />
      {approval && (
        <div className="consent-backdrop" role="presentation">
          <section aria-labelledby="submission-approval-title" aria-modal="true" className="consent-dialog submission-approval-dialog" role="dialog">
            <h2 id="submission-approval-title">Xác nhận hành động một lần</h2>
            <dl>
              <dt>Nơi nhận</dt><dd>{approval.destination}</dd>
              <dt>Mục đích</dt><dd>{approval.purpose}</dd>
              <dt>Dữ liệu đưa vào PDF</dt><dd>{approval.disclosed_fields.join(", ") || "Không có"}</dd>
              <dt>Kết quả</dt><dd>{approval.effect}</dd>
            </dl>
            <p className="simulation-disclaimer">Quyền xác nhận chỉ dùng một lần và hết hạn lúc {new Date(approval.expires_at).toLocaleTimeString(locale === "vi" ? "vi-VN" : "en-US")}.</p>
            <div>
              <button onClick={() => setApproval(null)} type="button">Hủy</button>
              <button className="primary" disabled={submitting} onClick={() => void confirmDataAndPreviewPdf()} type="button">
                {submitting ? "Đang tạo PDF..." : "Xác nhận thông tin và xem PDF"}
              </button>
            </div>
          </section>
        </div>
      )}
      {previewUrl && (
        <div className="pdf-preview-backdrop" role="presentation" onClick={closePreview}>
          <section
            aria-labelledby="pdf-preview-title"
            aria-modal="true"
            className="pdf-preview-dialog"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <header className="pdf-preview-header">
              <h2 id="pdf-preview-title">{finalConfirmation ? "Bước 2/2 · Kiểm tra PDF lần cuối" : text.previewTitle}</h2>
              <div className="pdf-preview-actions">
                <button onClick={downloadPreview} type="button">⬇ {text.downloadInPreview}</button>
                {finalConfirmation && (
                  <button className="final-submit-button" disabled={submitting} onClick={() => void confirmFinalSubmission()} type="button">
                    {submitting ? "Đang gửi..." : "Xác nhận lần cuối và gửi"}
                  </button>
                )}
                <button aria-label={finalConfirmation ? "Quay lại chỉnh sửa" : text.close} className="pdf-preview-close" onClick={closePreview} type="button">✕</button>
              </div>
            </header>
            <iframe className="pdf-preview-frame" src={previewUrl} title={text.previewTitle} />
          </section>
        </div>
      )}
    </div>
  );
}
