function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map(char => char.charCodeAt(0)));
}

function setAlertButtons(text, disabled = false) {
  document.querySelectorAll('#notificationButton, #notificationButtonMain, #notificationButtonHero').forEach(button => {
    if (button) { button.textContent = text; button.disabled = disabled; }
  });
}

async function enableNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    alert('Push notifications are not supported by this browser.');
    return;
  }
  if (!window.VAPID_PUBLIC_KEY) {
    alert('Push notifications are not configured on the server yet. Add your VAPID keys and restart the app.');
    return;
  }
  if (Notification.permission === 'denied') {
    alert('Notifications are blocked. Allow them in your browser site settings and try again.');
    return;
  }
  try {
    setAlertButtons('⏳ Enabling...', true);
    const registration = await navigator.serviceWorker.register('/service-worker.js');
    await navigator.serviceWorker.ready;
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') { setAlertButtons('🔔 Enable Alerts'); return; }
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(window.VAPID_PUBLIC_KEY) });
    }
    const response = await fetch('/subscribe-notifications', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(subscription) });
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.message || 'Subscription failed.');
    setAlertButtons('🔔 Alerts Enabled');
    alert('High impact alerts are enabled!');
  } catch (error) {
    console.error(error);
    setAlertButtons('🔔 Enable Alerts');
    alert('Could not enable notifications: ' + error.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('#notificationButton, #notificationButtonMain, #notificationButtonHero').forEach(button => button?.addEventListener('click', enableNotifications));
});
