SpeakerDesigner Online 2.5.2 - Online migration prototype
=======================================================

This package keeps the original SpeakerDesigner 2.5.2 interface and features.
The local bridge is replaced by a deployable web backend using the PORT environment
variable and listening on 0.0.0.0. No localhost bridge/start.sh is required.

Included:
- Original index.html interface and calculations (retained)
- Online search endpoint: /api/search?q=...
- PDF/HTML text extraction endpoint: /api/pdf?url=...
- Health endpoint: /api/health
- render.yaml deployment recipe (Render)
- requirements.txt (PyMuPDF for PDF text extraction)

Deployment (Render example):
1. Create a new Web Service from a repository containing this folder.
2. Use the included render.yaml blueprint or set:
   Build: pip install -r requirements.txt
   Start: python server.py
3. Once deployed, open the generated HTTPS URL. The app and /api endpoints are
   served from the same origin; the UI calls /api/search and /api/pdf.

Important:
- This is a migration prototype, not a production-reviewed internet service.
- PDF text extraction requires PyMuPDF. Scanned/image-only PDFs still need OCR.
- Online driver search depends on DuckDuckGo HTML results and may be rate-limited,
  blocked, or change format; verify every imported parameter against the datasheet.
- The API currently has no user accounts, quotas, or persistent server-side project
  storage. Existing browser-local project/library storage remains client-side.
- The PDF-fetch endpoint only permits public HTTP(S) hosts and blocks resolved
  non-public addresses; redirects are revalidated. Security review and rate limiting
  are still recommended before public production use.
