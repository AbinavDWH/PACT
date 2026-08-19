export function xorChecksum(text: string): string {
  let value = 0;
  for (let i = 0; i < text.length; i++) {
    value ^= text.charCodeAt(i);
  }
  return value.toString(16).toUpperCase().padStart(2, "0");
}