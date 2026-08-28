/**
 * Join class names, dropping anything absent.
 *
 * CSS-module lookups are typed `string | undefined` because `noUncheckedIndexedAccess`
 * is on — which is correct: a typo in a class name really does yield undefined.
 * This keeps that safety while producing a plain string for the `className` prop.
 */
export function cx(...values: Array<string | false | null | undefined>): string {
  return values.filter((value): value is string => Boolean(value)).join(' ')
}
