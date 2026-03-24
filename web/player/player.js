async function loadPayload() {
  const status = document.getElementById("status");
  const payload = document.getElementById("payload");

  try {
    const response = await fetch("/payload.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    status.textContent = `Session ${data.session_id} with ${data.packet_sequence.length} packets ready.`;
    payload.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    status.textContent = `Unable to load packet feed: ${error.message}`;
    payload.textContent = "";
  }
}

document.addEventListener("DOMContentLoaded", loadPayload);
