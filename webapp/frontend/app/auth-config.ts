const clientId = process.env.NEXT_PUBLIC_MSAL_CLIENT_ID!;
const tenantId = process.env.NEXT_PUBLIC_MSAL_TENANT_ID!;

export const msalConfig = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    // Uses current origin so it works in both local dev and production.
    // The redirect URI must be registered in the Azure app registration.
    redirectUri: typeof window !== "undefined" ? `${window.location.origin}/redirect.html` : "",
  },
  cache: {
    cacheLocation: "sessionStorage" as const,
  },
};

export const backendApiScope = `api://${clientId}/access_as_user`;

export const loginRequest = {
  scopes: [backendApiScope],
};
