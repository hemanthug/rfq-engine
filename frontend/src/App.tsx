import { AlertTriangle, CheckCircle2, Download, X } from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { submitCadPreview, submitCncQuote, submitMoldingQuote, submitSheetMetalQuote } from "./api";
import { LoadingSteps } from "./components/LoadingSteps";
import { MeshPreview } from "./components/MeshPreview";
import { downloadQuotePdf } from "./pdfQuote";
import type {
  CadPreviewWorkflowResult,
  ManufacturingProcess,
  MoldingFormValues,
  MoldingQuoteWorkflowResult,
  QuoteFormValues,
  QuoteWorkflowResult,
  SheetMetalFormValues,
  SheetMetalQuoteWorkflowResult,
  StepParseResult,
} from "./types";

const DEFAULT_CNC_VALUES: QuoteFormValues = {
  material: "aluminum_6061",
  quantity: 1,
  tolerance_class: "standard",
  finish: "as_machined",
  lead_time_class: "standard",
  notes: "",
};

const DEFAULT_MOLDING_VALUES: MoldingFormValues = {
  material: "abs",
  quantity: 1000,
  annual_volume: 10000,
  cavities: "auto",
  mold_class: "production",
  finish: "standard_spi_b3",
  lead_time_class: "standard",
  notes: "",
};

const DEFAULT_SHEET_METAL_VALUES: SheetMetalFormValues = {
  material: "aluminum_5052",
  quantity: 1,
  finish: "raw",
  lead_time_class: "standard",
  notes: "",
};

const cncMaterialOptions = [
  ["aluminum_6061", "Aluminum 6061"],
  ["steel_1018", "Steel 1018"],
  ["stainless_304", "Stainless 304"],
  ["brass_c360", "Brass C360"],
  ["delrin", "Delrin"],
];

const moldingMaterialOptions = [
  ["abs", "ABS"],
  ["pp", "Polypropylene"],
  ["pc", "Polycarbonate"],
  ["nylon_66", "Nylon 6/6"],
  ["acetal_pom", "Acetal/POM"],
];

const sheetMetalMaterialOptions = [
  ["aluminum_5052", "Aluminum 5052"],
  ["steel_crs", "Cold rolled steel"],
  ["stainless_304", "Stainless 304"],
  ["galvanized_steel", "Galvanized steel"],
];

const processOptions: { value: ManufacturingProcess; label: string; implemented: boolean }[] = [
  { value: "cnc", label: "CNC", implemented: true },
  { value: "injection_molding", label: "Injection molding", implemented: true },
  { value: "sheet_metal", label: "Sheet metal", implemented: true },
  { value: "3d_printing", label: "3D printing", implemented: false },
];

const QUOTE_DEBOUNCE_MS = 450;

const QUOTE_STEPS = [
  "Analyzing geometry",
  "Extracting features",
  "Applying material & rates",
  "Calculating price",
];

const DISCLAIMER_STORAGE_KEY = "rfq-engine-pricing-disclaimer-dismissed";

function isImplementedProcess(process: ManufacturingProcess) {
  return process === "cnc" || process === "injection_molding" || process === "sheet_metal";
}

