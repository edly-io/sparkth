import { api, ApiRequestError } from "@/lib/api";

// The parser route has no response_model, so the generated 200 type is
// unknown; this interface documents the dict the backend actually returns.
export interface UploadResponse {
  filename: string;
  length: number;
  text: string;
}

export async function uploadFile(formData: FormData, token?: string): Promise<UploadResponse> {
  try {
    const { data } = await api.POST("/api/v1/parser/upload", {
      body: { file: "" },
      bodySerializer: () => formData,
      // Content-Type must stay unset so fetch adds the multipart boundary.
      headers: {
        "Content-Type": null,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    return data as UploadResponse;
  } catch (error) {
    // This module's contract: plain Error carrying the bare backend detail;
    // network failures propagate untouched.
    if (error instanceof ApiRequestError) throw new Error(error.message);
    throw error;
  }
}
