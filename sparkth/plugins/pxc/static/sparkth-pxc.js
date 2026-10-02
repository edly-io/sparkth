// SparkthPXC — the <pxc-activity> variant for activities hosted by Sparkth.
//
// Uses pxc.js's own WebSocket transport: actions go out over the socket, and the events any
// action produces arrive on that socket — including events caused by somebody else's action,
// which is what a shared activity needs.
//
// Two things differ from the base class, both because this deployment authenticates every
// request with a launch token in the query string rather than a cookie:
//
//   * the socket URL comes from the inline configuration, not pxc.js's default path
//   * _postAction, which _flushQueue uses for payloads above its 512 KiB socket ceiling, is
//     overridden to address Sparkth's route and carry the token
//
// A third: reconnection stops, and says why. pxc.js retries a dropped socket forever. Here a
// socket the server refuses (an expired token, a missing activity) stops at once with a notice
// naming the cause, and any other drop stops with a notice after a bounded number of retries.
// sendAction resolves as soon as the action is queued, so without the notice an author would
// never learn that a save they were told succeeded did not reach the server.
//
// A fourth: the queue lives in memory, not in pxc.js's IndexedDB store. The embed page runs in
// an opaque origin, where IndexedDB throws, so an action still queued when the page reloads is
// lost.
//
// The configuration is a <script type="application/json"> child of the element, written by the
// embed route; nothing is fetched for it.
//
// data-pxc-token is one _initFromAttrs() already reads, into this._pxcToken. Every route this
// class calls requires it as a query parameter, so both _postAction() and the getAssetUrl()
// override append it themselves rather than having it baked into a base URL — a base URL that
// already ended in "?token=..." would land the token mid-path once a segment or another query
// string is appended after it.

import { PXC } from "./pxc.js";

// How many consecutive failed connections to accept before giving up. pxc.js's backoff caps at
// two seconds, so this is roughly a minute of retrying: long enough to ride out an ordinary
// network blip, after which the queued actions flush and nothing is lost, and short enough that
// a lapsed token stops costing the server a refused handshake every two seconds per stale tab.
const MAX_RECONNECT_ATTEMPTS = 30;

// pxc.js's own ceiling for one socket frame; a larger action goes through _postAction instead.
const WS_PAYLOAD_MAX = 512 * 1024;

// What to tell the viewer when the server refuses, by HTTP status. A refused socket closes with
// 4000 plus the same status.
const REFUSAL_NOTICES = {
  401: "Your session has expired. Reload this page to continue.",
  404: "This activity is no longer available.",
};
const CLOSE_CODE_BASE = 4000;

const DISCONNECTED_NOTICE =
  "Disconnected from Sparkth. Anything changed since may not have been saved. Reload this page to continue.";

export class SparkthPXC extends PXC {
  constructor() {
    super();
    this._actionUrl = null;
    this._queue = [];
    this._reconnectAttempts = 0;
    this._notice = null;
    this._onSocketOpen = this._onSocketOpen.bind(this);
  }

  async connectedCallback() {
    this._initFromAttrs();
    const config = JSON.parse(this.querySelector('script[type="application/json"]').textContent);
    this.context = config.context;
    this.state = config.state;
    this.permission = config.permission;
    this._assetBaseUrl = config.asset_base_url;
    this._actionUrl = config.action_base_url;
    this._wsUrl = config.ws_url;

    this._initShadow();
    this.render();
    // Before _loadScript: _pushAction reads this._ws.readyState, which throws if the
    // activity's own script calls sendAction before a socket object exists.
    this._connectWebSocket();
    await this._loadScript(config.ui_url);
  }

  // Overrides PXC's own _pushAction(), which writes to IndexedDB.
  _pushAction(action) {
    this._queue.push(action);
    if (this._ws.readyState === WebSocket.OPEN) this._flushQueue();
  }

