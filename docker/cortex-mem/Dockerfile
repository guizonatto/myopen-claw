FROM rust:bookworm AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN git config --global advice.detachedHead false

RUN GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch main https://github.com/sopaco/cortex-mem.git source

WORKDIR /build/source

RUN python3 - <<'PY'
from pathlib import Path
import re

main_path = Path("cortex-mem-service/src/main.rs")
main_source = main_path.read_text(encoding="utf-8")
main_source = main_source.replace(
    "use std::net::SocketAddr;",
    "use std::net::{IpAddr, SocketAddr};",
)
main_source = main_source.replace(
    "    let addr = SocketAddr::from(([127, 0, 0, 1], cli.port));",
    "    let addr = SocketAddr::from((cli.host.parse::<IpAddr>().unwrap_or(IpAddr::from([0, 0, 0, 0])), cli.port));",
)
main_path.write_text(main_source, encoding="utf-8")

state_path = Path("cortex-mem-service/src/state.rs")
state_source = state_path.read_text(encoding="utf-8")
state_source = re.sub(
    r'        let stats = sync_manager\.sync_all\(\)\.await\?;\s+        tracing::info!\(\s+            indexed_files = stats\.indexed_files,\s+            skipped_files = stats\.skipped_files,\s+            error_files = stats\.error_files,\s+            total_files = stats\.total_files,\s+            "Bootstrap vector sync completed"\s+        \);\s+        Ok\(\(\)\)',
    '''        match sync_manager.sync_all().await {
            Ok(stats) => tracing::info!(
                indexed_files = stats.indexed_files,
                skipped_files = stats.skipped_files,
                error_files = stats.error_files,
                total_files = stats.total_files,
                "Bootstrap vector sync completed"
            ),
            Err(e) => tracing::warn!("Bootstrap vector sync failed, continuing startup: {}", e),
        }
        Ok(())''',
    state_source,
    flags=re.MULTILINE,
)
state_path.write_text(state_source, encoding="utf-8")
PY

RUN cargo build --release -p cortex-mem-service

FROM debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/source/target/release/cortex-mem-service /usr/local/bin/cortex-mem-service

RUN mkdir -p /var/lib/cortex-mem

EXPOSE 8085

ENTRYPOINT ["cortex-mem-service", "--host", "0.0.0.0", "--port", "8085", "--data-dir", "/var/lib/cortex-mem"]
