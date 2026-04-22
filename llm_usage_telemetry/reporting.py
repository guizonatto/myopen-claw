"""
Tool: reporting
Função: Renderiza agregados de telemetria em texto e formato compatível com Discord.
Usar quando: Precisar transformar métricas agregadas em um relatório operacional legível.

ENV_VARS:
  - (nenhuma)

DB_TABLES:
  - (nenhuma)
"""
from dataclasses import dataclass


@dataclass(slots=True)
class UsageSummaryRow:
    service: str
    provider: str
    model: str
    request_kind: str
    attempts: int
    successes: int
    failures: int
    rpm_avg: float
    rpm_peak: int
    input_tokens_exact: int
    output_tokens_exact: int
    total_tokens_exact: int
    input_tokens_estimated: int
    output_tokens_estimated: int
    total_tokens_estimated: int
    token_quality: str


@dataclass(slots=True)
class ProviderSummary:
    provider: str
    enabled_models: int
    total_models: int
    day_requests: int
    day_tokens: int


def format_token_quality(exact_tokens: int, estimated_tokens: int) -> str:
    exact_tokens = int(exact_tokens or 0)
    estimated_tokens = int(estimated_tokens or 0)
    total = exact_tokens + estimated_tokens

    if total <= 0:
        return "n/a"
    if exact_tokens <= 0:
        return f"{total} (estimated)"
    if estimated_tokens <= 0:
        return f"{total} (exact)"
    return f"{total} (mixed: {exact_tokens} exact + {estimated_tokens} estimated)"


def _compact_int(value: int | None) -> str:
    value = int(value or 0)
    if value >= 1_000_000_000:
        scaled = value / 1_000_000_000
        label = f"{scaled:.1f}B"
    elif value >= 1_000_000:
        scaled = value / 1_000_000
        label = f"{scaled:.1f}M"
    elif value >= 1_000:
        scaled = value / 1_000
        label = f"{scaled:.1f}k"
    else:
        return str(value)
    return label.replace(".0", "")


def _format_daily_limits(
    provider: str,
    model: str,
    *,
    model_limits: dict[tuple[str, str], dict[str, int | None]] | None,
    day_usage: dict[tuple[str, str], tuple[int, int]] | None,
) -> str:
    if not model_limits or not day_usage:
        return ""

    key = (provider, model)
    limits = model_limits.get(key) or {}
    rpd = limits.get("rpd")
    tpd = limits.get("tpd")
    if rpd is None and tpd is None:
        return ""

    used_reqs, used_tokens = day_usage.get(key, (0, 0))
    parts: list[str] = []
    if rpd is not None:
        parts.append(f"rpd={used_reqs}/{int(rpd)}")
    if tpd is not None:
        parts.append(f"tpd={_compact_int(used_tokens)}/{_compact_int(int(tpd))}")
    return " " + " ".join(parts) if parts else ""


def _render_provider_section(providers: list[ProviderSummary] | None) -> str:
    if not providers:
        return ""
    lines = ["**Providers (hoje)**"]
    for item in providers:
        lines.append(
            f"- `{item.provider}` models={int(item.enabled_models)}/{int(item.total_models)} day_reqs={int(item.day_requests)} day_tokens={_compact_int(item.day_tokens)}"
        )
    return "\n".join(lines)


def _render_section(
    title: str,
    rows: list[UsageSummaryRow],
    *,
    model_limits: dict[tuple[str, str], dict[str, int | None]] | None = None,
    day_usage: dict[tuple[str, str], tuple[int, int]] | None = None,
) -> str:
    if not rows:
        return f"**{title}**\n- sem eventos"

    lines = [f"**{title}**"]
    for row in rows:
        model_ref = f"{row.provider}/{row.model}"
        token_label = format_token_quality(
            row.total_tokens_exact,
            row.total_tokens_estimated,
        )
        daily_limits = _format_daily_limits(
            row.provider,
            row.model,
            model_limits=model_limits,
            day_usage=day_usage,
        )
        lines.append(
            (
                f"- `{row.service}` | `{model_ref}` | `{row.request_kind}` | "
                f"attempts={row.attempts} failures={row.failures} "
                f"rpm_avg={row.rpm_avg:.2f} rpm_peak={row.rpm_peak} "
                f"tokens={token_label}{daily_limits}"
            )
        )
    return "\n".join(lines)


def build_discord_report(
    last_hour_rows: list[UsageSummaryRow],
    day_rows: list[UsageSummaryRow],
    timezone_name: str,
    bucket_label: str,
    *,
    provider_summaries: list[ProviderSummary] | None = None,
    model_limits: dict[tuple[str, str], dict[str, int | None]] | None = None,
    day_usage: dict[tuple[str, str], tuple[int, int]] | None = None,
) -> str:
    provider_section = _render_provider_section(provider_summaries)
    parts: list[str] = [
        "# LLM Usage Report",
        f"Janela: `{bucket_label}`",
        f"Timezone: `{timezone_name}`",
        "",
    ]
    if provider_section:
        parts.append(provider_section)
        parts.append("")
    parts.extend(
        [
            _render_section("Ultima hora", last_hour_rows, model_limits=model_limits, day_usage=day_usage),
            "",
            _render_section("Acumulado do dia", day_rows, model_limits=model_limits, day_usage=day_usage),
        ]
    )
    return "\n".join(parts).strip()
