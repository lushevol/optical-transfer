function renderFrame(frameSequence, index) {
  const status = document.getElementById("status");
  const frame = document.getElementById("frame");
  const image = frameSequence[index];

  status.textContent = `Frame ${index + 1} of ${frameSequence.length}`;
  frame.src = image;
}

function startPlayback(data) {
  const frameSequence = data.frame_sequence || [];
  if (frameSequence.length === 0) {
    document.getElementById("status").textContent = "No packets available.";
    document.getElementById("frame").removeAttribute("src");
    return;
  }

  let index = 0;
  renderFrame(frameSequence, index);

  window.setInterval(() => {
    index = (index + 1) % frameSequence.length;
    renderFrame(frameSequence, index);
  }, 600);
}

async function loadPayload() {
  const status = document.getElementById("status");
  const frame = document.getElementById("frame");

  try {
    const response = await fetch("/payload.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    status.textContent = `Session ${data.session_id} ready.`;
    frame.removeAttribute("src");
    startPlayback(data);
  } catch (error) {
    status.textContent = `Unable to load packet feed: ${error.message}`;
    frame.removeAttribute("src");
  }
}

document.addEventListener("DOMContentLoaded", loadPayload);
