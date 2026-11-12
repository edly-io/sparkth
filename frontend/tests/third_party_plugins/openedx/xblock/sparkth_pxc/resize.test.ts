import { afterEach, describe, expect, it } from "vitest";

import "@/../third_party_plugins/openedx/xblock/sparkth_pxc/resize.js";

function addFrame(markup: string): HTMLIFrameElement {
  document.body.insertAdjacentHTML("beforeend", markup);
  return document.body.lastElementChild as HTMLIFrameElement;
}

function addActivityFrame(): HTMLIFrameElement {
  return addFrame('<iframe data-sparkth-pxc style="height:24em"></iframe>');
}

function postFrom(frame: HTMLIFrameElement, data: unknown): void {
  window.dispatchEvent(new MessageEvent("message", { data, source: frame.contentWindow }));
}

describe("the XBlock's resize script", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("sizes an activity's iframe to the height its content reports", () => {
    const frame = addActivityFrame();

    postFrom(frame, { type: "pxc:resize", height: 613 });

    expect(frame.style.height).toBe("613px");
  });

  it("resizes only the iframe that reported, when a unit holds several activities", () => {
    const first = addActivityFrame();
    const second = addActivityFrame();

    postFrom(second, { type: "pxc:resize", height: 900 });

    expect(first.style.height).toBe("24em");
    expect(second.style.height).toBe("900px");
  });

  it("follows the content when it shrinks", () => {
    const frame = addActivityFrame();
    postFrom(frame, { type: "pxc:resize", height: 900 });

    postFrom(frame, { type: "pxc:resize", height: 300 });

    expect(frame.style.height).toBe("300px");
  });

  it("leaves an iframe that is not a Sparkth activity alone", () => {
    const other = addFrame('<iframe style="height:10em"></iframe>');

    postFrom(other, { type: "pxc:resize", height: 900 });

    expect(other.style.height).toBe("10em");
  });

  it.each([
    ["another kind of message", { type: "something-else", height: 900 }],
    ["a height that is not a number", { type: "pxc:resize", height: "tall" }],
    ["a height of zero", { type: "pxc:resize", height: 0 }],
    ["a message with no data", null],
  ])("ignores %s", (_label, data) => {
    const frame = addActivityFrame();

    postFrom(frame, data);

    expect(frame.style.height).toBe("24em");
  });
});
