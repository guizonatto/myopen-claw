export function buildUsageRouterRef(modelRef) {
  if (typeof modelRef !== "string" || !/^[a-z0-9][a-z0-9-]*\/.+$/i.test(modelRef)) {
    throw new TypeError(`invalid provider/model ref: ${modelRef}`);
  }
  return `usage-router/${modelRef}`;
}

export function parseUsageRouterRef(modelRef) {
  if (typeof modelRef !== "string" || !modelRef.startsWith("usage-router/")) {
    throw new TypeError(`invalid usage-router ref: ${modelRef}`);
  }

  const remainder = modelRef.slice("usage-router/".length);
  const slashIndex = remainder.indexOf("/");
  if (slashIndex <= 0 || slashIndex === remainder.length - 1) {
    throw new TypeError(`invalid usage-router ref: ${modelRef}`);
  }

  const provider = remainder.slice(0, slashIndex);
  const model = remainder.slice(slashIndex + 1);
  return {
    provider,
    model,
    modelRef: `${provider}/${model}`,
  };
}

