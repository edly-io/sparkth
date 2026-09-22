// SparkthPXC — the <pxc-activity> variant for activities hosted by Sparkth.
//
// Uses pxc.js's own WebSocket transport: actions go into its IndexedDB queue and out over the
// socket, and the events any action produces arrive on that socket — including events caused
// by somebody else's action, which is what a shared activity needs.
//
// Two things differ from the base class, both because this deployment authenticates every
// request with a launch token in the query string rather than a cookie:
//
//   * the socket URL comes from the configuration response, not pxc.js's default path
//   * _postAction, which _flushQueue uses for payloads above its 512 KiB socket ceiling, is
//     overridden to address Sparkth's route and carry the token
//
// A third difference is not about the token: reconnection gives up, and says so. pxc.js retries
// a dropped socket forever on a backoff capped at two seconds, and the launch token is baked
// into the socket URL, so once it lapses every reconnect's handshake is refused and the retry
// never ends. Nothing tells the viewer, and nothing tells an author that the save they were
// just told succeeded is sitting in a queue the server will never receive — sendAction resolves
// as soon as the action reaches IndexedDB, well before any round-trip.
//
// Reads two data-* attributes beyond the ones _initFromAttrs() handles:
//   data-config-url   GET endpoint returning this activity's configuration
//   data-action-url   POST endpoint for actions, one path segment short of the action name
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

export class SparkthPXC extends PXC {
  constructor() {
    super();
    this._configUrl = null;
    this._actionUrl = null;
    this._reconnectAttempts = 0;
    this._notice = null;
    this._onSocketOpen = this._onSocketOpen.bind(this);
  }

  async connectedCallback() {
    this._initFromAttrs();
    this._configUrl = this.getAttribute("data-config-url");
    this._actionUrl = this.getAttribute("data-action-url");

    const response = await fetch(this._configUrl);
    if (!response.ok) {
      console.error("PXC configuration failed:", response.status);
      return;
    }
    const config = await response.json();
    this.context = config.context;
    this.state = config.state;
    this.permission = config.permission;
    this._assetBaseUrl = config.asset_base_url;
    this._wsUrl = config.ws_url;

    this._initShadow();
    this.render();
    // Before _loadScript: _pushAction reads this._ws.readyState, which throws if the
    // activity's own script calls sendAction before a socket object exists.
    this._connectWebSocket();
    await this._loadScript(config.ui_url);
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
  // base class sets in _connectWebSocket().
  _connectWebSocket() {
    super._connectWebSocket();
    this._ws.addEventListener("open", this._onSocketOpen);
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
      this._showNotice();
      return;
    }
    super._scheduleReconnect();
  }

  // Into the document rather than the shadow root: an activity's UI owns that root and rewrites
  // its innerHTML on every render, which would take the notice with it.
  _showNotice() {
    if (this._notice) return;
    this._notice = document.createElement("div");
    this._notice.setAttribute("role", "alert");
    this._notice.textContent =
      "Disconnected from Sparkth. Anything changed since may not have been saved. Reload this page to continue.";
    this._notice.style.cssText =
      "padding:0.75em 1em;background:#fdecea;color:#611a15;font:inherit;border-bottom:1px solid #f5c6cb";
    document.body.prepend(this._notice);
  }

  _removeNotice() {
    if (!this._notice) return;
    this._notice.remove();
    this._notice = null;
  }
}

customElements.define("pxc-activity", SparkthPXC);
