import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateRawSync } from "node:zlib";

const here = dirname(fileURLToPath(import.meta.url));
const project = resolve(here, "..");
const repository = resolve(project, "../..");
const output = resolve(process.argv[2] ?? join(dirname(repository), "okcanvas-connector-examples-organization-context-api-fake-step002r2.zip"));
if (process.argv[2]?.startsWith("-")) throw new Error("package-source accepts one positional output path");

const excluded = new Set(["node_modules", "dist", ".git"]);
function sourceFiles(root) {
  const result = [];
  for (const name of readdirSync(root).sort()) {
    const path = join(root, name);
    const rel = relative(repository, path).replaceAll("\\", "/");
    if (rel.split("/").some((part) => excluded.has(part))) continue;
    if (resolve(path) === output || resolve(path) === `${output}.sha256`) continue;
    if (statSync(path).isDirectory()) result.push(...sourceFiles(path));
    else result.push(path);
  }
  return result;
}

const crcTable = Array.from({ length: 256 }, (_, index) => {
  let value = index;
  for (let bit = 0; bit < 8; bit += 1) value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
  return value >>> 0;
});
function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}
function u16(value) { const b = Buffer.alloc(2); b.writeUInt16LE(value & 0xffff); return b; }
function u32(value) { const b = Buffer.alloc(4); b.writeUInt32LE(value >>> 0); return b; }

const dosTime = 0;
const dosDate = ((2026 - 1980) << 9) | (8 << 5) | 6;
const locals = [];
const centrals = [];
let offset = 0;
for (const path of sourceFiles(repository)) {
  const nameText = relative(dirname(repository), path).replaceAll("\\", "/");
  const name = Buffer.from(nameText, "utf8");
  const data = readFileSync(path);
  const compressed = deflateRawSync(data, { level: 9 });
  const crc = crc32(data);
  const local = Buffer.concat([
    u32(0x04034b50), u16(20), u16(0), u16(8), u16(dosTime), u16(dosDate),
    u32(crc), u32(compressed.length), u32(data.length), u16(name.length), u16(0), name, compressed,
  ]);
  locals.push(local);
  const central = Buffer.concat([
    u32(0x02014b50), u16(0x0314), u16(20), u16(0), u16(8), u16(dosTime), u16(dosDate),
    u32(crc), u32(compressed.length), u32(data.length), u16(name.length), u16(0), u16(0),
    u16(0), u16(0), u32(0o100644 << 16), u32(offset), name,
  ]);
  centrals.push(central);
  offset += local.length;
}
const centralBody = Buffer.concat(centrals);
const end = Buffer.concat([
  u32(0x06054b50), u16(0), u16(0), u16(centrals.length), u16(centrals.length),
  u32(centralBody.length), u32(offset), u16(0),
]);
const archive = Buffer.concat([...locals, centralBody, end]);
mkdirSync(dirname(output), { recursive: true });
try { unlinkSync(output); } catch {}
writeFileSync(output, archive);
const digest = createHash("sha256").update(archive).digest("hex");
writeFileSync(`${output}.sha256`, `${digest}  ${output.split(/[\\/]/).at(-1)}\n`);
console.log(JSON.stringify({ path: output, sha256: digest, entryCount: centrals.length, root: "okcanvas-connector-examples" }, null, 2));
