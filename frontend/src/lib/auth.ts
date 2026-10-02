export type RetainAIUser = {
  id: string;
  name: string;
  email: string;
};

const SESSION_KEY = "retainai_active_user";
const REGISTERED_USERS_KEY = "retainai_registered_users";

export function getRetainAISession(): RetainAIUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearRetainAISession(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(SESSION_KEY);
    document.cookie = "retainai_account=; path=/; max-age=0";
  } catch {
    // ignore
  }
}

export async function loginRetainAI(email: string, password: string): Promise<RetainAIUser> {
  const cleanEmail = email.trim().toLowerCase();
  if (!cleanEmail) {
    throw new Error("Please enter your email address.");
  }
  if (!password) {
    throw new Error("Please enter your password.");
  }
  if (!cleanEmail.includes("@") || !cleanEmail.includes(".")) {
    throw new Error("Please enter a valid email address.");
  }

  // Artificial slight delay for authentic smooth loading state (300ms)
  await new Promise((resolve) => setTimeout(resolve, 300));

  let registeredUsers: Array<{ email: string; passwordHash: string; name: string }> = [];
  try {
    const raw = localStorage.getItem(REGISTERED_USERS_KEY);
    if (raw) registeredUsers = JSON.parse(raw);
  } catch {
    registeredUsers = [];
  }

  const existing = registeredUsers.find((u) => u.email.toLowerCase() === cleanEmail);
  if (existing) {
    if (existing.passwordHash !== password) {
      throw new Error("Incorrect password. Please try again.");
    }
    const user: RetainAIUser = {
      id: cleanEmail,
      name: existing.name || cleanEmail.split("@")[0],
      email: cleanEmail,
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
    document.cookie = `retainai_account=${encodeURIComponent(user.email)}; path=/; max-age=2592000`;
    return user;
  }

  // If no user has been registered yet in local storage, allow seamless initial login
  const defaultName = cleanEmail.split("@")[0];
  const user: RetainAIUser = {
    id: cleanEmail,
    name: defaultName.charAt(0).toUpperCase() + defaultName.slice(1),
    email: cleanEmail,
  };
  // Save to registered list
  registeredUsers.push({ email: cleanEmail, passwordHash: password, name: user.name });
  try {
    localStorage.setItem(REGISTERED_USERS_KEY, JSON.stringify(registeredUsers));
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
    document.cookie = `retainai_account=${encodeURIComponent(user.email)}; path=/; max-age=2592000`;
  } catch {
    // ignore storage error
  }

  return user;
}

export async function signupRetainAI(name: string, email: string, password: string, confirmPassword?: string): Promise<RetainAIUser> {
  const cleanEmail = email.trim().toLowerCase();
  const cleanName = name.trim();

  if (!cleanEmail) {
    throw new Error("Please enter your email address.");
  }
  if (!cleanEmail.includes("@") || !cleanEmail.includes(".")) {
    throw new Error("Please enter a valid email address.");
  }
  if (!password) {
    throw new Error("Please create a password.");
  }
  if (password.length < 6) {
    throw new Error("Password must be at least 6 characters.");
  }
  if (confirmPassword !== undefined && password !== confirmPassword) {
    throw new Error("Passwords do not match.");
  }

  await new Promise((resolve) => setTimeout(resolve, 350));

  let registeredUsers: Array<{ email: string; passwordHash: string; name: string }> = [];
  try {
    const raw = localStorage.getItem(REGISTERED_USERS_KEY);
    if (raw) registeredUsers = JSON.parse(raw);
  } catch {
    registeredUsers = [];
  }

  const existingIndex = registeredUsers.findIndex((u) => u.email.toLowerCase() === cleanEmail);
  const displayName = cleanName || cleanEmail.split("@")[0];

  if (existingIndex >= 0) {
    // Update existing user credentials
    registeredUsers[existingIndex] = { email: cleanEmail, passwordHash: password, name: displayName };
  } else {
    registeredUsers.push({ email: cleanEmail, passwordHash: password, name: displayName });
  }

  const user: RetainAIUser = {
    id: cleanEmail,
    name: displayName,
    email: cleanEmail,
  };

  try {
    localStorage.setItem(REGISTERED_USERS_KEY, JSON.stringify(registeredUsers));
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
    document.cookie = `retainai_account=${encodeURIComponent(user.email)}; path=/; max-age=2592000`;
  } catch {
    // ignore storage error
  }

  return user;
}
