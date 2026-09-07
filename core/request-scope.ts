export class StaleScopeError extends Error {
  constructor() {
    super("La sesión o el sitio cambió durante la solicitud");
  }
}

// A generation, rather than just a user/site string, also invalidates requests
// when someone signs out and then signs back in to the same account.
export class RequestScope {
  private key = "";
  private generation = 0;
  enter(key: string) {
    if (this.key !== key) {
      this.key = key;
      this.invalidate();
    }
    return this.generation;
  }
  invalidate() {
    this.generation++;
  }
  isCurrent(generation: number) {
    return this.generation === generation;
  }
  assertCurrent(generation: number) {
    if (!this.isCurrent(generation)) throw new StaleScopeError();
  }
}
