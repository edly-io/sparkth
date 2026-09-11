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

export class SparkthPXC extends PXC {
  constructor() {
    super();
    this._configUrl = null;
    this._actionUrl = null;
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
}

customElements.define("pxc-activity", SparkthPXC);
