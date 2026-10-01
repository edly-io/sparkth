import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/../sparkth/plugins/pxc/static/sparkth-pxc.js";

const CONFIG = {
  activity: "mcq",
  context: { activity_id: "placement-1", course_id: "course-v1:X+Y+Z", user_id: "learner-7" },
  permission: "play",
  state: { question: "2 + 2?" },
  ui_url: "https://sparkth.test/api/v1/pxc/assets/ui.js?token=tok",
  asset_base_url: "https://sparkth.test/api/v1/pxc/assets",
  action_base_url: "https://sparkth.test/api/v1/pxc/actions",
  ws_url: "wss://sparkth.test/api/v1/pxc/ws?token=tok",
};

// Large enough that SparkthPXC routes it through HTTP rather than the socket.
const OVERSIZED = "x".repeat(600 * 1024);

class FakeSocket extends EventTarget {
  static OPEN = 1;
  static instances: FakeSocket[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(public url: string) {
    super();
    FakeSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {}

  open(): void {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
    this.dispatchEvent(new Event("open"));
  }
}

interface ActivityElement extends HTMLElement {
  permission: string;
  state: Record<string, unknown>;
  sendAction(name: string, value: unknown): Promise<void>;
}

function mountActivity(): ActivityElement {
  // "<" is escaped the way the embed route escapes it, so a "</script>" in state cannot end the block.
  const json = JSON.stringify(CONFIG).replaceAll("<", "\\u003c");
  document.body.innerHTML = `<pxc-activity data-pxc-token="tok"><script type="application/json">${json}</script></pxc-activity>`;
  return document.querySelector("pxc-activity") as ActivityElement;
}

function sentActions(socket: FakeSocket): string[] {
  return socket.sent.map((frame) => JSON.parse(frame).action);
}

describe("SparkthPXC", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeSocket);
    vi.stubGlobal("fetch", vi.fn());
    // The activity's ui.js URL is not loadable here; its failure is logged and ignored.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("reads its configuration from the page without a request", () => {
    const activity = mountActivity();

    expect(activity.permission).toBe("play");
    expect(activity.state).toEqual(CONFIG.state);
    expect(FakeSocket.instances[0].url).toBe(CONFIG.ws_url);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends an action over an open socket", async () => {
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.open();

    await activity.sendAction("answer.submit", [0]);

    await vi.waitFor(() => expect(sentActions(socket)).toEqual(["answer.submit"]));
  });

  it("holds actions sent while disconnected and delivers them in order on connect", async () => {
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];

    await activity.sendAction("answer.submit", [0]);
    await activity.sendAction("answer.submit", [1]);
    expect(socket.sent).toEqual([]);
    socket.open();

    await vi.waitFor(() =>
      expect(socket.sent.map((frame) => JSON.parse(frame).value)).toEqual([[0], [1]]),
    );
  });

  it("posts a payload too large for the socket to the action route with the token", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    const activity = mountActivity();
    FakeSocket.instances[0].open();

    await activity.sendAction("config.save", OVERSIZED);

    await vi.waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        `${CONFIG.action_base_url}/config.save?token=tok`,
        expect.anything(),
      ),
    );
  });

  it("keeps a failed post queued and stops later actions overtaking it", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 502 }));
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.open();

    await activity.sendAction("config.save", OVERSIZED);
    await activity.sendAction("answer.submit", [0]);
    // Every microtask of the failed drain has run once a macrotask comes round.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetch).toHaveBeenCalled();
    expect(socket.sent).toEqual([]);

    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    socket.open();

    await vi.waitFor(() => expect(sentActions(socket)).toEqual(["answer.submit"]));
  });
});
