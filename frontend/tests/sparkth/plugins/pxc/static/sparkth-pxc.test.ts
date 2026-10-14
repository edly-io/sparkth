import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/../sparkth/plugins/pxc/static/sparkth-pxc.js";

const CONFIG = {
  activity: "mcq",
  context: { activity_id: "instance-1", course_id: "course-1", user_id: "learner-7" },
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
  onclose: ((event: CloseEvent) => void) | null = null;
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

  closeFromServer(code: number): void {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close", { code }));
  }
}

function notice(): string | null | undefined {
  return document.querySelector('[role="alert"]')?.textContent;
}

interface ActivityElement extends HTMLElement {
  permission: string;
  state: Record<string, unknown>;
  sendAction(name: string, value: unknown): Promise<void>;
  onEvent: (name: string, value: unknown) => void;
}

const ACTION_NOTICE =
  "Your last action did not go through. Try again, and tell your instructor if it keeps happening.";

function serverFrame(socket: FakeSocket, frame: object): void {
  socket.onmessage?.(new MessageEvent("message", { data: JSON.stringify(frame) }));
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
    vi.useRealTimers();
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

  it.each(["action_failed", "action_rejected"])(
    "tells the learner when the server answers an action with %s, and keeps the frame from the activity",
    (error) => {
      const activity = mountActivity();
      activity.onEvent = vi.fn();
      const socket = FakeSocket.instances[0];
      socket.open();

      serverFrame(socket, { error, action: "answer.submit" });

      expect(notice()).toBe(ACTION_NOTICE);
      expect(activity.onEvent).not.toHaveBeenCalled();
    },
  );

  it("takes the action notice down when the learner acts again", async () => {
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.open();
    serverFrame(socket, { error: "action_failed", action: "answer.submit" });
    expect(notice()).toBe(ACTION_NOTICE);

    await activity.sendAction("answer.submit", [1]);

    await vi.waitFor(() => expect(sentActions(socket)).toEqual(["answer.submit"]));
    expect(notice()).toBeUndefined();
  });

  it("keeps a refusal notice up when the learner acts", async () => {
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.closeFromServer(4401);

    await activity.sendAction("answer.submit", [1]);

    expect(notice()).toBe("Your session has expired. Reload this page to continue.");
  });

  it("hands an ordinary event to the activity", () => {
    const activity = mountActivity();
    activity.onEvent = vi.fn();
    const socket = FakeSocket.instances[0];
    socket.open();

    serverFrame(socket, { name: "answer.result", value: JSON.stringify({ correct: true }) });

    expect(activity.onEvent).toHaveBeenCalledWith("answer.result", { correct: true });
    expect(notice()).toBeUndefined();
  });

  it("tells the learner a post refused with 422 failed, and lets later actions go", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 422 }));
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.open();

    await activity.sendAction("config.save", OVERSIZED);
    await vi.waitFor(() => expect(notice()).toBe(ACTION_NOTICE));
    await activity.sendAction("answer.submit", [0]);

    await vi.waitFor(() => expect(sentActions(socket)).toEqual(["answer.submit"]));
  });

  it("keeps a refusal notice up when a post fails after it", async () => {
    let answer: (response: Response) => void = () => {};
    vi.mocked(fetch).mockReturnValue(new Promise((resolve) => (answer = resolve)));
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.open();
    await activity.sendAction("config.save", OVERSIZED);
    await vi.waitFor(() => expect(fetch).toHaveBeenCalled());

    socket.closeFromServer(4401);
    answer(new Response(null, { status: 422 }));
    // Every microtask of the failed drain has run once a macrotask comes round.
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(notice()).toBe("Your session has expired. Reload this page to continue.");
  });

  it("keeps a refusal notice up when an action fails on the socket", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 401 }));
    const activity = mountActivity();
    const socket = FakeSocket.instances[0];
    socket.open();
    await activity.sendAction("config.save", OVERSIZED);
    await vi.waitFor(() =>
      expect(notice()).toBe("Your session has expired. Reload this page to continue."),
    );

    serverFrame(socket, { error: "action_failed", action: "answer.submit" });

    expect(notice()).toBe("Your session has expired. Reload this page to continue.");
  });

  it.each([502, 503])(
    "keeps a post a proxy answered with %i queued and stops later actions overtaking it",
    async (status) => {
      vi.mocked(fetch).mockResolvedValue(new Response(null, { status }));
      const activity = mountActivity();
      const socket = FakeSocket.instances[0];
      socket.open();

      await activity.sendAction("config.save", OVERSIZED);
      await activity.sendAction("answer.submit", [0]);
      // Every microtask of the failed drain has run once a macrotask comes round.
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(fetch).toHaveBeenCalled();
      expect(socket.sent).toEqual([]);
      expect(notice()).toBeUndefined();

      vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
      socket.open();

      await vi.waitFor(() => expect(sentActions(socket)).toEqual(["answer.submit"]));
    },
  );

  it("says the session expired and stops reconnecting when the socket's token is refused", () => {
    vi.useFakeTimers();
    mountActivity();

    FakeSocket.instances[0].closeFromServer(4401);
    vi.advanceTimersByTime(10_000);

    expect(notice()).toBe("Your session has expired. Reload this page to continue.");
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("says the activity is gone and stops reconnecting when the server cannot find it", () => {
    vi.useFakeTimers();
    mountActivity();

    FakeSocket.instances[0].closeFromServer(4404);
    vi.advanceTimersByTime(10_000);

    expect(notice()).toBe("This activity is no longer available.");
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("reconnects without a notice after an ordinary disconnect", () => {
    vi.useFakeTimers();
    mountActivity();

    FakeSocket.instances[0].closeFromServer(1006);
    vi.advanceTimersByTime(10_000);

    expect(notice()).toBeUndefined();
    expect(FakeSocket.instances.length).toBeGreaterThan(1);
  });

  it("says the session expired when a post is refused for its token", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 401 }));
    const activity = mountActivity();
    FakeSocket.instances[0].open();

    await activity.sendAction("config.save", OVERSIZED);

    await vi.waitFor(() =>
      expect(notice()).toBe("Your session has expired. Reload this page to continue."),
    );
  });
});
