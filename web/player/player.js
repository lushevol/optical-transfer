function renderFrame(packetSequence, index) {
  const status = document.getElementById("status");
  const payload = document.getElementById("payload");
  const packet = packetSequence[index];

  status.textContent = `Frame ${index + 1} of ${packetSequence.length}`;
  payload.textContent = packet;
}

function startPlayback(data) {
  const packetSequence = data.packet_sequence || [];
  if (packetSequence.length === 0) {
    document.getElementById("status").textContent = "No packets available.";
    document.getElementById("payload").textContent = "";
    return;
  }

  let index = 0;
  renderFrame(packetSequence, index);

  window.setInterval(() => {
    index = (index + 1) % packetSequence.length;
    renderFrame(packetSequence, index);
  }, 600);
}

async function loadPayload() {
  const status = document.getElementById("status");
  const payload = document.getElementById("payload");

  try {
    const response = await fetch("/payload.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    status.textContent = `Session ${data.session_id} ready.`;
    payload.textContent = "Loading frame 1...";
    startPlayback(data);
  } catch (error) {
    status.textContent = `Unable to load packet feed: ${error.message}`;
    payload.textContent = "";
  }
}

document.addEventListener("DOMContentLoaded", loadPayload);
