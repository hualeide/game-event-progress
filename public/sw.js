/* 自清理：卸掉旧 SW + 清 Cache，避免改前端后刷不出来 */
self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.registration.unregister())
      .then(() => self.clients.claim())
  );
});

// 不再拦截任何请求
self.addEventListener("fetch", () => {});
