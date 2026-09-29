/**
 * EZ-Downloader Frontend Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // DOM Elements
  const urlInput = document.getElementById("urlInput");
  const btnPaste = document.getElementById("btnPaste");
  const btnClear = document.getElementById("btnClear");
  const downloadForm = document.getElementById("downloadForm");
  const btnSubmit = document.getElementById("btnSubmit");
  
  const loadingState = document.getElementById("loadingState");
  const errorAlert = document.getElementById("errorAlert");
  const errorMessage = document.getElementById("errorMessage");
  const btnErrorCookieHelp = document.getElementById("btnErrorCookieHelp");
  
  const resultContainer = document.getElementById("resultContainer");
  const videoPreviewWrapper = document.getElementById("videoPreviewWrapper");
  const videoPlayer = document.getElementById("videoPlayer");
  const photoPreviewWrapper = document.getElementById("photoPreviewWrapper");
  const carouselMainImg = document.getElementById("carouselMainImg");
  const btnPrevSlide = document.getElementById("btnPrevSlide");
  const btnNextSlide = document.getElementById("btnNextSlide");
  const slideCurrent = document.getElementById("slideCurrent");
  const slideTotal = document.getElementById("slideTotal");
  const thumbStrip = document.getElementById("thumbStrip");
  
  const audioPlayerCard = document.getElementById("audioPlayerCard");
  const audioPlayer = document.getElementById("audioPlayer");
  const audioTitle = document.getElementById("audioTitle");
  const audioAuthor = document.getElementById("audioAuthor");
  
  const authorAvatar = document.getElementById("authorAvatar");
  const authorNickname = document.getElementById("authorNickname");
  const authorHandle = document.getElementById("authorHandle");
  const platformBadge = document.getElementById("platformBadge");
  const postTitle = document.getElementById("postTitle");
  
  const statLikes = document.getElementById("statLikes");
  const statComments = document.getElementById("statComments");
  const statCollects = document.getElementById("statCollects");
  const statShares = document.getElementById("statShares");
  
  const videoOptionsGroup = document.getElementById("videoOptionsGroup");
  const videoButtons = document.getElementById("videoButtons");
  const photoOptionsGroup = document.getElementById("photoOptionsGroup");
  const btnDownloadSlideshowVideo = document.getElementById("btnDownloadSlideshowVideo");
  const btnCarouselQuickDownload = document.getElementById("btnCarouselQuickDownload");
  const btnDownloadCurrentPhoto = document.getElementById("btnDownloadCurrentPhoto");
  const labelCurrentPhoto = document.getElementById("labelCurrentPhoto");
  const btnDownloadAllZip = document.getElementById("btnDownloadAllZip");
  const badgeZipCount = document.getElementById("badgeZipCount");
  const btnSaveAlbumLocal = document.getElementById("btnSaveAlbumLocal");
  const photoGrid = document.getElementById("photoGrid");
  const photoGridCount = document.getElementById("photoGridCount");
  const audioOptionRow = document.getElementById("audioOptionRow");
  const btnDownloadAudio = document.getElementById("btnDownloadAudio");
  const audioButtonLabel = document.getElementById("audioButtonLabel");
  const coverOptionRow = document.getElementById("coverOptionRow");
  const btnDownloadCover = document.getElementById("btnDownloadCover");
  
  const btnOpenFolder = document.getElementById("btnOpenFolder");
  const btnOpenSettings = document.getElementById("btnOpenSettings");
  const settingsModal = document.getElementById("settingsModal");
  const btnCloseSettings = document.getElementById("btnCloseSettings");
  const cookieInput = document.getElementById("cookieInput");
  const btnSaveCookie = document.getElementById("btnSaveCookie");
  const downloadsPathDisplay = document.getElementById("downloadsPathDisplay");
  const btnModalOpenFolder = document.getElementById("btnModalOpenFolder");
  
  const historySection = document.getElementById("historySection");
  const historyList = document.getElementById("historyList");
  const btnClearHistory = document.getElementById("btnClearHistory");

  // State
  let currentMedia = null;
  let currentSlideIndex = 0;

  // Load saved cookie
  const savedCookie = localStorage.getItem("ez_user_cookie") || "";
  cookieInput.value = savedCookie;

  // Load download path
  fetch("/api/downloads-path")
    .then(r => r.json())
    .then(data => {
      if (data.path) {
        downloadsPathDisplay.value = data.path;
      }
    })
    .catch(() => {});

  // Telegram WebApp Integration
  const tg = window.Telegram?.WebApp;
  const tgBadge = document.getElementById("tgBadge");
  const telegramActionGroup = document.getElementById("telegramActionGroup");
  const btnSendToChat = document.getElementById("btnSendToChat");
  const labelSendToChat = document.getElementById("labelSendToChat");
  let tgUserId = null;

  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tgBadge) tgBadge.classList.remove("hidden");

      if (tg.initDataUnsafe?.user?.id) {
        tgUserId = tg.initDataUnsafe.user.id;
        if (telegramActionGroup) telegramActionGroup.classList.remove("hidden");
      }

      // Check incoming URL from query parameters (?url=... or ?link=...) or start_param
      const urlParams = new URLSearchParams(window.location.search);
      let startUrl = urlParams.get("url") || urlParams.get("link");
      if (!startUrl && tg.initDataUnsafe?.start_param) {
        startUrl = tg.initDataUnsafe.start_param;
      }
      if (startUrl) {
        urlInput.value = decodeURIComponent(startUrl);
        btnClear.classList.remove("hidden");
        setTimeout(() => {
          downloadForm.dispatchEvent(new Event("submit"));
        }, 300);
      }
    } catch (e) {
      console.warn("Telegram WebApp initialization error:", e);
    }
  }

  // Handle Telegram Send to Chat button
  if (btnSendToChat) {
    btnSendToChat.addEventListener("click", async () => {
      const activeUrl = urlInput.value.trim();
      if (!activeUrl) {
        showToast("Please enter a TikTok or Douyin link first.", "warning");
        return;
      }

      const userIdToSend = tgUserId || tg?.initDataUnsafe?.user?.id;
      if (!userIdToSend) {
        showToast("Telegram user ID not detected. Please open within Telegram.", "warning");
        return;
      }

      const originalBtnText = labelSendToChat ? labelSendToChat.textContent : "Send to Chat";
      if (labelSendToChat) labelSendToChat.textContent = "Sending to your Telegram chat...";
      btnSendToChat.disabled = true;
      showToast("Sending media directly to your Telegram chat...", "info");

      try {
        const res = await fetch("/api/telegram/send-to-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: userIdToSend,
            url: activeUrl
          })
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
          throw new Error(data.detail || data.error || "Failed to send to Telegram chat.");
        }

        showToast("Media sent to your Telegram chat! Check your messages.", "success");
        if (tg?.HapticFeedback) {
          tg.HapticFeedback.notificationOccurred("success");
        }
      } catch (err) {
        showToast("Telegram Chat: " + err.message, "error");
        if (tg?.HapticFeedback) {
          tg.HapticFeedback.notificationOccurred("error");
        }
      } finally {
        if (labelSendToChat) labelSendToChat.textContent = originalBtnText;
        btnSendToChat.disabled = false;
      }
    });
  }

  // Load download history
  renderHistory();

  // Input change / clear handlers
  urlInput.addEventListener("input", () => {
    btnClear.classList.toggle("hidden", !urlInput.value);
  });

  btnClear.addEventListener("click", () => {
    urlInput.value = "";
    btnClear.classList.add("hidden");
    urlInput.focus();
  });

  // Paste from clipboard
  btnPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        btnClear.classList.remove("hidden");
        showToast("Link pasted from clipboard!", "info");
      }
    } catch (err) {
      showToast("Unable to access clipboard. Please paste manually (Ctrl+V).", "warning");
    }
  });

  // Open Downloads Folder
  const openFolderHandler = async () => {
    try {
      const res = await fetch("/api/open-folder", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast("Opened downloads directory!", "success");
      } else {
        showToast("Error opening folder: " + (data.error || "Unknown"), "warning");
      }
    } catch (err) {
      showToast("Could not open folder: " + err, "error");
    }
  };

  btnOpenFolder.addEventListener("click", openFolderHandler);
  btnModalOpenFolder.addEventListener("click", openFolderHandler);

  // Settings Modal
  btnOpenSettings.addEventListener("click", () => {
    settingsModal.classList.remove("hidden");
  });

  btnCloseSettings.addEventListener("click", () => {
    settingsModal.classList.add("hidden");
  });

  settingsModal.addEventListener("click", (e) => {
    if (e.target === settingsModal) {
      settingsModal.classList.add("hidden");
    }
  });

  btnSaveCookie.addEventListener("click", () => {
    const val = cookieInput.value.trim();
    localStorage.setItem("ez_user_cookie", val);
    settingsModal.classList.add("hidden");
    showToast("Settings and Cookies saved!", "success");
  });

  btnErrorCookieHelp.addEventListener("click", () => {
    settingsModal.classList.remove("hidden");
  });

  // Form Submit: Analyze Link
  downloadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    // Reset UI
    hideError();
    resultContainer.classList.add("hidden");
    loadingState.classList.remove("hidden");
    btnSubmit.disabled = true;

    try {
      const activeCookie = localStorage.getItem("ez_user_cookie") || "";
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, cookie: activeCookie })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Failed to analyze URL.");
      }

      currentMedia = data.data;
      renderResult(currentMedia);
      saveToHistory(currentMedia);
    } catch (err) {
      showError(err.message);
    } finally {
      loadingState.classList.add("hidden");
      btnSubmit.disabled = false;
    }
  });

  // Render Result Card
  function renderResult(media) {
    resultContainer.classList.remove("hidden");

    // Platform Badge
    const isDouyin = media.platform === "douyin";
    platformBadge.textContent = isDouyin ? "Douyin (抖音)" : "TikTok";
    platformBadge.className = isDouyin
      ? "text-[10px] font-bold px-2 py-0.5 rounded-full badge-douyin"
      : "text-[10px] font-bold px-2 py-0.5 rounded-full badge-tiktok";

    // Author
    authorNickname.textContent = media.author.nickname || (isDouyin ? "Douyin User" : "TikTok User");
    authorHandle.textContent = media.author.unique_id ? `@${media.author.unique_id}` : "";
    authorAvatar.src = media.author.avatar || "/static/avatar_default.svg";
    authorAvatar.onerror = () => { authorAvatar.src = "/static/avatar_default.svg"; };

    // Post Content
    postTitle.textContent = media.title || "No description provided.";

    // Statistics
    statLikes.textContent = formatNumber(media.stats.digg_count);
    statComments.textContent = formatNumber(media.stats.comment_count);
    statCollects.textContent = formatNumber(media.stats.share_count || 0);
    statShares.textContent = formatNumber(media.stats.play_count || 0);

    // Media Preview Handling
    if (telegramActionGroup && (tgUserId || window.Telegram?.WebApp?.initDataUnsafe?.user?.id)) {
      telegramActionGroup.classList.remove("hidden");
    }

    if (media.type === "photo" && media.images && media.images.length > 0) {
      // Photo Mode
      videoPreviewWrapper.classList.add("hidden");
      photoPreviewWrapper.classList.remove("hidden");
      videoOptionsGroup.classList.add("hidden");
      photoOptionsGroup.classList.remove("hidden");

      currentSlideIndex = 0;
      slideTotal.textContent = media.images.length;
      setupCarousel(media.images);
    } else {
      // Video Mode
      photoPreviewWrapper.classList.add("hidden");
      videoPreviewWrapper.classList.remove("hidden");
      photoOptionsGroup.classList.add("hidden");
      videoOptionsGroup.classList.remove("hidden");

      // Setup Video Player
      if (media.videos && media.videos.length > 0) {
        const streamUrl = media.videos[0].url;
        videoPlayer.src = streamUrl;
        videoPlayer.poster = media.cover || "";
        videoPlayer.load();
      }

      // Render Video Download Buttons
      renderVideoButtons(media);
    }

    // Audio Player
    if (media.music && media.music.play_url) {
      audioPlayerCard.classList.remove("hidden");
      audioOptionRow.classList.remove("hidden");
      audioTitle.textContent = media.music.title || "Original Audio Track";
      audioAuthor.textContent = media.music.author || media.author.nickname || "Artist";
      
      // Use proxied stream to guarantee browser audio playback regardless of CDN hotlink protection
      const safeAudioName = `${cleanFilename(media.music.title || media.title || "audio")}.mp3`;
      audioPlayer.src = `/api/download?url=${encodeURIComponent(media.music.play_url)}&filename=${encodeURIComponent(safeAudioName)}`;
      audioPlayer.load();
      audioButtonLabel.textContent = `Download Audio Track (${media.music.title ? media.music.title.slice(0, 30) : "MP3"})`;

      btnDownloadAudio.onclick = () => {
        triggerDownload(media.music.play_url, safeAudioName);
      };
    } else {
      audioPlayerCard.classList.add("hidden");
      audioOptionRow.classList.add("hidden");
    }

    // Cover Image Option
    if (media.cover) {
      coverOptionRow.classList.remove("hidden");
      btnDownloadCover.onclick = () => {
        triggerDownload(
          media.cover,
          `${cleanFilename(media.title || "cover")}_cover.jpg`
        );
      };
    } else {
      coverOptionRow.classList.add("hidden");
    }

    // Refresh icons
    if (window.lucide) lucide.createIcons();

    // Scroll to results
    resultContainer.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Render Video Download Options
  function renderVideoButtons(media) {
    videoButtons.innerHTML = "";

    if (!media.videos || media.videos.length === 0) {
      videoButtons.innerHTML = `<p class="text-xs text-amber-400">No direct stream options found.</p>`;
      return;
    }

    media.videos.forEach((vid, idx) => {
      const isPrimary = idx === 0;
      const btn = document.createElement("button");
      btn.className = isPrimary
        ? "gradient-btn w-full py-3 px-4 rounded-xl text-white font-semibold text-sm flex items-center justify-between shadow-lg"
        : "w-full py-2.5 px-4 bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-200 hover:text-white font-medium text-sm rounded-xl flex items-center justify-between transition";

      const safeTitle = cleanFilename(media.title || "video");
      const filename = `${safeTitle}_${vid.quality}.mp4`;

      btn.innerHTML = `
        <div class="flex items-center gap-2">
          <i data-lucide="${isPrimary ? 'sparkles' : 'download'}" class="w-4 h-4 ${isPrimary ? 'text-white' : 'text-cyan-400'}"></i>
          <span>${vid.label || 'Download Video'}</span>
        </div>
        <span class="text-xs font-mono opacity-80">${vid.quality}</span>
      `;

      btn.onclick = () => triggerDownload(vid.url, filename);
      videoButtons.appendChild(btn);
    });
  }

  // Download Single Photo helper
  function downloadSinglePhoto(idx, images) {
    if (!images || !images[idx]) return;
    const url = images[idx];
    const safeTitle = cleanFilename(currentMedia?.title || "photo");
    const num = (idx + 1).toString().padStart(2, "0");
    const filename = `${safeTitle}_photo_${num}.jpg`;
    triggerDownload(url, filename);
  }

  // Setup Carousel & Photo Grid for Photo Albums
  function setupCarousel(images) {
    carouselMainImg.src = images[0];
    slideCurrent.textContent = "1";
    slideTotal.textContent = images.length.toString();
    thumbStrip.innerHTML = "";
    if (photoGrid) photoGrid.innerHTML = "";
    if (photoGridCount) photoGridCount.textContent = images.length.toString();
    if (badgeZipCount) badgeZipCount.textContent = `${images.length} Photos`;

    // Update label on current photo button
    if (labelCurrentPhoto) {
      labelCurrentPhoto.textContent = `Download Current Photo (#1)`;
    }

    // Thumbnail Strip below carousel
    images.forEach((imgUrl, i) => {
      const thumb = document.createElement("img");
      thumb.src = imgUrl;
      thumb.className = `w-14 h-14 rounded-lg object-cover cursor-pointer border-2 transition flex-shrink-0 ${
        i === 0 ? "border-pink-500 scale-105" : "border-slate-700 opacity-60 hover:opacity-100"
      }`;
      thumb.onclick = () => selectSlide(i, images);
      thumbStrip.appendChild(thumb);
    });

    // Populate Photo Grid with individual download actions
    if (photoGrid) {
      images.forEach((imgUrl, i) => {
        const item = document.createElement("div");
        item.className = "relative group rounded-lg overflow-hidden border border-slate-700 aspect-square bg-slate-900 cursor-pointer";
        item.innerHTML = `
          <img src="${imgUrl}" class="w-full h-full object-cover group-hover:scale-105 transition">
          <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
            <span class="p-1.5 bg-pink-500 rounded-full text-white shadow"><i data-lucide="download" class="w-3.5 h-3.5"></i></span>
          </div>
          <span class="absolute top-1 left-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-black/70 text-white font-bold">#${i + 1}</span>
        `;
        item.onclick = () => {
          selectSlide(i, images);
          downloadSinglePhoto(i, images);
        };
        photoGrid.appendChild(item);
      });
    }

    // Prev / Next Buttons
    btnPrevSlide.onclick = () => {
      const newIdx = (currentSlideIndex - 1 + images.length) % images.length;
      selectSlide(newIdx, images);
    };

    btnNextSlide.onclick = () => {
      const newIdx = (currentSlideIndex + 1) % images.length;
      selectSlide(newIdx, images);
    };

    // Download Photo with Song (MP4 Video Slideshow)
    if (btnDownloadSlideshowVideo) {
      btnDownloadSlideshowVideo.onclick = () => {
        downloadSlideshowVideo(images, currentMedia?.music?.play_url, currentMedia?.title || "slideshow");
      };
    }

    // Quick download icon on top of carousel
    if (btnCarouselQuickDownload) {
      btnCarouselQuickDownload.onclick = () => downloadSinglePhoto(currentSlideIndex, images);
    }

    // Download Current Photo Button
    if (btnDownloadCurrentPhoto) {
      btnDownloadCurrentPhoto.onclick = () => downloadSinglePhoto(currentSlideIndex, images);
    }

    // Download All as ZIP
    btnDownloadAllZip.onclick = () => {
      downloadZipArchive(images, currentMedia?.title || "photo_album");
    };

    // Save All to PC Downloads Folder directly
    if (btnSaveAlbumLocal) {
      btnSaveAlbumLocal.onclick = () => {
        saveAlbumLocally(images, currentMedia?.title || "photo_album");
      };
    }

    if (window.lucide) lucide.createIcons();
  }

  function selectSlide(idx, images) {
    currentSlideIndex = idx;
    carouselMainImg.src = images[idx];
    slideCurrent.textContent = (idx + 1).toString();
    if (labelCurrentPhoto) {
      labelCurrentPhoto.textContent = `Download Current Photo (#${idx + 1})`;
    }

    // Update thumb styles
    const thumbs = thumbStrip.querySelectorAll("img");
    thumbs.forEach((t, i) => {
      if (i === idx) {
        t.className = "w-14 h-14 rounded-lg object-cover cursor-pointer border-2 border-pink-500 scale-105 transition flex-shrink-0";
        t.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
      } else {
        t.className = "w-14 h-14 rounded-lg object-cover cursor-pointer border-2 border-slate-700 opacity-60 hover:opacity-100 transition flex-shrink-0";
      }
    });
  }

  // Trigger Download via Backend Streaming Endpoint
  function triggerDownload(url, filename) {
    if (!url) {
      showToast("Download URL is not available.", "error");
      return;
    }
    showToast(`Starting download: ${filename}`, "info");

    const dlUrl = `/api/download?url=${encodeURIComponent(url)}&filename=${encodeURIComponent(filename)}`;
    const fullUrl = window.location.origin + dlUrl;

    // Telegram in-app WebView suppresses standard <a> downloads; delegate to system browser
    if (window.Telegram?.WebApp && typeof window.Telegram.WebApp.openLink === "function") {
      showToast("Opening download in your device browser...", "info");
      window.Telegram.WebApp.openLink(fullUrl);
      return;
    }

    const a = document.createElement("a");
    a.href = dlUrl;
    a.download = filename;
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Download Image Album ZIP
  async function downloadZipArchive(images, title) {
    showToast(`Preparing ZIP with ${images.length} photos...`, "info");
    try {
      const res = await fetch("/api/download/zip-prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images, title })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Failed to prepare ZIP archive.");
      }

      const fullZipUrl = window.location.origin + data.download_url;

      // In Telegram WebApp: delegate to system browser
      if (window.Telegram?.WebApp && typeof window.Telegram.WebApp.openLink === "function") {
        showToast("Opening ZIP download in your device browser...", "info");
        window.Telegram.WebApp.openLink(fullZipUrl);
        return;
      }

      // Standard browser: trigger direct download
      const a = document.createElement("a");
      a.href = data.download_url;
      a.download = `${cleanFilename(title)}_photos.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showToast("Photos ZIP downloading...", "success");
    } catch (err) {
      showToast("Error creating ZIP: " + err.message, "error");
    }
  }

  // Download Photo with Song (MP4 Slideshow Video)
  async function downloadSlideshowVideo(images, audioUrl, title) {
    if (!images || images.length === 0) {
      showToast("No photos found to create video.", "error");
      return;
    }

    showToast("Rendering Photo with Song video (takes ~3-5s)...", "info");
    try {
      const res = await fetch("/api/download/slideshow-prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          images: images,
          audio_url: audioUrl || null,
          title: title
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Failed to prepare slideshow video.");
      }

      const fullUrl = window.location.origin + data.download_url;

      // In Telegram WebApp: delegate to system browser
      if (window.Telegram?.WebApp && typeof window.Telegram.WebApp.openLink === "function") {
        showToast("Opening slideshow video in your device browser...", "info");
        window.Telegram.WebApp.openLink(fullUrl);
        return;
      }

      // Standard browser: trigger direct download
      const a = document.createElement("a");
      a.href = data.download_url;
      a.download = `${cleanFilename(title)}_slideshow.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showToast("Photo with Song video downloading!", "success");
    } catch (err) {
      showToast("Error generating video: " + err.message, "error");
    }
  }

  // Save All Images Directly to PC Downloads Directory
  async function saveAlbumLocally(images, title) {
    showToast("Saving all photos to PC Downloads folder...", "info");
    try {
      const res = await fetch("/api/download/local-album", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images, title })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.detail || "Failed to save photos locally.");
      }
      showToast(`Saved ${data.count} photos to: ${data.folder_name}!`, "success");
    } catch (err) {
      showToast("Error saving photos locally: " + err.message, "error");
    }
  }

  // Error Presentation
  function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.classList.remove("hidden");
    if (msg.toLowerCase().includes("douyin") || msg.toLowerCase().includes("cookie")) {
      btnErrorCookieHelp.classList.remove("hidden");
    } else {
      btnErrorCookieHelp.classList.add("hidden");
    }
    if (window.lucide) lucide.createIcons();
  }

  function hideError() {
    errorAlert.classList.add("hidden");
    errorMessage.textContent = "";
  }

  // Toast Notification System
  function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");

    let borderClass = "border-cyan-500/40 text-cyan-200 bg-slate-900/95";
    let iconName = "info";

    if (type === "success") {
      borderClass = "border-emerald-500/40 text-emerald-200 bg-slate-900/95";
      iconName = "check-circle-2";
    } else if (type === "error") {
      borderClass = "border-rose-500/40 text-rose-200 bg-slate-900/95";
      iconName = "alert-circle";
    } else if (type === "warning") {
      borderClass = "border-amber-500/40 text-amber-200 bg-slate-900/95";
      iconName = "alert-triangle";
    }

    toast.className = `pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-md text-xs font-medium transition-all duration-300 transform translate-y-4 opacity-0 ${borderClass}`;
    toast.innerHTML = `<i data-lucide="${iconName}" class="w-4 h-4 flex-shrink-0"></i><span>${message}</span>`;
    container.appendChild(toast);

    if (window.lucide) lucide.createIcons();

    requestAnimationFrame(() => {
      toast.classList.remove("translate-y-4", "opacity-0");
    });

    setTimeout(() => {
      toast.classList.add("translate-y-4", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Utilities
  function formatNumber(num) {
    if (!num) return "0";
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num.toString();
  }

  function cleanFilename(str) {
    return (str || "media")
      .replace(/[\\/*?:"<>|#\n\r]/g, "")
      .replace(/\s+/g, "_")
      .slice(0, 45);
  }

  // History Management
  function saveToHistory(media) {
    let history = [];
    try {
      history = JSON.parse(localStorage.getItem("ez_history") || "[]");
    } catch {}
    
    // Deduplicate
    history = history.filter(h => h.id !== media.id);
    history.unshift({
      id: media.id,
      title: media.title,
      platform: media.platform,
      author: media.author.nickname,
      cover: media.cover,
      type: media.type,
      url: media.url,
      timestamp: Date.now()
    });

    if (history.length > 8) history.pop();
    localStorage.setItem("ez_history", JSON.stringify(history));
    renderHistory();
  }

  function renderHistory() {
    let history = [];
    try {
      history = JSON.parse(localStorage.getItem("ez_history") || "[]");
    } catch {}

    if (history.length === 0) {
      historySection.classList.add("hidden");
      return;
    }

    historySection.classList.remove("hidden");
    historyList.innerHTML = "";

    history.forEach(item => {
      const row = document.createElement("div");
      row.className = "p-3 rounded-xl bg-slate-800/40 hover:bg-slate-800 border border-slate-700/40 flex items-center justify-between gap-3 transition cursor-pointer";
      row.innerHTML = `
        <div class="flex items-center gap-3 min-w-0">
          <img src="${item.cover || '/static/avatar_default.svg'}" class="w-10 h-10 rounded-lg object-cover bg-slate-900 border border-slate-700">
          <div class="min-w-0">
            <p class="text-xs font-bold text-white truncate">${item.title || 'Media Post'}</p>
            <p class="text-[11px] text-slate-400 truncate">@${item.author} &bull; <span class="uppercase">${item.platform}</span></p>
          </div>
        </div>
        <button class="px-2.5 py-1.5 rounded-lg bg-pink-500/20 text-pink-400 hover:bg-pink-500 hover:text-white text-xs font-semibold flex items-center gap-1 transition">
          <i data-lucide="refresh-cw" class="w-3 h-3"></i> Load
        </button>
      `;

      row.onclick = () => {
        urlInput.value = item.url;
        btnClear.classList.remove("hidden");
        downloadForm.dispatchEvent(new Event("submit"));
      };

      historyList.appendChild(row);
    });

    if (window.lucide) lucide.createIcons();
  }

  btnClearHistory.addEventListener("click", () => {
    localStorage.removeItem("ez_history");
    renderHistory();
    showToast("History cleared!", "info");
  });
});
