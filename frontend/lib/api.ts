const API_BASE_URL = '';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export interface RegisterRequest {
  name: string;
  username: string;
  email: string;
  password: string;
}

export interface RegisterResponse {
  id: number;
  name: string;
  username: string;
  email: string;
  is_superuser: boolean;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiError {
  detail: string | ValidationError[];
}

export interface FormattedError {
  message: string;
  fieldErrors: Record<string, string>;
}

function formatApiError(error: ApiError): FormattedError {
  if (typeof error.detail === 'string') {
    return { message: error.detail, fieldErrors: {} };
  }

  if (Array.isArray(error.detail)) {
    const fieldErrors: Record<string, string> = {};
    const messages: string[] = [];

    for (const err of error.detail) {
      const field = err.loc[err.loc.length - 1];
      if (typeof field === 'string' && field !== 'body') {
        fieldErrors[field] = err.msg;
      } else {
        messages.push(err.msg);
      }
    }

    return {
      message: messages.length > 0 ? messages.join('. ') : Object.values(fieldErrors)[0] || 'Validation failed',
      fieldErrors,
    };
  }

  return { message: 'An unexpected error occurred', fieldErrors: {} };
}

export class ApiRequestError extends Error {
  fieldErrors: Record<string, string>;

  constructor(formatted: FormattedError) {
    super(formatted.message);
    this.name = 'ApiRequestError';
    this.fieldErrors = formatted.fieldErrors;
  }
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
  } catch {
    throw new ApiRequestError({
      message: 'Unable to connect to server. Please check your internet connection.',
      fieldErrors: {},
    });
  }

  if (!response.ok) {
    try {
      const error: ApiError = await response.json();
      throw new ApiRequestError(formatApiError(error));
    } catch (e) {
      if (e instanceof ApiRequestError) throw e;
      throw new ApiRequestError({
        message: 'Login failed. Please try again.',
        fieldErrors: {},
      });
    }
  }

  return response.json();
}

export async function register(data: RegisterRequest): Promise<RegisterResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
  } catch {
    throw new ApiRequestError({
      message: 'Unable to connect to server. Please check your internet connection.',
      fieldErrors: {},
    });
  }

  if (!response.ok) {
    try {
      const error: ApiError = await response.json();
      throw new ApiRequestError(formatApiError(error));
    } catch (e) {
      if (e instanceof ApiRequestError) throw e;
      throw new ApiRequestError({
        message: 'Registration failed. Please try again.',
        fieldErrors: {},
      });
    }
  }

  return response.json();
}
