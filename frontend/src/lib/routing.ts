export const CENTRAL_ROUTES = [
  "",
  "login",
  "dashboard",
  "customers",
  "users",
  "activity",
  "alerts",
  "profile",
];
export const RESERVED_SLUGS = new Set([
  ...CENTRAL_ROUTES,
  "api",
  "admin",
  "logout",
  "organizations",
  "static",
  "media",
  "fonts",
  "assets",
  "health",
  "robots",
  "sitemap",
  "favicon",
  "next",
  "_next",
  "auth",
  "settings",
  "account",
  "support",
  "help",
  "register",
  "signup",
  "portal",
]);
export function isPortalSlug(value: string) {
  return (
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value) &&
    value.length >= 3 &&
    value.length <= 48 &&
    !RESERVED_SLUGS.has(value)
  );
}
