import { randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";

const accounts = [
  ["citizen_tariq", "/citizen"], ["citizen_layla", "/citizen"],
  ["lawyer_omar", "/lawyer"], ["lawyer_sara", "/lawyer"],
  ["clerk_noor", "/court"], ["judge_adel", "/court"],
  ["land_officer_rami", "/entity"], ["civil_officer_dana", "/entity"],
  ["gov_tax_fadi", "/entity"], ["gov_gam_hana", "/entity"],
];
const destinations = [
  { entity: "2", type: "LAND_OWNERSHIP_EXTRACT", officer: "land_officer_rami" },
  { entity: "3", type: "CIVIL_RECORD_CHECK", officer: "civil_officer_dana" },
  { entity: "4", type: "GENERAL_OFFICIAL_LETTER", officer: "gov_tax_fadi" },
];

function action(page, name) {
  return page.locator("form").filter({ has: page.locator(`input[name="action"][value="${name}"]`) });
}

async function menu(page) {
  const button = page.getByRole("button", { name: "القائمة", exact: true });
  if (await button.isVisible() && await button.getAttribute("aria-expanded") === "false") {
    await button.click();
    await expect(button).toHaveAttribute("aria-expanded", "true");
  }
}

async function logout(page) {
  await menu(page);
  await page.getByRole("button", { name: "خروج", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
}

async function login(page, username) {
  await page.goto("/login?demo=1");
  const form = page.locator('form[action="/demo-login"]').filter({
    has: page.locator(`input[name="username"][value="${username}"]`),
  });
  await expect(form.locator(".rid")).toContainText("TEST-NID-");
  await form.getByRole("button").click();
  await expect(page).toHaveURL(accounts.find(([name]) => name === username)[1]);
  await expect(page.locator(".who")).toContainText("حساب تجريبي");
}

async function navigate(page, path, label) {
  await menu(page);
  await page.locator("#topnav").getByRole("link", { name: label, exact: true }).click();
  await expect(page).toHaveURL(path);
}

async function perform(page, name) {
  await action(page, name).locator("button").click();
  await expect(page.getByRole("alert")).toContainText("تم تنفيذ الإجراء");
}

async function status(page, value) {
  await expect(page.locator("h1 + .pill")).toHaveText(value);
}

async function capture(page, info, label) {
  await page.screenshot({ path: info.outputPath(`${label}.png`), fullPage: true, animations: "disabled" });
}

test.beforeEach(async ({ page }) => {
  const health = await page.request.get("/health");
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).data_mode).toBe("demo");
  // Confirm native confirmations, rather than removing their event handlers.
  page.on("dialog", dialog => dialog.accept());
});

test("public login, all ten TEST accounts, seven roles, navigation and logout", async ({ page }, info) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/lawyer");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.locator('form[action="/demo-login"]')).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("TEST-NID-");

  for (const [username, home] of accounts) {
    await test.step(username, async () => {
      await login(page, username);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      await expect(page.locator("main h1")).toBeVisible();
      if (info.project.name === "phone") {
        const button = page.getByRole("button", { name: "القائمة", exact: true });
        await expect(page.locator("#topnav")).toBeHidden();
        await button.click();
        await expect(page.locator("#topnav")).toBeVisible();
        await expect(button).toHaveAttribute("aria-expanded", "true");
        await page.keyboard.press("Escape");
        await expect(button).toHaveAttribute("aria-expanded", "false");
        await expect(button).toBeFocused();
      }
      await navigate(page, "/notifications", "الإشعارات");
      await expect(page.getByRole("heading", { name: "الإشعارات", exact: true })).toBeVisible();
      await navigate(page, home, "لوحتي");
      // Wide data tables may scroll internally; the page itself must fit a phone.
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
      await capture(page, info, username);
      await logout(page);
      await page.goto(home);
      await expect(page).toHaveURL(/\/login$/);
    });
  }
  // Exercise normal credentials too; these are public TEST fixture credentials.
  await page.getByLabel("الرقم الوطني").fill("TEST-NID-9901001001");
  await page.getByLabel("كلمة السر").fill("Demo@1001");
  await page.getByRole("button", { name: "دخول", exact: true }).click();
  await expect(page).toHaveURL("/citizen");
  expect(errors).toEqual([]);
});

