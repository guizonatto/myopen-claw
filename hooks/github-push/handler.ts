declare function require(module: string): any;
declare const process: { env: Record<string, string | undefined> };
const { execSync } = require("child_process") as { execSync: (cmd: string, opts?: { cwd?: string }) => string };

const handler = async (event: any) => {
  if (event.type !== "command" || event.action !== "stop") return;

  const workspaceDir = process.env.OPENCLAW_WORKSPACE ?? "/root/.openclaw/workspace";
  const token = process.env.GITHUB_TOKEN;
  const org = process.env.GITHUB_ORG;
  const repo = process.env.GITHUB_REPO;

  if (!token || !org || !repo) {
    console.warn("[github-push] GITHUB_TOKEN, GITHUB_ORG ou GITHUB_REPO não definidos — push ignorado.");
    return;
  }

  try {
    const status = execSync("git status --porcelain", { cwd: workspaceDir })
      .toString()
      .trim();

    if (!status) {
      console.log("[github-push] Sem alterações — nada a commitar.");
      return;
    }

    const timestamp = new Date().toISOString().slice(0, 16).replace("T", " ");
    execSync("git add -A", { cwd: workspaceDir });
    execSync(`git commit -m "chore: auto-push ${timestamp}"`, { cwd: workspaceDir });
    execSync(
      `git push https://${token}@github.com/${org}/${repo}.git main`,
      { cwd: workspaceDir }
    );

    console.log("[github-push] Push realizado com sucesso.");
    event.messages.push("Alterações enviadas ao GitHub.");
  } catch (err: any) {
    console.error("[github-push] Erro ao fazer push:", err.message);
  }
};

export default handler;
