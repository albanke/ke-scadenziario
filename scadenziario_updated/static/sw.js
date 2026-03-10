// KE Scadenziario — Service Worker per notifiche push persistenti
const CACHE_NAME = 'ke-sw-v1';

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});

// Gestisce le notifiche push dal server (se configurato)
self.addEventListener('push', function(event) {
  if (!event.data) return;
  var data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'KE Scadenziario', {
      body: data.body || '',
      icon: '/static/icon.png',
      badge: '/static/badge.png',
      tag: data.tag || 'ke-push',
      requireInteraction: data.critical || false,
      actions: [
        { action: 'open', title: 'Apri scadenziario' },
        { action: 'dismiss', title: 'Ignora' }
      ]
    })
  );
});

// Click sulla notifica → apre il sito
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.action === 'dismiss') return;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clients) {
      for (var i = 0; i < clients.length; i++) {
        if (clients[i].url.includes(self.location.origin)) {
          return clients[i].focus();
        }
      }
      return self.clients.openWindow('/');
    })
  );
});
