import jsPDF from "jspdf";
import type {
  ManufacturingProcess,
  MoldingQuoteWorkflowResult,
  PricingLineItem,
  QuoteWorkflowResult,
  SheetMetalQuoteWorkflowResult,
  StepParseResult,
} from "./types";

type AnyQuoteResult = QuoteWorkflowResult | MoldingQuoteWorkflowResult | SheetMetalQuoteWorkflowResult;

const PAGE_WIDTH = 210;
const PAGE_HEIGHT = 297;
const MARGIN = 16;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
const DISCLAIMER =
  "Current pricing uses example/default rate-card figures. In production, this model can be calibrated from your historical quotes and configured with your actual materials, machine rates, labor rates, margins, and pricing rules.";

export function downloadQuotePdf(result: AnyQuoteResult, process: ManufacturingProcess) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const quote = result.quote;
  const quoteMeta = quoteSummary(result, process);
  const quoteDate = new Date();
  const quoteNumber = buildQuoteNumber(result.upload.filename, quoteDate);
  let y = MARGIN;

  y = drawHeader(doc, y, quoteDate, quoteNumber);
  y = drawSectionTitle(doc, y + 5, "Prepared For");
  y = drawKeyValueGrid(doc, y, [
    ["Customer", "Not provided"],
    ["Company", "Not provided"],
    ["Email", "Not provided"],
    ["Quote validity", "Budgetary estimate; subject to review"],
  ]);

  y = drawSectionTitle(doc, y + 4, "Project / Part Summary");
  y = drawKeyValueGrid(doc, y, [
    ["Uploaded file", result.upload.filename],
    ["Manufacturing process", quoteMeta.processLabel],
    ["Quantity", String(quote.quantity)],
    ["Material", readRequestField(quote.request, "material")],
    ["Finish", readRequestField(quote.request, "finish")],
    ["Lead time", readRequestField(quote.request, "lead_time_class")],
    ["Notes", readRequestField(quote.request, "notes") || "Not provided"],
  ]);

  y = drawSectionTitle(doc, y + 4, "CAD Summary");
  y = drawCadSummary(doc, y, quote.source.source, quote.source.complexity?.score);

  y = drawSectionTitle(doc, y + 4, "Commercial Summary");
  y = drawKeyValueGrid(doc, y, [
    ["Currency", quote.currency],
    ["Total", money(quote.currency, quoteMeta.total)],
    ["Unit price", money(quote.currency, quote.unit_price)],
    ["Confidence", `${Math.round(quote.confidence * 100)}%`],
  ]);

  y = drawProcessDetails(doc, y + 2, result, process);
  y = drawLineItemSection(doc, y + 4, result, quote.currency, process);
  y = drawTerms(doc, y + 5, quote.assumptions);

  const filename = `rfq-quote-${safeFilename(result.upload.filename)}-${quoteDate.toISOString().slice(0, 10)}.pdf`;
  const blob = doc.output("blob");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return filename;
}

