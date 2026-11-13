document.addEventListener("DOMContentLoaded", function () {
  function localDateStr(dateObj) {
    const d = dateObj || new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + day;
  }

  const state = {
    user: null,
    csrfToken: "",
    allowSimulation: false,
    retentionDays: 30,
    selectedDate: localDateStr(),
    incidentFilter: "all",
    searchQuery: "",
    overview: null,
    activeCamera: "cam3",
    streamAttached: false,
    ws: null
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clearNode(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function openModal(title, bodyBuilder) {
    const backdrop = document.getElementById("modal-backdrop");
    const mTitle = document.getElementById("modal-title");
    const mBody = document.getElementById("modal-body");
    mTitle.textContent = title;
    clearNode(mBody);
    bodyBuilder(mBody);
    backdrop.classList.remove("hidden");
  }

  function closeModal() {
    const backdrop = document.getElementById("modal-backdrop");
    const mBody = document.getElementById("modal-body");
    const vids = mBody.querySelectorAll("video");
    vids.forEach(function (v) { v.pause(); v.removeAttribute("src"); });
    clearNode(mBody);
    backdrop.classList.add("hidden");
  }

  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-backdrop").addEventListener("click", function (e) {
    if (e.target === this) closeModal();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });

  function updateClock() {
    const now = new Date();
    document.getElementById("hdr-clock").textContent = now.toLocaleTimeString("id-ID", { hour12: false });
  }
  updateClock();
  setInterval(updateClock, 1000);

  async function apiGet(url) {
    const res = await fetch(url, { credentials: "same-origin" });
    if (res.status === 401) {
      window.location.replace("/login");
      throw new Error("Sesi berakhir");
    }
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      throw new Error(err.detail || "Gagal memuat data.");
    }
    return res.json();
  }

  async function apiPost(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": state.csrfToken
      },
      body: JSON.stringify(payload || {})
    });
    if (res.status === 401) {
      window.location.replace("/login");
      throw new Error("Sesi berakhir");
    }
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error(data.detail || "Permintaan gagal dijalankan.");
    }
    return data;
  }

  function formatDuration(sec) {
    const s = Math.max(0, Number(sec || 0));
    const m = Math.floor(s / 60);
    const rem = s % 60;
    if (m === 0) return rem + " detik";
    return m + " menit " + rem + " detik";
  }

  function formatTimeOnly(ts) {
    if (!ts) return "-";
    const parts = String(ts).split(/[T ]/);
    return parts.length > 1 ? parts[1].slice(0, 8) : String(ts).slice(0, 8);
  }

  function classifyIncident(a) {
    if (a.category) return a.category;
    const t = String(a.anomaly_type || "");
    const st = String(a.status || "");
    if (st === "RECOVERED_TO_TRUCK") return "recovered";
    if (t === "CAMERA_DISCONNECTED" || t === "SYSTEM_SHUTDOWN" || t === "SYSTEM_ENGINE_STOPPED" || t.indexOf("CAMERA_TAMPER_") === 0 || t === "CAMERA_RECONNECTED") {
      return "camera";
    }
    if (st === "CONFIRMED_THEFT") return "theft";
    return "pending";
  }

  function humanIncidentTitle(a, cat) {
    const t = String(a.anomaly_type || "");
    if (cat === "recovered") return "Batal Otomatis — Es Masuk Kembali ke Truk";
    if (t === "CAMERA_DISCONNECTED") return "Kamera Terputus / Listrik Padam";
    if (t === "CAMERA_RECONNECTED") return "Kamera Tersambung Kembali";
    if (t === "SYSTEM_ENGINE_STOPPED") return "Pemantauan Dihentikan Petugas";
    if (t === "SYSTEM_SHUTDOWN") return "Komputer / Program Dimatikan";
    if (t.indexOf("CAMERA_TAMPER_") === 0) return "Posisi / Lensa Kamera Terganggu";
    if (cat === "theft") return "Alarm Pencurian — Es Tidak Masuk ke Truk";
    return "Sedang Dipantau (Es di Samping Papan)";
  }

  function humanIncidentDetails(a, cat) {
    if (cat === "recovered") return "Es sempat bergeser ke samping, lalu dimasukkan kembali ke truk. Bukan pencurian.";
    const d = String(a.details || "");
    const cleaned = d.replace(/\[SHA-256:[^\]]+\]/g, "").replace(/\[SIMULASI\]/g, "(Uji Coba)").trim();
    return cleaned || "Tercatat oleh sistem pemantau pabrik.";
  }

  function showAdminFeedback(msg, isError) {
    const box = document.getElementById("admin-feedback");
    box.textContent = msg;
    box.className = isError ? "alert-box alert-danger" : "alert-box alert-ok";
    box.classList.remove("hidden");
  }

  function renderTelemetry(t, isActive) {
    const cam = (t && t.camera_profile) ? t.camera_profile : state.activeCamera;
    state.activeCamera = cam;

    document.getElementById("tab-cam3").classList.toggle("active", cam === "cam3");
    document.getElementById("tab-cam10").classList.toggle("active", cam === "cam10");
    document.getElementById("camera-subtitle").textContent =
      cam === "cam10" ? "Kamera 10 — Area Samping Papan" : "Kamera 3 — Papan Loading Utama";

    const active = Boolean(isActive !== undefined ? isActive : (t && t.is_running));
    const streamSt = (t && t.stream_status) || "IDLE";
    const tamperSt = (t && t.tamper_status) || "NORMAL";

    const pill = document.getElementById("hdr-status-pill");
    clearNode(pill);
    const dot = el("span", "dot");
    const txt = el("span");
    if (!active) {
      pill.className = "pill";
      txt.textContent = "Pemantauan Berhenti";
    } else if (streamSt === "DISCONNECTED" || streamSt === "RECONNECTING") {
      pill.className = "pill pill-danger";
      txt.textContent = "Kamera Terputus";
    } else if (tamperSt !== "NORMAL") {
      pill.className = "pill pill-warn";
      txt.textContent = "Kamera Terganggu";
    } else {
      pill.className = "pill pill-ok";
      txt.textContent = "Kamera Menyala";
    }
    pill.appendChild(dot);
    pill.appendChild(txt);

    const banner = document.getElementById("honest-banner");
    const bTitle = document.getElementById("banner-title");
    const bDesc = document.getElementById("banner-desc");
    const bTime = document.getElementById("banner-time");
    const lastActiveAt = (t && (t.last_active_at || t.last_event_time)) || "-";

    if (!active) {
      banner.className = "status-banner alert-warn";
      bTitle.textContent = "PEMANTAUAN SEDANG BERHENTI (STANDBY)";
      bDesc.textContent = "Angka di layar tidak sedang bertambah secara langsung sampai Admin menekan Mulai Pemantauan.";
      bTime.textContent = "Terakhir update: " + lastActiveAt;
      banner.classList.remove("hidden");
    } else if (streamSt === "DISCONNECTED" || streamSt === "RECONNECTING") {
      banner.className = "status-banner alert-danger";
      bTitle.textContent = "KAMERA TERPUTUS — MOHON PERIKSA KABEL / LISTRIK CCTV";
      bDesc.textContent = "Aliran video ke komputer terhenti sementara. Sistem mencoba menyambung ulang otomatis.";
      bTime.textContent = "Terakhir aktif: " + lastActiveAt;
      banner.classList.remove("hidden");
    } else if (tamperSt !== "NORMAL") {
      banner.className = "status-banner alert-danger";
      bTitle.textContent = "PERINGATAN: KAMERA TERTUTUP ATAU DIGESER";
      bDesc.textContent = "Harap periksa posisi dan lensa kamera CCTV di area muat pabrik.";
      bTime.textContent = "Terdeteksi: " + lastActiveAt;
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }

    const liveImg = document.getElementById("cctv-live-img");
    const standbyBox = document.getElementById("cctv-standby-box");
    const zoomBtn = document.getElementById("btn-zoom-cctv");
    const srcBadge = document.getElementById("source-kind-badge");

    if (active) {
      standbyBox.classList.add("hidden");
      liveImg.classList.remove("hidden");
      zoomBtn.classList.remove("hidden");
      if (!state.streamAttached) {
        liveImg.src = "/api/stream/live?t=" + Date.now();
        state.streamAttached = true;
      }
      const isLiveCam = state.overview && state.overview.source_is_rtsp;
      srcBadge.textContent = isLiveCam ? "Kamera Langsung" : "Rekaman Video Uji";
      srcBadge.className = "pill pill-ok";
    } else {
      if (state.streamAttached) {
        liveImg.removeAttribute("src");
        state.streamAttached = false;
      }
      liveImg.classList.add("hidden");
      zoomBtn.classList.add("hidden");
      standbyBox.classList.remove("hidden");
      srcBadge.textContent = "Standby";
      srcBadge.className = "pill";
    }

    if (state.user && state.user.role === "admin") {
      document.getElementById("btn-start-engine").classList.toggle("hidden", active);
      document.getElementById("btn-stop-engine").classList.toggle("hidden", !active);
    }

    const tamperEl = document.getElementById("tamper-label");
    if (tamperSt !== "NORMAL") {
      tamperEl.className = "pill pill-danger";
      tamperEl.textContent = "Peringatan: Posisi Kamera Terganggu";
    } else {
      tamperEl.className = "pill pill-ok";
      tamperEl.textContent = "Posisi Kamera Normal";
    }
    document.getElementById("last-update-label").textContent = "Terakhir update: " + lastActiveAt;

    const truckPresent = Boolean(t && t.truck_present);
    const tId = (t && t.truck_id && t.truck_id !== "-") ? t.truck_id : "";
    document.getElementById("active-truck-name").textContent =
      truckPresent && tId ? "Truk " + tId : "Menunggu Truk Masuk...";
    document.getElementById("active-trip-num").textContent =
      "Trip #" + ((t && t.trip_number) || "-");

    document.getElementById("active-large").textContent = String((t && t.count_large) || 0);
    document.getElementById("active-small").textContent = String((t && t.count_small) || 0);
    document.getElementById("active-total").textContent = String((t && t.count_total) || 0);

    const activeTheft = Number((t && t.active_anomalies_count) || 0);
    const pendingSide = Number((t && t.pending_side_count) || 0);
    const secBox = document.getElementById("security-status-box");
    const secTitle = document.getElementById("security-status-title");
    const secDesc = document.getElementById("security-status-desc");

    if (activeTheft > 0) {
      secBox.className = "security-box alert-danger";
      secTitle.textContent = "ALARM PENCURIAN (" + activeTheft + " Kejadian) — Es Tidak Masuk ke Truk!";
      secDesc.textContent = "Segera periksa daftar peringatan di bawah dan putar video bukti.";
    } else if (pendingSide > 0) {
      secBox.className = "security-box alert-warn";
      secTitle.textContent = "SEDANG DIPANTAU — Es Tergeser ke Samping (Belum Pencurian)";
      secDesc.textContent = "Sistem menunggu apakah pekerja memasukkan kembali es ke truk. Jika masuk lagi, alarm batal otomatis.";
    } else {
      secBox.className = "security-box alert-ok";
      secTitle.textContent = "AMAN — Semua Es Masuk ke Truk";
      secDesc.textContent = "Tidak ada es yang keluar ke samping atau tertinggal di luar truk.";
    }

    document.getElementById("active-last-event").textContent =
      (t && t.last_event) || "Menunggu aktivitas pemuatan...";
    document.getElementById("active-last-event-time").textContent =
      (t && t.last_event_time) || "--:--:--";

    if (t && Array.isArray(t.recent_counts)) {
      renderSnapshots(t.recent_counts);
    }
  }

  function renderSnapshots(items) {
    const strip = document.getElementById("snapshot-strip");
    const countPill = document.getElementById("snapshot-count-pill");
    clearNode(strip);

    if (!items || items.length === 0) {
      countPill.textContent = "0 foto baru";
      strip.appendChild(el("div", "empty-msg", "Belum ada foto hitungan pada sesi ini."));
      return;
    }

    countPill.textContent = items.length + " foto baru";
    items.slice(0, 12).forEach(function (item) {
      const card = el("button", "snap-card");
      card.type = "button";

      if (item.snapshot) {
        const img = document.createElement("img");
        img.className = "snap-thumb";
        img.src = "/api/snapshots/" + encodeURIComponent(item.snapshot);
        img.alt = (item.size_label || "Es") + " pada " + (item.time || "");
        card.appendChild(img);
      } else {
        card.appendChild(el("div", "snap-thumb"));
      }

      const info = el("div", "snap-info");
      const qtyText = item.is_stacked ? "2 Es Bertumpuk" : (item.size_label || "Kantong Es");
      info.appendChild(el("div", "snap-title", qtyText));
      info.appendChild(el("div", "snap-meta", (item.time || "-") + " • " + (item.trajectory_label || "Lewat Papan")));
      card.appendChild(info);

      card.addEventListener("click", function () {
        openModal("Detail Foto Hitungan Es", function (mBody) {
          if (item.snapshot) {
            const big = document.createElement("img");
            big.className = "modal-img";
            big.src = "/api/snapshots/" + encodeURIComponent(item.snapshot);
            big.alt = qtyText;
            mBody.appendChild(big);
          }
          const grid = el("div", "detail-grid");
          grid.style.marginTop = "12px";

          const s1 = el("div", "detail-stat");
          s1.appendChild(el("div", "card-subtitle", "Jenis Muatan"));
          s1.appendChild(el("strong", "", qtyText));

          const s2 = el("div", "detail-stat");
          s2.appendChild(el("div", "card-subtitle", "Cara Masuk Truk"));
          s2.appendChild(el("strong", "", item.trajectory_label || "Lewat Papan"));

          const s3 = el("div", "detail-stat");
          s3.appendChild(el("div", "card-subtitle", "Jam & Truk"));
          s3.appendChild(el("strong", "", (item.time || "-") + " (Truk " + (item.truck_id || "-") + ")"));

          grid.appendChild(s1);
          grid.appendChild(s2);
          grid.appendChild(s3);
          mBody.appendChild(grid);
        });
      });

      strip.appendChild(card);
    });
  }

  function renderIncidents(anomalies, recoveries) {
    const list = document.getElementById("incident-list");
    clearNode(list);

    const combined = [];
    (anomalies || []).forEach(function (a) {
      const cat = classifyIncident(a);
      combined.push({
        cat: cat,
        title: humanIncidentTitle(a, cat),
        desc: humanIncidentDetails(a, cat),
        time: a.timestamp || "",
        truck: a.truck_id || "-",
        video: a.video_clip_path || "",
        videoAvailable: a.video_available !== false
      });
    });
    (recoveries || []).forEach(function (r) {
      combined.push({
        cat: "recovered",
        title: "Batal Otomatis — Es Masuk Kembali ke Truk",
        desc: r.message || "Es dari samping kembali dimasukkan ke truk.",
        time: r.time || "",
        truck: r.truck_id || "-",
        video: ""
      });
    });

    const filtered = combined.filter(function (item) {
      if (state.incidentFilter === "all") return true;
      return item.cat === state.incidentFilter;
    });

    if (filtered.length === 0) {
      list.appendChild(el("div", "empty-msg", "Tidak ada catatan untuk filter yang dipilih."));
      return;
    }

    filtered.slice(0, 40).forEach(function (item) {
      const row = el("div", "incident-item incident-" + (item.cat === "pending" ? "camera" : item.cat));
      const top = el("div", "incident-top");
      top.appendChild(el("span", "", item.title));
      top.appendChild(el("span", "tabular", formatTimeOnly(item.time)));
      row.appendChild(top);

      row.appendChild(el("div", "incident-desc", "Truk " + item.truck + " — " + item.desc));

      if (item.video) {
        const fname = String(item.video).split(/[\\/]/).pop();
        if (fname && item.videoAvailable) {
          const btnWrap = el("div");
          const btn = el("button", "btn btn-danger btn-sm", "Putar Video Bukti");
          btn.type = "button";
          btn.addEventListener("click", function () {
            openEvidenceModal(fname, item.title, item.truck, item.time);
          });
          btnWrap.appendChild(btn);
          row.appendChild(btnWrap);
        } else if (fname) {
          row.appendChild(el("div", "card-subtitle", "Video bukti sudah dihapus otomatis untuk hemat ruang simpan; catatan & salinan Telegram tetap tersimpan."));
        }
      }

      list.appendChild(row);
    });
  }

  function openEvidenceModal(filename, titleText, truckId, timeText) {
    openModal("Video Bukti Kejadian", function (mBody) {
      const info = el("div", "alert-box alert-warn");
      info.textContent = titleText + " • Truk " + (truckId || "-") + " • Waktu: " + (timeText || "-");
      mBody.appendChild(info);

      const video = document.createElement("video");
      video.className = "modal-video";
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      video.src = "/api/evidence/" + encodeURIComponent(filename);
      mBody.appendChild(video);

      const actRow = el("div", "admin-row");
      actRow.style.marginTop = "10px";
      const dl = el("a", "btn btn-outline btn-sm", "Unduh Video (.mp4)");
      dl.href = "/api/evidence/" + encodeURIComponent(filename);
      dl.setAttribute("download", filename);
      actRow.appendChild(dl);
      actRow.appendChild(el("span", "card-subtitle", "Rekaman bukti tersimpan otomatis dan terlindungi dari perubahan."));
      mBody.appendChild(actRow);
    });
  }

  function renderTrips(trips) {
    const tbody = document.getElementById("trips-tbody");
    const empty = document.getElementById("trips-empty");
    clearNode(tbody);

    const q = state.searchQuery.trim().toLowerCase();
    const rows = (trips || []).filter(function (tr) {
      if (!q) return true;
      return String(tr.truck_id || "").toLowerCase().indexOf(q) !== -1;
    });

    if (rows.length === 0) {
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");

    rows.forEach(function (tr) {
      const row = document.createElement("tr");
      row.appendChild(el("td", "tabular", formatTimeOnly(tr.start_time)));

      const tdTruck = el("td");
      tdTruck.appendChild(el("strong", "", tr.truck_id || "Belum Terbaca"));
      tdTruck.appendChild(el("div", "card-subtitle", "Trip #" + (tr.trip_number || 1)));
      row.appendChild(tdTruck);

      row.appendChild(el("td", "tabular", String(tr.count_large || 0)));
      row.appendChild(el("td", "tabular", String(tr.count_small || 0)));

      const tdTotal = el("td", "tabular");
      tdTotal.appendChild(el("strong", "", String(tr.count_total || 0) + " kantong"));
      row.appendChild(tdTotal);

      const tdSt = el("td");
      const stPill = el("span", tr.status === "active" ? "pill pill-ok" : "pill");
      stPill.textContent = tr.status === "active" ? "Sedang Muat" : "Selesai";
      tdSt.appendChild(stPill);
      row.appendChild(tdSt);

      row.addEventListener("click", function () {
        openTripDetailModal(tr.id);
      });
      tbody.appendChild(row);
    });
  }

  async function openTripDetailModal(tripId) {
    try {
      const detail = await apiGet("/api/trips/" + encodeURIComponent(tripId));
      openModal("Rincian Muatan Truk " + (detail.truck_id || "-") + " (Trip #" + (detail.trip_number || 1) + ")", function (mBody) {
        const g1 = el("div", "detail-grid");
        const c1 = el("div", "detail-stat");
        c1.appendChild(el("div", "card-subtitle", "Total Kantong Es"));
        c1.appendChild(el("strong", "tabular", String(detail.count_total || 0) + " (Besar: " + (detail.count_large || 0) + ", Kecil: " + (detail.count_small || 0) + ")"));

        const c2 = el("div", "detail-stat");
        c2.appendChild(el("div", "card-subtitle", "Jam & Durasi"));
        c2.appendChild(el("strong", "", formatTimeOnly(detail.start_time) + " (" + formatDuration(detail.duration_sec) + ")"));

        const evs = detail.events || [];
        let papan = 0;
        let samping = 0;
        let lempar = 0;
        evs.forEach(function (ev) {
          if (ev.trajectory_type === "samping_kembali") samping += 1;
          else if (ev.trajectory_type === "lempar_langsung") lempar += 1;
          else papan += 1;
        });

        const c3 = el("div", "detail-stat");
        c3.appendChild(el("div", "card-subtitle", "Jalur Masuk Truk"));
        c3.appendChild(el("strong", "", "Papan: " + papan + " • Kembali: " + samping + " • Lempar: " + lempar));

        g1.appendChild(c1);
        g1.appendChild(c2);
        g1.appendChild(c3);
        mBody.appendChild(g1);

        const h = el("h4", "", "Peringatan pada Truk Ini");
        h.style.margin = "8px 0";
        mBody.appendChild(h);

        const anoms = detail.anomalies || [];
        if (anoms.length === 0) {
          mBody.appendChild(el("div", "alert-box alert-ok", "Aman. Tidak ada kejadian pencurian atau kendala pada trip ini."));
        } else {
          anoms.forEach(function (a) {
            const cat = classifyIncident(a);
            const box = el("div", "incident-item incident-" + (cat === "pending" ? "camera" : cat));
            box.style.marginBottom = "8px";
            box.appendChild(el("strong", "", humanIncidentTitle(a, cat) + " (" + formatTimeOnly(a.timestamp) + ")"));
            box.appendChild(el("div", "incident-desc", humanIncidentDetails(a, cat)));
            if (a.video_clip_path) {
              const fname = String(a.video_clip_path).split(/[\\/]/).pop();
              if (fname && a.video_available !== false) {
                const btn = el("button", "btn btn-danger btn-sm", "Putar Video Bukti");
                btn.type = "button";
                btn.addEventListener("click", function () {
                  openEvidenceModal(fname, humanIncidentTitle(a, cat), detail.truck_id, a.timestamp);
                });
                box.appendChild(btn);
              } else if (fname) {
                box.appendChild(el("div", "card-subtitle", "Video bukti sudah dihapus otomatis untuk hemat ruang simpan."));
              }
            }
            mBody.appendChild(box);
          });
        }
      });
    } catch (err) {
      openModal("Info", function (mBody) {
        mBody.appendChild(el("div", "alert-box alert-danger", err.message));
      });
    }
  }

  function renderOverview(data) {
    state.overview = data;
    document.getElementById("branch-label").textContent =
      "Cabang " + (data.city || "-") + " • Sumber: " + (data.active_source_label || "Standby");

    const stats = data.stats || {};
    const summary = data.summary || {};
    document.getElementById("kpi-trucks").textContent = String(summary.total_trucks || 0);
    document.getElementById("kpi-trips").textContent = String(summary.total_trips || 0) + " kali pengisian";
    document.getElementById("kpi-grand-total").textContent = String(summary.grand_total || 0);
    document.getElementById("kpi-split-detail").textContent =
      "Besar: " + (summary.total_large || 0) + " | Kecil: " + (summary.total_small || 0);
    document.getElementById("kpi-theft").textContent = String(stats.theft_count || 0);
    document.getElementById("kpi-recovered").textContent = String(stats.recovered_count || 0);

    const t = data.live_telemetry || {};
    renderTelemetry(t, data.is_active);
    renderIncidents(data.anomalies || [], t.recent_recoveries || []);
    renderTrips(data.trips || []);

    if (data.storage) {
      const pct = Number(data.storage.used_percent || 0);
      const retDays = Number(data.storage.retention_days || 0);
      state.retentionDays = retDays;
      const statusText = pct >= 85 ? "Hampir Penuh" : "Aman";
      const retText = retDays > 0 ? " • Auto-hapus video > " + retDays + " hari" : "";
      document.getElementById("footer-storage").textContent =
        "Ruang Penyimpanan Bukti: Sisa " + (data.storage.free_gb || 0) + " GB (" + statusText + ")" + retText;
    }
    if (data.cloud) {
      const cState = data.cloud.is_enabled ? (data.cloud.sync_status || "Aktif") : "Nonaktif (Lokal)";
      const cTime = data.cloud.last_sync_time ? " • Terakhir kirim: " + data.cloud.last_sync_time : "";
      document.getElementById("footer-cloud").textContent = "Cadangan Data Cloud: " + cState + cTime;
    }
  }

  async function refreshOverview() {
    try {
      const data = await apiGet("/api/overview?date=" + encodeURIComponent(state.selectedDate));
      renderOverview(data);
    } catch (err) {
      if (err.message !== "Sesi berakhir") {
        console.error(err);
      }
    }
  }

  async function loadCameraOptions() {
    if (!state.user || state.user.role !== "admin") return;
    try {
      const data = await apiGet("/api/cameras");
      const sel = document.getElementById("admin-source-select");
      clearNode(sel);
      (data.sources || []).forEach(function (src) {
        const opt = document.createElement("option");
        opt.value = src.value;
        opt.textContent = src.label;
        sel.appendChild(opt);
      });
    } catch (err) {
      console.error(err);
    }
  }

  function connectWebSocket() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(proto + "//" + window.location.host + "/ws/telemetry");
    state.ws = ws;

    ws.onmessage = function (event) {
      try {
        const t = JSON.parse(event.data);
        renderTelemetry(t, t.is_running);
      } catch (e) {
        console.error(e);
      }
    };

    ws.onclose = function (ev) {
      if (ev.code === 4401 || ev.code === 1008) {
        window.location.replace("/login");
        return;
      }
      setTimeout(connectWebSocket, 3000);
    };
  }

  async function init() {
    const me = await apiGet("/api/auth/me");
    state.user = me;
    state.csrfToken = me.csrf_token;
    state.allowSimulation = Boolean(me.allow_simulation);

    document.getElementById("hdr-user").textContent =
      me.username + " (" + (me.role === "admin" ? "Admin" : "Operator") + ")";

    if (me.role === "admin") {
      document.getElementById("admin-panel").classList.remove("hidden");
      if (state.allowSimulation) {
        document.getElementById("sim-panel").classList.remove("hidden");
      }
      await loadCameraOptions();
    }

    document.getElementById("date-filter").value = state.selectedDate;
    await refreshOverview();
    connectWebSocket();
    setInterval(refreshOverview, 5000);
  }

  document.getElementById("btn-logout").addEventListener("click", async function () {
    try {
      await apiPost("/api/auth/logout", {});
    } catch (e) {
      console.error(e);
    } finally {
      window.location.replace("/login");
    }
  });

  document.querySelectorAll("[data-help-title]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const title = btn.getAttribute("data-help-title");
      const body = btn.getAttribute("data-help-body");
      openModal(title, function (mBody) {
        mBody.appendChild(el("p", "", body));
      });
    });
  });

  document.querySelectorAll("[data-cam]").forEach(function (tab) {
    tab.addEventListener("click", async function () {
      const cam = tab.getAttribute("data-cam");
      if (!state.user || state.user.role !== "admin") {
        openModal("Ganti Kamera", function (mBody) {
          mBody.appendChild(el("p", "", "Hanya akun Admin yang bisa mengganti profil kamera yang sedang dipantau."));
        });
        return;
      }
      try {
        await apiPost("/api/camera/select", { camera_profile: cam });
        state.activeCamera = cam;
        await refreshOverview();
      } catch (err) {
        showAdminFeedback(err.message, true);
      }
    });
  });

  document.getElementById("btn-zoom-cctv").addEventListener("click", function () {
    openModal("Tampilan Kamera Diperbesar", function (mBody) {
      const img = document.createElement("img");
      img.className = "modal-img";
      img.src = "/api/stream/live?zoom=" + Date.now();
      img.alt = "Layar CCTV Diperbesar";
      mBody.appendChild(img);
    });
  });

  document.getElementById("btn-start-engine").addEventListener("click", async function () {
    const src = document.getElementById("admin-source-select").value;
    const minVal = parseFloat(document.getElementById("admin-start-min").value || "0");
    try {
      await apiPost("/api/engine/start", {
        source: src,
        start_minute: isNaN(minVal) ? 0 : minVal,
        camera_profile: state.activeCamera
      });
      showAdminFeedback("Pemantauan kamera berhasil dimulai.", false);
      state.streamAttached = false;
      await refreshOverview();
    } catch (err) {
      showAdminFeedback(err.message, true);
    }
  });

  document.getElementById("btn-stop-engine").addEventListener("click", function () {
    openModal("Konfirmasi Hentikan Pemantauan", function (mBody) {
      mBody.appendChild(el("div", "alert-box alert-warn", "Yakin ingin menghentikan pemantauan CCTV? Sistem akan mencatat kejadian berhenti dan mengirim laporan ke Telegram."));
      const row = el("div", "admin-row");
      const okBtn = el("button", "btn btn-danger", "Ya, Hentikan Sekarang");
      okBtn.type = "button";
      okBtn.addEventListener("click", async function () {
        closeModal();
        try {
          await apiPost("/api/engine/stop", {});
          showAdminFeedback("Pemantauan dihentikan dan dicatat ke log.", false);
          await refreshOverview();
        } catch (err) {
          showAdminFeedback(err.message, true);
        }
      });
      const cancelBtn = el("button", "btn btn-outline", "Batal");
      cancelBtn.type = "button";
      cancelBtn.addEventListener("click", closeModal);
      row.appendChild(okBtn);
      row.appendChild(cancelBtn);
      mBody.appendChild(row);
    });
  });

  document.getElementById("btn-sim-recovered").addEventListener("click", async function () {
    try {
      const res = await apiPost("/api/engine/simulate_incident?incident_type=recovered", {});
      showAdminFeedback(res.message || "Simulasi selesai.", false);
      await refreshOverview();
    } catch (err) {
      showAdminFeedback(err.message, true);
    }
  });

  document.getElementById("btn-sim-theft").addEventListener("click", async function () {
    try {
      const res = await apiPost("/api/engine/simulate_incident?incident_type=theft", {});
      showAdminFeedback(res.message || "Simulasi selesai.", false);
      await refreshOverview();
    } catch (err) {
      showAdminFeedback(err.message, true);
    }
  });

  document.getElementById("btn-sim-power").addEventListener("click", async function () {
    try {
      const res = await apiPost("/api/engine/simulate_power_outage?downtime_minutes=15", {});
      showAdminFeedback("Simulasi listrik pulih (" + (res.downtime || "-") + ") selesai.", false);
      await refreshOverview();
    } catch (err) {
      showAdminFeedback(err.message, true);
    }
  });

  document.getElementById("btn-date-today").addEventListener("click", function () {
    state.selectedDate = localDateStr();
    document.getElementById("date-filter").value = state.selectedDate;
    refreshOverview();
  });

  document.getElementById("btn-date-yesterday").addEventListener("click", function () {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    state.selectedDate = localDateStr(d);
    document.getElementById("date-filter").value = state.selectedDate;
    refreshOverview();
  });

  document.getElementById("date-filter").addEventListener("change", function () {
    if (this.value) {
      state.selectedDate = this.value;
      refreshOverview();
    }
  });

  document.querySelectorAll("[data-inc-filter]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll("[data-inc-filter]").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      state.incidentFilter = btn.getAttribute("data-inc-filter");
      if (state.overview) {
        const t = state.overview.live_telemetry || {};
        renderIncidents(state.overview.anomalies || [], t.recent_recoveries || []);
      }
    });
  });

  document.getElementById("truck-search").addEventListener("input", function () {
    state.searchQuery = this.value || "";
    if (state.overview) {
      renderTrips(state.overview.trips || []);
    }
  });

  document.getElementById("btn-export-csv").addEventListener("click", function () {
    window.location.href = "/api/reports/export?date=" + encodeURIComponent(state.selectedDate);
  });

  init().catch(function (err) {
    console.error(err);
  });
});
