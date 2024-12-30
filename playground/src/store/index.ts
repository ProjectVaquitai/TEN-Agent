"use client"

import globalReducer from "./reducers/global"
import authReducer from "./reducers/authReducer"
import { configureStore } from "@reduxjs/toolkit"

export const makeStore = () => {
  return configureStore({
    reducer: {
      global: globalReducer,
      auth: authReducer,
    },
    devTools: process.env.NODE_ENV !== "production",
  })
}

// Create a store instance
export const store = makeStore()

export * from "./provider"
export type AppStore = ReturnType<typeof makeStore>
export type RootState = ReturnType<AppStore["getState"]>
export type AppDispatch = AppStore["dispatch"]
