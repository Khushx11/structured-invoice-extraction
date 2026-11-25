"use strict";
const fs = require("node:fs");
const { spawn } = require("node:child_process");
const { once } = require("node:events");
const path = require("node:path");
const { chromium } = require("playwright");
const assert = require("node:assert/strict");

const baseline = process.env.INVOICE_URL || "http://127.0.0.1:8000";
const examples = process.env.INVOICE_DEMO_DIR || "var/demo";
const video = process.env.INVOICE_DEMO_VIDEO;
const encoderPath = video && process.env.INVOICE_FFMPEG;
const answers = JSON.parse(fs.readFileSync(path.join(examples, "answers.json"), "utf8"));
const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function run() {
  const browser = await chromium.launch({ executablePath: process.env.INVOICE_CHROMIUM_PATH || undefined });
  let context;
  let recording, encoder, encoderDone, captureTask;
  let captureRunning = false;
  let complete = false;
  try {
    context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      recordVideo: video && !encoderPath ? { dir: path.dirname(video), size: { width: 1280, height: 800 } } : undefined,
    });
    const page = await context.newPage();
    recording = page.video();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(baseline);
    if (encoderPath) {
      encoder = spawn(encoderPath, ["-y", "-loglevel", "error", "-f", "image2pipe",
        "-framerate", "5", "-vcodec", "mjpeg", "-i", "pipe:0", "-c:v", "libvpx-vp9", video],
        { stdio: ["pipe", "ignore", "inherit"] });
      encoderDone = once(encoder, "close");
      captureRunning = true;
      captureTask = (async () => {
        const started = performance.now();
        let count = 0;
        while (captureRunning) {
          const frame = await page.screenshot({ type: "jpeg", quality: 72 });
          const due = 1 + Math.floor((performance.now() - started) / 200);
          for (; count < due; count++) {
            if (!encoder.stdin.write(frame)) await once(encoder.stdin, "drain");
          }
          await wait(170);
        }
      })();
    }
    async function caption(value, milliseconds = 0) {
      if (!video) return;
      await page.evaluate(text => {
        let caption = document.getElementById("demo-caption");
        if (!caption) {
          caption = document.createElement("aside");
          caption.id = "demo-caption";
          Object.assign(caption.style, {position: "fixed", zIndex: 50, bottom: "16px",
            left: "26px", right: "26px", padding: "14px 18px", background: "#172a40",
            color: "white", borderRadius: "9px", font: "600 19px system-ui", pointerEvents: "none"});
          document.body.append(caption);
        }
        caption.textContent = text;
      }, value);
      await wait(milliseconds);
    }
    async function upload(name, expected) {
      await page.locator("#file").setInputFiles(path.join(examples, name));
      const response = page.waitForResponse(value => value.url().includes("/api/invoices?") && value.request().method() === "POST");
      await page.getByRole("button", {name: "Extract invoice"}).click();
      const result = await response;
      assert.equal(result.status(), 201);
      await page.getByText(expected, {exact: true}).waitFor();
      const src = await page.locator("#image").getAttribute("src");
      const id = src.split("/")[3];
      const body = await (await page.request.get(baseline + "/api/invoices/" + id)).json();
      return {id, ...body};
    }

    await caption("Structured Invoice Extraction and Review · two fictional scan uploads", 6500);
    const clean = await upload("clean-scan.png", "Auto-approved");
    assert.equal(clean.policy.auto_approval_enabled, true);
    await caption("Clean scan: required values have traceable evidence and all arithmetic checks pass.", 10500);
    await caption("Next, upload a scan with an inconsistent line amount.", 5000);
    const ambiguous = await upload("ambiguous-scan.png", "Needs review");
    assert.equal(ambiguous.status, "review");
    assert.ok(ambiguous.checks.some(check => check.path === "line_items.0.line_amount" && check.status === "fail"));
    await caption("The review queue surfaces the line extension and subtotal discrepancies.", 8500);
    await page.getByRole("button", {name: "Locate Line 1 · Line amount"}).click();
    assert.equal(await page.locator("#region").isVisible(), true);
    await caption("Click Locate to see the original line amount highlighted beside the editable field.", 9500);
    const target = page.locator('[data-path="line_items.0.line_amount"] input');
    const expected = answers[1].line_items[0].line_amount;
    const update = page.waitForResponse(value => value.url().endsWith("/" + ambiguous.id) && value.request().method() === "POST");
    await target.fill(expected);
    await target.press("Tab");
    assert.equal((await update).status(), 200);
    await page.getByText("Correction saved.", {exact: true}).waitFor();
    const corrected = await (await page.request.get(baseline + "/api/invoices/" + ambiguous.id)).json();
    assert.equal(corrected.current.line_items[0].line_amount.value, expected);
    assert.equal(corrected.original.line_items[0].line_amount.value, ambiguous.current.line_items[0].line_amount.value);
    assert.equal(corrected.checks.filter(check => check.status === "fail").length, 0);
    await caption("Correct the amount from quantity × unit price. The original extraction remains in the audit trail.", 10500);
    await page.getByText("Audit trail", {exact: true}).click();
    assert.match(await page.locator("#history").innerText(), /corrected/);
    await caption("The audit trail records the before and after amounts.", 7500);
    await page.getByRole("button", {name: "Approve invoice"}).click();
    await page.getByText("Approved", {exact: true}).waitFor();
    const json = page.waitForEvent("download");
    await page.getByRole("link", {name: "Export JSON"}).click();
    const downloaded = await json;
    const approval = JSON.parse(fs.readFileSync(await downloaded.path(), "utf8"));
    assert.ok(approval.history.some(event => event.event === "approved"));
    const csv = page.waitForEvent("download");
    await page.getByRole("link", {name: "Export CSV"}).click();
    assert.match(fs.readFileSync(await (await csv).path(), "utf8"), /line,description,quantity,unit_price,line_amount/);
    await caption("Approved. Export the structured JSON record or the line-items CSV.", 10500);
    assert.deepEqual(errors, []);
    complete = true;
    console.log("Browser flow passed: auto-approval, OCR evidence highlight, correction, audit and both exports.");
  } finally {
    if (captureTask) {
      captureRunning = false;
      await captureTask;
      encoder.stdin.end();
      const [code] = await encoderDone;
      assert.equal(code, 0, "The video encoder exited with an error");
      if (!complete) fs.rmSync(video, { force: true });
    }
    if (context) await context.close();
    if (video && recording && complete) await recording.saveAs(video);
    await browser.close();
  }
}

run().catch(error => { console.error(error); process.exitCode = 1; });




