// npm entry point; use the project's existing Python, with portable fallbacks.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = fileURLToPath(new URL("../", import.meta.url));
const local = path.join(root, "backend", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const candidates = [process.env.PYTHON, existsSync(local) ? local : null, "python", "python3"].filter(Boolean);
for (const python of candidates) {
  const result = spawnSync(python, [path.join(root, "scripts/sync_version.py")], { stdio: "inherit" });
  if (result.error?.code === "ENOENT") continue;
  process.exit(result.status ?? 1);
}
throw new Error("Python is required to prepare the shared software version.");
