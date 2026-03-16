/** Message in the conversation. */
export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

/** A source reference returned alongside an assistant answer. */
export interface Source {
  doc_source: string;
  chunk_text: string;
  relevance_score: number;
}

/** Shape of the POST /chat request body (genai-to-app contract). */
export interface ChatRequest {
  messages: { role: string; content: string }[];
}

/** Shape of the POST /chat response body (genai-to-app contract). */
export interface ChatResponse {
  choices: {
    message: { role: string; content: string };
    sources: Source[];
  }[];
}
