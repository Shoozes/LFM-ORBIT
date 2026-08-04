export type RequestGateHandle = {
  controller: AbortController;
};

export type RequestGate = {
  begin(): RequestGateHandle;
  isCurrent(request: RequestGateHandle): boolean;
  finish(request: RequestGateHandle): void;
  abort(): void;
};

export function createRequestGate(): RequestGate;
