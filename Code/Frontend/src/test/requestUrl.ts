/**
 * The URL a `fetch` call was made to, from any of the three things it accepts.
 *
 * Every stub in the suite routes on the URL, and `String(input)` is the obvious
 * way to get one and the wrong one: `fetch` takes `string | URL | Request`, and
 * a `Request` has no useful `toString`, so it stringifies to
 * `[object Object]`. Nothing throws — the route simply never matches and the
 * stub quietly answers with whatever its default branch returns, which is a
 * test that passes while exercising the wrong endpoint.
 *
 * `@typescript-eslint/no-base-to-string` is what catches this, and it is right
 * to.
 */
export function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}
