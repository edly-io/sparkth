const API_BASE_URL = "";

export interface UploadResponse {
  filename: string;
  length: number;
  text: string;
}

export async function uploadFile(
  token: string | null,
  formData: FormData,
): Promise<UploadResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/parser/upload`, {
    method: "POST",
    body: formData,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to parse file: ${text}`);
  }

  return response.json();
}
