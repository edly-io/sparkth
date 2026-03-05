const API_BASE_URL = "";

export interface UploadResponse {
  filename: string;
  length: number;
  text: string;
}

export async function uploadFile(formData: FormData, token?: string): Promise<UploadResponse> {
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/parser/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const json = JSON.parse(text);
      if (json.detail) detail = json.detail;
    } catch {
      // use raw text
    }
    throw new Error(detail);
  }

  return response.json();
}
