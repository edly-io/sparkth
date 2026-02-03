const API_BASE_URL = "";

async function callChatCompletion(
  messages: { role: "system" | "user" | "assistant"; content: string }[],
) {
  const res = await fetch(`${API_BASE_URL}/api/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      provider: "openai",
      model: "gpt-4",
      messages,
      temperature: 0.7,
      max_tokens: 800,
      stream: false,
      tool_choice: "auto",
      include_system_tools_message: true,
    }),
  });

  if (!res.ok) {
    throw new Error("Failed to fetch chat completion");
  }

  return res.json();
}
