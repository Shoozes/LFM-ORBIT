export function createRequestGate() {
  let activeRequest = null;

  return {
    begin() {
      activeRequest?.controller.abort();
      const request = { controller: new AbortController() };
      activeRequest = request;
      return request;
    },

    isLatest(request) {
      return activeRequest === request;
    },

    isCurrent(request) {
      return activeRequest === request && !request.controller.signal.aborted;
    },

    finish(request) {
      if (activeRequest === request) {
        activeRequest = null;
      }
    },

    abort() {
      activeRequest?.controller.abort();
      activeRequest = null;
    },
  };
}
