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
  try {
    const b = await r.json();
    if (typeof b.detail === 'string') msg = b.detail;
    else if (Array.isArray(b.detail) && b.detail[0]?.msg) msg = '입력값을 확인해 주세요';
    else if (b.error) msg = String(b.error);
  } catch {
    /* 본문 없음 */
  }
  if (r.status === 429) msg = '요청이 너무 많아요. 잠시 뒤 다시 시도해 주세요';
  throw new ApiError(r.status, msg);
}

export async function get<T>(path: string): Promise<T> {
  return handle<T>(await fetch(`/api/v1${path}`, { credentials: 'same-origin' }));
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
