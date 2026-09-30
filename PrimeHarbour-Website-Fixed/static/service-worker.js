self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'PrimePair Alert';
  const options = { body: data.body || 'New market update available.', tag: data.tag || 'primepair-alert', data: { url: data.url || '/news' } };
  event.waitUntil(self.registration.showNotification(title, options));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data?.url || '/news'));
});
