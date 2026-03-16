import type { ChatRequest, ChatResponse } from "./types";

const CHAT_URL = "/chat";

/**
 * Send a chat request to the backend.
 *
 * The request and response shapes match the genai-to-app contract.
 */
export async function sendChatMessage(
  request: ChatRequest
): Promise<ChatResponse> {
  const response = await fetch(CHAT_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Chat request failed (${response.status}): ${detail}`);
  }

  return response.json();
}
