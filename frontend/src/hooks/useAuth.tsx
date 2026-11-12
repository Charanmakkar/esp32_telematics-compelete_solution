import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, setCsrf } from "../services/api";
import type { AuthResponse, User } from "../services/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (current: string, next: string) => Promise<void>;
}
const AuthContext = createContext<AuthContextValue | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const accept = useCallback((response: AuthResponse) => {
    setUser(response.user);
    setCsrf(response.csrf_token);
  }, []);
  useEffect(() => {
    let active = true;
    api
      .me()
      .then((response) => {
        if (active) accept(response);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [accept]);
  useEffect(() => {
    const expired = () => {
      setCsrf("");
      setUser(null);
    };
    window.addEventListener("navsphere:unauthorized", expired);
    return () => window.removeEventListener("navsphere:unauthorized", expired);
  }, []);
  const login = useCallback(
    async (username: string, password: string) => {
      accept(await api.login(username, password));
    },
    [accept],
  );
  const logout = useCallback(async () => {
    await api.logout();
    setCsrf("");
    setUser(null);
  }, []);
  const changePassword = useCallback(
    async (current: string, next: string) => {
      accept(await api.password(current, next));
    },
    [accept],
  );
  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, changePassword }}
    >
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is required");
  return value;
}
