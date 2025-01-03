"use client"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { useDispatch } from "react-redux"
import { setAuthenticated } from "@/store/reducers/authReducer"
import Link from "next/link"
import api from "@/utils/axios"

export default function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const router = useRouter()
  const dispatch = useDispatch()

  useEffect(() => {
    const token = localStorage.getItem("authToken")
    if (token) {
      dispatch(setAuthenticated(true))
      router.push("/chatbot")
    }
  }, [router, dispatch])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    try {
      const response = await api.post("/login", { email, password })
      console.log("--> token: ", response.data.token)
      const token = response.data.data.token
      localStorage.setItem("authToken", token)
      dispatch(setAuthenticated(true))
      router.push("/chatbot")
    } catch (error) {
      console.error("Login error:", error)
      dispatch(setAuthenticated(false))
      setError("Login failed. Please check your credentials.")
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-r from-gray-900 to-gray-800 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-white">
            Welcome Back
          </h2>
          <p className="mt-2 text-center text-sm text-gray-400">
            Sign in to continue to chatbot
          </p>
        </div>
        <form onSubmit={handleSubmit} className="mt-8 space-y-6 bg-gray-800/50 backdrop-blur-sm p-8 rounded-xl shadow-lg border border-gray-700">
          {error && <div className="text-red-400 text-sm text-center">{error}</div>}
          <div className="space-y-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
              className="appearance-none rounded-lg relative block w-full px-3 py-2 border border-gray-600 bg-gray-700/50 placeholder-gray-400 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent focus:z-10 sm:text-sm"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              className="appearance-none rounded-lg relative block w-full px-3 py-2 border border-gray-600 bg-gray-700/50 placeholder-gray-400 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent focus:z-10 sm:text-sm"
            />
          </div>
          <button
            type="submit"
            className="group relative w-full flex justify-center py-2.5 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-purple-500 transition-all duration-200"
          >
            Sign in
          </button>
          <div className="text-sm text-center mt-4">
            <Link href="/register" className="font-medium text-purple-400 hover:text-purple-300">
              Don not have an account? Register
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
