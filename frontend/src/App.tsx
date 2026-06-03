import { AlertTriangle, Calculator, CheckCircle2, FileUp, Loader2, SlidersHorizontal } from "lucide-react";
import { ChangeEvent, FormEvent, useMemo, useRef, useState } from "react";
import { submitCadPreview, submitCncQuote, submitMoldingQuote, submitSheetMetalQuote } from "./api";
import { MeshPreview } from "./components/MeshPreview";
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
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isQuoteLoading, setIsQuoteLoading] = useState(false);
  const previewRequestId = useRef(0);
  const hasManualProcessSelection = useRef(false);

  const activeResult =
    process === "cnc" ? cncResult : process === "injection_molding" ? moldingResult : process === "sheet_metal" ? sheetMetalResult : null;
  const cadFacts = previewResult?.source ?? activeResult?.quote.source.source;
  const preview = previewResult?.preview ?? activeResult?.preview ?? null;
  const canSubmit =
    file !== null && !isQuoteLoading && (process === "cnc" || process === "injection_molding" || process === "sheet_metal");
  const activeComplexity = activeResult?.quote.source.complexity.score;
  const processFit = previewResult?.process_fit ?? null;

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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Select a STEP or STP file first.");
      return;
    }
    setIsQuoteLoading(true);
    setError(null);
    try {
      if (process === "cnc") {
        setCncResult(await submitCncQuote(file, cncValues));
        setMoldingResult(null);
        setSheetMetalResult(null);
      } else if (process === "injection_molding") {
        setMoldingResult(await submitMoldingQuote(file, moldingValues));
        setCncResult(null);
        setSheetMetalResult(null);
      } else if (process === "sheet_metal") {
        setSheetMetalResult(await submitSheetMetalQuote(file, sheetMetalValues));
        setCncResult(null);
        setMoldingResult(null);
      } else {
        throw new Error(`${processLabel(process)} quoting is not implemented yet.`);
      }
    } catch (requestError) {
      setCncResult(null);
      setMoldingResult(null);
      setSheetMetalResult(null);
      setError(requestError instanceof Error ? requestError.message : "Quote request failed.");
    } finally {
      setIsQuoteLoading(false);
    }
  }

  const dimensions = useMemo(() => formatDimensions(cadFacts), [cadFacts]);
  const quoteLabel = `${processLabel(process)} quote`;

  function selectProcess(nextProcess: ManufacturingProcess) {
    hasManualProcessSelection.current = true;
    setProcess(nextProcess);
    setCncResult(null);
    setMoldingResult(null);
    setSheetMetalResult(null);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>RFQ Engine</h1>
          <p>Budgetary quoting from real STEP geometry</p>
        </div>
        <div className="status-strip">
          <span>OpenCascade backend</span>
          <span>STEP-derived preview mesh</span>
        </div>
      </header>

      <div className="workspace">
        <section className="control-panel">
          <form onSubmit={onSubmit} className="quote-form">
            <div className="section-heading">
              <FileUp size={18} />
              <h2>Upload</h2>
            </div>
            <label className="file-input">
              <input type="file" accept=".step,.stp" onChange={(event) => void onFileChange(event)} />
              <span>{isPreviewLoading ? "Loading preview" : file ? file.name : "Choose STEP/STP file"}</span>
            </label>
            {file && <p className="file-meta">{formatBytes(file.size)}</p>}
            <MeshPreview preview={preview} isLoading={isPreviewLoading} />

            <div className="section-heading">
              <SlidersHorizontal size={18} />
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

            {process === "cnc" ? (
              <CncInputs values={cncValues} onChange={setCncValues} />
            ) : process === "injection_molding" ? (
              <MoldingInputs values={moldingValues} onChange={setMoldingValues} />
            ) : process === "sheet_metal" ? (
              <SheetMetalInputs values={sheetMetalValues} onChange={setSheetMetalValues} />
            ) : (
              <UnsupportedInputs process={process} />
            )}

            <button className="primary-action" type="submit" disabled={!canSubmit}>
              {isQuoteLoading ? <Loader2 className="spin" size={18} /> : <Calculator size={18} />}
              <span>{isQuoteLoading ? "Quoting" : "Generate Quote"}</span>
            </button>
          </form>
        </section>

        <section className="main-panel">
          <div className="detail-grid">
            <section className="summary-panel">
              <h2>CAD Facts</h2>
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
            </section>

            <section className="summary-panel">
              <h2>{quoteLabel}</h2>
              {process === "cnc" ? (
                <CncQuoteSummary result={cncResult} />
              ) : process === "injection_molding" ? (
                <MoldingQuoteSummary result={moldingResult} />
              ) : process === "sheet_metal" ? (
                <SheetMetalQuoteSummary result={sheetMetalResult} />
              ) : (
                <UnsupportedQuoteSummary process={process} />
              )}
            </section>
          </div>

          {error && (
            <div className="notice error">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}
          {activeResult && (
            <div className="notice success">
              <CheckCircle2 size={18} />
              <span>Quote completed in {activeResult.workflow.elapsed_ms.toFixed(0)} ms for {activeResult.upload.filename}.</span>
            </div>
          )}
          {previewResult && !activeResult && (
            <div className="notice success">
              <CheckCircle2 size={18} />
              <span>Preview generated in {previewResult.workflow.elapsed_ms.toFixed(0)} ms for {previewResult.upload.filename}.</span>
            </div>
          )}
          {activeResult && (
            <section className="messages">
              <MessageList title="Warnings" items={activeResult.workflow.warnings} />
              <MessageList title="Assumptions" items={activeResult.quote.assumptions} />
            </section>
          )}
        </section>
      </div>
    </main>
  );
}

