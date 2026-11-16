// 서버 API 호출. 쿠키(세션)를 같은 출처로 주고받는다.
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(r: Response): Promise<T> {
  if (r.ok) return (await r.json()) as T;
  let msg = `요청을 처리하지 못했어요 (${r.status})`;
  let hasDetail = false;
  try {
    const b = await r.json();
    if (typeof b.detail === 'string') { msg = b.detail; hasDetail = true; }
    else if (Array.isArray(b.detail) && b.detail[0]?.msg) msg = '입력값을 확인해 주세요';
    else if (b.error && r.status !== 429) { msg = String(b.error); hasDetail = true; }
  } catch {
    /* 본문 없음 */
  }
  if (r.status === 429 && !hasDetail) msg = '요청이 너무 많아요. 잠시 뒤 다시 시도해 주세요';
  // 세션이 끝났으면 앱 전체에 알려 로그인 화면으로 보낸다 (로그인 요청 자체의 실패는 제외)
  if (r.status === 401 && !r.url.includes('/auth/')) window.dispatchEvent(new Event('rc:unauthorized'));
  throw new ApiError(r.status, msg);
}

export async function get<T>(path: string): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/api/v1${path}`, { credentials: 'same-origin', cache: 'no-store' });
  } catch {
    throw new ApiError(0, '인터넷 연결을 확인해 주세요');
  }
  return handle<T>(r);
}

export async function send<T>(path: string, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown): Promise<T> {
  return handle<T>(
    await fetch(`/api/v1${path}`, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

export async function upload<T>(path: string, form: FormData): Promise<T> {
  return handle<T>(await fetch(`/api/v1${path}`, { method: 'POST', credentials: 'same-origin', body: form }));
}