  // Overrides PXC's own _flushQueue(). Drains in order and stops at the first action that cannot
  // go yet, so a later action never overtakes it; one pushed mid-drain is picked up by the loop.
  async _flushQueue() {
    if (this._flushing) return;
    this._flushing = true;
    try {
      while (this._queue.length > 0 && (await this._sendQueued(this._queue[0]))) {
        this._queue.shift();
      }
    } finally {
      this._flushing = false;
    }
  }

  // Sends one queued action, over the socket or by POST past the frame ceiling. Resolves to
  // whether it went.
  async _sendQueued({ action, value, permission }) {
    const payload = JSON.stringify({ action, value, permission });
    if (payload.length > WS_PAYLOAD_MAX) return this._postAction(action, value);
    if (this._ws.readyState !== WebSocket.OPEN) return false;
    this._ws.send(payload);
    return true;
  }

  // Overrides PXC's own _postAction(), which posts to /api/activity/{id}/actions/{name} with
  // cookie credentials — a route this deployment does not serve and a credential it does not
  // use. _flushQueue() calls this only for payloads above its 512 KiB socket ceiling, and reads
  // the returned boolean to decide whether to keep draining the queue: throwing instead would
  // abort the flush and strand every record behind this one.
  async _postAction(name, value) {
    const url = `${this._actionUrl}/${encodeURIComponent(name)}?token=${encodeURIComponent(this._pxcToken)}`;
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(value),
      });
    } catch (error) {
      console.error("Action failed:", name, error);
      return false;
    }
    if (!response.ok) {
      console.error("POST action failed:", name, response.status);
      const notice = REFUSAL_NOTICES[response.status];
      if (notice) this._showNotice(notice);
      return false;
    }
    return true;
  }

  // Overrides PXC's own getAssetUrl(), which builds `${this._assetBaseUrl}/${path}` with no
  // token. This transport's asset route requires one, and unlike _postAction()'s URL nothing is
  // appended after this one, so the token can go on as a trailing query string.
  getAssetUrl(path) {
    return `${super.getAssetUrl(path)}?token=${encodeURIComponent(this._pxcToken)}`;
  }

  // Listens on the socket rather than on pxc.js's own `pxc:connection` window event, which
  // every activity on a page would share, and rather than reassigning the onopen handler the
  // base class sets in _connectWebSocket(). The onclose handler is wrapped so a refusal ends
  // the retries: the same token would only be refused again.
  _connectWebSocket() {
    super._connectWebSocket();
    this._ws.addEventListener("open", this._onSocketOpen);
    const reconnect = this._ws.onclose;
    this._ws.onclose = (event) => {
      const notice = REFUSAL_NOTICES[event.code - CLOSE_CODE_BASE];
      if (notice) this._showNotice(notice);
      else reconnect(event);
    };
  }

  // A socket that opens means the queue is draining again, so the count starts over and the
  // notice comes down. Reached only on a real handshake: a refused one closes without opening.
  _onSocketOpen() {
    this._reconnectAttempts = 0;
    this._removeNotice();
  }

  // Overrides PXC's own _scheduleReconnect(), which retries without a ceiling.
  _scheduleReconnect() {
    this._reconnectAttempts += 1;
    if (this._reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      this._showNotice(DISCONNECTED_NOTICE);
      return;
    }
    super._scheduleReconnect();
  }

  // Into the document rather than the shadow root: an activity's UI owns that root and rewrites
  // its innerHTML on every render, which would take the notice with it.
  _showNotice(message) {
    if (!this._notice) {
      this._notice = document.createElement("div");
      this._notice.setAttribute("role", "alert");
      this._notice.style.cssText =
        "padding:0.75em 1em;background:#fdecea;color:#611a15;font:inherit;border-bottom:1px solid #f5c6cb";
      document.body.prepend(this._notice);
    }
    this._notice.textContent = message;
  }

  _removeNotice() {
    if (!this._notice) return;
    this._notice.remove();
    this._notice = null;
  }
}

customElements.define("pxc-activity", SparkthPXC);