function CncInputs({ values, onChange }: { values: QuoteFormValues; onChange: (values: QuoteFormValues) => void }) {
  return (
    <>
      <div className="section-heading">
        <Calculator size={18} />
        <h2>CNC Inputs</h2>
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
          onChange={(event) => onChange({ ...values, quantity: Number(event.target.value) })}
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
    </>
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
    <>
      <div className="section-heading">
        <Calculator size={18} />
        <h2>Molding Inputs</h2>
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
            onChange={(event) => onChange({ ...values, quantity: Number(event.target.value) })}
          />
        </label>
        <label>
          Annual volume
          <input
            type="number"
            min="1"
            value={values.annual_volume}
            onChange={(event) => onChange({ ...values, annual_volume: Number(event.target.value) })}
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
    </>
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
    <>
      <div className="section-heading">
        <Calculator size={18} />
        <h2>Sheet Metal Inputs</h2>
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
          onChange={(event) => onChange({ ...values, quantity: Number(event.target.value) })}
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
    </>
  );
}

function UnsupportedInputs({ process }: { process: ManufacturingProcess }) {
  return (
    <>
      <div className="section-heading">
        <Calculator size={18} />
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

function CncQuoteSummary({ result }: { result: QuoteWorkflowResult | null }) {
  if (!result) {
    return <p className="muted">Submit a STEP file to calculate a budgetary CNC quote.</p>;
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

function MoldingQuoteSummary({ result }: { result: MoldingQuoteWorkflowResult | null }) {
  if (!result) {
    return <p className="muted">Submit a STEP file to calculate a budgetary injection molding quote.</p>;
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

function SheetMetalQuoteSummary({ result }: { result: SheetMetalQuoteWorkflowResult | null }) {
  if (!result) {
    return <p className="muted">Submit a STEP file to calculate a budgetary sheet metal quote.</p>;
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

function MessageList({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h2>{title}</h2>
      <ul>
        {items.map((item) => (
          <li key={item}>{item.replace(/_/g, " ")}</li>
        ))}
      </ul>
    </section>
  );
}

function formatDimensions(cadFacts: StepParseResult | undefined) {
  if (!cadFacts) {
    return "No dimensions yet";
  }
  const mm = cadFacts.bounding_box.size.map((value) => `${value.toFixed(1)} mm`).join(" x ");
  const sourceUnits = cadFacts.diagnostics.source_length_units.map((unit) => unit.toUpperCase());
  if (sourceUnits.includes("INCH")) {
    const inches = cadFacts.bounding_box.size.map((value) => `${(value / 25.4).toFixed(3)} in`).join(" x ");
    return `${mm} (${inches})`;
  }
  return mm;
}

function formatBytes(size: number) {
  if (size < 1024) {
    return `${size} bytes`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
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
