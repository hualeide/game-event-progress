export const $ = (sel, root = document) => root.querySelector(sel);

/** ?soonHours=24 鍙皟銆屽嵆灏嗙粨鏉熴€嶉槇鍊硷紙榛樿 24 灏忔椂鍐咃級 */
export function soonHours() {
  const n = Number(new URLSearchParams(location.search).get("soonHours"));
  return Number.isFinite(n) && n > 0 ? n : 24;
}

export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function fmtDate(iso) {
  if (!iso) return "?";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "?";
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${m}/${day} ${h}:${min}`;
}

const rtf =
  typeof Intl !== "undefined" && Intl.RelativeTimeFormat
    ? new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" })
    : null;

/** 鐩稿鏃堕棿锛氫紭鍏?Intl锛屽洖閫€鎵嬪啓 */
export function fmtRelative(ms) {
  const sec = Math.round(ms / 1000);
  const abs = Math.abs(sec);
  if (rtf) {
    if (abs < 60) return rtf.format(Math.round(sec), "second");
    if (abs < 3600) return rtf.format(Math.round(sec / 60), "minute");
    if (abs < 86400) return rtf.format(Math.round(sec / 3600), "hour");
    if (abs < 86400 * 30) return rtf.format(Math.round(sec / 86400), "day");
    return rtf.format(Math.round(sec / (86400 * 30)), "month");
  }
  const days = Math.floor(abs / 86400);
  const hours = Math.floor((abs % 86400) / 3600);
  if (sec >= 0) {
    if (days > 0) return hours ? `${days}澶?{hours}鏃跺悗` : `${days}澶╁悗`;
    if (hours > 0) return `${hours}灏忔椂鍚巂;
    return "鍗冲皢寮€濮?;
  }
  const left = -sec;
  const d2 = Math.floor(left / 86400);
  const h2 = Math.floor((left % 86400) / 3600);
  if (d2 > 0) return h2 ? `${d2}澶?{h2}鏃禶 : `${d2}澶ー;
  if (h2 > 0) return `${h2}灏忔椂`;
  return "灏嗙粨鏉?;
}

export function fmtUpdated(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  const abs = `${m}/${day} ${h}:${min}`;
  const delta = d.getTime() - Date.now();
  const rel = fmtRelative(delta);
  if (Math.abs(delta) < 86400000 * 2) return `${abs} 路 ${rel}`;
  return abs;
}

export function endingSoon(ev, hours = soonHours()) {
  if (!ev?.end) return false;
  const left = new Date(ev.end).getTime() - Date.now();
  return left > 0 && left <= hours * 3600 * 1000;
}

export function adaptCover(img) {
  const cover = img?.closest?.(".cover");
  const card = img?.closest?.(".card");
  if (!cover || !card || !img.naturalWidth) return;
  const r = img.naturalWidth / img.naturalHeight;
  let kind = "std";
  let ar = "16 / 9";
  if (r >= 2.0) {
    kind = "wide";
    ar = "16 / 9";
  } else if (r <= 1.1) {
    kind = "square";
    ar = "1 / 1";
  } else if (r < 1.5) {
    kind = "tall";
    ar = "4 / 3";
  }
  card.dataset.ratio = kind;
  cover.style.aspectRatio = ar;
}

// 鍐呰仈 onload 鍥炶皟
window.adaptCover = adaptCover;


