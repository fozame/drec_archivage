function afficherToast(message, estErreur = false) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.background = estErreur ? "#dc2626" : "#1c2029";
  toast.classList.add("visible");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("visible"), 3500);
}

async function appelApi(url, options = {}) {
  const reponse = await fetch(url, options);
  if (!reponse.ok) {
    let detail = reponse.statusText;
    try {
      const data = await reponse.json();
      detail = data.detail || detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  const contentType = reponse.headers.get("content-type") || "";
  return contentType.includes("application/json") ? reponse.json() : reponse;
}
