declare function require(module: string): any;
declare const process: { env: Record<string, string | undefined> };
const { execSync } = require("child_process") as {
  execSync: (cmd: string, opts?: { cwd?: string }) => string | Buffer;
};

const handler = async (event: any) => {
  if (event.type !== "command" || event.action !== "stop") return;

  const stagingDir = "/root/.openclaw/git-staging";
  const workspaceDir = process.env.OPENCLAW_WORKSPACE ?? "/root/.openclaw/workspace";
  const token = process.env.GITHUB_TOKEN;
  const org = process.env.GITHUB_ORG;
  const repo = process.env.GITHUB_REPO;

  if (!token || !org || !repo) {
    console.warn("[github-push] GITHUB_TOKEN, GITHUB_ORG ou GITHUB_REPO não definidos — push ignorado.");
    return;
  }

  try {
    // Verificar se staging é um git repo
    try {
      execSync("git rev-parse --git-dir", { cwd: stagingDir });
    } catch {
      console.warn("[github-push] Staging dir não é um repositório git — reinicie o container para inicializar.");
      return;
    }

    // Sincronizar workspace → staging clone
    for (const dir of ["configs", "skills", "crons", "scripts"]) {
      const src = `${workspaceDir}/${dir}`;
      const dst = `${stagingDir}/${dir}`;
      try {
        execSync(`rm -rf "${dst}" && cp -r "${src}" "${dst}"`);
      } catch {}
    }

    // Atualizar remote URL (token pode rotacionar)
    execSync(
      `git remote set-url origin https://${token}@github.com/${org}/${repo}.git`,
      { cwd: stagingDir }
    );

    // Pull para reduzir conflitos
    try {
      execSync("git pull origin main --ff-only --quiet", { cwd: stagingDir });
    } catch {}

    const status = execSync("git status --porcelain", { cwd: stagingDir })
      .toString()
      .trim();

    if (!status) {
      console.log("[github-push] Sem alterações — nada a commitar.");
      return;
    }

    const timestamp = new Date().toISOString().slice(0, 16).replace("T", " ");
    execSync("git add -A", { cwd: stagingDir });
    execSync(`git commit -m "chore: workspace auto-push ${timestamp}"`, { cwd: stagingDir });
    execSync("git push origin main", { cwd: stagingDir });

    console.log("[github-push] Push realizado com sucesso.");
    event.messages?.push("Alterações enviadas ao GitHub.");
  } catch (err: any) {
    console.error("[github-push] Erro ao fazer push:", err.message);
  }
};

export default handler;
