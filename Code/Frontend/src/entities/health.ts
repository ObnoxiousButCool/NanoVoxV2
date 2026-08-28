/**
 * Health types, mirroring the backend's `/health` response.
 *
 * Hand-written for P0. From P4 these types are generated from the backend's
 * OpenAPI document so a contract change breaks the build rather than the page.
 */

export type ComponentStatus = 'up' | 'down'

export interface ComponentHealth {
  readonly name: string
  readonly status: ComponentStatus
  readonly detail: string | null
}

export interface HealthReport {
  readonly status: ComponentStatus
  readonly application: string
  readonly version: string
  readonly environment: string
  readonly checked_at: string
  readonly components: readonly ComponentHealth[]
}
