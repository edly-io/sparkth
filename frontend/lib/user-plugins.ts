const API_BASE_URL = "/api/v1";

export interface UserPlugin {
  plugin_name: string;
  enabled: boolean;
  config: Record<string, string>;
  is_core: boolean;
}

async function handleError(message: string, response: Response) {
  const text = await response.text();
  const error = `${message}: ${text}`;
  console.error(error);
  throw new Error(error);
}

export async function getUserPlugins(token: string): Promise<UserPlugin[]> {
  const response = await fetch(`${API_BASE_URL}/user-plugins/`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    await handleError("Cannot fetch user plugins", response);
  }

  return response.json();
}

export async function togglePlugin(
  plugin_name: string,
  action: string,
  token: string
): Promise<UserPlugin> {
  const res = await fetch(`/api/v1/user-plugins/${plugin_name}/${action}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    await handleError(`Failed to ${action} plugin`, res);
  }
  return await res.json();
}

export async function upsertUserPluginConfig(
  pluginName: string,
  config: Record<string, string>,
  token: string
): Promise<UserPlugin> {
  const res = await fetch(`${API_BASE_URL}/user-plugins/${pluginName}/config`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ config }),
  });

  if (!res.ok) {
    await handleError("Failed to save plugin configuration", res);
  }

  return await res.json();
}