function drawHeader(doc: jsPDF, y: number, date: Date, quoteNumber: string) {
  doc.setFillColor(31, 111, 104);
  doc.rect(0, 0, PAGE_WIDTH, 22, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("RFQ Engine", MARGIN, 14);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text("Budgetary Manufacturing Quote", PAGE_WIDTH - MARGIN, 9, { align: "right" });
  doc.text(`Quote #: ${quoteNumber}`, PAGE_WIDTH - MARGIN, 14, { align: "right" });
  doc.text(`Date: ${formatDate(date)}`, PAGE_WIDTH - MARGIN, 19, { align: "right" });
  doc.setTextColor(31, 41, 46);
  return y + 18;
}

function drawSectionTitle(doc: jsPDF, y: number, title: string) {
  y = ensureSpace(doc, y, 12);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(31, 111, 104);
  doc.text(title.toUpperCase(), MARGIN, y);
  doc.setDrawColor(211, 218, 214);
  doc.line(MARGIN, y + 2, PAGE_WIDTH - MARGIN, y + 2);
  doc.setTextColor(31, 41, 46);
  return y + 7;
}

function drawKeyValueGrid(doc: jsPDF, y: number, rows: [string, string][]) {
  doc.setFontSize(9);
  rows.forEach(([label, value]) => {
    y = ensureSpace(doc, y, 7);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(95, 109, 114);
    doc.text(label, MARGIN, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(31, 41, 46);
    const wrapped = doc.splitTextToSize(value || "Not provided", CONTENT_WIDTH - 54);
    doc.text(wrapped, MARGIN + 54, y);
    y += Math.max(6, wrapped.length * 4.5);
  });
  return y;
}

function drawCadSummary(doc: jsPDF, y: number, cad: StepParseResult, complexityScore?: number) {
  const dimensions = cad.bounding_box.size.map((value) => `${value.toFixed(1)} mm`).join(" x ");
  return drawKeyValueGrid(doc, y, [
    ["Dimensions", dimensions],
    ["Units", `${cad.diagnostics.source_length_units.join(", ")} -> ${cad.diagnostics.canonical_unit}`],
    ["Volume", `${cad.mass_properties.volume.toFixed(1)} mm3`],
    ["Surface area", `${cad.mass_properties.surface_area.toFixed(1)} mm2`],
    ["Faces / edges", `${cad.topology.faces} / ${cad.topology.edges}`],
    ["Complexity", complexityScore === undefined ? "Not provided" : String(complexityScore)],
  ]);
}

function drawProcessDetails(doc: jsPDF, y: number, result: AnyQuoteResult, process: ManufacturingProcess) {
  if (process === "injection_molding") {
    const quote = (result as MoldingQuoteWorkflowResult).quote;
    y = drawSectionTitle(doc, y, "Injection Molding Details");
    return drawKeyValueGrid(doc, y, [
      ["Tooling", money(quote.currency, quote.tooling_cost)],
      ["Production", money(quote.currency, quote.production_subtotal)],
      ["Cavities", String(quote.request.cavities)],
      ["Amortized unit", money(quote.currency, quote.diagnostics.effective_amortized_unit_price)],
    ]);
  }
  if (process === "sheet_metal") {
    const quote = (result as SheetMetalQuoteWorkflowResult).quote;
    const signals = quote.diagnostics.geometry_signals;
    y = drawSectionTitle(doc, y, "Sheet Metal Details");
    return drawKeyValueGrid(doc, y, [
      ["Thickness", formatSignal(signals.estimated_thickness_mm, "mm")],
      ["Bend candidates", formatSignal(signals.bend_candidate_count)],
      ["Flat pattern area", formatSignal(signals.flat_pattern_area_cm2, "cm2")],
      ["Sheet confidence", formatSignal(signals.sheet_metal_confidence_score, "/ 100")],
    ]);
  }
  return y;
}

function drawLineItemSection(doc: jsPDF, y: number, result: AnyQuoteResult, currency: string, process: ManufacturingProcess) {
  y = drawSectionTitle(doc, y, "Itemized Pricing");
  const items = lineItemsFor(result, process);
  doc.setFontSize(8.5);
  doc.setFont("helvetica", "bold");
  doc.setFillColor(244, 248, 246);
  doc.rect(MARGIN, y - 4, CONTENT_WIDTH, 7, "F");
  doc.text("Description", MARGIN + 2, y);
  doc.text("Basis", MARGIN + 78, y);
  doc.text("Amount", PAGE_WIDTH - MARGIN - 2, y, { align: "right" });
  y += 6;
  doc.setFont("helvetica", "normal");

  items.forEach((item) => {
    const basis = item.basis || summarizeDetails(item.details);
    const descriptionLines = doc.splitTextToSize(item.label, 70);
    const basisLines = doc.splitTextToSize(basis, 78);
    const rowHeight = Math.max(descriptionLines.length, basisLines.length, 1) * 4.2 + 3;
    y = ensureSpace(doc, y, rowHeight + 3);
    doc.setDrawColor(237, 240, 238);
    doc.line(MARGIN, y - 3, PAGE_WIDTH - MARGIN, y - 3);
    doc.text(descriptionLines, MARGIN + 2, y);
    doc.text(basisLines, MARGIN + 78, y);
    doc.setFont("helvetica", "bold");
    doc.text(money(currency, item.amount), PAGE_WIDTH - MARGIN - 2, y, { align: "right" });
    doc.setFont("helvetica", "normal");
    y += rowHeight;
  });
  return y;
}

function drawTerms(doc: jsPDF, y: number, assumptions: string[]) {
  y = drawSectionTitle(doc, y, "Terms, Assumptions, And Disclaimer");
  const terms = [
    "This document is a budgetary quote and is not binding until reviewed and accepted by the supplier.",
    "Final pricing, lead time, and manufacturability are subject to DFM/manual engineering review, material availability, and shop capacity.",
    DISCLAIMER,
    ...assumptions.map(formatSnakeCase),
  ];
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  terms.forEach((term) => {
    const wrapped = doc.splitTextToSize(`- ${term}`, CONTENT_WIDTH);
    y = ensureSpace(doc, y, wrapped.length * 4.3 + 2);
    doc.text(wrapped, MARGIN, y);
    y += wrapped.length * 4.3 + 2;
  });
  return y;
}

function ensureSpace(doc: jsPDF, y: number, needed: number) {
  if (y + needed <= PAGE_HEIGHT - MARGIN) {
    return y;
  }
  doc.addPage();
  return MARGIN;
}

function lineItemsFor(result: AnyQuoteResult, process: ManufacturingProcess): PricingLineItem[] {
  if (process === "injection_molding") {
    const quote = (result as MoldingQuoteWorkflowResult).quote;
    return [...quote.tooling_line_items, ...quote.production_line_items];
  }
  return (result as QuoteWorkflowResult | SheetMetalQuoteWorkflowResult).quote.line_items;
}

function quoteSummary(result: AnyQuoteResult, process: ManufacturingProcess) {
  if (process === "injection_molding") {
    return {
      processLabel: "Injection molding",
      total: (result as MoldingQuoteWorkflowResult).quote.total_first_order_cost,
    };
  }
  return {
    processLabel: process === "sheet_metal" ? "Sheet metal" : "CNC",
    total: (result as QuoteWorkflowResult | SheetMetalQuoteWorkflowResult).quote.subtotal,
  };
}

function readRequestField(request: Record<string, unknown>, field: string) {
  const value = request[field];
  if (value === null || value === undefined || value === "") {
    return "";
  }
  return String(value).replace(/_/g, " ");
}

function summarizeDetails(details: Record<string, unknown>) {
  const entries = Object.entries(details).slice(0, 3);
  if (entries.length === 0) {
    return "Quote calculation";
  }
  return entries.map(([key, value]) => `${formatSnakeCase(key)}: ${String(value)}`).join("; ");
}

function money(currency: string, amount: number) {
  return `${currency} ${amount.toFixed(2)}`;
}

function formatSignal(value: unknown, suffix = "") {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Not provided";
  }
  const formatted = Math.abs(value) >= 100 ? value.toFixed(1) : value.toFixed(2);
  return suffix ? `${formatted} ${suffix}` : formatted;
}

function formatSnakeCase(value: string) {
  return value.replace(/_/g, " ");
}

function formatDate(date: Date) {
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
}

function buildQuoteNumber(filename: string, date: Date) {
  const datePart = date.toISOString().slice(0, 10).replace(/-/g, "");
  let hash = 0;
  for (const character of filename) {
    hash = (hash * 31 + character.charCodeAt(0)) % 100000;
  }
  return `RFQ-${datePart}-${String(hash).padStart(5, "0")}`;
}

function safeFilename(filename: string) {
  return filename.replace(/\.[^.]+$/, "").replace(/[^a-z0-9._-]+/gi, "-").replace(/^-+|-+$/g, "") || "quote";
}