function parsePositiveInt(value: string, fallback: number) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function App() {
  const [process, setProcess] = useState<ManufacturingProcess>("cnc");
  const [file, setFile] = useState<File | null>(null);
  const [cncValues, setCncValues] = useState<QuoteFormValues>(DEFAULT_CNC_VALUES);
  const [moldingValues, setMoldingValues] = useState<MoldingFormValues>(DEFAULT_MOLDING_VALUES);
  const [sheetMetalValues, setSheetMetalValues] = useState<SheetMetalFormValues>(DEFAULT_SHEET_METAL_VALUES);
  const [previewResult, setPreviewResult] = useState<CadPreviewWorkflowResult | null>(null);
  const [cncResult, setCncResult] = useState<QuoteWorkflowResult | null>(null);
  const [moldingResult, setMoldingResult] = useState<MoldingQuoteWorkflowResult | null>(null);
  const [sheetMetalResult, setSheetMetalResult] = useState<SheetMetalQuoteWorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDisclaimerVisible, setIsDisclaimerVisible] = useState(() => localStorage.getItem(DISCLAIMER_STORAGE_KEY) !== "true");
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isQuoteLoading, setIsQuoteLoading] = useState(false);
  const previewRequestId = useRef(0);
  const quoteRequestId = useRef(0);
  const hasManualProcessSelection = useRef(false);

  const activeResult =
    process === "cnc" ? cncResult : process === "injection_molding" ? moldingResult : process === "sheet_metal" ? sheetMetalResult : null;
  const cadFacts = previewResult?.source ?? activeResult?.quote.source.source;
  const preview = previewResult?.preview ?? activeResult?.preview ?? null;
  const canQuote = file !== null && isImplementedProcess(process) && previewResult !== null && !isPreviewLoading;
  const activeComplexity = activeResult?.quote.source.complexity.score;
  const processFit = previewResult?.process_fit ?? null;

  const runQuote = useCallback(async () => {
    if (!file || !isImplementedProcess(process)) {
      return;
    }

    const requestId = quoteRequestId.current + 1;
    quoteRequestId.current = requestId;
    setIsQuoteLoading(true);
    setError(null);

    try {
      if (process === "cnc") {
        const result = await submitCncQuote(file, cncValues);
        if (quoteRequestId.current !== requestId) {
          return;
        }
        setCncResult(result);
        setMoldingResult(null);
        setSheetMetalResult(null);
      } else if (process === "injection_molding") {
        const result = await submitMoldingQuote(file, moldingValues);
        if (quoteRequestId.current !== requestId) {
          return;
        }
        setMoldingResult(result);
        setCncResult(null);
        setSheetMetalResult(null);
      } else if (process === "sheet_metal") {
        const result = await submitSheetMetalQuote(file, sheetMetalValues);
        if (quoteRequestId.current !== requestId) {
          return;
        }
        setSheetMetalResult(result);
        setCncResult(null);
        setMoldingResult(null);
      }
    } catch (requestError) {
      if (quoteRequestId.current !== requestId) {
        return;
      }
      setCncResult(null);
      setMoldingResult(null);
      setSheetMetalResult(null);
      setError(requestError instanceof Error ? requestError.message : "Quote request failed.");
    } finally {
      if (quoteRequestId.current === requestId) {
        setIsQuoteLoading(false);
      }
    }
  }, [file, process, cncValues, moldingValues, sheetMetalValues]);

  useEffect(() => {
    if (!canQuote) {
      return;
    }

    const timer = window.setTimeout(() => {
      void runQuote();
    }, QUOTE_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [canQuote, runQuote]);

  async function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null;
    const requestId = previewRequestId.current + 1;
    previewRequestId.current = requestId;
    setFile(selectedFile);
    setPreviewResult(null);
    setCncResult(null);
    setMoldingResult(null);
    setSheetMetalResult(null);
    setError(null);
    hasManualProcessSelection.current = false;

    if (!selectedFile) {
      setIsPreviewLoading(false);
      return;
    }

    setIsPreviewLoading(true);
    try {
      const nextPreview = await submitCadPreview(selectedFile);
      if (previewRequestId.current === requestId) {
        setPreviewResult(nextPreview);
        if (!hasManualProcessSelection.current && nextPreview.process_fit?.recommended_process) {
          setProcess(nextPreview.process_fit.recommended_process);
        }
      }
    } catch (requestError) {
      if (previewRequestId.current === requestId) {
        setError(requestError instanceof Error ? requestError.message : "Preview request failed.");
      }
    } finally {
      if (previewRequestId.current === requestId) {
        setIsPreviewLoading(false);
      }
    }
  }

  const dimensions = useMemo(() => formatDimensions(cadFacts), [cadFacts]);
  function startNewQuote() {
    previewRequestId.current += 1;
    quoteRequestId.current += 1;
    setFile(null);
    setPreviewResult(null);
    setCncResult(null);
    setMoldingResult(null);
    setSheetMetalResult(null);
    setError(null);
    setIsPreviewLoading(false);
    setIsQuoteLoading(false);
    hasManualProcessSelection.current = false;
  }

  function selectProcess(nextProcess: ManufacturingProcess) {
    hasManualProcessSelection.current = true;
    setProcess(nextProcess);
    setCncResult(null);
    setMoldingResult(null);
    setSheetMetalResult(null);
  }

  function dismissDisclaimer() {
    localStorage.setItem(DISCLAIMER_STORAGE_KEY, "true");
    setIsDisclaimerVisible(false);
  }

  function downloadActiveQuote() {
    if (!activeResult) {
      return;
    }
    try {
      downloadQuotePdf(activeResult, process);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "PDF download failed.");
    }
  }

  function restoreDisclaimer() {
    localStorage.removeItem(DISCLAIMER_STORAGE_KEY);
    setIsDisclaimerVisible(true);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>RFQ Generator</h1>
          <p>Instant budgetary quoting from real STEP geometry</p>
        </div>
      </header>

      {isDisclaimerVisible ? (
        <section className="calibration-banner" aria-label="Pricing calibration disclaimer">
          <div>
            <strong>Budgetary pricing uses example figures today.</strong>
            <span>
              Production deployments can be trained and calibrated from your historical quotes, then configured with your
              actual material costs, machine rates, labor rates, margins, and pricing rules.
            </span>
          </div>
          <button type="button" aria-label="Dismiss pricing disclaimer" onClick={dismissDisclaimer}>
            <X size={16} />
          </button>
        </section>
      ) : (
        <div className="calibration-restore">
          <button type="button" onClick={restoreDisclaimer}>
            Pricing notice
          </button>
        </div>
      )}

      <div className={file ? "workspace" : "workspace workspace-empty"}>
        {file && (
          <div className="preview-stage">
            <MeshPreview
              preview={preview}
              isLoading={isPreviewLoading}
              onNewQuote={startNewQuote}
            />
            <aside className="price-rail" aria-label="Quote summary">
              <div className="price-rail-head">
                <h2>Quote</h2>
                <div className="price-rail-actions">
                  <span>{processLabel(process)}</span>
                </div>
              </div>
              <div className="price-rail-body">
                {process === "cnc" ? (
                  <CncQuoteSummary result={cncResult} isLoading={isQuoteLoading} hasFile={file !== null} />
                ) : process === "injection_molding" ? (
                  <MoldingQuoteSummary result={moldingResult} isLoading={isQuoteLoading} hasFile={file !== null} />
                ) : process === "sheet_metal" ? (
                  <SheetMetalQuoteSummary result={sheetMetalResult} isLoading={isQuoteLoading} hasFile={file !== null} />
                ) : (
                  <UnsupportedQuoteSummary process={process} />
                )}
                {activeResult && (
                  <button type="button" className="quote-download-action" onClick={downloadActiveQuote}>
                    <Download size={17} />
                    <span>Download sendable PDF quote</span>
                  </button>
                )}
              </div>
            </aside>
          </div>
        )}
        <div className="left-rail">
        {!file && (
        <section className="control-panel">
          <div className="quote-form">
            <div className="section-heading">
              <h2>Upload</h2>
            </div>
            <label className="file-input">
              <input type="file" accept=".step,.stp" onChange={(event) => void onFileChange(event)} />
              <span>{isPreviewLoading ? "Analyzing STEP file…" : "Drop a STEP / STP file, or click to browse"}</span>
            </label>
          </div>
        </section>
        )}

        {file && (
          <>
            <details className="messages-disclosure" open>
              <summary>
                <div className="disclosure-intro">
                  <span className="disclosure-label">Model properties</span>
                </div>
              </summary>
              <div className="disclosure-body metric-list">
                <Metric label="Dimensions" value={dimensions} />
                <Metric
                  label="Source units"
                  value={
                    cadFacts
                      ? `${cadFacts.diagnostics.source_length_units.join(", ")} -> ${cadFacts.diagnostics.canonical_unit}`
                      : "Pending"
                  }
                />
                <Metric label="Volume" value={cadFacts ? `${cadFacts.mass_properties.volume.toFixed(1)} mm3` : "Pending"} />
                <Metric
                  label="Surface area"
                  value={cadFacts ? `${cadFacts.mass_properties.surface_area.toFixed(1)} mm2` : "Pending"}
                />
                <Metric
                  label="Faces / edges"
                  value={cadFacts ? `${cadFacts.topology.faces} / ${cadFacts.topology.edges}` : "Pending"}
                />
                <Metric label="Complexity" value={activeComplexity !== undefined ? String(activeComplexity) : "Pending"} />
              </div>
            </details>
            {activeResult && (
              <details className="messages-disclosure">
                <summary>
                  <div className="disclosure-intro">
                    <span className="disclosure-label">Assumptions</span>
                    <span className="disclosure-note">Will be calibrated to your operations</span>
                  </div>
                  <span className="disclosure-counts">
                    {activeResult.quote.assumptions.length} assumptions
                  </span>
                </summary>
                <div className="disclosure-body">
                  <ul className="disclosure-list">
                    {activeResult.quote.assumptions.map((item) => (
                      <li key={item}>{item.replace(/_/g, " ")}</li>
                    ))}
                  </ul>
                </div>
              </details>
            )}
          </>
        )}
        </div>

        {file && (
        <section className="main-panel">
            <section className="summary-panel quote-panel">
              <div className="parameter-panel">
                <div className="section-heading">
                  <h2>Process</h2>
                </div>
                {processFit && <ProcessRecommendationNote processFit={processFit} />}
                <div className="process-toggle process-toggle-four" role="group" aria-label="Manufacturing process">
                  {processOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={process === option.value ? "active" : ""}
                      onClick={() => selectProcess(option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                {!isImplementedProcess(process) && <UnsupportedInputs process={process} />}
              </div>
              {canQuote && process === "cnc" ? (
                <CncInputs values={cncValues} onChange={setCncValues} />
              ) : canQuote && process === "injection_molding" ? (
                <MoldingInputs values={moldingValues} onChange={setMoldingValues} />
              ) : canQuote && process === "sheet_metal" ? (
                <SheetMetalInputs values={sheetMetalValues} onChange={setSheetMetalValues} />
              ) : null}
            </section>

          {error && (
            <div className="notice error">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}
          {previewResult && !activeResult && (
            <div className="notice success">
              <CheckCircle2 size={18} />
              <span>Preview generated in {previewResult.workflow.elapsed_ms.toFixed(0)} ms for {previewResult.upload.filename}.</span>
            </div>
          )}
        </section>
        )}
      </div>
    </main>
  );
}

function CncInputs({ values, onChange }: { values: QuoteFormValues; onChange: (values: QuoteFormValues) => void }) {
  return (
    <div className="parameter-panel">
      <div className="section-heading">
        <h2>Parameters</h2>
      </div>
      <label>
        Material
        <select value={values.material} onChange={(event) => onChange({ ...values, material: event.target.value })}>
          {cncMaterialOptions.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Quantity
        <input
          type="number"
          min="1"
          value={values.quantity}
          onChange={(event) => onChange({ ...values, quantity: parsePositiveInt(event.target.value, values.quantity) })}
        />
      </label>
      <label>
        Tolerance
        <select value={values.tolerance_class} onChange={(event) => onChange({ ...values, tolerance_class: event.target.value })}>
          <option value="standard">Standard</option>
          <option value="tight">Tight</option>
          <option value="precision">Precision</option>
        </select>
      </label>
      <label>
        Finish
        <select value={values.finish} onChange={(event) => onChange({ ...values, finish: event.target.value })}>
          <option value="as_machined">As machined</option>
          <option value="bead_blasted">Bead blasted</option>
          <option value="anodized_clear">Clear anodized</option>
        </select>
      </label>
      <label>
        Lead time
        <select value={values.lead_time_class} onChange={(event) => onChange({ ...values, lead_time_class: event.target.value })}>
          <option value="economy">Economy</option>
          <option value="standard">Standard</option>
          <option value="expedited">Expedited</option>
        </select>
      </label>
      <NotesField value={values.notes} onChange={(notes) => onChange({ ...values, notes })} />
    </div>
  );
}

function MoldingInputs({
  values,
  onChange,
}: {
  values: MoldingFormValues;
  onChange: (values: MoldingFormValues) => void;
}) {
  return (
    <div className="parameter-panel">
      <div className="section-heading">
        <h2>Parameters</h2>
      </div>
      <label>
        Material
        <select value={values.material} onChange={(event) => onChange({ ...values, material: event.target.value })}>
          {moldingMaterialOptions.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div className="form-grid">
        <label>
          Quantity
          <input
            type="number"
            min="1"
            value={values.quantity}
            onChange={(event) => onChange({ ...values, quantity: parsePositiveInt(event.target.value, values.quantity) })}
          />
        </label>
        <label>
          Annual volume
          <input
            type="number"
            min="1"
            value={values.annual_volume}
            onChange={(event) => onChange({ ...values, annual_volume: parsePositiveInt(event.target.value, values.annual_volume) })}
          />
        </label>
      </div>
      <label>
        Cavities
        <select
          value={values.cavities}
          onChange={(event) => onChange({ ...values, cavities: event.target.value as MoldingFormValues["cavities"] })}
        >
          <option value="auto">Auto</option>
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="4">4</option>
          <option value="8">8</option>
        </select>
      </label>
      <label>
        Mold class
        <select value={values.mold_class} onChange={(event) => onChange({ ...values, mold_class: event.target.value })}>
          <option value="prototype">Prototype</option>
          <option value="bridge">Bridge</option>
          <option value="production">Production</option>
          <option value="high_volume">High-volume production</option>
        </select>
      </label>
      <label>
        Finish
        <select value={values.finish} onChange={(event) => onChange({ ...values, finish: event.target.value })}>
          <option value="standard_spi_b3">Standard SPI-B3</option>
          <option value="matte_texture">Matte texture</option>
          <option value="polished">Polished</option>
        </select>
      </label>
      <label>
        Lead time
        <select value={values.lead_time_class} onChange={(event) => onChange({ ...values, lead_time_class: event.target.value })}>
          <option value="standard">Standard</option>
          <option value="expedited">Expedited</option>
        </select>
      </label>
      <NotesField value={values.notes} onChange={(notes) => onChange({ ...values, notes })} />
    </div>
  );
}

function SheetMetalInputs({
  values,
  onChange,
}: {
  values: SheetMetalFormValues;
  onChange: (values: SheetMetalFormValues) => void;
}) {
  return (
    <div className="parameter-panel">
      <div className="section-heading">
        <h2>Parameters</h2>
      </div>
      <label>
        Material
        <select value={values.material} onChange={(event) => onChange({ ...values, material: event.target.value })}>
          {sheetMetalMaterialOptions.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Quantity
        <input
          type="number"
          min="1"
          value={values.quantity}
          onChange={(event) => onChange({ ...values, quantity: parsePositiveInt(event.target.value, values.quantity) })}
        />
      </label>
      <label>
        Finish
        <select value={values.finish} onChange={(event) => onChange({ ...values, finish: event.target.value })}>
          <option value="raw">Raw</option>
          <option value="grained">Grained/deburred</option>
          <option value="powder_coat">Powder coat</option>
        </select>
      </label>
      <label>
        Lead time
        <select value={values.lead_time_class} onChange={(event) => onChange({ ...values, lead_time_class: event.target.value })}>
          <option value="economy">Economy</option>
          <option value="standard">Standard</option>
          <option value="expedited">Expedited</option>
        </select>
      </label>
      <NotesField value={values.notes} onChange={(notes) => onChange({ ...values, notes })} />
    </div>
  );
}

function UnsupportedInputs({ process }: { process: ManufacturingProcess }) {
  return (
    <>
      <div className="section-heading">
        <h2>{processLabel(process)} Inputs</h2>
      </div>
      <p className="muted">
        {processLabel(process)} process fit can be recommended from CAD now. Quote inputs for this method are not implemented yet.
      </p>
    </>
  );
}

function NotesField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <label>
      Notes
      <textarea rows={3} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function CncQuoteSummary({
  result,
  isLoading,
  hasFile,
}: {
  result: QuoteWorkflowResult | null;
  isLoading: boolean;
  hasFile: boolean;
}) {
  if (!hasFile) {
    return <p className="muted">Upload a STEP file to calculate a budgetary CNC quote.</p>;
  }
  if (!result && isLoading) {
    return <LoadingSteps title="Pricing CNC part" steps={QUOTE_STEPS} />;
  }
  if (!result) {
    return <p className="muted">Adjust parameters below to generate a budgetary CNC quote.</p>;
  }

  return (
    <>
      <div className="quote-total">
        <span>
          {result.quote.currency} {result.quote.subtotal.toFixed(2)}
        </span>
        <small>
          {result.quote.currency} {result.quote.unit_price.toFixed(2)} / unit
        </small>
      </div>
      <LineItems currency={result.quote.currency} items={result.quote.line_items} />
    </>
  );
}

function MoldingQuoteSummary({
  result,
  isLoading,
  hasFile,
}: {
  result: MoldingQuoteWorkflowResult | null;
  isLoading: boolean;
  hasFile: boolean;
}) {
  if (!hasFile) {
    return <p className="muted">Upload a STEP file to calculate a budgetary injection molding quote.</p>;
  }
  if (!result && isLoading) {
    return <LoadingSteps title="Pricing molded part" steps={QUOTE_STEPS} />;
  }
  if (!result) {
    return <p className="muted">Adjust parameters below to generate a budgetary injection molding quote.</p>;
  }

  return (
    <>
      <div className="quote-total">
        <span>
          {result.quote.currency} {result.quote.total_first_order_cost.toFixed(2)}
        </span>
        <small>
          {result.quote.currency} {result.quote.unit_price.toFixed(2)} / production unit
        </small>
      </div>
      <div className="total-breakout">
        <Metric label="Tooling" value={`${result.quote.currency} ${result.quote.tooling_cost.toFixed(2)}`} />
        <Metric label="Production" value={`${result.quote.currency} ${result.quote.production_subtotal.toFixed(2)}`} />
        <Metric
          label="Cavities used"
          value={`${result.quote.request.cavities} (${result.quote.diagnostics.cavity_recommendation.user_overrode_cavities ? "manual" : "auto"})`}
        />
        <Metric
          label="Amortized unit"
          value={`${result.quote.currency} ${result.quote.diagnostics.effective_amortized_unit_price.toFixed(2)}`}
        />
      </div>
      <p className="recommendation-note">
        {result.quote.diagnostics.cavity_recommendation.cavity_recommendation_reason}
      </p>
      <h3>Tooling</h3>
      <LineItems currency={result.quote.currency} items={result.quote.tooling_line_items} />
      <h3>Production</h3>
      <LineItems currency={result.quote.currency} items={result.quote.production_line_items} />
    </>
  );
}

function SheetMetalQuoteSummary({
  result,
  isLoading,
  hasFile,
}: {
  result: SheetMetalQuoteWorkflowResult | null;
  isLoading: boolean;
  hasFile: boolean;
}) {
  if (!hasFile) {
    return <p className="muted">Upload a STEP file to calculate a budgetary sheet metal quote.</p>;
  }
  if (!result && isLoading) {
    return <LoadingSteps title="Pricing sheet metal part" steps={QUOTE_STEPS} />;
  }
  if (!result) {
    return <p className="muted">Adjust parameters below to generate a budgetary sheet metal quote.</p>;
  }

  const signals = result.quote.diagnostics.geometry_signals;
  return (
    <>
      <div className="quote-total">
        <span>
          {result.quote.currency} {result.quote.subtotal.toFixed(2)}
        </span>
        <small>
          {result.quote.currency} {result.quote.unit_price.toFixed(2)} / unit
        </small>
      </div>
      <div className="total-breakout">
        <Metric label="Thickness" value={`${signals.estimated_thickness_mm.toFixed(2)} mm`} />
        <Metric label="Bend candidates" value={String(Math.round(signals.bend_candidate_count))} />
        <Metric label="Sheet confidence" value={`${signals.sheet_metal_confidence_score.toFixed(0)} / 100`} />
      </div>
      <LineItems currency={result.quote.currency} items={result.quote.line_items} />
    </>
  );
}

function UnsupportedQuoteSummary({ process }: { process: ManufacturingProcess }) {
  return (
    <p className="muted">
      {processLabel(process)} was ranked for process fit, but this quote module has not been added yet.
    </p>
  );
}

function ProcessRecommendationNote({ processFit }: { processFit: NonNullable<CadPreviewWorkflowResult["process_fit"]> }) {
  const topReason = processFit.reasons[0] ?? "CAD geometry was evaluated against available manufacturing methods.";
  return (
    <div className="recommendation-note">
      <strong>Recommended: {processLabel(processFit.recommended_process)}</strong>
      <span>Confidence: {processFit.confidence}</span>
      <small>{topReason}</small>
    </div>
  );
}

function LineItems({ currency, items }: { currency: string; items: { code: string; label: string; amount: number }[] }) {
  return (
    <div className="line-items">
      {items.map((item) => (
        <div className="line-item" key={item.code}>
          <span>{item.label}</span>
          <strong>
            {currency} {item.amount.toFixed(2)}
          </strong>
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatDimensions(cadFacts: StepParseResult | undefined) {
  if (!cadFacts) {
    return "No dimensions yet";
  }
  return `${cadFacts.bounding_box.size.map((value) => value.toFixed(1)).join(" × ")} mm`;
}

function processLabel(process: ManufacturingProcess) {
  switch (process) {
    case "cnc":
      return "CNC";
    case "injection_molding":
      return "Injection molding";
    case "3d_printing":
      return "3D printing";
    case "sheet_metal":
      return "Sheet metal";
  }
}
