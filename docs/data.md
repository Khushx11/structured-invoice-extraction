# Data provenance

All bundled and generated examples are fictional. The generator uses seeded values and original sample layouts. No actual addresses, credentials, bank accounts, tax identifiers or payment information appear in the samples.

The default benchmark uses three development supplier templates, four held-out supplier templates and a separate stress cohort derived from the held-out templates. Each normal template yields four documents, mixing digital PDFs with raster PDFs. The stress cohort includes 90-degree rotation and low-resolution blur/contrast degradation. Some documents include a blank or continuation page. Demo templates are excluded from all benchmark splits. These are synthetic rasterisations, without the real acquisition noise or supplier diversity a production policy would need.

The benchmark also accepts a local permission-cleared manifest. Keep real files in a private data directory. Assign each original supplier template to a single development or test cohort, and keep stress variants of test documents in the stress cohort. Supply a JSON array where each object has unique id, relative path, template, split, kind, header and line_items fields. Use kind real for real scans. Header and row keys follow the extraction schema, with bare normalised values. Use null for annotated absence. Never mix synthetic and real instances in a single run.

Candidate sources reviewed include [Rossum DocILE](https://docile.rossum.ai/) and [Salesforce INV-CDIP](https://github.com/salesforce/inv-cdip). DocILE requires a research access request. INV-CDIP's annotations cover seven header fields and its underlying source documents have separate terms. Neither supplies results in this repository. A permission-cleared, English real-scan benchmark with complete line-item labels remains outstanding.

