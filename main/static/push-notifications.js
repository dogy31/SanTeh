/**
 * Push Notifications Utility
 * Shared functions for browser push notifications across all templates
 */

// Request notification permission from browser
function requestNotificationPermission() {
    if ('Notification' in window) {
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    console.log('Разрешение на уведомления получено');
                }
            });
        }
    }
}

// Show browser push notification
function showBrowserNotification(title, text) {
    if ('Notification' in window && Notification.permission === 'granted') {
        try {
            new Notification(title, {
                body: text,
                icon: '/static/logo.png',
                badge: '/static/logo.png',
                tag: 'santech-notification',
                requireInteraction: true
            });
        } catch(e) {
            console.error('Ошибка создания уведомления:', e);
            if (window.showAppAlert) window.showAppAlert(`${title}\n${text}`);
            else alert(`${title}\n${text}`);
        }
    } else if ('Notification' in window) {
        if (window.showAppAlert) window.showAppAlert(`${title}\n${text}`);
        else alert(`${title}\n${text}`);
    }
}

// Get VAPID public key from server
async function getVapidPublicKey() {
    try {
        const response = await fetch('/api/push/vapid_public_key/');
        if (!response.ok) {
            console.warn('Не удалось получить VAPID ключ');
            return null;
        }
        const data = await response.json();
        return data.publicKey;
    } catch (e) {
        console.error('Ошибка получения VAPID ключа:', e);
        return null;
    }
}

// Convert base64 URL-safe string to Uint8Array
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Send subscription to server for storing
async function sendSubscriptionToServer(subscription) {
    try {
        const response = await fetch('/api/push/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify(subscription.toJSON())
        });
        if (!response.ok) {
            console.warn('Ошибка отправки подписки на сервер');
        }
    } catch (e) {
        console.error('Ошибка отсылки подписки:', e);
    }
}

// Subscribe to push notifications
async function subscribePush(registration) {
    if (!registration || !registration.pushManager) {
        return;
    }

    if (Notification.permission !== 'granted') {
        await Notification.requestPermission();
    }
    if (Notification.permission !== 'granted') {
        return;
    }

    const vapidPublicKey = await getVapidPublicKey();
    if (!vapidPublicKey) {
        return;
    }

    const existingSubscription = await registration.pushManager.getSubscription();
    if (existingSubscription) {
        await sendSubscriptionToServer(existingSubscription);
        return;
    }

    try {
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
        });
        await sendSubscriptionToServer(subscription);
        console.log('Push подписка оформлена');
    } catch (err) {
        console.error('Ошибка подписки на push:', err);
    }
}

// Initialize push notifications
async function initializePushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        return;
    }

    try {
        const registration = await navigator.serviceWorker.register('/service-worker.js');
        if (registration) {
            await subscribePush(registration);
        }
    } catch (e) {
        console.error('Ошибка регистрации service worker:', e);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    requestNotificationPermission();
});

// Make available globally
window.showBrowserNotification = showBrowserNotification;
window.initializePushNotifications = initializePushNotifications;
