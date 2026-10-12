"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { api, ApiError, mutate, resetCsrf } from "@/lib/api";
import type { User } from "@/lib/types";

type Session = {
  user: User | null;
  loading: boolean;
  error: string | null;
  setUser: (user: User | null) => void;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};
const AuthContext = createContext<Session | null>(null);
const ToastContext = createContext<
  (message: string, variant?: "success" | "error") => void
>(() => {});
export const useAuth = () => {
  const result = useContext(AuthContext);
  if (!result) throw new Error("Missing session provider");
  return result;
};
export const useToast = () => useContext(ToastContext);
export function Providers({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toasts, setToasts] = useState<
    { id: number; message: string; variant: "success" | "error" }[]
  >([]);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUser(await api<User>("auth/me/"));
    } catch (error) {
      setUser(null);
      if (!(error instanceof ApiError) || error.status !== 401)
        setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    api<User>("auth/me/", { signal: controller.signal })
      .then(setUser)
      .catch((error) => {
        if (error.name === "AbortError") return;
        if (!(error instanceof ApiError) || error.status !== 401)
          setError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    const expired = () => {
      resetCsrf();
      setUser(null);
      setError(null);
    };
    window.addEventListener("madar:session-expired", expired);
    return () => {
      controller.abort();
      window.removeEventListener("madar:session-expired", expired);
    };
  }, []);
  const toast = useCallback(
    (message: string, variant: "success" | "error" = "success") => {
      const id = Date.now() + Math.random();
      setToasts((items) => [...items, { id, message, variant }]);
      window.setTimeout(
        () => setToasts((items) => items.filter((item) => item.id !== id)),
        6500,
      );
    },
    [],
  );
  const logout = async () => {
    await mutate("auth/logout/", "POST", {});
    resetCsrf();
    setUser(null);
  };
  return (
    <AuthContext.Provider
      value={{ user, loading, error, setUser, logout, refresh }}
    >
      <ToastContext.Provider value={toast}>
        {children}
        <div className="toast-stack" aria-live="polite" aria-atomic="false">
          {toasts.map((item) => (
            <div
              className={`toast ${item.variant}`}
              key={item.id}
              role={item.variant === "error" ? "alert" : "status"}
            >
              {item.variant === "success" ? (
                <CheckCircle2 size={19} />
              ) : (
                <CircleAlert size={19} />
              )}
              <span>{item.message}</span>
              <button
                className="icon-button"
                aria-label="بستن پیام"
                onClick={() =>
                  setToasts((items) =>
                    items.filter((current) => current.id !== item.id),
                  )
                }
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      </ToastContext.Provider>
    </AuthContext.Provider>
  );
}
