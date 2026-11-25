# Structured invoice record v1.0.0

The approved JSON contains the source filename and SHA-256, review status and revision, the original extractor result, the current corrected result, page records, reconciliation checks, and an append-only approval and correction history. The extractor identifier combines the method with its own revision. The OCR backend and operating-system revision are recorded when available.

Both extraction records share the same fields. Header keys are supplier_name, invoice_number, invoice_date, currency, subtotal, tax, discount and total. Line items contain description, quantity, unit_price and line_amount. Each field always has value, raw and evidence keys. JSON null expresses missing or unnormalisable data. Amounts and quantities are decimal strings and the date uses ISO 8601. Currency requires a recognised explicit code. Ambiguous numeric dates are left missing.

Evidence uses one-based page numbers. Boxes are [left, top, right, bottom], normalised to [0,1] against the displayed page after rotation correction. OCR confidence is an engine score rather than a calibrated probability. A correction changes the current value and records the reviewer entry. The original OCR text and source box still refer to the originally extracted source text. New values without verified evidence retain null evidence and remain flagged.

A passing invoice can be auto-approved by the demo policy. A human can approve with unresolved flags by recording a note. The export retains those flags and the note. CSV exports line items only and prefixes formula-like descriptions with an apostrophe for spreadsheet safety.

