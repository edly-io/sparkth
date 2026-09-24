import { test, expect } from "@playwright/test";

/**
 * The chat message box grows with what is typed, up to five lines, then scrolls.
 *
 * A real browser is required: jsdom performs no layout, so `scrollHeight` there is always 0 and
 * a unit test could only assert the CSS classes, which would pass with the growth deleted.
 */
const MAX_VISIBLE_LINES = 5;

test.describe("chat message box", () => {
  test("grows to five lines, then scrolls", async ({ page }) => {
    await page.goto("/dashboard/chat");

    const box = page.getByRole("textbox").first();
    await expect(box).toBeVisible();

    await box.fill("one line");
    const oneLine = await box.evaluate((el) => el.clientHeight);

    await box.fill(Array.from({ length: MAX_VISIBLE_LINES }, (_, i) => `line ${i + 1}`).join("\n"));
    const fiveLines = await box.evaluate((el) => el.clientHeight);
    expect(fiveLines).toBeGreaterThan(oneLine);

    await box.fill(Array.from({ length: 8 }, (_, i) => `line ${i + 1}`).join("\n"));
    const eightLines = await box.evaluate((el) => el.clientHeight);
    expect(eightLines).toBe(fiveLines);

    // Past the cap the content is still reachable, by scrolling rather than by growing.
    const overflows = await box.evaluate((el) => el.scrollHeight > el.clientHeight);
    expect(overflows).toBe(true);
  });

  test("returns to one line when the box is cleared", async ({ page }) => {
    await page.goto("/dashboard/chat");

    const box = page.getByRole("textbox").first();
    await expect(box).toBeVisible();

    const empty = await box.evaluate((el) => el.clientHeight);
    await box.fill("line 1\nline 2\nline 3");
    expect(await box.evaluate((el) => el.clientHeight)).toBeGreaterThan(empty);

    await box.fill("");
    expect(await box.evaluate((el) => el.clientHeight)).toBe(empty);
  });
});
