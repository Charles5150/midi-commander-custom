// A configuration in a link: its CSV text, deflated and in base64url, after
// "#config=" in the page's address. The part after # never reaches a server,
// so opening the link loads the configuration in the browser and nowhere else.

export const PREFIX = "#config=";

async function through(bytes, stream) {
  const out = new Blob([bytes]).stream().pipeThrough(stream);
  return new Uint8Array(await new Response(out).arrayBuffer());
}

function toBase64Url(bytes) {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text) {
  const s = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

// The link for a configuration's CSV text, on the page at `base`
export async function shareLink(base, csv) {
  const packed = await through(new TextEncoder().encode(csv), new CompressionStream("deflate-raw"));
  return base.replace(/#.*$/, "") + PREFIX + toBase64Url(packed);
}

// The CSV bytes in a page address's fragment ("#config=…"), or null when it
// holds none. Throws when it holds one that is cut short or not one at all
export async function linkedCsv(hash) {
  if (!hash.startsWith(PREFIX)) return null;
  const text = hash.slice(PREFIX.length).trim();
  if (!/^[\w-]+$/.test(text)) throw new Error("the link is cut short or changed");
  try {
    return await through(fromBase64Url(text), new DecompressionStream("deflate-raw"));
  } catch {
    throw new Error("the link is cut short or changed");
  }
}
