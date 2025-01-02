"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useDispatch } from "react-redux"
import { setAuthenticated } from "@/store/reducers/authReducer"

export default function Logout() {
  const router = useRouter()
  const dispatch = useDispatch()

  useEffect(() => {
    const logout = async () => {
      const token = localStorage.getItem("authToken")
      if (token) {
        try {
          const response = await fetch("http://localhost:8080/logout", {
            method: "POST",
            headers: {
              Authorization: token,
            },
          })
          if (!response.ok) {
            throw new Error("Logout failed")
          }
          localStorage.removeItem("authToken")
          dispatch(setAuthenticated(false))
          router.push("/login")
        } catch (error) {
          console.error("Logout error:", error)
        }
      } else {
        router.push("/login")
      }
    }
    logout()
  }, [router, dispatch])

  return <div>Logging out...</div>
}
