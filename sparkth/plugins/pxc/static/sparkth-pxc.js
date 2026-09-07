// SparkthPXC — the HTTP transport variant of <pxc-activity> for activities hosted by Sparkth.
//
// pxc.js's base PXC class ships a WebSocket transport. This slice returns an action's events in
// the same response that submitted it, so there is nothing to poll and no socket to keep: the
// subclass overrides the lifecycle to fetch its configuration once and POST actions.
//
// Reads two data-* attributes beyond the ones _initFromAttrs() handles:
//   data-config-url   GET endpoint returning this activity's configuration
//   data-action-url   POST endpoint for actions, one path segment short of the action name

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
    let response;
    try {
      response = await fetch(`${this._actionUrl}/${encodeURIComponent(name)}`, {
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
}

customElements.define("pxc-activity", SparkthPXC);
