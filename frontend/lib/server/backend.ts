import "server-only";

export function backendUrl(path: string) {
  const configured = process.env.HEALER_API_URL || "https://spectreli.onrender.com";
  const token = process.env.HEALER_SERVER_TOKEN;
  if (!configured || !token) throw new Error("Diagnostics backend is not configured");
  const url = new URL(path, configured);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))
    throw new Error("Diagnostics backend must use HTTPS or loopback HTTP");
  return { url, token };
}
