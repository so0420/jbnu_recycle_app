// 사진 축소와 위치 가져오기 (웹·앱 공통 표준 API)

export async function shrinkPhoto(file: File, edge = 1280, quality = 0.85): Promise<Blob> {
  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    bmp = await createImageBitmap(file);
  }
  const scale = Math.min(1, edge / Math.max(bmp.width, bmp.height));
  const w = Math.round(bmp.width * scale);
  const h = Math.round(bmp.height * scale);
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('사진을 처리할 수 없어요');
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close();
  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('사진을 처리할 수 없어요'))), 'image/jpeg', quality),
  );
}

export interface Fix {
  lat: number;
  lng: number;
  accuracy: number;
}

export function getPosition(timeoutMs = 15000): Promise<Fix> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new Error('이 기기에서는 위치를 쓸 수 없어요'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
      (e) => {
        if (e.code === e.PERMISSION_DENIED) reject(new Error('위치 권한을 허용해 주세요 (설정 → 앱 → 권한)'));
        else if (e.code === e.TIMEOUT) reject(new Error('위치를 찾는 데 시간이 걸려요. 밖으로 나와 다시 시도해 주세요'));
        else reject(new Error('위치를 가져오지 못했어요'));
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 10000 },
    );
  });
}

export function uuid(): string {
  if (crypto.randomUUID) return crypto.randomUUID().replace(/-/g, '');
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
}
