type SanitizeOptions = {
  highlightFunctionCalls?: boolean;
  normalizeWhitespace?: boolean;
};

function extractParameters(body: string): Record<string, string> {
  const paramRegex = /<parameter\s+name="([^"]+)">([\s\S]*?)<\/parameter>/gi;

  const params: Record<string, string> = {};
  let match: RegExpExecArray | null;

  while ((match = paramRegex.exec(body)) !== null) {
    const key = match[1];
    const value = match[2].trim();
    params[key] = value;
  }

  return params;
}

function extractFunctionCalls(block: string): string {
  const invokeRegex = /<invoke\s+name="([^"]+)">([\s\S]*?)<\/invoke>/gi;

  let result = "";
  let match: RegExpExecArray | null;

  while ((match = invokeRegex.exec(block)) !== null) {
    const toolName = match[1];
    const body = match[2];

    const params = extractParameters(body);

    result += `
### 🔧 MCP Tool Call: \`${toolName}\`

\`\`\`json
${JSON.stringify(params, null, 2)}
\`\`\`
`;
  }

  return result;
}

export function sanitizeAssistantMessage(
  input: string,
  options: SanitizeOptions = {},
): string {
  const { highlightFunctionCalls = true, normalizeWhitespace = true } = options;

  let output = input;

  /**
   * 1. Convert <function_calls> blocks into highlighted Markdown
   */
  if (highlightFunctionCalls) {
    output = output.replace(
      /<function_calls>([\s\S]*?)<\/function_calls>/gi,
      (_, functionBlock) => {
        return extractFunctionCalls(functionBlock);
      },
    );
  }

  /**
   * 2. Cleanup any remaining tags (safety net)
   */
  output = output
    .replace(/<\/?invoke[^>]*>/gi, "")
    .replace(/<\/?parameter[^>]*>/gi, "");

  /**
   * 3. Normalize headings
   */
  output = output.replace(/^([A-Z][A-Za-z\s]+):$/gm, "## $1");

  /**
   * 4. Normalize whitespace
   */
  if (normalizeWhitespace) {
    output = output.replace(/\n{3,}/g, "\n\n").trim();
  }

  return output;
}
