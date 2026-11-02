import { api, ApiRequestError, bearer, type Schema } from "@/lib/api";

export type UploadResponse = Schema<"UploadResponse">;

export async function uploadFile(formData: FormData, token?: string): Promise<UploadResponse> {
  try {
    const { data } = await api.POST("/api/v1/parser/upload", {
      body: { file: "" },
      bodySerializer: () => formData,
      // Content-Type must stay unset so fetch adds the multipart boundary.
      headers: {
        "Content-Type": null,
        ...(token ? bearer(token) : {}),
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
