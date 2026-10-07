/**
 * Client Device Fingerprint Engine (PRD Section 6: Anti-Abuse & Device Pool)
 * Generates and securely persists a client device identifier to enforce multi-account
 * daily conversion limits and abuse prevention server-side.
 */

export function getDeviceId(): string {
  if (typeof window === 'undefined') {
    return 'server-render';
  }

  const STORAGE_KEY = 'kh_device_id';
  try {
    let devId = localStorage.getItem(STORAGE_KEY);
    if (devId && devId.trim().length >= 16) {
      return devId.trim();
    }

    // Generate hardware-anchored pseudorandom fingerprint
    const screenRes = `${window.screen?.width || 0}x${window.screen?.height || 0}x${window.screen?.colorDepth || 24}`;
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'IST';
    const rand = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
    
    devId = `dev_${btoa(`${screenRes}-${tz}`).replace(/[^a-zA-Z0-9]/g, '').slice(0, 10)}_${rand.replace(/-/g, '')}`;
    localStorage.setItem(STORAGE_KEY, devId);
    return devId;
  } catch {
    return 'fallback-device-id';
  }
}

export function getDeviceHeaders(): Record<string, string> {
  const devId = getDeviceId();
  return devId ? { 'X-Device-Id': devId } : {};
}
