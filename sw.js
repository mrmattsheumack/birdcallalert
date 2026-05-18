// sw.js - minimal service worker for Bird Call Alert push notifications
// Purpose: enable registration.showNotification() on Chrome Android
// Does NOT do offline caching, background sync, or web push subscriptions.

const SW_VERSION = "v1.0-2026-05-18";

self.addEventListener("install", (event) => {
  // Activate this SW immediately on first install
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // Take control of all clients immediately
  event.waitUntil(self.clients.claim());
});

// When the user taps a notification, focus the app window (or open it)
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        // Focus an existing window if one is open
        for (const client of clients) {
          if ("focus" in client) return client.focus();
        }
        // Otherwise open a new window at the app root
        if (self.clients.openWindow) {
          return self.clients.openWindow("/");
        }
      })
  );
});
