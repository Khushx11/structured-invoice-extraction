# Local deployment

Install Python 3.10 or newer, Poppler and Tesseract with English language data. On macOS, Homebrew provides the external tools with `brew install poppler tesseract`. On Debian or Ubuntu use `sudo apt-get install poppler-utils tesseract-ocr tesseract-ocr-eng`. Create a virtual environment and install the Python requirements.

Start `python -m invoice_review.server --data var`. The service binds to 127.0.0.1 and stores source files, rendered pages and a SQLite database in the selected directory. No extraction API calls out to a remote model. Back up or remove that directory using your own local data retention process. Keep it outside source control.

The server is a single-user local service. Use a dedicated OS account or isolated container for processing untrusted documents, restrict filesystem access and enforce upload, page, CPU and retention limits. Shared deployments need authentication, reviewer identities, access control, encryption, job isolation, monitoring and a durable audit store. Do not expose this local service directly to the network.

For the measured macOS Vision environment, build the adapter with `swiftc native/vision_ocr.swift -o build/vision_ocr` after creating build. Start the server or benchmark with `INVOICE_VISION_OCR="$PWD/build/vision_ocr"`. Apple Vision may need a normal local process outside restricted headless runtimes.

