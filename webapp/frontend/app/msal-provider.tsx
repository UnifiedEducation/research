"use client";

import { ReactNode, createContext, useContext, useEffect, useState, useCallback } from "react";
import { msalConfig, loginRequest } from "./auth-config";

// We use msal-browser via CDN script tag because @azure/msal-browser v5 (npm)
// has SSR/initialization issues with Next.js 16 + React 19.
// The CDN version (v2) works reliably in the browser.

interface MsalContextType {
  isAuthenticated: boolean;
  account: { name: string; username: string } | null;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const MsalContext = createContext<MsalContextType>({
  isAuthenticated: false,
  account: null,
  login: async () => {},
  logout: async () => {},
  getToken: async () => null,
});

export const useAuth = () => useContext(MsalContext);

// Global ref to MSAL instance (set after script loads)
let pcaInstance: any = null;

export default function MsalProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [account, setAccount] = useState<{ name: string; username: string } | null>(null);

  const initMsal = useCallback(async () => {
    const msal = (window as any).msal;
    if (!msal) return;

    pcaInstance = new msal.PublicClientApplication(msalConfig);

    try {
      const resp = await pcaInstance.handleRedirectPromise();
      if (resp?.account) {
        pcaInstance.setActiveAccount(resp.account);
        setAccount({ name: resp.account.name, username: resp.account.username });
        setIsAuthenticated(true);
      }
    } catch (e) {
      console.warn("handleRedirectPromise:", e);
      sessionStorage.clear();
    }

    if (!pcaInstance.getActiveAccount()) {
      const accounts = pcaInstance.getAllAccounts();
      if (accounts.length > 0) {
        pcaInstance.setActiveAccount(accounts[0]);
        setAccount({ name: accounts[0].name, username: accounts[0].username });
        setIsAuthenticated(true);
      }
    }

    setReady(true);
  }, []);

  const login = useCallback(async () => {
    if (!pcaInstance) return;
    try {
      const resp = await pcaInstance.loginPopup(loginRequest);
      if (resp?.account) {
        pcaInstance.setActiveAccount(resp.account);
        setAccount({ name: resp.account.name, username: resp.account.username });
        setIsAuthenticated(true);
      }
    } catch (e) {
      console.error("Login error:", e);
    }
  }, []);

  const logout = useCallback(async () => {
    if (!pcaInstance) return;
    try {
      await pcaInstance.logoutPopup();
      setAccount(null);
      setIsAuthenticated(false);
    } catch (e) {
      console.error("Logout error:", e);
    }
  }, []);

  const getToken = useCallback(async () => {
    if (!pcaInstance) return null;
    const activeAccount = pcaInstance.getActiveAccount();
    if (!activeAccount) return null;
    try {
      const resp = await pcaInstance.acquireTokenSilent({
        scopes: loginRequest.scopes,
        account: activeAccount,
      });
      return resp.accessToken;
    } catch (e) {
      // Fall back to popup if silent fails
      try {
        const resp = await pcaInstance.acquireTokenPopup({
          scopes: loginRequest.scopes,
        });
        return resp.accessToken;
      } catch (e2) {
        console.error("Token acquisition failed:", e2);
        return null;
      }
    }
  }, []);

  useEffect(() => {
    // Load MSAL script dynamically
    if ((window as any).msal) {
      initMsal();
      return;
    }
    const script = document.createElement("script");
    script.src = "https://alcdn.msauth.net/browser/2.38.0/js/msal-browser.min.js";
    script.onload = () => initMsal();
    document.head.appendChild(script);
  }, [initMsal]);

  if (!ready) return null;

  return (
    <MsalContext.Provider value={{ isAuthenticated, account, login, logout, getToken }}>
      {children}
    </MsalContext.Provider>
  );
}
