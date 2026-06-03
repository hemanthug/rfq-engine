export type BoundingBox = {
  minimum: number[];
  maximum: number[];
  size: number[];
};

export type PreviewMeshResult = {
  schema_version: string;
  units: string;
  positions: number[];
  normals: number[];
  indices: number[];
  edges: number[];
  bbox: BoundingBox;
  triangle_count: number;
  vertex_count: number;
  mesh_quality: {
    linear_deflection_mm: number;
    angular_deflection_rad: number;
    is_relative: boolean;
    is_parallel: boolean;
    warnings: string[];
  };
};

export type PricingLineItem = {
  code: string;
  label: string;
  amount: number;
  basis: string;
  details: Record<string, unknown>;
};

export type ManufacturingProcess = "cnc" | "injection_molding" | "3d_printing" | "sheet_metal";

export type RankedProcessRecommendation = {
  process: ManufacturingProcess;
  label: string;
  score: number;
  confidence: string;
  reasons: string[];
  warnings: string[];
};

export type ProcessFitResult = {
  recommended_process: ManufacturingProcess;
  ranked_processes: RankedProcessRecommendation[];
  confidence: string;
  reasons: string[];
  warnings: string[];
  signals: Record<string, number>;
};

export type StepParseResult = {
  file: {
    source_name: string;
    size_bytes: number;
  };
  diagnostics: {
    canonical_unit: string;
    source_length_units: string[];
  };
  bounding_box: BoundingBox;
  mass_properties: {
    volume: number;
    surface_area: number;
  };
  topology: {
    faces: number;
    edges: number;
    solids: number;
  };
};

export type CadPreviewWorkflowResult = {
  preview: PreviewMeshResult;
  source: StepParseResult;
  process_fit: ProcessFitResult | null;
  upload: {
    filename: string;
    size_bytes: number;
    extension: string;
  };
  workflow: {
    schema_version: string;
    warnings: string[];
    elapsed_ms: number;
  };
};

export type CncQuoteWorkflowResult = {
  quote: {
    schema_version: string;
    process: string;
    currency: string;
    source: {
      source: StepParseResult;
      holes: unknown[];
      pockets: unknown[];
      complexity: {
        score: number;
      };
    };
    request: {
      material: string;
      quantity: number;
      tolerance_class: string;
      finish: string;
      lead_time_class: string;
      notes: string | null;
    };
    line_items: PricingLineItem[];
    subtotal: number;
    unit_price: number;
    quantity: number;
    confidence: number;
    warnings: string[];
    assumptions: string[];
  };
  preview: PreviewMeshResult;
  upload: {
    filename: string;
    size_bytes: number;
    extension: string;
  };
  workflow: {
    schema_version: string;
    warnings: string[];
    elapsed_ms: number;
  };
};

export type MoldingQuoteWorkflowResult = {
  quote: {
    schema_version: string;
    process: string;
    currency: string;
    source: {
      source: StepParseResult;
      holes: unknown[];
      pockets: unknown[];
      complexity: {
        score: number;
      };
    };
    request: {
      material: string;
      quantity: number;
      annual_volume: number;
      cavities: number;
      mold_class: string;
      finish: string;
      lead_time_class: string;
      notes: string | null;
    };
    tooling_line_items: PricingLineItem[];
    production_line_items: PricingLineItem[];
    tooling_cost: number;
    production_subtotal: number;
    unit_price: number;
    total_first_order_cost: number;
    quantity: number;
    confidence: number;
    warnings: string[];
    assumptions: string[];
    diagnostics: {
      pricing_version: string;
      rate_card_version: string;
      rate_card_kind: string;
      geometry_signals: Record<string, number>;
      effective_amortized_unit_price: number;
      cavity_recommendation: {
        recommended_cavities: number;
        user_overrode_cavities: boolean;
        candidate_cavity_results: {
          cavities: number;
          feasible: boolean;
          effective_amortized_unit_price: number | null;
          tooling_cost: number | null;
          production_subtotal: number | null;
          estimated_cycle_seconds: number | null;
          rejection_reasons: string[];
        }[];
        cavity_recommendation_reason: string;
        cavity_recommendation_confidence: string;
        details: Record<string, unknown>;
      };
      missing_or_inferred_values: string[];
    };
  };
  preview: PreviewMeshResult;
  upload: {
    filename: string;
    size_bytes: number;
    extension: string;
  };
  workflow: {
    schema_version: string;
    warnings: string[];
    elapsed_ms: number;
  };
};

export type SheetMetalQuoteWorkflowResult = {
  quote: {
    schema_version: string;
    process: string;
    currency: string;
    source: {
      source: StepParseResult;
      holes: unknown[];
      pockets: unknown[];
      complexity: {
        score: number;
      };
    };
    request: {
      material: string;
      quantity: number;
      finish: string;
      lead_time_class: string;
      notes: string | null;
    };
    line_items: PricingLineItem[];
    subtotal: number;
    unit_price: number;
    quantity: number;
    confidence: number;
    warnings: string[];
    assumptions: string[];
    diagnostics: {
      pricing_version: string;
      rate_card_version: string;
      rate_card_kind: string;
      geometry_signals: Record<string, number>;
      missing_or_inferred_values: string[];
    };
  };
  preview: PreviewMeshResult;
  upload: {
    filename: string;
    size_bytes: number;
    extension: string;
  };
  workflow: {
    schema_version: string;
    warnings: string[];
    elapsed_ms: number;
  };
};

export type QuoteWorkflowResult = CncQuoteWorkflowResult;

export type QuoteFormValues = {
  material: string;
  quantity: number;
  tolerance_class: string;
  finish: string;
  lead_time_class: string;
  notes: string;
};

export type MoldingFormValues = {
  material: string;
  quantity: number;
  annual_volume: number;
  cavities: "auto" | "1" | "2" | "4" | "8";
  mold_class: string;
  finish: string;
  lead_time_class: string;
  notes: string;
};

export type SheetMetalFormValues = {
  material: string;
  quantity: number;
  finish: string;
  lead_time_class: string;
  notes: string;
};

export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};
