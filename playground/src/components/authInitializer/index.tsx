"use client"

import { ReactNode, useEffect } from "react"
import { useRouter } from "next/navigation"
import {
  useAppDispatch,
  getOptionsFromLocal,
  getRandomChannel,
  getRandomUserId,
  useAppSelector,
} from "@/common"
import { setOptions, reset, fetchGraphDetails } from "@/store/reducers/global"
import { setAuthenticated } from "@/store/reducers/authReducer"
import { useGraphs } from "@/common/hooks"

interface AuthInitializerProps {
  children: ReactNode
}

const AuthInitializer = (props: AuthInitializerProps) => {
  const { children } = props
  const dispatch = useAppDispatch()
  const { initialize } = useGraphs()
  const selectedGraphId = useAppSelector(
    (state) => state.global.selectedGraphId,
  )
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)
  const router = useRouter()

  useEffect(() => {
    const verifyToken = async (token: string) => {
      try {
        const response = await fetch("http://localhost:8080/token/verify", {
          method: "POST",
          headers: {
            Authorization: token,
          },
        })
        if (!response.ok) {
          throw new Error("Token verification failed")
        }
        dispatch(setAuthenticated(true))
      } catch (error) {
        console.error("Token verification error:", error)
        localStorage.removeItem("authToken")
        router.push("/login")
      }
    }

    const token = localStorage.getItem("authToken")
    if (token) {
      verifyToken(token)
    } else if (!isAuthenticated) {
      router.push("/login")
      return
    }

    const options = getOptionsFromLocal()
    initialize()
    if (options && options.channel) {
      dispatch(reset())
      dispatch(setOptions(options))
    } else {
      dispatch(reset())
      dispatch(
        setOptions({
          channel: getRandomChannel(),
          userId: getRandomUserId(),
        }),
      )
    }
  }, [dispatch, isAuthenticated, router])

  useEffect(() => {
    if (selectedGraphId) {
      dispatch(fetchGraphDetails(selectedGraphId))
    }
  }, [selectedGraphId, dispatch])

  if (!isAuthenticated) {
    return null
  }

  return children
}

export default AuthInitializer
