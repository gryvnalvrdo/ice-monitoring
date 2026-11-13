document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("login-form");
  const errBox = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");

  function showError(msg) {
    errBox.textContent = msg;
    errBox.classList.remove("hidden");
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    errBox.classList.add("hidden");
    btn.disabled = true;
    btn.textContent = "Memeriksa...";

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ username: username, password: password })
      });
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok) {
        showError(data.detail || "Gagal masuk. Periksa nama pengguna dan kata sandi.");
        btn.disabled = false;
        btn.textContent = "Masuk ke Dashboard";
        return;
      }
      window.location.replace("/");
    } catch (err) {
      showError("Koneksi ke server terganggu. Coba beberapa saat lagi.");
      btn.disabled = false;
      btn.textContent = "Masuk ke Dashboard";
    }
  });
});

