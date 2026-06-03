import type {
  ApiError,
  CadPreviewWorkflowResult,
  MoldingFormValues,
  MoldingQuoteWorkflowResult,
  QuoteFormValues,
  QuoteWorkflowResult,
  SheetMetalFormValues,
  SheetMetalQuoteWorkflowResult,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function buildQuoteFormData(file: File, values: QuoteFormValues): FormData {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("material", values.material);
  formData.append("quantity", String(values.quantity));
  formData.append("tolerance_class", values.tolerance_class);
  formData.append("finish", values.finish);
  formData.append("lead_time_class", values.lead_time_class);
  if (values.notes.trim()) {
    formData.append("notes", values.notes.trim());
  }
  return formData;
}

export function buildMoldingQuoteFormData(file: File, values: MoldingFormValues): FormData {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("material", values.material);
  formData.append("quantity", String(values.quantity));
  formData.append("annual_volume", String(values.annual_volume));
  formData.append("cavities", String(values.cavities));
  formData.append("mold_class", values.mold_class);
  formData.append("finish", values.finish);
  formData.append("lead_time_class", values.lead_time_class);
  if (values.notes.trim()) {
    formData.append("notes", values.notes.trim());
  }
  return formData;
}

export function buildSheetMetalQuoteFormData(file: File, values: SheetMetalFormValues): FormData {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("material", values.material);
  formData.append("quantity", String(values.quantity));
  formData.append("finish", values.finish);
  formData.append("lead_time_class", values.lead_time_class);
  if (values.notes.trim()) {
    formData.append("notes", values.notes.trim());
  }
  return formData;
}

export async function submitCadPreview(file: File): Promise<CadPreviewWorkflowResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/cad/preview`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail as ApiError | undefined;
    throw new Error(detail ? `${detail.code}: ${detail.message}` : `Request failed with ${response.status}`);
  }

  return (await response.json()) as CadPreviewWorkflowResult;
}

export async function submitCncQuote(file: File, values: QuoteFormValues): Promise<QuoteWorkflowResult> {
  const response = await fetch(`${API_BASE_URL}/quotes/cnc`, {
    method: "POST",
    body: buildQuoteFormData(file, values),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail as ApiError | undefined;
    throw new Error(detail ? `${detail.code}: ${detail.message}` : `Request failed with ${response.status}`);
  }

  return (await response.json()) as QuoteWorkflowResult;
}

export async function submitMoldingQuote(
  file: File,
  values: MoldingFormValues,
): Promise<MoldingQuoteWorkflowResult> {
  const response = await fetch(`${API_BASE_URL}/quotes/injection-molding`, {
    method: "POST",
    body: buildMoldingQuoteFormData(file, values),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail as ApiError | undefined;
    throw new Error(detail ? `${detail.code}: ${detail.message}` : `Request failed with ${response.status}`);
  }

  return (await response.json()) as MoldingQuoteWorkflowResult;
}

export async function submitSheetMetalQuote(
  file: File,
  values: SheetMetalFormValues,
): Promise<SheetMetalQuoteWorkflowResult> {
  const response = await fetch(`${API_BASE_URL}/quotes/sheet-metal`, {
    method: "POST",
    body: buildSheetMetalQuoteFormData(file, values),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail as ApiError | undefined;
    throw new Error(detail ? `${detail.code}: ${detail.message}` : `Request failed with ${response.status}`);
  }

  return (await response.json()) as SheetMetalQuoteWorkflowResult;
}
