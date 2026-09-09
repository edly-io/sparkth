// SparkthPXC — the HTTP transport variant of <pxc-activity> for activities hosted by Sparkth.
//
// pxc.js's base PXC class ships a WebSocket transport. This slice returns an action's events in
// the same response that submitted it, so there is nothing to poll and no socket to keep: the
// subclass overrides the lifecycle to fetch its configuration once and POST actions.
//
// Reads two data-* attributes beyond the ones _initFromAttrs() handles:
//   data-config-url   GET endpoint returning this activity's configuration
//   data-action-url   POST endpoint for actions, one path segment short of the action name
//
// data-pxc-token is one _initFromAttrs() already reads, into this._pxcToken. Every route this
// class calls requires it as a query parameter, so both sendAction() and the getAssetUrl()
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

    this._initShadow();
    this.render();
    await this._loadScript(config.ui_url);
  }

  async sendAction(name, value = "") {
    if (this.permission === "view") {
      console.warn("sendAction called in view mode — ignored:", name);
      return;
    }
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
      return;
    }
    if (!response.ok) {
      console.error("Action rejected:", name, response.status);
      return;
    }
    const data = await response.json();
    for (const event of data.events || []) {
      this.onEvent(event.name, JSON.parse(event.value));
    }
  }

  // Overrides PXC's own getAssetUrl(), which builds `${this._assetBaseUrl}/${path}` with no
  // token. This transport's asset route requires one, and unlike sendAction()'s URL nothing is
  // appended after this one, so the token can go on as a trailing query string.
  getAssetUrl(path) {
    return `${super.getAssetUrl(path)}?token=${encodeURIComponent(this._pxcToken)}`;
  }
}

customElements.define("pxc-activity", SparkthPXC);