test("request types follow every target entity without stale options", async ({ page }, info) => {
  await login(page, "lawyer_omar");
  await navigate(page, "/requests/new", "طلب كتاب جديد");
  await expect(page.getByLabel("القضية")).toHaveValue("1");
  await expect(page.getByLabel("القضية").locator("option")).toHaveCount(1);
  const expected = [
    ["2", "LAND_OWNERSHIP_EXTRACT"], ["3", "CIVIL_RECORD_CHECK"],
    ["4", "GENERAL_OFFICIAL_LETTER"], ["5", "GENERAL_OFFICIAL_LETTER"],
    ["6", "GENERAL_OFFICIAL_LETTER"], ["7", "GENERAL_OFFICIAL_LETTER"],
    ["8", "ZONING_STATUS_LETTER"], ["2", "LAND_OWNERSHIP_EXTRACT"],
  ];
  for (const [entity, type] of expected) {
    await page.getByLabel("الجهة المستهدفة").selectOption(entity);
    await expect(page.getByLabel("نوع الطلب")).toHaveValue(type);
    await expect(page.getByLabel("نوع الطلب").locator("option")).toHaveCount(1);
  }
  await capture(page, info, "request-types");
});

for (const target of destinations) {
  test(`lawyer → clerk → judge → ${target.officer} → court release → citizen print`, async ({ page }, info) => {
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const unique = randomUUID().slice(0, 8);
    const title = `TEST طلب تحقق متصفح ${unique}`;
    const reason = `TEST سبب قضائي داخلي ${unique}`;
    const note = `TEST ملاحظة سرية ${unique}`;
    const pdf = await page.request.get("/__TEST_fixture.pdf");
    expect(pdf.ok()).toBeTruthy();
    const bytes = await pdf.body();
    expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
    const upload = { name: `TEST-${unique}.pdf`, mimeType: "application/pdf", buffer: bytes };

    await login(page, "lawyer_omar");
    await navigate(page, "/requests/new", "طلب كتاب جديد");
    await page.getByLabel("الجهة المستهدفة").selectOption(target.entity);
    await expect(page.getByLabel("نوع الطلب")).toHaveValue(target.type);
    await page.getByLabel("عنوان الطلب").fill(title);
    await page.getByRole("button", { name: "حفظ كمسودة", exact: true }).click();
    await expect(page).toHaveURL(/\/requests\/\d+$/);
    const path = new URL(page.url()).pathname;
    await status(page, "مسودة");
    // Submission cannot succeed without an attachment.
    await action(page, "submit").getByRole("button").click();
    await expect(page.locator(".alert-danger")).toBeVisible();
    await status(page, "مسودة");
    await page.getByLabel("ملف PDF", { exact: true }).setInputFiles(upload);
    await page.getByRole("button", { name: "رفع / استبدال الملف" }).click();
    await expect(page.getByRole("alert")).toContainText("تم رفع الملف");
    await expect(page.locator('.doc a[href$="/view"]')).toHaveCount(1);
    const lawyerDocument = await page.locator('.doc a[href$="/view"]').getAttribute("href");
    await perform(page, "submit");
    await status(page, "مقدَّم");
    await expect(page.locator('form[action$="/pdf"]')).toHaveCount(0);
    await capture(page, info, `${target.entity}-lawyer-submitted`);
    await logout(page);

    await login(page, "clerk_noor");
    await page.locator(`a[href="${path}"]`).first().click();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await perform(page, "start_review");
    await status(page, "قيد مراجعة المحكمة");
    await expect(action(page, "approve")).toHaveCount(0);
    await expect(action(page, "reject")).toHaveCount(0);
    await page.getByLabel("ملاحظة داخلية (للمحكمة فقط)").fill(note);
    await perform(page, "note");
    await capture(page, info, `${target.entity}-clerk-reviewed`);
    await logout(page);

    await login(page, "judge_adel");
    await page.locator(`a[href="${path}"]`).first().click();
    const approval = action(page, "approve");
    // HTML validation blocks empty reasons, and the server rejects whitespace.
    await approval.getByRole("button").click();
    expect(await approval.getByLabel("السبب", { exact: true }).evaluate(input => input.validity.valueMissing)).toBe(true);
    await status(page, "قيد مراجعة المحكمة");
    await approval.getByLabel("السبب", { exact: true }).fill("   ");
    await approval.getByRole("button").click();
    await expect(page.getByRole("alert")).toContainText("السبب مطلوب");
    await status(page, "قيد مراجعة المحكمة");
    await action(page, "approve").getByLabel("السبب", { exact: true }).fill(reason);
    await perform(page, "approve");
    await status(page, "معتمد");
    await capture(page, info, `${target.entity}-judge-approved`);
    await logout(page);

    await login(page, target.officer);
    expect((await page.goto(path)).status()).toBe(404);
    await logout(page);
    await login(page, "clerk_noor");
    await page.goto(path);
    await perform(page, "send");
    await status(page, "أُرسل للجهة");
    await logout(page);

    await login(page, target.officer);
    await page.locator(`a[href="${path}"]`).first().click();
    await perform(page, "start_processing");
    await status(page, "قيد المعالجة");
    await action(page, "upload_response").getByLabel("ملف PDF", { exact: true }).setInputFiles(upload);
    await perform(page, "upload_response");
    await status(page, "تم استلام الرد");
    await expect(page.locator("main")).not.toContainText(note);
    // The existing policy hides an unreleased response even from its uploader.
    await expect(page.locator('.doc a[href$="/view"]')).toHaveCount(0);
    await capture(page, info, `${target.entity}-entity-response`);
    await logout(page);
    await login(page, "lawyer_omar");
    await page.goto(path);
    const responseCard = page.locator(".doc").filter({ hasText: "رد الجهة الحكومية" });
    await expect(responseCard).toHaveCount(1);
    const responseDocument = await responseCard.locator('a[href$="/view"]').getAttribute("href");
    expect(responseDocument).not.toBe(lawyerDocument);
    const printPath = responseDocument.replace(/\/view$/, "/print");
    expect((await page.request.get(responseDocument)).status()).toBe(200);
    await logout(page);

    await login(page, "citizen_tariq");
    await page.goto(path);
    await expect(page.locator(`a[href="${responseDocument}"]`)).toHaveCount(0);
    await expect(page.locator(`a[href="${printPath}"]`)).toHaveCount(0);
    expect((await page.request.get(responseDocument)).status()).toBe(403);
    expect((await page.request.get(printPath)).status()).toBe(403);
    expect((await page.request.get(lawyerDocument)).status()).toBe(403);
    await expect(page.locator("main")).not.toContainText(note);
    await expect(page.locator("main")).not.toContainText(reason);
    await logout(page);

    await login(page, "clerk_noor");
    await page.goto(path);
    await perform(page, "release_response");
    await expect(page.locator(".doc").filter({ hasText: "رد الجهة الحكومية" }))
      .toContainText("المواطن والمحامي الموكل");
    await expect(action(page, "release_response")).toHaveCount(0);
    await page.reload();
    await expect(action(page, "release_response")).toHaveCount(0);
    await logout(page);

    await login(page, "citizen_tariq");
    await page.goto(path);
    await expect(page.locator("main")).not.toContainText(note);
    await expect(page.locator("main")).not.toContainText(reason);
    const popupPromise = page.waitForEvent("popup");
    await page.getByRole("link", { name: "طباعة", exact: true }).click();
    const popup = await popupPromise;
    await popup.waitForLoadState("domcontentloaded");
    await expect(popup).toHaveURL(printPath);
    const iframe = popup.locator("iframe.pdf");
    await expect(iframe).toBeVisible();
    const raw = await iframe.getAttribute("src");
    expect(raw).toBe(responseDocument.replace(/\/view$/, "/raw?for=print"));
    const printed = await page.request.get(raw);
    expect(printed.status()).toBe(200);
    expect(printed.headers()["content-type"]).toContain("application/pdf");
    expect(Buffer.compare(await printed.body(), bytes)).toBe(0);
    await capture(popup, info, `${target.entity}-citizen-print`);
    await popup.close();
    await logout(page);
    // Another citizen cannot open the request or any form of its released PDF.
    await login(page, "citizen_layla");
    expect((await page.goto(path)).status()).toBe(404);
    for (const forbidden of [responseDocument, printPath, raw]) {
      expect((await page.request.get(forbidden)).status()).toBe(404);
    }
    expect(errors).toEqual([]);
  });
}
