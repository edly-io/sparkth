// Sizes each Sparkth activity iframe on this page to the height its content reports, so the
// activity shows in full and nothing scrolls inside the frame.
//
// The activity's page posts { type: "pxc:resize", height } to this page. Its iframe is
// sandboxed without same-origin access, so the message's origin is always "null" and cannot
// identify it; the sending window can.

function resizeSparkthActivity(event) {
  const data = event.data;
  if (!data || data.type !== "pxc:resize" || typeof data.height !== "number" || data.height <= 0) return;
  for (const frame of document.querySelectorAll("iframe[data-sparkth-pxc]")) {
    // Only the frame that sent the message: a unit can hold several activities.
    if (frame.contentWindow === event.source) frame.style.height = `${data.height}px`;
  }
}

// One listener per page, however many blocks ship this script.
if (!window.sparkthPxcResizing) {
  window.sparkthPxcResizing = true;
  window.addEventListener("message", resizeSparkthActivity);
}
