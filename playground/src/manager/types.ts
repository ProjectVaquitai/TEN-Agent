/* eslint-disable @typescript-eslint/no-explicit-any */
export type EventHandler<T extends any[]> = (...data: T) => void
