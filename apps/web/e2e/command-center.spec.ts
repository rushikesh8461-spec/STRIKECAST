import { expect, test } from "@playwright/test";

const predict = {
  timestamp: "2026-09-27T10:00:00Z", forecast_horizon_minutes: 60,
  latitude: 12.9716, longitude: 77.5946, grid_shape: null, prediction: 40,
  probability: 0.4, confidence: 0.7, model_name: "StrikeCast-ConvLSTM-Demo",
  model_version: "1.0.0-trained-demo", model_mode: "demo", model_status: "DEMO",
  data_status: "DEMO", data_source: "synthetic-fallback",
  atmospheric: { temperature_c: 28, humidity_pct: 65, pressure_hpa: 1008, wind_speed_ms: 3, cape_jkg: 200, cin_jkg: -20, precipitation_mm_h: 0 },
};
const risk = {
  forecast: "Demo risk only", confidence: 0.7, risk_level: "HIGH", alerts: ["Demo alert"],
  timestamp: predict.timestamp, latitude: predict.latitude, longitude: predict.longitude, model_version: predict.model_version,
};

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8000/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/health") return route.fulfill({ json: { status: "ok", model_mode: "demo" } });
    if (path === "/metadata") return route.fulfill({ json: {
      model_name: predict.model_name, model_version: predict.model_version,
      model_mode: "demo", model_status: "candidate_demo_only", evaluation_status: "not_available",
    } });
    if (path === "/predict" && request.method() === "POST") {
      if (await page.evaluate(() => sessionStorage.getItem("test-fail-prediction")) === "1") {
        return route.fulfill({ status: 500, json: { detail: { message: "Prediction is temporarily unavailable." } } });
      }
      return route.fulfill({ json: { ...predict, latitude: request.postDataJSON().latitude, longitude: request.postDataJSON().longitude } });
    }
    if (path === "/risk" && request.method() === "POST") return route.fulfill({ json: { ...risk, latitude: request.postDataJSON().latitude, longitude: request.postDataJSON().longitude } });
    if (path === "/lightning") return route.fulfill({ json: { mode: "none", source: "disabled", updated_at: predict.timestamp, strikes: [] } });
    return route.fulfill({ status: 404, json: { detail: "not found" } });
  });
  await page.route("https://nominatim.openstreetmap.org/search**", route => route.fulfill({
    json: [{ lat: "19.0760", lon: "72.8777", display_name: "Mumbai, India" }],
  }));
  await page.route("https://tile.openstreetmap.org/**", route => route.fulfill({
    status: 200, contentType: "image/png",
    body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg==", "base64"),
  }));
  await page.goto("/");
  await page.getByRole("button", { name: /enter demo command center/i }).click();
  await expect(page.getByText("ONLINE", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("HIGH", { exact: true }).first()).toBeVisible();
});

test("searches a location, updates selected point and risk field", async ({ page }) => {
  const search = page.getByPlaceholder("Search city, region, country");
  await search.fill("Mumbai");
  await page.locator(".search-row button").click();
  await page.getByRole("button", { name: /Mumbai, India/i }).click();
  await expect(page.getByTestId("risk-field-active")).toHaveAttribute("data-latitude", "19.076");
  await expect(page.getByTestId("risk-field-active")).toHaveAttribute("data-risk-level", "HIGH");
  await expect(page.getByText("DEMO", { exact: true }).first()).toBeVisible();
});

test("weather product without a configured provider is unavailable", async ({ page }) => {
  await page.getByRole("button", { name: /RADAR/ }).click();
  await expect(page.locator(".layer-badge")).toContainText("UNAVAILABLE");
});

test("renders the risk card and radial risk field from backend values", async ({ page }) => {
  await expect(page.getByText("40.0%")).toBeVisible();
  await expect(page.locator(".risk-stat-grid")).toContainText("DEMO SCORE (UNVALIDATED)");
  await expect(page.locator(".risk-stat-grid")).toContainText("DEMO CONFIDENCE (UNVALIDATED)");
  await expect(page.locator(".alert-main")).toContainText("Demo risk only");
  await expect(page.locator(".alert-meta")).toContainText("Demo alert");
  await expect(page.getByText("NOT_AVAILABLE", { exact: true })).toBeVisible();
});

test("labels unavailable lightning source without showing simulated events", async ({ page }) => {
  await page.getByRole("button", { name: /LIGHTNING/ }).click();
  await expect(page.locator(".lightning-feed-badge")).toContainText("LIGHTNING FEED OFFLINE");
  await expect(page.locator(".lightning-feed-badge")).toContainText("0");
});

test("shows a safe error and clears stale risk when the prediction API fails", async ({ page }) => {
  await page.evaluate(() => sessionStorage.setItem("test-fail-prediction", "1"));
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.locator(".map-error")).toContainText("Prediction is temporarily unavailable.");
  await expect(page.locator(".risk-title")).toHaveText("UNAVAILABLE");
  await expect(page.getByTestId("risk-field-active")).toHaveCount(0);
  await expect(page.locator(".top-metrics")).toContainText("OFFLINE");
});
